"""Case management CRUD API."""
import csv
import io
import re
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import CaseCreate, CaseModel, CaseResponse, CaseUpdate, orm_to_case_response
from app.models.db import DocumentModel, FindingModel, PlaybookModel
from app.models.schemas import (
    AnnotatedDocumentListItem,
    DSBReportResponse,
    RunChecksRequest,
    VVTFieldResponse,
    VVTNormalizationResponse,
)
from app.services.annotated_document_service import build_annotated_docx, list_annotatable_documents
from app.services.check_runner import run_check
from app.services.dsb_report_service import build_dsb_report, render_report_markdown
from app.services.vvt_service import normalize_vvt

router = APIRouter()


@router.get("", response_model=list[CaseResponse])
async def list_cases(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """List cases with optional pagination."""
    result = await db.execute(
        select(CaseModel).order_by(CaseModel.updated_at.desc()).offset(skip).limit(limit)
    )
    cases = result.scalars().all()
    return [CaseResponse(**orm_to_case_response(c)) for c in cases]


@router.get("/{case_id}", response_model=CaseResponse)
async def get_case(
    case_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a single case by ID."""
    result = await db.execute(select(CaseModel).where(CaseModel.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return CaseResponse(**orm_to_case_response(case))


@router.post("", response_model=CaseResponse, status_code=201)
async def create_case(
    body: CaseCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new case."""
    case = CaseModel(
        title=body.title,
        department=body.department,
        case_type=body.case_type,
        language=body.language,
        created_by=body.created_by,
        assignee=body.assignee,
        status="intake",
        playbook_version="",
    )
    db.add(case)
    await db.flush()
    await db.refresh(case)
    return CaseResponse(**orm_to_case_response(case))


@router.patch("/{case_id}", response_model=CaseResponse)
async def update_case(
    case_id: UUID,
    body: CaseUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a case (partial update)."""
    result = await db.execute(select(CaseModel).where(CaseModel.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(case, key, value)
    await db.flush()
    await db.refresh(case)
    return CaseResponse(**orm_to_case_response(case))


@router.delete("/{case_id}", status_code=204)
async def delete_case(
    case_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a case and its documents/findings (cascade)."""
    result = await db.execute(select(CaseModel).where(CaseModel.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    await db.delete(case)
    await db.flush()
    return None


@router.get("/{case_id}/vvt-normalization/export", response_class=Response)
async def get_vvt_normalization_export(
    case_id: UUID,
    document_id: UUID | None = Query(None, alias="document_id"),
    format: str = Query("csv", alias="format"),
    db: AsyncSession = Depends(get_db),
):
    """
    Export VVT normalization as CSV. Uses first VVT document if document_id not given.
    Response: Content-Disposition attachment; filename="VVT-Export-{case_id}-{date}.csv".
    """
    result = await db.execute(
        select(CaseModel)
        .where(CaseModel.id == case_id)
        .options(selectinload(CaseModel.documents))
    )
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    vvt_docs = [d for d in case.documents if d.type == "vvt"]
    if not vvt_docs:
        raise HTTPException(status_code=404, detail="No VVT document in this case")

    if document_id is not None:
        doc = next((d for d in vvt_docs if d.id == document_id), None)
        if not doc:
            raise HTTPException(
                status_code=404,
                detail="Document not found or is not a VVT document of this case",
            )
    else:
        doc = vvt_docs[0]

    raw_text = doc.content or ""
    extraction = await normalize_vvt(raw_text)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["document_name", "source_template", "field_name", "status", "canonical_value", "evidence", "finding"])
    for f in extraction.fields:
        writer.writerow([
            doc.name,
            extraction.source_template or "",
            f.field_name,
            f.status,
            (f.canonical_value or "").replace("\r\n", " ").replace("\n", " "),
            (f.evidence or "").replace("\r\n", " ").replace("\n", " "),
            (f.finding or "").replace("\r\n", " ").replace("\n", " "),
        ])
    csv_content = buf.getvalue()
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    filename = f"VVT-Export-{case_id}-{date_str}.csv"
    body = "\ufeff" + csv_content  # UTF-8 BOM for Excel
    return Response(
        content=body.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{case_id}/vvt-normalization", response_model=VVTNormalizationResponse)
async def get_vvt_normalization(
    case_id: UUID,
    document_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Get VVT normalization for the case. Uses the first VVT document if document_id is not given.
    Returns canonical VVT fields and template detection (LLM-based).
    """
    result = await db.execute(
        select(CaseModel)
        .where(CaseModel.id == case_id)
        .options(selectinload(CaseModel.documents))
    )
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    vvt_docs = [d for d in case.documents if d.type == "vvt"]
    if not vvt_docs:
        return VVTNormalizationResponse(
            document_id=None,
            document_name="",
            source_template="",
            fields=[],
        )

    if document_id is not None:
        doc = next((d for d in vvt_docs if d.id == document_id), None)
        if not doc:
            raise HTTPException(
                status_code=404,
                detail="Document not found or is not a VVT document of this case",
            )
    else:
        doc = vvt_docs[0]

    raw_text = doc.content or ""
    extraction = await normalize_vvt(raw_text)

    fields = [
        VVTFieldResponse(
            field_name=f.field_name,
            required=True,
            status=f.status,
            source_template=extraction.source_template,
            canonical_value=f.canonical_value,
            evidence=f.evidence,
            finding=f.finding,
        )
        for f in extraction.fields
    ]
    return VVTNormalizationResponse(
        document_id=doc.id,
        document_name=doc.name,
        source_template=extraction.source_template or "Unbekannt",
        fields=fields,
    )


@router.get("/{case_id}/dsb-report")
async def get_dsb_report(
    case_id: UUID,
    format: str = Query("markdown", alias="format"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get DSB summary report for the case. format=markdown (default) or format=json.
    Markdown returns file download with Content-Disposition.
    """
    report = await build_dsb_report(case_id, db)
    if format == "json":
        return JSONResponse(content=report.model_dump(mode="json"))
    md = render_report_markdown(report)
    slug = re.sub(r"[^\w\s-]", "", report.case_title)[:50].strip() or "Report"
    slug = re.sub(r"[-\s]+", "-", slug)
    date_str = report.generated_at.strftime("%Y-%m-%d")
    filename = f"DSB-Report-{slug}-{date_str}.md"
    return Response(
        content=md,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.get("/{case_id}/annotated-documents", response_model=list[AnnotatedDocumentListItem])
async def list_annotated_documents(
    case_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """List documents that have findings and can be downloaded as annotated DOCX."""
    result = await db.execute(select(CaseModel).where(CaseModel.id == case_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Case not found")
    items = await list_annotatable_documents(case_id, db)
    return [
        AnnotatedDocumentListItem(document_id=doc_id, document_name=name, finding_count=count)
        for doc_id, name, count in items
    ]


@router.get("/{case_id}/annotated-documents/{document_id}", response_class=Response)
async def get_annotated_document(
    case_id: UUID,
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Download annotated DOCX for a document (content + findings section)."""
    try:
        content, filename = await build_annotated_docx(case_id, document_id, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{case_id}/run-checks", response_model=CaseResponse)
async def run_checks(
    case_id: UUID,
    body: RunChecksRequest,
    db: AsyncSession = Depends(get_db),
):
    """Run playbook checks against all case documents and persist findings."""
    result = await db.execute(
        select(CaseModel)
        .where(CaseModel.id == case_id)
        .options(selectinload(CaseModel.documents))
    )
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    pb_result = await db.execute(select(PlaybookModel).where(PlaybookModel.id == body.playbook_id))
    playbook = pb_result.scalar_one_or_none()
    if not playbook:
        raise HTTPException(status_code=404, detail="Playbook not found")

    checks = playbook.content.get("checks") if isinstance(playbook.content, dict) else []
    if not checks:
        await db.refresh(case)
        return CaseResponse(**orm_to_case_response(case))

    for doc in case.documents:
        text = (doc.content or "") or ""
        for item in checks:
            name = item.get("name") or item.get("check_name") or "Check"
            instruction = item.get("instruction") or item.get("requirement") or ""
            if not instruction:
                continue
            try:
                check_result = await run_check(text, instruction)
            except Exception:
                continue
            if not check_result.is_compliant:
                finding = FindingModel(
                    case_id=case_id,
                    document_id=doc.id,
                    check_name=name,
                    severity=check_result.severity,
                    status="open",
                    category=name,
                    description=check_result.description,
                    evidence=check_result.evidence or [],
                    recommendation=check_result.recommendation or "",
                )
                db.add(finding)

    await db.flush()
    # Reload case with documents and findings for response
    result2 = await db.execute(
        select(CaseModel)
        .where(CaseModel.id == case_id)
        .options(selectinload(CaseModel.documents), selectinload(CaseModel.findings))
    )
    case = result2.scalar_one()
    return CaseResponse(**orm_to_case_response(case))
