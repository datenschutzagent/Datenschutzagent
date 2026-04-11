"""TOM-Katalog API (Art. 32 DSGVO) – Technisch-Organisatorische Maßnahmen."""
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_roles
from app.database import get_db
from app.models.db import TOMModel, orm_to_tom_response
from app.models.schemas import (
    TOMCreate,
    TOMListResponse,
    TOMResponse,
    TOMStatsResponse,
    TOMUpdate,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("", response_model=TOMListResponse, summary="TOMs auflisten")
async def list_toms(
    category: str | None = Query(default=None),
    implementation_status: str | None = Query(default=None),
    department_code: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=200, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _user=require_roles("viewer", "editor", "admin"),
):
    q = select(TOMModel)
    if category:
        q = q.where(TOMModel.category == category)
    if implementation_status:
        q = q.where(TOMModel.implementation_status == implementation_status)
    if department_code:
        q = q.where(TOMModel.department_codes.contains([department_code]))

    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar_one()

    q = q.order_by(TOMModel.category.asc(), TOMModel.title.asc()).offset(skip).limit(limit)
    result = await db.execute(q)
    items = [TOMResponse(**orm_to_tom_response(r)) for r in result.scalars().all()]
    return TOMListResponse(items=items, total=total)


@router.get("/stats", response_model=TOMStatsResponse, summary="TOM-Statistiken")
async def get_tom_stats(
    db: AsyncSession = Depends(get_db),
    _user=require_roles("viewer", "editor", "admin"),
):
    """Gibt Implementierungsrate und Aufschlüsselung nach Status/Kategorie zurück."""
    result = await db.execute(select(TOMModel))
    all_toms = result.scalars().all()

    by_status: dict[str, int] = {}
    by_category: dict[str, int] = {}
    implemented = 0

    for tom in all_toms:
        by_status[tom.implementation_status] = by_status.get(tom.implementation_status, 0) + 1
        by_category[tom.category] = by_category.get(tom.category, 0) + 1
        if tom.implementation_status == "implemented":
            implemented += 1

    relevant = len([t for t in all_toms if t.implementation_status != "not_applicable"])
    rate = (implemented / relevant * 100) if relevant > 0 else 0.0

    return TOMStatsResponse(
        total=len(all_toms),
        by_status=by_status,
        by_category=by_category,
        implementation_rate=round(rate, 1),
    )


@router.post("", response_model=TOMResponse, status_code=201, summary="TOM anlegen")
async def create_tom(
    body: TOMCreate,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("editor", "admin"),
):
    tom = TOMModel(
        title=body.title,
        description=body.description,
        category=body.category,
        implementation_status=body.implementation_status,
        responsible=body.responsible,
        review_date=body.review_date,
        evidence=body.evidence,
        department_codes=body.department_codes,
    )
    db.add(tom)
    await db.flush()
    await db.refresh(tom)
    return TOMResponse(**orm_to_tom_response(tom))


@router.get("/{tom_id}", response_model=TOMResponse, summary="TOM abrufen")
async def get_tom(
    tom_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("viewer", "editor", "admin"),
):
    result = await db.execute(select(TOMModel).where(TOMModel.id == tom_id))
    tom = result.scalar_one_or_none()
    if not tom:
        raise HTTPException(status_code=404, detail="TOM nicht gefunden")
    return TOMResponse(**orm_to_tom_response(tom))


@router.patch("/{tom_id}", response_model=TOMResponse, summary="TOM aktualisieren")
async def update_tom(
    tom_id: UUID,
    body: TOMUpdate,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("editor", "admin"),
):
    result = await db.execute(select(TOMModel).where(TOMModel.id == tom_id))
    tom = result.scalar_one_or_none()
    if not tom:
        raise HTTPException(status_code=404, detail="TOM nicht gefunden")

    for field in ["title", "description", "category", "implementation_status",
                  "responsible", "review_date", "evidence", "department_codes"]:
        val = getattr(body, field, None)
        if val is not None:
            setattr(tom, field, val)

    await db.flush()
    await db.refresh(tom)
    return TOMResponse(**orm_to_tom_response(tom))


@router.delete("/{tom_id}", status_code=204, summary="TOM löschen")
async def delete_tom(
    tom_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("admin"),
):
    result = await db.execute(select(TOMModel).where(TOMModel.id == tom_id))
    tom = result.scalar_one_or_none()
    if not tom:
        raise HTTPException(status_code=404, detail="TOM nicht gefunden")
    await db.delete(tom)
    await db.flush()
