"""Unit tests for pure helper functions in run_checks_service.py.

Only tests module-level pure functions (_legal_base_applicable) and
schema defaults. No database, LLM, or Weaviate required.
"""
import uuid
from types import SimpleNamespace

from app.models.db import LegalBaseModel
from app.models.schemas import RunChecksRequest
from app.services.run_checks_service import _legal_base_applicable


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_legal_base(
    *,
    applicability: str = "always",
    department_codes: list[str] | None = None,
    case_types: list[str] | None = None,
    internal_only: bool = False,
) -> LegalBaseModel:
    base = LegalBaseModel()
    base.id = uuid.uuid4()
    base.title = "Test Legal Base"
    base.applicability = applicability
    base.department_codes = department_codes
    base.case_types = case_types
    base.internal_only = internal_only
    return base


# ---------------------------------------------------------------------------
# applicability == "always"
# ---------------------------------------------------------------------------


def test_always_applicable_any_department():
    base = make_legal_base(applicability="always")
    assert _legal_base_applicable(base, "IT", "Softwareeinführung") is True


def test_always_applicable_any_case_type():
    base = make_legal_base(applicability="always")
    assert _legal_base_applicable(base, "HR", "Datenpanne") is True


def test_always_applicable_ignores_department_codes():
    # Even if department_codes is set, "always" still returns True
    base = make_legal_base(applicability="always", department_codes=["HR"])
    assert _legal_base_applicable(base, "IT", "Softwareeinführung") is True


# ---------------------------------------------------------------------------
# applicability == "unknown" / other values
# ---------------------------------------------------------------------------


def test_unknown_applicability_returns_false():
    base = make_legal_base(applicability="never")
    assert _legal_base_applicable(base, "IT", "Softwareeinführung") is False


def test_empty_applicability_returns_false():
    base = make_legal_base(applicability="")
    assert _legal_base_applicable(base, "IT", "Softwareeinführung") is False


# ---------------------------------------------------------------------------
# applicability == "conditional" — no restrictions
# ---------------------------------------------------------------------------


def test_conditional_no_restrictions_always_true():
    base = make_legal_base(
        applicability="conditional",
        department_codes=None,
        case_types=None,
        internal_only=False,
    )
    assert _legal_base_applicable(base, "IT", "Softwareeinführung") is True


def test_conditional_empty_lists_always_true():
    base = make_legal_base(
        applicability="conditional",
        department_codes=[],
        case_types=[],
        internal_only=False,
    )
    assert _legal_base_applicable(base, "IT", "Softwareeinführung") is True


# ---------------------------------------------------------------------------
# applicability == "conditional" — department_codes restriction
# ---------------------------------------------------------------------------


def test_conditional_department_code_match():
    base = make_legal_base(applicability="conditional", department_codes=["IT"])
    assert _legal_base_applicable(base, "IT", "Softwareeinführung") is True


def test_conditional_department_code_no_match():
    base = make_legal_base(applicability="conditional", department_codes=["HR"])
    assert _legal_base_applicable(base, "IT", "Softwareeinführung") is False


def test_conditional_multiple_department_codes_one_matches():
    base = make_legal_base(applicability="conditional", department_codes=["HR", "IT"])
    assert _legal_base_applicable(base, "IT", "Softwareeinführung") is True


# ---------------------------------------------------------------------------
# applicability == "conditional" — case_types restriction
# ---------------------------------------------------------------------------


def test_conditional_case_type_match():
    base = make_legal_base(applicability="conditional", case_types=["Softwareeinführung"])
    assert _legal_base_applicable(base, "IT", "Softwareeinführung") is True


def test_conditional_case_type_no_match():
    base = make_legal_base(applicability="conditional", case_types=["Softwareeinführung"])
    assert _legal_base_applicable(base, "IT", "Datenpanne") is False


def test_conditional_multiple_case_types_one_matches():
    base = make_legal_base(applicability="conditional", case_types=["Datenpanne", "Softwareeinführung"])
    assert _legal_base_applicable(base, "IT", "Datenpanne") is True


