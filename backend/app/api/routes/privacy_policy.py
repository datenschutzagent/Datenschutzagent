"""Datenschutzerklaerung-API (Art. 13/14 DSGVO).

Eine Datenschutzerklaerung gehoert zu einem Case (Vorgang). Endpunkte:

- GET    /cases/{case_id}/privacy-policies        Versionen fuer einen Case
- POST   /cases/{case_id}/privacy-policies/generate  Neue Version generieren
- GET    /privacy-policies                        Globale Uebersicht (read-only)
- GET    /privacy-policies/{policy_id}            Einzelne Erklaerung
- PATCH  /privacy-policies/{policy_id}            Inhalt/Titel bearbeiten
- DELETE /privacy-policies/{policy_id}            Loeschen (admin)
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_roles
from app.core.rate_limit import limiter
from app.database import get_db
from app.models.db import CaseModel, PrivacyPolicyModel

router = APIRouter()
case_scoped_router = APIRouter()
logger = logging.getLogger(__name__)


class PrivacyPolicyGenerateRequest(BaseModel):
    contact: str = ""
    notes: str = ""


class PrivacyPolicyResponse(BaseModel):
    id: UUID
    case_id: UUID
    version: int
    title: str
    content_markdown: str
    version_note: str | None
    generated_at: str
    created_by: str


def _orm_to_response(p: PrivacyPolicyModel) -> PrivacyPolicyResponse:
    return PrivacyPolicyResponse(
        id=p.id,
        case_id=p.case_id,
        version=p.version,
        title=p.title,
        content_markdown=p.content_markdown,
        version_note=p.version_note,
        generated_at=p.generated_at.isoformat(),
        created_by=p.created_by,
    )


# ---------------------------------------------------------------------------
# Globale Uebersicht (read-only) – haengt unter /privacy-policies
# ---------------------------------------------------------------------------


@router.get("", summary="Alle Datenschutzerklaerungen auflisten (read-only Uebersicht)")
async def list_privacy_policies(
    db: AsyncSession = Depends(get_db),
    _user=require_roles("viewer", "editor", "admin"),
) -> list[PrivacyPolicyResponse]:
    from app.services.privacy_policy_service import list_privacy_policies as _list

    items = await _list(db)
    return [_orm_to_response(p) for p in items]


@router.get("/{policy_id}", summary="Datenschutzerklaerung abrufen")
async def get_privacy_policy(
    policy_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("viewer", "editor", "admin"),
) -> PrivacyPolicyResponse:
    result = await db.execute(
        select(PrivacyPolicyModel).where(PrivacyPolicyModel.id == policy_id)
    )
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(
            status_code=404, detail="Datenschutzerklaerung nicht gefunden"
        )
    return _orm_to_response(policy)


class PrivacyPolicyUpdate(BaseModel):
    title: str | None = None
    content_markdown: str | None = None
    version_note: str | None = None


@router.patch("/{policy_id}", summary="Datenschutzerklaerung bearbeiten")
@limiter.limit("60/minute")
async def update_privacy_policy(
    request: Request,
    policy_id: UUID,
    body: PrivacyPolicyUpdate,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("editor", "admin"),
) -> PrivacyPolicyResponse:
    result = await db.execute(
        select(PrivacyPolicyModel).where(PrivacyPolicyModel.id == policy_id)
    )
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(
            status_code=404, detail="Datenschutzerklaerung nicht gefunden"
        )
    if body.title is not None:
        policy.title = body.title
    if body.content_markdown is not None:
        policy.content_markdown = body.content_markdown
    if body.version_note is not None:
        policy.version_note = body.version_note
    await db.flush()
    await db.refresh(policy)
    return _orm_to_response(policy)


@router.delete(
    "/{policy_id}", status_code=204, summary="Datenschutzerklaerung loeschen"
)
async def delete_privacy_policy(
    policy_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("admin"),
):
    result = await db.execute(
        select(PrivacyPolicyModel).where(PrivacyPolicyModel.id == policy_id)
    )
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(
            status_code=404, detail="Datenschutzerklaerung nicht gefunden"
        )
    await db.delete(policy)
    await db.flush()


# ---------------------------------------------------------------------------
# Case-bezogene Endpunkte – haengen unter /cases/{case_id}/privacy-policies
# ---------------------------------------------------------------------------


@case_scoped_router.get(
    "/{case_id}/privacy-policies",
    summary="Datenschutzerklaerungen fuer einen Vorgang auflisten",
)
async def list_privacy_policies_for_case(
    case_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("viewer", "editor", "admin"),
) -> list[PrivacyPolicyResponse]:
    from app.services.privacy_policy_service import (
        list_privacy_policies_for_case as _list,
    )

    case = await db.get(CaseModel, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Vorgang nicht gefunden")
    items = await _list(db, case_id)
    return [_orm_to_response(p) for p in items]


@case_scoped_router.post(
    "/{case_id}/privacy-policies/generate",
    summary="Datenschutzerklaerung fuer einen Vorgang generieren",
    status_code=201,
)
@limiter.limit("5/minute")
async def generate_privacy_policy_for_case(
    request: Request,
    case_id: UUID,
    body: PrivacyPolicyGenerateRequest,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("editor", "admin"),
) -> PrivacyPolicyResponse:
    """Generiert eine neue, vorgangsspezifische Datenschutzerklaerung.

    Der Inhalt wird vom aktiven LLM erzeugt und basiert ausschliesslich auf den
    Daten dieses Vorgangs (plus AVV der gleichen Abteilung).
    """
    from app.services.privacy_policy_service import (
        generate_privacy_policy as _gen,
    )
    from app.services.privacy_policy_service import (
        save_privacy_policy,
    )

    case = await db.get(CaseModel, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Vorgang nicht gefunden")

    try:
        payload = await _gen(
            db=db, case_id=case_id, contact=body.contact, notes=body.notes
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Privacy policy generation failed: %s", exc)
        raise HTTPException(
            status_code=500, detail=f"Generierung fehlgeschlagen: {exc}"
        ) from exc

    creator = getattr(_user, "display_name", "") if _user else ""
    policy = await save_privacy_policy(db, case_id, payload, created_by=creator)
    return _orm_to_response(policy)
