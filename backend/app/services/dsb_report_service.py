"""DSB Summary Report: build report data and render as Markdown."""
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.db import CaseModel
from app.models.schemas import (
    DSBReportResponse,
    DSBReportRisk,
    DSBReportSummary,
)
from app.services.vvt_service import normalize_vvt


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
        try:
            extraction = await normalize_vvt(raw_text)
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

    summary = DSBReportSummary(
        total_documents=total_docs,
        total_findings=total_findings,
        critical_findings=critical,
        high_findings=high,
        dsfa_required=critical > 0 or high > 0,
        vvt_completeness=vvt_completeness,
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
        f"- VVT-Vollständigkeit: {report.summary.vvt_completeness}%",
        f"- DSFA erforderlich: {'Ja' if report.summary.dsfa_required else 'Nein'}",
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
    lines.append("## Nächste Schritte")
    lines.append("")
    for step in report.next_steps:
        lines.append(f"- {step}")
    lines.append("")
    return "\n".join(lines)