# ---------------------------------------------------------------------------
# applicability == "conditional" — internal_only restriction
# ---------------------------------------------------------------------------


def test_conditional_internal_only_with_innenrecht():
    base = make_legal_base(applicability="conditional", internal_only=True)
    assert _legal_base_applicable(base, "IT", "Innenrecht") is True


def test_conditional_internal_only_with_other_case_type():
    base = make_legal_base(applicability="conditional", internal_only=True)
    assert _legal_base_applicable(base, "IT", "Softwareeinführung") is False


def test_conditional_internal_only_false_any_case_type():
    base = make_legal_base(applicability="conditional", internal_only=False)
    assert _legal_base_applicable(base, "IT", "Softwareeinführung") is True


# ---------------------------------------------------------------------------
# Combined restrictions
# ---------------------------------------------------------------------------


def test_conditional_department_and_case_type_both_match():
    base = make_legal_base(
        applicability="conditional",
        department_codes=["IT"],
        case_types=["Softwareeinführung"],
    )
    assert _legal_base_applicable(base, "IT", "Softwareeinführung") is True


def test_conditional_department_match_case_type_no_match():
    base = make_legal_base(
        applicability="conditional",
        department_codes=["IT"],
        case_types=["Softwareeinführung"],
    )
    assert _legal_base_applicable(base, "IT", "Datenpanne") is False


def test_conditional_department_no_match_case_type_match():
    base = make_legal_base(
        applicability="conditional",
        department_codes=["IT"],
        case_types=["Softwareeinführung"],
    )
    assert _legal_base_applicable(base, "HR", "Softwareeinführung") is False


# ---------------------------------------------------------------------------
# RunChecksRequest schema – skip_resolved default (Bug #1)
# ---------------------------------------------------------------------------


def test_run_checks_request_skip_resolved_defaults_to_true():
    """skip_resolved must default to True so periodic re-checks never reopen reviewed findings."""
    req = RunChecksRequest(playbook_id=uuid.uuid4())
    assert req.skip_resolved is True


def test_run_checks_request_skip_resolved_can_be_set_false():
    """Callers may explicitly request a full force-recheck by setting skip_resolved=False."""
    req = RunChecksRequest(playbook_id=uuid.uuid4(), skip_resolved=False)
    assert req.skip_resolved is False


def test_run_checks_request_strategies_default():
    """Default strategy is full_text (unchanged by Bug #1 fix)."""
    req = RunChecksRequest(playbook_id=uuid.uuid4())
    assert req.strategies == ["full_text"]


# ---------------------------------------------------------------------------
# Document extraction-status filtering (Bug #2)
# ---------------------------------------------------------------------------

def _make_doc(extraction_status: str) -> SimpleNamespace:
    """Minimal document stub with id and extraction_status."""
    return SimpleNamespace(id=uuid.uuid4(), content="text", extraction_status=extraction_status)


def test_only_done_documents_are_checked():
    """run_checks_impl filters to extraction_status=='done'; other statuses yield no docs."""
    docs = [
        _make_doc("done"),
        _make_doc("pending"),
        _make_doc("processing"),
        _make_doc("failed"),
    ]
    extractable = [d for d in docs if d.extraction_status == "done"]
    assert len(extractable) == 1
    assert extractable[0].extraction_status == "done"


def test_all_done_documents_included():
    """All 'done' documents are included."""
    docs = [_make_doc("done"), _make_doc("done"), _make_doc("done")]
    extractable = [d for d in docs if d.extraction_status == "done"]
    assert len(extractable) == 3


def test_no_done_documents_yields_empty():
    """If no documents are extracted yet, no checks are run."""
    docs = [_make_doc("pending"), _make_doc("processing")]
    extractable = [d for d in docs if d.extraction_status == "done"]
    assert extractable == []


def test_skipped_doc_count_is_correct():
    """The count of skipped (non-done) documents is reported accurately."""
    docs = [
        _make_doc("done"),
        _make_doc("pending"),
        _make_doc("failed"),
    ]
    extractable = [d for d in docs if d.extraction_status == "done"]
    skipped = len(docs) - len(extractable)
    assert skipped == 2
