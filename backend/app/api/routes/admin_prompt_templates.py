"""Admin API: versioned prompt templates (admin role required)."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_roles
from app.core.rate_limit import limiter
from app.database import get_db
from app.models.db import PromptTemplateModel
from app.models.schemas import (
    PromptTemplateCreate,
    PromptTemplateKeyMeta,
    PromptTemplateResponse,
    PromptTemplateUpdate,
)
from app.services.prompt_template_service import (
    PROMPT_TEMPLATE_KEY_META,
    VALID_PROMPT_KEYS,
    invalidate_cache,
)

router = APIRouter()


@router.get("/keys", response_model=list[PromptTemplateKeyMeta])
def get_prompt_template_keys(_user=require_roles("admin")):
    """Return metadata for all prompt template keys (description, placeholders)."""
    return [PromptTemplateKeyMeta(**m) for m in PROMPT_TEMPLATE_KEY_META]


@router.get("/versions", response_model=list[PromptTemplateResponse])
async def list_prompt_template_versions(
    key: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
    _user=require_roles("admin"),
):
    """List all versions for a given key, newest first."""
    if key not in VALID_PROMPT_KEYS:
        raise HTTPException(status_code=400, detail="Invalid prompt template key")
    result = await db.execute(
        select(PromptTemplateModel)
        .where(PromptTemplateModel.key == key)
        .order_by(PromptTemplateModel.created_at.desc())
    )
    items = result.scalars().all()
    return [PromptTemplateResponse.model_validate(t) for t in items]


@router.get("", response_model=list[PromptTemplateResponse])
async def list_prompt_templates(
    key: str | None = Query(default=None, min_length=1),
    db: AsyncSession = Depends(get_db),
    _user=require_roles("admin"),
):
    """List active prompt templates. Optionally filter by key."""
    q = select(PromptTemplateModel).where(PromptTemplateModel.is_active.is_(True))
    if key is not None:
        if key not in VALID_PROMPT_KEYS:
            raise HTTPException(status_code=400, detail="Invalid prompt template key")
        q = q.where(PromptTemplateModel.key == key)
    result = await db.execute(q)
    items = result.scalars().all()
    return [PromptTemplateResponse.model_validate(t) for t in items]


@router.post("", response_model=PromptTemplateResponse, status_code=201)
@limiter.limit("30/minute")
async def create_prompt_template(
    request: Request,
    body: PromptTemplateCreate,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("admin"),
):
    """Create a new version. If set_active is true, this version becomes active for the key."""
    if body.key not in VALID_PROMPT_KEYS:
        raise HTTPException(status_code=400, detail="Invalid prompt template key")
    version = body.version
    if not version:
        from datetime import datetime
        result = await db.execute(
            select(PromptTemplateModel.version)
            .where(PromptTemplateModel.key == body.key)
            .order_by(PromptTemplateModel.created_at.desc())
            .limit(1)
        )
        last = result.scalar_one_or_none()
        if last is None:
            version = "1.0"
        else:
            try:
                major, _, minor = last.partition(".")
                version = f"{major}.{int(minor or 0) + 1}"
            except Exception:
                version = f"v-{datetime.utcnow().strftime('%Y%m%d-%H%M')}"
    else:
        existing = await db.execute(
            select(PromptTemplateModel.id).where(
                PromptTemplateModel.key == body.key,
                PromptTemplateModel.version == version,
            ).limit(1)
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(status_code=409, detail="This key and version already exist")
    if body.set_active:
        result = await db.execute(select(PromptTemplateModel).where(PromptTemplateModel.key == body.key))
        for row in result.scalars().all():
            row.is_active = False
    template = PromptTemplateModel(
        key=body.key,
        version=version,
        content=body.content,
        is_active=body.set_active,
    )
    db.add(template)
    await db.flush()
    await db.refresh(template)
    invalidate_cache(body.key)
    return PromptTemplateResponse.model_validate(template)


@router.patch("/{template_id}", response_model=PromptTemplateResponse)
@limiter.limit("60/minute")
async def update_prompt_template(
  request: Request,
  template_id: UUID,
  body: PromptTemplateUpdate,
  db: AsyncSession = Depends(get_db),
  _user=require_roles("admin"),
):
    """Update a template (e.g. set is_active to true to activate this version)."""
    result = await db.execute(select(PromptTemplateModel).where(PromptTemplateModel.id == template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Prompt template not found")
    if body.is_active is True:
        for row in (await db.execute(select(PromptTemplateModel).where(PromptTemplateModel.key == template.key))).scalars().all():
            row.is_active = row.id == template_id
        template.is_active = True
        invalidate_cache(template.key)
    return PromptTemplateResponse.model_validate(template)
