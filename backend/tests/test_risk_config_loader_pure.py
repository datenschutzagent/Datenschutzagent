"""Pure unit tests for risk_config_loader (no DB needed)."""
from __future__ import annotations

import logging
from pathlib import Path

import pytest

from app.config import Settings
from app.services import risk_config_loader as rcl
from app.services.risk_config_loader import (
    AvvRiskConfig,
    RiskConfig,
    load_risk_config,
    reload_risk_config,
    resolve_risk_config_path,
)

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------


def test_defaults_match_legacy_avv_thresholds():
    """Built-in defaults must reproduce the legacy hardcoded 1.5/2.5/3.5 cut-offs."""
    cfg = RiskConfig()
    assert cfg.avv.level_for_score(1.0) == "low"
    assert cfg.avv.level_for_score(1.5) == "low"
    assert cfg.avv.level_for_score(1.51) == "medium"
    assert cfg.avv.level_for_score(2.5) == "medium"
    assert cfg.avv.level_for_score(2.51) == "high"
    assert cfg.avv.level_for_score(3.5) == "high"
    assert cfg.avv.level_for_score(3.51) == "critical"
    assert cfg.avv.level_for_score(5.0) == "critical"


def test_defaults_match_legacy_score_normalization():
    """percent = (avg - 1) / 4 * 100 — the legacy formula."""
    cfg = RiskConfig()
    assert cfg.avv.normalize_to_percent(1.0) == 0
    assert cfg.avv.normalize_to_percent(3.0) == 50
    assert cfg.avv.normalize_to_percent(5.0) == 100


def test_defaults_match_legacy_case_score_weights():
    cfg = RiskConfig()
    assert cfg.case_score.severity_weights == {
        "critical": 30,
        "high": 15,
        "medium": 5,
        "low": 0,
        "info": 0,
    }
    assert cfg.case_score.max_score == 100


def test_defaults_match_legacy_maturity():
    cfg = RiskConfig()
    assert cfg.maturity.weights == {
        "vvt": 0.20,
        "dsfa": 0.20,
        "avv": 0.20,
        "tom": 0.20,
        "velocity": 0.20,
    }
    assert cfg.maturity.velocity.optimal_days == 14
    assert cfg.maturity.velocity.worst_days == 60


def test_defaults_match_legacy_dsfa_threshold():
    cfg = RiskConfig()
    assert cfg.dsfa_screening.required_threshold == 2


# ---------------------------------------------------------------------------
# Loader behaviour
# ---------------------------------------------------------------------------


def test_load_returns_defaults_when_no_file(tmp_path: Path, monkeypatch):
    """Pointing to a non-existent file must not raise; defaults are returned."""
    s = Settings(risk_config_path=str(tmp_path / "missing.yaml"))
    cfg = load_risk_config(s)
    assert cfg.avv.level_for_score(2.0) == "medium"


def test_load_yaml_overrides_thresholds(tmp_path: Path):
    yaml_path = tmp_path / "risk_config.yaml"
    yaml_path.write_text(
        """
version: 1
avv:
  level_thresholds:
    - { max_score: 1.0, level: low }
    - { max_score: 2.0, level: medium }
    - { max_score: 3.0, level: high }
    - { max_score: 5.0, level: critical }
""",
        encoding="utf-8",
    )
    s = Settings(risk_config_path=str(yaml_path))
    cfg = load_risk_config(s)
    # legacy default would call 1.6 "medium", here it's already "medium" but
    # 2.1 should now be "high" (legacy: "medium").
    assert cfg.avv.level_for_score(1.0) == "low"
    assert cfg.avv.level_for_score(2.0) == "medium"
    assert cfg.avv.level_for_score(2.1) == "high"


def test_load_partial_yaml_preserves_other_defaults(tmp_path: Path):
    """Only overriding one section keeps defaults for the others."""
    yaml_path = tmp_path / "risk_config.yaml"
    yaml_path.write_text(
        "version: 1\ndsfa_screening:\n  required_threshold: 1\n",
        encoding="utf-8",
    )
    s = Settings(risk_config_path=str(yaml_path))
    cfg = load_risk_config(s)
    assert cfg.dsfa_screening.required_threshold == 1
    # AVV section untouched -> defaults still apply
    assert cfg.avv.level_for_score(1.5) == "low"
    assert cfg.case_score.severity_weights["critical"] == 30


