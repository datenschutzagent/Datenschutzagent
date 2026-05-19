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
# Section: DSFA screening
# ---------------------------------------------------------------------------


class DsfaScreeningFactor(BaseModel):
    """Declarative spec for a DSFA-screening factor (EDSA 9-factor test).

    Replaces the hardcoded lambdas in dsfa_service. A factor matches if any
    of its conditions is met:
      - ``case_flag`` is set on the case
      - ``keywords_processing_context`` contains a substring of case.processing_context
      - ``keywords_title`` contains a substring of case.title
      - any open finding has a severity in ``findings_severity``
    """

    id: str
    label: str
    description: str = ""
    weight: float = Field(default=1.0, ge=0.0)
    keywords_processing_context: list[str] = Field(default_factory=list)
    keywords_title: list[str] = Field(default_factory=list)
    case_flag: str | None = None  # attribute name on CaseModel that must be truthy
    findings_severity: list[str] = Field(default_factory=list)  # list of FindingSeverity values


_DEFAULT_DSFA_FACTORS: list[dict[str, Any]] = [
    {
        "id": "profiling",
        "label": "Profiling oder automatisierte Entscheidung",
        "description": "Systematische und umfassende Bewertung persönlicher Aspekte durch automatisierte Verarbeitung (Art. 35 Abs. 3 lit. a).",
        "keywords_processing_context": ["profil", "scoring", "automat", "entscheid"],
        "keywords_title": ["profil", "scoring"],
    },
    {
        "id": "special_categories",
        "label": "Besondere Kategorien personenbezogener Daten (Art. 9)",
        "description": "Verarbeitung von Gesundheitsdaten, biometrischen Daten, Daten zur Herkunft etc.",
        "case_flag": "special_category_data",
    },
    {
        "id": "large_scale",
        "label": "Umfangreiche Verarbeitung",
        "description": "Verarbeitung personenbezogener Daten in großem Umfang (viele Betroffene oder große Datenmenge).",
        "keywords_processing_context": ["massendaten", "großmaßst", "umfangreich", "viele betroffene", "large scale"],
    },
    {
        "id": "international_transfer",
        "label": "Internationaler Datentransfer",
        "description": "Übermittlung in Drittländer ohne angemessenes Schutzniveau.",
        "case_flag": "international_transfer",
    },
    {
        "id": "vulnerable_subjects",
        "label": "Schutzbedürftige Betroffene",
        "description": "Kinder, Patienten, Mitarbeiter oder andere schutzbedürftige Personengruppen.",
        "keywords_processing_context": ["kind", "patient", "mitarbeiter", "employee", "schüler", "student", "vulnerable"],
    },
    {
        "id": "systematic_monitoring",
        "label": "Systematische Überwachung",
        "description": "Überwachung öffentlich zugänglicher Bereiche oder systematische Beobachtung.",
        "keywords_processing_context": ["überwach", "kamera", "tracking", "monitoring", "standort", "location"],
    },
    {
        "id": "critical_findings",
        "label": "Kritische Compliance-Befunde",
        "description": "Offene kritische oder hochschwere Befunde aus Playbook-Prüfungen.",
        "findings_severity": ["critical", "high"],
    },
    {
        "id": "sensitive_purpose",
        "label": "Sensibler Verarbeitungszweck",
        "description": "Verarbeitung für Strafverfolgung, Finanzdienstleistungen, Sozialhilfe oder ähnliches.",
        "keywords_processing_context": ["straf", "justiz", "finan", "kredit", "sozial", "versicher", "gesundheit"],
    },
    {
        "id": "innovative_technology",
        "label": "Neue oder innovative Technologie",
        "description": "Einsatz neuer Technologien (KI, Biometrie, IoT) mit unbekannten Risiken.",
        "keywords_processing_context": ["ki ", "künstliche intel", "biometrie", "iot", "internet of things", "blockchain", "neu"],
    },
]


class DsfaScreeningConfig(BaseModel):
    required_threshold: float = Field(default=2.0, ge=0.0)
    factors: list[DsfaScreeningFactor] = Field(
        default_factory=lambda: [DsfaScreeningFactor.model_validate(f) for f in _DEFAULT_DSFA_FACTORS]
    )

    @field_validator("factors")
    @classmethod
    def _unique_ids(cls, v: list[DsfaScreeningFactor]) -> list[DsfaScreeningFactor]:
        ids = [f.id for f in v]
        if len(ids) != len(set(ids)):
            raise ValueError("DSFA screening factor ids must be unique")
        return v


# ---------------------------------------------------------------------------
# Section: DSFA assessment (ISO 27005 Likelihood × Severity Matrix)
# ---------------------------------------------------------------------------


