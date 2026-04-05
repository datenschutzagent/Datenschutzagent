"""Findings API: list, update, bulk-update, CSV export, DOCX export, comments."""
import csv
import io
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from docx import Document as DocxDocument
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import require_roles
from app.database import get_db
from app.models.db import (
    ActivityLogModel,
    CaseModel,
    DocumentModel,
    FindingCommentModel,
    FindingModel,
    UserModel,
    orm_to_finding_comment_response,
    orm_to_finding_response,
)
from app.models.schemas import (
    FindingBulkUpdate,
    FindingCommentCreate,
    FindingCommentResponse,
    FindingListResponse,
    FindingResponse,
    FindingUpdate,
)

router = APIRouter()

EXPORT_MAX = 5000


@router.get("", response_model=FindingListResponse)
async def list_findings(
    case_id: Annotated[UUID | None, Query()] = None,
    severity: Annotated[str | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
    category: Annotated[str | None, Query()] = None,
    source_strategy: Annotated[str | None, Query(description="Filter by check source: full_text or rag")] = None,
    has_due_date: Annotated[bool | None, Query(description="True = only findings with a due date set")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("viewer", "editor", "admin"),
):
    """List findings with optional filters. Returns paginated results."""
    q = select(FindingModel)
    if case_id is not None:
        q = q.where(FindingModel.case_id == case_id)
    if severity is not None:
        q = q.where(FindingModel.severity == severity)
    if status is not None:
        q = q.where(FindingModel.status == status)
    if category is not None:
        q = q.where(FindingModel.category == category)
    if source_strategy is not None:
        q = q.where(FindingModel.source_strategy == source_strategy)
    if has_due_date is True:
        q = q.where(FindingModel.due_date != None)  # noqa: E711
    elif has_due_date is False:
        q = q.where(FindingModel.due_date == None)  # noqa: E711

    count_q = select(func.count()).select_from(q.subquery())
    total_result = await db.execute(count_q)
    total = total_result.scalar_one()

    q = q.offset(offset).limit(limit)
    result = await db.execute(q)
    findings = result.scalars().all()

    return FindingListResponse(
        items=[FindingResponse(**orm_to_finding_response(f)) for f in findings],
        total=total,
    )


@router.patch("/bulk-update")
async def bulk_update_findings(
    body: FindingBulkUpdate,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("editor", "admin"),
):
    """Set the same status on multiple findings at once."""
    if not body.finding_ids:
        return {"updated": 0}

    result = await db.execute(
        select(FindingModel).where(FindingModel.id.in_(body.finding_ids))
    )
    findings = result.scalars().all()

    updated = 0
    for finding in findings:
        if finding.status != body.status:
            old_status = finding.status
            finding.status = body.status
            activity = ActivityLogModel(
                case_id=finding.case_id,
                event_type="finding_status_updated",
                payload={
                    "finding_id": str(finding.id),
                    "old_status": old_status,
                    "new_status": body.status,
                    "bulk": True,
                },
            )
            db.add(activity)
        updated += 1

    await db.flush()
    return {"updated": updated}


def _build_findings_docx(case_title: str, findings: list, docs_by_id: dict) -> bytes:
    """Build DOCX with structured findings report: title page, summary table, per-finding sections."""
    severity_labels = {
        "critical": "Kritisch", "high": "Hoch", "medium": "Mittel", "low": "Niedrig", "info": "Info",
    }
    status_labels = {
        "open": "Offen", "accepted": "Akzeptiert", "overruled": "Überfahren", "fixed": "Behoben",
    }

    doc = DocxDocument()
    doc.add_heading("Befunde-Bericht", 0)
    doc.add_paragraph(f"Vorgang: {case_title}")
    doc.add_paragraph(f"Erstellt: {datetime.now(timezone.utc).strftime('%d.%m.%Y')}")
    doc.add_paragraph()

    # Summary table
    severity_counts = {s: sum(1 for f in findings if f.severity == s) for s in severity_labels}
    status_counts = {s: sum(1 for f in findings if f.status == s) for s in status_labels}
    doc.add_heading("Zusammenfassung", level=1)
    summary_table = doc.add_table(rows=1 + len(severity_labels), cols=2)
    summary_table.style = "Table Grid"
    summary_table.rows[0].cells[0].text = "Schweregrad"
    summary_table.rows[0].cells[1].text = "Anzahl"
    for i, (sev, label) in enumerate(severity_labels.items()):
        row = summary_table.rows[i + 1]
        row.cells[0].text = label
        row.cells[1].text = str(severity_counts.get(sev, 0))
    doc.add_paragraph()

    # Per-finding sections
    doc.add_heading("Einzelbefunde", level=1)
    for f in findings:
        doc.add_heading(f.check_name, level=2)
        info_table = doc.add_table(rows=5, cols=2)
        info_table.style = "Table Grid"
        labels_rows = [
            ("Schweregrad", severity_labels.get(f.severity, f.severity)),
            ("Status", status_labels.get(f.status, f.status)),
            ("Kategorie", f.category),
            ("Dokument", docs_by_id.get(f.document_id, "Vorgangsbezogen") if f.document_id else "Vorgangsbezogen"),
            ("Strategie", f.source_strategy or ""),
        ]
        for i, (label, value) in enumerate(labels_rows):
            info_table.rows[i].cells[0].text = label
            info_table.rows[i].cells[1].text = value
        doc.add_paragraph()
        doc.add_paragraph("Beschreibung:").bold = True
        doc.add_paragraph(f.description)
        if f.evidence:
            doc.add_paragraph("Nachweise:").bold = True
            for ev in f.evidence:
                doc.add_paragraph(f"• {ev}")
        if f.recommendation:
            doc.add_paragraph("Empfehlung:").bold = True
            doc.add_paragraph(f.recommendation)
        doc.add_paragraph()

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


@router.get("/export", response_class=Response)
async def export_findings(
    case_id: Annotated[UUID | None, Query()] = None,
    severity: Annotated[str | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
    category: Annotated[str | None, Query()] = None,
    format: Annotated[str, Query()] = "csv",
    db: AsyncSession = Depends(get_db),
    _user=require_roles("viewer", "editor", "admin"),
):
    """Export findings as CSV (default) or DOCX. If case_id is omitted, exports all findings (org-wide)."""
    q = select(FindingModel)
    if case_id is not None:
        q = q.where(FindingModel.case_id == case_id)
    if severity is not None:
        q = q.where(FindingModel.severity == severity)
    if status is not None:
        q = q.where(FindingModel.status == status)
    if category is not None:
        q = q.where(FindingModel.category == category)

    # Count total before applying limit so we can signal truncation
    count_result = await db.execute(select(func.count()).select_from(q.subquery()))
    total_count = count_result.scalar_one()

    findings_result = await db.execute(q.limit(EXPORT_MAX))
    findings = findings_result.scalars().all()
    is_truncated = total_count > EXPORT_MAX

    case_title = "Alle Vorgänge"
    if case_id is not None:
        case_result = await db.execute(select(CaseModel).where(CaseModel.id == case_id))
        case = case_result.scalar_one_or_none()
        if case is None:
            raise HTTPException(status_code=404, detail="Case not found")
        case_title = case.title

    doc_ids = {f.document_id for f in findings if f.document_id is not None}
    docs_by_id: dict[UUID, str] = {}
    if doc_ids:
        docs_result = await db.execute(
            select(DocumentModel).where(DocumentModel.id.in_(doc_ids))
        )
        docs_by_id = {d.id: d.name for d in docs_result.scalars().all()}

    # Build case title map for CSV (when exporting org-wide)
    case_ids = {f.case_id for f in findings}
    cases_by_id: dict[UUID, str] = {}
    if case_ids:
        cases_result = await db.execute(select(CaseModel).where(CaseModel.id.in_(case_ids)))
        cases_by_id = {c.id: c.title for c in cases_result.scalars().all()}

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    slug = case_title.replace("/", "-").replace("\\", "-")[:50]

    export_headers = {
        "X-Total-Count": str(total_count),
        "X-Truncated": str(is_truncated).lower(),
    }

    if format.lower() == "docx":
        content_bytes = _build_findings_docx(case_title, findings, docs_by_id)
        filename = f"Befunde-{slug}-{date_str}.docx"
        return Response(
            content=content_bytes,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{filename}"', **export_headers},
        )

    severity_labels = {
        "critical": "Kritisch",
        "high": "Hoch",
        "medium": "Mittel",
        "low": "Niedrig",
        "info": "Info",
    }
    status_labels = {
        "open": "Offen",
        "accepted": "Akzeptiert",
        "overruled": "Überfahren",
        "fixed": "Behoben",
    }

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "ID",
        "Vorgang",
        "Checkname",
        "Kategorie",
        "Schweregrad",
        "Status",
        "Beschreibung",
        "Empfehlung",
        "Dokument",
        "Strategie",
    ])
    for f in findings:
        writer.writerow([
            str(f.id),
            cases_by_id.get(f.case_id, str(f.case_id)),
            f.check_name,
            f.category,
            severity_labels.get(f.severity, f.severity),
            status_labels.get(f.status, f.status),
            f.description,
            f.recommendation,
            docs_by_id.get(f.document_id, "") if f.document_id else "",
            f.source_strategy or "",
        ])

    filename = f"Befunde-{slug}-{date_str}.csv"

    # UTF-8 BOM for Excel compatibility (consistent with VVT export)
    body = "\ufeff" + buf.getvalue()
    return Response(
        content=body.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"', **export_headers},
    )


@router.patch("/{finding_id}", response_model=FindingResponse)
async def update_finding(
    finding_id: UUID,
    body: FindingUpdate,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("editor", "admin"),
):
    """Update a finding (status and/or due_date)."""
    result = await db.execute(select(FindingModel).where(FindingModel.id == finding_id))
    finding = result.scalar_one_or_none()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")
    old_status = finding.status
    finding.status = body.status
    if body.due_date is not None or "due_date" in body.model_fields_set:
        finding.due_date = body.due_date
    await db.flush()
    if old_status != body.status:
        actor = _user.display_name if isinstance(_user, UserModel) else "System"
        activity = ActivityLogModel(
            case_id=finding.case_id,
            event_type="finding_status_updated",
            payload={
                "finding_id": str(finding_id),
                "check_name": finding.check_name,
                "old_status": old_status,
                "new_status": body.status,
                "actor": actor,
            },
        )
        db.add(activity)
    await db.refresh(finding)
    return FindingResponse(**orm_to_finding_response(finding))


# --- Finding Comments ---

@router.get("/{finding_id}/comments", response_model=list[FindingCommentResponse])
async def list_finding_comments(
    finding_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("viewer", "editor", "admin"),
):
    """List comments for a finding, sorted oldest-first."""
    result = await db.execute(select(FindingModel).where(FindingModel.id == finding_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Finding not found")
    comments_result = await db.execute(
        select(FindingCommentModel)
        .where(FindingCommentModel.finding_id == finding_id)
        .order_by(FindingCommentModel.created_at.asc())
    )
    return [FindingCommentResponse(**orm_to_finding_comment_response(c)) for c in comments_result.scalars().all()]


@router.post("/{finding_id}/comments", response_model=FindingCommentResponse, status_code=201)
async def create_finding_comment(
    finding_id: UUID,
    body: FindingCommentCreate,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("editor", "admin"),
):
    """Add a comment to a finding (audit trail for status decisions)."""
    result = await db.execute(select(FindingModel).where(FindingModel.id == finding_id))
    finding = result.scalar_one_or_none()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    display_name = "System"
    user_id = None
    if isinstance(_user, UserModel):
        display_name = _user.display_name or "System"
        user_id = _user.id

    comment = FindingCommentModel(
        finding_id=finding_id,
        case_id=finding.case_id,
        author=display_name,
        user_id=user_id,
        text=body.text,
    )
    db.add(comment)
    activity = ActivityLogModel(
        case_id=finding.case_id,
        event_type="comment_added",
        payload={"finding_id": str(finding_id), "author": display_name},
    )
    db.add(activity)
    await db.flush()
    await db.refresh(comment)
    return FindingCommentResponse(**orm_to_finding_comment_response(comment))
