"""Unit tests for DSB report service functions that require DB interaction.

Uses unittest.mock.AsyncMock to avoid real DB connections.
Tests get_last_run_checks_at() and save_report() in isolation.
build_dsb_report() is complex enough that it is better tested via integration tests.
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.schemas import DSBReportResponse, DSBReportRisk, DSBReportSummary
from app.services.dsb_report_service import get_last_run_checks_at, save_report

pytestmark = pytest.mark.asyncio

_NOW = datetime(2024, 6, 1, 12, 0, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db_session() -> AsyncMock:
    """Build a minimal AsyncSession mock.

    The execute() result must be a sync MagicMock: AsyncMock children are AsyncMock
    themselves, so result.scalar_one_or_none() would return a coroutine instead of
    the configured value (the production code calls it synchronously).
    """
    db = AsyncMock()
    db.execute.return_value = MagicMock()
    return db


def _make_report(case_id: uuid.UUID | None = None) -> DSBReportResponse:
    return DSBReportResponse(
        case_id=case_id or uuid.uuid4(),
        case_title="Test Vorgang",
        generated_at=_NOW,
        playbook_version="1.0",
        status="in_review",
        summary=DSBReportSummary(
            total_documents=2,
            total_findings=1,
            critical_findings=0,
            high_findings=1,
            dsfa_required=True,
            dsfa_assessment="required",
            vvt_completeness=70,
            vvt_available=True,
        ),
        risks=[DSBReportRisk(title="Issue", severity="high", description="Some issue")],
        open_questions=["Q1"],
        recommendations=["Rec1"],
        next_steps=["Step1"],
        next_steps_is_suggested=True,
    )


# ---------------------------------------------------------------------------
# get_last_run_checks_at
# ---------------------------------------------------------------------------


async def test_get_last_run_checks_at_returns_none_when_no_activity():
    db = _make_db_session()
    db.execute.return_value.scalar_one_or_none.return_value = None

    result = await get_last_run_checks_at(uuid.uuid4(), db)

    assert result is None
    db.execute.assert_called_once()


async def test_get_last_run_checks_at_returns_created_at_from_row():
    db = _make_db_session()
    mock_row = MagicMock()
    mock_row.created_at = _NOW
    db.execute.return_value.scalar_one_or_none.return_value = mock_row

    result = await get_last_run_checks_at(uuid.uuid4(), db)

    assert result == _NOW


# ---------------------------------------------------------------------------
# save_report
# ---------------------------------------------------------------------------


async def test_save_report_calls_merge_and_flush():
    case_id = uuid.uuid4()
    db = _make_db_session()
    # Make get_last_run_checks_at return None (no prior activity)
    db.execute.return_value.scalar_one_or_none.return_value = None

    report = _make_report(case_id=case_id)
    await save_report(case_id, report, db)

    db.merge.assert_called_once()
    db.flush.assert_called()


async def test_save_report_stores_correct_basis_document_count():
    """The model passed to merge() should carry the correct basis_document_count."""
    case_id = uuid.uuid4()
    db = _make_db_session()
    db.execute.return_value.scalar_one_or_none.return_value = None

    report = _make_report(case_id=case_id)
    report.summary.total_documents = 5

    await save_report(case_id, report, db)

    # Extract the DSBReportModel passed to merge
    call_args = db.merge.call_args
    saved_model = call_args[0][0]
    assert saved_model.basis_document_count == 5


async def test_save_report_stores_last_run_checks_at():
    """basis_last_run_checks_at should be set from the last activity timestamp."""
    case_id = uuid.uuid4()
    db = _make_db_session()
    mock_activity = MagicMock()
    mock_activity.created_at = _NOW
    db.execute.return_value.scalar_one_or_none.return_value = mock_activity

    report = _make_report(case_id=case_id)
    await save_report(case_id, report, db)

    call_args = db.merge.call_args
    saved_model = call_args[0][0]
    assert saved_model.basis_last_run_checks_at == _NOW


async def test_save_report_stores_none_when_no_activity():
    """basis_last_run_checks_at is None when no run_checks activity exists."""
    case_id = uuid.uuid4()
    db = _make_db_session()
    db.execute.return_value.scalar_one_or_none.return_value = None

    report = _make_report(case_id=case_id)
    await save_report(case_id, report, db)

    call_args = db.merge.call_args
    saved_model = call_args[0][0]
    assert saved_model.basis_last_run_checks_at is None
