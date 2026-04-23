"""OAuth2/OIDC authentication: JWT validation and current user resolution."""
import json
import logging
import urllib.request
from typing import Any

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.db import UserModel

logger = logging.getLogger(__name__)

# When OIDC is enabled, require Bearer token for protected routes.
security = HTTPBearer(auto_error=False)

# In-memory cache for JWKS (kid -> key). Refreshed when kid is missing.
_jwks_cache: dict[str, Any] = {}
_jwks_uri_cached: str | None = None


def _oidc_discovery_url() -> str:
    issuer = (settings.oidc_issuer_url or "").rstrip("/")
    return f"{issuer}/.well-known/openid-configuration"


def _get_jwks_uri() -> str:
    """Fetch OIDC discovery and return jwks_uri."""
    url = _oidc_discovery_url()
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:  # nosec B310 – URL from trusted config (OIDC_ISSUER_URL)
            data = json.loads(resp.read().decode())
            return data.get("jwks_uri") or ""
    except Exception as e:
        logger.warning("OIDC discovery failed for %s: %s", url, e)
        return ""


def _load_jwks(jwks_uri: str) -> dict[str, Any]:
    """Fetch JWKS and return dict kid -> public key (for jwt.decode)."""
    req = urllib.request.Request(jwks_uri, method="GET")
    with urllib.request.urlopen(req, timeout=5) as resp:  # nosec B310 – URL from OIDC discovery (trusted issuer)
        jwks = json.loads(resp.read().decode())
    keys = {}
    for jwk in jwks.get("keys", []):
        kid = jwk.get("kid")
        if not kid:
            continue
        jwk_str = json.dumps(jwk)
        try:
            kty = jwk.get("kty", "")
            if kty == "RSA":
                keys[kid] = jwt.algorithms.RSAAlgorithm.from_jwk(jwk_str)
            elif kty == "EC":
                keys[kid] = jwt.algorithms.ECAlgorithm.from_jwk(jwk_str)
            else:
                continue
        except Exception as exc:
            logger.debug("Failed to parse JWK (kid=%s): %s", kid, exc)
            continue
    return keys


def _get_signing_key(token: str):
    """Resolve signing key for token from JWKS (cache by kid and jwks_uri)."""
    global _jwks_cache, _jwks_uri_cached
    try:
        unverified = jwt.get_unverified_header(token)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token header")
    kid = unverified.get("kid")
    if not kid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token missing kid")
    if kid not in _jwks_cache:
        # Re-use cached jwks_uri to avoid fetching OIDC discovery on every cache miss
        jwks_uri = _jwks_uri_cached or _get_jwks_uri()
        if not jwks_uri:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Could not obtain JWKS from issuer",
            )
        _jwks_uri_cached = jwks_uri
        _jwks_cache = _load_jwks(jwks_uri)
        logger.debug("JWKS cache refreshed", extra={"kid": kid, "key_count": len(_jwks_cache)})
        if kid not in _jwks_cache:
            # kid truly unknown even after refresh – key may have rotated; try fresh discovery
            fresh_uri = _get_jwks_uri()
            if fresh_uri and fresh_uri != jwks_uri:
                logger.debug("JWKS key rotation detected, fetching fresh JWKS", extra={"kid": kid})
                _jwks_uri_cached = fresh_uri
                _jwks_cache = _load_jwks(fresh_uri)
            if kid not in _jwks_cache:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Signing key not found",
                )
    return _jwks_cache[kid]


_security_audit_logger = logging.getLogger("app.security.audit")


def _verify_jwt(token: str) -> dict[str, Any]:
    """Verify JWT with JWKS from OIDC issuer. Returns payload (sub, email, preferred_username, etc.)."""
    issuer = (settings.oidc_issuer_url or "").rstrip("/")
    if not issuer:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OIDC issuer not configured",
        )
    key = _get_signing_key(token)
    try:
        algorithms = ["RS256", "RS384", "RS512", "ES256", "ES384", "ES512"]
        # Use oidc_audience if set; fall back to oidc_client_id to prevent cross-app token reuse
        effective_audience = settings.oidc_audience or settings.oidc_client_id or None
        options = {"verify_aud": effective_audience is not None}
        payload = jwt.decode(
            token,
            key,
            algorithms=algorithms,
            audience=effective_audience,
            issuer=issuer,
            options=options,
        )
        return payload
    except jwt.ExpiredSignatureError:
        _security_audit_logger.warning(
            "Authentication failed: token expired",
            extra={"event": "auth_failure", "reason": "token_expired"},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
        )
    except jwt.InvalidTokenError as e:
        _security_audit_logger.warning(
            "Authentication failed: invalid token",
            extra={"event": "auth_failure", "reason": "invalid_token", "detail": str(e)[:100]},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )


