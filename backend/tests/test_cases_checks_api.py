"""Integration tests for the run-checks routes under /api/v1/cases/{case_id}/run-checks.

These tests require a live PostgreSQL database (DATABASE_URL env var). The LLM-backed
service function ``run_checks_impl`` is patched in the route module where it needs to
be, so no provider is required; ``CELERY_ENABLED=false`` keeps the synchronous fallback.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from tests.factories import create_case

pytestmark = pytest.mark.asyncio

NIL_UUID = "00000000-0000-0000-0000-000000000000"

DEFAULT_CHECKS = [
    {
        "name": "Rechtsgrundlage dokumentiert",
        "category": "Rechtsgrundlage",
        "instruction": "Prüfe, ob eine Rechtsgrundlage genannt wird.",
        "scope": "document",
    }
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_playbook(client, *, checks=None, **overrides) -> dict:
    payload = {
        "name": f"Checks-PB-{uuid.uuid4().hex[:8]}",
        "version": "1.0",
        "content": {"checks": DEFAULT_CHECKS if checks is None else checks},
        **overrides,
    }
    resp = await client.post("/api/v1/playbooks", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _add_job(case_id: str, playbook: dict, status: str, **fields) -> str:
    from app.database import async_session_factory
    from app.models.db import RunChecksJobModel

    async with async_session_factory() as session:
        job = RunChecksJobModel(
            case_id=uuid.UUID(case_id),
            status=status,
            playbook_id=uuid.UUID(playbook["id"]),
            playbook_name=playbook["name"],
            strategies=["full_text"],
            **fields,
        )
        session.add(job)
        await session.commit()
        return str(job.id)


async def _add_document(case_id: str, *, version: int = 1, doc_type: str = "other"):
    from app.database import async_session_factory
    from app.models.db import DocumentModel

    async with async_session_factory() as session:
        session.add(
            DocumentModel(
                case_id=uuid.UUID(case_id),
                name=f"doc-v{version}.pdf",
                type=doc_type,
                version=version,
                format="pdf",
                size_bytes=10,
                storage_path=f"test/{case_id}/doc-v{version}.pdf",
                extraction_status="done",
                content="Inhalt",
            )
        )
        await session.commit()


async def _set_job_status(job_id: str, status: str) -> None:
    from app.database import async_session_factory
    from app.models.db import RunChecksJobModel

    async with async_session_factory() as session:
        job = await session.get(RunChecksJobModel, uuid.UUID(job_id))
        job.status = status
        await session.commit()


def _sse_events(body: str) -> list[tuple[str, str]]:
    """Parse ``event:``/``data:`` pairs from an SSE body."""
    events: list[tuple[str, str]] = []
    for block in body.strip().split("\n\n"):
        lines = block.split("\n")
        event = next(ln[len("event: ") :] for ln in lines if ln.startswith("event: "))
        data = next(ln[len("data: ") :] for ln in lines if ln.startswith("data: "))
        events.append((event, data))
    return events


# ---------------------------------------------------------------------------
# GET /{case_id}/run-checks/status
# ---------------------------------------------------------------------------


async def test_status_unknown_case_returns_404(client):
    resp = await client.get(f"/api/v1/cases/{NIL_UUID}/run-checks/status")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Case not found"


async def test_status_never_run_for_new_case(client):
    case = await create_case(client, title=f"Status-neu-{uuid.uuid4().hex[:6]}")
    resp = await client.get(f"/api/v1/cases/{case['id']}/run-checks/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "never_run"
    assert body["job_id"] is None
    assert body["playbook_name"] is None
    assert body["last_run"] is None
    assert body["documents_changed_since_last_run"] is False
    assert body["checks_total"] == 0
    assert body["checks_done"] == 0


async def test_status_reports_failed_job(client):
    case = await create_case(client, title=f"Status-failed-{uuid.uuid4().hex[:6]}")
    playbook = await _create_playbook(client)
    job_id = await _add_job(
        case["id"],
        playbook,
        "failed",
        error="LLM nicht erreichbar",
        checks_total=3,
        checks_done=1,
    )
    resp = await client.get(f"/api/v1/cases/{case['id']}/run-checks/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "failed"
    assert body["job_id"] == job_id
    assert body["playbook_name"] == playbook["name"]
    assert body["error"] == "LLM nicht erreichbar"
    assert body["checks_total"] == 3
    assert body["checks_done"] == 1
    # documents_changed is only evaluated for completed jobs
    assert body["documents_changed_since_last_run"] is False


async def test_status_documents_changed_since_completed_job(client):
    case = await create_case(client, title=f"Status-docs-{uuid.uuid4().hex[:6]}")
    playbook = await _create_playbook(client)
    await _add_job(case["id"], playbook, "completed", findings_count=2)

    # A first-version upload after the run does not count as a re-upload.
    await _add_document(case["id"], version=1)
    resp = await client.get(f"/api/v1/cases/{case['id']}/run-checks/status")
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"
    assert resp.json()["findings_count"] == 2
    assert resp.json()["documents_changed_since_last_run"] is False

    # A re-upload (version > 1) after the job flips the flag.
    await _add_document(case["id"], version=2)
    resp = await client.get(f"/api/v1/cases/{case['id']}/run-checks/status")
    assert resp.json()["documents_changed_since_last_run"] is True


# ---------------------------------------------------------------------------
# POST /{case_id}/run-checks — validation and lookups
# ---------------------------------------------------------------------------


async def test_run_checks_unknown_case_returns_404(client):
    resp = await client.post(
        f"/api/v1/cases/{NIL_UUID}/run-checks", json={"playbook_id": NIL_UUID}
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Case not found"


async def test_run_checks_unknown_playbook_returns_404(client):
    case = await create_case(client, title=f"Run-404-pb-{uuid.uuid4().hex[:6]}")
    resp = await client.post(
        f"/api/v1/cases/{case['id']}/run-checks", json={"playbook_id": NIL_UUID}
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Playbook not found"


async def test_run_checks_missing_playbook_id_returns_422(client):
    case = await create_case(client, title=f"Run-422-{uuid.uuid4().hex[:6]}")
    resp = await client.post(f"/api/v1/cases/{case['id']}/run-checks", json={})
    assert resp.status_code == 422


async def test_run_checks_invalid_strategy_returns_422(client):
    case = await create_case(client, title=f"Run-422-strat-{uuid.uuid4().hex[:6]}")
    playbook = await _create_playbook(client)
    resp = await client.post(
        f"/api/v1/cases/{case['id']}/run-checks",
        json={"playbook_id": playbook["id"], "strategies": ["hybrid"]},
    )
    assert resp.status_code == 422


@pytest.mark.parametrize("content", [{"checks": []}, {"description": "no checks key"}])
async def test_run_checks_playbook_without_checks_returns_case(client, content):
    """Regression: the short-circuit used ``db.refresh`` and then lazy-loaded
    ``findings`` from the response model → MissingGreenlet → 500."""
    case = await create_case(client)
    playbook = await _create_playbook(client, checks=content.get("checks"))
    if "checks" not in content:
        resp = await client.patch(
            f"/api/v1/playbooks/{playbook['id']}", json={"content": content}
        )
        assert resp.status_code == 200, resp.text

    resp = await client.post(
        f"/api/v1/cases/{case['id']}/run-checks",
        json={"playbook_id": playbook["id"]},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == case["id"]
    assert body["findings"] == []


# ---------------------------------------------------------------------------
# POST /{case_id}/run-checks — synchronous fallback (Celery disabled)
# ---------------------------------------------------------------------------


async def test_run_checks_sync_writes_activity_and_returns_case(client, monkeypatch):
    from app.api.routes.cases import checks as checks_module

    payload = {"playbook_name": "PB", "findings_count": 1, "llm_calls": 1}
    impl = AsyncMock(return_value=(1, [], payload))
    monkeypatch.setattr(checks_module, "run_checks_impl", impl)

    case = await create_case(client, title=f"Run-sync-{uuid.uuid4().hex[:6]}")
    playbook = await _create_playbook(client)
    resp = await client.post(
        f"/api/v1/cases/{case['id']}/run-checks", json={"playbook_id": playbook["id"]}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == case["id"]
    assert "findings" in body

    impl.assert_awaited_once()
    args, kwargs = impl.await_args
    assert str(args[1]) == case["id"]
    assert str(args[2]) == playbook["id"]
    assert args[3] == ["full_text"]  # default strategy
    assert kwargs["skip_resolved"] is True

    status = await client.get(f"/api/v1/cases/{case['id']}/run-checks/status")
    assert status.status_code == 200
    last_run = status.json()["last_run"]
    assert last_run is not None
    assert last_run["event_type"] == "run_checks"
    assert last_run["case_id"] == case["id"]
    assert last_run["payload"] == payload


async def test_run_checks_sync_forwards_strategies_and_skip_resolved(
    client, monkeypatch
):
    from app.api.routes.cases import checks as checks_module

    impl = AsyncMock(return_value=(0, [], {}))
    monkeypatch.setattr(checks_module, "run_checks_impl", impl)

    case = await create_case(client, title=f"Run-strat-{uuid.uuid4().hex[:6]}")
    playbook = await _create_playbook(client)
    resp = await client.post(
        f"/api/v1/cases/{case['id']}/run-checks",
        json={
            "playbook_id": playbook["id"],
            "strategies": ["rag", "full_text"],
            "skip_resolved": False,
        },
    )
    assert resp.status_code == 200, resp.text
    args, kwargs = impl.await_args
    assert args[3] == ["rag", "full_text"]
    assert kwargs["skip_resolved"] is False


async def test_run_checks_sync_real_impl_without_documents(client):
    """End-to-end through the real service: no extractable documents → no LLM call,
    but an activity entry with the playbook metadata is still written."""
    case = await create_case(client, title=f"Run-real-{uuid.uuid4().hex[:6]}")
    playbook = await _create_playbook(client)
    resp = await client.post(
        f"/api/v1/cases/{case['id']}/run-checks", json={"playbook_id": playbook["id"]}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["findings"] == []

    status = await client.get(f"/api/v1/cases/{case['id']}/run-checks/status")
    last_run = status.json()["last_run"]
    assert last_run is not None
    assert last_run["payload"]["playbook_id"] == playbook["id"]
    assert last_run["payload"]["playbook_name"] == playbook["name"]
    assert last_run["payload"]["findings_count"] == 0
    assert last_run["payload"]["llm_calls"] == 0


# ---------------------------------------------------------------------------
# POST /{case_id}/run-checks — concurrency guards
# ---------------------------------------------------------------------------


async def test_run_checks_returns_409_when_job_already_running(client, monkeypatch):
    from app.api.routes.cases import checks as checks_module

    impl = AsyncMock()
    monkeypatch.setattr(checks_module, "run_checks_impl", impl)

    case = await create_case(client, title=f"Run-409-{uuid.uuid4().hex[:6]}")
    playbook = await _create_playbook(client)
    await _add_job(case["id"], playbook, "running")

    resp = await client.post(
        f"/api/v1/cases/{case['id']}/run-checks", json={"playbook_id": playbook["id"]}
    )
    assert resp.status_code == 409
    assert "already in progress" in resp.json()["detail"]
    impl.assert_not_awaited()


async def test_run_checks_running_job_for_other_playbook_does_not_block(
    client, monkeypatch
):
    from app.api.routes.cases import checks as checks_module

    impl = AsyncMock(return_value=(0, [], {}))
    monkeypatch.setattr(checks_module, "run_checks_impl", impl)

    case = await create_case(client, title=f"Run-409-other-{uuid.uuid4().hex[:6]}")
    running_pb = await _create_playbook(client)
    other_pb = await _create_playbook(client)
    await _add_job(case["id"], running_pb, "running")

    resp = await client.post(
        f"/api/v1/cases/{case['id']}/run-checks", json={"playbook_id": other_pb["id"]}
    )
    assert resp.status_code == 200, resp.text
    impl.assert_awaited_once()


async def test_run_checks_returns_423_when_advisory_lock_held(client, monkeypatch):
    import app.core.concurrency as concurrency
    from app.api.routes.cases import checks as checks_module

    impl = AsyncMock()
    monkeypatch.setattr(checks_module, "run_checks_impl", impl)
    monkeypatch.setattr(
        concurrency, "try_acquire_run_checks_lock", AsyncMock(return_value=False)
    )

    case = await create_case(client, title=f"Run-423-{uuid.uuid4().hex[:6]}")
    playbook = await _create_playbook(client)
    resp = await client.post(
        f"/api/v1/cases/{case['id']}/run-checks", json={"playbook_id": playbook["id"]}
    )
    assert resp.status_code == 423
    assert "another request" in resp.json()["detail"]
    impl.assert_not_awaited()


# ---------------------------------------------------------------------------
# POST /{case_id}/run-checks — asynchronous dispatch (Celery enabled)
# ---------------------------------------------------------------------------


async def test_run_checks_async_dispatch_returns_202_and_job(client, monkeypatch):
    from app.api.routes.cases import checks as checks_module
    from app.config import settings
    from app.database import async_session_factory
    from app.models.db import RunChecksJobModel

    monkeypatch.setattr(settings, "celery_enabled", True, raising=False)
    monkeypatch.setattr(
        settings, "celery_broker_url", "redis://test:6379/0", raising=False
    )
    dispatched: list[tuple[str, object]] = []

    def _fake_delay(job_id, request_id=None):
        dispatched.append((job_id, request_id))
        return SimpleNamespace(id=f"celery-{job_id[:8]}")

    monkeypatch.setattr(checks_module.run_playbook_checks, "delay", _fake_delay)
    impl = AsyncMock()
    monkeypatch.setattr(checks_module, "run_checks_impl", impl)

    case = await create_case(client, title=f"Run-async-{uuid.uuid4().hex[:6]}")
    playbook = await _create_playbook(client)
    resp = await client.post(
        f"/api/v1/cases/{case['id']}/run-checks",
        json={"playbook_id": playbook["id"], "strategies": ["rag"]},
    )
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["status"] == "running"
    assert body["message"]
    job_id = body["job_id"]
    assert dispatched == [(job_id, None)] or dispatched[0][0] == job_id
    impl.assert_not_awaited()  # async path never runs checks inline

    async with async_session_factory() as session:
        job = await session.get(RunChecksJobModel, uuid.UUID(job_id))
        assert job is not None
        assert job.celery_task_id == f"celery-{job_id[:8]}"
        assert job.strategies == ["rag"]
        assert job.playbook_name == playbook["name"]

    status = await client.get(f"/api/v1/cases/{case['id']}/run-checks/status")
    assert status.status_code == 200
    assert status.json()["status"] == "running"
    assert status.json()["job_id"] == job_id
    assert status.json()["playbook_name"] == playbook["name"]
    assert status.json()["documents_changed_since_last_run"] is False


# ---------------------------------------------------------------------------
# GET /{case_id}/run-checks/stream (SSE)
# ---------------------------------------------------------------------------


async def test_stream_unknown_case_returns_404(client):
    resp = await client.get(f"/api/v1/cases/{NIL_UUID}/run-checks/stream")
    assert resp.status_code == 404


async def test_stream_emits_done_immediately_when_never_run(client):
    import json

    case = await create_case(client, title=f"Stream-neu-{uuid.uuid4().hex[:6]}")
    resp = await client.get(f"/api/v1/cases/{case['id']}/run-checks/stream")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    assert resp.headers["cache-control"] == "no-cache"
    assert resp.headers["x-accel-buffering"] == "no"

    events = _sse_events(resp.text)
    assert len(events) == 1
    event, data = events[0]
    assert event == "done"
    payload = json.loads(data)
    assert payload["status"] == "never_run"
    assert payload["job_id"] is None
    assert payload["checks_total"] == 0


async def test_stream_emits_done_for_completed_job(client):
    import json

    case = await create_case(client, title=f"Stream-done-{uuid.uuid4().hex[:6]}")
    playbook = await _create_playbook(client)
    job_id = await _add_job(
        case["id"], playbook, "completed", findings_count=3, checks_total=4
    )
    resp = await client.get(f"/api/v1/cases/{case['id']}/run-checks/stream")
    assert resp.status_code == 200
    events = _sse_events(resp.text)
    assert [e for e, _ in events] == ["done"]
    payload = json.loads(events[0][1])
    assert payload["status"] == "completed"
    assert payload["job_id"] == job_id
    assert payload["findings_count"] == 3
    assert payload["checks_total"] == 4


async def test_stream_emits_progress_then_done(client, monkeypatch):
    """Running job → ``progress`` event; once the job completes the stream closes with ``done``.

    The 2 s poll sleep is replaced by a hook that completes the job in the DB, so the
    second poll observes the terminal state without waiting.
    """
    import json

    from app.api.routes.cases import checks as checks_module

    case = await create_case(client, title=f"Stream-progress-{uuid.uuid4().hex[:6]}")
    playbook = await _create_playbook(client)
    job_id = await _add_job(
        case["id"], playbook, "running", checks_total=5, checks_done=2
    )

    async def _fake_sleep(_seconds):
        await _set_job_status(job_id, "completed")

    monkeypatch.setattr(checks_module, "asyncio", SimpleNamespace(sleep=_fake_sleep))

    resp = await client.get(f"/api/v1/cases/{case['id']}/run-checks/stream")
    assert resp.status_code == 200
    events = _sse_events(resp.text)
    assert [e for e, _ in events] == ["progress", "done"]
    progress = json.loads(events[0][1])
    assert progress["status"] == "running"
    assert progress["job_id"] == job_id
    assert progress["checks_total"] == 5
    assert progress["checks_done"] == 2
    done = json.loads(events[1][1])
    assert done["status"] == "completed"
    assert done["job_id"] == job_id


async def test_stream_times_out_with_empty_done_event(client, monkeypatch):
    """A job that never finishes: after max_polls the stream ends with ``event: done`` and ``{}``."""
    from app.api.routes.cases import checks as checks_module

    case = await create_case(client, title=f"Stream-timeout-{uuid.uuid4().hex[:6]}")
    playbook = await _create_playbook(client)
    await _add_job(case["id"], playbook, "running")

    async def _no_sleep(_seconds):
        return None

    monkeypatch.setattr(checks_module, "asyncio", SimpleNamespace(sleep=_no_sleep))

    resp = await client.get(f"/api/v1/cases/{case['id']}/run-checks/stream")
    assert resp.status_code == 200
    events = _sse_events(resp.text)
    assert len(events) == 301  # 300 progress polls + final timeout marker
    assert all(e == "progress" for e, _ in events[:-1])
    assert events[-1] == ("done", "{}")
