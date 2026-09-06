"""Integration tests for the /api/v1/avv routes.

These tests require a live PostgreSQL database (DATABASE_URL env var).
They test create, read, update, and delete behaviour for AVV contracts
(Auftragsverarbeitungsverträge, Art. 28 DSGVO).
"""

import pytest

from tests.factories import create_avv

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# AVV CRUD
# ---------------------------------------------------------------------------


async def test_create_avv_returns_id(client):
    avv = await create_avv(client, partner_name="Neuer Auftragsverarbeiter GmbH")
    assert "id" in avv
    assert avv["partner_name"] == "Neuer Auftragsverarbeiter GmbH"
    assert avv["status"] == "pending"
    assert avv["partner_type"] == "processor"


async def test_get_avv_by_id(client):
    avv = await create_avv(client, partner_name="Get-by-ID Partner GmbH")
    avv_id = avv["id"]

    resp = await client.get(f"/api/v1/avv/{avv_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == avv_id
    assert data["partner_name"] == "Get-by-ID Partner GmbH"


async def test_get_avv_not_found(client):
    resp = await client.get("/api/v1/avv/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


async def test_list_avv_includes_created(client):
    avv = await create_avv(client, partner_name="List-Test Partner GmbH")
    resp = await client.get("/api/v1/avv")
    assert resp.status_code == 200
    data = resp.json()
    ids = [item["id"] for item in data["items"]]
    assert avv["id"] in ids


async def test_update_avv_status(client):
    avv = await create_avv(client)
    avv_id = avv["id"]

    resp = await client.patch(f"/api/v1/avv/{avv_id}", json={"status": "under_review"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "under_review"


async def test_delete_avv(client):
    avv = await create_avv(client, partner_name="Zu löschender Partner GmbH")
    avv_id = avv["id"]

    del_resp = await client.delete(f"/api/v1/avv/{avv_id}")
    assert del_resp.status_code in (200, 204)

    get_resp = await client.get(f"/api/v1/avv/{avv_id}")
    assert get_resp.status_code == 404
