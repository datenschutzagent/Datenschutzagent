"""Celery app and tasks for async jobs (document extraction, optional run_checks)."""
from uuid import UUID

from celery import Celery
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.models.db import DocumentModel
from app.storage import get_file
from app.services.document_processor import extract_text
from app.services.weaviate_service import index_document_chunks

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


@celery_app.task(name="app.celery_app.extract_document_text", bind=True)
def extract_document_text(self, document_id: str) -> dict:
    """
    Run text extraction for a document and update Document.content.
    Called after upload; document row must exist and storage_path must be set.
    """
    uid = UUID(document_id)
    session: Session = _get_session_factory()()
    try:
        row = session.execute(select(DocumentModel).where(DocumentModel.id == uid)).scalar_one_or_none()
        if not row:
            return {"ok": False, "error": "document_not_found"}
        if not row.storage_path:
            return {"ok": False, "error": "no_storage_path"}
        content_bytes = get_file(row.storage_path)
        result = extract_text(row.name, content_bytes)
        row.content = result.text
        row.extraction_method = result.extraction_method
        session.commit()
        if getattr(settings, "weaviate_indexing_enabled", False) and result.text:
            index_document_chunks(row.id, row.case_id, result.text)
        return {"ok": True, "document_id": document_id}
    except FileNotFoundError:
        return {"ok": False, "error": "file_not_found"}
    except Exception as e:
        session.rollback()
        return {"ok": False, "error": str(e)}
    finally:
        session.close()
