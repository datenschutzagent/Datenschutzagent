"""Run playbook checks against case documents; used by API (sync fallback) and Celery task."""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models.db import CaseModel, FindingModel, PlaybookModel
from app.services.check_runner import (
    run_check,
    run_check_rag,
    run_cross_document_check,
    run_cross_document_check_rag,
)


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
    findings_added = 0
    rag_skipped = False
    errors: list[dict] = []

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
        severity: str,
        description: str,
        evidence: list,
        recommendation: str,
        source_strategy: str | None = "full_text",
    ):
        nonlocal findings_added
        finding = FindingModel(
            case_id=case_id,
            document_id=document_id,
            check_name=check_name,
            severity=severity,
            status="open",
            category=check_name,
            description=description,
            evidence=evidence or [],
            recommendation=recommendation or "",
            source_strategy=source_strategy,
        )
        db.add(finding)
        findings_added += 1

    for doc in case.documents:
        text = (doc.content or "") or ""
        for item in document_checks:
            name = item.get("name") or item.get("check_name") or "Check"
            instruction = _instruction_for_check(item)
            if not instruction:
                continue
            if "full_text" in strategies:
                try:
                    check_result = await run_check(text, instruction, language=case_language)
                except Exception as e:
                    errors.append({"check": name, "scope": "document", "document_id": str(doc.id), "strategy": "full_text", "error": str(e)})
                    continue
                if not check_result.is_compliant:
                    _add_finding(
                        case_id=case_id,
                        document_id=doc.id,
                        check_name=name,
                        severity=check_result.severity,
                        description=check_result.description,
                        evidence=check_result.evidence or [],
                        recommendation=check_result.recommendation or "",
                        source_strategy="full_text",
                    )
            if "rag" in strategies:
                try:
                    rag_result = await run_check_rag(doc.id, case_id, instruction, language=case_language)
                except Exception as e:
                    errors.append({"check": name, "scope": "document", "document_id": str(doc.id), "strategy": "rag", "error": str(e)})
                    rag_skipped = True
                    continue
                if rag_result is None:
                    rag_skipped = True
                    errors.append({"check": name, "scope": "document", "document_id": str(doc.id), "strategy": "rag", "error": "Weaviate/chunks unavailable"})
                    continue
                if not rag_result.is_compliant:
                    _add_finding(
                        case_id=case_id,
                        document_id=doc.id,
                        check_name=name,
                        severity=rag_result.severity,
                        description=rag_result.description,
                        evidence=rag_result.evidence or [],
                        recommendation=rag_result.recommendation or "",
                        source_strategy="rag",
                    )

    if case_checks and case.documents:
        doc_list = [(doc.id, (doc.content or "") or "") for doc in case.documents]
        for item in case_checks:
            name = item.get("name") or item.get("check_name") or "Check"
            instruction = _instruction_for_check(item)
            if not instruction:
                continue
            if "full_text" in strategies:
                try:
                    check_result = await run_cross_document_check(doc_list, instruction, language=case_language)
                except Exception as e:
                    errors.append({"check": name, "scope": "case", "document_id": None, "strategy": "full_text", "error": str(e)})
                    continue
                if not check_result.is_compliant:
                    _add_finding(
                        case_id=case_id,
                        document_id=None,
                        check_name=name,
                        severity=check_result.severity,
                        description=check_result.description,
                        evidence=check_result.evidence or [],
                        recommendation=check_result.recommendation or "",
                        source_strategy="full_text",
                    )
            if "rag" in strategies:
                try:
                    rag_result = await run_cross_document_check_rag(case_id, instruction, language=case_language)
                except Exception as e:
                    errors.append({"check": name, "scope": "case", "document_id": None, "strategy": "rag", "error": str(e)})
                    rag_skipped = True
                    continue
                if rag_result is None:
                    rag_skipped = True
                    errors.append({"check": name, "scope": "case", "document_id": None, "strategy": "rag", "error": "Weaviate/chunks unavailable"})
                    continue
                if not rag_result.is_compliant:
                    _add_finding(
                        case_id=case_id,
                        document_id=None,
                        check_name=name,
                        severity=rag_result.severity,
                        description=rag_result.description,
                        evidence=rag_result.evidence or [],
                        recommendation=rag_result.recommendation or "",
                        source_strategy="rag",
                    )

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
