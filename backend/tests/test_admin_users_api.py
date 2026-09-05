"""Integration tests for PATCH /admin/users/{id}/role (requires DATABASE_URL)."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.asyncio


async def _create_user(oidc_sub: str | None, role: str = "viewer") -> uuid.UUID:
    from app.database import async_session_factory
    from app.models.db import UserModel

    async with async_session_factory() as session:
        user = UserModel(
            oidc_sub=oidc_sub, display_name="Role Test", email=None, role=role
        )
        session.add(user)
        await session.commit()
        return user.id


async def test_role_change_revokes_user_sessions(client):
    sub = f"sub-{uuid.uuid4()}"
    user_id = await _create_user(sub, role="editor")
    revoke = AsyncMock(return_value=2)
    with patch("app.core.session.destroy_user_sessions", revoke):
        resp = await client.patch(
            f"/api/v1/admin/users/{user_id}/role", json={"role": "viewer"}
        )
    assert resp.status_code == 200, resp.text
    assert resp.json()["role"] == "viewer"
    revoke.assert_awaited_once_with(sub)


async def test_unchanged_role_does_not_revoke(client):
    user_id = await _create_user(f"sub-{uuid.uuid4()}", role="viewer")
    revoke = AsyncMock(return_value=0)
    with patch("app.core.session.destroy_user_sessions", revoke):
        resp = await client.patch(
            f"/api/v1/admin/users/{user_id}/role", json={"role": "viewer"}
        )
    assert resp.status_code == 200
    revoke.assert_not_awaited()


async def test_invalid_role_rejected(client):
    user_id = await _create_user(None)
    resp = await client.patch(
        f"/api/v1/admin/users/{user_id}/role", json={"role": "superuser"}
    )
    assert resp.status_code == 400
