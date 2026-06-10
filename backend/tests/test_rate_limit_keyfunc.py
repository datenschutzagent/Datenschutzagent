"""Tests for the rate limiter's trusted-proxy-aware key function.

Ensures that ``X-Forwarded-For`` is only honoured when the direct peer is
listed in ``settings.trusted_proxies``; otherwise, the header is ignored so it
cannot be used to bypass rate limits.
"""

from __future__ import annotations

import importlib
from unittest.mock import MagicMock

import pytest


def _make_request(peer_host: str, xff: str | None = None, *, user=None):
    req = MagicMock()
    req.client = MagicMock()
    req.client.host = peer_host
    headers = {}
    if xff is not None:
        headers["x-forwarded-for"] = xff
    req.headers = headers
    # Only attach ``state.current_user`` if the test wants per-user keying;
    # otherwise MagicMock would auto-create a truthy attribute that
    # accidentally exercises the user-aware branch.
    if user is None:
        req.state = MagicMock(spec=[])  # no attributes
    else:
        state = MagicMock()
        state.current_user = user
        req.state = state
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


# ---------------------------------------------------------------------------
# Phase 4: per-user rate-limit key
# ---------------------------------------------------------------------------


def test_user_aware_key_falls_back_to_ip_when_no_user(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "trusted_proxies", [])
    rl = _reload_rate_limit()
    req = _make_request(peer_host="203.0.113.5")
    assert rl._user_aware_key(req) == "ip:203.0.113.5"


def test_user_aware_key_uses_user_id_when_present(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "trusted_proxies", [])
    rl = _reload_rate_limit()
    user = MagicMock()
    user.id = "user-uuid-42"
    req = _make_request(peer_host="203.0.113.5", user=user)
    assert rl._user_aware_key(req) == "user:user-uuid-42"


def test_user_aware_key_two_users_behind_same_ip_have_distinct_buckets(monkeypatch):
    """The bug fixed by Phase 4 — two users behind the same NAT must not
    share a rate-limit bucket."""
    from app.config import settings

    monkeypatch.setattr(settings, "trusted_proxies", [])
    rl = _reload_rate_limit()
    alice = MagicMock()
    alice.id = "alice"
    bob = MagicMock()
    bob.id = "bob"
    req_a = _make_request(peer_host="198.51.100.1", user=alice)
    req_b = _make_request(peer_host="198.51.100.1", user=bob)
    assert rl._user_aware_key(req_a) != rl._user_aware_key(req_b)


def test_user_aware_key_distinct_prefixes_for_user_and_ip(monkeypatch):
    """A UUID that happens to be numeric must not collide with an IP bucket."""
    from app.config import settings

    monkeypatch.setattr(settings, "trusted_proxies", [])
    rl = _reload_rate_limit()
    user = MagicMock()
    user.id = "203.0.113.5"  # contrived but possible
    req_user = _make_request(peer_host="198.51.100.1", user=user)
    req_ip = _make_request(peer_host="203.0.113.5")
    assert rl._user_aware_key(req_user) != rl._user_aware_key(req_ip)
    assert rl._user_aware_key(req_user).startswith("user:")
    assert rl._user_aware_key(req_ip).startswith("ip:")
