"""Datenpannen-Management API (Art. 33/34 DSGVO) – 72-Stunden-Meldepflicht."""

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_roles
from app.core.rate_limit import limiter
from app.database import get_db
from app.models.db import (
    DataBreachActivityLogModel,
    DataBreachModel,
    UserModel,
)
from app.models.schemas import (
    DataBreachActivityResponse,
    DataBreachCreate,
    DataBreachListResponse,
    DataBreachMonthlyItem,
    DataBreachResponse,
    DataBreachStatsResponse,
    DataBreachUpdate,
)

router = APIRouter()
logger = logging.getLogger(__name__)

_NOTIFICATION_DEADLINE_HOURS = 72  # Art. 33 Abs. 1 DSGVO


@router.get(
    "/stats",
    response_model=DataBreachStatsResponse,
    summary="Datenpannen-Statistiken abrufen",
)
async def get_data_breach_stats(
    db: AsyncSession = Depends(get_db),
    _user=require_roles("viewer", "editor", "admin"),
):
    """Aggregierte Datenpannen-Statistiken: 72h-Compliance, Risikoverteilung, Monatstrend."""
    from sqlalchemy import text

    result = await db.execute(
        text(
            """
        WITH by_status AS (
            SELECT status AS key1, COUNT(*) AS cnt FROM data_breaches GROUP BY status
        ),
        by_risk AS (
            SELECT risk_level AS key1, COUNT(*) AS cnt FROM data_breaches WHERE risk_level IS NOT NULL GROUP BY risk_level
        ),
        by_type AS (
            SELECT breach_type AS key1, COUNT(*) AS cnt FROM data_breaches GROUP BY breach_type
        ),
        notification AS (
            SELECT
                COUNT(*) FILTER (WHERE authority_notified_at IS NOT NULL) AS notified,
                COUNT(*) FILTER (
                    WHERE authority_notified_at IS NOT NULL
                    AND authority_notified_at <= notification_deadline
                ) AS on_time
            FROM data_breaches
            WHERE status IN ('reported_to_authority', 'reported_to_subjects', 'closed')
        ),
        persons AS (
            SELECT AVG(affected_persons_count) AS avg_persons
            FROM data_breaches
            WHERE affected_persons_count IS NOT NULL
        ),
        monthly AS (
            SELECT TO_CHAR(DATE_TRUNC('month', discovered_at), 'YYYY-MM') AS month,
                   COUNT(*) AS cnt,
                   COALESCE(SUM(affected_persons_count), 0) AS total_persons
            FROM data_breaches
            WHERE discovered_at >= NOW() - INTERVAL '6 months'
            GROUP BY DATE_TRUNC('month', discovered_at)
            ORDER BY 1 ASC
        ),
        total AS (
            SELECT COUNT(*) AS cnt FROM data_breaches
        )
        SELECT 'status'  AS qname, key1, cnt, NULL::float, NULL::bigint FROM by_status
        UNION ALL
        SELECT 'risk',    key1, cnt, NULL, NULL FROM by_risk
        UNION ALL
        SELECT 'type',    key1, cnt, NULL, NULL FROM by_type
        UNION ALL
        SELECT 'notify',  NULL, notified, NULL, on_time FROM notification
        UNION ALL
        SELECT 'persons', NULL, NULL, avg_persons, NULL FROM persons
        UNION ALL
        SELECT 'monthly', month, cnt, NULL, total_persons FROM monthly
        UNION ALL
        SELECT 'total',   NULL, cnt, NULL, NULL FROM total
    """
        )
    )
    rows = result.fetchall()

    by_status: dict[str, int] = {}
    by_risk_level: dict[str, int] = {}
    by_breach_type: dict[str, int] = {}
    monthly_trend: list[DataBreachMonthlyItem] = []
    notification_compliance_rate: float | None = None
    avg_affected_persons: float | None = None
    total: int = 0

    for row in rows:
        qname, key1, cnt, f1, f2 = row
        if qname == "status":
            by_status[key1] = int(cnt or 0)
        elif qname == "risk":
            by_risk_level[key1] = int(cnt or 0)
        elif qname == "type":
            by_breach_type[key1] = int(cnt or 0)
        elif qname == "notify":
            notified = int(cnt or 0)
            on_time = int(f2 or 0)
            if notified > 0:
                notification_compliance_rate = round(on_time / notified, 4)
        elif qname == "persons":
            avg_affected_persons = float(f1) if f1 is not None else None
        elif qname == "monthly":
            monthly_trend.append(
                DataBreachMonthlyItem(
                    month=key1, count=int(cnt or 0), total_persons=int(f2 or 0)
                )
            )
        elif qname == "total":
            total = int(cnt or 0)

    return DataBreachStatsResponse(
        total=total,
        by_status=by_status,
        by_risk_level=by_risk_level,
        by_breach_type=by_breach_type,
        notification_compliance_rate=notification_compliance_rate,
        avg_affected_persons=avg_affected_persons,
        monthly_trend=monthly_trend,
    )


