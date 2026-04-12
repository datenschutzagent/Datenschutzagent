"""Celery app and tasks for async jobs (document extraction, run_checks, DSFA, retention, notifications)."""
import asyncio
import logging
import uuid
from uuid import UUID

from celery import Celery
from celery.schedules import crontab
from sqlalchemy import create_engine, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.models.db import ActivityLogModel, CaseModel, DocumentModel, DSBReportJobModel, DSFAJobModel, PlaybookModel, RunChecksJobModel
from app.services.run_checks_service import run_checks_impl
from app.services.dsb_report_service import build_dsb_report, save_report
from app.storage import get_file
from app.services.document_processor import extract_text
from app.services.playbook_matching import rank_playbooks_for_selection
from app.services.weaviate_service import index_document_chunks

logger = logging.getLogger(__name__)

celery_app = Celery(
    "datenschutzagent",
    broker=settings.celery_broker_url,
    backend=settings.celery_broker_url,
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_routes={"app.celery_app.extract_document_text": "extraction"},
    beat_schedule={
        "retention-scan-nightly": {
            "task": "app.celery_app.retention_scan_task",
            "schedule": crontab(hour=2, minute=0),  # täglich um 02:00 Uhr
        },
        "deadline-notifications-daily": {
            "task": "app.celery_app.deadline_notifications_task",
            "schedule": crontab(hour=7, minute=0),  # täglich um 07:00 Uhr
        },
        "periodic-recheck-daily": {
            "task": "app.celery_app.periodic_recheck_task",
            "schedule": crontab(hour=3, minute=0),  # täglich um 03:00 Uhr
        },
    },
)

# Sync engine/session for worker only (lazy so API process does not need psycopg2 connection)
_engine = None
_session_factory = None

# Shared async engine/session factory for run_checks tasks.
# Created once per worker process to avoid per-task connection pool exhaustion.
_async_engine = None
_async_session_factory = None


def _get_session_factory():
    global _engine, _session_factory
    if _session_factory is None:
        _engine = create_engine(settings.database_sync_url, pool_pre_ping=True)
        _session_factory = sessionmaker(bind=_engine, autocommit=False, autoflush=False)
    return _session_factory


