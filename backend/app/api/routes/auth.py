"""Public auth config for frontend (OIDC endpoints, no auth required)."""

import logging

import httpx
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
async def get_auth_config(request: Request):
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
        discovery = await _oidc_discovery(out["oidc_issuer_url"], timeout=3.0)
        out["authorization_endpoint"] = discovery.get("authorization_endpoint") or ""
        out["token_endpoint"] = discovery.get("token_endpoint") or ""
        out["end_session_endpoint"] = discovery.get("end_session_endpoint") or ""
    # OIDC discovery is best-effort; frontend falls back to manual config
    except Exception as exc:  # noqa: BLE001
        logger.warning("OIDC discovery failed for %s: %s", out["oidc_issuer_url"], exc)
        out["authorization_endpoint"] = ""
        out["token_endpoint"] = ""
        out["end_session_endpoint"] = ""
    return out


async def _oidc_discovery(issuer: str, *, timeout: float) -> dict:
    """Fetch the OpenID discovery document without blocking the event loop."""
    url = f"{issuer.rstrip('/')}/.well-known/openid-configuration"
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(url)  # URL from trusted config (OIDC_ISSUER_URL)
        resp.raise_for_status()
        data = resp.json()
    if not isinstance(data, dict):
        raise ValueError("OIDC discovery document is not a JSON object")
    return data


# ---------------------------------------------------------------------------
# Session cookie flow
# ---------------------------------------------------------------------------


class _SessionExchangeBody(BaseModel):
    code: str
    redirect_uri: str
    code_verifier: str


async def _oidc_token_endpoint() -> str:
    """Resolve the OIDC token endpoint via discovery (hit only during login)."""
    issuer = (settings.oidc_issuer_url or "").rstrip("/")
    if not issuer:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OIDC issuer not configured",
        )
    try:
        discovery = await _oidc_discovery(issuer, timeout=5.0)
        token_endpoint = discovery.get("token_endpoint")
    except Exception as exc:  # noqa: BLE001 – discovery failure is mapped to 503
        logger.warning("OIDC discovery failed during token exchange: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OIDC discovery unavailable",
        ) from exc
    if not token_endpoint:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="token_endpoint missing from OIDC discovery",
        )
    return token_endpoint


async def _exchange_code_for_id_token(body: _SessionExchangeBody) -> str:
    """Exchange the PKCE authorization code for tokens at the IdP, return the id_token.

    The backend performs the exchange so a confidential client's secret (if any)
    never reaches the browser. Public clients with PKCE still work; we send the
    client_id and optional client_secret if configured. Runs on httpx.AsyncClient so
    a slow IdP (up to 10 s) no longer blocks the event loop for every other request.
    """
    token_endpoint = await _oidc_token_endpoint()
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
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(token_endpoint, data=form)
    except httpx.HTTPError as exc:
        logger.warning("OIDC token exchange error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Token exchange unreachable",
        ) from exc
    if resp.status_code >= 400:
        logger.warning(
            "OIDC token exchange failed: %s %s", resp.status_code, resp.text[:200]
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token exchange failed"
        )
    try:
        payload = resp.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token response is not JSON",
        ) from exc
    id_token = payload.get("id_token") if isinstance(payload, dict) else None
    if not id_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="id_token missing in token response",
        )
    return id_token


@router.post("/session")
@limiter.limit("10/minute")
async def start_session(
    request: Request, response: Response, body: _SessionExchangeBody
):
    """Exchange a PKCE authorization code for an HttpOnly session cookie.

    Only available when ``auth_session_cookie_enabled=true``. The legacy
    Bearer-token path (``/auth/token``, if implemented elsewhere) stays
    separate so deployments can migrate stepwise.
    """
    if not settings.auth_session_cookie_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session cookie auth is disabled",
        )
    if not settings.oidc_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="OIDC is not enabled"
        )
    id_token = await _exchange_code_for_id_token(body)
    # Trust the JWT signature via the central verifier to avoid duplicating logic.
    from app.core.auth import _verify_jwt

    claims = await _verify_jwt(id_token)
    sub = claims.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="id_token missing sub"
        )
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
