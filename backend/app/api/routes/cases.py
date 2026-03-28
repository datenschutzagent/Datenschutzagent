"""Case management CRUD API."""
import asyncio
import csv
import io
import logging
import re
from datetime import datetime, timezone
from uuid import UUID

logger = logging.getLogger(__name__)

from docx import Document as DocxDocument
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import get_db
from app.models import CaseCreate, CaseListResponse, CaseModel, CaseResponse, CaseUpdate, orm_to_case_response
from app.models.db import (
    ActivityLogModel,
    DocumentModel,
    DSBReportJobModel,
    PlaybookModel,
    RunChecksJobModel,
    orm_to_activity_response,
)
from app.models.schemas import (
    ActivityResponse,
    AnnotatedDocumentListItem,
    DSBReportResponse,
    RunChecksRequest,
    VVTFieldResponse,
    VVTNormalizationResponse,
)
from app.services.annotated_document_service import (
    build_annotated_docx,
    build_annotated_pdf,
    list_annotatable_documents,
)
from app.services.run_checks_service import run_checks_impl
from app.celery_app import build_dsb_report_task, run_playbook_checks
from app.services.weaviate_service import delete_chunks_by_case_id
from app.services.dsb_report_service import (
    build_dsb_report,
    compute_stale,
    get_last_run_checks_at,
    get_latest_report,
    render_report_markdown,
    save_report,
)
from app.services.dsb_report_service import _payload_to_report
from app.services.vvt_service import normalize_vvt
from app.services.org_profile_loader import get_vvt_field_names
from app.core.auth import require_roles

router = APIRouter()


