"""Pure unit tests for the rule-based risk fallback (no DB, no LLM, no IO).

Covers:
  - AVV: keyword-based dimension scoring; sub-processor escalation; default
    "no signal" → mid-cautious; critical / high level thresholds.
  - DSFA: case-flag triggers, processing-context keyword triggers, critical
    findings, conservative baseline when nothing matches.
  - Confidence-policy: strategy validators, enabled flags.
"""

from __future__ import annotations

import pytest

from app.services.risk_config_loader import ConfidencePolicyConfig
from app.services.risk_fallback_service import (
    compute_avv_fallback,
    compute_dsfa_fallback,
)

# ---------------------------------------------------------------------------
# Confidence policy
# ---------------------------------------------------------------------------


def test_policy_defaults_uses_rules_fallback():
    p = ConfidencePolicyConfig()
    assert p.enabled is True
    assert p.fallback_strategy == "rules"
    assert p.uses_rule_fallback is True
    assert p.emits_audit_event is False
    assert 0.0 <= p.low_threshold <= 1.0


def test_policy_strategy_validators():
    with pytest.raises(ValueError):
        ConfidencePolicyConfig(fallback_strategy="unknown")
    # Each accepted strategy has consistent flags.
    cases = {
        "none": (False, False),
        "rules": (True, False),
        "escalate": (False, True),
        "both": (True, True),
    }
    for strat, (rules, escalate) in cases.items():
        p = ConfidencePolicyConfig(fallback_strategy=strat)
        assert p.uses_rule_fallback is rules
        assert p.emits_audit_event is escalate


# ---------------------------------------------------------------------------
# AVV fallback
# ---------------------------------------------------------------------------


def test_avv_fallback_empty_input_returns_mid_score():
    r = compute_avv_fallback(
        partner_name="Acme",
        partner_type="processor",
        subject_matter=None,
        department=None,
        notes=None,
    )
    assert {d["score"] for d in r["dimensions"]} == {3}  # all defaults to 3
    assert (
        r["overall_risk_level"] == "high"
    )  # 3.0 ≤ 3.5 → high under default thresholds
    assert r["confidence"] == 0.3
    assert len(r["dimensions"]) == 5


def test_avv_fallback_health_data_keywords_lift_score():
    r = compute_avv_fallback(
        partner_name="HealthVendor",
        partner_type="processor",
        subject_matter="Verarbeitung von Gesundheitsdaten und Patientenakten.",
        department="Klinik",
        notes=None,
    )
    sens = next(d for d in r["dimensions"] if d["name"] == "Datensensitivität")
    assert sens["score"] == 4
    assert "Verarbeitung sensibler personenbezogener Daten" in r["main_risks"]


def test_avv_fallback_sub_processor_raises_subprocessor_dim():
    r_proc = compute_avv_fallback(
        partner_name="Acme",
        partner_type="processor",
        subject_matter="Normale Daten",
        department="IT",
        notes=None,
    )
    r_sub = compute_avv_fallback(
        partner_name="Acme",
        partner_type="sub_processor",
        subject_matter="Normale Daten",
        department="IT",
        notes=None,
    )
    sub_dim_proc = next(
        d for d in r_proc["dimensions"] if d["name"] == "Subauftragsverarbeiter-Risiko"
    )
    sub_dim_sub = next(
        d for d in r_sub["dimensions"] if d["name"] == "Subauftragsverarbeiter-Risiko"
    )
    assert sub_dim_proc["score"] == 3
    assert sub_dim_sub["score"] == 4


def test_avv_fallback_third_country_triggers_critical_pathway():
    r = compute_avv_fallback(
        partner_name="GlobalCorp",
        partner_type="processor",
        subject_matter="Cloud-Hosting USA",
        department=None,
        notes="Drittland-Transfer USA.",
    )
    drittland = next(d for d in r["dimensions"] if d["name"] == "Drittlandrisiko")
    assert drittland["score"] == 4
    assert any("Drittland" in mr for mr in r["main_risks"])


def test_avv_fallback_draft_contract_flags_contractual_dim():
    r = compute_avv_fallback(
        partner_name="X",
        partner_type="processor",
        subject_matter="Standardvertrag",
        department=None,
        notes="AVV im Entwurf, noch nicht unterzeichnet.",
    )
    contract_dim = next(
        d for d in r["dimensions"] if d["name"] == "Vertragliche Absicherung"
    )
    assert contract_dim["score"] == 4
    assert any("unvollständig" in mr or "unterzeichnet" in mr for mr in r["main_risks"])