def test_load_malformed_yaml_falls_back_to_defaults(tmp_path: Path, caplog):
    yaml_path = tmp_path / "risk_config.yaml"
    yaml_path.write_text("this: is: not: valid: yaml: [", encoding="utf-8")
    s = Settings(risk_config_path=str(yaml_path))
    with caplog.at_level(logging.WARNING, logger="app.services.risk_config_loader"):
        cfg = load_risk_config(s)
    assert isinstance(cfg, AvvRiskConfig) or cfg.avv.level_for_score(2.0) == "medium"


def test_load_invalid_schema_falls_back_to_defaults(tmp_path: Path, caplog):
    """Descending thresholds violate the validator — must NOT crash."""
    yaml_path = tmp_path / "risk_config.yaml"
    yaml_path.write_text(
        """
version: 1
avv:
  level_thresholds:
    - { max_score: 5.0, level: low }
    - { max_score: 1.0, level: critical }
""",
        encoding="utf-8",
    )
    s = Settings(risk_config_path=str(yaml_path))
    with caplog.at_level(logging.WARNING, logger="app.services.risk_config_loader"):
        cfg = load_risk_config(s)
    # Defaults restored
    assert cfg.avv.level_for_score(1.5) == "low"
    assert any("failed validation" in r.message for r in caplog.records)


def test_load_real_default_profile(monkeypatch):
    """The shipped default/risk_config.yaml must round-trip to legacy behaviour."""
    s = Settings(org_profile="default")
    cfg = load_risk_config(s)
    assert cfg.avv.level_for_score(1.5) == "low"
    assert cfg.avv.level_for_score(3.5) == "high"
    assert cfg.case_score.severity_weights == {
        "critical": 30,
        "high": 15,
        "medium": 5,
        "low": 0,
        "info": 0,
    }


def test_load_example_profile_overrides_defaults():
    """The example profile uses stricter thresholds; verify the YAML is picked up."""
    s = Settings(org_profile="example")
    cfg = load_risk_config(s)
    assert cfg.avv.level_for_score(1.5) == "medium"  # default would say "low"
    assert cfg.dsfa_screening.required_threshold == 1
    assert cfg.maturity.velocity.optimal_days == 7


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


def test_resolve_returns_none_for_unknown_profile_without_file(tmp_path: Path):
    s = Settings(org_profile=f"nonexistent_{tmp_path.name}")
    assert resolve_risk_config_path(s) is None


def test_resolve_prefers_env_override(tmp_path: Path):
    override = tmp_path / "custom.yaml"
    override.write_text("version: 1\n", encoding="utf-8")
    s = Settings(risk_config_path=str(override), org_profile="default")
    assert resolve_risk_config_path(s) == override


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------


def test_ascending_thresholds_enforced():
    with pytest.raises(Exception):
        AvvRiskConfig(
            level_thresholds=[
                {"max_score": 3.0, "level": "low"},
                {"max_score": 1.0, "level": "high"},
            ]
        )


def test_score_normalization_max_gt_min():
    with pytest.raises(Exception):
        AvvRiskConfig.model_validate(
            {"score_normalization": {"score_min": 5.0, "score_max": 1.0}}
        )


# ---------------------------------------------------------------------------
# Weighted average helper (used by AVV service)
# ---------------------------------------------------------------------------


def test_weighted_average_falls_back_to_mean_without_weights():
    """When dimension_weights is empty, the arithmetic mean must be used."""
    from app.services.avv_risk_service import _AVVRiskDimension, _weighted_average

    dims = [
        _AVVRiskDimension(name="Datensensitivität", score=2, rationale=""),
        _AVVRiskDimension(name="Drittlandrisiko", score=4, rationale=""),
    ]
    assert _weighted_average(dims, {}) == pytest.approx(3.0)


def test_weighted_average_applies_weights():
    from app.services.avv_risk_service import _AVVRiskDimension, _weighted_average

    dims = [
        _AVVRiskDimension(name="Datensensitivität", score=2, rationale=""),
        _AVVRiskDimension(name="Drittlandrisiko", score=4, rationale=""),
    ]
    # Drittland 3x stronger -> mean shifts towards 4
    weights = {"Drittlandrisiko": 3.0, "Datensensitivität": 1.0}
    assert _weighted_average(dims, weights) == pytest.approx((2 + 4 * 3) / 4)


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


