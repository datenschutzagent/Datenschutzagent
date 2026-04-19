"""TOM-Katalog API (Art. 32 DSGVO) – Technisch-Organisatorische Maßnahmen."""
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_roles
from app.core.rate_limit import limiter
from app.config import settings
from app.database import get_db
from app.models.db import TOMModel, TOMAttachmentModel
from app.models.schemas import (
    TOMAttachmentResponse,
    TOMCreate,
    TOMListResponse,
    TOMResponse,
    TOMStatsResponse,
    TOMUpdate,
)
from app.storage import save_tom_file, get_tom_file, delete_tom_file

router = APIRouter()
logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {"docx", "pdf", "xlsx", "doc"}
EXT_TO_FORMAT = {"docx": "docx", "pdf": "pdf", "xlsx": "xlsx", "doc": "doc"}
FORMAT_TO_MEDIA_TYPE = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "doc": "application/msword",
}


@router.get("", response_model=TOMListResponse, summary="TOMs auflisten")
async def list_toms(
    category: str | None = Query(default=None),
    implementation_status: str | None = Query(default=None),
    department_code: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=200, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _user=require_roles("viewer", "editor", "admin"),
):
    q = select(TOMModel)
    if category:
        q = q.where(TOMModel.category == category)
    if implementation_status:
        q = q.where(TOMModel.implementation_status == implementation_status)
    if department_code:
        q = q.where(TOMModel.department_codes.contains([department_code]))

    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar_one()

    q = q.order_by(TOMModel.category.asc(), TOMModel.title.asc()).offset(skip).limit(limit)
    result = await db.execute(q)
    items = [TOMResponse.model_validate(r) for r in result.scalars().all()]
    return TOMListResponse(items=items, total=total)


@router.get("/stats", response_model=TOMStatsResponse, summary="TOM-Statistiken")
async def get_tom_stats(
    db: AsyncSession = Depends(get_db),
    _user=require_roles("viewer", "editor", "admin"),
):
    """Gibt Implementierungsrate und Aufschlüsselung nach Status/Kategorie zurück."""
    result = await db.execute(select(TOMModel))
    all_toms = result.scalars().all()

    by_status: dict[str, int] = {}
    by_category: dict[str, int] = {}
    implemented = 0

    for tom in all_toms:
        by_status[tom.implementation_status] = by_status.get(tom.implementation_status, 0) + 1
        by_category[tom.category] = by_category.get(tom.category, 0) + 1
        if tom.implementation_status == "implemented":
            implemented += 1

    relevant = len([t for t in all_toms if t.implementation_status != "not_applicable"])
    rate = (implemented / relevant * 100) if relevant > 0 else 0.0

    return TOMStatsResponse(
        total=len(all_toms),
        by_status=by_status,
        by_category=by_category,
        implementation_rate=round(rate, 1),
    )


@router.post("", response_model=TOMResponse, status_code=201, summary="TOM anlegen")
@limiter.limit("30/minute")
async def create_tom(
    request: Request,
    body: TOMCreate,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("editor", "admin"),
):
    tom = TOMModel(
        title=body.title,
        description=body.description,
        category=body.category,
        implementation_status=body.implementation_status,
        responsible=body.responsible,
        review_date=body.review_date,
        evidence=body.evidence,
        department_codes=body.department_codes,
    )
    db.add(tom)
    await db.flush()
    await db.refresh(tom)
    return TOMResponse.model_validate(tom)


@router.get("/{tom_id}", response_model=TOMResponse, summary="TOM abrufen")
async def get_tom(
    tom_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("viewer", "editor", "admin"),
):
    result = await db.execute(select(TOMModel).where(TOMModel.id == tom_id))
    tom = result.scalar_one_or_none()
    if not tom:
        raise HTTPException(status_code=404, detail="TOM nicht gefunden")
    return TOMResponse.model_validate(tom)


@router.patch("/{tom_id}", response_model=TOMResponse, summary="TOM aktualisieren")
@limiter.limit("60/minute")
async def update_tom(
    request: Request,
    tom_id: UUID,
    body: TOMUpdate,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("editor", "admin"),
):
    result = await db.execute(select(TOMModel).where(TOMModel.id == tom_id))
    tom = result.scalar_one_or_none()
    if not tom:
        raise HTTPException(status_code=404, detail="TOM nicht gefunden")

    for field in ["title", "description", "category", "implementation_status",
                  "responsible", "review_date", "evidence", "department_codes"]:
        val = getattr(body, field, None)
        if val is not None:
            setattr(tom, field, val)

    await db.flush()
    await db.refresh(tom)
    return TOMResponse.model_validate(tom)


