"""Pure unit tests for the Risk-Config admin endpoints (DB-frei).

Testet das Save-/Reload-/Preview-Verhalten am Loader; die HTTP-Authentifizierung
ist in test_admin_risk_config_api.py abgedeckt (sobald Postgres verfügbar).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.config import Settings
from app.services import risk_config_loader as rcl
from app.services.risk_config_loader import (
    RiskConfig,
    load_risk_config,
    resolve_risk_config_path,
    resolve_writable_risk_config_path,
    save_risk_config,
)


def test_resolve_writable_path_uses_override(tmp_path: Path):
    target = tmp_path / "custom_risk.yaml"
    s = Settings(risk_config_path=str(target))
    assert resolve_writable_risk_config_path(s) == target


def test_resolve_writable_path_falls_back_to_profile(tmp_path: Path):
    s = Settings(org_profile="default")
    result = resolve_writable_risk_config_path(s)
    assert result.name == "risk_config.yaml"
    assert "default" in str(result)


def test_save_persists_yaml(tmp_path: Path):
    """save_risk_config writes valid YAML that round-trips through load_risk_config."""
    target = tmp_path / "risk_config.yaml"
    s = Settings(risk_config_path=str(target))

    cfg = RiskConfig()
    # Strengere AVV-Schwellen als Override.
    cfg.avv.level_thresholds = [
        rcl.AvvLevelThreshold(max_score=1.0, level="low"),
        rcl.AvvLevelThreshold(max_score=2.0, level="medium"),
        rcl.AvvLevelThreshold(max_score=3.0, level="high"),
        rcl.AvvLevelThreshold(max_score=5.0, level="critical"),
    ]
    cfg.dsfa_screening.required_threshold = 1.5

    written = save_risk_config(cfg, s)
    assert written == target
    assert target.is_file()

    loaded = load_risk_config(s)
    assert loaded.avv.level_for_score(2.5) == "high"  # neue Schwellen aktiv
    assert loaded.dsfa_screening.required_threshold == 1.5


def test_save_creates_backup_of_previous_file(tmp_path: Path):
    """Bestehende YAMLs werden vor dem Überschreiben als .bak.{ts} gesichert."""
    target = tmp_path / "risk_config.yaml"
    target.write_text("version: 1\navv:\n  min_confidence: 0.42\n", encoding="utf-8")

    s = Settings(risk_config_path=str(target))
    save_risk_config(RiskConfig(), s)

    # Genau eine .bak.* Datei muss entstehen
    backups = list(tmp_path.glob("risk_config.yaml.bak.*"))
    assert len(backups) == 1
    assert "min_confidence: 0.42" in backups[0].read_text()


def test_save_invalidates_cache(tmp_path: Path):
    """Nach save_risk_config liefert get_risk_config die neue Config (Cache-Clear)."""
    # Reset cache, dann eine Custom-Config speichern.
    rcl.reload_risk_config()
    target = tmp_path / "risk_config.yaml"

    custom = RiskConfig()
    custom.dsfa_screening.required_threshold = 7.0

    s = Settings(risk_config_path=str(target))
    save_risk_config(custom, s)

    # get_risk_config mit demselben Settings-Objekt muss die persistierte
    # Threshold lesen (bypassed den default-LRU-Cache, weil settings != default).
    reread = rcl.get_risk_config(s)
    assert reread.dsfa_screening.required_threshold == 7.0


def test_save_with_path_resolution(tmp_path: Path, monkeypatch):
    """Wenn risk_config_path nicht gesetzt ist, wird der Profilpfad benutzt."""
    # Mock _DATA_DIR auf tmp_path
    monkeypatch.setattr(rcl, "_DATA_DIR", tmp_path)
    s = Settings(org_profile="testprofile")

    save_risk_config(RiskConfig(), s)
    expected = tmp_path / "org_profiles" / "testprofile" / "risk_config.yaml"
    assert expected.is_file()


def test_preview_helpers_match_service_behaviour():
    """Die Preview-Funktion verwendet Loader-Methoden, die deterministisch sind."""
    default_cfg = RiskConfig()
    # AVV-Lookup
    assert default_cfg.avv.level_for_score(2.0) in {"low", "medium", "high", "critical"}
    # Matrix-Lookup
    assert default_cfg.dsfa_assessment.risk_level_for(3, 4) in {"low", "medium", "high", "critical"}
    # Score-Range
    pct = default_cfg.avv.normalize_to_percent(2.0)
    assert 0 <= pct <= 100


def test_pydantic_validation_rejects_invalid_matrix():
    """Ein RiskConfig mit unvollständiger Matrix kann nicht erstellt werden
    (dies ist die Schutzlinie im PUT-Endpoint)."""
    from app.services.risk_config_loader import DsfaAssessmentConfig

    with pytest.raises(Exception):
        DsfaAssessmentConfig(scale_type="1-5", matrix={"1_1": "low"})


def test_pydantic_validation_rejects_bad_avv_thresholds():
    """Absteigende thresholds müssen abgelehnt werden."""
    from app.services.risk_config_loader import AvvLevelThreshold, AvvRiskConfig

    with pytest.raises(Exception):
        AvvRiskConfig(
            level_thresholds=[
                AvvLevelThreshold(max_score=5.0, level="low"),
                AvvLevelThreshold(max_score=1.0, level="critical"),
            ]
        )


def test_resolve_writable_path_with_legacy_settings():
    """Settings ohne risk_config_path liefert profilbasierten Pfad."""
    s = Settings(org_profile="default", risk_config_path=None)
    p = resolve_writable_risk_config_path(s)
    # Sollte unter org_profiles/default/risk_config.yaml liegen.
    assert p.name == "risk_config.yaml"
    parts = p.parts
    assert "default" in parts
    assert "org_profiles" in parts


def test_round_trip_default_config_unchanged(tmp_path: Path):
    """Save+Load eines Default-RiskConfig erhält die wichtigsten Werte."""
    target = tmp_path / "risk_config.yaml"
    s = Settings(risk_config_path=str(target))
    original = RiskConfig()
    save_risk_config(original, s)

    reloaded = load_risk_config(s)
    # Numerische Defaults
    assert reloaded.avv.level_for_score(1.5) == "low"
    assert reloaded.dsfa_screening.required_threshold == 2.0
    assert reloaded.case_score.severity_weights["critical"] == 30
    assert reloaded.maturity.weights["vvt"] == pytest.approx(0.2)
    assert reloaded.dsfa_assessment.matrix["5_5"] == "critical"
    assert reloaded.risk_velocity.window_days == 90


def test_resolve_returns_none_when_target_missing():
    """resolve_risk_config_path (read) ≠ resolve_writable_risk_config_path."""
    s = Settings(org_profile="nonexistent_profile_xyz")
    assert resolve_risk_config_path(s) is None
    # Write-side liefert trotzdem einen Pfad.
    write_path = resolve_writable_risk_config_path(s)
    assert write_path.name == "risk_config.yaml"
