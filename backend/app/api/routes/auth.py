"""Public auth config for frontend (OIDC endpoints, no auth required)."""
import json
import logging
import urllib.request

from fastapi import APIRouter, Request

from app.config import settings
from app.core.rate_limit import limiter

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