def test_avv_fallback_output_shape_matches_llm_result():
    """The fallback must produce all fields _AVVRiskResult expects."""
    r = compute_avv_fallback(
        partner_name="Y",
        partner_type="processor",
        subject_matter="x",
        department="x",
        notes="x",
    )
    required = {
        "dimensions",
        "overall_risk_level",
        "main_risks",
        "recommended_measures",
        "summary",
        "confidence",
    }
    assert required.issubset(r.keys())
    for d in r["dimensions"]:
        assert set(d.keys()) == {"name", "score", "rationale"}
        assert 1 <= d["score"] <= 5


# ---------------------------------------------------------------------------
# DSFA fallback
# ---------------------------------------------------------------------------


def test_dsfa_fallback_no_signals_emits_baseline_risk():
    r = compute_dsfa_fallback(
        case_title="Standardvorgang",
        case_type="Verarbeitung",
        processing_context=None,
        special_category_data=False,
        international_transfer=False,
        open_critical_findings=0,
    )
    assert len(r["risks"]) == 1
    assert "manuelle Bewertung" in r["risks"][0]["description"]
    assert r["confidence"] == 0.3


def test_dsfa_fallback_special_category_triggers_dedicated_risk():
    r = compute_dsfa_fallback(
        case_title="Gesundheitsdatenverarbeitung",
        case_type="Health",
        processing_context=None,
        special_category_data=True,
        international_transfer=False,
        open_critical_findings=0,
    )
    descs = [risk["description"] for risk in r["risks"]]
    assert any("besonderer Kategorien" in d for d in descs)


def test_dsfa_fallback_international_transfer_triggers():
    r = compute_dsfa_fallback(
        case_title="X",
        case_type="X",
        processing_context=None,
        special_category_data=False,
        international_transfer=True,
        open_critical_findings=0,
    )
    descs = [risk["description"] for risk in r["risks"]]
    assert any("Drittländer" in d for d in descs)


def test_dsfa_fallback_processing_context_keywords_match():
    r = compute_dsfa_fallback(
        case_title="Tracking-Tool",
        case_type="IT",
        processing_context="Mitarbeiter-Monitoring mit Kamera",
        special_category_data=False,
        international_transfer=False,
        open_critical_findings=0,
    )
    descs = [risk["description"] for risk in r["risks"]]
    assert any("Überwachung" in d for d in descs)


def test_dsfa_fallback_critical_findings_add_finding_risk():
    r = compute_dsfa_fallback(
        case_title="X",
        case_type="X",
        processing_context=None,
        special_category_data=False,
        international_transfer=False,
        open_critical_findings=3,
    )
    descs = [risk["description"] for risk in r["risks"]]
    assert any("3 offene kritische" in d for d in descs)


def test_dsfa_fallback_multi_signal_aggregates_risks():
    r = compute_dsfa_fallback(
        case_title="KI-Scoring von Schülern",
        case_type="Education",
        processing_context="Profiling von Schülern in der Cloud (USA)",
        special_category_data=True,
        international_transfer=True,
        open_critical_findings=1,
    )
    # At least 4 distinct risk types should fire: special category, transfer,
    # profiling, vulnerable subjects/innovative tech, critical findings.
    assert len(r["risks"]) >= 4
    descs_blob = " ".join(risk["description"] for risk in r["risks"])
    assert "besonderer Kategorien" in descs_blob
    assert "Drittländer" in descs_blob
    assert "Profiling" in descs_blob or "automatisier" in descs_blob.lower()


def test_dsfa_fallback_output_shape_matches_llm_result():
    """The fallback must produce all fields _DSFAResult expects."""
    r = compute_dsfa_fallback(
        case_title="x",
        case_type="x",
        processing_context=None,
        special_category_data=False,
        international_transfer=False,
        open_critical_findings=0,
    )
    required = {
        "necessity_assessment",
        "proportionality_assessment",
        "risks",
        "measures",
        "confidence",
    }
    assert required.issubset(r.keys())
    for risk in r["risks"]:
        assert set(risk.keys()) >= {
            "description",
            "likelihood",
            "severity",
            "mitigation",
        }
        assert 1 <= risk["likelihood"] <= 5
        assert 1 <= risk["severity"] <= 5
