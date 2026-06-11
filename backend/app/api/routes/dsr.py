"""DSR API: Betroffenenrechts-Anfragen (Art. 15–22 DSGVO) verwalten."""

import logging
from datetime import date, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_roles
from app.core.rate_limit import limiter
from app.database import get_db
from app.models.db import (
    DSRActivityLogModel,
    DSRRequestModel,
    UserModel,
)
from app.models.schemas import (
    DSRActivityResponse,
    DSRListResponse,
    DSRMonthlyVolumeItem,
    DSRRequestCreate,
    DSRRequestResponse,
    DSRRequestUpdate,
    DSRStatsResponse,
)

router = APIRouter()
logger = logging.getLogger(__name__)

_DEFAULT_DEADLINE_DAYS = 30  # Art. 12 Abs. 3 DSGVO


@router.get(
    "/stats", response_model=DSRStatsResponse, summary="DSR-Statistiken abrufen"
)
async def get_dsr_stats(
    db: AsyncSession = Depends(get_db),
    _user=require_roles("viewer", "editor", "admin"),
):
    """Aggregierte DSR-Statistiken: Antwortzeiten, On-Time-Rate, Typ- und Status-Verteilung."""
    from sqlalchemy import text

    result = await db.execute(
        text(
            """
        WITH by_type AS (
            SELECT request_type AS key1, COUNT(*) AS cnt FROM dsr_requests GROUP BY request_type
        ),
        by_status AS (
            SELECT status AS key1, COUNT(*) AS cnt FROM dsr_requests GROUP BY status
        ),
        response_times AS (
            SELECT
                AVG(EXTRACT(EPOCH FROM (responded_at - received_at)) / 86400.0) AS avg_days,
                COUNT(*) FILTER (WHERE responded_at <= response_deadline) AS on_time,
                COUNT(*) AS total_responded
            FROM dsr_requests
            WHERE responded_at IS NOT NULL
        ),
        overdue AS (
            SELECT COUNT(*) AS cnt
            FROM dsr_requests
            WHERE status NOT IN ('closed', 'response_sent', 'denied')
            AND response_deadline < CURRENT_DATE
        ),
        monthly AS (
            SELECT TO_CHAR(DATE_TRUNC('month', created_at), 'YYYY-MM') AS month,
                   COUNT(*) AS cnt
            FROM dsr_requests
            WHERE created_at >= NOW() - INTERVAL '6 months'
            GROUP BY DATE_TRUNC('month', created_at)
            ORDER BY 1 ASC
        ),
        total AS (
            SELECT COUNT(*) AS cnt FROM dsr_requests
        )
        SELECT 'type'     AS qname, key1, cnt, NULL::float, NULL::bigint, NULL::bigint FROM by_type
        UNION ALL
        SELECT 'status'   AS qname, key1, cnt, NULL, NULL, NULL FROM by_status
        UNION ALL
        SELECT 'response' AS qname, NULL, total_responded, avg_days, on_time, NULL FROM response_times
        UNION ALL
        SELECT 'overdue'  AS qname, NULL, cnt, NULL, NULL, NULL FROM overdue
        UNION ALL
        SELECT 'monthly'  AS qname, month, cnt, NULL, NULL, NULL FROM monthly
        UNION ALL
        SELECT 'total'    AS qname, NULL, cnt, NULL, NULL, NULL FROM total
    """
        )
    )
    rows = result.fetchall()

    by_type: dict[str, int] = {}
    by_status: dict[str, int] = {}
    monthly_volume: list[DSRMonthlyVolumeItem] = []
    avg_days: float | None = None
    on_time_rate: float | None = None
    overdue_count: int = 0
    total: int = 0

    for row in rows:
        qname, key1, cnt, f1, f2, _ = row
        if qname == "type":
            by_type[key1] = int(cnt or 0)
        elif qname == "status":
            by_status[key1] = int(cnt or 0)
        elif qname == "response":
            total_responded = int(cnt or 0)
            if total_responded > 0:
                avg_days = float(f1) if f1 is not None else None
                on_time_rate = (
                    round(float(f2) / total_responded, 4) if f2 is not None else None
                )
        elif qname == "overdue":
            overdue_count = int(cnt or 0)
        elif qname == "monthly":
            monthly_volume.append(DSRMonthlyVolumeItem(month=key1, count=int(cnt or 0)))
        elif qname == "total":
            total = int(cnt or 0)

    return DSRStatsResponse(
        total=total,
        by_type=by_type,
        by_status=by_status,
        avg_response_days=avg_days,
        on_time_rate=on_time_rate,
        overdue_count=overdue_count,
        monthly_volume=monthly_volume,
    )


