"""Datenschutzerklärung-Generator API (Art. 13/14 DSGVO)."""
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_roles
from app.database import get_db
from app.models.db import PrivacyPolicyModel

router = APIRouter()
logger = logging.getLogger(__name__)


class PrivacyPolicyGenerateRequest(BaseModel):
    org_name: str = ""
    department: str = ""
    contact: str = ""
    notes: str = ""


class PrivacyPolicyResponse(BaseModel):
    id: UUID
    title: str
    content_markdown: str
    version_note: str | None
    org_name: str | None
    department: str | None
    generated_at: str
    created_by: str


def _orm_to_response(p: PrivacyPolicyModel) -> PrivacyPolicyResponse:
    return PrivacyPolicyResponse(
        id=p.id,
        title=p.title,
        content_markdown=p.content_markdown,
        version_note=p.version_note,
        org_name=p.org_name,
        department=p.department,
        generated_at=p.generated_at.isoformat(),
        created_by=p.created_by,
    )


@router.get("", summary="Datenschutzerklärungen auflisten")
async def list_privacy_policies(
    db: AsyncSession = Depends(get_db),
    _user=require_roles("viewer", "editor", "admin"),
) -> list[PrivacyPolicyResponse]:
    """Gibt alle gespeicherten Datenschutzerklärungen zurück."""
    from app.services.privacy_policy_service import list_privacy_policies as _list
    items = await _list(db)
    return [_orm_to_response(p) for p in items]


@router.post("/generate", summary="Datenschutzerklärung generieren", status_code=201)
async def generate_privacy_policy(
    body: PrivacyPolicyGenerateRequest,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("editor", "admin"),
) -> PrivacyPolicyResponse:
    """Generiert eine neue Datenschutzerklärung auf Basis der VVT-Daten und des Org-Profils.

    Nutzt das aktive LLM (konfigurierbar via LLM_PROVIDER). Die Erklärung wird gespeichert
    und kann anschließend bearbeitet und exportiert werden.
    """
    from app.services.privacy_policy_service import generate_privacy_policy as _gen, save_privacy_policy

    try:
        payload = await _gen(
            db=db,
            org_name=body.org_name,
            department=body.department,
            contact=body.contact,
            notes=body.notes,
        )
    except Exception as exc:
        logger.error("Privacy policy generation failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Generierung fehlgeschlagen: {exc}")

    creator = getattr(_user, "display_name", "") if _user else ""
    policy = await save_privacy_policy(db, payload, created_by=creator)
    return _orm_to_response(policy)


@router.get("/{policy_id}", summary="Datenschutzerklärung abrufen")
async def get_privacy_policy(
    policy_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("viewer", "editor", "admin"),
) -> PrivacyPolicyResponse:
    result = await db.execute(select(PrivacyPolicyModel).where(PrivacyPolicyModel.id == policy_id))
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="Datenschutzerklärung nicht gefunden")
    return _orm_to_response(policy)


class PrivacyPolicyUpdate(BaseModel):
    title: str | None = None
    content_markdown: str | None = None
    version_note: str | None = None


@router.patch("/{policy_id}", summary="Datenschutzerklärung bearbeiten")
async def update_privacy_policy(
    policy_id: UUID,
    body: PrivacyPolicyUpdate,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("editor", "admin"),
) -> PrivacyPolicyResponse:
    result = await db.execute(select(PrivacyPolicyModel).where(PrivacyPolicyModel.id == policy_id))
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="Datenschutzerklärung nicht gefunden")
    if body.title is not None:
        policy.title = body.title
    if body.content_markdown is not None:
        policy.content_markdown = body.content_markdown
    if body.version_note is not None:
        policy.version_note = body.version_note
    await db.flush()
    await db.refresh(policy)
    return _orm_to_response(policy)


@router.delete("/{policy_id}", status_code=204, summary="Datenschutzerklärung löschen")
async def delete_privacy_policy(
    policy_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("admin"),
):
    result = await db.execute(select(PrivacyPolicyModel).where(PrivacyPolicyModel.id == policy_id))
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="Datenschutzerklärung nicht gefunden")
    await db.delete(policy)
    await db.flush()
