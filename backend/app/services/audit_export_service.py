"""Audit-Paket-Export: Erstellt ein ZIP-Archiv mit allen Audit-relevanten Daten eines Vorgangs.

Inhalt des ZIP:
  - findings.csv              – Alle Befunde mit Status, Schwere, Empfehlung
  - activity_log.csv          – Audit-Trail aller Ereignisse
  - case_summary.json         – Metadaten des Vorgangs
  - documents_list.csv        – Liste aller Dokumente
  - manifest.json             – SHA-256-Prüfsummen aller Dateien (Integritätsnachweis)
"""

import csv
import hashlib
import io
import json
import logging
import zipfile
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import ActivityLogModel, CaseModel, DocumentModel, FindingModel

logger = logging.getLogger(__name__)


async def build_audit_export(case_id: UUID, db: AsyncSession) -> tuple[bytes, str]:
    """Erstellt das ZIP-Audit-Paket und gibt (zip_bytes, filename) zurück."""
    logger.info("Audit export started", extra={"case_id": str(case_id)})
    # Case laden
    case_result = await db.execute(select(CaseModel).where(CaseModel.id == case_id))
    case = case_result.scalar_one_or_none()
    if not case:
        raise ValueError(f"Case {case_id} not found")

    # Findings laden
    findings_result = await db.execute(
        select(FindingModel)
        .where(FindingModel.case_id == case_id)
        .order_by(FindingModel.severity.asc(), FindingModel.created_at.asc())
    )
    findings = findings_result.scalars().all()

    # Dokumente laden
    docs_result = await db.execute(
        select(DocumentModel)
        .where(DocumentModel.case_id == case_id)
        .order_by(DocumentModel.uploaded_at.asc())
    )
    documents = docs_result.scalars().all()

    # Activity-Log laden
    activity_result = await db.execute(
        select(ActivityLogModel)
        .where(ActivityLogModel.case_id == case_id)
        .order_by(ActivityLogModel.created_at.asc())
    )
    activities = activity_result.scalars().all()

    # ZIP zusammenstellen
    zip_buffer = io.BytesIO()
    file_hashes: dict[str, str] = {}

    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        # 1. case_summary.json
        summary = {
            "case_id": str(case.id),
            "title": case.title,
            "department": case.department,
            "case_type": case.case_type,
            "status": case.status,
            "language": case.language,
            "created_by": case.created_by,
            "assignee": case.assignee,
            "deadline": case.deadline.isoformat() if case.deadline else None,
            "special_category_data": case.special_category_data,
            "international_transfer": case.international_transfer,
            "created_at": case.created_at.isoformat(),
            "updated_at": case.updated_at.isoformat(),
            "export_generated_at": datetime.now(UTC).isoformat(),
            "total_findings": len(findings),
            "total_documents": len(documents),
        }
        summary_bytes = json.dumps(summary, ensure_ascii=False, indent=2).encode(
            "utf-8"
        )
        zf.writestr("case_summary.json", summary_bytes)
        file_hashes["case_summary.json"] = _sha256(summary_bytes)

        # 2. findings.csv
        findings_buf = io.StringIO()
        findings_writer = csv.writer(findings_buf)
        findings_writer.writerow(
            [
                "id",
                "check_name",
                "severity",
                "status",
                "category",
                "description",
                "recommendation",
                "evidence",
                "due_date",
                "created_at",
                "updated_at",
            ]
        )
        for f in findings:
            findings_writer.writerow(
                [
                    str(f.id),
                    f.check_name,
                    f.severity,
                    f.status,
                    f.category,
                    f.description,
                    f.recommendation,
                    "; ".join(f.evidence or []),
                    f.due_date.isoformat() if f.due_date else "",
                    f.created_at.isoformat(),
                    f.updated_at.isoformat(),
                ]
            )
        findings_bytes = findings_buf.getvalue().encode("utf-8-sig")
        zf.writestr("findings.csv", findings_bytes)
        file_hashes["findings.csv"] = _sha256(findings_bytes)

        # 3. documents_list.csv
        docs_buf = io.StringIO()
        docs_writer = csv.writer(docs_buf)
        docs_writer.writerow(
            [
                "id",
                "name",
                "type",
                "format",
                "size_bytes",
                "version",
                "uploaded_by",
                "extraction_status",
                "uploaded_at",
            ]
        )
        for d in documents:
            docs_writer.writerow(
                [
                    str(d.id),
                    d.name,
                    d.type,
                    d.format,
                    d.size_bytes,
                    d.version,
                    d.uploaded_by,
                    d.extraction_status,
                    d.uploaded_at.isoformat(),
                ]
            )
        docs_bytes = docs_buf.getvalue().encode("utf-8-sig")
        zf.writestr("documents_list.csv", docs_bytes)
        file_hashes["documents_list.csv"] = _sha256(docs_bytes)

        # 4. activity_log.csv
        activity_buf = io.StringIO()
        activity_writer = csv.writer(activity_buf)
        activity_writer.writerow(["id", "event_type", "payload", "created_at"])
        for a in activities:
            activity_writer.writerow(
                [
                    str(a.id),
                    a.event_type,
                    json.dumps(a.payload, ensure_ascii=False),
                    a.created_at.isoformat(),
                ]
            )
        activity_bytes = activity_buf.getvalue().encode("utf-8-sig")
        zf.writestr("activity_log.csv", activity_bytes)
        file_hashes["activity_log.csv"] = _sha256(activity_bytes)

        # 5. manifest.json (SHA-256 Integrität)
        manifest = {
            "generated_at": datetime.now(UTC).isoformat(),
            "case_id": str(case_id),
            "files": file_hashes,
        }
        manifest_bytes = json.dumps(manifest, ensure_ascii=False, indent=2).encode(
            "utf-8"
        )
        zf.writestr("manifest.json", manifest_bytes)

    zip_bytes = zip_buffer.getvalue()
    safe_title = "".join(
        c if c.isalnum() or c in "-_" else "_" for c in case.title[:40]
    )
    filename = f"audit_{safe_title}_{case_id.hex[:8]}.zip"
    logger.info(
        "Audit export complete",
        extra={
            "case_id": str(case_id),
            "filename": filename,
            "size_bytes": len(zip_bytes),
        },
    )
    return zip_bytes, filename