@router.delete("/{tom_id}", status_code=204, summary="TOM löschen")
async def delete_tom(
    tom_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("admin"),
):
    result = await db.execute(select(TOMModel).where(TOMModel.id == tom_id))
    tom = result.scalar_one_or_none()
    if not tom:
        raise HTTPException(status_code=404, detail="TOM nicht gefunden")
    await db.delete(tom)
    await db.flush()


# ---------------------------------------------------------------------------
# TOM Attachments
# ---------------------------------------------------------------------------

@router.get("/{tom_id}/attachments", response_model=list[TOMAttachmentResponse], summary="Anhänge auflisten")
async def list_tom_attachments(
    tom_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("viewer", "editor", "admin"),
):
    """List all file attachments for a TOM measure."""
    result = await db.execute(select(TOMModel).where(TOMModel.id == tom_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="TOM nicht gefunden")
    q = (
        select(TOMAttachmentModel)
        .where(TOMAttachmentModel.tom_id == tom_id)
        .order_by(TOMAttachmentModel.uploaded_at.asc())
    )
    rows = (await db.execute(q)).scalars().all()
    return [TOMAttachmentResponse.model_validate(r) for r in rows]


@router.post("/{tom_id}/attachments", response_model=TOMAttachmentResponse, status_code=201, summary="Anhang hochladen")
@limiter.limit("10/minute")
async def upload_tom_attachment(
    request: Request,
    tom_id: UUID,
    file: UploadFile = File(...),
    uploaded_by: str = Form(default=""),
    db: AsyncSession = Depends(get_db),
    _user=require_roles("editor", "admin"),
):
    """Upload a file attachment to a TOM measure. Allowed: PDF, DOCX, XLSX, DOC. Max configured upload size."""
    result = await db.execute(select(TOMModel).where(TOMModel.id == tom_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="TOM nicht gefunden")

    filename = file.filename or "attachment"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Nicht unterstütztes Dateiformat '{filename}'. Erlaubt: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    content = await file.read(settings.max_upload_size_bytes + 1)
    if len(content) > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Datei überschreitet das Maximum von {settings.max_upload_size_bytes // (1024 * 1024)} MB.",
        )

    attachment = TOMAttachmentModel(
        tom_id=tom_id,
        name=filename,
        format=EXT_TO_FORMAT[ext],
        size_bytes=len(content),
        uploaded_by=uploaded_by or "unknown",
        storage_path="",
    )
    db.add(attachment)
    await db.flush()  # populates attachment.id

    storage_path = save_tom_file(tom_id, attachment.id, filename, content)
    attachment.storage_path = storage_path
    await db.flush()
    await db.refresh(attachment)
    return TOMAttachmentResponse.model_validate(attachment)


@router.get("/{tom_id}/attachments/{attachment_id}/download", summary="Anhang herunterladen")
async def download_tom_attachment(
    tom_id: UUID,
    attachment_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("viewer", "editor", "admin"),
):
    """Download a TOM attachment file."""
    result = await db.execute(
        select(TOMAttachmentModel).where(
            TOMAttachmentModel.id == attachment_id,
            TOMAttachmentModel.tom_id == tom_id,
        )
    )
    attachment = result.scalar_one_or_none()
    if not attachment:
        raise HTTPException(status_code=404, detail="Anhang nicht gefunden")
    try:
        content = get_tom_file(attachment.storage_path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")

    from urllib.parse import quote as _quote
    _name = attachment.name or f"attachment.{attachment.format}"
    _name_enc = _quote(_name, safe="")
    _name_ascii = _name.encode("ascii", errors="replace").decode().replace('"', "_")
    media_type = FORMAT_TO_MEDIA_TYPE.get(attachment.format, "application/octet-stream")
    return StreamingResponse(
        iter([content]),
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{_name_ascii}"; filename*=UTF-8\'\'{_name_enc}',
            "Content-Length": str(len(content)),
        },
    )


@router.delete("/{tom_id}/attachments/{attachment_id}", status_code=204, summary="Anhang löschen")
async def delete_tom_attachment(
    tom_id: UUID,
    attachment_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("editor", "admin"),
):
    """Delete a TOM attachment (file + DB record)."""
    result = await db.execute(
        select(TOMAttachmentModel).where(
            TOMAttachmentModel.id == attachment_id,
            TOMAttachmentModel.tom_id == tom_id,
        )
    )
    attachment = result.scalar_one_or_none()
    if not attachment:
        raise HTTPException(status_code=404, detail="Anhang nicht gefunden")

    storage_path = attachment.storage_path
    await db.delete(attachment)
    await db.flush()

    try:
        delete_tom_file(storage_path)
    except Exception:
        logger.warning("Could not delete TOM attachment file: %s", storage_path)
