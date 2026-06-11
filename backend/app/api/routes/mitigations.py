"""Mitigation catalog + link endpoints.

Routes:
  - GET    /mitigations/catalog            list all catalog entries
  - GET    /cases/{id}/mitigations         list links for a case (DSFA)
  - POST   /cases/{id}/mitigations         link a mitigation
  - DELETE /cases/{id}/mitigations/{mid}   unlink
  - GET    /cases/{id}/risk-delta          inherent vs residual (DSFA)
  - GET    /avv/{id}/mitigations           list links for an AVV
  - POST   /avv/{id}/mitigations           link a mitigation
  - DELETE /avv/{id}/mitigations/{mid}     unlink
  - GET    /avv/{id}/risk-delta            inherent vs residual (AVV)
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_roles
from app.core.rate_limit import limiter
from app.database import get_db
from app.models.db import (
    AVVContractModel,
    AvvMitigationLinkModel,
    CaseMitigationLinkModel,
    CaseModel,
)
from app.models.schemas import (
    AvvMitigationLinkResponse,
    CaseMitigationLinkResponse,
    MitigationCatalogEntry,
    MitigationCatalogResponse,
    MitigationLinkRequest,
    MitigationReductionResponse,
    RiskDeltaResponse,
    RiskDeltaSide,
)
from app.services.risk_config_loader import MitigationConfig, get_risk_config

router = APIRouter()
logger = logging.getLogger(__name__)


def _catalog_entry_to_schema(m: MitigationConfig) -> MitigationCatalogEntry:
    return MitigationCatalogEntry(
        id=m.id,
        label=m.label,
        description=m.description,
        applies_to=m.applies_to,
        tom_category=m.tom_category,
        evidence_required=m.evidence_required,
        reduction=MitigationReductionResponse(
            score_delta=m.reduction.score_delta,
            dimension_deltas=dict(m.reduction.dimension_deltas),
            likelihood_delta=m.reduction.likelihood_delta,
            severity_delta=m.reduction.severity_delta,
            applicable_risk_keywords=list(m.reduction.applicable_risk_keywords),
        ),
    )


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------


@router.get(
    "/mitigations/catalog",
    response_model=MitigationCatalogResponse,
    summary="Mitigation-Katalog auflisten",
)
async def get_mitigation_catalog(_user=require_roles("viewer", "editor", "admin")):
    cfg = get_risk_config().mitigations
    return MitigationCatalogResponse(
        enabled=cfg.enabled,
        min_likelihood=cfg.min_likelihood,
        min_severity=cfg.min_severity,
        min_avv_score=cfg.min_avv_score,
        catalog=[_catalog_entry_to_schema(m) for m in cfg.catalog],
    )


# ---------------------------------------------------------------------------
# Case ↔ mitigation (DSFA-side)
# ---------------------------------------------------------------------------


@router.get(
    "/cases/{case_id}/mitigations",
    response_model=list[CaseMitigationLinkResponse],
    summary="Angewendete Mitigations für einen Vorgang",
)
async def list_case_mitigations(
    case_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("viewer", "editor", "admin"),
):
    await _require_case(case_id, db)
    rows = (
        (
            await db.execute(
                select(CaseMitigationLinkModel)
                .where(CaseMitigationLinkModel.case_id == case_id)
                .order_by(CaseMitigationLinkModel.applied_at.asc())
            )
        )
        .scalars()
        .all()
    )
    catalog = get_risk_config().mitigations
    out: list[CaseMitigationLinkResponse] = []
    for link in rows:
        resp = CaseMitigationLinkResponse.model_validate(link)
        entry = catalog.by_id(link.mitigation_id)
        if entry is not None:
            resp.catalog_entry = _catalog_entry_to_schema(entry)
        out.append(resp)
    return out


@router.post(
    "/cases/{case_id}/mitigations",
    response_model=CaseMitigationLinkResponse,
    status_code=201,
    summary="Mitigation für einen Vorgang verknüpfen",
)
@limiter.limit("60/minute")
async def link_case_mitigation(
    request: Request,
    case_id: UUID,
    body: MitigationLinkRequest,
    db: AsyncSession = Depends(get_db),
    user=require_roles("editor", "admin"),
):
    await _require_case(case_id, db)
    catalog = get_risk_config().mitigations
    entry = catalog.by_id(body.mitigation_id)
    if entry is None:
        raise HTTPException(
            status_code=404,
            detail=f"Mitigation '{body.mitigation_id}' nicht im Katalog",
        )
    if entry.applies_to not in ("dsfa", "both"):
        raise HTTPException(
            status_code=422,
            detail=f"Mitigation '{entry.id}' ist nicht auf DSFA anwendbar",
        )

    existing = (
        await db.execute(
            select(CaseMitigationLinkModel).where(
                CaseMitigationLinkModel.case_id == case_id,
                CaseMitigationLinkModel.mitigation_id == body.mitigation_id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=409, detail="Diese Mitigation ist bereits verknüpft"
        )

    link = CaseMitigationLinkModel(
        case_id=case_id,
        mitigation_id=body.mitigation_id,
        tom_id=body.tom_id,
        evidence_doc_id=body.evidence_doc_id,
        notes=body.notes,
        applied_by=_user_label(user),
    )
    db.add(link)
    await db.flush()
    await db.refresh(link)
    resp = CaseMitigationLinkResponse.model_validate(link)
    resp.catalog_entry = _catalog_entry_to_schema(entry)
    return resp


@router.delete(
    "/cases/{case_id}/mitigations/{mitigation_id}",
    status_code=204,
    summary="Verknüpfte Mitigation entfernen",
)
async def unlink_case_mitigation(
    case_id: UUID,
    mitigation_id: str,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("editor", "admin"),
):
    link = (
        await db.execute(
            select(CaseMitigationLinkModel).where(
                CaseMitigationLinkModel.case_id == case_id,
                CaseMitigationLinkModel.mitigation_id == mitigation_id,
            )
        )
    ).scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=404, detail="Verknüpfung nicht gefunden")
    await db.delete(link)
    await db.flush()


@router.get(
    "/cases/{case_id}/risk-delta",
    response_model=RiskDeltaResponse,
    summary="DSFA: Vor-/Nach-Risiko-Vergleich",
)
async def get_case_risk_delta(
    case_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("viewer", "editor", "admin"),
):
    """Returns inherent vs residual risk for the case's DSFA.

    Reads from the persisted DSFA payload — re-running the LLM is not
    needed. If no DSFA exists yet, returns 404 so the UI can surface
    a hint instead of an empty card.
    """
    from app.models.db import DSFAAssessmentModel

    await _require_case(case_id, db)
    dsfa = (
        await db.execute(
            select(DSFAAssessmentModel).where(DSFAAssessmentModel.case_id == case_id)
        )
    ).scalar_one_or_none()
    if dsfa is None or not dsfa.payload:
        raise HTTPException(
            status_code=404,
            detail="Keine DSFA vorhanden. Bitte zuerst generieren, dann ist ein Risk-Delta verfügbar.",
        )
    payload = dsfa.payload
    return RiskDeltaResponse(
        target_type="dsfa",
        target_id=case_id,
        inherent=RiskDeltaSide(
            risk_score=None,
            risk_level=payload.get("inherent_residual_risk")
            or payload.get("residual_risk"),
        ),
        residual=RiskDeltaSide(
            risk_score=None,
            risk_level=payload.get("residual_risk"),
        ),
        applied_mitigations=list(payload.get("applied_mitigations", []) or []),
        applied_effects=list(payload.get("applied_effects", []) or []),
        assessed_at=dsfa.generated_at,
    )


# ---------------------------------------------------------------------------
# AVV ↔ mitigation
# ---------------------------------------------------------------------------


@router.get(
    "/avv/{contract_id}/mitigations",
    response_model=list[AvvMitigationLinkResponse],
    summary="Angewendete Mitigations für einen AVV",
)
async def list_avv_mitigations(
    contract_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("viewer", "editor", "admin"),
):
    await _require_avv(contract_id, db)
    rows = (
        (
            await db.execute(
                select(AvvMitigationLinkModel)
                .where(AvvMitigationLinkModel.avv_contract_id == contract_id)
                .order_by(AvvMitigationLinkModel.applied_at.asc())
            )
        )
        .scalars()
        .all()
    )
    catalog = get_risk_config().mitigations
    out: list[AvvMitigationLinkResponse] = []
    for link in rows:
        resp = AvvMitigationLinkResponse.model_validate(link)
        entry = catalog.by_id(link.mitigation_id)
        if entry is not None:
            resp.catalog_entry = _catalog_entry_to_schema(entry)
        out.append(resp)
    return out


@router.post(
    "/avv/{contract_id}/mitigations",
    response_model=AvvMitigationLinkResponse,
    status_code=201,
    summary="Mitigation für einen AVV verknüpfen",
)
@limiter.limit("60/minute")
async def link_avv_mitigation(
    request: Request,
    contract_id: UUID,
    body: MitigationLinkRequest,
    db: AsyncSession = Depends(get_db),
    user=require_roles("editor", "admin"),
):
    await _require_avv(contract_id, db)
    catalog = get_risk_config().mitigations
    entry = catalog.by_id(body.mitigation_id)
    if entry is None:
        raise HTTPException(
            status_code=404,
            detail=f"Mitigation '{body.mitigation_id}' nicht im Katalog",
        )
    if entry.applies_to not in ("avv", "both"):
        raise HTTPException(
            status_code=422,
            detail=f"Mitigation '{entry.id}' ist nicht auf AVV anwendbar",
        )

    existing = (
        await db.execute(
            select(AvvMitigationLinkModel).where(
                AvvMitigationLinkModel.avv_contract_id == contract_id,
                AvvMitigationLinkModel.mitigation_id == body.mitigation_id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=409, detail="Diese Mitigation ist bereits verknüpft"
        )

    link = AvvMitigationLinkModel(
        avv_contract_id=contract_id,
        mitigation_id=body.mitigation_id,
        tom_id=body.tom_id,
        notes=body.notes,
        applied_by=_user_label(user),
    )
    db.add(link)
    await db.flush()
    await db.refresh(link)
    resp = AvvMitigationLinkResponse.model_validate(link)
    resp.catalog_entry = _catalog_entry_to_schema(entry)
    return resp


@router.delete(
    "/avv/{contract_id}/mitigations/{mitigation_id}",
    status_code=204,
    summary="Verknüpfte Mitigation entfernen",
)
async def unlink_avv_mitigation(
    contract_id: UUID,
    mitigation_id: str,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("editor", "admin"),
):
    link = (
        await db.execute(
            select(AvvMitigationLinkModel).where(
                AvvMitigationLinkModel.avv_contract_id == contract_id,
                AvvMitigationLinkModel.mitigation_id == mitigation_id,
            )
        )
    ).scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=404, detail="Verknüpfung nicht gefunden")
    await db.delete(link)
    await db.flush()


@router.get(
    "/avv/{contract_id}/risk-delta",
    response_model=RiskDeltaResponse,
    summary="AVV: Vor-/Nach-Risiko-Vergleich",
)
async def get_avv_risk_delta(
    contract_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("viewer", "editor", "admin"),
):
    contract = await _require_avv(contract_id, db)
    if contract.risk_assessed_at is None:
        raise HTTPException(
            status_code=404,
            detail="Keine Risikobewertung vorhanden. Bitte zuerst /risk-assessment auslösen.",
        )
    assessment = contract.risk_assessment or {}
    return RiskDeltaResponse(
        target_type="avv",
        target_id=contract_id,
        inherent=RiskDeltaSide(
            risk_score=contract.inherent_risk_score,
            risk_level=contract.inherent_risk_level,
        ),
        residual=RiskDeltaSide(
            risk_score=contract.risk_score,
            risk_level=contract.risk_level,
        ),
        applied_mitigations=list(assessment.get("applied_mitigations", []) or []),
        applied_effects=list(assessment.get("applied_effects", []) or []),
        assessed_at=contract.risk_assessed_at,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _require_case(case_id: UUID, db: AsyncSession) -> CaseModel:
    case = (
        await db.execute(select(CaseModel).where(CaseModel.id == case_id))
    ).scalar_one_or_none()
    if case is None:
        raise HTTPException(status_code=404, detail="Vorgang nicht gefunden")
    return case


async def _require_avv(contract_id: UUID, db: AsyncSession) -> AVVContractModel:
    contract = (
        await db.execute(
            select(AVVContractModel).where(AVVContractModel.id == contract_id)
        )
    ).scalar_one_or_none()
    if contract is None:
        raise HTTPException(status_code=404, detail="AVV nicht gefunden")
    return contract


def _user_label(user) -> str:
    """Return a printable user identifier for audit fields.

    ``require_roles`` returns a UserModel-like object; fall back gracefully
    if the test-mode dependency override returns a stub or dict.
    """
    for attr in ("email", "username", "id"):
        val = getattr(user, attr, None)
        if val:
            return str(val)[:200]
    if isinstance(user, dict):
        for key in ("email", "username", "id"):
            v = user.get(key)
            if v:
                return str(v)[:200]
    return ""
