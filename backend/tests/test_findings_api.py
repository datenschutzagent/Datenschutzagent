"""Integration tests for the /api/v1/findings routes.

These tests require a live PostgreSQL database (DATABASE_URL env var).
They test listing, filtering, updating, and bulk-updating findings.
"""
import pytest

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_case(client, title: str = "Findings Test Case") -> dict:
    resp = await client.post(
        "/api/v1/cases",
        json={
            "title": title,
            "department": "IT",
            "case_type": "Softwareeinführung",
            "language": "de",
            "created_by": "test@example.com",
            "assignee": "DSB",
            "processing_context": None,
            "special_category_data": False,
            "international_transfer": False,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# List findings
# ---------------------------------------------------------------------------


async def test_list_findings_empty_for_new_case(client):
    """Newly created cases have no findings."""
    case = await _create_case(client, title="Empty Findings")
    resp = await client.get("/api/v1/findings", params={"case_id": case["id"]})
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert "total" in body
    assert body["items"] == []
    assert body["total"] == 0


async def test_list_findings_all_returns_200(client):
    """GET /findings without filters returns paginated response."""
    resp = await client.get("/api/v1/findings")
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert "total" in body
    assert isinstance(body["items"], list)


async def test_list_findings_invalid_case_id_returns_empty(client):
    """Filtering by a non-existent case_id returns empty list (not 404)."""
    resp = await client.get(
        "/api/v1/findings",
        params={"case_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


async def test_list_findings_pagination_params_accepted(client):
    """limit and offset params are accepted."""
    resp = await client.get("/api/v1/findings", params={"limit": 10, "offset": 0})
    assert resp.status_code == 200


async def test_list_findings_severity_filter(client):
    """Severity filter is accepted without error."""
    resp = await client.get("/api/v1/findings", params={"severity": "critical"})
    assert resp.status_code == 200


async def test_list_findings_status_filter(client):
    """Status filter is accepted without error."""
    resp = await client.get("/api/v1/findings", params={"status": "open"})
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------


async def test_export_findings_csv_returns_csv(client):
    """Export endpoint returns CSV content for a case."""
    case = await _create_case(client, title="CSV Export Test")
    resp = await client.get("/api/v1/findings/export", params={"case_id": case["id"]})
    assert resp.status_code == 200
    assert "csv" in resp.headers.get("content-type", "").lower()


async def test_export_findings_csv_nonexistent_case_returns_404(client):
    """Export for a non-existent case returns 404."""
    resp = await client.get(
        "/api/v1/findings/export",
        params={"case_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Bulk update
# ---------------------------------------------------------------------------


async def test_bulk_update_empty_ids_returns_zero(client):
    """Bulk update with empty finding_ids list returns updated=0."""
    resp = await client.patch(
        "/api/v1/findings/bulk-update",
        json={"finding_ids": [], "status": "accepted"},
    )
    assert resp.status_code == 200
    assert resp.json()["updated"] == 0


async def test_bulk_update_nonexistent_ids_returns_zero(client):
    """Bulk update with non-existent IDs returns updated=0."""
    resp = await client.patch(
        "/api/v1/findings/bulk-update",
        json={
            "finding_ids": ["00000000-0000-0000-0000-000000000001"],
            "status": "accepted",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["updated"] == 0
