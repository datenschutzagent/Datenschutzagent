"""Integration tests for the /api/v1/dsr routes.

These tests require a live PostgreSQL database (DATABASE_URL env var).
They test create, read, update, and delete behaviour for DSR requests
(Betroffenenrechts-Anfragen, Art. 15–22 DSGVO).
"""
import pytest

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

async def _create_dsr(client, **overrides) -> dict:
    payload = {
        "request_type": "access",
        "requestor_name": "Max Mustermann",
        "requestor_email": "max@example.com",
        "description": "Auskunft über gespeicherte Daten",
        "department": "IT",
        "assignee": "DSB Team",
        "received_at": "2026-04-14",
        "deadline_extension_days": 0,
        **overrides,
    }
    resp = await client.post("/api/v1/dsr", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# DSR CRUD
# ---------------------------------------------------------------------------


async def test_create_dsr_request_returns_id(client):
    dsr = await _create_dsr(client, requestor_name="Erika Musterfrau")
    assert "id" in dsr
    assert dsr["request_type"] == "access"
    assert dsr["status"] == "received"
    assert dsr["requestor_name"] == "Erika Musterfrau"


async def test_create_dsr_request_calculates_deadline(client):
    dsr = await _create_dsr(client, received_at="2026-04-14", deadline_extension_days=0)
    # Art. 12 Abs. 3 DSGVO: 30-day default deadline
    assert dsr["response_deadline"] == "2026-05-14"


async def test_create_dsr_request_with_extension(client):
    dsr = await _create_dsr(client, received_at="2026-04-14", deadline_extension_days=30)
    # 30 base days + 30 extension days = 60 days total
    assert dsr["response_deadline"] == "2026-06-13"


async def test_get_dsr_request_by_id(client):
    dsr = await _create_dsr(client, requestor_name="Get-by-ID Test")
    dsr_id = dsr["id"]

    resp = await client.get(f"/api/v1/dsr/{dsr_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == dsr_id
    assert data["requestor_name"] == "Get-by-ID Test"


async def test_get_dsr_request_not_found(client):
    resp = await client.get("/api/v1/dsr/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


async def test_list_dsr_requests_includes_created(client):
    dsr = await _create_dsr(client, requestor_email="list-test@example.com")
    resp = await client.get("/api/v1/dsr")
    assert resp.status_code == 200
    data = resp.json()
    ids = [item["id"] for item in data["items"]]
    assert dsr["id"] in ids


async def test_list_dsr_filter_status(client):
    dsr = await _create_dsr(client)
    dsr_id = dsr["id"]

    # Advance status to in_progress
    patch_resp = await client.patch(f"/api/v1/dsr/{dsr_id}", json={"status": "in_progress"})
    assert patch_resp.status_code == 200

    resp = await client.get("/api/v1/dsr?status=in_progress")
    assert resp.status_code == 200
    data = resp.json()
    ids = [item["id"] for item in data["items"]]
    assert dsr_id in ids

    resp_received = await client.get("/api/v1/dsr?status=received")
    assert resp_received.status_code == 200
    ids_received = [item["id"] for item in resp_received.json()["items"]]
    assert dsr_id not in ids_received


async def test_update_dsr_status(client):
    dsr = await _create_dsr(client)
    dsr_id = dsr["id"]

    resp = await client.patch(f"/api/v1/dsr/{dsr_id}", json={"status": "in_progress"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_progress"


async def test_delete_dsr_request(client):
    dsr = await _create_dsr(client, requestor_name="Zu löschen")
    dsr_id = dsr["id"]

    del_resp = await client.delete(f"/api/v1/dsr/{dsr_id}")
    assert del_resp.status_code in (200, 204)

    get_resp = await client.get(f"/api/v1/dsr/{dsr_id}")
    assert get_resp.status_code == 404


async def test_get_dsr_activity_has_created_event(client):
    dsr = await _create_dsr(client)
    dsr_id = dsr["id"]

    resp = await client.get(f"/api/v1/dsr/{dsr_id}/activity")
    assert resp.status_code == 200
    events = resp.json()
    assert len(events) >= 1
    event_types = [e["event_type"] for e in events]
    assert "created" in event_types
