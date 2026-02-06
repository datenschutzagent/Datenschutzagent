"""Document upload and management API."""
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import func, select

from app.core.auth import require_roles
from sqlalchemy.ext.asyncio import AsyncSession

from app.celery_app import extract_document_text
from app.config import settings
from app.database import get_db
from app.models import DocumentModel, DocumentResponse, orm_to_document_response
from app.models.db import CaseModel
from app.services.document_processor import extract_text
from app.services.weaviate_service import delete_chunks_by_document_id
from app.storage import save_file, delete_file

router = APIRouter()

ALLOWED_EXTENSIONS = {"docx", "pdf", "xlsx", "doc"}
EXT_TO_FORMAT = {"docx": "docx", "pdf": "pdf", "xlsx": "xlsx", "doc": "doc"}


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
    content = await file.read()
    size_bytes = len(content)
    if async_extraction:
        text_content = None
        extraction_method = None
    else:
        ext_result = extract_text(filename, content)
        text_content = ext_result.text
        extraction_method = ext_result.extraction_method
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
    return [DocumentResponse(**orm_to_document_response(d)) for d in docs]


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a single document by ID."""
    result = await db.execute(select(DocumentModel).where(DocumentModel.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentResponse(**orm_to_document_response(doc))


@router.post("", response_model=DocumentResponse, status_code=201)
async def upload_document(
    _user=Depends(require_roles("editor", "admin")),
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
    if use_async:
        await db.commit()
        extract_document_text.delay(str(doc.id))
    return DocumentResponse(**orm_to_document_response(doc))


@router.post("/bulk", response_model=list[DocumentResponse], status_code=201)
async def upload_documents_bulk(
    case_id: UUID = Form(...),
    files: list[UploadFile] = File(...),
    document_type: str = Form("other"),
    uploaded_by: str = Form(""),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_roles("editor", "admin")),
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
            created.append(DocumentResponse(**orm_to_document_response(doc)))
            if use_async:
                doc_ids.append(doc.id)
        except HTTPException as e:
            errors.append(f"{f.filename or 'file'}: {e.detail}")
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
    _user=Depends(require_roles("editor", "admin")),
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
    return None