_VALID_RISK_LEVELS = {"low", "medium", "high", "critical"}


def _default_dsfa_matrix() -> dict[str, str]:
    """Standard ISO-27005-ähnliche 5x5-Matrix für Likelihood × Severity → Risikolevel."""
    return {
        "1_1": "low", "1_2": "low", "1_3": "low", "1_4": "medium", "1_5": "medium",
        "2_1": "low", "2_2": "low", "2_3": "medium", "2_4": "medium", "2_5": "high",
        "3_1": "low", "3_2": "medium", "3_3": "medium", "3_4": "high", "3_5": "high",
        "4_1": "medium", "4_2": "medium", "4_3": "high", "4_4": "high", "4_5": "critical",
        "5_1": "medium", "5_2": "high", "5_3": "high", "5_4": "critical", "5_5": "critical",
    }


def _default_dsfa_scale_labels() -> dict[str, dict[int, str]]:
    return {
        "likelihood": {
            1: "sehr unwahrscheinlich",
            2: "unwahrscheinlich",
            3: "möglich",
            4: "wahrscheinlich",
            5: "sehr wahrscheinlich",
        },
        "severity": {
            1: "vernachlässigbar",
            2: "begrenzt",
            3: "spürbar",
            4: "erheblich",
            5: "maximal",
        },
    }


class DsfaAssessmentConfig(BaseModel):
    scale_type: str = Field(default="1-5", description="Skala: '1-5' (heute) oder '1-3' (kompakt)")
    scale_labels: dict[str, dict[int, str]] = Field(default_factory=_default_dsfa_scale_labels)
    matrix: dict[str, str] = Field(default_factory=_default_dsfa_matrix)
    dpo_consultation_required_when_residual_in: list[str] = Field(default_factory=lambda: ["high", "critical"])
    min_confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    @field_validator("scale_type")
    @classmethod
    def _scale_type_known(cls, v: str) -> str:
        if v not in {"1-3", "1-5"}:
            raise ValueError("scale_type must be '1-3' or '1-5'")
        return v

    @field_validator("matrix")
    @classmethod
    def _matrix_complete(cls, v: dict[str, str], info) -> dict[str, str]:
        scale_type = info.data.get("scale_type", "1-5")
        size = 5 if scale_type == "1-5" else 3
        expected = {f"{lik}_{sev}" for lik in range(1, size + 1) for sev in range(1, size + 1)}
        actual = set(v.keys())
        missing = expected - actual
        if missing:
            raise ValueError(f"matrix is missing cells: {sorted(missing)}")
        extra = actual - expected
        if extra:
            raise ValueError(f"matrix has unexpected cells: {sorted(extra)}")
        invalid = {k: lvl for k, lvl in v.items() if lvl not in _VALID_RISK_LEVELS}
        if invalid:
            raise ValueError(f"matrix has invalid risk levels: {invalid}")
        return v

    @field_validator("dpo_consultation_required_when_residual_in")
    @classmethod
    def _dpo_levels_valid(cls, v: list[str]) -> list[str]:
        invalid = [lvl for lvl in v if lvl not in _VALID_RISK_LEVELS]
        if invalid:
            raise ValueError(f"dpo_consultation_required_when_residual_in has invalid levels: {invalid}")
        return v

    def risk_level_for(self, likelihood: int, severity: int) -> str:
        """Look up the risk level for given numeric likelihood/severity (1-based)."""
        return self.matrix[f"{likelihood}_{severity}"]


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
# Section: Risk velocity (trend analysis)
# ---------------------------------------------------------------------------


class RiskVelocityConfig(BaseModel):
    enabled: bool = True
    window_days: int = Field(default=90, ge=1)
    significant_change_pct: float = Field(default=15.0, ge=0.0)

    def classify_trend(self, delta_pct: float) -> str:
        """Return 'up' | 'down' | 'stable' based on |delta| vs threshold."""
        if abs(delta_pct) < self.significant_change_pct:
            return "stable"
        return "up" if delta_pct > 0 else "down"


# ---------------------------------------------------------------------------
# Top-level config
# ---------------------------------------------------------------------------


class RiskConfig(BaseModel):
    version: int = 1
    avv: AvvRiskConfig = Field(default_factory=AvvRiskConfig)
    dsfa_screening: DsfaScreeningConfig = Field(default_factory=DsfaScreeningConfig)
    dsfa_assessment: DsfaAssessmentConfig = Field(default_factory=DsfaAssessmentConfig)
    case_score: CaseScoreConfig = Field(default_factory=CaseScoreConfig)
    maturity: MaturityConfig = Field(default_factory=MaturityConfig)
    risk_velocity: RiskVelocityConfig = Field(default_factory=RiskVelocityConfig)


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
