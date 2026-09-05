"""Unit tests for Celery task logic.

Tests the core logic of extract_document_text and related helpers
without requiring a running Celery broker, Redis, or real DB.
All external dependencies (DB session, file storage, text extraction)
are patched via unittest.mock.
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.celery_app import (
    _count_checks_total,
    _set_extraction_failed,
    extract_document_text,
)

# ---------------------------------------------------------------------------
# _count_checks_total (pure function)
# ---------------------------------------------------------------------------


def test_count_checks_total_empty_playbook():
    assert _count_checks_total({}, doc_count=3, strategies=["full_text"]) == 0


def test_count_checks_total_no_checks_key():
    assert (
        _count_checks_total({"name": "Playbook"}, doc_count=2, strategies=["full_text"])
        == 0
    )


def test_count_checks_total_document_scoped_single_strategy():
    content = {
        "checks": [
            {"name": "Check A", "scope": "document"},
            {"name": "Check B", "scope": "document"},
        ]
    }
    # 2 doc-checks × 3 docs × 1 strategy
    assert _count_checks_total(content, doc_count=3, strategies=["full_text"]) == 6


def test_count_checks_total_case_scoped_checks():
    content = {
        "checks": [
            {"name": "Check A", "scope": "case"},
            {"name": "Check B", "scope": "cross_document"},
        ]
    }
    # 0 doc-checks × n + 2 case-checks × 1 strategy
    assert _count_checks_total(content, doc_count=5, strategies=["full_text"]) == 2


def test_count_checks_total_mixed_checks_two_strategies():
    content = {
        "checks": [
            {"name": "Doc Check", "scope": "document"},
            {"name": "Case Check", "scope": "case"},
        ]
    }
    # (1 doc-check × 2 docs + 1 case-check) × 2 strategies = (2+1) × 2 = 6
    assert (
        _count_checks_total(content, doc_count=2, strategies=["full_text", "rag"]) == 6
    )


def test_count_checks_total_zero_docs_defaults_to_one():
    content = {"checks": [{"name": "Doc Check", "scope": "document"}]}
    # doc_count=0 → treated as 1
    assert _count_checks_total(content, doc_count=0, strategies=["full_text"]) == 1


def test_count_checks_total_checks_without_scope_treated_as_document():
    """Checks with no 'scope' key should be counted as document-scoped."""
    content = {
        "checks": [
            {"name": "No Scope Check"},
        ]
    }
    assert _count_checks_total(content, doc_count=4, strategies=["full_text"]) == 4


# ---------------------------------------------------------------------------
# _set_extraction_failed
# ---------------------------------------------------------------------------


def test_set_extraction_failed_updates_document():
    doc_id = uuid.uuid4()
    mock_doc = MagicMock()
    mock_session = MagicMock()
    mock_session.execute.return_value.scalar_one_or_none.return_value = mock_doc

    _set_extraction_failed(mock_session, doc_id, "ocr_timeout")

    assert mock_doc.extraction_status == "failed"
    assert mock_doc.extraction_error == "ocr_timeout"
    mock_session.commit.assert_called_once()


def test_set_extraction_failed_no_document_does_nothing():
    doc_id = uuid.uuid4()
    mock_session = MagicMock()
    mock_session.execute.return_value.scalar_one_or_none.return_value = None

    _set_extraction_failed(mock_session, doc_id, "file_not_found")

    mock_session.commit.assert_not_called()


# ---------------------------------------------------------------------------
# extract_document_text task logic
# ---------------------------------------------------------------------------


class _FakeDoc:
    """Minimal document model stub."""

    def __init__(self, doc_id: uuid.UUID, storage_path: str = "/fake/path/doc.pdf"):
        self.id = doc_id
        self.name = "test.pdf"
        self.storage_path = storage_path
        self.case_id = uuid.uuid4()
        self.content = None
        self.extraction_status = "pending"
        self.extraction_method = None
        self.extraction_error = None


def _make_session_factory(doc: _FakeDoc | None):
    """Return a patched _get_session_factory that yields a session with `doc`."""
    mock_session = MagicMock()
    mock_session.execute.return_value.scalar_one_or_none.return_value = doc
    mock_factory = MagicMock(return_value=mock_session)
    return mock_factory, mock_session


def test_extract_document_text_success():
    doc_id = uuid.uuid4()
    doc = _FakeDoc(doc_id)
    mock_factory, mock_session = _make_session_factory(doc)

    fake_result = MagicMock()
    fake_result.text = "Extracted document text."
    fake_result.extraction_method = "text"

    with (
        patch("app.celery_app._get_session_factory", return_value=mock_factory),
        patch("app.celery_app.get_file", return_value=b"PDF bytes"),
        patch("app.celery_app.extract_text", return_value=fake_result),
        patch("app.celery_app._maybe_auto_run_checks"),
        patch("app.celery_app.index_document_chunks", return_value=False),
    ):
        result = extract_document_text(str(doc_id))

    assert result["ok"] is True
    assert doc.extraction_status == "done"
    assert doc.content == "Extracted document text."
    assert doc.extraction_method == "text"


def test_extract_document_text_document_not_found():
    doc_id = uuid.uuid4()
    mock_factory, mock_session = _make_session_factory(None)  # No document in DB

    with patch("app.celery_app._get_session_factory", return_value=mock_factory):
        result = extract_document_text(str(doc_id))

    assert result["ok"] is False
    assert result["error"] == "document_not_found"


def test_extract_document_text_no_storage_path():
    doc_id = uuid.uuid4()
    doc = _FakeDoc(doc_id, storage_path="")  # Empty path
    mock_factory, mock_session = _make_session_factory(doc)

    with patch("app.celery_app._get_session_factory", return_value=mock_factory):
        result = extract_document_text(str(doc_id))

    assert result["ok"] is False
    assert result["error"] == "no_storage_path"


def test_extract_document_text_file_not_found():
    doc_id = uuid.uuid4()
    doc = _FakeDoc(doc_id)
    mock_factory, mock_session = _make_session_factory(doc)

    with (
        patch("app.celery_app._get_session_factory", return_value=mock_factory),
        patch("app.celery_app.get_file", side_effect=FileNotFoundError("missing")),
    ):
        result = extract_document_text(str(doc_id))

    assert result["ok"] is False
    assert result["error"] == "file_not_found"
    assert doc.extraction_status == "failed"


def test_extract_document_text_unexpected_error_marks_failed_and_raises():
    """Phase 2 R2: unexpected errors surface as Celery FAILURE, not as a SUCCESS result."""
    doc_id = uuid.uuid4()
    doc = _FakeDoc(doc_id)
    mock_factory, mock_session = _make_session_factory(doc)

    with (
        patch("app.celery_app._get_session_factory", return_value=mock_factory),
        patch("app.celery_app.get_file", return_value=b"bytes"),
        patch("app.celery_app.extract_text", side_effect=RuntimeError("OCR crash")),
        pytest.raises(RuntimeError, match="OCR crash"),
    ):
        extract_document_text(str(doc_id))

    assert doc.extraction_status == "failed"
    assert "OCR crash" in doc.extraction_error


def test_extract_document_text_unsupported_document_is_terminal():
    from app.services.document_processor import UnsupportedDocumentError

    doc_id = uuid.uuid4()
    doc = _FakeDoc(doc_id)
    mock_factory, mock_session = _make_session_factory(doc)

    with (
        patch("app.celery_app._get_session_factory", return_value=mock_factory),
        patch("app.celery_app.get_file", return_value=b"bytes"),
        patch(
            "app.celery_app.extract_text",
            side_effect=UnsupportedDocumentError("PDF verschlüsselt"),
        ),
    ):
        result = extract_document_text(str(doc_id))

    assert result["ok"] is False
    assert "verschlüsselt" in result["error"]
    assert doc.extraction_status == "failed"


def test_extract_document_text_transient_error_is_retried():
    """Storage/network hiccups (OSError) go through task.retry with backoff."""
    from app import celery_app

    doc_id = uuid.uuid4()
    doc = _FakeDoc(doc_id)
    mock_factory, mock_session = _make_session_factory(doc)
    retry_calls: list[dict] = []

    class _Retried(Exception):
        pass

    def _fake_retry(**kwargs):
        retry_calls.append(kwargs)
        return _Retried()

    with (
        patch("app.celery_app._get_session_factory", return_value=mock_factory),
        patch("app.celery_app.get_file", side_effect=ConnectionError("minio down")),
        patch.object(celery_app.extract_document_text, "retry", _fake_retry),
        pytest.raises(_Retried),
    ):
        extract_document_text(str(doc_id))

    assert len(retry_calls) == 1
    assert retry_calls[0]["countdown"] == celery_app.TASK_RETRY_BACKOFF_SECONDS[0]
    assert retry_calls[0]["max_retries"] == celery_app.TASK_MAX_RETRIES
    # Still "processing": the retry will pick it up, no premature FAILED state.
    assert doc.extraction_status == "processing"


def test_run_playbook_checks_llm_outage_is_retried_and_budget_is_not():
    from app import celery_app
    from app.core.exceptions import LLMBudgetExceededError, LLMProviderError

    retried: list[dict] = []

    class _Retried(Exception):
        pass

    def _fake_retry(**kwargs):
        retried.append(kwargs)
        return _Retried()

    with (
        patch(
            "app.celery_app.asyncio.run", side_effect=LLMProviderError("breaker open")
        ),
        patch("app.celery_app._set_run_checks_job_failed") as mark_failed,
        patch.object(celery_app.run_playbook_checks, "retry", _fake_retry),
        pytest.raises(_Retried),
    ):
        celery_app.run_playbook_checks(str(uuid.uuid4()))
    assert len(retried) == 1
    mark_failed.assert_not_called()

    job_id = str(uuid.uuid4())
    with (
        patch(
            "app.celery_app.asyncio.run", side_effect=LLMBudgetExceededError("budget")
        ),
        patch("app.celery_app._set_run_checks_job_failed") as mark_failed,
        pytest.raises(LLMBudgetExceededError),
    ):
        celery_app.run_playbook_checks(job_id)
    mark_failed.assert_called_once()
    assert mark_failed.call_args.args[0] == job_id


def test_run_playbook_checks_programming_error_marks_failed_and_raises():
    from app import celery_app

    job_id = str(uuid.uuid4())
    with (
        patch(
            "app.celery_app.asyncio.run", side_effect=ValueError("Playbook not found")
        ),
        patch("app.celery_app._set_run_checks_job_failed") as mark_failed,
        pytest.raises(ValueError),
    ):
        celery_app.run_playbook_checks(job_id)
    mark_failed.assert_called_once_with(job_id, "Playbook not found")


def test_extract_document_text_sets_processing_then_done():
    """Verifies the status transitions: pending → processing → done."""
    doc_id = uuid.uuid4()
    doc = _FakeDoc(doc_id)
    status_history: list[str] = []

    def track_commit():
        status_history.append(doc.extraction_status)

    mock_factory, mock_session = _make_session_factory(doc)
    mock_session.commit.side_effect = track_commit

    fake_result = MagicMock()
    fake_result.text = "text"
    fake_result.extraction_method = "text"

    with (
        patch("app.celery_app._get_session_factory", return_value=mock_factory),
        patch("app.celery_app.get_file", return_value=b"bytes"),
        patch("app.celery_app.extract_text", return_value=fake_result),
        patch("app.celery_app._maybe_auto_run_checks"),
        patch("app.celery_app.index_document_chunks", return_value=False),
    ):
        extract_document_text(str(doc_id))

    assert "processing" in status_history
    assert "done" in status_history
    assert status_history.index("processing") < status_history.index("done")


# ---------------------------------------------------------------------------
# periodic_recheck: jobs must be committed BEFORE the Celery dispatch, otherwise
# the worker's own session cannot find the job row.
# ---------------------------------------------------------------------------


def test_periodic_recheck_dispatches_after_commit():
    import asyncio
    from datetime import UTC, datetime, timedelta
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from app import celery_app

    old = datetime.now(UTC) - timedelta(days=30)
    case = SimpleNamespace(
        id=uuid.uuid4(),
        recheck_interval_days=7,
        last_rechecked_at=old,
        created_at=old,
        department="IT",
        processing_context=None,
        case_type="Softwareeinführung",
    )
    playbook = SimpleNamespace(id=uuid.uuid4(), name="PB")

    cases_result = MagicMock()
    cases_result.scalars.return_value.all.return_value = [case]
    playbooks_result = MagicMock()
    playbooks_result.scalars.return_value.all.return_value = [playbook]

    session = MagicMock()
    session.execute = AsyncMock(side_effect=[cases_result, playbooks_result])
    session.flush = AsyncMock()
    committed: list[bool] = []

    async def _commit():
        committed.append(True)

    session.commit = _commit
    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=False)

    dispatched_after_commit: list[bool] = []

    def _apply_async(args, countdown=0):
        dispatched_after_commit.append(bool(committed))

    with (
        patch("app.celery_app._get_async_session_factory", return_value=factory),
        patch(
            "app.celery_app.rank_playbooks_for_selection",
            return_value=[(playbook, 1.0)],
        ),
        patch("app.celery_app._parse_recheck_strategies", return_value=["full_text"]),
        patch.object(celery_app.run_playbook_checks, "apply_async", _apply_async),
    ):
        result = asyncio.run(celery_app._periodic_recheck_async())

    assert result == {"queued": 1}
    assert dispatched_after_commit == [True]
    assert case.last_rechecked_at > old
