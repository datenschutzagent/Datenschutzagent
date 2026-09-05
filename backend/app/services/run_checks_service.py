"""Run playbook checks against case documents; used by API (sync fallback) and Celery task."""

import asyncio
import contextlib
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.constants import DocumentExtractionStatus, FindingStatus
from app.core.llm import (
    LLMCallBudget,
    get_llm_provider_info,
    reset_llm_budget,
    set_llm_budget,
)
from app.models.db import CaseModel, FindingModel, LegalBaseModel, PlaybookModel
from app.services.check_runner import (
    CheckResult,
    run_check,
    run_check_rag,
    run_cross_document_check,
    run_cross_document_check_rag,
)
from app.services.query_helpers import case_relations
from app.services.weaviate_service import get_relevant_legal_base_chunks

logger = logging.getLogger(__name__)

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
    return not (base.internal_only and case_case_type != "Innenrecht")


def _parse_uuid_list(ids: list) -> set[UUID]:
    out: set[UUID] = set()
    for x in ids or []:
        if isinstance(x, UUID):
            out.add(x)
        elif isinstance(x, str):
            with contextlib.suppress(ValueError, TypeError):
                out.add(UUID(x))
    return out


def _instruction_for_check(item: dict, language: str) -> str:
    if language in ("en", "de_en"):
        instr = (
            item.get("instruction_en")
            or item.get("instruction")
            or item.get("requirement")
        )
    else:
        instr = (
            item.get("instruction")
            or item.get("requirement")
            or item.get("instruction_en")
        )
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


async def _legal_bases_context(
    legal_base_ids: list[UUID],
    instruction: str,
    top_k: int,
) -> str:
    """Retrieve legal-basis chunks for one instruction (Weaviate; runs in a thread)."""
    if not legal_base_ids or not instruction:
        return ""
    chunks = await asyncio.to_thread(
        get_relevant_legal_base_chunks,
        legal_base_ids,
        instruction,
        top_k=top_k,
        include_source=True,
    )
    return "\n\n".join(chunks) if chunks else ""


async def _legal_context_for(
    state: "_CheckRunState", lb_ids: list[UUID], instruction: str
) -> str:
    """Per-run cache: the same (legal bases, instruction) pair is needed once per check,
    not once per check × document. Concurrent callers share one in-flight lookup."""
    key = (tuple(sorted(str(u) for u in lb_ids)), instruction)
    fut = state.legal_ctx_cache.get(key)
    if fut is None:
        fut = asyncio.ensure_future(
            _legal_bases_context(
                lb_ids, instruction, settings.weaviate_legal_bases_top_k
            )
        )
        state.legal_ctx_cache[key] = fut
    try:
        return await fut
    except Exception as exc:  # noqa: BLE001 – RAG context is optional
        logger.warning("legal-bases context unavailable (%s); continuing without", exc)
        return ""


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
        dedup_where.append(FindingModel.status == FindingStatus.OPEN)
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
    lb_result = await db.execute(
        select(LegalBaseModel).where(LegalBaseModel.id.in_(all_ref_ids))
    )
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
    playbook_revision: str
    playbook_legal_ids: list[UUID]
    legal_bases_by_id: dict[UUID, LegalBaseModel]
    existing_open: set[tuple]
    on_check_done: Callable[[], Awaitable[None]] | None
    semaphore: asyncio.Semaphore | None
    timeout: float | None
    # mutated during run
    findings_added: int = 0
    rag_skipped: bool = False
    rag_weaviate_error_logged: bool = False
    errors: list[dict] = field(default_factory=list)
    legal_ctx_cache: dict[tuple, "asyncio.Future[str]"] = field(default_factory=dict)

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
        for item in evidence or []:
            normalized = item.strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                deduped.append(normalized)
        finding = FindingModel(
            case_id=self.case_id,
            document_id=document_id,
            check_name=check_name,
            severity=severity,
            status=FindingStatus.OPEN,
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
    coro: Awaitable[bool],
    label: str,
    error_scope: str,
    document_id: UUID | None,
    strategy: str,
) -> None:
    """Run a check coroutine with optional semaphore and per-check timeout.

    The coroutine must return True when the check completed successfully (LLM ran to
    completion). Progress callbacks run after the timeout window, not inside it.
    """
    completed = False

    async def _guarded() -> None:
        nonlocal completed
        try:
            if state.timeout:
                result = await asyncio.wait_for(coro, timeout=state.timeout)
            else:
                result = await coro
            completed = bool(result)
        except TimeoutError:
            logger.error("run_check timed out after %.0fs: %s", state.timeout, label)
            state.errors.append(
                {
                    "check": label,
                    "scope": error_scope,
                    "document_id": str(document_id) if document_id else None,
                    "strategy": strategy,
                    "error": f"timed out after {state.timeout}s",
                }
            )

    if state.semaphore:
        async with state.semaphore:
            await _guarded()
    else:
        await _guarded()

    if completed and state.on_check_done:
        try:
            await state.on_check_done()
        except Exception as exc:  # noqa: BLE001 – progress is non-critical
            logger.warning("Progress update failed (non-critical): %s", exc)


