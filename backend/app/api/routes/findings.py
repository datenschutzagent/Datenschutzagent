"""Findings API: list, update, bulk-update, CSV export."""
import csv
import io
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import require_roles
from app.database import get_db
from app.models.db import ActivityLogModel, CaseModel, DocumentModel, FindingModel, orm_to_finding_response
from app.models.schemas import (
    FindingBulkUpdate,
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


@router.get("/export", response_class=Response)
async def export_findings(
    case_id: Annotated[UUID, Query()],
    severity: Annotated[str | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
    category: Annotated[str | None, Query()] = None,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("viewer", "editor", "admin"),
):
    """Export findings for a case as CSV."""
    q = (
        select(FindingModel)
        .where(FindingModel.case_id == case_id)
        .limit(EXPORT_MAX)
    )
    if severity is not None:
        q = q.where(FindingModel.severity == severity)
    if status is not None:
        q = q.where(FindingModel.status == status)
    if category is not None:
        q = q.where(FindingModel.category == category)

    findings_result = await db.execute(q)
    findings = findings_result.scalars().all()

    case_result = await db.execute(select(CaseModel).where(CaseModel.id == case_id))
    case = case_result.scalar_one_or_none()
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")

    doc_ids = {f.document_id for f in findings if f.document_id is not None}
    docs_by_id: dict[UUID, str] = {}
    if doc_ids:
        docs_result = await db.execute(
            select(DocumentModel).where(DocumentModel.id.in_(doc_ids))
        )
        docs_by_id = {d.id: d.name for d in docs_result.scalars().all()}

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
            case.title,
            f.check_name,
            f.category,
            severity_labels.get(f.severity, f.severity),
            status_labels.get(f.status, f.status),
            f.description,
            f.recommendation,
            docs_by_id.get(f.document_id, "") if f.document_id else "",
            f.source_strategy or "",
        ])

    from datetime import datetime
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    slug = case.title.replace("/", "-").replace("\\", "-")[:50]
    filename = f"Befunde-{slug}-{date_str}.csv"

    return Response(
        content=buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.patch("/{finding_id}", response_model=FindingResponse)
async def update_finding(
    finding_id: UUID,
    body: FindingUpdate,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("editor", "admin"),
):
    """Update a finding (e.g. status: open, accepted, overruled, fixed)."""
    result = await db.execute(select(FindingModel).where(FindingModel.id == finding_id))
    finding = result.scalar_one_or_none()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")
    old_status = finding.status
    finding.status = body.status
    await db.flush()
    if old_status != body.status:
        activity = ActivityLogModel(
            case_id=finding.case_id,
            event_type="finding_status_updated",
            payload={
                "finding_id": str(finding_id),
                "old_status": old_status,
                "new_status": body.status,
            },
        )
        db.add(activity)
    await db.refresh(finding)
    return FindingResponse(**orm_to_finding_response(finding))
