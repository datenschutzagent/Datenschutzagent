"""Pure unit tests for the session-cookie CSRF verifier and cookie helpers.

The Redis-backed session store and OIDC token exchange are covered by
integration tests elsewhere; this file exercises the logic that can be
reasoned about without Redis or an IdP.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException, Response

from app.core.session import (
    clear_session_cookies,
    csrf_cookie_name,
    session_cookie_name,
    set_session_cookies,
    verify_csrf,
)


def _req(
    method: str, *, csrf_cookie: str | None = None, csrf_header: str | None = None
):
    req = MagicMock()
    req.method = method
    req.cookies = {csrf_cookie_name(): csrf_cookie} if csrf_cookie is not None else {}
    req.headers = {"x-csrf-token": csrf_header} if csrf_header is not None else {}
    return req


def test_safe_methods_skip_csrf_check():
    for method in ("GET", "HEAD", "OPTIONS"):
        verify_csrf(_req(method), session_csrf="anything")


def test_post_without_csrf_header_rejected():
    with pytest.raises(HTTPException) as excinfo:
        verify_csrf(
            _req("POST", csrf_cookie="abc", csrf_header=None), session_csrf="abc"
        )
    assert excinfo.value.status_code == 403


def test_post_without_csrf_cookie_rejected():
    with pytest.raises(HTTPException) as excinfo:
        verify_csrf(
            _req("POST", csrf_cookie=None, csrf_header="abc"), session_csrf="abc"
        )
    assert excinfo.value.status_code == 403


def test_post_with_mismatched_tokens_rejected():
    with pytest.raises(HTTPException) as excinfo:
        verify_csrf(
            _req("POST", csrf_cookie="abc", csrf_header="xyz"), session_csrf="abc"
        )
    assert excinfo.value.status_code == 403


def test_post_with_matching_cookie_header_but_wrong_session_rejected():
    with pytest.raises(HTTPException) as excinfo:
        verify_csrf(
            _req("POST", csrf_cookie="abc", csrf_header="abc"), session_csrf="different"
        )
    assert excinfo.value.status_code == 403


def test_post_with_matching_triple_passes():
    verify_csrf(_req("POST", csrf_cookie="abc", csrf_header="abc"), session_csrf="abc")


def test_set_session_cookies_flags(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "app_environment", "production")
    response = Response()
    set_session_cookies(response, "session-id", "csrf-token")
    cookies = response.headers.getlist("set-cookie")
    session_hdr = next(c for c in cookies if c.startswith(session_cookie_name()))
    csrf_hdr = next(c for c in cookies if c.startswith(csrf_cookie_name()))
    # Session cookie must be HttpOnly + Secure + SameSite=strict
    assert "HttpOnly" in session_hdr
    assert "Secure" in session_hdr
    assert "SameSite=strict" in session_hdr
    # CSRF cookie must NOT be HttpOnly (the SPA needs to read it)
    assert "HttpOnly" not in csrf_hdr


def test_development_cookie_names_drop_host_prefix(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "app_environment", "development")
    assert not session_cookie_name().startswith("__Host-")
    assert not csrf_cookie_name().startswith("__Host-")


def test_production_cookie_names_use_host_prefix(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "app_environment", "production")
    assert session_cookie_name().startswith("__Host-")
    assert csrf_cookie_name().startswith("__Host-")


def test_clear_session_cookies_emits_max_age_zero(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "app_environment", "development")
    response = Response()
    clear_session_cookies(response)
    cookies = response.headers.getlist("set-cookie")
    assert any(
        "Max-Age=0" in c for c in cookies
    ), "expected Max-Age=0 to delete cookies"