def test_reload_clears_cache():
    """reload_risk_config must invalidate the LRU cache."""
    # Prime cache
    rcl.get_risk_config()
    cache_info_before = rcl._cached_config_for_key.cache_info()
    reload_risk_config()
    cache_info_after = rcl._cached_config_for_key.cache_info()
    assert cache_info_after.currsize == 0
    assert cache_info_before.currsize >= 0  # sanity check


# ---------------------------------------------------------------------------
# Velocity helper (analytics_service)
# ---------------------------------------------------------------------------


def test_velocity_score_matches_legacy_formula():
    """Default 14d->100, 60d->0 must reproduce the legacy (60-d)/46*100 mapping."""
    from app.services.analytics_service import _velocity_score

    assert _velocity_score(14.0, 14, 60) == pytest.approx(100.0)
    assert _velocity_score(60.0, 14, 60) == pytest.approx(0.0)
    # Median 37d (midpoint): legacy gives 100 * (60-37)/46 ≈ 50.0
    assert _velocity_score(37.0, 14, 60) == pytest.approx(50.0, abs=0.1)


def test_velocity_score_clamps_to_range():
    from app.services.analytics_service import _velocity_score

    assert _velocity_score(0.0, 14, 60) == 100.0  # well below optimal
    assert _velocity_score(120.0, 14, 60) == 0.0  # well above worst


def test_velocity_score_handles_degenerate_span():
    """worst == optimal would divide by zero — must clamp safely."""
    from app.services.analytics_service import _velocity_score

    assert _velocity_score(5.0, 10, 10) == 100.0  # under threshold
    assert _velocity_score(15.0, 10, 10) == 0.0  # over threshold


# ---------------------------------------------------------------------------
# Case-score weighting (cases.py)
# ---------------------------------------------------------------------------


def test_case_score_with_default_weights():
    """Default weights 30/15/5 reproduce the legacy formula and cap."""
    cfg = RiskConfig()
    w = cfg.case_score.severity_weights
    # 1 critical: 30
    assert min(cfg.case_score.max_score, 1 * w["critical"]) == 30
    # 3 critical + 2 high + 5 medium: 90+30+25 = 145 -> capped to 100
    assert min(cfg.case_score.max_score, 3 * w["critical"] + 2 * w["high"] + 5 * w["medium"]) == 100


def test_case_score_with_example_profile_weights():
    """Example profile uses higher weights — same finding counts produce higher scores."""
    s = Settings(org_profile="example")
    cfg = load_risk_config(s)
    w = cfg.case_score.severity_weights
    # 1 critical: 40 (vs 30 default)
    assert min(cfg.case_score.max_score, 1 * w["critical"]) == 40


# ---------------------------------------------------------------------------
# DSFA screening factors (Item 8 — declarative spec)
# ---------------------------------------------------------------------------


def test_default_dsfa_factors_have_nine_entries():
    """Built-in DSFA screening factors must reproduce the legacy 9-factor list."""
    cfg = RiskConfig()
    factor_ids = [f.id for f in cfg.dsfa_screening.factors]
    assert factor_ids == [
        "profiling",
        "special_categories",
        "large_scale",
        "international_transfer",
        "vulnerable_subjects",
        "systematic_monitoring",
        "critical_findings",
        "sensitive_purpose",
        "innovative_technology",
    ]
    # All default weights = 1.0
    assert all(f.weight == 1.0 for f in cfg.dsfa_screening.factors)


def test_dsfa_factor_unique_id_validator():
    """Duplicate factor ids must be rejected by the loader."""
    from app.services.risk_config_loader import DsfaScreeningConfig

    with pytest.raises(Exception):
        DsfaScreeningConfig(
            factors=[
                {"id": "foo", "label": "Foo"},
                {"id": "foo", "label": "Foo again"},
            ]
        )


