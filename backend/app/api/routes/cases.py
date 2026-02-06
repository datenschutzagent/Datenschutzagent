"""Case management CRUD API."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import CaseCreate, CaseModel, CaseResponse, CaseUpdate, orm_to_case_response

router = APIRouter()


@router.get("", response_model=list[CaseResponse])
async def list_cases(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """List cases with optional pagination."""
    result = await db.execute(
        select(CaseModel).order_by(CaseModel.updated_at.desc()).offset(skip).limit(limit)
    )
    cases = result.scalars().all()
    return [CaseResponse(**orm_to_case_response(c)) for c in cases]


@router.get("/{case_id}", response_model=CaseResponse)
async def get_case(
    case_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a single case by ID."""
    result = await db.execute(select(CaseModel).where(CaseModel.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return CaseResponse(**orm_to_case_response(case))


@router.post("", response_model=CaseResponse, status_code=201)
async def create_case(
    body: CaseCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new case."""
    case = CaseModel(
        title=body.title,
        department=body.department,
        case_type=body.case_type,
        language=body.language,
        created_by=body.created_by,
        assignee=body.assignee,
        status="intake",
        playbook_version="",
    )
    db.add(case)
    await db.flush()
    await db.refresh(case)
    return CaseResponse(**orm_to_case_response(case))


@router.patch("/{case_id}", response_model=CaseResponse)
async def update_case(
    case_id: UUID,
    body: CaseUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a case (partial update)."""
    result = await db.execute(select(CaseModel).where(CaseModel.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(case, key, value)
    await db.flush()
    await db.refresh(case)
    return CaseResponse(**orm_to_case_response(case))


@router.delete("/{case_id}", status_code=204)
async def delete_case(
    case_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a case and its documents/findings (cascade)."""
    result = await db.execute(select(CaseModel).where(CaseModel.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    await db.delete(case)
    await db.flush()
    return None
