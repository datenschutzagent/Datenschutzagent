"""Run playbook checks against case documents; used by API (sync fallback) and Celery task."""
import asyncio
from collections.abc import Awaitable, Callable
from typing import Optional
from uuid import UUID

from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models.db import CaseModel, FindingModel, LegalBaseModel, PlaybookModel
from app.services.check_runner import (
    run_check,
    run_check_rag,
    run_cross_document_check,
    run_cross_document_check_rag,
)
import logging

logger = logging.getLogger(__name__)
from app.services.weaviate_service import get_relevant_legal_base_chunks
from app.core.llm import get_llm_provider_info


def _legal_base_applicable(
    base: LegalBaseModel,
    case_department: str,
    case_case_type: str,
) -> bool:
    """True if this legal base is applicable for the given case (department, case_type, internal_only)."""
    if base.applicability == "always":
        return True
    if base.applicability != "conditional":
        return False
    if base.department_codes and case_department not in base.department_codes:
        return False
    if base.case_types and case_case_type not in base.case_types:
        return False
    if base.internal_only and case_case_type != "Innenrecht":
        return False
    return True


async def run_checks_impl(
    db: AsyncSession,
    case_id: UUID,
    playbook_id: UUID,
    strategies: list[str],
    on_check_done: Optional[Callable[[], Awaitable[None]]] = None,
    skip_resolved: bool = True,
) -> tuple[int, list[dict], dict]:
    """
    Run all playbook checks (document- and case-scoped, full_text/rag).
    Writes findings to db; does not write ActivityLog or RunChecksJob.
    on_check_done: optional async callback invoked after each individual check completes.
    skip_resolved: when True (default), findings with status accepted/fixed/overruled/in_review
        are included in the deduplication set so they are not re-opened on subsequent runs.
        Set to False only when explicitly forcing a full re-check that should ignore prior decisions.
    Returns (findings_added, errors, activity_payload).
    """
    result = await db.execute(
        select(CaseModel)
        .where(CaseModel.id == case_id)
        .options(selectinload(CaseModel.documents))
    )
    case = result.scalar_one_or_none()
    if not case:
        raise ValueError("Case not found")

    pb_result = await db.execute(select(PlaybookModel).where(PlaybookModel.id == playbook_id))
    playbook = pb_result.scalar_one_or_none()
    if not playbook:
        raise ValueError("Playbook not found")

    raw_checks = playbook.content.get("checks") if isinstance(playbook.content, dict) else []
    if not raw_checks:
        return 0, [], {}

    document_checks: list[dict] = []
    case_checks: list[dict] = []
    for item in raw_checks:
        if not isinstance(item, dict):
            continue
        scope = (item.get("scope") or item.get("type") or "document").lower()
        if scope in ("case", "cross_document"):
            case_checks.append(item)
        else:
            document_checks.append(item)

    case_language = getattr(case, "language", None) or "de"
    case_department = getattr(case, "department", None) or ""
    case_case_type = getattr(case, "case_type", None) or ""
    findings_added = 0
    rag_skipped = False
    # Logged once per run to avoid flooding the errors list with the same Weaviate message
    # for every check when RAG is globally unavailable.
    _rag_weaviate_error_logged = False
    errors: list[dict] = []

    # Semaphore begrenzt gleichzeitige LLM-Aufrufe (verhindert Überlastung / Rate-Limit-Fehler).
    _max_concurrent = getattr(settings, "max_concurrent_llm_calls", 5)
    _llm_semaphore = asyncio.Semaphore(_max_concurrent) if _max_concurrent > 0 else None

    # Load existing findings for deduplication (check_name + document_id).
    # When skip_resolved=True (default) we include all statuses so that reviewed/resolved
    # findings (accepted, fixed, overruled, in_review) are not re-created on subsequent runs.
    # When skip_resolved=False only open findings are skipped – all resolved findings will
    # be recreated (use only for explicit force-rechecks).
    dedup_where = [FindingModel.case_id == case_id]
    if not skip_resolved:
        dedup_where.append(FindingModel.status == "open")
    existing_result = await db.execute(
        select(FindingModel.check_name, FindingModel.document_id)
        .where(*dedup_where)
    )
    existing_open: set[tuple] = {(row[0], row[1]) for row in existing_result.all()}

    def _parse_uuid_list(ids: list) -> set[UUID]:
        out: set[UUID] = set()
        for x in ids or []:
            if isinstance(x, UUID):
                out.add(x)
            elif isinstance(x, str):
                try:
                    out.add(UUID(x))
                except (ValueError, TypeError):
                    pass
        return out

    playbook_content = playbook.content if isinstance(playbook.content, dict) else {}
    playbook_legal_ids_raw = playbook_content.get("legal_basis_ids") or []
    if not isinstance(playbook_legal_ids_raw, list):
        playbook_legal_ids_raw = []
    playbook_legal_ids = list(_parse_uuid_list(playbook_legal_ids_raw))

    legal_bases_by_id: dict[UUID, LegalBaseModel] = {}
    all_ref_ids = set(playbook_legal_ids)
    for item in raw_checks:
        if isinstance(item, dict):
            check_ids = item.get("legal_basis_ids")
            if isinstance(check_ids, list):
                all_ref_ids |= _parse_uuid_list(check_ids)
    if all_ref_ids:
        lb_result = await db.execute(
            select(LegalBaseModel).where(LegalBaseModel.id.in_(all_ref_ids))
        )
        for lb in lb_result.scalars().all():
            if _legal_base_applicable(lb, case_department, case_case_type):
                legal_bases_by_id[lb.id] = lb

    def _legal_base_ids_for_check(item: dict) -> list[UUID]:
        check_ids = item.get("legal_basis_ids") if isinstance(item, dict) else None
        if isinstance(check_ids, list) and check_ids:
            ids = _parse_uuid_list(check_ids)
            return [uid for uid in ids if uid in legal_bases_by_id]
        return [uid for uid in playbook_legal_ids if uid in legal_bases_by_id]

    def _legal_bases_context_for_instruction(instruction: str, legal_base_ids: list[UUID]) -> str:
        if not legal_base_ids or not instruction:
            return ""
        chunks = get_relevant_legal_base_chunks(
            legal_base_ids,
            instruction,
            top_k=settings.weaviate_legal_bases_top_k,
            include_source=True,
        )
        return "\n\n".join(chunks) if chunks else ""

    def _instruction_for_check(item: dict) -> str:
        if case_language in ("en", "de_en"):
            instr = item.get("instruction_en") or item.get("instruction") or item.get("requirement")
        else:
            instr = item.get("instruction") or item.get("requirement") or item.get("instruction_en")
        return instr or ""

    def _add_finding(
        *,
        case_id: UUID,
        document_id: UUID | None,
        check_name: str,
        category: str,
        severity: str,
        description: str,
        evidence: list,
        recommendation: str,
        source_strategy: str | None = "full_text",
    ):
        nonlocal findings_added
        # Skip if an open finding for this check+document already exists (deduplication)
        if (check_name, document_id) in existing_open:
            return
        existing_open.add((check_name, document_id))
        # Deduplicate evidence items while preserving order
        seen_evidence: set[str] = set()
        deduped_evidence: list[str] = []
        for item in (evidence or []):
            normalized = item.strip()
            if normalized and normalized not in seen_evidence:
                seen_evidence.add(normalized)
                deduped_evidence.append(normalized)
        finding = FindingModel(
            case_id=case_id,
            document_id=document_id,
            check_name=check_name,
            severity=severity,
            status="open",
            category=category,
            description=description,
            evidence=deduped_evidence,
            recommendation=recommendation or "",
            source_strategy=source_strategy,
        )
        db.add(finding)
        findings_added += 1

    async def _run_doc_check_full_text(doc_id, doc_text, item):
        name = item.get("name") or item.get("check_name") or "Check"
        category = item.get("category") or name
        instruction = _instruction_for_check(item)
        if not instruction:
            return
        lb_ids = _legal_base_ids_for_check(item)
        legal_ctx = _legal_bases_context_for_instruction(instruction, lb_ids)
        async def _do():
            try:
                check_result = await run_check(
                    doc_text, instruction, language=case_language, legal_bases_context=legal_ctx or None
                )
            except Exception as e:
                errors.append({"check": name, "scope": "document", "document_id": str(doc_id), "strategy": "full_text", "error": str(e)})
                return
            if not check_result.is_compliant:
                _add_finding(
                    case_id=case_id,
                    document_id=doc_id,
                    check_name=name,
                    category=category,
                    severity=check_result.severity,
                    description=check_result.description,
                    evidence=check_result.evidence or [],
                    recommendation=check_result.recommendation or "",
                    source_strategy="full_text",
                )
            if on_check_done:
                await on_check_done()
        if _llm_semaphore:
            async with _llm_semaphore:
                await _do()
        else:
            await _do()

    async def _run_doc_check_rag(doc_id, item):
        nonlocal rag_skipped
        name = item.get("name") or item.get("check_name") or "Check"
        category = item.get("category") or name
        instruction = _instruction_for_check(item)
        if not instruction:
            return
        lb_ids = _legal_base_ids_for_check(item)
        legal_ctx = _legal_bases_context_for_instruction(instruction, lb_ids)

        async def _do():
            nonlocal rag_skipped, _rag_weaviate_error_logged
            rag_result = None
            try:
                rag_result = await run_check_rag(
                    doc_id, case_id, instruction, language=case_language, legal_bases_context=legal_ctx or None
                )
            except Exception as e:
                errors.append({"check": name, "scope": "document", "document_id": str(doc_id), "strategy": "rag", "error": str(e)})
                rag_skipped = True
            if rag_result is None:
                # Fallback to full_text when RAG is unavailable; log Weaviate error only once per run
                rag_skipped = True
                if not _rag_weaviate_error_logged:
                    _rag_weaviate_error_logged = True
                    errors.append({"check": name, "scope": "document", "document_id": str(doc_id), "strategy": "rag", "error": "Weaviate/chunks unavailable – falling back to full_text"})
                doc_text = next((d.content or "" for d in case.documents if d.id == doc_id), "")
                try:
                    fallback_result = await run_check(
                        doc_text, instruction, language=case_language, legal_bases_context=legal_ctx or None
                    )
                    if not fallback_result.is_compliant:
                        _add_finding(
                            case_id=case_id,
                            document_id=doc_id,
                            check_name=name,
                            category=category,
                            severity=fallback_result.severity,
                            description=fallback_result.description,
                            evidence=fallback_result.evidence or [],
                            recommendation=fallback_result.recommendation or "",
                            source_strategy="full_text",
                        )
                except Exception as e2:
                    errors.append({"check": name, "scope": "document", "document_id": str(doc_id), "strategy": "rag_fallback_full_text", "error": str(e2)})
                if on_check_done:
                    await on_check_done()
                return
            if not rag_result.is_compliant:
                _add_finding(
                    case_id=case_id,
                    document_id=doc_id,
                    check_name=name,
                    category=category,
                    severity=rag_result.severity,
                    description=rag_result.description,
                    evidence=rag_result.evidence or [],
                    recommendation=rag_result.recommendation or "",
                    source_strategy="rag",
                )
            if on_check_done:
                await on_check_done()

        if _llm_semaphore:
            async with _llm_semaphore:
                await _do()
        else:
            await _do()

    # Only run checks against documents whose text extraction has completed.
    # Documents still in pending/processing/failed state have no content yet – running checks
    # on them would produce empty-text results and false-positive "compliant" verdicts.
    extractable_docs = [doc for doc in case.documents if doc.extraction_status == "done"]
    skipped_doc_count = len(case.documents) - len(extractable_docs)
    if skipped_doc_count:
        logger.warning(
            "run_checks: skipping %d document(s) with extraction_status != 'done' for case %s",
            skipped_doc_count,
            case_id,
        )

    doc_coros = []
    for doc in extractable_docs:
        text = doc.content or ""
        for item in document_checks:
            if "full_text" in strategies:
                doc_coros.append(_run_doc_check_full_text(doc.id, text, item))
            if "rag" in strategies:
                doc_coros.append(_run_doc_check_rag(doc.id, item))
    if doc_coros:
        await asyncio.gather(*doc_coros)

    if case_checks and extractable_docs:
        doc_list = [(doc.id, doc.content or "") for doc in extractable_docs]

        async def _run_case_check_full_text(item):
            name = item.get("name") or item.get("check_name") or "Check"
            category = item.get("category") or name
            instruction = _instruction_for_check(item)
            if not instruction:
                return
            lb_ids = _legal_base_ids_for_check(item)
            legal_ctx = _legal_bases_context_for_instruction(instruction, lb_ids)
            async def _do():
                try:
                    check_result = await run_cross_document_check(
                        doc_list, instruction, language=case_language, legal_bases_context=legal_ctx or None
                    )
                except Exception as e:
                    errors.append({"check": name, "scope": "case", "document_id": None, "strategy": "full_text", "error": str(e)})
                    return
                if not check_result.is_compliant:
                    _add_finding(
                        case_id=case_id,
                        document_id=None,
                        check_name=name,
                        category=category,
                        severity=check_result.severity,
                        description=check_result.description,
                        evidence=check_result.evidence or [],
                        recommendation=check_result.recommendation or "",
                        source_strategy="full_text",
                    )
                if on_check_done:
                    await on_check_done()
            if _llm_semaphore:
                async with _llm_semaphore:
                    await _do()
            else:
                await _do()

        async def _run_case_check_rag(item):
            nonlocal rag_skipped
            name = item.get("name") or item.get("check_name") or "Check"
            category = item.get("category") or name
            instruction = _instruction_for_check(item)
            if not instruction:
                return
            lb_ids = _legal_base_ids_for_check(item)
            legal_ctx = _legal_bases_context_for_instruction(instruction, lb_ids)

            async def _do():
                nonlocal rag_skipped, _rag_weaviate_error_logged
                rag_result = None
                try:
                    rag_result = await run_cross_document_check_rag(
                        case_id, instruction, language=case_language, legal_bases_context=legal_ctx or None
                    )
                except Exception as e:
                    errors.append({"check": name, "scope": "case", "document_id": None, "strategy": "rag", "error": str(e)})
                    rag_skipped = True
                if rag_result is None:
                    # Fallback to full_text when RAG is unavailable; log Weaviate error only once per run
                    rag_skipped = True
                    if not _rag_weaviate_error_logged:
                        _rag_weaviate_error_logged = True
                        errors.append({"check": name, "scope": "case", "document_id": None, "strategy": "rag", "error": "Weaviate/chunks unavailable – falling back to full_text"})
                    try:
                        fallback_result = await run_cross_document_check(
                            doc_list, instruction, language=case_language, legal_bases_context=legal_ctx or None
                        )
                        if not fallback_result.is_compliant:
                            _add_finding(
                                case_id=case_id,
                                document_id=None,
                                check_name=name,
                                category=category,
                                severity=fallback_result.severity,
                                description=fallback_result.description,
                                evidence=fallback_result.evidence or [],
                                recommendation=fallback_result.recommendation or "",
                                source_strategy="full_text",
                            )
                    except Exception as e2:
                        errors.append({"check": name, "scope": "case", "document_id": None, "strategy": "rag_fallback_full_text", "error": str(e2)})
                    if on_check_done:
                        await on_check_done()
                    return
                if not rag_result.is_compliant:
                    _add_finding(
                        case_id=case_id,
                        document_id=None,
                        check_name=name,
                        category=category,
                        severity=rag_result.severity,
                        description=rag_result.description,
                        evidence=rag_result.evidence or [],
                        recommendation=rag_result.recommendation or "",
                        source_strategy="rag",
                    )
                if on_check_done:
                    await on_check_done()

            if _llm_semaphore:
                async with _llm_semaphore:
                    await _do()
            else:
                await _do()

        case_coros = []
        for item in case_checks:
            if "full_text" in strategies:
                case_coros.append(_run_case_check_full_text(item))
            if "rag" in strategies:
                case_coros.append(_run_case_check_rag(item))
        if case_coros:
            await asyncio.gather(*case_coros)

    await db.flush()

    llm_info = get_llm_provider_info()
    activity_payload: dict = {
        "playbook_id": str(playbook_id),
        "playbook_name": playbook.name,
        "playbook_version": playbook.version,
        "llm_provider": llm_info.get("provider", settings.llm_provider),
        "model": llm_info.get("model", settings.ollama_model),
        "findings_count": findings_added,
        "strategies": strategies,
        "skip_resolved": skip_resolved,
    }
    if skipped_doc_count:
        activity_payload["skipped_unextracted_docs"] = skipped_doc_count
    if rag_skipped:
        activity_payload["rag_fallback"] = "rag requested but Weaviate/chunks unavailable for some checks"
    if errors:
        activity_payload["errors"] = errors
        activity_payload["skipped_checks_count"] = len(errors)

    return findings_added, errors, activity_payload