def test_dsfa_factor_met_keyword_match():
    """_factor_met handles keyword matches in processing_context (case-insensitive)."""
    from app.services.dsfa_service import _factor_met
    from app.services.risk_config_loader import DsfaScreeningFactor

    class _Case:
        processing_context = "Wir nutzen Profiling für Kundensegmente."
        title = ""
        special_category_data = False
        international_transfer = False

    factor = DsfaScreeningFactor(
        id="profiling", label="Profiling", keywords_processing_context=["profil"]
    )
    assert _factor_met(factor, _Case(), []) is True


def test_dsfa_factor_met_case_flag():
    """_factor_met returns True when case_flag attribute is truthy."""
    from app.services.dsfa_service import _factor_met
    from app.services.risk_config_loader import DsfaScreeningFactor

    class _Case:
        processing_context = ""
        title = ""
        special_category_data = True
        international_transfer = False

    factor = DsfaScreeningFactor(
        id="special_categories", label="Art. 9", case_flag="special_category_data"
    )
    assert _factor_met(factor, _Case(), []) is True

    class _CaseNo:
        processing_context = ""
        title = ""
        special_category_data = False
        international_transfer = False

    assert _factor_met(factor, _CaseNo(), []) is False


def test_dsfa_factor_met_findings_severity():
    """_factor_met returns True when any finding has matching severity."""
    from app.services.dsfa_service import _factor_met
    from app.services.risk_config_loader import DsfaScreeningFactor

    class _Case:
        processing_context = ""
        title = ""
        special_category_data = False
        international_transfer = False

    class _Finding:
        def __init__(self, severity: str):
            self.severity = severity

    factor = DsfaScreeningFactor(
        id="critical_findings", label="Critical findings", findings_severity=["critical", "high"]
    )
    assert _factor_met(factor, _Case(), [_Finding("critical")]) is True
    assert _factor_met(factor, _Case(), [_Finding("low")]) is False
    assert _factor_met(factor, _Case(), []) is False


def test_dsfa_factor_met_no_conditions():
    """Factor without any conditions never matches."""
    from app.services.dsfa_service import _factor_met
    from app.services.risk_config_loader import DsfaScreeningFactor

    class _Case:
        processing_context = "anything"
        title = "anything"
        special_category_data = True
        international_transfer = True

    factor = DsfaScreeningFactor(id="empty", label="Empty factor")
    assert _factor_met(factor, _Case(), []) is False


def test_dsfa_factor_weight_in_example_profile():
    """Example profile's special_categories factor has weight 2.0."""
    s = Settings(org_profile="example")
    cfg = load_risk_config(s)
    special = next(f for f in cfg.dsfa_screening.factors if f.id == "special_categories")
    assert special.weight == 2.0


# ---------------------------------------------------------------------------
# Risk-velocity (Item 12)
# ---------------------------------------------------------------------------


def test_risk_velocity_config_defaults():
    cfg = RiskConfig()
    assert cfg.risk_velocity.enabled is True
    assert cfg.risk_velocity.window_days == 90
    assert cfg.risk_velocity.significant_change_pct == 15.0


def test_risk_velocity_classify_trend():
    cfg = RiskConfig()
    rv = cfg.risk_velocity
    # threshold = 15
    assert rv.classify_trend(0.0) == "stable"
    assert rv.classify_trend(14.9) == "stable"
    assert rv.classify_trend(-14.9) == "stable"
    assert rv.classify_trend(15.0) == "up"
    assert rv.classify_trend(20.0) == "up"
    assert rv.classify_trend(-15.0) == "down"
    assert rv.classify_trend(-30.0) == "down"


def test_classify_trend_helper_matches_config():
    """Standalone helper in analytics_service uses the same logic."""
    from app.services.analytics_service import _classify_trend

    assert _classify_trend(5.0, 10.0) == "stable"
    assert _classify_trend(10.0, 10.0) == "up"
    assert _classify_trend(-10.0, 10.0) == "down"


def test_risk_velocity_example_profile_overrides():
    """Example profile shortens window to 60d and lowers threshold to 10%."""
    s = Settings(org_profile="example")
    cfg = load_risk_config(s)
    assert cfg.risk_velocity.window_days == 60
    assert cfg.risk_velocity.significant_change_pct == 10.0


# ---------------------------------------------------------------------------
# Confidence-Score (Item 11) — AVV LLM result schema
# ---------------------------------------------------------------------------


