"""Integration tests for the /api/v1/cases routes.

These tests require a live PostgreSQL database (DATABASE_URL env var).
They test create, read, update, and delete behaviour for cases and findings.
"""

import uuid

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


# ---------------------------------------------------------------------------
# Export ↔ list filter parity (regression: export treated has_open_findings as
# "has a document")
# ---------------------------------------------------------------------------


async def _add_finding(case_id: str, status: str = "open") -> None:
    from app.database import async_session_factory
    from app.models.db import FindingModel

    async with async_session_factory() as session:
        session.add(
            FindingModel(
                case_id=uuid.UUID(case_id),
                check_name="check",
                severity="high",
                status=status,
                category="test",
                description="desc",
            )
        )
        await session.commit()


async def _add_document(case_id: str) -> None:
    from app.database import async_session_factory
    from app.models.db import DocumentModel

    async with async_session_factory() as session:
        session.add(
            DocumentModel(
                case_id=uuid.UUID(case_id),
                name="doc.pdf",
                type="other",
                format="pdf",
                size_bytes=10,
                storage_path=f"test/{case_id}/doc.pdf",
            )
        )
        await session.commit()


async def test_export_has_open_findings_matches_list_filter(client):
    with_finding = await _create_case(client, title="Export-mit-Befund")
    doc_only = await _create_case(client, title="Export-nur-Dokument")
    fixed_only = await _create_case(client, title="Export-behobener-Befund")
    await _add_finding(with_finding["id"], status="open")
    await _add_document(doc_only["id"])
    await _add_finding(fixed_only["id"], status="fixed")

    list_resp = await client.get(
        "/api/v1/cases", params={"has_open_findings": "true", "limit": 500}
    )
    assert list_resp.status_code == 200
    listed_ids = {c["id"] for c in list_resp.json()["items"]}

    export_resp = await client.get(
        "/api/v1/cases/export", params={"has_open_findings": "true"}
    )
    assert export_resp.status_code == 200
    csv_text = export_resp.content.decode("utf-8-sig")
    exported_ids = {
        row.split(",")[0] for row in csv_text.splitlines()[1:] if row.strip()
    }

    assert with_finding["id"] in listed_ids
    assert with_finding["id"] in exported_ids
    # "Offene Befunde" column is computed in SQL (correlated subquery), not in Python.
    row = next(r for r in csv_text.splitlines()[1:] if r.startswith(with_finding["id"]))
    assert row.split(",")[10] == "1"
    for excluded in (doc_only["id"], fixed_only["id"]):
        assert excluded not in listed_ids
        assert excluded not in exported_ids


async def test_export_accepts_deadline_overdue_filter(client):
    """The export exposes the same filter set as the list endpoint."""
    overdue = await _create_case(
        client, title="Export-überfällig", deadline="2000-01-01"
    )
    # Regression: POST /cases accepted ``deadline`` but never persisted it.
    assert overdue["deadline"] == "2000-01-01"
    resp = await client.get("/api/v1/cases/export", params={"deadline_overdue": "true"})
    assert resp.status_code == 200
    assert overdue["id"] in resp.content.decode("utf-8-sig")

    listed = await client.get(
        "/api/v1/cases", params={"deadline_overdue": "true", "limit": 500}
    )
    assert overdue["id"] in {c["id"] for c in listed.json()["items"]}


# ---------------------------------------------------------------------------
# DSB report job: commit BEFORE dispatching the Celery task (worker must see the row)
# ---------------------------------------------------------------------------


async def test_generate_dsb_report_commits_before_dispatch(client, monkeypatch):
    from unittest.mock import patch

    from app.api.routes.cases import crud
    from app.config import settings
    from app.database import async_session_factory, get_db
    from app.main import app

    monkeypatch.setattr(settings, "celery_enabled", True, raising=False)
    monkeypatch.setattr(
        settings, "celery_broker_url", "redis://test:6379/0", raising=False
    )
    case = await _create_case(client, title="DSB-Report-Dispatch")

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

    app.dependency_overrides[get_db] = _tracked_db
    try:
        with patch.object(crud.build_dsb_report_task, "delay", _fake_delay):
            resp = await client.post(f"/api/v1/cases/{case['id']}/dsb-report/generate")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 202, resp.text
    assert dispatched_after_commits == [1], "task must be dispatched after commit"
