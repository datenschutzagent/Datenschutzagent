from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.auth import require_roles
from app.core.rate_limit import limiter
from app.database import get_db
from app.models.db import (
    CaseModel,
    DocumentModel,
    PlaybookModel,
    PlaybookRevisionModel,
    UserModel,
)
from app.models.schemas import (
    PlaybookCoverageItem,
    PlaybookCoverageResponse,
    PlaybookCreate,
    PlaybookMatchResult,
    PlaybookResponse,
    PlaybookRevisionResponse,
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
            playbook=PlaybookResponse.model_validate(pb),
            match_priority=pri,
        )
        for pb, pri in ranked
    ]


@router.get("", response_model=list[PlaybookResponse], summary="Playbooks auflisten")
async def list_playbooks(
    skip: int = Query(default=0, ge=0, description="Anzahl übersprungener Einträge (Pagination)"),
    limit: int = Query(default=200, ge=1, le=500, description="Maximale Anzahl zurückgegebener Einträge"),
    is_active: bool | None = Query(default=None, description="Filtert nach Aktiv-Status (true/false)"),
    db: AsyncSession = Depends(get_db),
):
    """List playbooks with optional filtering by active state and pagination."""
    q = select(PlaybookModel).order_by(PlaybookModel.created_at.desc())
    if is_active is not None:
        q = q.where(PlaybookModel.is_active == is_active)
    q = q.offset(skip).limit(limit)
    result = await db.execute(q)
    playbooks = result.scalars().all()
    return [PlaybookResponse.model_validate(p) for p in playbooks]

@router.post("", response_model=PlaybookResponse, status_code=201)
@limiter.limit("20/minute")
async def create_playbook(
    request: Request,
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
    return PlaybookResponse.model_validate(db_playbook)

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
    return PlaybookResponse.model_validate(playbook)


@router.patch("/{playbook_id}", response_model=PlaybookResponse)
async def update_playbook(
    playbook_id: UUID,
    body: PlaybookUpdate,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("editor", "admin"),
):
    """Update a playbook (partial). Saves a revision snapshot before applying changes."""
    result = await db.execute(select(PlaybookModel).where(PlaybookModel.id == playbook_id))
    playbook = result.scalar_one_or_none()
    if not playbook:
        raise HTTPException(status_code=404, detail="Playbook not found")

    # Snapshot current state as a revision before overwriting
    changed_by = _user.display_name if isinstance(_user, UserModel) else "System"
    revision = PlaybookRevisionModel(
        playbook_id=playbook.id,
        version=playbook.version,
        content=playbook.content,
        changed_by=changed_by,
    )
    db.add(revision)

    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(playbook, key, value)
    await db.flush()
    await db.refresh(playbook)
    return PlaybookResponse.model_validate(playbook)


@router.get("/{playbook_id}/revisions")
async def list_playbook_revisions(
    playbook_id: UUID,
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _user=require_roles("viewer", "editor", "admin"),
):
    """List version history snapshots for a playbook (newest first)."""
    pb_result = await db.execute(select(PlaybookModel).where(PlaybookModel.id == playbook_id))
    if not pb_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Playbook not found")

    rev_result = await db.execute(
        select(PlaybookRevisionModel)
        .where(PlaybookRevisionModel.playbook_id == playbook_id)
        .order_by(PlaybookRevisionModel.created_at.desc())
        .limit(limit)
    )
    revisions = rev_result.scalars().all()
    return [PlaybookRevisionResponse.model_validate(r) for r in revisions]


@router.post("/{playbook_id}/revisions/{revision_id}/restore", response_model=PlaybookResponse)
async def restore_playbook_revision(
    playbook_id: UUID,
    revision_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("editor", "admin"),
):
    """Restore a playbook to a previous revision snapshot."""
    pb_result = await db.execute(select(PlaybookModel).where(PlaybookModel.id == playbook_id))
    playbook = pb_result.scalar_one_or_none()
    if not playbook:
        raise HTTPException(status_code=404, detail="Playbook not found")

    rev_result = await db.execute(
        select(PlaybookRevisionModel).where(
            PlaybookRevisionModel.id == revision_id,
            PlaybookRevisionModel.playbook_id == playbook_id,
        )
    )
    revision = rev_result.scalar_one_or_none()
    if not revision:
        raise HTTPException(status_code=404, detail="Revision not found")

    # Save current state as a new revision before restoring
    changed_by = _user.display_name if isinstance(_user, UserModel) else "System"
    snapshot = PlaybookRevisionModel(
        playbook_id=playbook.id,
        version=playbook.version,
        content=playbook.content,
        changed_by=f"{changed_by} (vor Wiederherstellung)",
    )
    db.add(snapshot)

    playbook.version = revision.version
    playbook.content = revision.content
    await db.flush()
    await db.refresh(playbook)
    return PlaybookResponse.model_validate(playbook)


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
