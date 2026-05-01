"""AVV-Management API (Art. 28 DSGVO) – Auftragsverarbeitungsverträge."""
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_roles
from app.core.rate_limit import limiter
from app.database import get_db
from app.models.db import AVVContractModel
from app.models.schemas import (
    AVVContractCreate,
    AVVContractResponse,
    AVVContractUpdate,
    AVVListResponse,
    AVVStatsResponse,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/stats", response_model=AVVStatsResponse, summary="AVV-Statistiken abrufen")
async def get_avv_stats(
    db: AsyncSession = Depends(get_db),
    _user=require_roles("viewer", "editor", "admin"),
):
    """Aggregierte AVV-Statistiken: Status-Verteilung, Ablaufrisiko, Risiko-Score-Verteilung."""
    from datetime import date, timedelta
    from sqlalchemy import text
    today = date.today()
    threshold_90 = today + timedelta(days=90)

    result = await db.execute(text("""
        WITH by_status AS (
            SELECT status AS key1, COUNT(*) AS cnt FROM avv_contracts GROUP BY status
        ),
        by_risk AS (
            SELECT risk_level AS key1, COUNT(*) AS cnt
            FROM avv_contracts WHERE risk_level IS NOT NULL GROUP BY risk_level
        ),
        expiry AS (
            SELECT
                COUNT(*) FILTER (
                    WHERE status = 'signed'
                    AND expiry_date IS NOT NULL
                    AND expiry_date <= :threshold_90
                    AND expiry_date >= :today
                ) AS expiring_soon,
                COUNT(*) FILTER (WHERE status = 'expired') AS expired,
                AVG(risk_score) FILTER (WHERE risk_score IS NOT NULL) AS avg_risk
            FROM avv_contracts
        ),
        total AS (
            SELECT COUNT(*) AS cnt FROM avv_contracts
        )
        SELECT 'status'  AS qname, key1, cnt, NULL::float FROM by_status
        UNION ALL
        SELECT 'risk',    key1, cnt, NULL FROM by_risk
        UNION ALL
        SELECT 'expiry',  NULL, expiring_soon, avg_risk FROM expiry
        UNION ALL
        SELECT 'expired', NULL, expired, NULL FROM expiry
        UNION ALL
        SELECT 'total',   NULL, cnt, NULL FROM total
    """), {"today": today, "threshold_90": threshold_90})
    rows = result.fetchall()

    by_status: dict[str, int] = {}
    by_risk_level: dict[str, int] = {}
    expiring_soon: int = 0
    expired: int = 0
    avg_risk_score: float | None = None
    total: int = 0

    for row in rows:
        qname, key1, cnt, f1 = row
        if qname == "status":
            by_status[key1] = int(cnt or 0)
        elif qname == "risk":
            by_risk_level[key1] = int(cnt or 0)
        elif qname == "expiry":
            expiring_soon = int(cnt or 0)
            avg_risk_score = float(f1) if f1 is not None else None
        elif qname == "expired":
            expired = int(cnt or 0)
        elif qname == "total":
            total = int(cnt or 0)

    return AVVStatsResponse(
        total=total,
        by_status=by_status,
        expiring_soon=expiring_soon,
        expired=expired,
        avg_risk_score=round(avg_risk_score, 1) if avg_risk_score is not None else None,
        by_risk_level=by_risk_level,
    )


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
    items = [AVVContractResponse.model_validate(r) for r in result.scalars().all()]
    return AVVListResponse(items=items, total=total)


@router.post("", response_model=AVVContractResponse, status_code=201, summary="AVV anlegen")
@limiter.limit("30/minute")
async def create_avv_contract(
    request: Request,
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
    return AVVContractResponse.model_validate(contract)


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
    return AVVContractResponse.model_validate(contract)


@router.patch("/{contract_id}", response_model=AVVContractResponse, summary="AVV aktualisieren")
@limiter.limit("60/minute")
async def update_avv_contract(
    request: Request,
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
    return AVVContractResponse.model_validate(contract)


@router.post("/{contract_id}/risk-assessment", summary="Supplier-Risikobewertung durchführen")
@limiter.limit("5/minute")
async def assess_avv_risk(
    request: Request,
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