async def get_current_user_oidc(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
):
    """Resolve current user from OIDC Bearer token. Validates JWT and ensures user exists in DB (create on first login)."""
    if not credentials or credentials.credentials is None:
        _security_audit_logger.warning(
            "Authentication failed: no Bearer token provided",
            extra={"event": "auth_failure", "reason": "no_credentials"},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = _verify_jwt(credentials.credentials)
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing sub",
        )
    email = payload.get("email") or payload.get("mail")
    if isinstance(email, list):
        email = email[0] if email else None
    preferred_username = payload.get("preferred_username") or payload.get("name") or sub
    display_name = (payload.get("name") or preferred_username or sub)[:200]

    result = await db.execute(select(UserModel).where(UserModel.oidc_sub == sub))
    user = result.scalar_one_or_none()
    if user:
        # Optionally update email/display_name from token (e.g. if changed in IdP)
        if email and (user.email or "") != email:
            user.email = email[:320] if len(email) > 320 else email
        if (user.display_name or "").strip() == "" or user.display_name == "Standardnutzer":
            user.display_name = display_name
        await db.flush()
        await db.refresh(user)
        return user

    # First login: create user with default RBAC role
    new_user = UserModel(
        oidc_sub=sub,
        display_name=display_name,
        email=email[:320] if email and len(email) > 320 else (email or None),
        role=settings.rbac_default_role if settings.rbac_default_role in ("viewer", "editor", "admin") else "viewer",
        preferences={"theme": "system", "language": "de"},
    )
    db.add(new_user)
    await db.flush()
    await db.refresh(new_user)
    logger.info("New OIDC user created on first login", extra={"user_id": str(new_user.id), "role": new_user.role})
    _security_audit_logger.info(
        "Authentication successful: new user provisioned",
        extra={"event": "auth_success", "user_id": str(new_user.id), "reason": "first_login"},
    )
    return new_user


async def get_current_user_fallback(db: AsyncSession = Depends(get_db)):
    """Resolve current user from CURRENT_USER_ID or default user (when OIDC is disabled)."""
    import uuid
    raw = settings.current_user_id
    user_id = None
    if raw and str(raw).strip():
        try:
            user_id = uuid.UUID(str(raw).strip())
        except ValueError:
            pass
    if user_id is None:
        user_id = uuid.UUID("00000000-0000-4000-8000-000000000001")
    result = await db.execute(select(UserModel).where(UserModel.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


async def _get_user_by_sub(db: AsyncSession, sub: str) -> UserModel:
    result = await db.execute(select(UserModel).where(UserModel.oidc_sub == sub))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session user not found")
    return user


async def get_current_user_cookie(
    request: Request,
    db: AsyncSession,
) -> UserModel | None:
    """Resolve user from session cookie if present + CSRF header valid.

    Returns ``None`` when no session cookie is set, so callers can fall back
    to Bearer-token authentication. Raises 401/403 only when a cookie IS
    present but invalid (missing session, CSRF mismatch) — a missing cookie
    is not an error, it simply means the caller did not opt into cookie auth.
    """
    from app.core.session import (
        csrf_cookie_name,
        load_session,
        refresh_session_ttl,
        session_cookie_name,
        verify_csrf,
    )

    if not settings.auth_session_cookie_enabled:
        return None
    session_id = request.cookies.get(session_cookie_name(), "")
    if not session_id:
        return None
    payload = await load_session(session_id)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")
    verify_csrf(request, payload.get("csrf", ""))
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session missing sub")
    user = await _get_user_by_sub(db, sub)
    await refresh_session_ttl(session_id)
    return user


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> UserModel:
    """Dependency: return current user.

    Resolution order:
    1. Session cookie (when ``auth_session_cookie_enabled=true`` and cookie set)
    2. OIDC Bearer token (when ``oidc_enabled=true``)
    3. ``CURRENT_USER_ID`` fallback / default user (when OIDC is disabled)
    """
    if settings.auth_session_cookie_enabled:
        user = await get_current_user_cookie(request=request, db=db)
        if user is not None:
            return user
    if settings.oidc_enabled:
        return await get_current_user_oidc(credentials=credentials, db=db)
    return await get_current_user_fallback(db=db)


def require_roles(*allowed_roles: str):
    """Dependency factory: require current user to have one of the given roles (e.g. editor, admin). Raises 403 otherwise."""
    async def _dependency(current_user: UserModel = Depends(get_current_user)) -> UserModel:
        if current_user.role not in allowed_roles:
            logger.warning(
                "Authorization denied: insufficient role",
                extra={
                    "user_id": str(current_user.id),
                    "user_role": current_user.role,
                    "required_roles": list(allowed_roles),
                },
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user
    return Depends(_dependency)


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
):
    """Dependency: return current user or None. For routes that work with or without auth (e.g. optional profile)."""
    if settings.oidc_enabled:
        if not credentials or not credentials.credentials:
            return None
        try:
            return await get_current_user_oidc(credentials=credentials, db=db)
        except HTTPException:
            return None
    return await get_current_user_fallback(db=db)
