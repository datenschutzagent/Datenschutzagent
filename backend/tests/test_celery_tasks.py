"""Unit tests for Celery task logic.

Tests the core logic of extract_document_text and related helpers
without requiring a running Celery broker, Redis, or real DB.
All external dependencies (DB session, file storage, text extraction)
are patched via unittest.mock.
"""
import uuid
from unittest.mock import MagicMock, patch, call

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
    assert _count_checks_total({"name": "Playbook"}, doc_count=2, strategies=["full_text"]) == 0


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
    assert _count_checks_total(content, doc_count=2, strategies=["full_text", "rag"]) == 6


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


def test_extract_document_text_extraction_error():
    doc_id = uuid.uuid4()
    doc = _FakeDoc(doc_id)
    mock_factory, mock_session = _make_session_factory(doc)

    with (
        patch("app.celery_app._get_session_factory", return_value=mock_factory),
        patch("app.celery_app.get_file", return_value=b"bytes"),
        patch("app.celery_app.extract_text", side_effect=RuntimeError("OCR crash")),
    ):
        result = extract_document_text(str(doc_id))

    assert result["ok"] is False
    assert "OCR crash" in result["error"]
    assert doc.extraction_status == "failed"


def test_extract_document_text_sets_processing_then_done():
    """Verifies the status transitions: pending → processing → done."""
    doc_id = uuid.uuid4()
    doc = _FakeDoc(doc_id)
    status_history: list[str] = []

    original_commit = None

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
