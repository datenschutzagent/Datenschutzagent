"""Run playbook checks against case documents; used by API (sync fallback) and Celery task."""
import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Optional
from uuid import UUID

from sqlalchemy import select
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


# ---------------------------------------------------------------------------
# Module-level pure helpers
# ---------------------------------------------------------------------------

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


def _instruction_for_check(item: dict, language: str) -> str:
    if language in ("en", "de_en"):
        instr = item.get("instruction_en") or item.get("instruction") or item.get("requirement")
    else:
        instr = item.get("instruction") or item.get("requirement") or item.get("instruction_en")
    return instr or ""


def _legal_base_ids_for_check(
    item: dict,
    playbook_legal_ids: list[UUID],
    legal_bases_by_id: dict[UUID, LegalBaseModel],
) -> list[UUID]:
    check_ids = item.get("legal_basis_ids") if isinstance(item, dict) else None
    if isinstance(check_ids, list) and check_ids:
        ids = _parse_uuid_list(check_ids)
        return [uid for uid in ids if uid in legal_bases_by_id]
    return [uid for uid in playbook_legal_ids if uid in legal_bases_by_id]


def _legal_bases_context(
    legal_base_ids: list[UUID],
    instruction: str,
    top_k: int,
) -> str:
    if not legal_base_ids or not instruction:
        return ""
    chunks = get_relevant_legal_base_chunks(legal_base_ids, instruction, top_k=top_k, include_source=True)
    return "\n\n".join(chunks) if chunks else ""


# ---------------------------------------------------------------------------
# Async DB helpers
# ---------------------------------------------------------------------------

async def _build_existing_findings_set(
    db: AsyncSession,
    case_id: UUID,
    skip_resolved: bool,
) -> set[tuple]:
    """Load existing (check_name, document_id) pairs for deduplication."""
    dedup_where = [FindingModel.case_id == case_id]
    if not skip_resolved:
        dedup_where.append(FindingModel.status == "open")
    result = await db.execute(
        select(FindingModel.check_name, FindingModel.document_id).where(*dedup_where)
    )
    return {(row[0], row[1]) for row in result.all()}


async def _load_applicable_legal_bases(
    db: AsyncSession,
    all_ref_ids: set[UUID],
    case_department: str,
    case_case_type: str,
) -> dict[UUID, LegalBaseModel]:
    """Load legal bases referenced by the playbook/checks, filtered by case applicability."""
    if not all_ref_ids:
        return {}
    lb_result = await db.execute(select(LegalBaseModel).where(LegalBaseModel.id.in_(all_ref_ids)))
    return {
        lb.id: lb
        for lb in lb_result.scalars().all()
        if _legal_base_applicable(lb, case_department, case_case_type)
    }


# ---------------------------------------------------------------------------
# Shared mutable state for a single run
# ---------------------------------------------------------------------------

@dataclass
class _CheckRunState:
    db: AsyncSession
    case: CaseModel
    case_id: UUID
    case_language: str
    playbook_legal_ids: list[UUID]
    legal_bases_by_id: dict[UUID, LegalBaseModel]
    existing_open: set[tuple]
    on_check_done: Optional[Callable[[], Awaitable[None]]]
    semaphore: asyncio.Semaphore | None
    timeout: float | None
    # mutated during run
    findings_added: int = 0
    rag_skipped: bool = False
    rag_weaviate_error_logged: bool = False
    errors: list[dict] = field(default_factory=list)

    def add_finding(
        self,
        *,
        document_id: UUID | None,
        check_name: str,
        category: str,
        severity: str,
        description: str,
        evidence: list,
        recommendation: str,
        source_strategy: str | None = "full_text",
    ) -> None:
        if (check_name, document_id) in self.existing_open:
            return
        self.existing_open.add((check_name, document_id))
        seen: set[str] = set()
        deduped: list[str] = []
        for item in (evidence or []):
            normalized = item.strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                deduped.append(normalized)
        finding = FindingModel(
            case_id=self.case_id,
            document_id=document_id,
            check_name=check_name,
            severity=severity,
            status="open",
            category=category,
            description=description,
            evidence=deduped,
            recommendation=recommendation or "",
            source_strategy=source_strategy,
        )
        self.db.add(finding)
        self.findings_added += 1


