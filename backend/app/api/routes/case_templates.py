"""Vorgangs-Vorlagen API – wiederverwendbare Case-Templates."""
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_roles
from app.core.rate_limit import limiter
from app.database import get_db
from app.models.db import CaseModel, CaseTemplateModel, UserModel
from app.models.schemas import (
    CaseResponse,
    CaseTemplateApplyRequest,
    CaseTemplateCreate,
    CaseTemplateResponse,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("", response_model=list[CaseTemplateResponse], summary="Vorlagen auflisten")
async def list_templates(
    case_type: str | None = Query(default=None),
    department: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _user=require_roles("viewer", "editor", "admin"),
):
    q = select(CaseTemplateModel)
    if case_type:
        q = q.where(CaseTemplateModel.case_type == case_type)
    if department:
        q = q.where(CaseTemplateModel.department.ilike(f"%{department}%"))
    q = q.order_by(CaseTemplateModel.is_builtin.desc(), CaseTemplateModel.name.asc())
    result = await db.execute(q)
    return [CaseTemplateResponse.model_validate(t) for t in result.scalars().all()]


@router.post("", response_model=CaseTemplateResponse, status_code=201, summary="Vorlage erstellen")
@limiter.limit("30/minute")
async def create_template(
    request: Request,
    body: CaseTemplateCreate,
    db: AsyncSession = Depends(get_db),
    user=require_roles("editor", "admin"),
):
    actor = user.display_name if isinstance(user, UserModel) else "System"
    template = CaseTemplateModel(
        name=body.name,
        description=body.description,
        case_type=body.case_type,
        department=body.department,
        language=body.language,
        processing_context=body.processing_context,
        special_category_data=body.special_category_data,
        international_transfer=body.international_transfer,
        created_by=actor,
    )
    db.add(template)
    await db.flush()
    await db.refresh(template)
    return CaseTemplateResponse.model_validate(template)


@router.delete("/{template_id}", status_code=204, summary="Vorlage löschen")
async def delete_template(
    template_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("admin"),
):
    result = await db.execute(select(CaseTemplateModel).where(CaseTemplateModel.id == template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Vorlage nicht gefunden")
    if template.is_builtin:
        raise HTTPException(status_code=403, detail="Eingebaute Vorlagen können nicht gelöscht werden")
    await db.delete(template)
    await db.flush()


@router.post("/apply", response_model=CaseResponse, status_code=201, summary="Vorlage auf neuen Vorgang anwenden")
@limiter.limit("10/minute")
async def apply_template(
    request: Request,
    body: CaseTemplateApplyRequest,
    db: AsyncSession = Depends(get_db),
    user=require_roles("editor", "admin"),
):
    """Erstellt einen neuen Vorgang basierend auf einer Vorlage."""
    result = await db.execute(select(CaseTemplateModel).where(CaseTemplateModel.id == body.template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Vorlage nicht gefunden")

    actor = user.display_name if isinstance(user, UserModel) else "System"
    case = CaseModel(
        title=body.title,
        department=template.department or "",
        case_type=template.case_type,
        language=template.language,
        processing_context=template.processing_context,
        special_category_data=template.special_category_data,
        international_transfer=template.international_transfer,
        created_by=actor,
        assignee=body.assignee,
        deadline=body.deadline,
    )
    db.add(case)
    await db.flush()
    await db.refresh(case)
    return CaseResponse.model_validate(case)
