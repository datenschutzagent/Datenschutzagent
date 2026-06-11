"""Stage 5 export & gap endpoints.

Routes:
  - GET /cases/{case_id}/tom-gaps       — TOM-Baseline-Coverage für den Vorgang
  - GET /cases/{case_id}/audit/export   — Signierter Audit-Trail (CSV / JSONL)
  - GET /cases/{case_id}/ropa-export    — ROPA nach Art. 30 (CSV / DOCX)

Globaler Endpoint (org-weit, nicht case-spezifisch):
  - GET /tom-gaps                       — Org-weite Baseline-Coverage
"""

from __future__ import annotations

import logging
from typing import Literal
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.auth import require_roles
from app.database import get_db
from app.models.db import CaseModel, TOMModel
from app.services.audit_export_service import export_full_trail
from app.services.org_profile_loader import get_vvt_field_names
from app.services.risk_config_loader import get_risk_config
from app.services.ropa_export_service import build_ropa_csv, build_ropa_docx
from app.services.tom_gap_service import analyse_gaps
from app.services.vvt_service import normalize_vvt

router = APIRouter()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# TOM-Gap
# ---------------------------------------------------------------------------


@router.get("/tom-gaps", summary="Org-weite TOM-Baseline-Coverage")
async def get_tom_gaps_global(
    db: AsyncSession = Depends(get_db),
    _user=require_roles("viewer", "editor", "admin"),
):
    """Compute baseline-vs-implemented gap analysis across ALL TOMs in the org."""
    toms = (await db.execute(select(TOMModel))).scalars().all()
    return analyse_gaps(get_risk_config().tom_baseline, toms)


@router.get(
    "/cases/{case_id}/tom-gaps", summary="TOM-Baseline-Coverage für einen Vorgang"
)
async def get_tom_gaps_for_case(
    case_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("viewer", "editor", "admin"),
):
    """Same baseline check, but scoped to TOMs assigned to the case's department.

    Falls back to the global set when the case has no department string
    or when no department-matching TOMs are tagged with ``department_codes``.
    """
    case = (
        await db.execute(select(CaseModel).where(CaseModel.id == case_id))
    ).scalar_one_or_none()
    if case is None:
        raise HTTPException(status_code=404, detail="Vorgang nicht gefunden")

    dept = (case.department or "").strip()
    toms_q = select(TOMModel)
    rows = (await db.execute(toms_q)).scalars().all()
    if dept:
        # Department codes are an ARRAY(String) on TOMModel. Match on
        # exact department string; empty/None list = "applies everywhere".
        in_scope = [
            t for t in rows if not t.department_codes or dept in t.department_codes
        ]
        if in_scope:
            rows = in_scope
    return analyse_gaps(get_risk_config().tom_baseline, rows)


# ---------------------------------------------------------------------------
# Audit-Trail-Export
# ---------------------------------------------------------------------------


@router.get(
    "/cases/{case_id}/audit/export",
    summary="Audit-Trail-Export (signiert)",
)
async def export_case_audit_trail(
    case_id: UUID,
    fmt: Literal["csv", "jsonl"] = Query("csv", alias="format"),
    db: AsyncSession = Depends(get_db),
    _user=require_roles("viewer", "editor", "admin"),
):
    """Return a signed activity-log export for the case.

    The ``X-Audit-Signature`` response header contains an HMAC-SHA256 over
    the response body; auditors can re-verify by hashing the file with
    the same key (see ``services/audit_export_service.verify_audit_signature``).
    """
    case = (
        await db.execute(select(CaseModel).where(CaseModel.id == case_id))
    ).scalar_one_or_none()
    if case is None:
        raise HTTPException(status_code=404, detail="Vorgang nicht gefunden")

    body, content_type, signature = await export_full_trail(case_id, db, fmt=fmt)
    ext = "csv" if fmt == "csv" else "jsonl"
    safe_title = "".join(
        c if c.isalnum() or c in "-_" else "_" for c in (case.title or "case")[:40]
    )
    filename = f"audit_{safe_title}_{case_id.hex[:8]}.{ext}"
    return Response(
        content=body,
        media_type=content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Audit-Signature": signature,
            "X-Audit-Signature-Alg": "HMAC-SHA256",
        },
    )


# ---------------------------------------------------------------------------
# ROPA-Export
# ---------------------------------------------------------------------------


@router.get("/cases/{case_id}/ropa-export", summary="ROPA gemäß Art. 30 DSGVO")
async def export_case_ropa(
    case_id: UUID,
    fmt: Literal["csv", "docx"] = Query("csv", alias="format"),
    document_id: UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _user=require_roles("viewer", "editor", "admin"),
):
    """Render the case's VVT data as an Art-30-style ROPA (CSV or DOCX).

    Uses the first attached VVT document by default; ``document_id`` lets
    callers pick a specific one when a case has multiple VVT variants.
    """
    case = (
        await db.execute(
            select(CaseModel)
            .where(CaseModel.id == case_id)
            .options(selectinload(CaseModel.documents))
        )
    ).scalar_one_or_none()
    if case is None:
        raise HTTPException(status_code=404, detail="Vorgang nicht gefunden")

    vvt_docs = [d for d in case.documents if d.type == "vvt"]
    if not vvt_docs:
        raise HTTPException(
            status_code=404, detail="Kein VVT-Dokument für diesen Vorgang"
        )

    if document_id is not None:
        doc = next((d for d in vvt_docs if d.id == document_id), None)
        if doc is None:
            raise HTTPException(status_code=404, detail="VVT-Dokument nicht gefunden")
    else:
        doc = vvt_docs[0]

    raw_text = doc.content or ""
    if not raw_text.strip():
        raise HTTPException(
            status_code=404, detail="VVT-Dokument hat keinen extrahierten Inhalt"
        )

    vvt_fields = get_vvt_field_names(settings)
    extraction = await normalize_vvt(
        raw_text, language=case.language, field_names=vvt_fields
    )
    fields_payload = [
        {
            "field_name": f.field_name,
            "canonical_value": f.canonical_value,
        }
        for f in extraction.fields
    ]
    case_summary = {
        "title": case.title,
        "department": case.department,
        "international_transfer": case.international_transfer,
        "org_name": settings.org_name,
        # ``dpo_contact`` may not exist on every settings instance.
        "dpo_contact": getattr(settings, "dpo_contact", None),
    }

    if fmt == "docx":
        body = build_ropa_docx(case_summary=case_summary, vvt_fields=fields_payload)
        ctype = (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        filename = f"ROPA_{_safe_filename(case.title)}_{case_id.hex[:8]}.docx"
    else:
        body = build_ropa_csv(case_summary=case_summary, vvt_fields=fields_payload)
        ctype = "text/csv; charset=utf-8"
        filename = f"ROPA_{_safe_filename(case.title)}_{case_id.hex[:8]}.csv"

    return Response(
        content=body,
        media_type=ctype,
        headers={
            "Content-Disposition": f"attachment; filename=\"{filename}\"; filename*=UTF-8''{quote(filename)}"
        },
    )


def _safe_filename(title: str | None) -> str:
    return "".join(
        c if c.isalnum() or c in "-_" else "_" for c in (title or "case")[:40]
    )