@dataclass(frozen=True)
class _CheckSpec:
    """One playbook check, resolved for the current case (name, instruction, legal bases)."""

    name: str
    category: str
    instruction: str
    legal_base_ids: list[UUID]


def _check_spec(state: _CheckRunState, item: dict) -> _CheckSpec | None:
    name = item.get("name") or item.get("check_name") or "Check"
    instruction = _instruction_for_check(item, state.case_language)
    if not instruction:
        logger.warning("run_checks: skipping check '%s' — no instruction", name)
        return None
    return _CheckSpec(
        name=name,
        category=item.get("category") or name,
        instruction=instruction,
        legal_base_ids=_legal_base_ids_for_check(
            item, state.playbook_legal_ids, state.legal_bases_by_id
        ),
    )


@dataclass(frozen=True)
class _CheckTarget:
    """What a check runs against: a single document or the whole case.

    The four former variants (document/case × full_text/rag) differed only in which
    ``check_runner`` function they called and how they labelled errors; both live here.
    """

    scope: str  # "document" | "case"
    document_id: UUID | None = None
    text: str = ""
    documents: list[tuple[UUID, str]] = field(default_factory=list)

    @classmethod
    def for_document(cls, document_id: UUID, text: str) -> "_CheckTarget":
        return cls(scope="document", document_id=document_id, text=text)

    @classmethod
    def for_case(cls, documents: list[tuple[UUID, str]]) -> "_CheckTarget":
        return cls(scope="case", documents=documents)

    def describe(self) -> str:
        return f" doc={self.document_id}" if self.document_id else ""

    async def run_full_text(
        self, state: _CheckRunState, instruction: str, legal_ctx: str
    ) -> CheckResult:
        if self.scope == "document":
            return await run_check(
                self.text,
                instruction,
                language=state.case_language,
                legal_bases_context=legal_ctx or None,
                case_id=state.case_id,
                playbook_revision=state.playbook_revision,
            )
        return await run_cross_document_check(
            self.documents,
            instruction,
            language=state.case_language,
            legal_bases_context=legal_ctx or None,
            case_id=state.case_id,
            playbook_revision=state.playbook_revision,
        )

    async def run_rag(
        self, state: _CheckRunState, instruction: str, legal_ctx: str
    ) -> CheckResult | None:
        if self.scope == "document":
            assert self.document_id is not None
            return await run_check_rag(
                self.document_id,
                state.case_id,
                instruction,
                language=state.case_language,
                legal_bases_context=legal_ctx or None,
                playbook_revision=state.playbook_revision,
            )
        return await run_cross_document_check_rag(
            state.case_id,
            instruction,
            language=state.case_language,
            legal_bases_context=legal_ctx or None,
            playbook_revision=state.playbook_revision,
        )


def _record_error(
    state: _CheckRunState,
    spec: _CheckSpec,
    target: _CheckTarget,
    strategy: str,
    error: str,
) -> None:
    state.errors.append(
        {
            "check": spec.name,
            "scope": target.scope,
            "document_id": str(target.document_id) if target.document_id else None,
            "strategy": strategy,
            "error": error,
        }
    )