# ---------------------------------------------------------------------------
# Per-check execution helpers
# ---------------------------------------------------------------------------

async def _run_with_limits(
    state: _CheckRunState,
    coro: Awaitable,
    label: str,
    error_scope: str,
    document_id: UUID | None,
    strategy: str,
) -> None:
    """Run a coroutine with optional semaphore and per-check timeout."""
    async def _guarded():
        try:
            if state.timeout:
                await asyncio.wait_for(coro, timeout=state.timeout)
            else:
                await coro
        except TimeoutError:
            logger.error("run_check timed out after %.0fs: %s", state.timeout, label)
            state.errors.append({
                "check": label, "scope": error_scope,
                "document_id": str(document_id) if document_id else None,
                "strategy": strategy, "error": f"timed out after {state.timeout}s",
            })
            if state.on_check_done:
                await state.on_check_done()

    if state.semaphore:
        async with state.semaphore:
            await _guarded()
    else:
        await _guarded()


async def _doc_check_full_text(state: _CheckRunState, doc_id: UUID, doc_text: str, item: dict) -> None:
    name = item.get("name") or item.get("check_name") or "Check"
    category = item.get("category") or name
    instruction = _instruction_for_check(item, state.case_language)
    if not instruction:
        logger.warning("run_checks: skipping check '%s' — no instruction", name)
        return
    lb_ids = _legal_base_ids_for_check(item, state.playbook_legal_ids, state.legal_bases_by_id)
    legal_ctx = _legal_bases_context(lb_ids, instruction, settings.weaviate_legal_bases_top_k)

    async def _execute():
        logger.info("run_check [full_text] start: '%s' doc=%s", name, doc_id)
        t_chk = time.monotonic()
        try:
            result = await run_check(doc_text, instruction, language=state.case_language, legal_bases_context=legal_ctx or None)
        except Exception as e:
            logger.error("run_check [full_text] error: '%s' doc=%s: %s", name, doc_id, e)
            state.errors.append({"check": name, "scope": "document", "document_id": str(doc_id), "strategy": "full_text", "error": str(e)})
            return
        elapsed_chk = round(time.monotonic() - t_chk, 2)
        logger.info("run_check [full_text] done: '%s' doc=%s compliant=%s elapsed=%.2fs", name, doc_id, result.is_compliant, elapsed_chk)
        if not result.is_compliant:
            state.add_finding(
                document_id=doc_id, check_name=name, category=category,
                severity=result.severity, description=result.description,
                evidence=result.evidence or [], recommendation=result.recommendation or "",
                source_strategy="full_text",
            )
        if state.on_check_done:
            await state.on_check_done()

    await _run_with_limits(state, _execute(), name, "document", doc_id, "full_text")


