"""DSFA API: Datenschutz-Folgenabschätzung (Art. 35 DSGVO) generieren und verwalten."""
import asyncio
import logging
import uuid
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_roles
from app.database import get_db
from app.models.db import (
    CaseModel,
    DSFAAssessmentModel,
    DSFAJobModel,
    UserModel,
)
from app.models.schemas import (
    DSFAFinalizeRequest,
    DSFAJobStatusResponse,
    DSFAResponse,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/{case_id}/dsfa/screening", summary="DSFA-Screening (Prüft ob DSFA erforderlich)")
async def screen_dsfa(
    case_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("viewer", "editor", "admin"),
):
    """Prüft anhand der EDSA-Leitlinien (9-Faktoren-Test), ob eine DSFA gemäß Art. 35 DSGVO
    erforderlich ist. Gibt score, Faktoren und Empfehlung zurück (keine LLM-Kosten).
    """
    from app.services.dsfa_service import screen_dsfa_requirement
    case_result = await db.execute(select(CaseModel).where(CaseModel.id == case_id))
    if case_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Vorgang nicht gefunden")
    result = await screen_dsfa_requirement(case_id, db)
    return result


@router.get("/{case_id}/dsfa", response_model=DSFAResponse, summary="DSFA abrufen")
async def get_dsfa(
    case_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("viewer", "editor", "admin"),
):
    """Gibt die aktuelle DSFA für einen Vorgang zurück."""
    result = await db.execute(select(DSFAAssessmentModel).where(DSFAAssessmentModel.case_id == case_id))
    dsfa = result.scalar_one_or_none()
    if not dsfa:
        raise HTTPException(status_code=404, detail="Keine DSFA für diesen Vorgang vorhanden. Bitte zuerst generieren.")
    return DSFAResponse.model_validate(dsfa)


@router.post("/{case_id}/dsfa/generate", response_model=DSFAJobStatusResponse, status_code=202, summary="DSFA generieren")
async def generate_dsfa(
    case_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("editor", "admin"),
):
    """Startet die asynchrone Generierung einer DSFA für den Vorgang."""
    case_result = await db.execute(select(CaseModel).where(CaseModel.id == case_id))
    if case_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Vorgang nicht gefunden")

    from app.config import settings
    job_id = uuid.uuid4()
    job = DSFAJobModel(
        id=job_id,
        case_id=case_id,
        status="running",
    )
    db.add(job)
    await db.flush()

    if settings.celery_enabled:
        from app.celery_app import build_dsfa_task
        task = build_dsfa_task.delay(str(job_id))
        job.celery_task_id = task.id
        await db.flush()
    else:
        # Synchroner Fallback
        asyncio.create_task(_run_dsfa_inline(job_id, db))

    return DSFAJobStatusResponse(
        job_id=job_id,
        case_id=case_id,
        status="running",
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.get("/{case_id}/dsfa/status", summary="DSFA-Job-Status abfragen")
async def get_dsfa_job_status(
    case_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("viewer", "editor", "admin"),
):
    """Gibt den Status des letzten DSFA-Generierungsjobs zurück."""
    result = await db.execute(
        select(DSFAJobModel)
        .where(DSFAJobModel.case_id == case_id)
        .order_by(DSFAJobModel.created_at.desc())
        .limit(1)
    )
    job = result.scalar_one_or_none()
    if not job:
        return {"status": "not_started"}
    return DSFAJobStatusResponse(
        job_id=job.id,
        case_id=job.case_id,
        status=job.status,
        error=job.error,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.patch("/{case_id}/dsfa/finalize", response_model=DSFAResponse, summary="DSFA finalisieren")
async def finalize_dsfa(
    case_id: UUID,
    body: DSFAFinalizeRequest,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("editor", "admin"),
):
    """Markiert die DSFA als finalisiert (nicht mehr bearbeitbar)."""
    result = await db.execute(select(DSFAAssessmentModel).where(DSFAAssessmentModel.case_id == case_id))
    dsfa = result.scalar_one_or_none()
    if not dsfa:
        raise HTTPException(status_code=404, detail="Keine DSFA vorhanden")
    if dsfa.status == "finalized":
        raise HTTPException(status_code=400, detail="DSFA ist bereits finalisiert")

    dsfa.status = "finalized"
    dsfa.finalized_at = datetime.now(timezone.utc)
    dsfa.finalized_by = body.finalized_by
    await db.flush()
    await db.refresh(dsfa)
    return DSFAResponse.model_validate(dsfa)


async def _run_dsfa_inline(job_id: UUID, db: AsyncSession) -> None:
    """Synchroner Fallback für DSFA-Generierung ohne Celery."""
    from app.services.dsfa_service import generate_dsfa, save_dsfa
    from app.database import async_session_factory

    async with async_session_factory() as session:
        job_result = await session.execute(select(DSFAJobModel).where(DSFAJobModel.id == job_id))
        job = job_result.scalar_one_or_none()
        if not job:
            return
        try:
            payload = await generate_dsfa(job.case_id, session)
            await save_dsfa(job.case_id, payload, session)
            job.status = "completed"
            await session.commit()
        except Exception as exc:
            job.status = "failed"
            job.error = str(exc)[:490]
            await session.commit()
            logger.error("DSFA inline generation failed for job %s: %s", job_id, exc)
