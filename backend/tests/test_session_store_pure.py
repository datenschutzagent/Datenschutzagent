"""Redis-backed session store with an in-memory fake (Phase 1 S5).

Covers the absolute lifetime cap, the per-user session index and bulk revocation;
the CSRF/cookie helpers are covered by test_session_cookie_pure.py.
"""

from __future__ import annotations

import json
import time

import pytest

from app.config import settings
from app.core import session as sess


class _FakeRedis:
    """Minimal async subset of redis.asyncio used by app.core.session."""

    def __init__(self):
        self.kv: dict[str, str] = {}
        self.ttl: dict[str, int] = {}
        self.sets: dict[str, set[str]] = {}

    async def setex(self, key, ttl, value):
        self.kv[key] = value
        self.ttl[key] = ttl

    async def get(self, key):
        return self.kv.get(key)

    async def expire(self, key, ttl):
        if key in self.kv or key in self.sets:
            self.ttl[key] = ttl

    async def delete(self, key):
        self.kv.pop(key, None)
        self.sets.pop(key, None)
        self.ttl.pop(key, None)

    async def sadd(self, key, member):
        self.sets.setdefault(key, set()).add(member)

    async def srem(self, key, member):
        self.sets.get(key, set()).discard(member)

    async def smembers(self, key):
        return set(self.sets.get(key, set()))


@pytest.fixture
def fake_redis(monkeypatch):
    r = _FakeRedis()
    monkeypatch.setattr(sess, "_get_redis", lambda: r)
    return r


@pytest.mark.asyncio
async def test_create_and_load_roundtrip(fake_redis):
    sid, csrf = await sess.create_session(user_sub="user-1")
    payload = await sess.load_session(sid)
    assert payload["sub"] == "user-1"
    assert payload["csrf"] == csrf
    assert isinstance(payload["issued_at"], int)
    # Indexed per user for bulk revocation.
    assert sid in fake_redis.sets[sess._user_sessions_key("user-1")]


@pytest.mark.asyncio
async def test_idle_ttl_is_capped_by_absolute_ttl(fake_redis, monkeypatch):
    monkeypatch.setattr(settings, "session_ttl_seconds", 43200)
    monkeypatch.setattr(settings, "session_absolute_ttl_seconds", 600)
    sid, _ = await sess.create_session(user_sub="u")
    assert fake_redis.ttl[sess._SESSION_KEY_PREFIX + sid] == 600


@pytest.mark.asyncio
async def test_session_past_absolute_lifetime_is_revoked(fake_redis, monkeypatch):
    monkeypatch.setattr(settings, "session_absolute_ttl_seconds", 100)
    sid, _ = await sess.create_session(user_sub="u")
    key = sess._SESSION_KEY_PREFIX + sid
    stale = json.loads(fake_redis.kv[key])
    stale["issued_at"] = int(time.time()) - 101
    fake_redis.kv[key] = json.dumps(stale)

    assert await sess.load_session(sid) is None
    assert key not in fake_redis.kv
    assert sid not in fake_redis.sets.get(sess._user_sessions_key("u"), set())


@pytest.mark.asyncio
async def test_legacy_session_without_issued_at_is_rejected(fake_redis):
    key = sess._SESSION_KEY_PREFIX + "legacy"
    fake_redis.kv[key] = json.dumps({"sub": "u", "csrf": "c"})
    assert await sess.load_session("legacy") is None


@pytest.mark.asyncio
async def test_refresh_never_extends_beyond_absolute_lifetime(fake_redis, monkeypatch):
    monkeypatch.setattr(settings, "session_ttl_seconds", 1000)
    monkeypatch.setattr(settings, "session_absolute_ttl_seconds", 300)
    sid, _ = await sess.create_session(user_sub="u")
    key = sess._SESSION_KEY_PREFIX + sid
    payload = json.loads(fake_redis.kv[key])
    payload["issued_at"] = int(time.time()) - 250  # 50 s of absolute lifetime left
    fake_redis.kv[key] = json.dumps(payload)

    await sess.refresh_session_ttl(sid)
    assert fake_redis.ttl[key] <= 50


@pytest.mark.asyncio
async def test_destroy_user_sessions_revokes_all(fake_redis):
    sid1, _ = await sess.create_session(user_sub="u")
    sid2, _ = await sess.create_session(user_sub="u")
    other, _ = await sess.create_session(user_sub="someone-else")

    revoked = await sess.destroy_user_sessions("u")

    assert revoked == 2
    assert await sess.load_session(sid1) is None
    assert await sess.load_session(sid2) is None
    assert (await sess.load_session(other))["sub"] == "someone-else"
