"""Integration tests for the /api/v1/findings routes.

These tests require a live PostgreSQL database (DATABASE_URL env var).
They test listing, filtering, updating, and bulk-updating findings.
"""

import pytest

from tests.factories import create_case

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# List findings
# ---------------------------------------------------------------------------


async def test_list_findings_empty_for_new_case(client):
    """Newly created cases have no findings."""
    case = await create_case(client, title="Empty Findings")
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
    case = await create_case(client, title="CSV Export Test")
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


async def _add_findings(case_id: str, n: int, status: str = "open") -> list[str]:
    import uuid

    from app.database import async_session_factory
    from app.models.db import FindingModel

    ids: list[str] = []
    async with async_session_factory() as session:
        for i in range(n):
            finding = FindingModel(
                case_id=uuid.UUID(case_id),
                check_name=f"check-{i}",
                severity="medium",
                status=status,
                category="test",
                description="desc",
            )
            session.add(finding)
            await session.flush()
            ids.append(str(finding.id))
        await session.commit()
    return ids


async def test_bulk_update_counts_only_changed_findings(client):
    """Regression: ``updated`` was incremented for every finding, changed or not."""
    case = await create_case(client, title="Bulk-Count")
    ids = await _add_findings(case["id"], 3, status="open")

    same = await client.patch(
        "/api/v1/findings/bulk-update", json={"finding_ids": ids, "status": "open"}
    )
    assert same.status_code == 200
    assert same.json()["updated"] == 0

    changed = await client.patch(
        "/api/v1/findings/bulk-update",
        json={"finding_ids": ids, "status": "accepted"},
    )
    assert changed.status_code == 200
    assert changed.json()["updated"] == 3

    again = await client.patch(
        "/api/v1/findings/bulk-update",
        json={"finding_ids": ids, "status": "accepted"},
    )
    assert again.json()["updated"] == 0

    listed = await client.get("/api/v1/findings", params={"case_id": case["id"]})
    assert listed.status_code == 200
    statuses = {f["status"] for f in listed.json()["items"]}
    assert statuses == {"accepted"}