@router.get("", response_model=DataBreachListResponse, summary="Datenpannen auflisten")
async def list_data_breaches(
    status: str | None = Query(default=None),
    risk_level: str | None = Query(default=None),
    department: str | None = Query(default=None),
    overdue_only: bool = Query(
        default=False, description="Nur Pannen mit überschrittener 72h-Frist"
    ),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _user=require_roles("viewer", "editor", "admin"),
):
    """Listet Datenpannen mit optionalen Filtern."""
    q = select(DataBreachModel)
    if status:
        q = q.where(DataBreachModel.status == status)
    if risk_level:
        q = q.where(DataBreachModel.risk_level == risk_level)
    if department:
        q = q.where(DataBreachModel.department.ilike(f"%{department}%"))
    if overdue_only:
        now = datetime.now(UTC)
        q = q.where(
            DataBreachModel.notification_deadline < now,
            DataBreachModel.status.notin_(
                ["reported_to_authority", "closed", "no_notification_required"]
            ),
        )

    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar_one()

    q = (
        q.order_by(DataBreachModel.notification_deadline.asc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(q)
    items = [DataBreachResponse.model_validate(r) for r in result.scalars().all()]

    return DataBreachListResponse(items=items, total=total)


@router.post(
    "", response_model=DataBreachResponse, status_code=201, summary="Datenpanne melden"
)
@limiter.limit("30/minute")
async def create_data_breach(
    request: Request,
    body: DataBreachCreate,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("editor", "admin"),
):
    """Erfasst eine neue Datenschutzverletzung und setzt die 72h-Frist."""
    notification_deadline = body.discovered_at + timedelta(
        hours=_NOTIFICATION_DEADLINE_HOURS
    )

    breach = DataBreachModel(
        title=body.title,
        description=body.description,
        discovered_at=body.discovered_at,
        notification_deadline=notification_deadline,
        breach_type=body.breach_type,
        affected_data_categories=body.affected_data_categories,
        affected_persons_count=body.affected_persons_count,
        department=body.department,
        assignee=body.assignee,
        risk_level=body.risk_level,
        measures_taken=body.measures_taken,
    )
    db.add(breach)
    await db.flush()

    activity = DataBreachActivityLogModel(
        breach_id=breach.id,
        event_type="created",
        payload={
            "breach_type": body.breach_type,
            "notification_deadline": notification_deadline.isoformat(),
        },
    )
    db.add(activity)
    await db.flush()
    await db.refresh(breach)
    return DataBreachResponse.model_validate(breach)


@router.get(
    "/{breach_id}", response_model=DataBreachResponse, summary="Datenpanne abrufen"
)
async def get_data_breach(
    breach_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("viewer", "editor", "admin"),
):
    result = await db.execute(
        select(DataBreachModel).where(DataBreachModel.id == breach_id)
    )
    breach = result.scalar_one_or_none()
    if not breach:
        raise HTTPException(status_code=404, detail="Datenpanne nicht gefunden")
    return DataBreachResponse.model_validate(breach)


@router.patch(
    "/{breach_id}",
    response_model=DataBreachResponse,
    summary="Datenpanne aktualisieren",
)
@limiter.limit("60/minute")
async def update_data_breach(
    request: Request,
    breach_id: UUID,
    body: DataBreachUpdate,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("editor", "admin"),
):
    """Aktualisiert Status, Risikobewertung oder Meldestatus einer Datenpanne."""
    result = await db.execute(
        select(DataBreachModel).where(DataBreachModel.id == breach_id)
    )
    breach = result.scalar_one_or_none()
    if not breach:
        raise HTTPException(status_code=404, detail="Datenpanne nicht gefunden")

    old_status = breach.status
    fields = [
        "title",
        "description",
        "status",
        "breach_type",
        "affected_data_categories",
        "affected_persons_count",
        "department",
        "assignee",
        "risk_level",
        "authority_notified_at",
        "subjects_notified_at",
        "authority_reference",
        "measures_taken",
    ]
    for field in fields:
        val = getattr(body, field, None)
        if val is not None:
            setattr(breach, field, val)

    actor = _user.display_name if isinstance(_user, UserModel) else "System"
    payload: dict = {"actor": actor}
    if body.status and old_status != body.status:
        payload["old_status"] = old_status
        payload["new_status"] = body.status

    activity = DataBreachActivityLogModel(
        breach_id=breach_id,
        event_type="updated",
        payload=payload,
    )
    db.add(activity)
    await db.flush()
    await db.refresh(breach)
    return DataBreachResponse.model_validate(breach)


@router.delete("/{breach_id}", status_code=204, summary="Datenpanne löschen")
async def delete_data_breach(
    breach_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("admin"),
):
    result = await db.execute(
        select(DataBreachModel).where(DataBreachModel.id == breach_id)
    )
    breach = result.scalar_one_or_none()
    if not breach:
        raise HTTPException(status_code=404, detail="Datenpanne nicht gefunden")
    await db.delete(breach)
    await db.flush()


@router.post(
    "/{breach_id}/generate-notification",
    response_model=DataBreachResponse,
    summary="Behörden-Meldung generieren",
)
@limiter.limit("5/minute")
async def generate_notification_draft(
    request: Request,
    breach_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("editor", "admin"),
):
    """Generiert per LLM einen Meldungsentwurf für die Aufsichtsbehörde."""
    result = await db.execute(
        select(DataBreachModel).where(DataBreachModel.id == breach_id)
    )
    breach = result.scalar_one_or_none()
    if not breach:
        raise HTTPException(status_code=404, detail="Datenpanne nicht gefunden")

    from app.services.data_breach_service import generate_breach_notification

    await generate_breach_notification(breach_id, db)
    await db.refresh(breach)
    return DataBreachResponse.model_validate(breach)


@router.get(
    "/{breach_id}/activity",
    response_model=list[DataBreachActivityResponse],
    summary="Aktivitätsprotokoll abrufen",
)
async def get_breach_activity(
    breach_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("viewer", "editor", "admin"),
):
    result = await db.execute(
        select(DataBreachModel).where(DataBreachModel.id == breach_id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Datenpanne nicht gefunden")

    log_result = await db.execute(
        select(DataBreachActivityLogModel)
        .where(DataBreachActivityLogModel.breach_id == breach_id)
        .order_by(DataBreachActivityLogModel.created_at.asc())
    )
    return [
        DataBreachActivityResponse.model_validate(e) for e in log_result.scalars().all()
    ]
