"""DSB Summary Report: build report data, persist, and render as Markdown."""
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.db import ActivityLogModel, CaseModel, DSBReportModel
from app.models.schemas import (
    DSBReportResponse,
    DSBReportRisk,
    DSBReportSummary,
)
from app.services.vvt_service import normalize_vvt


async def get_last_run_checks_at(case_id: UUID, db: AsyncSession) -> datetime | None:
    """Return created_at of the latest run_checks activity for the case, or None."""
    result = await db.execute(
        select(ActivityLogModel)
        .where(
            ActivityLogModel.case_id == case_id,
            ActivityLogModel.event_type == "run_checks",
        )
        .order_by(ActivityLogModel.created_at.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    return row.created_at if row else None


async def save_report(case_id: UUID, report: DSBReportResponse, db: AsyncSession) -> None:
    """Persist report for the case; overwrites existing. Stores basis for staleness checks."""
    last_run_at = await get_last_run_checks_at(case_id, db)
    payload = report.model_dump(mode="json")
    model = DSBReportModel(
        case_id=case_id,
        generated_at=report.generated_at,
        payload=payload,
        basis_document_count=report.summary.total_documents,
        basis_last_run_checks_at=last_run_at,
    )
    await db.merge(model)
    await db.flush()


def _payload_to_report(payload: dict) -> DSBReportResponse:
    """Build DSBReportResponse from stored JSONB payload."""
    from app.models.schemas import DSBReportRisk

    summary = payload.get("summary") or {}
    risks = [
        DSBReportRisk(
            title=r.get("title", ""),
            severity=r.get("severity", "medium"),
            description=r.get("description", ""),
        )
        for r in payload.get("risks") or []
    ]
    return DSBReportResponse(
        case_id=UUID(payload["case_id"]) if isinstance(payload.get("case_id"), str) else payload["case_id"],
        case_title=payload.get("case_title", ""),
        generated_at=datetime.fromisoformat(payload["generated_at"].replace("Z", "+00:00")) if isinstance(payload.get("generated_at"), str) else payload["generated_at"],
        playbook_version=payload.get("playbook_version", ""),
        status=payload.get("status", ""),
        summary=DSBReportSummary(
            total_documents=summary.get("total_documents", 0),
            total_findings=summary.get("total_findings", 0),
            critical_findings=summary.get("critical_findings", 0),
            high_findings=summary.get("high_findings", 0),
            dsfa_required=summary.get("dsfa_required", False),
            dsfa_assessment=summary.get("dsfa_assessment", "unclear"),
            vvt_completeness=summary.get("vvt_completeness", 0),
            vvt_available=summary.get("vvt_available", False),
        ),
        risks=risks,
        open_questions=payload.get("open_questions") or [],
        recommendations=payload.get("recommendations") or [],
        next_steps=payload.get("next_steps") or [],
        next_steps_is_suggested=payload.get("next_steps_is_suggested", True),
    )


async def get_latest_report(case_id: UUID, db: AsyncSession) -> DSBReportModel | None:
    """Load the latest stored report row for the case, or None."""
    result = await db.execute(select(DSBReportModel).where(DSBReportModel.case_id == case_id))
    return result.scalar_one_or_none()


def compute_stale(
    report_row: DSBReportModel,
    current_document_count: int,
    current_last_run_checks_at: datetime | None,
) -> tuple[bool, str | None]:
    """Return (report_stale, stale_reason). stale_reason is 'new_documents' | 'new_analysis' | 'both'."""
    doc_changed = current_document_count != report_row.basis_document_count
    run_newer = False
    if current_last_run_checks_at and report_row.basis_last_run_checks_at:
        run_newer = current_last_run_checks_at > report_row.basis_last_run_checks_at
    elif current_last_run_checks_at and not report_row.basis_last_run_checks_at:
        run_newer = True
    if doc_changed and run_newer:
        return True, "both"
    if doc_changed:
        return True, "new_documents"
    if run_newer:
        return True, "new_analysis"
    return False, None


async def build_dsb_report(case_id: UUID, db: AsyncSession) -> DSBReportResponse:
    """
    Build DSB report for a case: load case with documents and findings,
    optionally compute VVT summary from first VVT document, return structured report.
    """
    result = await db.execute(
        select(CaseModel)
        .where(CaseModel.id == case_id)
        .options(
            selectinload(CaseModel.documents),
            selectinload(CaseModel.findings),
        )
    )
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    total_docs = len(case.documents)
    findings = list(case.findings)
    total_findings = len(findings)
    critical = sum(1 for f in findings if f.severity == "critical")
    high = sum(1 for f in findings if f.severity == "high")
    vvt_completeness = 0
    source_template = ""

    vvt_docs = [d for d in case.documents if d.type == "vvt"]
    if vvt_docs:
        raw_text = vvt_docs[0].content or ""
        case_lang = getattr(case, "language", None)
        try:
            extraction = await normalize_vvt(raw_text, language=case_lang)
            total_fields = len(extraction.fields)
            filled = sum(1 for f in extraction.fields if f.status == "filled")
            vvt_completeness = round((filled / total_fields) * 100) if total_fields else 0
            source_template = extraction.source_template or ""
        except Exception:
            pass

    risks = [
        DSBReportRisk(
            title=f.check_name,
            severity=f.severity if f.severity in ("critical", "high", "medium", "low", "info") else "medium",
            description=f.description or "",
        )
        for f in findings
    ]
    recommendations = list({f.recommendation for f in findings if f.recommendation and f.recommendation.strip()})
    open_questions = []
    for f in findings:
        if f.status == "open" and f.recommendation and f.recommendation.strip():
            open_questions.append(f.recommendation)

    next_steps = [
        "Rückmeldung an Antragsteller mit offenen Punkten",
        "Nach Revision: Playbook erneut durchlaufen",
        "Abschließende Entscheidungsvorlage für DSB",
    ]

    last_run_at = await get_last_run_checks_at(case_id, db)
    if last_run_at is None:
        dsfa_assessment = "unclear"
    elif critical > 0 or high > 0:
        dsfa_assessment = "required"
    else:
        dsfa_assessment = "not_required"

    summary = DSBReportSummary(
        total_documents=total_docs,
        total_findings=total_findings,
        critical_findings=critical,
        high_findings=high,
        dsfa_required=critical > 0 or high > 0,
        dsfa_assessment=dsfa_assessment,
        vvt_completeness=vvt_completeness,
        vvt_available=bool(vvt_docs),
    )

    return DSBReportResponse(
        case_id=case.id,
        case_title=case.title,
        generated_at=datetime.now(timezone.utc),
        playbook_version=case.playbook_version or "",
        status=case.status,
        summary=summary,
        risks=risks,
        open_questions=open_questions,
        recommendations=recommendations,
        next_steps=next_steps,
        next_steps_is_suggested=True,
    )


def render_report_markdown(report: DSBReportResponse) -> str:
    """Render DSB report as Markdown string."""
    lines = [
        f"# DSB Summary Report: {report.case_title}",
        "",
        f"**Vorgang:** {report.case_id}  ",
        f"**Status:** {report.status}  ",
        f"**Erstellt:** {report.generated_at.isoformat()}  ",
        f"**Playbook-Version:** {report.playbook_version or '-'}",
        "",
        "---",
        "",
        "## Übersicht",
        "",
        f"- Dokumente: {report.summary.total_documents}",
        f"- Findings gesamt: {report.summary.total_findings}",
        f"- Kritisch: {report.summary.critical_findings}, Hoch: {report.summary.high_findings}",
        f"- VVT-Vollständigkeit: {'– (kein VVT vorhanden)' if not report.summary.vvt_available else f'{report.summary.vvt_completeness}%'}",
        f"- DSFA erforderlich: {'Unklar (noch keine Check-Läufe durchgeführt)' if report.summary.dsfa_assessment == 'unclear' else ('Ja' if report.summary.dsfa_required else 'Nein')}",
        "",
        "---",
        "",
        "## Risiken / Findings",
        "",
    ]
    if not report.risks:
        lines.append("*Keine Findings.*")
        lines.append("")
    else:
        for r in report.risks:
            lines.append(f"### {r.title}")
            lines.append(f"- **Severity:** {r.severity}")
            lines.append(f"- {r.description}")
            lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Empfehlungen")
    lines.append("")
    if not report.recommendations:
        lines.append("*Keine.*")
        lines.append("")
    else:
        for rec in report.recommendations:
            lines.append(f"- {rec}")
        lines.append("")
    if report.open_questions:
        lines.append("## Offene Fragen")
        lines.append("")
        for q in report.open_questions:
            lines.append(f"- {q}")
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Nächste Schritte (Vorschläge)" if report.next_steps_is_suggested else "## Nächste Schritte")
    lines.append("")
    for step in report.next_steps:
        lines.append(f"- {step}")
    lines.append("")
    return "\n".join(lines)
