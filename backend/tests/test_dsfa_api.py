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
    # Weighted factor score (configurable weights in risk_config) — numeric, not necessarily int.
    assert isinstance(data["score"], int | float)
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
        assert "id" in factor, f"Factor missing 'id': {factor}"
        assert "label" in factor, f"Factor missing 'label': {factor}"
        assert "met" in factor, f"Factor missing 'met': {factor}"
        assert "description" in factor, f"Factor missing 'description': {factor}"
        assert "weight" in factor, f"Factor missing 'weight': {factor}"


async def test_generate_dsfa_commits_before_dispatch(client, monkeypatch):
    """The Celery worker opens its own session: the job row must be committed first."""
    from unittest.mock import MagicMock, patch

    from app import celery_app
    from app.config import settings
    from app.database import async_session_factory, get_db
    from app.main import app

    monkeypatch.setattr(settings, "celery_enabled", True, raising=False)
    case = await _create_case(client, title="DSFA-Dispatch")

    commits: list[int] = []
    dispatched_after_commits: list[int] = []

    async def _tracked_db():
        async with async_session_factory() as session:
            original_commit = session.commit

            async def _commit():
                await original_commit()
                commits.append(1)

            session.commit = _commit  # type: ignore[method-assign]
            try:
                yield session
                await session.commit()
            finally:
                await session.close()

    def _fake_delay(job_id, request_id=None):
        dispatched_after_commits.append(len(commits))
        return MagicMock(id="celery-task-id")

    app.dependency_overrides[get_db] = _tracked_db
    try:
        with patch.object(celery_app.build_dsfa_task, "delay", _fake_delay):
            resp = await client.post(f"/api/v1/cases/{case['id']}/dsfa/generate")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 202, resp.text
    assert dispatched_after_commits == [1], "task must be dispatched after commit"
    # Job row is visible in a fresh request/session, i.e. it was committed.
    status_resp = await client.get(f"/api/v1/cases/{case['id']}/dsfa/status")
    assert status_resp.status_code == 200, status_resp.text
    assert status_resp.json()["job_id"] == resp.json()["job_id"]
