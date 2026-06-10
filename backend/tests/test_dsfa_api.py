"""Integration tests for the DSFA screening endpoint (Art. 35 DSGVO).

These tests require a live PostgreSQL database (DATABASE_URL env var).
DSFA screening is case-scoped: a case must exist before calling the endpoint.
"""

import pytest

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


async def _create_case(client, **overrides) -> dict:
    payload = {
        "title": "DSFA-Test-Vorgang",
        "department": "Forschung",
        "case_type": "Forschungsprojekt",
        "language": "de",
        "created_by": "test@example.com",
        "assignee": "DSB Team",
        **overrides,
    }
    resp = await client.post("/api/v1/cases", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# DSFA Screening
# ---------------------------------------------------------------------------


async def test_dsfa_screening_returns_result(client):
    case = await _create_case(client, title="DSFA Screening Smoke Test")
    case_id = case["id"]

    resp = await client.get(f"/api/v1/cases/{case_id}/dsfa/screening")
    assert resp.status_code == 200
    data = resp.json()
    assert "required" in data
    assert "score" in data
    assert "factors" in data
    assert "recommendation" in data
    assert isinstance(data["required"], bool)
    assert isinstance(data["score"], int)
    assert isinstance(data["factors"], list)
    assert isinstance(data["recommendation"], str)


async def test_dsfa_screening_requires_valid_case(client):
    resp = await client.get(
        "/api/v1/cases/00000000-0000-0000-0000-000000000000/dsfa/screening"
    )
    assert resp.status_code == 404


async def test_dsfa_screening_has_factors(client):
    case = await _create_case(client, title="DSFA Faktoren Test")
    case_id = case["id"]

    resp = await client.get(f"/api/v1/cases/{case_id}/dsfa/screening")
    assert resp.status_code == 200
    data = resp.json()
    factors = data["factors"]
    assert isinstance(factors, list)
    assert len(factors) > 0
    for factor in factors:
        assert "name" in factor, f"Factor missing 'name': {factor}"
        assert "triggered" in factor, f"Factor missing 'triggered': {factor}"
        assert "rationale" in factor, f"Factor missing 'rationale': {factor}"
