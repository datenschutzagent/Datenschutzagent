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
