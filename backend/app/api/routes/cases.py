"""Case management CRUD API."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import CaseCreate, CaseModel, CaseResponse, CaseUpdate, orm_to_case_response
from app.models.db import FindingModel, PlaybookModel
from app.models.schemas import RunChecksRequest
from app.services.check_runner import run_check

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


@router.post("/{case_id}/run-checks", response_model=CaseResponse)
async def run_checks(
    case_id: UUID,
    body: RunChecksRequest,
    db: AsyncSession = Depends(get_db),
):
    """Run playbook checks against all case documents and persist findings."""
    result = await db.execute(
        select(CaseModel)
        .where(CaseModel.id == case_id)
        .options(selectinload(CaseModel.documents))
    )
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    pb_result = await db.execute(select(PlaybookModel).where(PlaybookModel.id == body.playbook_id))
    playbook = pb_result.scalar_one_or_none()
    if not playbook:
        raise HTTPException(status_code=404, detail="Playbook not found")

    checks = playbook.content.get("checks") if isinstance(playbook.content, dict) else []
    if not checks:
        await db.refresh(case)
        return CaseResponse(**orm_to_case_response(case))

    for doc in case.documents:
        text = (doc.content or "") or ""
        for item in checks:
            name = item.get("name") or item.get("check_name") or "Check"
            instruction = item.get("instruction") or item.get("requirement") or ""
            if not instruction:
                continue
            try:
                check_result = await run_check(text, instruction)
            except Exception:
                continue
            if not check_result.is_compliant:
                finding = FindingModel(
                    case_id=case_id,
                    document_id=doc.id,
                    check_name=name,
                    severity=check_result.severity,
                    status="open",
                    category=name,
                    description=check_result.description,
                    evidence=check_result.evidence or [],
                    recommendation=check_result.recommendation or "",
                )
                db.add(finding)

    await db.flush()
    # Reload case with documents and findings for response
    result2 = await db.execute(
        select(CaseModel)
        .where(CaseModel.id == case_id)
        .options(selectinload(CaseModel.documents), selectinload(CaseModel.findings))
    )
    case = result2.scalar_one()
    return CaseResponse(**orm_to_case_response(case))
