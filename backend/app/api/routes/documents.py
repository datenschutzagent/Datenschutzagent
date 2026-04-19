"""Document upload and management API."""
import asyncio
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

logger = logging.getLogger(__name__)
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_roles
from app.core.rate_limit import limiter
from app.models.db import UserModel
from app.celery_app import extract_document_text
from app.config import settings
from app.database import get_db
from app.models import DocumentModel, DocumentResponse
from app.models.db import CaseModel, DocumentCommentModel, UserModel
from app.models.schemas import DocumentCommentCreate, DocumentCommentResponse, DocumentUpdate
from app.services.document_processor import extract_text
from app.services.weaviate_service import delete_chunks_by_document_id
from app.storage import save_file, delete_file, get_file

router = APIRouter()

ALLOWED_EXTENSIONS = {"docx", "pdf", "xlsx", "doc"}
EXT_TO_FORMAT = {"docx": "docx", "pdf": "pdf", "xlsx": "xlsx", "doc": "doc"}
FORMAT_TO_MEDIA_TYPE = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "doc": "application/msword",
}


async def _next_version_for_type(
    db: AsyncSession,
    case_id: UUID,
    document_type: str,
) -> int:
    """Return the next version number for (case_id, document_type). Version is 1-based per document type."""
    q = select(func.coalesce(func.max(DocumentModel.version), 0)).where(
        DocumentModel.case_id == case_id,
        DocumentModel.type == document_type,
    )
    result = await db.execute(q)
    max_version = result.scalar() or 0
    return max_version + 1


async def _process_one_upload(
    *,
    case_id: UUID,
    file: UploadFile,
    document_type: str,
    uploaded_by: str,
    db: AsyncSession,
    async_extraction: bool = True,
) -> DocumentModel:
    """Validate, store and optionally extract text. If async_extraction=True (default), content is set in a Celery task; otherwise inline.
    Returns created DocumentModel. Caller must ensure case exists. Version is auto-assigned per (case_id, document_type)."""
    filename = file.filename or "document"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format for '{filename}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )
    file_format = EXT_TO_FORMAT[ext]
    content = await file.read(settings.max_upload_size_bytes + 1)
    if len(content) > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Datei '{filename}' überschreitet das erlaubte Maximum von {settings.max_upload_size_bytes // (1024 * 1024)} MB.",
        )
    size_bytes = len(content)
    if async_extraction:
        text_content = None
        extraction_method = None
        extraction_status = "pending"
        extraction_error = None
    else:
        ext_result = extract_text(filename, content)
        text_content = ext_result.text
        extraction_method = ext_result.extraction_method
        extraction_status = "done"
        extraction_error = None
    version = await _next_version_for_type(db, case_id, document_type)
    doc = DocumentModel(
        case_id=case_id,
        name=filename,
        type=document_type,
        version=version,
        format=file_format,
        size_bytes=size_bytes,
        uploaded_by=uploaded_by or "unknown",
        storage_path="",
        content=text_content,
        extraction_method=extraction_method,
        extraction_status=extraction_status,
        extraction_error=extraction_error,
    )
    db.add(doc)
    await db.flush()
    storage_path = save_file(case_id, doc.id, filename, content)
    doc.storage_path = storage_path
    await db.flush()
    await db.refresh(doc)
    return doc


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    case_id: UUID | None = None,
    document_type: str | None = None,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("viewer", "editor", "admin"),
):
    """List documents, optionally filtered by case_id and/or document_type. Ordered by type, then version (asc)."""
    q = select(DocumentModel)
    if case_id is not None:
        q = q.where(DocumentModel.case_id == case_id)
    if document_type is not None:
        q = q.where(DocumentModel.type == document_type)
    q = q.order_by(DocumentModel.type.asc(), DocumentModel.version.asc())
    result = await db.execute(q)
    docs = result.scalars().all()
    return [DocumentResponse.model_validate(d) for d in docs]


