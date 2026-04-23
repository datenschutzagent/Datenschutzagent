"""HttpOnly session cookie and CSRF helpers.

Provides:
- a Redis-backed session store keyed by an opaque session id (the cookie value)
- CSRF double-submit verification that compares a non-HttpOnly cookie with an
  ``X-CSRF-Token`` header on unsafe methods
- helpers to set/clear the session + CSRF cookies with ``__Host-`` prefix in
  production and the plain names in development so browsers accept them on
  plain-HTTP local setups

The bearer-token flow in :mod:`app.core.auth` stays the authority whenever the
feature flag ``auth_session_cookie_enabled`` is off; this module is additive.
"""
from __future__ import annotations

import json
import logging
import secrets
from typing import Any

from fastapi import HTTPException, Request, Response, status

from app.config import settings

logger = logging.getLogger(__name__)

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def session_cookie_name() -> str:
    return (
        settings.session_cookie_name_production
        if settings.app_environment == "production"
        else settings.session_cookie_name_development
    )


def csrf_cookie_name() -> str:
    return (
        settings.csrf_cookie_name_production
        if settings.app_environment == "production"
        else settings.csrf_cookie_name_development
    )


def _use_secure_cookie() -> bool:
    return settings.app_environment == "production"


# ---------------------------------------------------------------------------
# Redis-backed session store
# ---------------------------------------------------------------------------

_SESSION_KEY_PREFIX = "ds_session:"

_redis_client = None


def _get_redis():
    """Lazy Redis client, reused across requests."""
    global _redis_client
    if _redis_client is None:
        try:
            import redis.asyncio as aioredis  # type: ignore
            _redis_client = aioredis.from_url(
                settings.celery_broker_url,
                decode_responses=True,
                max_connections=10,
            )
        except Exception as exc:  # pragma: no cover — only in misconfigured dev
            logger.error("Session store init failed: %s", exc)
            _redis_client = None
    return _redis_client


async def create_session(*, user_sub: str, extra: dict[str, Any] | None = None) -> tuple[str, str]:
    """Allocate a new session and CSRF token, persist both in Redis.

    Returns ``(session_id, csrf_token)``. The caller attaches them as cookies.
    """
    r = _get_redis()
    if r is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Session store unavailable",
        )
    session_id = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)
    payload = {"sub": user_sub, "csrf": csrf_token}
    if extra:
        payload.update(extra)
    await r.setex(
        _SESSION_KEY_PREFIX + session_id,
        settings.session_ttl_seconds,
        json.dumps(payload),
    )
    return session_id, csrf_token


async def load_session(session_id: str) -> dict[str, Any] | None:
    r = _get_redis()
    if r is None or not session_id:
        return None
    try:
        raw = await r.get(_SESSION_KEY_PREFIX + session_id)
    except Exception as exc:  # pragma: no cover — Redis down
        logger.warning("Session load failed: %s", exc)
        return None
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


async def refresh_session_ttl(session_id: str) -> None:
    r = _get_redis()
    if r is None or not session_id:
        return
    try:
        await r.expire(_SESSION_KEY_PREFIX + session_id, settings.session_ttl_seconds)
    except Exception as exc:  # pragma: no cover
        logger.debug("Session TTL refresh failed: %s", exc)


async def destroy_session(session_id: str) -> None:
    r = _get_redis()
    if r is None or not session_id:
        return
    try:
        await r.delete(_SESSION_KEY_PREFIX + session_id)
    except Exception as exc:  # pragma: no cover
        logger.warning("Session destroy failed: %s", exc)


# ---------------------------------------------------------------------------
# Cookie helpers
# ---------------------------------------------------------------------------


def set_session_cookies(response: Response, session_id: str, csrf_token: str) -> None:
    """Attach session + CSRF cookies to the response.

    - Session cookie: HttpOnly, so JS cannot read it — protects against token
      exfiltration via XSS.
    - CSRF cookie: NOT HttpOnly, because the SPA must read it to echo the value
      back in the ``X-CSRF-Token`` header on unsafe requests.
    """
    secure = _use_secure_cookie()
    response.set_cookie(
        key=session_cookie_name(),
        value=session_id,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        secure=secure,
        samesite="strict",
        path="/",
    )
    response.set_cookie(
        key=csrf_cookie_name(),
        value=csrf_token,
        max_age=settings.session_ttl_seconds,
        httponly=False,
        secure=secure,
        samesite="strict",
        path="/",
    )


def clear_session_cookies(response: Response) -> None:
    secure = _use_secure_cookie()
    for name in (session_cookie_name(), csrf_cookie_name()):
        response.delete_cookie(key=name, path="/", secure=secure, httponly=False, samesite="strict")


# ---------------------------------------------------------------------------
# CSRF double-submit verification
# ---------------------------------------------------------------------------


def verify_csrf(request: Request, session_csrf: str) -> None:
    """Raise 403 if the request fails CSRF double-submit.

    Only unsafe methods are checked. Safe methods (GET/HEAD/OPTIONS) are
    assumed side-effect free and do not require a CSRF header.

    The cookie-borne CSRF value must match the ``X-CSRF-Token`` header AND the
    value stored inside the session document. This rules out an attacker who
    could only forge a cookie via a subdomain takeover from bypassing the check.
    """
    if request.method.upper() in _SAFE_METHODS:
        return
    header_token = request.headers.get("x-csrf-token", "")
    cookie_token = request.cookies.get(csrf_cookie_name(), "")
    if not header_token or not cookie_token or header_token != cookie_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token missing or invalid")
    if not secrets.compare_digest(header_token, session_csrf):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token does not match session")
