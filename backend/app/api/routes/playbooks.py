from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.auth import require_roles
from app.database import get_db
from app.models.db import CaseModel, DocumentModel, PlaybookModel, orm_to_playbook_response
from app.models.schemas import (
    PlaybookCoverageItem,
    PlaybookCoverageResponse,
    PlaybookCreate,
    PlaybookMatchResult,
    PlaybookResponse,
    PlaybookUpdate,
)
from app.services.playbook_matching import rank_playbooks_for_selection

router = APIRouter()


@router.get("/for-selection", response_model=list[PlaybookMatchResult])
async def list_playbooks_for_selection(
    department: str = Query(..., min_length=1, description="Case department value (e.g. from GET /departments)."),
    processing_context: str | None = Query(None, description="Optional processing_context from case."),
    case_type: str | None = Query(None),
    strict_case_type: bool = Query(
        False,
        description="If true, playbooks with non-empty match.case_types must match case_type.",
    ),
    db: AsyncSession = Depends(get_db),
):
    """Playbooks that match the given attributes, highest match_priority first (for wizard and run-checks UI)."""
    result = await db.execute(select(PlaybookModel))
    pbs = list(result.scalars().all())
    ranked = rank_playbooks_for_selection(
        pbs,
        department=department,
        processing_context=processing_context,
        case_type=case_type,
        org_profile=(settings.org_profile or "default").strip() or "default",
        strict_case_type=strict_case_type,
    )
    return [
        PlaybookMatchResult(
            playbook=PlaybookResponse(**orm_to_playbook_response(pb)),
            match_priority=pri,
        )
        for pb, pri in ranked
    ]


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
    _user=require_roles("editor", "admin"),
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
    _user=require_roles("editor", "admin"),
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
    _user=require_roles("editor", "admin"),
):
    """Delete a playbook."""
    result = await db.execute(select(PlaybookModel).where(PlaybookModel.id == playbook_id))
    playbook = result.scalar_one_or_none()
    if not playbook:
        raise HTTPException(status_code=404, detail="Playbook not found")
    await db.delete(playbook)
    await db.flush()
    return None


@router.get("/{playbook_id}/coverage-preview", response_model=PlaybookCoverageResponse)
async def get_playbook_coverage_preview(
    playbook_id: UUID,
    case_id: UUID = Query(..., description="Case ID to check document availability against."),
    db: AsyncSession = Depends(get_db),
):
    """Preview which checks of the playbook will apply to the given case's documents.

    Returns a per-check breakdown (applicable / not applicable + reason) and a list of
    document types that are missing but required by at least one check.
    """
    pb_result = await db.execute(select(PlaybookModel).where(PlaybookModel.id == playbook_id))
    playbook = pb_result.scalar_one_or_none()
    if not playbook:
        raise HTTPException(status_code=404, detail="Playbook not found")

    case_result = await db.execute(
        select(CaseModel)
        .where(CaseModel.id == case_id)
        .options(selectinload(CaseModel.documents))
    )
    case = case_result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    present_doc_types = {d.type for d in case.documents}
    raw_checks = playbook.content.get("checks", []) if isinstance(playbook.content, dict) else []

    items: list[PlaybookCoverageItem] = []
    missing_doc_types: set[str] = set()

    for check in raw_checks:
        name = check.get("name", "")
        category = check.get("category", "")
        scope = check.get("scope", "document")
        required_types: list[str] = check.get("document_types", [])

        if scope == "case" or not required_types:
            applicable = True
            reason = "Vorgangsbezogen" if scope == "case" else "Gilt für alle Dokumente"
        else:
            applicable = any(t in present_doc_types for t in required_types)
            if applicable:
                reason = f"Passende Dokumente vorhanden: {', '.join(required_types)}"
            else:
                missing = [t for t in required_types if t not in present_doc_types]
                missing_doc_types.update(missing)
                reason = f"Fehlende Dokumenttypen: {', '.join(missing)}"

        items.append(PlaybookCoverageItem(
            name=name,
            category=category,
            scope=scope,
            applicable=applicable,
            reason=reason,
        ))

    applicable_count = sum(1 for i in items if i.applicable)
    return PlaybookCoverageResponse(
        playbook_id=playbook_id,
        case_id=case_id,
        total_checks=len(items),
        applicable_count=applicable_count,
        checks=items,
        missing_document_types=sorted(missing_doc_types),
    )