def _apply_result(
    state: _CheckRunState,
    spec: _CheckSpec,
    target: _CheckTarget,
    result: CheckResult,
    source_strategy: str,
) -> None:
    if result.is_compliant:
        return
    state.add_finding(
        document_id=target.document_id,
        check_name=spec.name,
        category=spec.category,
        severity=result.severity,
        description=result.description,
        evidence=result.evidence or [],
        recommendation=result.recommendation or "",
        source_strategy=source_strategy,
    )


async def _run_full_text(
    state: _CheckRunState,
    spec: _CheckSpec,
    target: _CheckTarget,
    legal_ctx: str,
    *,
    error_strategy: str = "full_text",
) -> bool:
    """Full-text check; ``error_strategy`` labels errors raised on the RAG fallback path."""
    label = f"{target.scope}/{error_strategy}"
    logger.info("run_check [%s] start: '%s'%s", label, spec.name, target.describe())
    t_chk = time.monotonic()
    try:
        result = await target.run_full_text(state, spec.instruction, legal_ctx)
    except Exception as exc:  # noqa: BLE001 – recorded per check, run continues
        logger.error(
            "run_check [%s] error: '%s'%s: %s", label, spec.name, target.describe(), exc
        )
        _record_error(state, spec, target, error_strategy, str(exc))
        return False
    logger.info(
        "run_check [%s] done: '%s'%s compliant=%s elapsed=%.2fs",
        label,
        spec.name,
        target.describe(),
        result.is_compliant,
        round(time.monotonic() - t_chk, 2),
    )
    _apply_result(state, spec, target, result, "full_text")
    return True


async def _run_rag(
    state: _CheckRunState, spec: _CheckSpec, target: _CheckTarget, legal_ctx: str
) -> bool:
    """RAG check with full-text fallback when Weaviate/chunks are unavailable."""
    label = f"{target.scope}/rag"
    logger.info("run_check [%s] start: '%s'%s", label, spec.name, target.describe())
    t_chk = time.monotonic()
    rag_result: CheckResult | None = None
    try:
        rag_result = await target.run_rag(state, spec.instruction, legal_ctx)
    except Exception as exc:  # noqa: BLE001 – recorded per check, falls back
        logger.error(
            "run_check [%s] error: '%s'%s: %s", label, spec.name, target.describe(), exc
        )
        _record_error(state, spec, target, "rag", str(exc))
        state.rag_skipped = True
    if rag_result is None:
        state.rag_skipped = True
        logger.warning(
            "run_check [%s] fallback to full_text: '%s'%s",
            label,
            spec.name,
            target.describe(),
        )
        # Report the degraded mode once per run, not once per check.
        if not state.rag_weaviate_error_logged:
            state.rag_weaviate_error_logged = True
            _record_error(
                state,
                spec,
                target,
                "rag",
                "Weaviate/chunks unavailable – falling back to full_text",
            )
        return await _run_full_text(
            state, spec, target, legal_ctx, error_strategy="rag_fallback_full_text"
        )
    logger.info(
        "run_check [%s] done: '%s'%s compliant=%s elapsed=%.2fs",
        label,
        spec.name,
        target.describe(),
        rag_result.is_compliant,
        round(time.monotonic() - t_chk, 2),
    )
    _apply_result(state, spec, target, rag_result, "rag")
    return True


async def _execute_check(
    state: _CheckRunState, target: _CheckTarget, item: dict, strategy: str
) -> None:
    """Run one playbook check against one target with the given strategy."""
    spec = _check_spec(state, item)
    if spec is None:
        return
    legal_ctx = await _legal_context_for(state, spec.legal_base_ids, spec.instruction)
    if strategy == "rag":
        coro = _run_rag(state, spec, target, legal_ctx)
    else:
        coro = _run_full_text(state, spec, target, legal_ctx)
    await _run_with_limits(
        state, coro, spec.name, target.scope, target.document_id, strategy
    )


def _dispatch(
    state: _CheckRunState,
    targets: list[_CheckTarget],
    checks: list[dict],
    strategies: list[str],
) -> list[Awaitable[None]]:
    """Cartesian product target × check × requested strategy, in a stable order."""
    return [
        _execute_check(state, target, item, strategy)
        for target in targets
        for item in checks
        for strategy in ("full_text", "rag")
        if strategy in strategies
    ]


