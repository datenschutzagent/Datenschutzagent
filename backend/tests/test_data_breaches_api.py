"""Integration tests for the /api/v1/data-breaches routes.

These tests require a live PostgreSQL database (DATABASE_URL env var).
They test create, read, update, and delete behaviour for data breach records
(Datenpannen-Management, Art. 33/34 DSGVO – 72-Stunden-Meldepflicht).
"""
import pytest

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

async def _create_breach(client, **overrides) -> dict:
    payload = {
        "title": "Testdatenpanne",
        "description": "E-Mail-Versand an falschen Empfänger",
        "discovered_at": "2026-04-14T10:00:00",
        "breach_type": "confidentiality",
        "affected_data_categories": ["name", "email"],
        "affected_persons_count": 50,
        "department": "HR",
        "assignee": "DSB Team",
        "risk_level": "medium",
        **overrides,
    }
    resp = await client.post("/api/v1/data-breaches", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Data Breach CRUD
# ---------------------------------------------------------------------------


async def test_create_breach_returns_id(client):
    breach = await _create_breach(client, title="Neues Datenleck")
    assert "id" in breach
    assert breach["title"] == "Neues Datenleck"
    assert breach["status"] == "discovered"
    assert breach["breach_type"] == "confidentiality"


async def test_create_breach_has_notification_deadline(client):
    breach = await _create_breach(client, discovered_at="2026-04-14T10:00:00")
    # Art. 33 Abs. 1 DSGVO: 72-hour notification deadline
    assert "notification_deadline" in breach
    # discovered_at is 2026-04-14T10:00:00 → deadline is 2026-04-17T10:00:00
    assert breach["notification_deadline"].startswith("2026-04-17T10:00:00")


async def test_get_breach_by_id(client):
    breach = await _create_breach(client, title="Get-by-ID Datenpanne")
    breach_id = breach["id"]

    resp = await client.get(f"/api/v1/data-breaches/{breach_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == breach_id
    assert data["title"] == "Get-by-ID Datenpanne"


async def test_get_breach_not_found(client):
    resp = await client.get("/api/v1/data-breaches/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


async def test_list_breaches_includes_created(client):
    breach = await _create_breach(client, title="List-Test-Datenpanne")
    resp = await client.get("/api/v1/data-breaches")
    assert resp.status_code == 200
    data = resp.json()
    ids = [item["id"] for item in data["items"]]
    assert breach["id"] in ids


async def test_update_breach_status(client):
    breach = await _create_breach(client)
    breach_id = breach["id"]

    resp = await client.patch(f"/api/v1/data-breaches/{breach_id}", json={"status": "assessed"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "assessed"


async def test_delete_breach(client):
    breach = await _create_breach(client, title="Zu löschende Datenpanne")
    breach_id = breach["id"]

    del_resp = await client.delete(f"/api/v1/data-breaches/{breach_id}")
    assert del_resp.status_code in (200, 204)

    get_resp = await client.get(f"/api/v1/data-breaches/{breach_id}")
    assert get_resp.status_code == 404


async def test_get_breach_activity_has_created_event(client):
    breach = await _create_breach(client)
    breach_id = breach["id"]

    resp = await client.get(f"/api/v1/data-breaches/{breach_id}/activity")
    assert resp.status_code == 200
    events = resp.json()
    assert len(events) >= 1
    event_types = [e["event_type"] for e in events]
    assert "created" in event_types