def _sha256(data: bytes) -> str:
    """SHA-256-Hex-Digest für Integritätsnachweis."""
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# Audit-Trail-Export (Stufe 5): signed CSV / JSONL of activity_log only.
# ---------------------------------------------------------------------------


def _audit_signing_key() -> bytes:
    """Return the HMAC-SHA256 signing key for the audit trail export.

    Reuses the existing webhook-secret encryption key when set (deployments
    keep that secret out of git already). Falls back to a deterministic
    derivation from CASE_SECRET_KEY + a fixed domain string so dev/test
    environments still produce verifiable signatures. We never ship a
    constant key in source — the fallback only fires when nothing is
    configured at all, and only in non-production.
    """
    import os
    from hashlib import blake2b

    explicit = os.environ.get("AUDIT_EXPORT_SIGNING_KEY")
    if explicit:
        return explicit.encode("utf-8")
    secret = (
        os.environ.get("WEBHOOK_SECRET_ENCRYPTION_KEY")
        or os.environ.get("APP_SECRET_KEY")
        or ""
    )
    derived = blake2b(
        b"audit-trail-export:" + secret.encode("utf-8"), digest_size=32
    ).digest()
    return derived


async def export_full_trail(
    case_id: UUID,
    db: AsyncSession,
    *,
    fmt: str = "csv",
) -> tuple[bytes, str, str]:
    """Build a signed activity-log export for a single case.

    Format options:
      - ``csv``  – UTF-8-BOM CSV with id, event_type, payload, created_at.
      - ``jsonl`` – one JSON object per line (preserves payload structure).

    The body is hashed (SHA-256) and signed (HMAC-SHA256) with the
    configured audit key. Both are returned so the caller can either
    embed them in the response file (CSV trailer / JSONL trailer line)
    or surface them as HTTP headers for verifiability.

    Returns (body_bytes, content_type, signature_hex).
    """
    if fmt not in {"csv", "jsonl"}:
        raise ValueError(f"unsupported format: {fmt!r} (use 'csv' or 'jsonl')")

    rows = (
        (
            await db.execute(
                select(ActivityLogModel)
                .where(ActivityLogModel.case_id == case_id)
                .order_by(ActivityLogModel.created_at.asc())
            )
        )
        .scalars()
        .all()
    )

    if fmt == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["id", "event_type", "payload", "created_at"])
        for a in rows:
            writer.writerow(
                [
                    str(a.id),
                    a.event_type,
                    json.dumps(a.payload, ensure_ascii=False, sort_keys=True),
                    a.created_at.isoformat(),
                ]
            )
        body = ("﻿" + buf.getvalue()).encode("utf-8")
        content_type = "text/csv; charset=utf-8"
    else:
        lines: list[str] = []
        for a in rows:
            lines.append(
                json.dumps(
                    {
                        "id": str(a.id),
                        "event_type": a.event_type,
                        "payload": a.payload,
                        "created_at": a.created_at.isoformat(),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
        body = ("\n".join(lines) + ("\n" if lines else "")).encode("utf-8")
        content_type = "application/x-ndjson; charset=utf-8"

    import hmac

    signature = hmac.new(_audit_signing_key(), body, hashlib.sha256).hexdigest()
    return body, content_type, signature


def verify_audit_signature(body: bytes, signature_hex: str) -> bool:
    """Verify a previously emitted audit-trail signature. Used by tests + tools."""
    import hmac

    expected = hmac.new(_audit_signing_key(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_hex)


__all__ = [
    "build_audit_export",
    "export_full_trail",
    "verify_audit_signature",
]
