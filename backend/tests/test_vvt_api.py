"""Integration tests for the /api/v1/vvt-overview routes.

These tests require a live PostgreSQL database (DATABASE_URL env var).
They test VVT list, stats, and export endpoints.
"""

import pytest

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_case(
    client, title: str = "VVT Test Case", department: str = "IT"
) -> dict:
    resp = await client.post(
        "/api/v1/cases",
        json={
            "title": title,
            "department": department,
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
# GET /api/v1/vvt-overview
# ---------------------------------------------------------------------------


async def test_vvt_overview_returns_200(client):
    resp = await client.get("/api/v1/vvt-overview")
    assert resp.status_code == 200


async def test_vvt_overview_returns_list(client):
    resp = await client.get("/api/v1/vvt-overview")
    assert isinstance(resp.json(), list)


async def test_vvt_overview_contains_created_case(client):
    case = await _create_case(client, title="VVT Overview Test")
    resp = await client.get("/api/v1/vvt-overview")
    assert resp.status_code == 200
    case_ids = [item["case_id"] for item in resp.json()]
    assert case["id"] in case_ids


async def test_vvt_overview_item_has_required_fields(client):
    await _create_case(client, title="VVT Field Test")
    resp = await client.get("/api/v1/vvt-overview")
    assert resp.status_code == 200
    items = resp.json()
    if items:
        item = items[0]
        assert "case_id" in item
        assert "title" in item
        assert "department" in item
        assert "case_type" in item
        assert "status" in item
        assert "has_vvt_document" in item


async def test_vvt_overview_new_case_has_no_vvt(client):
    case = await _create_case(client, title="No VVT Test")
    resp = await client.get("/api/v1/vvt-overview")
    items = {i["case_id"]: i for i in resp.json()}
    if case["id"] in items:
        assert items[case["id"]]["has_vvt_document"] is False


async def test_vvt_overview_department_filter(client):
    dept = "Spezial-VVT-Abteilung"
    case = await _create_case(client, title="Dept Filter Test", department=dept)
    resp = await client.get("/api/v1/vvt-overview", params={"department": dept})
    assert resp.status_code == 200
    ids = [i["case_id"] for i in resp.json()]
    assert case["id"] in ids


async def test_vvt_overview_filter_has_vvt_false(client):
    """Filter has_vvt=false returns only cases without VVT documents."""
    case = await _create_case(client, title="No VVT Filter Test")
    resp = await client.get("/api/v1/vvt-overview", params={"has_vvt": "false"})
    assert resp.status_code == 200
    ids = [i["case_id"] for i in resp.json()]
    assert case["id"] in ids


async def test_vvt_overview_pagination(client):
    resp = await client.get("/api/v1/vvt-overview", params={"skip": 0, "limit": 5})
    assert resp.status_code == 200
    assert len(resp.json()) <= 5


# ---------------------------------------------------------------------------
# GET /api/v1/vvt-overview/stats
# ---------------------------------------------------------------------------


async def test_vvt_stats_returns_200(client):
    resp = await client.get("/api/v1/vvt-overview/stats")
    assert resp.status_code == 200


async def test_vvt_stats_has_required_fields(client):
    resp = await client.get("/api/v1/vvt-overview/stats")
    body = resp.json()
    assert "total_cases" in body
    assert "with_vvt" in body
    assert "without_vvt" in body
    assert "by_department" in body
    assert "by_case_type" in body


async def test_vvt_stats_counts_are_non_negative(client):
    resp = await client.get("/api/v1/vvt-overview/stats")
    body = resp.json()
    assert body["total_cases"] >= 0
    assert body["with_vvt"] >= 0
    assert body["without_vvt"] >= 0


# ---------------------------------------------------------------------------
# GET /api/v1/vvt-overview/export
# ---------------------------------------------------------------------------


async def test_vvt_overview_export_csv_returns_200(client):
    resp = await client.get("/api/v1/vvt-overview/export", params={"format": "csv"})
    assert resp.status_code == 200
    assert "csv" in resp.headers.get("content-type", "").lower()


async def test_vvt_overview_export_unsupported_format_returns_400(client):
    resp = await client.get("/api/v1/vvt-overview/export", params={"format": "xlsx"})
    assert resp.status_code == 400
