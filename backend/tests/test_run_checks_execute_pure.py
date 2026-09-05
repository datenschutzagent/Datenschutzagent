"""Pure tests for the unified check execution in run_checks_service.

``_execute_check`` replaced four near-identical document/case × full_text/rag
variants (Qualitätsplan Phase 2 R7). These tests pin the behaviour the variants
shared: finding creation, error labelling, and the RAG → full-text fallback.
No DB, LLM or Weaviate: the check_runner entry points are monkeypatched.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services import run_checks_service as rcs
from app.services.check_runner import CheckResult
from app.services.run_checks_service import _CheckRunState, _CheckTarget

DOC_ID = uuid.uuid4()
CHECK = {"name": "Rechtsgrundlage", "category": "Art. 6", "instruction": "Prüfe X"}


def _state(**overrides) -> _CheckRunState:
    kwargs: dict = {
        "db": MagicMock(),
        "case": SimpleNamespace(documents=[]),
        "case_id": uuid.uuid4(),
        "case_language": "de",
        "playbook_revision": "pb:1",
        "playbook_legal_ids": [],
        "legal_bases_by_id": {},
        "existing_open": set(),
        "on_check_done": None,
        "semaphore": None,
        "timeout": None,
    }
    kwargs.update(overrides)
    return _CheckRunState(**kwargs)


def _result(compliant: bool) -> CheckResult:
    return CheckResult(
        is_compliant=compliant,
        severity="info" if compliant else "high",
        description="desc",
        evidence=["quote", "quote", " "],
        recommendation="fix",
        confidence=0.9,
    )


def _added_findings(state: _CheckRunState) -> list:
    return [call.args[0] for call in state.db.add.call_args_list]


async def test_full_text_non_compliant_adds_finding(monkeypatch):
    calls = []

    async def _run_check(text, instruction, **kwargs):
        calls.append((text, instruction, kwargs))
        return _result(False)

    monkeypatch.setattr(rcs, "run_check", _run_check)
    state = _state()
    target = _CheckTarget.for_document(DOC_ID, "Dokumenttext")

    await rcs._execute_check(state, target, CHECK, "full_text")

    assert calls[0][0] == "Dokumenttext" and calls[0][1] == "Prüfe X"
    assert calls[0][2]["playbook_revision"] == "pb:1"
    (finding,) = _added_findings(state)
    assert finding.document_id == DOC_ID
    assert finding.check_name == "Rechtsgrundlage"
    assert finding.category == "Art. 6"
    assert finding.source_strategy == "full_text"
    assert finding.evidence == ["quote"]  # deduplicated, blanks dropped
    assert state.findings_added == 1
    assert state.errors == []


async def test_full_text_compliant_adds_nothing(monkeypatch):
    async def _run_check(*args, **kwargs):
        return _result(True)

    monkeypatch.setattr(rcs, "run_check", _run_check)
    state = _state()
    await rcs._execute_check(
        state, _CheckTarget.for_document(DOC_ID, "t"), CHECK, "full_text"
    )
    assert _added_findings(state) == []
    assert state.findings_added == 0


async def test_case_scope_uses_cross_document_runner(monkeypatch):
    seen = {}

    async def _cross(documents, instruction, **kwargs):
        seen["documents"] = documents
        return _result(False)

    monkeypatch.setattr(rcs, "run_cross_document_check", _cross)
    state = _state()
    docs = [(DOC_ID, "a"), (uuid.uuid4(), "b")]
    await rcs._execute_check(state, _CheckTarget.for_case(docs), CHECK, "full_text")

    assert seen["documents"] == docs
    (finding,) = _added_findings(state)
    assert finding.document_id is None


async def test_full_text_error_is_recorded_with_scope(monkeypatch):
    async def _boom(*args, **kwargs):
        raise RuntimeError("llm down")

    monkeypatch.setattr(rcs, "run_check", _boom)
    progress = []

    async def _done():
        progress.append(1)

    state = _state(on_check_done=_done)
    await rcs._execute_check(
        state, _CheckTarget.for_document(DOC_ID, "t"), CHECK, "full_text"
    )

    assert state.errors == [
        {
            "check": "Rechtsgrundlage",
            "scope": "document",
            "document_id": str(DOC_ID),
            "strategy": "full_text",
            "error": "llm down",
        }
    ]
    assert progress == []  # failed checks do not count as progress
    assert _added_findings(state) == []


async def test_rag_result_is_persisted_with_rag_strategy(monkeypatch):
    async def _rag(document_id, case_id, instruction, **kwargs):
        assert document_id == DOC_ID
        return _result(False)

    monkeypatch.setattr(rcs, "run_check_rag", _rag)
    state = _state()
    await rcs._execute_check(
        state, _CheckTarget.for_document(DOC_ID, "t"), CHECK, "rag"
    )

    (finding,) = _added_findings(state)
    assert finding.source_strategy == "rag"
    assert state.rag_skipped is False
    assert state.errors == []


async def test_rag_unavailable_falls_back_to_full_text_once_reported(monkeypatch):
    async def _rag(*args, **kwargs):
        return None

    async def _full(*args, **kwargs):
        return _result(False)

    monkeypatch.setattr(rcs, "run_check_rag", _rag)
    monkeypatch.setattr(rcs, "run_check", _full)
    state = _state()
    target = _CheckTarget.for_document(DOC_ID, "t")

    await rcs._execute_check(state, target, CHECK, "rag")
    await rcs._execute_check(state, target, {**CHECK, "name": "Zweiter"}, "rag")

    findings = _added_findings(state)
    assert [f.source_strategy for f in findings] == ["full_text", "full_text"]
    assert state.rag_skipped is True
    # Degraded mode is reported once per run, not once per check.
    assert [e["error"] for e in state.errors] == [
        "Weaviate/chunks unavailable – falling back to full_text"
    ]
    assert state.errors[0]["strategy"] == "rag"


async def test_rag_exception_then_fallback_failure_records_both(monkeypatch):
    async def _rag(*args, **kwargs):
        raise ConnectionError("weaviate refused")

    async def _full(*args, **kwargs):
        raise RuntimeError("llm down")

    monkeypatch.setattr(rcs, "run_cross_document_check_rag", _rag)
    monkeypatch.setattr(rcs, "run_cross_document_check", _full)
    state = _state()
    await rcs._execute_check(
        state, _CheckTarget.for_case([(DOC_ID, "t")]), CHECK, "rag"
    )

    assert [(e["strategy"], e["error"]) for e in state.errors] == [
        ("rag", "weaviate refused"),
        ("rag", "Weaviate/chunks unavailable – falling back to full_text"),
        ("rag_fallback_full_text", "llm down"),
    ]
    assert all(e["scope"] == "case" and e["document_id"] is None for e in state.errors)
    assert state.rag_skipped is True


async def test_check_without_instruction_is_skipped(monkeypatch):
    async def _never(*args, **kwargs):
        raise AssertionError("must not be called")

    monkeypatch.setattr(rcs, "run_check", _never)
    state = _state()
    await rcs._execute_check(
        state, _CheckTarget.for_document(DOC_ID, "t"), {"name": "Leer"}, "full_text"
    )
    assert state.errors == [] and _added_findings(state) == []


async def test_dedup_against_existing_findings(monkeypatch):
    async def _run_check(*args, **kwargs):
        return _result(False)

    monkeypatch.setattr(rcs, "run_check", _run_check)
    state = _state(existing_open={("Rechtsgrundlage", DOC_ID)})
    await rcs._execute_check(
        state, _CheckTarget.for_document(DOC_ID, "t"), CHECK, "full_text"
    )
    assert _added_findings(state) == []


def test_dispatch_order_and_strategy_filter():
    state = _state()
    targets = [_CheckTarget.for_document(DOC_ID, "a"), _CheckTarget.for_case([])]
    coros = rcs._dispatch(state, targets, [CHECK, CHECK], ["rag"])
    try:
        assert len(coros) == 4  # 2 targets × 2 checks × 1 requested strategy
    finally:
        for c in coros:
            c.close()
    assert rcs._dispatch(state, targets, [CHECK], ["unknown"]) == []


def test_partition_and_legal_base_collection():
    pb_id = uuid.uuid4()
    check_id = uuid.uuid4()
    raw = [
        {"name": "a"},
        {"name": "b", "scope": "case"},
        {"name": "c", "type": "cross_document", "legal_basis_ids": [str(check_id)]},
        "garbage",
    ]
    doc_checks, case_checks = rcs._partition_checks(raw)
    assert [c["name"] for c in doc_checks] == ["a"]
    assert [c["name"] for c in case_checks] == ["b", "c"]

    playbook_ids, all_ids = rcs._referenced_legal_base_ids(
        {"legal_basis_ids": [str(pb_id), "not-a-uuid"]}, raw
    )
    assert playbook_ids == [pb_id]
    assert all_ids == {pb_id, check_id}


def test_activity_payload_reports_rag_and_budget(monkeypatch):
    monkeypatch.setattr(
        rcs, "get_llm_provider_info", lambda: {"provider": "p", "model": "m"}
    )
    state = _state()
    state.findings_added = 2
    state.rag_skipped = True
    state.errors = [{"check": "x"}]
    playbook = SimpleNamespace(id=uuid.uuid4(), name="PB", version=3)
    budget = rcs.LLMCallBudget(1, label="t")
    budget.used = 1

    payload = rcs._build_activity_payload(
        state,
        playbook,
        strategies=["full_text", "rag"],
        skip_resolved=True,
        budget=budget,
        skipped_doc_count=1,
    )
    assert payload["findings_count"] == 2
    assert payload["rag_available"] is False
    assert "rag_fallback" in payload
    assert payload["skipped_unextracted_docs"] == 1
    assert payload["skipped_checks_count"] == 1
    assert payload["llm_calls"] == 1
    assert payload["model"] == "m"

    no_rag = rcs._build_activity_payload(
        state,
        playbook,
        strategies=["full_text"],
        skip_resolved=False,
        budget=rcs.LLMCallBudget(0, label="t"),
        skipped_doc_count=0,
    )
    assert no_rag["rag_available"] is None
    assert "skipped_unextracted_docs" not in no_rag


@pytest.mark.parametrize("scope", ["document", "case"])
async def test_run_with_limits_reports_timeout_with_target_scope(scope):
    import asyncio

    state = _state(timeout=0.01)

    async def _slow() -> bool:
        await asyncio.sleep(1)
        return True

    await rcs._run_with_limits(state, _slow(), "Slow", scope, None, "full_text")
    assert state.errors[0]["scope"] == scope