def test_avv_result_default_confidence():
    """_AVVRiskResult must default confidence to 0.7 when LLM omits the field."""
    from app.services.avv_risk_service import _AVVRiskDimension, _AVVRiskResult

    result = _AVVRiskResult(
        dimensions=[_AVVRiskDimension(name="Datensensitivität", score=3, rationale="")],
        overall_risk_level="medium",
        main_risks=[],
        recommended_measures=[],
        summary="",
    )
    assert result.confidence == 0.7


def test_avv_result_confidence_bounds():
    """confidence must be in [0, 1]."""
    from app.services.avv_risk_service import _AVVRiskDimension, _AVVRiskResult

    with pytest.raises(Exception):
        _AVVRiskResult(
            dimensions=[_AVVRiskDimension(name="x", score=3, rationale="")],
            overall_risk_level="medium",
            main_risks=[],
            recommended_measures=[],
            summary="",
            confidence=1.5,
        )


# ---------------------------------------------------------------------------
# DSFA-Assessment / ISO-27005 Matrix (Item 9)
# ---------------------------------------------------------------------------


def test_dsfa_assessment_default_matrix_complete():
    """Default 5x5 matrix covers all 25 cells with valid risk levels."""
    cfg = RiskConfig()
    matrix = cfg.dsfa_assessment.matrix
    assert len(matrix) == 25
    for lik in range(1, 6):
        for sev in range(1, 6):
            assert f"{lik}_{sev}" in matrix
            assert matrix[f"{lik}_{sev}"] in {"low", "medium", "high", "critical"}


def test_dsfa_assessment_matrix_corners_match_iso27005():
    cfg = RiskConfig()
    m = cfg.dsfa_assessment.matrix
    assert m["1_1"] == "low"        # minimum risk
    assert m["5_5"] == "critical"   # maximum risk
    assert m["3_3"] == "medium"     # midpoint


def test_dsfa_matrix_validator_rejects_missing_cells():
    """A matrix with missing cells must be rejected."""
    from app.services.risk_config_loader import DsfaAssessmentConfig

    with pytest.raises(Exception):
        DsfaAssessmentConfig(scale_type="1-5", matrix={"1_1": "low"})


def test_dsfa_matrix_validator_rejects_invalid_level():
    """Cell with an unknown risk level must be rejected."""
    from app.services.risk_config_loader import DsfaAssessmentConfig

    bad_matrix = {f"{lik}_{sev}": "low" for lik in range(1, 6) for sev in range(1, 6)}
    bad_matrix["3_3"] = "extreme"  # not a valid level
    with pytest.raises(Exception):
        DsfaAssessmentConfig(scale_type="1-5", matrix=bad_matrix)


def test_dsfa_matrix_risk_level_for():
    """risk_level_for() looks up cells correctly."""
    cfg = RiskConfig().dsfa_assessment
    assert cfg.risk_level_for(1, 1) == "low"
    assert cfg.risk_level_for(5, 5) == "critical"
    assert cfg.risk_level_for(4, 5) == "critical"


def test_dsfa_example_profile_stricter_matrix():
    """Example profile escalates earlier — 1_5 is high (default is medium)."""
    s = Settings(org_profile="example")
    cfg = load_risk_config(s)
    assert cfg.dsfa_assessment.matrix["1_5"] == "high"
    assert cfg.dsfa_assessment.matrix["3_3"] == "high"
    # DPO consultation triggers already at medium.
    assert "medium" in cfg.dsfa_assessment.dpo_consultation_required_when_residual_in


# ---------------------------------------------------------------------------
# DSFA Dual-Read (Item 10) — _normalize_dsfa_payload
# ---------------------------------------------------------------------------


