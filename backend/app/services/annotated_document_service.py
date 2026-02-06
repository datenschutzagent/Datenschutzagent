"""Generate annotated DOCX documents: original content plus findings as comments section."""
from __future__ import annotations

import io
from uuid import UUID

from docx import Document
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.db import CaseModel, DocumentModel, FindingModel


# Max characters of document content to include in the generated DOCX (avoid huge files)
MAX_CONTENT_CHARS = 100_000


async def list_annotatable_documents(case_id: UUID, db: AsyncSession) -> list[tuple[UUID, str, int]]:
    """
    Return list of (document_id, document_name, finding_count) for documents in this case
    that have at least one finding.
    """
    result = await db.execute(
        select(CaseModel).where(CaseModel.id == case_id).options(selectinload(CaseModel.documents))
    )
    case = result.scalar_one_or_none()
    if not case:
        return []

    from sqlalchemy import func

    counts_result = await db.execute(
        select(FindingModel.document_id, func.count(FindingModel.id))
        .where(FindingModel.case_id == case_id, FindingModel.document_id.isnot(None))
        .group_by(FindingModel.document_id)
    )
    count_by_doc = dict(counts_result.all())

    out: list[tuple[UUID, str, int]] = []
    for doc in case.documents:
        if doc.id in count_by_doc:
            out.append((doc.id, doc.name, count_by_doc[doc.id]))
    return out


async def build_annotated_docx(
    case_id: UUID, document_id: UUID, db: AsyncSession
) -> tuple[bytes, str]:
    """
    Build a DOCX containing the document's extracted content and a findings section.
    Returns (docx_bytes, suggested_filename).
    """
    result = await db.execute(
        select(CaseModel)
        .where(CaseModel.id == case_id)
        .options(selectinload(CaseModel.documents), selectinload(CaseModel.findings))
    )
    case = result.scalar_one_or_none()
    if not case:
        raise ValueError("Case not found")

    doc = next((d for d in case.documents if d.id == document_id), None)
    if not doc:
        raise ValueError("Document not found or not in this case")

    findings = [f for f in case.findings if f.document_id == document_id]

    docx_doc = Document()
    docx_doc.add_heading(doc.name, 0)
    docx_doc.add_paragraph("(Automatisch generierte annotierte Version mit Findings)")

    content = (doc.content or "").strip()
    if content:
        truncated = content[:MAX_CONTENT_CHARS]
        if len(content) > MAX_CONTENT_CHARS:
            truncated += "\n\n[... Inhalt gekürzt ...]"
        docx_doc.add_heading("Dokumentinhalt (extrahiert)", level=1)
        docx_doc.add_paragraph(truncated)

    docx_doc.add_heading("Findings (Prüfergebnisse)", level=1)
    for i, f in enumerate(findings, 1):
        docx_doc.add_heading(f"{i}. {f.check_name} ({f.severity})", level=2)
        docx_doc.add_paragraph(f.description)
        if f.evidence:
            p = docx_doc.add_paragraph()
            p.add_run("Belege: ").bold = True
            p.add_run(" ".join(f.evidence[:3]))  # limit evidence lines
        if f.recommendation:
            p = docx_doc.add_paragraph()
            p.add_run("Empfehlung: ").bold = True
            p.add_run(f.recommendation)
        docx_doc.add_paragraph()

    buf = io.BytesIO()
    docx_doc.save(buf)
    buf.seek(0)

    safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in doc.name)
    if not safe_name.rstrip("._"):
        safe_name = "document"
    if not safe_name.endswith(".docx"):
        safe_name += ".docx"
    filename = f"Annotiert-{safe_name}"

    return buf.getvalue(), filename
