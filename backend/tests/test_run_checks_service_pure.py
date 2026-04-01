"""Unit tests for pure helper functions in run_checks_service.py.

Only tests module-level pure functions (_legal_base_applicable).
No database, LLM, or Weaviate required.
"""
import uuid

from app.models.db import LegalBaseModel
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
