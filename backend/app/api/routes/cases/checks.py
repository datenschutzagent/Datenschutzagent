"""Case run-checks endpoints: status polling, SSE stream, and check execution."""

import asyncio
import json as _json
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.celery_app import run_playbook_checks
from app.config import settings
from app.constants import JobStatus
from app.core.auth import require_roles
from app.core.rate_limit import limiter
from app.core.request_id import get_request_id
from app.database import get_db
from app.models import CaseModel, CaseResponse
from app.models.db import (
    ActivityLogModel,
    DocumentModel,
    PlaybookModel,
    RunChecksJobModel,
)
from app.models.schemas import (
    ActivityResponse,
    RunChecksRequest,
)
from app.services.query_helpers import case_relations
from app.services.run_checks_service import run_checks_impl

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/{case_id}/run-checks/status")
async def get_run_checks_status(
    case_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Return the latest run_checks job status for this case (for polling). Includes last_run activity for timeline and documents_changed_since_last_run flag."""
    result = await db.execute(select(CaseModel).where(CaseModel.id == case_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Case not found")
    job_result = await db.execute(
        select(RunChecksJobModel)
        .where(RunChecksJobModel.case_id == case_id)
        .order_by(RunChecksJobModel.created_at.desc())
        .limit(1)
    )
    job = job_result.scalar_one_or_none()
    activity_result = await db.execute(
        select(ActivityLogModel)
        .where(
            ActivityLogModel.case_id == case_id,
            ActivityLogModel.event_type == "run_checks",
        )
        .order_by(ActivityLogModel.created_at.desc())
        .limit(1)
    )
    last_activity = activity_result.scalar_one_or_none()
    last_run = ActivityResponse.model_validate(last_activity) if last_activity else None

    # Determine if any document was re-uploaded after the last run-checks job
    documents_changed = False
    if job and job.status == JobStatus.COMPLETED:
        max_reupload_result = await db.execute(
            select(func.max(DocumentModel.uploaded_at)).where(
                DocumentModel.case_id == case_id, DocumentModel.version > 1
            )
        )
        max_reupload = max_reupload_result.scalar_one_or_none()
        if max_reupload and max_reupload > job.created_at:
            documents_changed = True

    if not job:
        return {
            "status": "never_run",
            "job_id": None,
            "playbook_name": None,
            "findings_count": None,
            "error": None,
            "last_run": last_run,
            "documents_changed_since_last_run": False,
            "checks_total": 0,
            "checks_done": 0,
        }
    return {
        "status": job.status,
        "job_id": str(job.id),
        "playbook_name": job.playbook_name,
        "findings_count": job.findings_count,
        "error": job.error,
        "last_run": last_run,
        "documents_changed_since_last_run": documents_changed,
        "checks_total": job.checks_total,
        "checks_done": job.checks_done,
    }


@router.get("/{case_id}/run-checks/stream", summary="Run-Checks-Status als SSE-Stream")
async def stream_run_checks_status(
    case_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Server-Sent Events stream for run-checks job progress.

    Emits ``data: <json>`` events every 2 s while a job is running.
    Sends a final ``event: done`` when the job reaches completed/failed/never_run,
    then closes the stream.  The client can use ``EventSource`` instead of polling.

    Event payload matches GET /{case_id}/run-checks/status.
    """
    result = await db.execute(select(CaseModel).where(CaseModel.id == case_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Case not found")

    async def _event_generator():
        poll_interval = 2  # seconds between DB polls
        max_polls = 300  # ~10 min max stream duration
        for _ in range(max_polls):
            # Fresh session per poll to avoid stale reads
            from app.database import async_session_factory

            async with async_session_factory() as poll_db:
                job_result = await poll_db.execute(
                    select(RunChecksJobModel)
                    .where(RunChecksJobModel.case_id == case_id)
                    .order_by(RunChecksJobModel.created_at.desc())
                    .limit(1)
                )
                job = job_result.scalar_one_or_none()
                activity_result = await poll_db.execute(
                    select(ActivityLogModel)
                    .where(
                        ActivityLogModel.case_id == case_id,
                        ActivityLogModel.event_type == "run_checks",
                    )
                    .order_by(ActivityLogModel.created_at.desc())
                    .limit(1)
                )
                last_activity = activity_result.scalar_one_or_none()
                last_run = (
                    ActivityResponse.model_validate(last_activity)
                    if last_activity
                    else None
                )

                if not job:
                    payload = {
                        "status": "never_run",
                        "job_id": None,
                        "playbook_name": None,
                        "findings_count": None,
                        "error": None,
                        "last_run": last_run,
                        "checks_total": 0,
                        "checks_done": 0,
                    }
                else:
                    payload = {
                        "status": job.status,
                        "job_id": str(job.id),
                        "playbook_name": job.playbook_name,
                        "findings_count": job.findings_count,
                        "error": job.error,
                        "last_run": last_run,
                        "checks_total": job.checks_total,
                        "checks_done": job.checks_done,
                    }

                is_terminal = not job or job.status in (
                    JobStatus.COMPLETED,
                    JobStatus.FAILED,
                    "never_run",
                )
                event_type = "done" if is_terminal else "progress"
                yield f"event: {event_type}\ndata: {_json.dumps(payload, default=str)}\n\n"

            if is_terminal:
                return
            await asyncio.sleep(poll_interval)
        # Timeout: send done with last known state
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # nginx: disable proxy buffering
        },
    )


@router.post("/{case_id}/run-checks", summary="Playbook-Prüfungen starten")
@limiter.limit("10/minute")
async def run_checks(
    request: Request,
    case_id: UUID,
    body: RunChecksRequest,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("editor", "admin"),
):
    """Run playbook checks against all case documents. Returns 202 when queued (Celery), 200 with case when run synchronously."""
    result = await db.execute(
        select(CaseModel)
        .where(CaseModel.id == case_id)
        .options(*case_relations(findings=False))
    )
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    pb_result = await db.execute(
        select(PlaybookModel).where(PlaybookModel.id == body.playbook_id)
    )
    playbook = pb_result.scalar_one_or_none()
    if not playbook:
        raise HTTPException(status_code=404, detail="Playbook not found")

    raw_checks = (
        playbook.content.get("checks") if isinstance(playbook.content, dict) else []
    )
    if not raw_checks:
        await db.refresh(case)
        return CaseResponse.model_validate(case)

    strategies = body.strategies or ["full_text"]
    use_async = settings.celery_enabled and bool(
        (settings.celery_broker_url or "").strip()
    )

    # Concurrency hardening (Phase 4): take a Postgres advisory lock on
    # (case_id, playbook_id) BEFORE the duplicate-job check. Without the
    # lock two concurrent requests could both pass the SELECT and both
    # insert a job (classic SELECT-then-INSERT race). 423 = "Locked"
    # signals to the UI that the conflict is operational, not a 409
    # "you sent the wrong thing".
    from app.core.concurrency import try_acquire_run_checks_lock

    if not await try_acquire_run_checks_lock(db, case_id, body.playbook_id):
        raise HTTPException(
            status_code=423,
            detail="A check run for this case and playbook is currently being started by another request.",
        )

    # Prevent duplicate concurrent runs: return 409 if a job is already running
    running_job_result = await db.execute(
        select(RunChecksJobModel).where(
            RunChecksJobModel.case_id == case_id,
            RunChecksJobModel.playbook_id == body.playbook_id,
            RunChecksJobModel.status == JobStatus.RUNNING,
        )
    )
    if running_job_result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=409,
            detail="A check run for this case and playbook is already in progress. Please wait for it to finish.",
        )

    if use_async:
        job = RunChecksJobModel(
            case_id=case_id,
            status=JobStatus.RUNNING,
            playbook_id=playbook.id,
            playbook_name=playbook.name,
            strategies=strategies,
        )
        db.add(job)
        await db.flush()
        await db.refresh(job)
        # Commit FIRST so the job row is visible to the Celery worker's DB session.
        # Previously the task was dispatched before commit, causing a race condition
        # where the worker could not find the job row.
        await db.commit()
        celery_result = run_playbook_checks.delay(str(job.id), get_request_id())
        job.celery_task_id = celery_result.id
        await db.commit()
        logger.info(
            "run_checks: dispatched celery task",
            extra={
                "job_id": str(job.id),
                "case_id": str(case_id),
                "playbook_name": playbook.name,
                "strategies": strategies,
                "celery_task_id": celery_result.id,
            },
        )
        return JSONResponse(
            status_code=202,
            content={
                "job_id": str(job.id),
                "status": JobStatus.RUNNING,
                "message": "Playbook-Checks werden ausgeführt.",
            },
        )

    findings_added, errors, activity_payload = await run_checks_impl(
        db, case_id, body.playbook_id, strategies, skip_resolved=body.skip_resolved
    )
    activity = ActivityLogModel(
        case_id=case_id,
        event_type="run_checks",
        payload=activity_payload,
    )
    db.add(activity)
    await db.flush()
    result2 = await db.execute(
        select(CaseModel).where(CaseModel.id == case_id).options(*case_relations())
    )
    case = result2.scalar_one()
    return CaseResponse.model_validate(case)
