"""VVT overview at university level: list, stats, export (no LLM)."""

import csv
import io
import logging
from collections import defaultdict
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.db import CaseModel, DSBReportModel
from app.models.schemas import (
    VVTOverviewItem,
    VVTOverviewStatsGroup,
    VVTOverviewStatsResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()

EXPORT_MAX = 5000


def _vvt_docs(case: CaseModel) -> list:
    return [d for d in case.documents if d.type == "vvt"]


def _vvt_completeness_from_payload(payload: dict) -> int | None:
    summary = payload.get("summary") or {}
    if not summary.get("vvt_available"):
        return None
    c = summary.get("vvt_completeness")
    return int(c) if c is not None else None


async def _build_overview_items(
    cases: list[CaseModel],
    reports_by_case: dict[UUID, DSBReportModel],
) -> list[VVTOverviewItem]:
    items = []
    for case in cases:
        vvt_docs = _vvt_docs(case)
        has_vvt = len(vvt_docs) > 0
        vvt_name = vvt_docs[0].name if vvt_docs else None
        report = reports_by_case.get(case.id)
        vvt_completeness = None
        if report and report.payload:
            vvt_completeness = _vvt_completeness_from_payload(report.payload)
        items.append(
            VVTOverviewItem(
                case_id=case.id,
                title=case.title,
                department=case.department,
                case_type=case.case_type,
                status=case.status,
                updated_at=case.updated_at,
                has_vvt_document=has_vvt,
                vvt_completeness=vvt_completeness,
                vvt_document_name=vvt_name,
            )
        )
    return items


@router.get("", response_model=list[VVTOverviewItem])
async def get_vvt_overview(
    department: str | None = Query(None, description="Filter by department"),
    case_type: str | None = Query(None, description="Filter by case_type"),
    status: str | None = Query(None, description="Filter by status"),
    has_vvt: bool | None = Query(
        None, description="Filter: only with VVT (true) or without (false)"
    ),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """List cases with VVT metadata (has_vvt_document, vvt_completeness from DSB report). No LLM."""
    q = (
        select(CaseModel)
        .options(selectinload(CaseModel.documents))
        .order_by(CaseModel.updated_at.desc())
    )
    if department is not None:
        q = q.where(CaseModel.department == department)
    if case_type is not None:
        q = q.where(CaseModel.case_type == case_type)
    if status is not None:
        q = q.where(CaseModel.status == status)
    q = q.limit(EXPORT_MAX)
    result = await db.execute(q)
    cases = result.scalars().all()

    case_ids = [c.id for c in cases]
    if not case_ids:
        return []

    reports_result = await db.execute(
        select(DSBReportModel).where(DSBReportModel.case_id.in_(case_ids))
    )
    reports = reports_result.scalars().all()
    reports_by_case = {r.case_id: r for r in reports}

    items = await _build_overview_items(cases, reports_by_case)

    if has_vvt is True:
        items = [i for i in items if i.has_vvt_document]
    elif has_vvt is False:
        items = [i for i in items if not i.has_vvt_document]

    return items[skip : skip + limit]


@router.get("/stats", response_model=VVTOverviewStatsResponse)
async def get_vvt_overview_stats(db: AsyncSession = Depends(get_db)):
    """Aggregate stats: totals and by department / case_type."""
    result = await db.execute(
        select(CaseModel)
        .options(selectinload(CaseModel.documents))
        .order_by(CaseModel.updated_at.desc())
    )
    cases = result.scalars().all()
    case_ids = [c.id for c in cases]
    if not case_ids:
        return VVTOverviewStatsResponse()

    reports_result = await db.execute(
        select(DSBReportModel).where(DSBReportModel.case_id.in_(case_ids))
    )
    reports = reports_result.scalars().all()
    reports_by_case = {r.case_id: r for r in reports}

    items = await _build_overview_items(cases, reports_by_case)

    total = len(items)
    with_vvt = sum(1 for i in items if i.has_vvt_document)
    without_vvt = total - with_vvt
    completeness_values = [
        i.vvt_completeness for i in items if i.vvt_completeness is not None
    ]
    avg_completeness = (
        round(sum(completeness_values) / len(completeness_values), 1)
        if completeness_values
        else None
    )

    by_dep: dict[str, list[VVTOverviewItem]] = defaultdict(list)
    by_type: dict[str, list[VVTOverviewItem]] = defaultdict(list)
    for i in items:
        by_dep[i.department].append(i)
        by_type[i.case_type].append(i)

    def to_group(
        name: str, group_items: list[VVTOverviewItem]
    ) -> VVTOverviewStatsGroup:
        n = len(group_items)
        w = sum(1 for x in group_items if x.has_vvt_document)
        wo = n - w
        vals = [
            x.vvt_completeness for x in group_items if x.vvt_completeness is not None
        ]
        avg = round(sum(vals) / len(vals), 1) if vals else None
        return VVTOverviewStatsGroup(
            name=name,
            total_cases=n,
            with_vvt=w,
            without_vvt=wo,
            avg_completeness=avg,
        )

    by_department = [
        to_group(name, group_items) for name, group_items in sorted(by_dep.items())
    ]
    by_case_type = [
        to_group(name, group_items) for name, group_items in sorted(by_type.items())
    ]

    return VVTOverviewStatsResponse(
        total_cases=total,
        with_vvt=with_vvt,
        without_vvt=without_vvt,
        avg_completeness=avg_completeness,
        by_department=by_department,
        by_case_type=by_case_type,
    )


@router.get("/export", response_class=Response)
async def get_vvt_overview_export(
    department: str | None = Query(None),
    case_type: str | None = Query(None),
    status: str | None = Query(None),
    has_vvt: bool | None = Query(None),
    format: str = Query("csv", description="csv"),
    db: AsyncSession = Depends(get_db),
):
    """Export VVT overview as CSV (same filters as list). Max 5000 rows."""
    if format != "csv":
        return Response(content="Only format=csv supported", status_code=400)

    q = (
        select(CaseModel)
        .options(selectinload(CaseModel.documents))
        .order_by(CaseModel.updated_at.desc())
    )
    if department is not None:
        q = q.where(CaseModel.department == department)
    if case_type is not None:
        q = q.where(CaseModel.case_type == case_type)
    if status is not None:
        q = q.where(CaseModel.status == status)
    q = q.limit(EXPORT_MAX)
    result = await db.execute(q)
    cases = result.scalars().all()
    case_ids = [c.id for c in cases]
    if not case_ids:
        reports_by_case = {}
    else:
        reports_result = await db.execute(
            select(DSBReportModel).where(DSBReportModel.case_id.in_(case_ids))
        )
        reports = reports_result.scalars().all()
        reports_by_case = {r.case_id: r for r in reports}

    items = await _build_overview_items(cases, reports_by_case)
    if has_vvt is True:
        items = [i for i in items if i.has_vvt_document]
    elif has_vvt is False:
        items = [i for i in items if not i.has_vvt_document]

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "Case-ID",
            "Titel",
            "Fachbereich",
            "Vorgangstyp",
            "Status",
            "VVT vorhanden",
            "VVT-Vollständigkeit (%)",
            "VVT-Dokumentname",
            "Stand (updated_at)",
        ]
    )
    for i in items:
        writer.writerow(
            [
                str(i.case_id),
                i.title,
                i.department,
                i.case_type,
                i.status,
                "Ja" if i.has_vvt_document else "Nein",
                str(i.vvt_completeness) if i.vvt_completeness is not None else "",
                i.vvt_document_name or "",
                (
                    i.updated_at.isoformat()
                    if isinstance(i.updated_at, datetime)
                    else str(i.updated_at)
                ),
            ]
        )

    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    filename = f"VVT-Uebersicht-{date_str}.csv"
    logger.info(
        "VVT overview exported",
        extra={"row_count": len(items), "export_filename": filename},
    )
    return Response(
        content=buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