async def _run_batch(
    state: _CheckRunState, label: str, coros: list[Awaitable[None]]
) -> None:
    logger.info(
        "run_checks_impl: dispatching %s checks",
        label,
        extra={"case_id": str(state.case_id), "coroutine_count": len(coros)},
    )
    if not coros:
        return
    t_batch = time.monotonic()
    await asyncio.gather(*coros)
    logger.info(
        "run_checks_impl: %s checks completed",
        label,
        extra={
            "case_id": str(state.case_id),
            "coroutine_count": len(coros),
            "elapsed_seconds": round(time.monotonic() - t_batch, 2),
            "findings_so_far": state.findings_added,
        },
    )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def _partition_checks(raw_checks: list) -> tuple[list[dict], list[dict]]:
    """Split playbook checks into document-scoped and case-scoped lists."""
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
    return document_checks, case_checks


def _referenced_legal_base_ids(
    playbook_content: dict, raw_checks: list
) -> tuple[list[UUID], set[UUID]]:
    """(playbook-level legal base ids, all ids referenced by playbook or any check)."""
    playbook_legal_ids = list(
        _parse_uuid_list(playbook_content.get("legal_basis_ids") or [])
    )
    all_ref_ids: set[UUID] = set(playbook_legal_ids)
    for item in raw_checks:
        if isinstance(item, dict):
            check_ids = item.get("legal_basis_ids")
            if isinstance(check_ids, list):
                all_ref_ids |= _parse_uuid_list(check_ids)
    return playbook_legal_ids, all_ref_ids


async def _load_case_and_playbook(
    db: AsyncSession, case_id: UUID, playbook_id: UUID
) -> tuple[CaseModel, PlaybookModel]:
    result = await db.execute(
        select(CaseModel)
        .where(CaseModel.id == case_id)
        .options(*case_relations(findings=False))
    )
    case = result.scalar_one_or_none()
    if not case:
        raise ValueError("Case not found")
    pb_result = await db.execute(
        select(PlaybookModel).where(PlaybookModel.id == playbook_id)
    )
    playbook = pb_result.scalar_one_or_none()
    if not playbook:
        raise ValueError("Playbook not found")
    return case, playbook


def _build_activity_payload(
    state: _CheckRunState,
    playbook: PlaybookModel,
    *,
    strategies: list[str],
    skip_resolved: bool,
    budget: LLMCallBudget,
    skipped_doc_count: int,
) -> dict:
    llm_info = get_llm_provider_info()
    payload: dict = {
        "llm_calls": budget.used,
        "playbook_id": str(playbook.id),
        "playbook_name": playbook.name,
        "playbook_version": playbook.version,
        "llm_provider": llm_info.get("provider", settings.llm_provider),
        "model": llm_info.get("model", settings.ollama_model),
        "findings_count": state.findings_added,
        "strategies": strategies,
        "skip_resolved": skip_resolved,
    }
    if skipped_doc_count:
        payload["skipped_unextracted_docs"] = skipped_doc_count
    # Always record RAG availability so monitoring dashboards can detect degraded mode
    # without having to parse the error list.
    payload["rag_available"] = not state.rag_skipped if "rag" in strategies else None
    if state.rag_skipped:
        payload["rag_fallback"] = (
            "rag requested but Weaviate/chunks unavailable for some checks"
        )
    if budget.exhausted:
        payload["llm_budget_exhausted"] = True
        logger.error(
            "run_checks_impl: LLM call budget exhausted (%d calls) – remaining checks "
            "were skipped; raise RUN_CHECKS_MAX_LLM_CALLS or reduce fragments/samples",
            budget.limit,
            extra={"case_id": str(state.case_id)},
        )
    if state.errors:
        payload["errors"] = state.errors
        payload["skipped_checks_count"] = len(state.errors)
    return payload


