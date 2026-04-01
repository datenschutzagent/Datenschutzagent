"""Unit tests for pure playbook matching/ranking logic in playbook_matching.py.

No database or external services needed — all functions are pure logic that
operate on in-memory PlaybookModel instances.
"""
import uuid

import pytest

from app.models.db import PlaybookModel
from app.services.playbook_matching import (
    playbook_selection_priority,
    rank_playbooks_for_selection,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_playbook(
    *,
    name: str = "Test Playbook",
    is_active: bool = True,
    content: dict | None = None,
    department: str | None = None,
    version: str = "1.0",
) -> PlaybookModel:
    """Build a minimal PlaybookModel without a DB session."""
    pb = PlaybookModel()
    pb.id = uuid.uuid4()
    pb.name = name
    pb.is_active = is_active
    pb.content = content if content is not None else {}
    pb.department = department
    pb.version = version
    pb.case_type = None
    return pb


# ---------------------------------------------------------------------------
# playbook_selection_priority — basic
# ---------------------------------------------------------------------------


def test_inactive_playbook_returns_none():
    pb = make_playbook(is_active=False, content={"match": {"priority": 10}})
    assert playbook_selection_priority(pb, department="IT") is None


def test_active_no_restrictions_returns_priority():
    pb = make_playbook(content={"match": {"priority": 5}})
    assert playbook_selection_priority(pb, department="IT") == 5


def test_priority_zero_when_not_specified():
    pb = make_playbook(content={"match": {}})
    assert playbook_selection_priority(pb, department="IT") == 0


def test_priority_fallback_to_zero_on_invalid_string():
    pb = make_playbook(content={"match": {"priority": "not_a_number"}})
    assert playbook_selection_priority(pb, department="IT") == 0


# ---------------------------------------------------------------------------
# Department matching
# ---------------------------------------------------------------------------


def test_department_exact_match_passes():
    pb = make_playbook(content={"match": {"priority": 1, "department_values": ["IT"]}})
    assert playbook_selection_priority(pb, department="IT") == 1


def test_department_exact_match_fails():
    pb = make_playbook(content={"match": {"priority": 1, "department_values": ["IT"]}})
    assert playbook_selection_priority(pb, department="HR") is None


def test_department_empty_values_matches_any():
    pb = make_playbook(content={"match": {"priority": 1, "department_values": []}})
    assert playbook_selection_priority(pb, department="Anything") == 1


def test_department_code_exact_match():
    pb = make_playbook(content={"match": {"priority": 1, "department_codes": ["IT"]}})
    assert playbook_selection_priority(pb, department="IT") == 1


def test_department_code_prefix_with_dash():
    pb = make_playbook(content={"match": {"priority": 1, "department_codes": ["IT"]}})
    assert playbook_selection_priority(pb, department="IT – Unterabteilung") == 1


def test_department_code_prefix_with_space():
    pb = make_playbook(content={"match": {"priority": 1, "department_codes": ["IT"]}})
    assert playbook_selection_priority(pb, department="IT Abteilung") == 1


def test_department_code_no_match():
    pb = make_playbook(content={"match": {"priority": 1, "department_codes": ["IT"]}})
    assert playbook_selection_priority(pb, department="HR") is None


def test_department_legacy_spec_exact():
    # Legacy: content has no "match" key; falls back to playbook.department
    pb = make_playbook(department="IT", content={})
    assert playbook_selection_priority(pb, department="IT") == 0  # priority=0 in legacy spec


def test_department_legacy_spec_no_match():
    pb = make_playbook(department="IT", content={})
    assert playbook_selection_priority(pb, department="HR") is None


def test_department_legacy_spec_no_department_matches_all():
    pb = make_playbook(department=None, content={})
    assert playbook_selection_priority(pb, department="IT") == 0
    assert playbook_selection_priority(pb, department="HR") == 0


# ---------------------------------------------------------------------------
# Case type matching
# ---------------------------------------------------------------------------


def test_case_type_exact_match():
    pb = make_playbook(content={"match": {"priority": 1, "case_types": ["Softwareeinführung"]}})
    assert playbook_selection_priority(
        pb, department="IT", case_type="Softwareeinführung", strict_case_type=True
    ) == 1


def test_case_type_mismatch_strict():
    pb = make_playbook(content={"match": {"priority": 1, "case_types": ["Softwareeinführung"]}})
    assert playbook_selection_priority(
        pb, department="IT", case_type="Datenpanne", strict_case_type=True
    ) is None


def test_case_type_none_strict_does_not_match():
    """When strict=True and case_type is None, a playbook requiring specific case_types should not match."""
    pb = make_playbook(content={"match": {"priority": 1, "case_types": ["Softwareeinführung"]}})
    assert playbook_selection_priority(
        pb, department="IT", case_type=None, strict_case_type=True
    ) is None


def test_case_type_none_non_strict_matches():
    """When strict=False and case_type is None, the case_types restriction is relaxed."""
    pb = make_playbook(content={"match": {"priority": 1, "case_types": ["Softwareeinführung"]}})
    assert playbook_selection_priority(
        pb, department="IT", case_type=None, strict_case_type=False
    ) == 1


def test_case_type_no_restriction_matches_any():
    pb = make_playbook(content={"match": {"priority": 1}})
    assert playbook_selection_priority(
        pb, department="IT", case_type="Anything", strict_case_type=True
    ) == 1


# ---------------------------------------------------------------------------
# Processing context matching
# ---------------------------------------------------------------------------


def test_processing_context_exact_match():
    pb = make_playbook(content={"match": {"priority": 1, "processing_contexts": ["cloud"]}})
    assert playbook_selection_priority(pb, department="IT", processing_context="cloud") == 1


def test_processing_context_no_match():
    pb = make_playbook(content={"match": {"priority": 1, "processing_contexts": ["cloud"]}})
    assert playbook_selection_priority(pb, department="IT", processing_context="on-prem") is None


def test_processing_context_none_when_restriction_set():
    pb = make_playbook(content={"match": {"priority": 1, "processing_contexts": ["cloud"]}})
    assert playbook_selection_priority(pb, department="IT", processing_context=None) is None


def test_processing_context_no_restriction_matches_anything():
    pb = make_playbook(content={"match": {"priority": 1}})
    assert playbook_selection_priority(pb, department="IT", processing_context="cloud") == 1
    assert playbook_selection_priority(pb, department="IT", processing_context=None) == 1


# ---------------------------------------------------------------------------
# Org profile matching
# ---------------------------------------------------------------------------


def test_org_profile_exact_match():
    pb = make_playbook(content={"match": {"priority": 1, "org_profiles": ["university"]}})
    assert playbook_selection_priority(pb, department="IT", org_profile="university") == 1


def test_org_profile_no_match():
    pb = make_playbook(content={"match": {"priority": 1, "org_profiles": ["university"]}})
    assert playbook_selection_priority(pb, department="IT", org_profile="hospital") is None


def test_org_profile_no_restriction_matches_all():
    pb = make_playbook(content={"match": {"priority": 1}})
    assert playbook_selection_priority(pb, department="IT", org_profile="university") == 1
    assert playbook_selection_priority(pb, department="IT", org_profile="default") == 1


# ---------------------------------------------------------------------------
# rank_playbooks_for_selection
# ---------------------------------------------------------------------------


def test_rank_higher_priority_first():
    pb_low = make_playbook(name="B", content={"match": {"priority": 5}})
    pb_high = make_playbook(name="A", content={"match": {"priority": 10}})
    ranked = rank_playbooks_for_selection([pb_low, pb_high], department="IT")
    assert len(ranked) == 2
    assert ranked[0][0].name == "A"
    assert ranked[0][1] == 10
    assert ranked[1][0].name == "B"
    assert ranked[1][1] == 5


def test_rank_tie_broken_by_name_alphabetically():
    pb_b = make_playbook(name="Beta", content={"match": {"priority": 5}})
    pb_a = make_playbook(name="Alpha", content={"match": {"priority": 5}})
    ranked = rank_playbooks_for_selection([pb_b, pb_a], department="IT")
    assert ranked[0][0].name == "Alpha"
    assert ranked[1][0].name == "Beta"


def test_rank_excludes_inactive():
    pb_active = make_playbook(name="Active", is_active=True, content={"match": {"priority": 10}})
    pb_inactive = make_playbook(name="Inactive", is_active=False, content={"match": {"priority": 10}})
    ranked = rank_playbooks_for_selection([pb_active, pb_inactive], department="IT")
    assert len(ranked) == 1
    assert ranked[0][0].name == "Active"


def test_rank_excludes_non_matching_department():
    pb_it = make_playbook(name="IT", content={"match": {"priority": 1, "department_values": ["IT"]}})
    pb_hr = make_playbook(name="HR", content={"match": {"priority": 1, "department_values": ["HR"]}})
    ranked = rank_playbooks_for_selection([pb_it, pb_hr], department="IT")
    assert len(ranked) == 1
    assert ranked[0][0].name == "IT"


def test_rank_empty_input():
    ranked = rank_playbooks_for_selection([], department="IT")
    assert ranked == []


def test_rank_returns_correct_priority_values():
    pb = make_playbook(content={"match": {"priority": 42}})
    ranked = rank_playbooks_for_selection([pb], department="IT")
    assert ranked[0][1] == 42
