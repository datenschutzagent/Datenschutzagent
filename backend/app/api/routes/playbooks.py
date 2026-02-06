from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.db import PlaybookModel, orm_to_playbook_response
from app.models.schemas import PlaybookCreate, PlaybookResponse, PlaybookUpdate

router = APIRouter()

@router.get("", response_model=list[PlaybookResponse])
async def list_playbooks(
    db: AsyncSession = Depends(get_db),
):
    """List all playbooks."""
    result = await db.execute(select(PlaybookModel).order_by(PlaybookModel.created_at.desc()))
    playbooks = result.scalars().all()
    return [PlaybookResponse(**orm_to_playbook_response(p)) for p in playbooks]

@router.post("", response_model=PlaybookResponse, status_code=201)
async def create_playbook(
    playbook: PlaybookCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new playbook."""
    db_playbook = PlaybookModel(
        name=playbook.name,
        version=playbook.version,
        content=playbook.content,
        case_type=playbook.case_type,
        department=playbook.department,
    )
    db.add(db_playbook)
    await db.commit()
    await db.refresh(db_playbook)
    return PlaybookResponse(**orm_to_playbook_response(db_playbook))

@router.get("/{playbook_id}", response_model=PlaybookResponse)
async def get_playbook(
    playbook_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a playbook by ID."""
    result = await db.execute(select(PlaybookModel).where(PlaybookModel.id == playbook_id))
    playbook = result.scalar_one_or_none()
    if not playbook:
        raise HTTPException(status_code=404, detail="Playbook not found")
    return PlaybookResponse(**orm_to_playbook_response(playbook))


@router.patch("/{playbook_id}", response_model=PlaybookResponse)
async def update_playbook(
    playbook_id: UUID,
    body: PlaybookUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a playbook (partial)."""
    result = await db.execute(select(PlaybookModel).where(PlaybookModel.id == playbook_id))
    playbook = result.scalar_one_or_none()
    if not playbook:
        raise HTTPException(status_code=404, detail="Playbook not found")
    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(playbook, key, value)
    await db.flush()
    await db.refresh(playbook)
    return PlaybookResponse(**orm_to_playbook_response(playbook))


@router.delete("/{playbook_id}", status_code=204)
async def delete_playbook(
    playbook_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a playbook."""
    result = await db.execute(select(PlaybookModel).where(PlaybookModel.id == playbook_id))
    playbook = result.scalar_one_or_none()
    if not playbook:
        raise HTTPException(status_code=404, detail="Playbook not found")
    await db.delete(playbook)
    await db.flush()
    return None