async def run_checks_impl(
    db: AsyncSession,
    case_id: UUID,
    playbook_id: UUID,
    strategies: list[str],
    on_check_done: Callable[[], Awaitable[None]] | None = None,
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
    logger.info(
        "run_checks_impl: starting",
        extra={
            "case_id": str(case_id),
            "playbook_id": str(playbook_id),
            "strategies": strategies,
            "skip_resolved": skip_resolved,
        },
    )
    case, playbook = await _load_case_and_playbook(db, case_id, playbook_id)

    playbook_content = playbook.content if isinstance(playbook.content, dict) else {}
    raw_checks = playbook_content.get("checks") or []
    if not raw_checks:
        logger.warning(
            "run_checks_impl: playbook has no checks defined, returning empty",
            extra={
                "case_id": str(case_id),
                "playbook_id": str(playbook_id),
                "playbook_name": playbook.name,
            },
        )
        return 0, [], {}
    document_checks, case_checks = _partition_checks(raw_checks)
    logger.info(
        "run_checks_impl: checks parsed",
        extra={
            "case_id": str(case_id),
            "playbook_name": playbook.name,
            "total_raw_checks": len(raw_checks),
            "document_checks": len(document_checks),
            "case_checks": len(case_checks),
        },
    )

    playbook_legal_ids, all_ref_ids = _referenced_legal_base_ids(
        playbook_content, raw_checks
    )
    existing_open, legal_bases_by_id = await asyncio.gather(
        _build_existing_findings_set(db, case_id, skip_resolved),
        _load_applicable_legal_bases(
            db,
            all_ref_ids,
            getattr(case, "department", None) or "",
            getattr(case, "case_type", None) or "",
        ),
    )

    # Only documents with completed text extraction can be checked.
    extractable_docs = [
        doc
        for doc in case.documents
        if doc.extraction_status == DocumentExtractionStatus.DONE
    ]
    skipped_doc_count = len(case.documents) - len(extractable_docs)
    if skipped_doc_count:
        logger.warning(
            "run_checks: skipping %d document(s) with extraction_status != 'done' for case %s",
            skipped_doc_count,
            case_id,
        )
    logger.info(
        "run_checks_impl: document filtering complete",
        extra={
            "case_id": str(case_id),
            "total_documents": len(case.documents),
            "extractable_documents": len(extractable_docs),
            "skipped_documents": skipped_doc_count,
            "existing_dedup_findings": len(existing_open),
        },
    )

    budget = LLMCallBudget(
        getattr(settings, "run_checks_max_llm_calls", 0), label=f"run_checks {case_id}"
    )
    budget_token = set_llm_budget(budget)
    try:
        max_concurrent = getattr(settings, "max_concurrent_llm_calls", 2)
        state = _CheckRunState(
            db=db,
            case=case,
            case_id=case_id,
            case_language=getattr(case, "language", None) or "de",
            playbook_revision=f"{playbook.id}:{playbook.version}",
            playbook_legal_ids=playbook_legal_ids,
            legal_bases_by_id=legal_bases_by_id,
            existing_open=existing_open,
            on_check_done=on_check_done,
            semaphore=asyncio.Semaphore(max_concurrent) if max_concurrent > 0 else None,
            timeout=getattr(settings, "check_timeout_seconds", 180.0) or None,
        )
        doc_targets = [
            _CheckTarget.for_document(doc.id, doc.content or "")
            for doc in extractable_docs
        ]
        await _run_batch(
            state,
            "document",
            _dispatch(state, doc_targets, document_checks, strategies),
        )
        if case_checks and extractable_docs:
            case_target = _CheckTarget.for_case(
                [(doc.id, doc.content or "") for doc in extractable_docs]
            )
            await _run_batch(
                state, "case", _dispatch(state, [case_target], case_checks, strategies)
            )
        await db.flush()
    finally:
        reset_llm_budget(budget_token)

    activity_payload = _build_activity_payload(
        state,
        playbook,
        strategies=strategies,
        skip_resolved=skip_resolved,
        budget=budget,
        skipped_doc_count=skipped_doc_count,
    )
    logger.info(
        "run_checks_impl: finished",
        extra={
            "case_id": str(case_id),
            "playbook_id": str(playbook_id),
            "findings_added": state.findings_added,
            "error_count": len(state.errors),
            "rag_skipped": state.rag_skipped,
            "elapsed_seconds": round(time.monotonic() - t0, 2),
        },
    )
    return state.findings_added, state.errors, activity_payload