@router.get("", response_model=DSRListResponse, summary="DSR-Anfragen auflisten")
async def list_dsr_requests(
    status: str | None = Query(default=None),
    request_type: str | None = Query(default=None),
    assignee: str | None = Query(default=None),
    overdue_only: bool = Query(default=False, description="Nur überfällige Anfragen"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _user=require_roles("viewer", "editor", "admin"),
):
    """Listet DSR-Anfragen mit optionalen Filtern."""
    q = select(DSRRequestModel)
    if status:
        q = q.where(DSRRequestModel.status == status)
    if request_type:
        q = q.where(DSRRequestModel.request_type == request_type)
    if assignee:
        q = q.where(DSRRequestModel.assignee.ilike(f"%{assignee}%"))
    if overdue_only:
        today = date.today()
        q = q.where(
            DSRRequestModel.response_deadline < today,
            DSRRequestModel.status.notin_(["closed", "response_sent", "denied"]),
        )

    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar_one()

    q = q.order_by(DSRRequestModel.response_deadline.asc()).offset(skip).limit(limit)
    result = await db.execute(q)
    items = [DSRRequestResponse.model_validate(r) for r in result.scalars().all()]

    return DSRListResponse(items=items, total=total)


@router.post(
    "",
    response_model=DSRRequestResponse,
    status_code=201,
    summary="DSR-Anfrage erstellen",
)
@limiter.limit("30/minute")
async def create_dsr_request(
    request: Request,
    body: DSRRequestCreate,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("editor", "admin"),
):
    """Erstellt eine neue Betroffenenrechts-Anfrage."""
    deadline_days = _DEFAULT_DEADLINE_DAYS + body.deadline_extension_days
    response_deadline = body.received_at + timedelta(days=deadline_days)

    request = DSRRequestModel(
        request_type=body.request_type,
        requestor_name=body.requestor_name,
        requestor_email=body.requestor_email,
        description=body.description,
        department=body.department,
        assignee=body.assignee,
        received_at=body.received_at,
        response_deadline=response_deadline,
    )
    db.add(request)
    await db.flush()

    activity = DSRActivityLogModel(
        request_id=request.id,
        event_type="created",
        payload={
            "request_type": body.request_type,
            "deadline": response_deadline.isoformat(),
        },
    )
    db.add(activity)
    await db.flush()
    await db.refresh(request)
    logger.info(
        "DSR request created",
        extra={
            "dsr_request_id": str(request.id),
            "request_type": body.request_type,
            "response_deadline": response_deadline.isoformat(),
        },
    )
    return DSRRequestResponse.model_validate(request)


@router.get(
    "/{request_id}", response_model=DSRRequestResponse, summary="DSR-Anfrage abrufen"
)
async def get_dsr_request(
    request_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("viewer", "editor", "admin"),
):
    result = await db.execute(
        select(DSRRequestModel).where(DSRRequestModel.id == request_id)
    )
    request = result.scalar_one_or_none()
    if not request:
        raise HTTPException(status_code=404, detail="DSR-Anfrage nicht gefunden")
    return DSRRequestResponse.model_validate(request)


@router.patch(
    "/{request_id}",
    response_model=DSRRequestResponse,
    summary="DSR-Anfrage aktualisieren",
)
@limiter.limit("60/minute")
async def update_dsr_request(
    request: Request,
    request_id: UUID,
    body: DSRRequestUpdate,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("editor", "admin"),
):
    """Aktualisiert Status, Zugewiesenen oder Antwort einer DSR-Anfrage."""
    result = await db.execute(
        select(DSRRequestModel).where(DSRRequestModel.id == request_id)
    )
    request = result.scalar_one_or_none()
    if not request:
        raise HTTPException(status_code=404, detail="DSR-Anfrage nicht gefunden")

    old_status = request.status
    if body.status is not None:
        request.status = body.status
    if body.assignee is not None:
        request.assignee = body.assignee
    if body.response_summary is not None:
        request.response_summary = body.response_summary
    if body.responded_at is not None:
        request.responded_at = body.responded_at
    if body.department is not None:
        request.department = body.department

    actor = _user.display_name if isinstance(_user, UserModel) else "System"
    payload: dict = {"actor": actor}
    if body.status and old_status != body.status:
        payload["old_status"] = old_status
        payload["new_status"] = body.status

    activity = DSRActivityLogModel(
        request_id=request_id,
        event_type="updated",
        payload=payload,
    )
    db.add(activity)
    await db.flush()
    await db.refresh(request)
    if body.status and old_status != body.status:
        logger.info(
            "DSR request status changed",
            extra={
                "dsr_request_id": str(request_id),
                "old_status": old_status,
                "new_status": body.status,
            },
        )
    return DSRRequestResponse.model_validate(request)


@router.delete("/{request_id}", status_code=204, summary="DSR-Anfrage löschen")
async def delete_dsr_request(
    request_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("admin"),
):
    result = await db.execute(
        select(DSRRequestModel).where(DSRRequestModel.id == request_id)
    )
    request = result.scalar_one_or_none()
    if not request:
        raise HTTPException(status_code=404, detail="DSR-Anfrage nicht gefunden")
    await db.delete(request)
    await db.flush()
    logger.info("DSR request deleted", extra={"dsr_request_id": str(request_id)})


@router.post(
    "/{request_id}/generate-draft",
    response_model=DSRRequestResponse,
    summary="Antwortschreiben-Entwurf generieren",
)
@limiter.limit("5/minute")
async def generate_response_draft(
    request: Request,
    request_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("editor", "admin"),
):
    """Generiert per LLM einen Entwurf für das Antwortschreiben."""
    result = await db.execute(
        select(DSRRequestModel).where(DSRRequestModel.id == request_id)
    )
    request = result.scalar_one_or_none()
    if not request:
        raise HTTPException(status_code=404, detail="DSR-Anfrage nicht gefunden")

    from app.services.dsr_response_service import generate_draft_response

    await generate_draft_response(request_id, db)
    await db.refresh(request)
    return DSRRequestResponse.model_validate(request)


@router.get(
    "/{request_id}/activity",
    response_model=list[DSRActivityResponse],
    summary="Aktivitätsprotokoll abrufen",
)
async def get_dsr_activity(
    request_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("viewer", "editor", "admin"),
):
    """Gibt das Aktivitätsprotokoll einer DSR-Anfrage zurück."""
    result = await db.execute(
        select(DSRRequestModel).where(DSRRequestModel.id == request_id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="DSR-Anfrage nicht gefunden")

    log_result = await db.execute(
        select(DSRActivityLogModel)
        .where(DSRActivityLogModel.request_id == request_id)
        .order_by(DSRActivityLogModel.created_at.asc())
    )
    return [DSRActivityResponse.model_validate(e) for e in log_result.scalars().all()]