def test_normalize_legacy_dsfa_payload_string_to_numeric():
    """A v1 payload (string likelihood/severity) gets numeric fields added."""
    from app.services.dsfa_service import _normalize_dsfa_payload

    legacy = {
        "necessity_assessment": "ok",
        "proportionality_assessment": "ok",
        "risks": [
            {"description": "Risk A", "likelihood": "low", "severity": "high", "mitigation": "x"},
            {"description": "Risk B", "likelihood": "medium", "severity": "medium", "mitigation": "y"},
        ],
        "residual_risk": "high",
        "dpo_consultation_required": True,
        "measures": [],
    }
    out = _normalize_dsfa_payload(legacy)
    # First risk: low (1) × high (5) → matrix lookup
    assert out["risks"][0]["likelihood_score"] == 1
    assert out["risks"][0]["severity_score"] == 5
    assert out["risks"][0]["risk_level"] in {"low", "medium", "high", "critical"}
    # Second risk: medium (3) × medium (3) → "medium" with default matrix
    assert out["risks"][1]["likelihood_score"] == 3
    assert out["risks"][1]["severity_score"] == 3
    # String fields preserved for backward compatibility
    assert out["risks"][0]["likelihood"] == "low"
    assert out["risks"][1]["severity"] == "medium"


def test_normalize_numeric_dsfa_payload_passthrough():
    """A v2 payload (numeric) remains numeric and adds string labels."""
    from app.services.dsfa_service import _normalize_dsfa_payload

    new = {
        "risks": [
            {
                "description": "Risk X",
                "likelihood_score": 4,
                "severity_score": 5,
                "likelihood": "high",
                "severity": "high",
                "risk_level": "critical",
                "mitigation": "z",
            }
        ],
        "scale_version": "v2_numeric",
    }
    out = _normalize_dsfa_payload(new)
    r = out["risks"][0]
    assert r["likelihood_score"] == 4
    assert r["severity_score"] == 5
    # risk_level recomputed deterministically from matrix → critical with default
    assert r["risk_level"] == "critical"
    assert out["residual_risk"] == "critical"
    assert out["dpo_consultation_required"] is True


def test_normalize_is_idempotent():
    """Calling normalize twice yields identical output."""
    from app.services.dsfa_service import _normalize_dsfa_payload

    legacy = {
        "risks": [
            {"description": "x", "likelihood": "medium", "severity": "high", "mitigation": ""},
        ],
        "residual_risk": "high",
        "dpo_consultation_required": True,
    }
    once = _normalize_dsfa_payload(legacy)
    twice = _normalize_dsfa_payload(once)
    assert once["risks"] == twice["risks"]
    assert once["residual_risk"] == twice["residual_risk"]


def test_normalize_recomputes_residual_from_risks():
    """residual_risk is recomputed as the max level of contained risks.

    Note: legacy "high" maps to score 5, and 5×5 in the default ISO-27005
    matrix is "critical" — escalation is by design when moving from the
    coarse 3-level scale to the 5×5 matrix.
    """
    from app.services.dsfa_service import _normalize_dsfa_payload

    payload = {
        "risks": [
            {"description": "a", "likelihood": "low", "severity": "low", "mitigation": ""},
            {"description": "b", "likelihood": "high", "severity": "high", "mitigation": ""},
        ],
        "residual_risk": "low",  # wrong on input — must be corrected
    }
    out = _normalize_dsfa_payload(payload)
    # legacy high → score 5; 5×5 cell in default matrix = "critical"
    assert out["residual_risk"] == "critical"


def test_normalize_handles_empty_risks():
    from app.services.dsfa_service import _normalize_dsfa_payload

    out = _normalize_dsfa_payload({"risks": [], "residual_risk": "low"})
    assert out["risks"] == []
    assert out["residual_risk"] == "low"


def test_normalize_handles_non_dict_input():
    """Edge case: payload that is not a dict is returned as-is."""
    from app.services.dsfa_service import _normalize_dsfa_payload

    assert _normalize_dsfa_payload(None) is None  # type: ignore[arg-type]
    assert _normalize_dsfa_payload("not a dict") == "not a dict"  # type: ignore[arg-type]


def test_to_score_clamps_and_maps():
    from app.services.dsfa_service import _to_score

    assert _to_score("low") == 1
    assert _to_score("medium") == 3
    assert _to_score("high") == 5
    assert _to_score("critical") == 5
    assert _to_score(0) == 1
    assert _to_score(7) == 5
    assert _to_score(3) == 3
    assert _to_score(None) == 3
    assert _to_score(True) == 3  # bool is excluded
    assert _to_score(3.6) == 4


def test_to_label_inverse_of_to_score():
    from app.services.dsfa_service import _to_label

    assert _to_label(1) == "low"
    assert _to_label(3) == "medium"
    assert _to_label(5) == "high"
