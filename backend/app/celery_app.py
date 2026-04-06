"""Celery app and tasks for async jobs (document extraction, run_checks)."""
import asyncio
import logging
import uuid
from uuid import UUID

from celery import Celery
from sqlalchemy import create_engine, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.models.db import ActivityLogModel, CaseModel, DocumentModel, DSBReportJobModel, PlaybookModel, RunChecksJobModel
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
)

# Sync engine/session for worker only (lazy so API process does not need psycopg2 connection)
_engine = None
_session_factory = None


def _get_session_factory():
    global _engine, _session_factory
    if _session_factory is None:
        _engine = create_engine(settings.database_sync_url, pool_pre_ping=True)
        _session_factory = sessionmaker(bind=_engine, autocommit=False, autoflush=False)
    return _session_factory


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
        job_id = uuid.uuid4()
        job = RunChecksJobModel(
            id=job_id,
            case_id=case_id,
            status="running",
            playbook_id=best_playbook.id,
            playbook_name=best_playbook.name,
            strategies=["full_text"],
        )
        session.add(job)
        session.commit()
        run_playbook_checks.delay(str(job_id))
        logger.info("auto_run_checks queued job %s for case %s (playbook: %s)", job_id, case_id, best_playbook.name)
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
    """Load job, run run_checks_impl, write activity log and update job. Uses own async engine/session."""
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    async_session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    # Progress callback uses a separate session to avoid interfering with the main transaction
    progress_engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    progress_session_factory = async_sessionmaker(
        progress_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    job_uuid = UUID(job_id)

    async def _on_check_done() -> None:
        """Atomically increment checks_done on the job row."""
        try:
            async with progress_session_factory() as psession:
                await psession.execute(
                    update(RunChecksJobModel)
                    .where(RunChecksJobModel.id == job_uuid)
                    .values(checks_done=RunChecksJobModel.checks_done + 1)
                )
                await psession.commit()
        except Exception as exc:
            logger.debug("Progress update failed (non-critical): %s", exc)

    async with async_session_factory() as session:
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
        from sqlalchemy.orm import selectinload
        pb_result = await session.execute(select(PlaybookModel).where(PlaybookModel.id == playbook_id))
        playbook = pb_result.scalar_one_or_none()
        doc_result = await session.execute(
            select(DocModel).where(DocModel.case_id == case_id)
        )
        doc_count = len(doc_result.scalars().all())
        if playbook:
            checks_total = _count_checks_total(playbook.content, doc_count, strategies)
            job.checks_total = checks_total
            await session.flush()

        findings_added, errors, activity_payload = await run_checks_impl(
            session, case_id, playbook_id, strategies, on_check_done=_on_check_done
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
    await engine.dispose()
    await progress_engine.dispose()


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
    """Load DSB report job, run build_dsb_report, save report and update job. Uses own async engine/session."""
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    async_session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    async with async_session_factory() as session:
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
    await engine.dispose()


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