@router.get("/{document_id}/download")
async def download_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("viewer", "editor", "admin"),
):
    """Download the original document file. Access requires authentication (same as listing documents)."""
    result = await db.execute(select(DocumentModel).where(DocumentModel.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if not doc.storage_path:
        raise HTTPException(status_code=404, detail="File not found")
    try:
        content = get_file(doc.storage_path)
    except FileNotFoundError:
        logger.warning(
            "Document file missing from storage",
            extra={"document_id": str(document_id), "storage_path": doc.storage_path},
        )
        raise HTTPException(status_code=404, detail="File not found")
    media_type = FORMAT_TO_MEDIA_TYPE.get(doc.format, "application/octet-stream")
    filename = doc.name or f"document.{doc.format}"
    # RFC 5987 encoding prevents header injection from filenames containing quotes or non-ASCII
    from urllib.parse import quote
    filename_encoded = quote(filename, safe="")
    ascii_fallback = filename.encode("ascii", errors="replace").decode().replace('"', "_")
    content_disposition = f'attachment; filename="{ascii_fallback}"; filename*=UTF-8\'\'{filename_encoded}'
    return StreamingResponse(
        iter([content]),
        media_type=media_type,
        headers={
            "Content-Disposition": content_disposition,
            "Content-Length": str(len(content)),
        },
    )


@router.get("/{document_id}/content")
async def get_document_content(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("viewer", "editor", "admin"),
):
    """Get the extracted text content of a document (for in-app display). Includes extraction_status and extraction_error for UI state."""
    result = await db.execute(select(DocumentModel).where(DocumentModel.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return {
        "content": doc.content or "",
        "extraction_status": doc.extraction_status,
        "extraction_error": doc.extraction_error,
    }


@router.get("/{document_id}/comments", response_model=list[DocumentCommentResponse])
async def list_document_comments(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("viewer", "editor", "admin"),
):
    """List comments for a document, sorted by created_at ascending."""
    result = await db.execute(select(DocumentModel).where(DocumentModel.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    q = (
        select(DocumentCommentModel)
        .where(DocumentCommentModel.document_id == document_id)
        .order_by(DocumentCommentModel.created_at.asc())
    )
    comments_result = await db.execute(q)
    comments = comments_result.scalars().all()
    return [DocumentCommentResponse.model_validate(c) for c in comments]


@router.post("/{document_id}/comments", response_model=DocumentCommentResponse, status_code=201)
@limiter.limit("30/minute")
async def create_document_comment(
    request: Request,
    document_id: UUID,
    body: DocumentCommentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = require_roles("editor", "admin"),
):
    """Add a comment to a document. Author is taken from current user."""
    result = await db.execute(select(DocumentModel).where(DocumentModel.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    author = (current_user.display_name or "").strip() or "Unbekannt"
    comment = DocumentCommentModel(
        document_id=document_id,
        case_id=doc.case_id,
        author=author,
        user_id=current_user.id,
        text=body.text,
    )
    db.add(comment)
    await db.flush()
    await db.refresh(comment)
    return DocumentCommentResponse.model_validate(comment)


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("viewer", "editor", "admin"),
):
    """Get a single document by ID."""
    result = await db.execute(select(DocumentModel).where(DocumentModel.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentResponse.model_validate(doc)


@router.patch("/{document_id}", response_model=DocumentResponse)
@limiter.limit("60/minute")
async def update_document(
    request: Request,
    document_id: UUID,
    body: DocumentUpdate,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("editor", "admin"),
):
    """Update document metadata or extracted content. When content is updated, Weaviate chunks for this document are removed (RAG will use new content after re-indexing)."""
    result = await db.execute(select(DocumentModel).where(DocumentModel.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if body.content is not None:
        doc.content = body.content
        await db.flush()
        await db.refresh(doc)
        delete_chunks_by_document_id(document_id)
    await db.commit()
    return DocumentResponse.model_validate(doc)


@router.post("", response_model=DocumentResponse, status_code=201, summary="Dokument hochladen")
@limiter.limit("30/minute")
async def upload_document(
    request: Request,
    _user=require_roles("editor", "admin"),
    case_id: UUID = Form(...),
    file: UploadFile = File(...),
    document_type: str = Form("other"),
    uploaded_by: str = Form(""),
    db: AsyncSession = Depends(get_db),
):
    """Upload a single document for a case. Text extraction runs asynchronously (Celery). document_type: vvt, screening, info_sheet_de, info_sheet_en, dsfa, avv, other."""
    result = await db.execute(select(CaseModel).where(CaseModel.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    use_async = settings.celery_enabled and bool((settings.celery_broker_url or "").strip())
    doc = await _process_one_upload(
        case_id=case_id, file=file, document_type=document_type, uploaded_by=uploaded_by, db=db, async_extraction=use_async
    )
    logger.info(
        "Document uploaded",
        extra={
            "case_id": str(case_id),
            "document_id": str(doc.id),
            "format": doc.format,
            "size_bytes": doc.size_bytes,
            "async_extraction": use_async,
        },
    )
    if use_async:
        await db.commit()
        extract_document_text.delay(str(doc.id))
    return DocumentResponse.model_validate(doc)


@router.post("/bulk", response_model=list[DocumentResponse], status_code=201)
@limiter.limit("10/minute")
async def upload_documents_bulk(
    request: Request,
    case_id: UUID = Form(...),
    files: list[UploadFile] = File(...),
    document_type: str = Form("other"),
    uploaded_by: str = Form(""),
    db: AsyncSession = Depends(get_db),
    _user=require_roles("editor", "admin"),
):
    """Upload multiple documents for a case in one request. Text extraction runs asynchronously (Celery). Same document_type and uploaded_by apply to all."""
    if not files:
        raise HTTPException(status_code=400, detail="At least one file is required")
    result = await db.execute(select(CaseModel).where(CaseModel.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    use_async = settings.celery_enabled and bool((settings.celery_broker_url or "").strip())
    created: list[DocumentResponse] = []
    doc_ids: list[UUID] = []
    errors: list[str] = []
    for f in files:
        try:
            doc = await _process_one_upload(
                case_id=case_id, file=f, document_type=document_type, uploaded_by=uploaded_by, db=db, async_extraction=use_async
            )
            created.append(DocumentResponse.model_validate(doc))
            if use_async:
                doc_ids.append(doc.id)
        except HTTPException as e:
            errors.append(f"{f.filename or 'file'}: {e.detail}")
    if errors:
        logger.warning(
            "Bulk upload partial or full failure",
            extra={"case_id": str(case_id), "errors": errors, "created_count": len(created)},
        )
    if errors and not created:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    if use_async and doc_ids:
        await db.commit()
        for did in doc_ids:
            extract_document_text.delay(str(did))
    return created


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("editor", "admin"),
):
    """Delete a document (DB record and storage file)."""
    result = await db.execute(select(DocumentModel).where(DocumentModel.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    storage_path = doc.storage_path
    delete_chunks_by_document_id(document_id)
    await db.delete(doc)
    await db.flush()
    if storage_path:
        try:
            delete_file(storage_path)
        except FileNotFoundError:
            pass
    logger.info("Document deleted", extra={"document_id": str(document_id), "case_id": str(doc.case_id)})
    return None
