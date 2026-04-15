"""Datenpannen-Management API (Art. 33/34 DSGVO) – 72-Stunden-Meldepflicht."""
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_roles
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
    DataBreachResponse,
    DataBreachUpdate,
)

router = APIRouter()
logger = logging.getLogger(__name__)

_NOTIFICATION_DEADLINE_HOURS = 72  # Art. 33 Abs. 1 DSGVO


@router.get("", response_model=DataBreachListResponse, summary="Datenpannen auflisten")
async def list_data_breaches(
    status: str | None = Query(default=None),
    risk_level: str | None = Query(default=None),
    department: str | None = Query(default=None),
    overdue_only: bool = Query(default=False, description="Nur Pannen mit überschrittener 72h-Frist"),
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
        now = datetime.now(timezone.utc)
        q = q.where(
            DataBreachModel.notification_deadline < now,
            DataBreachModel.status.notin_(["reported_to_authority", "closed", "no_notification_required"]),
        )

    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar_one()

    q = q.order_by(DataBreachModel.notification_deadline.asc()).offset(skip).limit(limit)
    result = await db.execute(q)
    items = [DataBreachResponse.model_validate(r) for r in result.scalars().all()]

    return DataBreachListResponse(items=items, total=total)


@router.post("", response_model=DataBreachResponse, status_code=201, summary="Datenpanne melden")
async def create_data_breach(
    body: DataBreachCreate,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("editor", "admin"),
):
    """Erfasst eine neue Datenschutzverletzung und setzt die 72h-Frist."""
    notification_deadline = body.discovered_at + timedelta(hours=_NOTIFICATION_DEADLINE_HOURS)

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


@router.get("/{breach_id}", response_model=DataBreachResponse, summary="Datenpanne abrufen")
async def get_data_breach(
    breach_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("viewer", "editor", "admin"),
):
    result = await db.execute(select(DataBreachModel).where(DataBreachModel.id == breach_id))
    breach = result.scalar_one_or_none()
    if not breach:
        raise HTTPException(status_code=404, detail="Datenpanne nicht gefunden")
    return DataBreachResponse.model_validate(breach)


@router.patch("/{breach_id}", response_model=DataBreachResponse, summary="Datenpanne aktualisieren")
async def update_data_breach(
    breach_id: UUID,
    body: DataBreachUpdate,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("editor", "admin"),
):
    """Aktualisiert Status, Risikobewertung oder Meldestatus einer Datenpanne."""
    result = await db.execute(select(DataBreachModel).where(DataBreachModel.id == breach_id))
    breach = result.scalar_one_or_none()
    if not breach:
        raise HTTPException(status_code=404, detail="Datenpanne nicht gefunden")

    old_status = breach.status
    fields = [
        "title", "description", "status", "breach_type", "affected_data_categories",
        "affected_persons_count", "department", "assignee", "risk_level",
        "authority_notified_at", "subjects_notified_at", "authority_reference", "measures_taken",
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
    result = await db.execute(select(DataBreachModel).where(DataBreachModel.id == breach_id))
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
async def generate_notification_draft(
    breach_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("editor", "admin"),
):
    """Generiert per LLM einen Meldungsentwurf für die Aufsichtsbehörde."""
    result = await db.execute(select(DataBreachModel).where(DataBreachModel.id == breach_id))
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
    result = await db.execute(select(DataBreachModel).where(DataBreachModel.id == breach_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Datenpanne nicht gefunden")

    log_result = await db.execute(
        select(DataBreachActivityLogModel)
        .where(DataBreachActivityLogModel.breach_id == breach_id)
        .order_by(DataBreachActivityLogModel.created_at.asc())
    )
    return [
        DataBreachActivityResponse.model_validate(e)
        for e in log_result.scalars().all()
    ]
