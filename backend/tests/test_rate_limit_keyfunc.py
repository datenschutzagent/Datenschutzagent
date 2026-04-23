"""Tests for the rate limiter's trusted-proxy-aware key function.

Ensures that ``X-Forwarded-For`` is only honoured when the direct peer is
listed in ``settings.trusted_proxies``; otherwise, the header is ignored so it
cannot be used to bypass rate limits.
"""
from __future__ import annotations

import importlib
from unittest.mock import MagicMock

import pytest


def _make_request(peer_host: str, xff: str | None = None):
    req = MagicMock()
    req.client = MagicMock()
    req.client.host = peer_host
    headers = {}
    if xff is not None:
        headers["x-forwarded-for"] = xff
    req.headers = headers
    return req


def _reload_rate_limit():
    """Reload the rate_limit module so that the cached trusted-networks list
    reflects the current settings (the module parses trusted_proxies at import)."""
    from app.core import rate_limit as rl
    importlib.reload(rl)
    return rl


def test_returns_peer_host_when_no_trusted_proxies_configured(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "trusted_proxies", [])
    rl = _reload_rate_limit()
    req = _make_request(peer_host="203.0.113.5", xff="198.51.100.10")
    assert rl._trusted_forwarded_for(req) == "203.0.113.5"


def test_honours_xff_when_peer_is_trusted_proxy(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "trusted_proxies", ["10.0.0.0/8"])
    rl = _reload_rate_limit()
    req = _make_request(peer_host="10.0.0.7", xff="198.51.100.10")
    assert rl._trusted_forwarded_for(req) == "198.51.100.10"


def test_ignores_xff_when_peer_is_untrusted(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "trusted_proxies", ["10.0.0.0/8"])
    rl = _reload_rate_limit()
    req = _make_request(peer_host="203.0.113.5", xff="198.51.100.10")
    assert rl._trusted_forwarded_for(req) == "203.0.113.5"


def test_takes_first_hop_from_xff_chain(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "trusted_proxies", ["10.0.0.0/8"])
    rl = _reload_rate_limit()
    req = _make_request(peer_host="10.0.0.7", xff="198.51.100.10, 10.0.0.7")
    assert rl._trusted_forwarded_for(req) == "198.51.100.10"


def test_falls_back_to_peer_when_xff_is_garbage(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "trusted_proxies", ["10.0.0.0/8"])
    rl = _reload_rate_limit()
    req = _make_request(peer_host="10.0.0.7", xff="not-an-ip")
    assert rl._trusted_forwarded_for(req) == "10.0.0.7"


def test_no_client_on_request(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "trusted_proxies", [])
    rl = _reload_rate_limit()
    req = MagicMock()
    req.client = None
    req.headers = {}
    assert rl._trusted_forwarded_for(req) == "unknown"


def test_config_rejects_invalid_trusted_proxy_entry():
    from app.config import Settings
    with pytest.raises(ValueError, match="TRUSTED_PROXIES"):
        Settings(trusted_proxies="not-an-ip-range")
