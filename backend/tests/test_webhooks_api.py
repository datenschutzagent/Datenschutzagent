"""Integration tests for the /api/v1/admin/webhooks routes.

These tests require a live PostgreSQL database (DATABASE_URL env var).
They test create, read, update, delete, and event-listing behaviour for webhooks.
"""

import pytest

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


async def _create_webhook(client, **overrides) -> dict:
    payload = {
        "name": "Test Webhook",
        "url": "https://example.com/webhook",
        "events": ["case_status_changed"],
        "secret": "test-secret-123",
        **overrides,
    }
    resp = await client.post("/api/v1/admin/webhooks", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Webhook Tests
# ---------------------------------------------------------------------------


async def test_list_webhook_events(client):
    resp = await client.get("/api/v1/admin/webhooks/events")
    assert resp.status_code == 200
    events = resp.json()
    assert isinstance(events, list)
    assert len(events) > 0
    assert "case_status_changed" in events


async def test_create_webhook_returns_id(client):
    webhook = await _create_webhook(client, name="Create-Test-Webhook")
    assert "id" in webhook
    assert webhook["url"] == "https://example.com/webhook"
    assert "case_status_changed" in webhook["events"]
    assert webhook["is_active"] is True


async def test_list_webhooks_includes_created(client):
    webhook = await _create_webhook(client, name="List-Test-Webhook")
    resp = await client.get("/api/v1/admin/webhooks")
    assert resp.status_code == 200
    ids = [w["id"] for w in resp.json()]
    assert webhook["id"] in ids


async def test_update_webhook(client):
    webhook = await _create_webhook(client, name="Update-Test-Webhook")
    webhook_id = webhook["id"]

    resp = await client.patch(
        f"/api/v1/admin/webhooks/{webhook_id}",
        json={"is_active": False, "name": "Updated Webhook Name"},
    )
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["is_active"] is False
    assert updated["name"] == "Updated Webhook Name"


async def test_delete_webhook(client):
    webhook = await _create_webhook(client, name="Zu-löschender-Webhook")
    webhook_id = webhook["id"]

    del_resp = await client.delete(f"/api/v1/admin/webhooks/{webhook_id}")
    assert del_resp.status_code in (200, 204)

    list_resp = await client.get("/api/v1/admin/webhooks")
    assert list_resp.status_code == 200
    ids = [w["id"] for w in list_resp.json()]
    assert webhook_id not in ids


async def test_create_webhook_invalid_event(client):
    resp = await client.post(
        "/api/v1/admin/webhooks",
        json={
            "name": "Invalid-Event-Webhook",
            "url": "https://example.com/webhook",
            "events": ["invalid_event"],
        },
    )
    assert resp.status_code == 400
