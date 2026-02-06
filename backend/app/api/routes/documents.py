"""Document upload and management API."""
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import DocumentModel, DocumentResponse, orm_to_document_response
from app.models.db import CaseModel
from app.storage import save_file

router = APIRouter()

ALLOWED_EXTENSIONS = {"docx", "pdf", "xlsx", "doc"}
EXT_TO_FORMAT = {"docx": "docx", "pdf": "pdf", "xlsx": "xlsx", "doc": "doc"}


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    case_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
):
    """List documents, optionally filtered by case_id."""
    q = select(DocumentModel)
    if case_id is not None:
        q = q.where(DocumentModel.case_id == case_id)
    q = q.order_by(DocumentModel.uploaded_at.desc())
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
    case_id: UUID = Form(...),
    file: UploadFile = File(...),
    document_type: str = Form("other"),
    uploaded_by: str = Form(""),
    db: AsyncSession = Depends(get_db),
):
    """Upload a document for a case. document_type: vvt, screening, info_sheet_de, info_sheet_en, dsfa, avv, other."""
    # Ensure case exists
    result = await db.execute(select(CaseModel).where(CaseModel.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    filename = file.filename or "document"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )
    file_format = EXT_TO_FORMAT[ext]

    content = await file.read()
    size_bytes = len(content)

    doc = DocumentModel(
        case_id=case_id,
        name=filename,
        type=document_type,
        version=1,
        format=file_format,
        size_bytes=size_bytes,
        uploaded_by=uploaded_by or "unknown",
        storage_path="",  # set after we have doc.id
    )
    db.add(doc)
    await db.flush()

    storage_path = save_file(case_id, doc.id, filename, content)
    doc.storage_path = storage_path
    await db.flush()
    await db.refresh(doc)

    return DocumentResponse(**orm_to_document_response(doc))
