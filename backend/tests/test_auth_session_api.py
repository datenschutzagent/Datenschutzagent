"""Integration tests for POST /auth/session (PKCE code → HttpOnly session cookie).

Regression for the missing ``await`` on ``_verify_jwt`` (async): the endpoint used to
call ``claims.get("sub")`` on a coroutine object and fail with a 500 — which also meant
the id_token signature was never actually verified. These tests pin both directions:
a rejected token must yield 401, a valid token must set the session cookie.

Requires DATABASE_URL (shared ``client`` fixture); the IdP round-trip and Redis session
store are patched.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException, status

from app.config import settings
from app.core.session import csrf_cookie_name, session_cookie_name

pytestmark = pytest.mark.asyncio

_BODY = {"code": "abc", "redirect_uri": "http://localhost/cb", "code_verifier": "v"}


@pytest.fixture
def _session_cookie_mode(monkeypatch):
    monkeypatch.setattr(settings, "auth_session_cookie_enabled", True, raising=False)
    monkeypatch.setattr(settings, "oidc_enabled", True, raising=False)


async def test_session_rejects_invalid_id_token(client, _session_cookie_mode):
    verify = AsyncMock(
        side_effect=HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="bad signature"
        )
    )
    with (
        patch(
            "app.api.routes.auth._exchange_code_for_id_token",
            AsyncMock(return_value="x.y.z"),
        ),
        patch("app.core.auth._verify_jwt", verify),
    ):
        resp = await client.post("/api/v1/auth/session", json=_BODY)

    assert resp.status_code == 401, resp.text
    verify.assert_awaited_once_with("x.y.z")
    assert session_cookie_name() not in resp.cookies


async def test_session_rejects_token_without_sub(client, _session_cookie_mode):
    with (
        patch(
            "app.api.routes.auth._exchange_code_for_id_token",
            AsyncMock(return_value="x.y.z"),
        ),
        patch("app.core.auth._verify_jwt", AsyncMock(return_value={"iss": "idp"})),
    ):
        resp = await client.post("/api/v1/auth/session", json=_BODY)

    assert resp.status_code == 401
    assert "sub" in resp.json()["detail"]


async def test_session_sets_cookies_for_valid_token(client, _session_cookie_mode):
    create_session = AsyncMock(return_value=("sid-123", "csrf-456"))
    with (
        patch(
            "app.api.routes.auth._exchange_code_for_id_token",
            AsyncMock(return_value="x.y.z"),
        ),
        patch("app.core.auth._verify_jwt", AsyncMock(return_value={"sub": "user-1"})),
        patch("app.api.routes.auth.create_session", create_session),
    ):
        resp = await client.post("/api/v1/auth/session", json=_BODY)

    assert resp.status_code == 200, resp.text
    assert resp.json() == {"ok": True}
    create_session.assert_awaited_once_with(user_sub="user-1")
    assert resp.cookies.get(session_cookie_name()) == "sid-123"
    assert resp.cookies.get(csrf_cookie_name()) == "csrf-456"


async def test_session_disabled_returns_404(client, monkeypatch):
    monkeypatch.setattr(settings, "auth_session_cookie_enabled", False, raising=False)
    resp = await client.post("/api/v1/auth/session", json=_BODY)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Phase 2 R1: OIDC discovery/token exchange run on httpx.AsyncClient (no blocking urllib)
# ---------------------------------------------------------------------------


def _mock_async_client(handler):
    """Patch httpx.AsyncClient in the auth module with a MockTransport-backed client."""
    import httpx

    real_client = httpx.AsyncClient

    def _factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(*args, **kwargs)

    return patch("app.api.routes.auth.httpx.AsyncClient", _factory)


async def test_token_exchange_uses_async_http(
    client, _session_cookie_mode, monkeypatch
):
    import httpx

    monkeypatch.setattr(
        settings, "oidc_issuer_url", "https://idp.example.com", raising=False
    )
    monkeypatch.setattr(settings, "oidc_client_id", "cid", raising=False)
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(f"{request.method} {request.url.path}")
        if request.url.path.endswith("/.well-known/openid-configuration"):
            return httpx.Response(
                200, json={"token_endpoint": "https://idp.example.com/token"}
            )
        assert request.method == "POST"
        body = request.content.decode()
        assert "grant_type=authorization_code" in body
        assert "code_verifier=v" in body
        return httpx.Response(200, json={"id_token": "x.y.z"})

    with (
        _mock_async_client(handler),
        patch("app.core.auth._verify_jwt", AsyncMock(return_value={"sub": "u"})),
        patch(
            "app.api.routes.auth.create_session",
            AsyncMock(return_value=("sid", "csrf")),
        ),
    ):
        resp = await client.post("/api/v1/auth/session", json=_BODY)

    assert resp.status_code == 200, resp.text
    assert seen == ["GET /.well-known/openid-configuration", "POST /token"]


async def test_token_exchange_idp_rejection_is_401(
    client, _session_cookie_mode, monkeypatch
):
    import httpx

    monkeypatch.setattr(
        settings, "oidc_issuer_url", "https://idp.example.com", raising=False
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("openid-configuration"):
            return httpx.Response(
                200, json={"token_endpoint": "https://idp.example.com/token"}
            )
        return httpx.Response(400, json={"error": "invalid_grant"})

    with _mock_async_client(handler):
        resp = await client.post("/api/v1/auth/session", json=_BODY)
    assert resp.status_code == 401
    assert "invalid_grant" not in resp.text


async def test_auth_config_survives_idp_outage(client, monkeypatch):
    import httpx

    monkeypatch.setattr(settings, "oidc_enabled", True, raising=False)
    monkeypatch.setattr(
        settings, "oidc_issuer_url", "https://idp.example.com", raising=False
    )

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    with _mock_async_client(handler):
        resp = await client.get("/api/v1/auth/config")
    assert resp.status_code == 200
    body = resp.json()
    assert body["oidc_enabled"] is True
    assert body["authorization_endpoint"] == ""
