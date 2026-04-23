"""Public auth config for frontend (OIDC endpoints, no auth required)."""
import json
import logging
import urllib.parse
import urllib.request

import jwt
from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel

from app.config import settings
from app.core.rate_limit import limiter
from app.core.session import (
    clear_session_cookies,
    create_session,
    destroy_session,
    session_cookie_name,
    set_session_cookies,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/config")
@limiter.limit("30/minute")
def get_auth_config(request: Request):
    """
    Return OIDC configuration for the frontend (login URL, client id, scopes).
    No authentication required. When OIDC is disabled, frontend may skip login.
    """
    out = {
        "oidc_enabled": settings.oidc_enabled,
        "oidc_issuer_url": (settings.oidc_issuer_url or "").rstrip("/"),
        "oidc_client_id": settings.oidc_client_id or "",
        "oidc_scopes": (settings.oidc_scopes or "openid profile email").strip().split(),
        # Frontend flag: when true, the SPA uses the session-cookie flow
        # (POST /auth/session) instead of storing the access token in JS.
        "auth_session_cookie_enabled": settings.auth_session_cookie_enabled,
    }
    if not settings.oidc_enabled or not out["oidc_issuer_url"]:
        return out
    try:
        url = f"{out['oidc_issuer_url']}/.well-known/openid-configuration"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:  # nosec B310 – URL from trusted config (OIDC_ISSUER_URL)
            discovery = json.loads(resp.read().decode())
            out["authorization_endpoint"] = discovery.get("authorization_endpoint") or ""
            out["token_endpoint"] = discovery.get("token_endpoint") or ""
            out["end_session_endpoint"] = discovery.get("end_session_endpoint") or ""
    except Exception as exc:
        logger.warning("OIDC discovery failed for %s: %s", url, exc)
        out["authorization_endpoint"] = ""
        out["token_endpoint"] = ""
        out["end_session_endpoint"] = ""
    return out


# ---------------------------------------------------------------------------
# Session cookie flow
# ---------------------------------------------------------------------------


class _SessionExchangeBody(BaseModel):
    code: str
    redirect_uri: str
    code_verifier: str


def _oidc_token_endpoint() -> str:
    """Resolve the OIDC token endpoint via discovery. Cached would be nice
    but this endpoint is hit only during login, so a fresh call is fine."""
    issuer = (settings.oidc_issuer_url or "").rstrip("/")
    if not issuer:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OIDC issuer not configured",
        )
    try:
        url = f"{issuer}/.well-known/openid-configuration"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:  # nosec B310 — trusted issuer URL from config
            discovery = json.loads(resp.read().decode())
        token_endpoint = discovery.get("token_endpoint")
    except Exception as exc:
        logger.warning("OIDC discovery failed during token exchange: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OIDC discovery unavailable",
        )
    if not token_endpoint:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="token_endpoint missing from OIDC discovery",
        )
    return token_endpoint


def _exchange_code_for_id_token(body: _SessionExchangeBody) -> str:
    """Exchange the PKCE authorization code for tokens at the IdP, return the id_token.

    The backend performs the exchange so a confidential client's secret (if any)
    never reaches the browser. Public clients with PKCE still work; we send the
    client_id and optional client_secret if configured.
    """
    token_endpoint = _oidc_token_endpoint()
    form = {
        "grant_type": "authorization_code",
        "code": body.code,
        "redirect_uri": body.redirect_uri,
        "client_id": settings.oidc_client_id,
        "code_verifier": body.code_verifier,
    }
    client_secret = settings.oidc_client_secret.get_secret_value()
    if client_secret:
        form["client_secret"] = client_secret
    data = urllib.parse.urlencode(form).encode()
    req = urllib.request.Request(
        token_endpoint,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:  # nosec B310 — token endpoint from trusted OIDC discovery
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:200]
        logger.warning("OIDC token exchange failed: %s %s", exc.code, detail)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token exchange failed")
    except Exception as exc:
        logger.warning("OIDC token exchange error: %s", exc)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Token exchange unreachable")
    id_token = payload.get("id_token")
    if not id_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="id_token missing in token response")
    return id_token


@router.post("/session")
@limiter.limit("10/minute")
async def start_session(request: Request, response: Response, body: _SessionExchangeBody):
    """Exchange a PKCE authorization code for an HttpOnly session cookie.

    Only available when ``auth_session_cookie_enabled=true``. The legacy
    Bearer-token path (``/auth/token``, if implemented elsewhere) stays
    separate so deployments can migrate stepwise.
    """
    if not settings.auth_session_cookie_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session cookie auth is disabled")
    if not settings.oidc_enabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OIDC is not enabled")
    id_token = _exchange_code_for_id_token(body)
    # Trust the JWT signature via the central verifier to avoid duplicating logic.
    from app.core.auth import _verify_jwt
    claims = _verify_jwt(id_token)
    sub = claims.get("sub")
    if not sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="id_token missing sub")
    session_id, csrf_token = await create_session(user_sub=sub)
    set_session_cookies(response, session_id, csrf_token)
    return {"ok": True}


@router.post("/logout")
@limiter.limit("30/minute")
async def logout(request: Request, response: Response):
    """Invalidate the session (Redis + cookies)."""
    session_id = request.cookies.get(session_cookie_name(), "")
    if session_id:
        await destroy_session(session_id)
    clear_session_cookies(response)
    return {"ok": True}
