"""AVV-Management API (Art. 28 DSGVO) – Auftragsverarbeitungsverträge."""
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_roles
from app.database import get_db
from app.models.db import AVVContractModel, orm_to_avv_response
from app.models.schemas import (
    AVVContractCreate,
    AVVContractResponse,
    AVVContractUpdate,
    AVVListResponse,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("", response_model=AVVListResponse, summary="AVV-Verträge auflisten")
async def list_avv_contracts(
    status: str | None = Query(default=None),
    department: str | None = Query(default=None),
    partner_type: str | None = Query(default=None),
    expiring_soon: bool = Query(default=False, description="Nur bald ablaufende Verträge (90 Tage)"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _user=require_roles("viewer", "editor", "admin"),
):
    q = select(AVVContractModel)
    if status:
        q = q.where(AVVContractModel.status == status)
    if department:
        q = q.where(AVVContractModel.department.ilike(f"%{department}%"))
    if partner_type:
        q = q.where(AVVContractModel.partner_type == partner_type)
    if expiring_soon:
        from datetime import date, timedelta
        threshold = date.today() + timedelta(days=90)
        q = q.where(
            AVVContractModel.expiry_date <= threshold,
            AVVContractModel.expiry_date >= date.today(),
            AVVContractModel.status == "signed",
        )

    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar_one()

    q = q.order_by(AVVContractModel.partner_name.asc()).offset(skip).limit(limit)
    result = await db.execute(q)
    items = [AVVContractResponse(**orm_to_avv_response(r)) for r in result.scalars().all()]
    return AVVListResponse(items=items, total=total)


@router.post("", response_model=AVVContractResponse, status_code=201, summary="AVV anlegen")
async def create_avv_contract(
    body: AVVContractCreate,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("editor", "admin"),
):
    contract = AVVContractModel(
        partner_name=body.partner_name,
        partner_type=body.partner_type,
        subject_matter=body.subject_matter,
        department=body.department,
        assignee=body.assignee,
        contract_date=body.contract_date,
        expiry_date=body.expiry_date,
        notes=body.notes,
    )
    db.add(contract)
    await db.flush()
    await db.refresh(contract)
    return AVVContractResponse(**orm_to_avv_response(contract))


@router.get("/{contract_id}", response_model=AVVContractResponse, summary="AVV abrufen")
async def get_avv_contract(
    contract_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("viewer", "editor", "admin"),
):
    result = await db.execute(select(AVVContractModel).where(AVVContractModel.id == contract_id))
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="AVV nicht gefunden")
    return AVVContractResponse(**orm_to_avv_response(contract))


@router.patch("/{contract_id}", response_model=AVVContractResponse, summary="AVV aktualisieren")
async def update_avv_contract(
    contract_id: UUID,
    body: AVVContractUpdate,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("editor", "admin"),
):
    result = await db.execute(select(AVVContractModel).where(AVVContractModel.id == contract_id))
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="AVV nicht gefunden")

    for field in ["partner_name", "partner_type", "subject_matter", "department",
                  "status", "assignee", "contract_date", "expiry_date", "notes"]:
        val = getattr(body, field, None)
        if val is not None:
            setattr(contract, field, val)

    await db.flush()
    await db.refresh(contract)
    return AVVContractResponse(**orm_to_avv_response(contract))


@router.post("/{contract_id}/risk-assessment", summary="Supplier-Risikobewertung durchführen")
async def assess_avv_risk(
    contract_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("editor", "admin"),
):
    """Führt eine LLM-gestützte Datenschutz-Risikobewertung für den Auftragsverarbeiter durch.

    Bewertet 5 Risikodimensionen und gibt Risikoscore (0-100), Risikolevel
    (low/medium/high/critical) sowie Maßnahmenempfehlungen zurück.
    Das Ergebnis wird im AVV-Datensatz gespeichert.
    """
    from app.services.avv_risk_service import assess_avv_risk as _assess
    result = await db.execute(select(AVVContractModel).where(AVVContractModel.id == contract_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="AVV nicht gefunden")
    try:
        assessment = await _assess(contract_id, db)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error("AVV risk assessment failed for %s: %s", contract_id, exc)
        raise HTTPException(status_code=500, detail=f"Risikobewertung fehlgeschlagen: {exc}")
    return assessment


@router.delete("/{contract_id}", status_code=204, summary="AVV löschen")
async def delete_avv_contract(
    contract_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("admin"),
):
    result = await db.execute(select(AVVContractModel).where(AVVContractModel.id == contract_id))
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="AVV nicht gefunden")
    await db.delete(contract)
    await db.flush()
