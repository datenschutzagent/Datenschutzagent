"""Run playbook checks against case documents; used by API (sync fallback) and Celery task."""
import asyncio
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
) -> tuple[int, list[dict], dict]:
    """
    Run all playbook checks (document- and case-scoped, full_text/rag).
    Writes findings to db; does not write ActivityLog or RunChecksJob.
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
    errors: list[dict] = []

    # Load existing open findings for deduplication (check_name + document_id)
    existing_result = await db.execute(
        select(FindingModel.check_name, FindingModel.document_id)
        .where(FindingModel.case_id == case_id, FindingModel.status == "open")
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

    async def _run_doc_check_rag(doc_id, item):
        nonlocal rag_skipped
        name = item.get("name") or item.get("check_name") or "Check"
        category = item.get("category") or name
        instruction = _instruction_for_check(item)
        if not instruction:
            return
        lb_ids = _legal_base_ids_for_check(item)
        legal_ctx = _legal_bases_context_for_instruction(instruction, lb_ids)
        rag_result = None
        try:
            rag_result = await run_check_rag(
                doc_id, case_id, instruction, language=case_language, legal_bases_context=legal_ctx or None
            )
        except Exception as e:
            errors.append({"check": name, "scope": "document", "document_id": str(doc_id), "strategy": "rag", "error": str(e)})
            rag_skipped = True
        if rag_result is None:
            # Fallback to full_text when RAG is unavailable
            rag_skipped = True
            if "Weaviate/chunks unavailable" not in str(errors[-1].get("error", "") if errors else ""):
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

    doc_coros = []
    for doc in case.documents:
        text = (doc.content or "") or ""
        for item in document_checks:
            if "full_text" in strategies:
                doc_coros.append(_run_doc_check_full_text(doc.id, text, item))
            if "rag" in strategies:
                doc_coros.append(_run_doc_check_rag(doc.id, item))
    if doc_coros:
        await asyncio.gather(*doc_coros)

    if case_checks and case.documents:
        doc_list = [(doc.id, (doc.content or "") or "") for doc in case.documents]

        async def _run_case_check_full_text(item):
            name = item.get("name") or item.get("check_name") or "Check"
            category = item.get("category") or name
            instruction = _instruction_for_check(item)
            if not instruction:
                return
            lb_ids = _legal_base_ids_for_check(item)
            legal_ctx = _legal_bases_context_for_instruction(instruction, lb_ids)
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

        async def _run_case_check_rag(item):
            nonlocal rag_skipped
            name = item.get("name") or item.get("check_name") or "Check"
            category = item.get("category") or name
            instruction = _instruction_for_check(item)
            if not instruction:
                return
            lb_ids = _legal_base_ids_for_check(item)
            legal_ctx = _legal_bases_context_for_instruction(instruction, lb_ids)
            rag_result = None
            try:
                rag_result = await run_cross_document_check_rag(
                    case_id, instruction, language=case_language, legal_bases_context=legal_ctx or None
                )
            except Exception as e:
                errors.append({"check": name, "scope": "case", "document_id": None, "strategy": "rag", "error": str(e)})
                rag_skipped = True
            if rag_result is None:
                # Fallback to full_text when RAG is unavailable
                rag_skipped = True
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

        case_coros = []
        for item in case_checks:
            if "full_text" in strategies:
                case_coros.append(_run_case_check_full_text(item))
            if "rag" in strategies:
                case_coros.append(_run_case_check_rag(item))
        if case_coros:
            await asyncio.gather(*case_coros)

    await db.flush()

    activity_payload: dict = {
        "playbook_id": str(playbook_id),
        "playbook_name": playbook.name,
        "playbook_version": playbook.version,
        "model": settings.ollama_model,
        "findings_count": findings_added,
        "strategies": strategies,
    }
    if rag_skipped:
        activity_payload["rag_fallback"] = "rag requested but Weaviate/chunks unavailable for some checks"
    if errors:
        activity_payload["errors"] = errors
        activity_payload["skipped_checks_count"] = len(errors)

    return findings_added, errors, activity_payload
