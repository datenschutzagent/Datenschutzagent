"""Load risk-model configuration (thresholds, weights) from YAML per org profile.

Risk thresholds and weights that were previously hardcoded across the risk-model
services (AVV, DSFA, Case-Score, Maturity) are externalised here. Resolution
follows the same pattern as ``org_profile_loader.py``:

    env override → org_profiles/{profile}/risk_config.yaml → built-in defaults

Missing files, missing sections, or missing individual fields all fall back to
the built-in defaults — so removing the YAML entirely keeps the original
behaviour bit-for-bit.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator

from app.config import Settings
from app.config import settings as default_settings

logger = logging.getLogger(__name__)

_APP_DIR = Path(__file__).resolve().parent.parent
_DATA_DIR = _APP_DIR / "data"


# ---------------------------------------------------------------------------
# Section: AVV risk
# ---------------------------------------------------------------------------


class AvvLevelThreshold(BaseModel):
    max_score: float = Field(ge=0)
    level: str


class AvvScoreNormalization(BaseModel):
    score_min: float = 1.0
    score_max: float = 5.0

    @field_validator("score_max")
    @classmethod
    def _max_gt_min(cls, v: float, info) -> float:
        score_min = info.data.get("score_min", 1.0)
        if v <= score_min:
            raise ValueError("score_max must be greater than score_min")
        return v


class AvvRiskConfig(BaseModel):
    level_thresholds: list[AvvLevelThreshold] = Field(
        default_factory=lambda: [
            AvvLevelThreshold(max_score=1.5, level="low"),
            AvvLevelThreshold(max_score=2.5, level="medium"),
            AvvLevelThreshold(max_score=3.5, level="high"),
            AvvLevelThreshold(max_score=5.0, level="critical"),
        ]
    )
    score_normalization: AvvScoreNormalization = Field(default_factory=AvvScoreNormalization)
    dimension_weights: dict[str, float] = Field(default_factory=dict)
    min_confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    @field_validator("level_thresholds")
    @classmethod
    def _ascending_thresholds(cls, v: list[AvvLevelThreshold]) -> list[AvvLevelThreshold]:
        if not v:
            raise ValueError("level_thresholds must not be empty")
        previous = float("-inf")
        for entry in v:
            if entry.max_score < previous:
                raise ValueError("level_thresholds must be ordered ascending by max_score")
            previous = entry.max_score
        return v

    def level_for_score(self, score: float) -> str:
        """Return the level label for a numeric score on the configured scale.

        Mirrors the legacy ``_risk_level_from_score`` semantics: the first
        threshold whose ``max_score`` is >= the score wins; values above the
        highest threshold fall back to that threshold's level (critical by
        default).
        """
        for entry in self.level_thresholds:
            if score <= entry.max_score:
                return entry.level
        return self.level_thresholds[-1].level

    def normalize_to_percent(self, score: float) -> int:
        """Map a raw score on [score_min, score_max] linearly onto 0..100."""
        rng = self.score_normalization.score_max - self.score_normalization.score_min
        if rng <= 0:
            return 0
        normalized = (score - self.score_normalization.score_min) / rng * 100
        return min(100, max(0, int(normalized)))


# ---------------------------------------------------------------------------
# Section: DSFA screening (kept minimal for Phase A — threshold only)
# ---------------------------------------------------------------------------


class DsfaScreeningConfig(BaseModel):
    required_threshold: int = Field(default=2, ge=1)


# ---------------------------------------------------------------------------
# Section: Case score
# ---------------------------------------------------------------------------


class CaseScoreConfig(BaseModel):
    severity_weights: dict[str, int] = Field(
        default_factory=lambda: {"critical": 30, "high": 15, "medium": 5, "low": 0, "info": 0}
    )
    max_score: int = Field(default=100, gt=0)


# ---------------------------------------------------------------------------
# Section: Maturity
# ---------------------------------------------------------------------------


class MaturityVelocityConfig(BaseModel):
    optimal_days: int = Field(default=14, ge=0)
    worst_days: int = Field(default=60, gt=0)

    @field_validator("worst_days")
    @classmethod
    def _worst_gt_optimal(cls, v: int, info) -> int:
        optimal = info.data.get("optimal_days", 14)
        if v <= optimal:
            raise ValueError("worst_days must be greater than optimal_days")
        return v


class MaturityConfig(BaseModel):
    weights: dict[str, float] = Field(
        default_factory=lambda: {"vvt": 0.20, "dsfa": 0.20, "avv": 0.20, "tom": 0.20, "velocity": 0.20}
    )
    velocity: MaturityVelocityConfig = Field(default_factory=MaturityVelocityConfig)


# ---------------------------------------------------------------------------
# Top-level config
# ---------------------------------------------------------------------------


class RiskConfig(BaseModel):
    version: int = 1
    avv: AvvRiskConfig = Field(default_factory=AvvRiskConfig)
    dsfa_screening: DsfaScreeningConfig = Field(default_factory=DsfaScreeningConfig)
    case_score: CaseScoreConfig = Field(default_factory=CaseScoreConfig)
    maturity: MaturityConfig = Field(default_factory=MaturityConfig)


# ---------------------------------------------------------------------------
# Resolution + loading
# ---------------------------------------------------------------------------


def resolve_risk_config_path(settings: Settings) -> Path | None:
    """Resolve the YAML path for the current org profile, or None if no file exists.

    Resolution order:
    1. ``settings.risk_config_path`` (env override; absolute or relative to data dir)
    2. ``data/org_profiles/{org_profile}/risk_config.yaml`` if present
    3. ``None`` — caller falls back to built-in defaults
    """
    override = (getattr(settings, "risk_config_path", None) or "").strip()
    if override:
        path = Path(override)
        if not path.is_absolute():
            path = _DATA_DIR / path
        return path
    profile = (settings.org_profile or "default").strip() or "default"
    candidate = _DATA_DIR / "org_profiles" / profile / "risk_config.yaml"
    if candidate.is_file():
        return candidate
    return None


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except (OSError, yaml.YAMLError) as exc:
        logger.warning("Failed to read risk_config YAML at %s: %s", path, exc)
        return {}
    return data if isinstance(data, dict) else {}


def load_risk_config(settings: Settings) -> RiskConfig:
    """Load and validate the risk config for the current settings.

    Returns built-in defaults on missing file, missing sections, or validation
    errors — never raises, so a malformed YAML can't crash the API.
    """
    path = resolve_risk_config_path(settings)
    if path is None or not path.is_file():
        return RiskConfig()
    raw = _load_yaml(path)
    if not raw:
        return RiskConfig()
    try:
        return RiskConfig.model_validate(raw)
    except Exception as exc:
        logger.warning(
            "risk_config at %s failed validation, using defaults: %s",
            path,
            exc,
        )
        return RiskConfig()


@lru_cache(maxsize=8)
def _cached_config_for_key(cache_key: str) -> RiskConfig:
    """Internal: cache by profile name + override path (the only inputs to resolution)."""
    return load_risk_config(default_settings)


def get_risk_config(settings: Settings | None = None) -> RiskConfig:
    """Return the cached risk config for the active settings.

    ``settings`` defaults to the application singleton. The cache key combines
    the org profile and the override path, so changes to env vars between
    requests are picked up on next call after ``reload_risk_config()``.
    """
    s = settings or default_settings
    key = f"{s.org_profile or 'default'}|{(getattr(s, 'risk_config_path', '') or '').strip()}"
    # The cache value is computed via load_risk_config(default_settings) — but
    # for non-default callers (tests passing custom settings) we bypass the cache.
    if settings is None or settings is default_settings:
        return _cached_config_for_key(key)
    return load_risk_config(s)


def reload_risk_config() -> None:
    """Invalidate the cache — call after editing risk_config.yaml at runtime."""
    _cached_config_for_key.cache_clear()
