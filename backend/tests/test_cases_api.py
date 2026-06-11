"""Integration tests for the /api/v1/cases routes.

These tests require a live PostgreSQL database (DATABASE_URL env var).
They test create, read, update, and delete behaviour for cases and findings.
"""
import pytest

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

async def _create_case(client, **overrides) -> dict:
    payload = {
        "title": "Test-Vorgang",
        "department": "IT",
        "case_type": "Softwareeinführung",
        "language": "de",
        "created_by": "test@example.com",
        "assignee": "DSB Team",
        "processing_context": None,
        "special_category_data": False,
        "international_transfer": False,
        **overrides,
    }
    resp = await client.post("/api/v1/cases", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Case CRUD
# ---------------------------------------------------------------------------


async def test_create_case_returns_id(client):
    case = await _create_case(client, title="Neues CRM-System")
    assert "id" in case
    assert case["title"] == "Neues CRM-System"
    assert case["status"] == "intake"


async def test_get_case_by_id(client):
    case = await _create_case(client, title="Get-by-ID Test")
    case_id = case["id"]

    resp = await client.get(f"/api/v1/cases/{case_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == case_id
    assert data["title"] == "Get-by-ID Test"


async def test_get_case_not_found(client):
    resp = await client.get("/api/v1/cases/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


async def test_list_cases_includes_created(client):
    case = await _create_case(client, title="List-Test-Vorgang")
    resp = await client.get("/api/v1/cases", params={"limit": 500})
    assert resp.status_code == 200
    ids = [c["id"] for c in resp.json()["items"]]
    assert case["id"] in ids


async def test_update_case_status(client):
    case = await _create_case(client)
    case_id = case["id"]

    resp = await client.patch(f"/api/v1/cases/{case_id}", json={"status": "in_review"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_review"


async def test_delete_case(client):
    case = await _create_case(client, title="Zu-löschen")
    case_id = case["id"]

    del_resp = await client.delete(f"/api/v1/cases/{case_id}")
    assert del_resp.status_code in (200, 204)

    get_resp = await client.get(f"/api/v1/cases/{case_id}")
    assert get_resp.status_code == 404


# ---------------------------------------------------------------------------
# Finding status
# ---------------------------------------------------------------------------


async def test_list_findings_empty_for_new_case(client):
    case = await _create_case(client)
    resp = await client.get(f"/api/v1/cases/{case['id']}")
    assert resp.status_code == 200
    assert resp.json()["findings"] == []


# ---------------------------------------------------------------------------
# Playbooks list (basic smoke test)
# ---------------------------------------------------------------------------


async def test_playbooks_list(client):
    resp = await client.get("/api/v1/playbooks")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
