"""CRUD API for legal bases (Rechtsgrundlagen). Indexing to Weaviate on create/update, chunk deletion on delete."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_roles
from app.database import get_db
from app.models.db import LegalBaseModel, orm_to_legal_base_response
from app.models.schemas import (
    ApplicabilityEnum,
    LegalBaseCreate,
    LegalBaseResponse,
    LegalBaseUpdate,
)
from app.services.weaviate_service import delete_legal_base_chunks, index_legal_base

router = APIRouter()


@router.get("", response_model=list[LegalBaseResponse], summary="Rechtsgrundlagen auflisten")
async def list_legal_bases(
    db: AsyncSession = Depends(get_db),
    applicability: ApplicabilityEnum | None = Query(None, description="Filter by applicability"),
    skip: int = Query(default=0, ge=0, description="Anzahl übersprungener Einträge (Pagination)"),
    limit: int = Query(default=500, ge=1, le=1000, description="Maximale Anzahl zurückgegebener Einträge"),
):
    """List legal bases with optional filtering by applicability and pagination."""
    q = select(LegalBaseModel).order_by(LegalBaseModel.title)
    if applicability is not None:
        q = q.where(LegalBaseModel.applicability == applicability)
    q = q.offset(skip).limit(limit)
    result = await db.execute(q)
    bases = result.scalars().all()
    return [LegalBaseResponse(**orm_to_legal_base_response(b)) for b in bases]


@router.post("", response_model=LegalBaseResponse, status_code=201)
async def create_legal_base(
    body: LegalBaseCreate,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("editor", "admin"),
):
    """Create a new legal base. Content is indexed in Weaviate for RAG when indexing is enabled."""
    model = LegalBaseModel(
        title=body.title,
        short_name=body.short_name,
        content=body.content,
        applicability=body.applicability,
        department_codes=body.department_codes,
        case_types=body.case_types,
        internal_only=body.internal_only,
    )
    db.add(model)
    await db.commit()
    await db.refresh(model)
    index_legal_base(model.id, model.title, model.content or "")
    return LegalBaseResponse(**orm_to_legal_base_response(model))


@router.get("/{legal_base_id}", response_model=LegalBaseResponse)
async def get_legal_base(
    legal_base_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a legal base by ID."""
    result = await db.execute(select(LegalBaseModel).where(LegalBaseModel.id == legal_base_id))
    base = result.scalar_one_or_none()
    if not base:
        raise HTTPException(status_code=404, detail="Legal base not found")
    return LegalBaseResponse(**orm_to_legal_base_response(base))


@router.patch("/{legal_base_id}", response_model=LegalBaseResponse)
async def update_legal_base(
    legal_base_id: UUID,
    body: LegalBaseUpdate,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("editor", "admin"),
):
    """Update a legal base. Weaviate chunks are re-indexed when content or title change."""
    result = await db.execute(select(LegalBaseModel).where(LegalBaseModel.id == legal_base_id))
    base = result.scalar_one_or_none()
    if not base:
        raise HTTPException(status_code=404, detail="Legal base not found")
    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(base, key, value)
    await db.commit()
    await db.refresh(base)
    index_legal_base(base.id, base.title, base.content or "")
    return LegalBaseResponse(**orm_to_legal_base_response(base))


@router.delete("/{legal_base_id}", status_code=204)
async def delete_legal_base(
    legal_base_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("editor", "admin"),
):
    """Delete a legal base. Weaviate chunks for this base are removed."""
    result = await db.execute(select(LegalBaseModel).where(LegalBaseModel.id == legal_base_id))
    base = result.scalar_one_or_none()
    if not base:
        raise HTTPException(status_code=404, detail="Legal base not found")
    await db.delete(base)
    await db.commit()
    delete_legal_base_chunks(legal_base_id)
    return None