def _get_async_session_factory():
    global _async_engine, _async_session_factory
    if _async_session_factory is None:
        _async_engine = create_async_engine(settings.database_url, pool_pre_ping=True)
        _async_session_factory = async_sessionmaker(
            _async_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    return _async_session_factory


def _set_extraction_failed(session: Session, document_id: UUID, error_message: str) -> None:
    """Set document extraction_status to failed and persistence the error. Commits."""
    try:
        row = session.execute(select(DocumentModel).where(DocumentModel.id == document_id)).scalar_one_or_none()
        if row:
            row.extraction_status = "failed"
            row.extraction_error = error_message
            session.commit()
    except Exception:
        session.rollback()
        raise


def _parse_recheck_strategies() -> list[str]:
    """Parse RECHECK_DEFAULT_STRATEGIES setting into a list of strategy strings."""
    raw = getattr(settings, "recheck_default_strategies", "full_text") or "full_text"
    strategies = [s.strip() for s in raw.split(",") if s.strip() in ("full_text", "rag")]
    return strategies if strategies else ["full_text"]


def _maybe_auto_run_checks(session: Session, case_id: uuid.UUID) -> None:
    """If the case has auto_run_checks=True, find the best matching playbook and queue a run_checks job."""
    try:
        case = session.execute(select(CaseModel).where(CaseModel.id == case_id)).scalar_one_or_none()
        if not case or not getattr(case, "auto_run_checks", False):
            return
        playbooks = session.execute(select(PlaybookModel).where(PlaybookModel.is_active == True)).scalars().all()  # noqa: E712
        if not playbooks:
            logger.info("auto_run_checks: no active playbooks for case %s", case_id)
            return
        ranked = rank_playbooks_for_selection(
            playbooks,
            department=case.department or "",
            processing_context=case.processing_context,
            case_type=case.case_type,
            org_profile=settings.org_profile,
            strict_case_type=False,
        )
        best_playbook = ranked[0][0] if ranked else playbooks[0]
        strategies = _parse_recheck_strategies()
        job_id = uuid.uuid4()
        job = RunChecksJobModel(
            id=job_id,
            case_id=case_id,
            status="running",
            playbook_id=best_playbook.id,
            playbook_name=best_playbook.name,
            strategies=strategies,
        )
        session.add(job)
        session.commit()
        run_playbook_checks.delay(str(job_id))
        logger.info(
            "auto_run_checks queued job %s for case %s (playbook: %s, strategies: %s)",
            job_id, case_id, best_playbook.name, strategies,
        )
    except Exception as exc:
        logger.warning("auto_run_checks failed to queue job for case %s: %s", case_id, exc)


@celery_app.task(name="app.celery_app.extract_document_text", bind=True)
def extract_document_text(self, document_id: str) -> dict:
    """
    Run text extraction for a document and update Document.content.
    Called after upload; document row must exist and storage_path must be set.
    """
    logger.info("extract_document_text started", extra={"document_id": document_id})
    uid = UUID(document_id)
    session: Session = _get_session_factory()()
    try:
        row = session.execute(select(DocumentModel).where(DocumentModel.id == uid)).scalar_one_or_none()
        if not row:
            logger.error(
                "extract_document_text failed",
                extra={"document_id": document_id, "error": "document_not_found"},
            )
            return {"ok": False, "error": "document_not_found"}
        if not row.storage_path:
            logger.error(
                "extract_document_text failed",
                extra={"document_id": document_id, "error": "no_storage_path"},
            )
            return {"ok": False, "error": "no_storage_path"}
        row.extraction_status = "processing"
        row.extraction_error = None
        session.commit()
        content_bytes = get_file(row.storage_path)
        result = extract_text(row.name, content_bytes)
        row.content = result.text
        row.extraction_method = result.extraction_method
        row.extraction_status = "done"
        row.extraction_error = None
        session.commit()
        if getattr(settings, "weaviate_indexing_enabled", False) and result.text:
            indexed = index_document_chunks(row.id, row.case_id, result.text)
            if not indexed:
                logger.warning(
                    "Weaviate indexing skipped or failed for document %s – RAG checks will fall back to full_text",
                    document_id,
                )
        logger.info("extract_document_text done", extra={"document_id": document_id})

        # Auto-run checks if the case has auto_run_checks=True
        _maybe_auto_run_checks(session, row.case_id)

        return {"ok": True, "document_id": document_id}
    except FileNotFoundError:
        _set_extraction_failed(session, uid, "file_not_found")
        logger.error(
            "extract_document_text failed",
            extra={"document_id": document_id, "error": "file_not_found"},
        )
        return {"ok": False, "error": "file_not_found"}
    except Exception as e:
        err_msg = str(e)
        _set_extraction_failed(session, uid, err_msg)
        logger.error(
            "extract_document_text failed",
            extra={"document_id": document_id, "error": err_msg},
        )
        return {"ok": False, "error": err_msg}
    finally:
        session.close()


def _count_checks_total(playbook_content: dict, doc_count: int, strategies: list[str]) -> int:
    """Calculate total number of individual check invocations for progress tracking."""
    raw_checks = playbook_content.get("checks") if isinstance(playbook_content, dict) else []
    if not raw_checks:
        return 0
    doc_checks = sum(
        1 for item in raw_checks
        if isinstance(item, dict)
        and (item.get("scope") or item.get("type") or "document").lower() not in ("case", "cross_document")
    )
    case_checks = len(raw_checks) - doc_checks
    n_strategies = len(strategies) if strategies else 1
    return (doc_checks * max(doc_count, 1) + case_checks) * n_strategies


async def _run_checks_async(job_id: str) -> None:
    """Load job, run run_checks_impl, write activity log and update job.

    Uses the module-level shared async engine to avoid creating a new connection
    pool per task invocation (which would exhaust database connections under load).
    """
    session_factory = _get_async_session_factory()
    job_uuid = UUID(job_id)

    async def _on_check_done() -> None:
        """Atomically increment checks_done on the job row using a short-lived session."""
        try:
            async with session_factory() as psession:
                await psession.execute(
                    update(RunChecksJobModel)
                    .where(RunChecksJobModel.id == job_uuid)
                    .values(checks_done=RunChecksJobModel.checks_done + 1)
                )
                await psession.commit()
        except Exception as exc:
            logger.debug("Progress update failed (non-critical): %s", exc)

    async with session_factory() as session:
        result = await session.execute(select(RunChecksJobModel).where(RunChecksJobModel.id == job_uuid))
        job = result.scalar_one_or_none()
        if not job:
            raise ValueError("run_checks job not found")
        if job.status != "running":
            return
        case_id = job.case_id
        playbook_id = job.playbook_id
        strategies = list(job.strategies) if job.strategies else ["full_text"]

        # Load playbook to calculate checks_total; set it before running
        from app.models.db import PlaybookModel, DocumentModel as DocModel
        pb_result = await session.execute(select(PlaybookModel).where(PlaybookModel.id == playbook_id))
        playbook = pb_result.scalar_one_or_none()
        doc_result = await session.execute(
            select(DocModel).where(
                DocModel.case_id == case_id,
                DocModel.extraction_status == "done",
            )
        )
        doc_count = len(doc_result.scalars().all())
        if playbook:
            checks_total = _count_checks_total(playbook.content, doc_count, strategies)
            job.checks_total = checks_total
            await session.flush()

        findings_added, errors, activity_payload = await run_checks_impl(
            session, case_id, playbook_id, strategies, on_check_done=_on_check_done, skip_resolved=True
        )
        activity = ActivityLogModel(
            case_id=case_id,
            event_type="run_checks",
            payload=activity_payload,
        )
        session.add(activity)
        job.status = "completed"
        job.findings_count = findings_added
        job.checks_done = job.checks_total  # ensure 100% at completion
        job.result_payload = activity_payload
        job.error = None
        await session.commit()


@celery_app.task(name="app.celery_app.run_playbook_checks", bind=True)
def run_playbook_checks(self, job_id: str) -> dict:
    """
    Run playbook checks for a run_checks_jobs row. Loads job, runs run_checks_impl in async context,
    writes ActivityLog and updates job to completed/failed.
    """
    logger.info("run_playbook_checks started", extra={"job_id": job_id})
    try:
        asyncio.run(_run_checks_async(job_id))
        logger.info("run_playbook_checks done", extra={"job_id": job_id})
        return {"ok": True, "job_id": job_id}
    except Exception as e:
        err_msg = str(e)
        logger.error("run_playbook_checks failed", extra={"job_id": job_id, "error": err_msg})
        _set_run_checks_job_failed(job_id, err_msg)
        return {"ok": False, "error": err_msg}


def _set_run_checks_job_failed(job_id: str, error_message: str) -> None:
    """Update run_checks_jobs row to status=failed. Uses sync session."""
    session: Session = _get_session_factory()()
    try:
        row = session.execute(select(RunChecksJobModel).where(RunChecksJobModel.id == UUID(job_id))).scalar_one_or_none()
        if row:
            row.status = "failed"
            row.error = error_message
            session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


async def _build_dsb_report_async(job_id: str) -> None:
    """Load DSB report job, run build_dsb_report, save report and update job.

    Uses the module-level shared async engine (same pool as _run_checks_async).
    """
    session_factory = _get_async_session_factory()
    async with session_factory() as session:
        result = await session.execute(select(DSBReportJobModel).where(DSBReportJobModel.id == UUID(job_id)))
        job = result.scalar_one_or_none()
        if not job:
            raise ValueError("dsb_report job not found")
        if job.status != "running":
            return
        case_id = job.case_id
        report = await build_dsb_report(case_id, session)
        await save_report(case_id, report, session)
        job.status = "completed"
        job.error = None
        await session.commit()


@celery_app.task(name="app.celery_app.build_dsb_report_task", bind=True)
def build_dsb_report_task(self, job_id: str) -> dict:
    """
    Build DSB report for a dsb_report_jobs row. Runs build_dsb_report in async context and persists result.
    """
    logger.info("build_dsb_report_task started", extra={"job_id": job_id})
    try:
        asyncio.run(_build_dsb_report_async(job_id))
        logger.info("build_dsb_report_task done", extra={"job_id": job_id})
        return {"ok": True, "job_id": job_id}
    except Exception as e:
        err_msg = str(e)
        logger.error("build_dsb_report_task failed", extra={"job_id": job_id, "error": err_msg})
        _set_dsb_report_job_failed(job_id, err_msg)
        return {"ok": False, "error": err_msg}


def _set_dsb_report_job_failed(job_id: str, error_message: str) -> None:
    """Update dsb_report_jobs row to status=failed. Uses sync session."""
    session: Session = _get_session_factory()()
    try:
        row = session.execute(select(DSBReportJobModel).where(DSBReportJobModel.id == UUID(job_id))).scalar_one_or_none()
        if row:
            row.status = "failed"
            row.error = error_message
            session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ---------------------------------------------------------------------------
# DSFA-Task
# ---------------------------------------------------------------------------

async def _build_dsfa_async(job_id: str) -> None:
    """Lädt DSFA-Job, generiert die DSFA via LLM und persistiert das Ergebnis."""
    session_factory = _get_async_session_factory()
    async with session_factory() as session:
        result = await session.execute(select(DSFAJobModel).where(DSFAJobModel.id == UUID(job_id)))
        job = result.scalar_one_or_none()
        if not job or job.status != "running":
            return
        from app.services.dsfa_service import generate_dsfa, save_dsfa
        payload = await generate_dsfa(job.case_id, session)
        await save_dsfa(job.case_id, payload, session)
        job.status = "completed"
        job.error = None
        await session.commit()


@celery_app.task(name="app.celery_app.build_dsfa_task", bind=True)
def build_dsfa_task(self, job_id: str) -> dict:
    """Generiert DSFA für einen dsfa_jobs-Eintrag asynchron."""
    logger.info("build_dsfa_task started", extra={"job_id": job_id})
    try:
        asyncio.run(_build_dsfa_async(job_id))
        logger.info("build_dsfa_task done", extra={"job_id": job_id})
        return {"ok": True, "job_id": job_id}
    except Exception as e:
        err_msg = str(e)
        logger.error("build_dsfa_task failed", extra={"job_id": job_id, "error": err_msg})
        _set_dsfa_job_failed(job_id, err_msg)
        return {"ok": False, "error": err_msg}


def _set_dsfa_job_failed(job_id: str, error_message: str) -> None:
    """Update dsfa_jobs row to status=failed. Uses sync session."""
    session: Session = _get_session_factory()()
    try:
        row = session.execute(select(DSFAJobModel).where(DSFAJobModel.id == UUID(job_id))).scalar_one_or_none()
        if row:
            row.status = "failed"
            row.error = error_message
            session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Retention-Scan-Task (Celery Beat, nächtlich)
# ---------------------------------------------------------------------------

@celery_app.task(name="app.celery_app.retention_scan_task", bind=True)
def retention_scan_task(self) -> dict:
    """Archiviert fällige Vorgänge gemäß Aufbewahrungsfrist. Läuft täglich via Celery Beat."""
    logger.info("retention_scan_task started")
    try:
        result = asyncio.run(_retention_scan_async())
        logger.info("retention_scan_task done", extra={"archived": result.get("archived_count", 0)})
        return {"ok": True, **result}
    except Exception as e:
        err_msg = str(e)
        logger.error("retention_scan_task failed", extra={"error": err_msg})
        return {"ok": False, "error": err_msg}


async def _retention_scan_async() -> dict:
    session_factory = _get_async_session_factory()
    async with session_factory() as session:
        from app.services.retention_service import scan_cases_for_retention
        archived = await scan_cases_for_retention(session, dry_run=False)
        await session.commit()
        return {"archived_count": len(archived)}


# ---------------------------------------------------------------------------
# Deadline-Benachrichtigungs-Task (Celery Beat, täglich)
# ---------------------------------------------------------------------------

@celery_app.task(name="app.celery_app.deadline_notifications_task", bind=True)
def deadline_notifications_task(self) -> dict:
    """Scannt Fristen und sendet E-Mail-Benachrichtigungen. Läuft täglich via Celery Beat."""
    logger.info("deadline_notifications_task started")
    try:
        result = asyncio.run(_deadline_notifications_async())
        logger.info("deadline_notifications_task done", extra={"sent": result.get("sent", 0)})
        return {"ok": True, **result}
    except Exception as e:
        err_msg = str(e)
        logger.error("deadline_notifications_task failed", extra={"error": err_msg})
        return {"ok": False, "error": err_msg}


async def _deadline_notifications_async() -> dict:
    session_factory = _get_async_session_factory()
    async with session_factory() as session:
        from app.services.notification_service import scan_and_notify_deadlines
        result = await scan_and_notify_deadlines(session)
        await session.commit()
        return result


# ---------------------------------------------------------------------------
# Periodische Re-Check-Task (Celery Beat, täglich)
# ---------------------------------------------------------------------------

@celery_app.task(name="app.celery_app.periodic_recheck_task", bind=True)
def periodic_recheck_task(self) -> dict:
    """Führt automatische Re-Checks für Vorgänge durch, deren recheck_interval_days abgelaufen ist."""
    logger.info("periodic_recheck_task started")
    try:
        result = asyncio.run(_periodic_recheck_async())
        logger.info("periodic_recheck_task done", extra={"queued": result.get("queued", 0)})
        return {"ok": True, **result}
    except Exception as e:
        err_msg = str(e)
        logger.error("periodic_recheck_task failed", extra={"error": err_msg})
        return {"ok": False, "error": err_msg}


async def _periodic_recheck_async() -> dict:
    """Findet Vorgänge, bei denen recheck_interval_days seit dem letzten Check abgelaufen ist,
    und stellt automatisch neue run_checks-Jobs ein."""
    from datetime import datetime, timezone, timedelta
    from sqlalchemy import and_

    session_factory = _get_async_session_factory()
    queued_count = 0

    async with session_factory() as session:
        now = datetime.now(timezone.utc)
        # Vorgänge mit konfiguriertem Recheck-Intervall laden
        result = await session.execute(
            select(CaseModel).where(
                and_(
                    CaseModel.recheck_interval_days != None,  # noqa: E711
                    CaseModel.recheck_interval_days > 0,
                    CaseModel.archived_at == None,  # noqa: E711
                    CaseModel.status != "completed",
                )
            )
        )
        cases = result.scalars().all()

        for case in cases:
            # Prüfen ob Interval abgelaufen
            last_check = case.last_rechecked_at or case.created_at
            interval = timedelta(days=case.recheck_interval_days)
            if (now - last_check) < interval:
                continue

            # Bestes aktives Playbook finden
            playbooks = await session.execute(
                select(PlaybookModel).where(PlaybookModel.is_active == True)  # noqa: E712
            )
            active_playbooks = playbooks.scalars().all()
            if not active_playbooks:
                continue

            ranked = rank_playbooks_for_selection(
                active_playbooks,
                department=case.department or "",
                processing_context=case.processing_context,
                case_type=case.case_type,
                org_profile=settings.org_profile,
                strict_case_type=False,
            )
            best_playbook = ranked[0][0] if ranked else active_playbooks[0]

            recheck_strategies = _parse_recheck_strategies()
            job_id = uuid.uuid4()
            job = RunChecksJobModel(
                id=job_id,
                case_id=case.id,
                status="running",
                playbook_id=best_playbook.id,
                playbook_name=best_playbook.name,
                strategies=recheck_strategies,
            )
            session.add(job)

            # last_rechecked_at aktualisieren
            case.last_rechecked_at = now

            await session.flush()
            run_playbook_checks.apply_async(
                (str(job_id),),
                countdown=queued_count * settings.run_checks_stagger_seconds,
            )
            queued_count += 1
            logger.info(
                "periodic_recheck queued job %s for case %s (interval: %dd, countdown: %ds)",
                job_id, case.id, case.recheck_interval_days,
                (queued_count - 1) * settings.run_checks_stagger_seconds,
            )

        await session.commit()

    return {"queued": queued_count}