@router.get("", response_model=CaseListResponse)
async def list_cases(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """List cases with optional pagination. Returns items and total count."""
    count_result = await db.execute(select(func.count()).select_from(CaseModel))
    total = count_result.scalar_one()

    result = await db.execute(
        select(CaseModel)
        .options(selectinload(CaseModel.documents), selectinload(CaseModel.findings))
        .order_by(CaseModel.updated_at.desc())
        .offset(skip)
        .limit(limit)
    )
    cases = result.scalars().all()
    return CaseListResponse(
        items=[CaseResponse(**orm_to_case_response(c)) for c in cases],
        total=total,
    )


@router.get("/{case_id}", response_model=CaseResponse)
async def get_case(
    case_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a single case by ID."""
    result = await db.execute(
        select(CaseModel)
        .where(CaseModel.id == case_id)
        .options(selectinload(CaseModel.documents), selectinload(CaseModel.findings))
    )
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return CaseResponse(**orm_to_case_response(case))


@router.get("/{case_id}/activities", response_model=list[ActivityResponse])
async def get_case_activities(
    case_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get activity log for the case (run_checks, finding_status_updated, etc.), sorted by time descending."""
    result = await db.execute(
        select(CaseModel).where(CaseModel.id == case_id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Case not found")
    activities_result = await db.execute(
        select(ActivityLogModel)
        .where(ActivityLogModel.case_id == case_id)
        .order_by(ActivityLogModel.created_at.desc())
    )
    activities = activities_result.scalars().all()
    return [ActivityResponse(**orm_to_activity_response(a)) for a in activities]


@router.post("", response_model=CaseResponse, status_code=201)
async def create_case(
    body: CaseCreate,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("editor", "admin"),
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
        processing_context=body.processing_context,
        special_category_data=body.special_category_data,
        international_transfer=body.international_transfer,
    )
    db.add(case)
    await db.flush()
    # Re-fetch with relationships loaded to avoid lazy load in async context (MissingGreenlet)
    result = await db.execute(
        select(CaseModel)
        .where(CaseModel.id == case.id)
        .options(selectinload(CaseModel.documents), selectinload(CaseModel.findings))
    )
    case = result.scalar_one()
    return CaseResponse(**orm_to_case_response(case))


@router.patch("/{case_id}", response_model=CaseResponse)
async def update_case(
    case_id: UUID,
    body: CaseUpdate,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("editor", "admin"),
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
    # Re-fetch with relationships loaded to avoid lazy load in async context (MissingGreenlet)
    result = await db.execute(
        select(CaseModel)
        .where(CaseModel.id == case_id)
        .options(selectinload(CaseModel.documents), selectinload(CaseModel.findings))
    )
    case = result.scalar_one()
    return CaseResponse(**orm_to_case_response(case))


@router.delete("/{case_id}", status_code=204)
async def delete_case(
    case_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("editor", "admin"),
):
    """Delete a case and its documents/findings (cascade)."""
    result = await db.execute(select(CaseModel).where(CaseModel.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    await asyncio.to_thread(delete_chunks_by_case_id, case_id)
    await db.delete(case)
    await db.flush()
    return None


def _build_vvt_export_docx(doc_name: str, source_template: str, fields: list) -> bytes:
    """Build DOCX with VVT normalization (Ziel-Template): document name, template, table of fields."""
    doc = DocxDocument()
    doc.add_heading("VVT-Normalisierung (Ziel-Template)", 0)
    doc.add_paragraph()
    doc.add_paragraph(f"Dokument: {doc_name}")
    doc.add_paragraph(f"Erkanntes Template: {source_template or '—'}")
    doc.add_paragraph()
    table = doc.add_table(rows=1 + len(fields), cols=5)
    table.style = "Table Grid"
    hdr = table.rows[0].cells
    hdr[0].text = "Feldname"
    hdr[1].text = "Status"
    hdr[2].text = "Kanonischer Wert"
    hdr[3].text = "Nachweis"
    hdr[4].text = "Hinweis"
    for i, f in enumerate(fields):
        row = table.rows[i + 1].cells
        row[0].text = (f.field_name or "").replace("\r\n", " ").replace("\n", " ")
        row[1].text = (f.status or "").replace("\r\n", " ").replace("\n", " ")
        row[2].text = (f.canonical_value or "").replace("\r\n", " ").replace("\n", " ")
        row[3].text = (f.evidence or "").replace("\r\n", " ").replace("\n", " ")
        row[4].text = (f.finding or "").replace("\r\n", " ").replace("\n", " ")
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


@router.get("/{case_id}/vvt-normalization/export", response_class=Response)
async def get_vvt_normalization_export(
    case_id: UUID,
    document_id: UUID | None = Query(None, alias="document_id"),
    format: str = Query("csv", alias="format"),
    db: AsyncSession = Depends(get_db),
):
    """
    Export VVT normalization. Query: format=csv (default) or format=docx.
    Uses first VVT document if document_id not given.
    CSV: text/csv. DOCX: VVT Ziel-Template (document name, template, fields table).
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
    if not raw_text.strip():
        raise HTTPException(
            status_code=404,
            detail="VVT-Dokument hat keinen extrahierten Inhalt",
        )

    case_lang = getattr(case, "language", None)
    vvt_fields = get_vvt_field_names(settings)
    extraction = await normalize_vvt(raw_text, language=case_lang, field_names=vvt_fields)
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if (format or "csv").lower() == "docx":
        content = _build_vvt_export_docx(doc.name, extraction.source_template or "", extraction.fields)
        filename = f"VVT-Ziel-{case_id}-{date_str}.docx"
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

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
    if not raw_text.strip():
        return VVTNormalizationResponse(
            document_id=doc.id,
            document_name=doc.name,
            source_template="",
            fields=[],
        )

    case_lang = getattr(case, "language", None)
    vvt_fields = get_vvt_field_names(settings)
    extraction = await normalize_vvt(raw_text, language=case_lang, field_names=vvt_fields)

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
    Get stored DSB summary report for the case. Returns 404 if no report exists.
    format=json (with report_stale, stale_reason) or format=markdown (download).
    """
    result = await db.execute(select(CaseModel).where(CaseModel.id == case_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Case not found")
    report_row = await get_latest_report(case_id, db)
    if not report_row:
        raise HTTPException(status_code=404, detail="No report available. Generate a report first.")
    report = _payload_to_report(report_row.payload)
    result = await db.execute(
        select(CaseModel).where(CaseModel.id == case_id).options(selectinload(CaseModel.documents))
    )
    case = result.scalar_one_or_none()
    current_doc_count = len(case.documents) if case else 0
    current_last_run_at = await get_last_run_checks_at(case_id, db)
    report_stale, stale_reason = compute_stale(report_row, current_doc_count, current_last_run_at)
    if format == "json":
        out = report.model_dump(mode="json")
        out["report_stale"] = report_stale
        out["stale_reason"] = stale_reason
        return JSONResponse(content=out)
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


@router.get("/{case_id}/dsb-report/status")
async def get_dsb_report_status(
    case_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Return status of report generation for polling: no_report, running, completed, failed."""
    result = await db.execute(select(CaseModel).where(CaseModel.id == case_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Case not found")
    report_row = await get_latest_report(case_id, db)
    job_result = await db.execute(
        select(DSBReportJobModel)
        .where(DSBReportJobModel.case_id == case_id)
        .order_by(DSBReportJobModel.created_at.desc())
        .limit(1)
    )
    job = job_result.scalar_one_or_none()
    if job and job.status == "running":
        return {"status": "running", "job_id": str(job.id), "error": None}
    if job and job.status == "failed":
        return {"status": "failed", "job_id": str(job.id), "error": job.error}
    if report_row:
        return {"status": "completed", "job_id": None, "error": None}
    return {"status": "no_report", "job_id": None, "error": None}


@router.post("/{case_id}/dsb-report/generate")
async def generate_dsb_report(
    case_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("editor", "admin"),
):
    """Start DSB report generation. Returns 202 when queued (Celery), 200 when run synchronously."""
    result = await db.execute(select(CaseModel).where(CaseModel.id == case_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Case not found")
    use_async = settings.celery_enabled and bool((settings.celery_broker_url or "").strip())
    if use_async:
        job = DSBReportJobModel(case_id=case_id, status="running")
        db.add(job)
        await db.flush()
        await db.refresh(job)
        build_dsb_report_task.delay(str(job.id))
        return JSONResponse(
            status_code=202,
            content={"job_id": str(job.id), "status": "running", "message": "Report wird erstellt."},
        )
    report = await build_dsb_report(case_id, db)
    await save_report(case_id, report, db)
    return JSONResponse(
        status_code=200,
        content={"status": "completed", "message": "Report erstellt.", "generated_at": report.generated_at.isoformat()},
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
    format: str = Query("docx", alias="format"),
    db: AsyncSession = Depends(get_db),
):
    """Download annotated document (content + findings). Query: format=docx (default) or format=pdf."""
    try:
        if (format or "docx").lower() == "pdf":
            content, filename = await build_annotated_pdf(case_id, document_id, db)
            media_type = "application/pdf"
        else:
            content, filename = await build_annotated_docx(case_id, document_id, db)
            media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{case_id}/run-checks/status")
async def get_run_checks_status(
    case_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Return the latest run_checks job status for this case (for polling). Includes last_run activity for timeline."""
    result = await db.execute(select(CaseModel).where(CaseModel.id == case_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Case not found")
    job_result = await db.execute(
        select(RunChecksJobModel)
        .where(RunChecksJobModel.case_id == case_id)
        .order_by(RunChecksJobModel.created_at.desc())
        .limit(1)
    )
    job = job_result.scalar_one_or_none()
    activity_result = await db.execute(
        select(ActivityLogModel)
        .where(ActivityLogModel.case_id == case_id, ActivityLogModel.event_type == "run_checks")
        .order_by(ActivityLogModel.created_at.desc())
        .limit(1)
    )
    last_activity = activity_result.scalar_one_or_none()
    last_run = orm_to_activity_response(last_activity) if last_activity else None
    if not job:
        return {"status": "never_run", "job_id": None, "playbook_name": None, "findings_count": None, "error": None, "last_run": last_run}
    return {
        "status": job.status,
        "job_id": str(job.id),
        "playbook_name": job.playbook_name,
        "findings_count": job.findings_count,
        "error": job.error,
        "last_run": last_run,
    }


@router.post("/{case_id}/run-checks")
async def run_checks(
    case_id: UUID,
    body: RunChecksRequest,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("editor", "admin"),
):
    """Run playbook checks against all case documents. Returns 202 when queued (Celery), 200 with case when run synchronously."""
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

    raw_checks = playbook.content.get("checks") if isinstance(playbook.content, dict) else []
    if not raw_checks:
        await db.refresh(case)
        return CaseResponse(**orm_to_case_response(case))

    strategies = body.strategies or ["full_text"]
    use_async = settings.celery_enabled and bool((settings.celery_broker_url or "").strip())

    if use_async:
        job = RunChecksJobModel(
            case_id=case_id,
            status="running",
            playbook_id=playbook.id,
            playbook_name=playbook.name,
            strategies=strategies,
        )
        db.add(job)
        await db.flush()
        await db.refresh(job)
        celery_result = run_playbook_checks.delay(str(job.id))
        job.celery_task_id = celery_result.id
        await db.commit()
        return JSONResponse(
            status_code=202,
            content={
                "job_id": str(job.id),
                "status": "running",
                "message": "Playbook-Checks werden ausgeführt.",
            },
        )

    findings_added, errors, activity_payload = await run_checks_impl(db, case_id, body.playbook_id, strategies)
    activity = ActivityLogModel(
        case_id=case_id,
        event_type="run_checks",
        payload=activity_payload,
    )
    db.add(activity)
    await db.flush()
    result2 = await db.execute(
        select(CaseModel)
        .where(CaseModel.id == case_id)
        .options(selectinload(CaseModel.documents), selectinload(CaseModel.findings))
    )
    case = result2.scalar_one()
    return CaseResponse(**orm_to_case_response(case))