async def _doc_check_rag(state: _CheckRunState, doc_id: UUID, item: dict) -> None:
    name = item.get("name") or item.get("check_name") or "Check"
    category = item.get("category") or name
    instruction = _instruction_for_check(item, state.case_language)
    if not instruction:
        logger.warning("run_checks: skipping RAG check '%s' — no instruction", name)
        return
    lb_ids = _legal_base_ids_for_check(item, state.playbook_legal_ids, state.legal_bases_by_id)
    legal_ctx = _legal_bases_context(lb_ids, instruction, settings.weaviate_legal_bases_top_k)

    async def _execute():
        logger.info("run_check [rag] start: '%s' doc=%s", name, doc_id)
        t_chk = time.monotonic()
        rag_result = None
        try:
            rag_result = await run_check_rag(doc_id, state.case_id, instruction, language=state.case_language, legal_bases_context=legal_ctx or None)
        except Exception as e:
            logger.error("run_check [rag] error: '%s' doc=%s: %s", name, doc_id, e)
            state.errors.append({"check": name, "scope": "document", "document_id": str(doc_id), "strategy": "rag", "error": str(e)})
            state.rag_skipped = True
        if rag_result is None:
            state.rag_skipped = True
            logger.warning("run_check [rag] fallback to full_text: '%s' doc=%s", name, doc_id)
            if not state.rag_weaviate_error_logged:
                state.rag_weaviate_error_logged = True
                state.errors.append({"check": name, "scope": "document", "document_id": str(doc_id), "strategy": "rag", "error": "Weaviate/chunks unavailable – falling back to full_text"})
            doc_text = next((d.content or "" for d in state.case.documents if d.id == doc_id), "")
            try:
                fallback = await run_check(doc_text, instruction, language=state.case_language, legal_bases_context=legal_ctx or None)
                if not fallback.is_compliant:
                    state.add_finding(
                        document_id=doc_id, check_name=name, category=category,
                        severity=fallback.severity, description=fallback.description,
                        evidence=fallback.evidence or [], recommendation=fallback.recommendation or "",
                        source_strategy="full_text",
                    )
            except Exception as e2:
                state.errors.append({"check": name, "scope": "document", "document_id": str(doc_id), "strategy": "rag_fallback_full_text", "error": str(e2)})
            logger.info("run_check [rag→full_text] done: '%s' doc=%s elapsed=%.2fs", name, doc_id, round(time.monotonic() - t_chk, 2))
            if state.on_check_done:
                await state.on_check_done()
            return
        logger.info("run_check [rag] done: '%s' doc=%s compliant=%s elapsed=%.2fs", name, doc_id, rag_result.is_compliant, round(time.monotonic() - t_chk, 2))
        if not rag_result.is_compliant:
            state.add_finding(
                document_id=doc_id, check_name=name, category=category,
                severity=rag_result.severity, description=rag_result.description,
                evidence=rag_result.evidence or [], recommendation=rag_result.recommendation or "",
                source_strategy="rag",
            )
        if state.on_check_done:
            await state.on_check_done()

    await _run_with_limits(state, _execute(), name, "document", doc_id, "rag")


async def _case_check_full_text(state: _CheckRunState, doc_list: list[tuple], item: dict) -> None:
    name = item.get("name") or item.get("check_name") or "Check"
    category = item.get("category") or name
    instruction = _instruction_for_check(item, state.case_language)
    if not instruction:
        logger.warning("run_checks: skipping case check '%s' — no instruction", name)
        return
    lb_ids = _legal_base_ids_for_check(item, state.playbook_legal_ids, state.legal_bases_by_id)
    legal_ctx = _legal_bases_context(lb_ids, instruction, settings.weaviate_legal_bases_top_k)

    async def _execute():
        logger.info("run_check [case/full_text] start: '%s'", name)
        t_chk = time.monotonic()
        try:
            result = await run_cross_document_check(doc_list, instruction, language=state.case_language, legal_bases_context=legal_ctx or None)
        except Exception as e:
            logger.error("run_check [case/full_text] error: '%s': %s", name, e)
            state.errors.append({"check": name, "scope": "case", "document_id": None, "strategy": "full_text", "error": str(e)})
            return
        logger.info("run_check [case/full_text] done: '%s' compliant=%s elapsed=%.2fs", name, result.is_compliant, round(time.monotonic() - t_chk, 2))
        if not result.is_compliant:
            state.add_finding(
                document_id=None, check_name=name, category=category,
                severity=result.severity, description=result.description,
                evidence=result.evidence or [], recommendation=result.recommendation or "",
                source_strategy="full_text",
            )
        if state.on_check_done:
            await state.on_check_done()

    await _run_with_limits(state, _execute(), name, "case", None, "full_text")


