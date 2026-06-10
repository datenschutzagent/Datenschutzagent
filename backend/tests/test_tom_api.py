"""Integration tests for the /api/v1/tom routes (Art. 32 DSGVO – TOMs).

These tests require a live PostgreSQL database (DATABASE_URL env var).
They test create, read, update, and delete behaviour for TOM entries.
"""

import pytest

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


async def _create_tom(client, **overrides) -> dict:
    payload = {
        "title": "Verschlüsselung ruhender Daten",
        "description": "AES-256 Verschlüsselung für Datenbanken",
        "category": "encryption",
        "implementation_status": "implemented",
        "responsible": "IT-Sicherheit",
        "evidence": "Dokumentiert in IT-Richtlinie §5",
        **overrides,
    }
    resp = await client.post("/api/v1/tom", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# TOM CRUD
# ---------------------------------------------------------------------------


async def test_create_tom_returns_id(client):
    tom = await _create_tom(client, title="Zugangskontrolle")
    assert "id" in tom
    assert tom["title"] == "Zugangskontrolle"
    assert tom["implementation_status"] == "implemented"
    assert tom["category"] == "encryption"


async def test_get_tom_by_id(client):
    tom = await _create_tom(client, title="Get-by-ID TOM Test")
    tom_id = tom["id"]

    resp = await client.get(f"/api/v1/tom/{tom_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == tom_id
    assert data["title"] == "Get-by-ID TOM Test"


async def test_get_tom_not_found(client):
    resp = await client.get("/api/v1/tom/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


async def test_list_toms_includes_created(client):
    tom = await _create_tom(client, title="List-TOM-Test")
    resp = await client.get("/api/v1/tom")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    ids = [t["id"] for t in data["items"]]
    assert tom["id"] in ids


async def test_tom_stats_returns_data(client):
    # Ensure at least one TOM exists
    await _create_tom(client, title="Stats-TOM")
    resp = await client.get("/api/v1/tom/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "by_status" in data
    assert "by_category" in data
    assert "implementation_rate" in data
    assert data["total"] >= 1


async def test_update_tom(client):
    tom = await _create_tom(client, title="Update-TOM-Test")
    tom_id = tom["id"]

    resp = await client.patch(
        f"/api/v1/tom/{tom_id}",
        json={"implementation_status": "in_progress", "responsible": "DSB"},
    )
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["implementation_status"] == "in_progress"
    assert updated["responsible"] == "DSB"


async def test_delete_tom(client):
    tom = await _create_tom(client, title="Zu-löschende-TOM")
    tom_id = tom["id"]

    del_resp = await client.delete(f"/api/v1/tom/{tom_id}")
    assert del_resp.status_code in (200, 204)

    get_resp = await client.get(f"/api/v1/tom/{tom_id}")
    assert get_resp.status_code == 404
