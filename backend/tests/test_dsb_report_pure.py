"""Unit tests for pure functions in dsb_report_service.py.

Tests compute_stale(), render_report_markdown(), and _payload_to_report()
without any database or external service dependencies.
"""

import uuid
from datetime import UTC, datetime, timedelta

from app.models.db import DSBReportModel
from app.models.schemas import DSBReportResponse, DSBReportRisk, DSBReportSummary
from app.services.dsb_report_service import (
    _payload_to_report,
    compute_stale,
    render_report_markdown,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BASE_TIME = datetime(2024, 6, 1, 12, 0, 0, tzinfo=UTC)
_LATER_TIME = _BASE_TIME + timedelta(hours=1)


def make_report_row(
    *,
    basis_document_count: int = 2,
    basis_last_run_checks_at: datetime | None = _BASE_TIME,
) -> DSBReportModel:
    row = DSBReportModel()
    row.case_id = uuid.uuid4()
    row.generated_at = _BASE_TIME
    row.payload = {}
    row.basis_document_count = basis_document_count
    row.basis_last_run_checks_at = basis_last_run_checks_at
    return row


def make_report(
    *,
    case_id: uuid.UUID | None = None,
    title: str = "Test Case",
    risks: list | None = None,
    recommendations: list | None = None,
    open_questions: list | None = None,
    next_steps: list | None = None,
    next_steps_is_suggested: bool = True,
    critical: int = 0,
    high: int = 0,
    total_docs: int = 2,
) -> DSBReportResponse:
    return DSBReportResponse(
        case_id=case_id or uuid.uuid4(),
        case_title=title,
        generated_at=_BASE_TIME,
        playbook_version="1.0",
        status="in_review",
        summary=DSBReportSummary(
            total_documents=total_docs,
            total_findings=critical + high,
            critical_findings=critical,
            high_findings=high,
            dsfa_required=bool(critical or high),
            dsfa_assessment="required" if (critical or high) else "not_required",
            vvt_completeness=80,
            vvt_available=True,
        ),
        risks=risks or [],
        open_questions=open_questions or [],
        recommendations=recommendations or [],
        next_steps=next_steps or ["Step 1", "Step 2"],
        next_steps_is_suggested=next_steps_is_suggested,
    )


# ---------------------------------------------------------------------------
# compute_stale
# ---------------------------------------------------------------------------


def test_not_stale_same_docs_same_run_at():
    row = make_report_row(basis_document_count=2, basis_last_run_checks_at=_BASE_TIME)
    stale, reason = compute_stale(
        row, current_document_count=2, current_last_run_checks_at=_BASE_TIME
    )
    assert stale is False
    assert reason is None


def test_stale_document_count_changed():
    row = make_report_row(basis_document_count=2, basis_last_run_checks_at=_BASE_TIME)
    stale, reason = compute_stale(
        row, current_document_count=3, current_last_run_checks_at=_BASE_TIME
    )
    assert stale is True
    assert reason == "new_documents"


def test_stale_newer_run_checks_at():
    row = make_report_row(basis_document_count=2, basis_last_run_checks_at=_BASE_TIME)
    stale, reason = compute_stale(
        row, current_document_count=2, current_last_run_checks_at=_LATER_TIME
    )
    assert stale is True
    assert reason == "new_analysis"


def test_stale_both_changed():
    row = make_report_row(basis_document_count=2, basis_last_run_checks_at=_BASE_TIME)
    stale, reason = compute_stale(
        row, current_document_count=5, current_last_run_checks_at=_LATER_TIME
    )
    assert stale is True
    assert reason == "both"


def test_stale_no_previous_run_but_current_run_exists():
    row = make_report_row(basis_document_count=2, basis_last_run_checks_at=None)
    stale, reason = compute_stale(
        row, current_document_count=2, current_last_run_checks_at=_BASE_TIME
    )
    assert stale is True
    assert reason == "new_analysis"


def test_not_stale_no_run_checks_ever():
    row = make_report_row(basis_document_count=2, basis_last_run_checks_at=None)
    stale, reason = compute_stale(
        row, current_document_count=2, current_last_run_checks_at=None
    )
    assert stale is False
    assert reason is None


def test_stale_only_doc_count_changed_no_run_at():
    row = make_report_row(basis_document_count=2, basis_last_run_checks_at=None)
    stale, reason = compute_stale(
        row, current_document_count=4, current_last_run_checks_at=None
    )
    assert stale is True
    assert reason == "new_documents"


# ---------------------------------------------------------------------------
# render_report_markdown
# ---------------------------------------------------------------------------


def test_render_markdown_contains_title():
    report = make_report(title="Mein Vorgang")
    md = render_report_markdown(report)
    assert "Mein Vorgang" in md


def test_render_markdown_has_overview_section():
    report = make_report()
    md = render_report_markdown(report)
    assert "## Übersicht" in md


def test_render_markdown_has_risks_section():
    report = make_report()
    md = render_report_markdown(report)
    assert "## Risiken" in md


def test_render_markdown_has_recommendations_section():
    report = make_report()
    md = render_report_markdown(report)
    assert "## Empfehlungen" in md


def test_render_markdown_no_findings_message():
    report = make_report(risks=[])
    md = render_report_markdown(report)
    assert "Keine Findings" in md


def test_render_markdown_with_risks_shows_titles():
    risks = [
        DSBReportRisk(title="DSGVO Verletzung", severity="high", description="Fehler")
    ]
    report = make_report(risks=risks)
    md = render_report_markdown(report)
    assert "DSGVO Verletzung" in md
    assert "high" in md


def test_render_markdown_with_recommendations():
    report = make_report(recommendations=["Empfehlung A", "Empfehlung B"])
    md = render_report_markdown(report)
    assert "Empfehlung A" in md
    assert "Empfehlung B" in md


def test_render_markdown_open_questions_section_appears_when_present():
    report = make_report(open_questions=["Frage 1"])
    md = render_report_markdown(report)
    assert "Offene Fragen" in md
    assert "Frage 1" in md


def test_render_markdown_open_questions_section_absent_when_empty():
    report = make_report(open_questions=[])
    md = render_report_markdown(report)
    assert "Offene Fragen" not in md


def test_render_markdown_next_steps_suggested_label():
    report = make_report(next_steps=["Schritt 1"], next_steps_is_suggested=True)
    md = render_report_markdown(report)
    assert "Vorschläge" in md


def test_render_markdown_next_steps_definitive_label():
    report = make_report(next_steps=["Schritt 1"], next_steps_is_suggested=False)
    md = render_report_markdown(report)
    assert "Nächste Schritte" in md
    assert "Vorschläge" not in md


def test_render_markdown_dsfa_unclear_message():
    report = make_report()
    report.summary.dsfa_assessment = "unclear"
    md = render_report_markdown(report)
    assert "Unklar" in md or "unclear" in md.lower()


def test_render_markdown_vvt_not_available_message():
    report = make_report()
    report.summary.vvt_available = False
    md = render_report_markdown(report)
    assert "kein VVT" in md


# ---------------------------------------------------------------------------
# _payload_to_report
# ---------------------------------------------------------------------------


def test_payload_to_report_basic():
    case_id = uuid.uuid4()
    payload = {
        "case_id": str(case_id),
        "case_title": "Test Vorgang",
        "generated_at": "2024-06-01T12:00:00+00:00",
        "playbook_version": "2.0",
        "status": "completed",
        "summary": {
            "total_documents": 3,
            "total_findings": 2,
            "critical_findings": 1,
            "high_findings": 1,
            "dsfa_required": True,
            "dsfa_assessment": "required",
            "vvt_completeness": 75,
            "vvt_available": True,
        },
        "risks": [
            {"title": "Risk A", "severity": "high", "description": "Some issue"},
        ],
        "open_questions": ["Q1"],
        "recommendations": ["Rec1"],
        "next_steps": ["Step1"],
        "next_steps_is_suggested": False,
    }
    report = _payload_to_report(payload)
    assert report.case_id == case_id
    assert report.case_title == "Test Vorgang"
    assert report.summary.total_documents == 3
    assert report.summary.critical_findings == 1
    assert len(report.risks) == 1
    assert report.risks[0].title == "Risk A"
    assert report.risks[0].severity == "high"
    assert report.open_questions == ["Q1"]
    assert report.recommendations == ["Rec1"]
    assert report.next_steps_is_suggested is False


def test_payload_to_report_empty_risks():
    case_id = uuid.uuid4()
    payload = {
        "case_id": str(case_id),
        "case_title": "Empty",
        "generated_at": "2024-06-01T12:00:00Z",
        "playbook_version": "",
        "status": "intake",
        "summary": {},
        "risks": [],
        "open_questions": [],
        "recommendations": [],
        "next_steps": [],
        "next_steps_is_suggested": True,
    }
    report = _payload_to_report(payload)
    assert report.risks == []
    assert report.summary.total_documents == 0