async def _case_check_rag(state: _CheckRunState, doc_list: list[tuple], item: dict) -> None:
    name = item.get("name") or item.get("check_name") or "Check"
    category = item.get("category") or name
    instruction = _instruction_for_check(item, state.case_language)
    if not instruction:
        logger.warning("run_checks: skipping case RAG check '%s' — no instruction", name)
        return
    lb_ids = _legal_base_ids_for_check(item, state.playbook_legal_ids, state.legal_bases_by_id)
    legal_ctx = _legal_bases_context(lb_ids, instruction, settings.weaviate_legal_bases_top_k)

    async def _execute():
        logger.info("run_check [case/rag] start: '%s'", name)
        t_chk = time.monotonic()
        rag_result = None
        try:
            rag_result = await run_cross_document_check_rag(state.case_id, instruction, language=state.case_language, legal_bases_context=legal_ctx or None)
        except Exception as e:
            logger.error("run_check [case/rag] error: '%s': %s", name, e)
            state.errors.append({"check": name, "scope": "case", "document_id": None, "strategy": "rag", "error": str(e)})
            state.rag_skipped = True
        if rag_result is None:
            state.rag_skipped = True
            logger.warning("run_check [case/rag] fallback to full_text: '%s'", name)
            if not state.rag_weaviate_error_logged:
                state.rag_weaviate_error_logged = True
                state.errors.append({"check": name, "scope": "case", "document_id": None, "strategy": "rag", "error": "Weaviate/chunks unavailable – falling back to full_text"})
            try:
                fallback = await run_cross_document_check(doc_list, instruction, language=state.case_language, legal_bases_context=legal_ctx or None)
                if not fallback.is_compliant:
                    state.add_finding(
                        document_id=None, check_name=name, category=category,
                        severity=fallback.severity, description=fallback.description,
                        evidence=fallback.evidence or [], recommendation=fallback.recommendation or "",
                        source_strategy="full_text",
                    )
            except Exception as e2:
                state.errors.append({"check": name, "scope": "case", "document_id": None, "strategy": "rag_fallback_full_text", "error": str(e2)})
            logger.info("run_check [case/rag→full_text] done: '%s' elapsed=%.2fs", name, round(time.monotonic() - t_chk, 2))
            if state.on_check_done:
                await state.on_check_done()
            return
        logger.info("run_check [case/rag] done: '%s' compliant=%s elapsed=%.2fs", name, rag_result.is_compliant, round(time.monotonic() - t_chk, 2))
        if not rag_result.is_compliant:
            state.add_finding(
                document_id=None, check_name=name, category=category,
                severity=rag_result.severity, description=rag_result.description,
                evidence=rag_result.evidence or [], recommendation=rag_result.recommendation or "",
                source_strategy="rag",
            )
        if state.on_check_done:
            await state.on_check_done()

    await _run_with_limits(state, _execute(), name, "case", None, "rag")


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

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
    t0 = time.monotonic()
    logger.info("run_checks_impl: starting", extra={"case_id": str(case_id), "playbook_id": str(playbook_id), "strategies": strategies, "skip_resolved": skip_resolved})

    result = await db.execute(select(CaseModel).where(CaseModel.id == case_id).options(selectinload(CaseModel.documents)))
    case = result.scalar_one_or_none()
    if not case:
        raise ValueError("Case not found")

    pb_result = await db.execute(select(PlaybookModel).where(PlaybookModel.id == playbook_id))
    playbook = pb_result.scalar_one_or_none()
    if not playbook:
        raise ValueError("Playbook not found")

    raw_checks = playbook.content.get("checks") if isinstance(playbook.content, dict) else []
    if not raw_checks:
        logger.warning("run_checks_impl: playbook has no checks defined, returning empty", extra={"case_id": str(case_id), "playbook_id": str(playbook_id), "playbook_name": playbook.name})
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

    logger.info("run_checks_impl: checks parsed", extra={"case_id": str(case_id), "playbook_name": playbook.name, "total_raw_checks": len(raw_checks), "document_checks": len(document_checks), "case_checks": len(case_checks)})

    case_language = getattr(case, "language", None) or "de"
    case_department = getattr(case, "department", None) or ""
    case_case_type = getattr(case, "case_type", None) or ""

    # Collect all legal base IDs referenced by the playbook and individual checks
    playbook_content = playbook.content if isinstance(playbook.content, dict) else {}
    playbook_legal_ids = list(_parse_uuid_list(playbook_content.get("legal_basis_ids") or []))
    all_ref_ids: set[UUID] = set(playbook_legal_ids)
    for item in raw_checks:
        if isinstance(item, dict):
            check_ids = item.get("legal_basis_ids")
            if isinstance(check_ids, list):
                all_ref_ids |= _parse_uuid_list(check_ids)

    existing_open, legal_bases_by_id = await asyncio.gather(
        _build_existing_findings_set(db, case_id, skip_resolved),
        _load_applicable_legal_bases(db, all_ref_ids, case_department, case_case_type),
    )

    _max_concurrent = getattr(settings, "max_concurrent_llm_calls", 2)
    state = _CheckRunState(
        db=db,
        case=case,
        case_id=case_id,
        case_language=case_language,
        playbook_legal_ids=playbook_legal_ids,
        legal_bases_by_id=legal_bases_by_id,
        existing_open=existing_open,
        on_check_done=on_check_done,
        semaphore=asyncio.Semaphore(_max_concurrent) if _max_concurrent > 0 else None,
        timeout=getattr(settings, "check_timeout_seconds", 180.0) or None,
    )

    # Filter to only documents with completed text extraction
    extractable_docs = [doc for doc in case.documents if doc.extraction_status == "done"]
    skipped_doc_count = len(case.documents) - len(extractable_docs)
    if skipped_doc_count:
        logger.warning("run_checks: skipping %d document(s) with extraction_status != 'done' for case %s", skipped_doc_count, case_id)
    logger.info("run_checks_impl: document filtering complete", extra={"case_id": str(case_id), "total_documents": len(case.documents), "extractable_documents": len(extractable_docs), "skipped_documents": skipped_doc_count, "existing_dedup_findings": len(existing_open)})

    # Dispatch document-scoped checks
    doc_coros = []
    for doc in extractable_docs:
        for item in document_checks:
            if "full_text" in strategies:
                doc_coros.append(_doc_check_full_text(state, doc.id, doc.content or "", item))
            if "rag" in strategies:
                doc_coros.append(_doc_check_rag(state, doc.id, item))
    logger.info("run_checks_impl: dispatching document checks", extra={"case_id": str(case_id), "doc_coroutine_count": len(doc_coros)})
    if doc_coros:
        t_doc = time.monotonic()
        await asyncio.gather(*doc_coros)
        logger.info("run_checks_impl: document checks completed", extra={"case_id": str(case_id), "doc_coroutine_count": len(doc_coros), "elapsed_seconds": round(time.monotonic() - t_doc, 2), "findings_so_far": state.findings_added})

    # Dispatch case-scoped checks
    if case_checks and extractable_docs:
        doc_list = [(doc.id, doc.content or "") for doc in extractable_docs]
        case_coros = []
        for item in case_checks:
            if "full_text" in strategies:
                case_coros.append(_case_check_full_text(state, doc_list, item))
            if "rag" in strategies:
                case_coros.append(_case_check_rag(state, doc_list, item))
        logger.info("run_checks_impl: dispatching case checks", extra={"case_id": str(case_id), "case_coroutine_count": len(case_coros)})
        if case_coros:
            t_case = time.monotonic()
            await asyncio.gather(*case_coros)
            logger.info("run_checks_impl: case checks completed", extra={"case_id": str(case_id), "case_coroutine_count": len(case_coros), "elapsed_seconds": round(time.monotonic() - t_case, 2), "findings_so_far": state.findings_added})

    await db.flush()

    llm_info = get_llm_provider_info()
    activity_payload: dict = {
        "playbook_id": str(playbook_id),
        "playbook_name": playbook.name,
        "playbook_version": playbook.version,
        "llm_provider": llm_info.get("provider", settings.llm_provider),
        "model": llm_info.get("model", settings.ollama_model),
        "findings_count": state.findings_added,
        "strategies": strategies,
        "skip_resolved": skip_resolved,
    }
    if skipped_doc_count:
        activity_payload["skipped_unextracted_docs"] = skipped_doc_count
    if state.rag_skipped:
        activity_payload["rag_fallback"] = "rag requested but Weaviate/chunks unavailable for some checks"
    if state.errors:
        activity_payload["errors"] = state.errors
        activity_payload["skipped_checks_count"] = len(state.errors)

    logger.info("run_checks_impl: finished", extra={"case_id": str(case_id), "playbook_id": str(playbook_id), "findings_added": state.findings_added, "error_count": len(state.errors), "rag_skipped": state.rag_skipped, "elapsed_seconds": round(time.monotonic() - t0, 2)})
    return state.findings_added, state.errors, activity_payload
