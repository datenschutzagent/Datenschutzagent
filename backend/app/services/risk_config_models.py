"""Pydantic models for the risk configuration (AVV, DSFA, Maturity, Mitigations, TOM baseline).

Extracted from risk_config_loader.py so the models are importable without pulling in
the YAML-loading and caching infrastructure.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

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
    score_normalization: AvvScoreNormalization = Field(
        default_factory=AvvScoreNormalization
    )
    dimension_weights: dict[str, float] = Field(default_factory=dict)
    min_confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    @field_validator("level_thresholds")
    @classmethod
    def _ascending_thresholds(
        cls, v: list[AvvLevelThreshold]
    ) -> list[AvvLevelThreshold]:
        if not v:
            raise ValueError("level_thresholds must not be empty")
        previous = float("-inf")
        for entry in v:
            if entry.max_score < previous:
                raise ValueError(
                    "level_thresholds must be ordered ascending by max_score"
                )
            previous = entry.max_score
        return v

    def level_for_score(self, score: float) -> str:
        for entry in self.level_thresholds:
            if score <= entry.max_score:
                return entry.level
        return self.level_thresholds[-1].level

    def normalize_to_percent(self, score: float) -> int:
        rng = self.score_normalization.score_max - self.score_normalization.score_min
        if rng <= 0:
            return 0
        normalized = (score - self.score_normalization.score_min) / rng * 100
        return min(100, max(0, int(normalized)))


# ---------------------------------------------------------------------------
# Section: DSFA screening
# ---------------------------------------------------------------------------


class DsfaScreeningFactor(BaseModel):
    id: str
    label: str
    description: str = ""
    weight: float = Field(default=1.0, ge=0.0)
    keywords_processing_context: list[str] = Field(default_factory=list)
    keywords_title: list[str] = Field(default_factory=list)
    case_flag: str | None = None
    findings_severity: list[str] = Field(default_factory=list)


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
        "keywords_processing_context": [
            "massendaten",
            "großmaßst",
            "umfangreich",
            "viele betroffene",
            "large scale",
        ],
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
        "keywords_processing_context": [
            "kind",
            "patient",
            "mitarbeiter",
            "employee",
            "schüler",
            "student",
            "vulnerable",
        ],
    },
    {
        "id": "systematic_monitoring",
        "label": "Systematische Überwachung",
        "description": "Überwachung öffentlich zugänglicher Bereiche oder systematische Beobachtung.",
        "keywords_processing_context": [
            "überwach",
            "kamera",
            "tracking",
            "monitoring",
            "standort",
            "location",
        ],
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
        "keywords_processing_context": [
            "straf",
            "justiz",
            "finan",
            "kredit",
            "sozial",
            "versicher",
            "gesundheit",
        ],
    },
    {
        "id": "innovative_technology",
        "label": "Neue oder innovative Technologie",
        "description": "Einsatz neuer Technologien (KI, Biometrie, IoT) mit unbekannten Risiken.",
        "keywords_processing_context": [
            "ki ",
            "künstliche intel",
            "biometrie",
            "iot",
            "internet of things",
            "blockchain",
            "neu",
        ],
    },
]

_VALID_RULE_ACTIONS = {"require_dsfa", "skip_dsfa"}


class DsfaScreeningRule(BaseModel):
    id: str = Field(..., min_length=1, max_length=80)
    label: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    expression: str = Field(..., min_length=1)
    action: str = Field(default="require_dsfa")

    @field_validator("action")
    @classmethod
    def _action_known(cls, v: str) -> str:
        if v not in _VALID_RULE_ACTIONS:
            raise ValueError(f"action must be one of {sorted(_VALID_RULE_ACTIONS)}")
        return v

    @field_validator("expression")
    @classmethod
    def _expression_parses(cls, v: str) -> str:
        from app.services.boolean_rule_parser import parse

        try:
            parse(v)
        except ValueError as exc:
            raise ValueError(f"Invalid boolean expression: {exc}") from exc
        return v


class DsfaScreeningConfig(BaseModel):
    required_threshold: float = Field(default=2.0, ge=0.0)
    factors: list[DsfaScreeningFactor] = Field(
        default_factory=lambda: [
            DsfaScreeningFactor.model_validate(f) for f in _DEFAULT_DSFA_FACTORS
        ]
    )
    rules: list[DsfaScreeningRule] = Field(default_factory=list)

    @field_validator("factors")
    @classmethod
    def _unique_ids(cls, v: list[DsfaScreeningFactor]) -> list[DsfaScreeningFactor]:
        ids = [f.id for f in v]
        if len(ids) != len(set(ids)):
            raise ValueError("DSFA screening factor ids must be unique")
        return v

    @field_validator("rules")
    @classmethod
    def _unique_rule_ids(cls, v: list[DsfaScreeningRule]) -> list[DsfaScreeningRule]:
        ids = [r.id for r in v]
        if len(ids) != len(set(ids)):
            raise ValueError("DSFA screening rule ids must be unique")
        return v

    @model_validator(mode="after")
    def _rule_identifiers_known(self) -> DsfaScreeningConfig:
        from app.services.boolean_rule_parser import collect_identifiers, parse

        factor_ids = {f.id for f in self.factors}
        unknown_by_rule: dict[str, set[str]] = {}
        for rule in self.rules:
            try:
                ast = parse(rule.expression)
            except ValueError:
                continue
            ids = collect_identifiers(ast)
            unknown = ids - factor_ids
            if unknown:
                unknown_by_rule[rule.id] = unknown
        if unknown_by_rule:
            raise ValueError(
                "DSFA screening rules reference unknown factor ids: "
                + ", ".join(
                    f"{rid}: {sorted(missing)}"
                    for rid, missing in unknown_by_rule.items()
                )
            )
        return self


# ---------------------------------------------------------------------------
# Section: DSFA assessment (ISO 27005 Likelihood × Severity Matrix)
# ---------------------------------------------------------------------------

_VALID_RISK_LEVELS = {"low", "medium", "high", "critical"}
_VALID_SCALE_TYPES = {"1-3", "1-5", "1-7"}


def _scale_size(scale_type: str) -> int:
    return int(scale_type.split("-", 1)[1])


def _level_for_normalised(rel_score: float) -> str:
    if rel_score <= 0.20:
        return "low"
    if rel_score <= 0.45:
        return "medium"
    if rel_score <= 0.75:
        return "high"
    return "critical"


def _default_dsfa_matrix_for_size(size: int) -> dict[str, str]:
    out: dict[str, str] = {}
    denom = 2 * (size - 1)
    for lik in range(1, size + 1):
        for sev in range(1, size + 1):
            rel = (lik + sev - 2) / denom if denom else 0.0
            out[f"{lik}_{sev}"] = _level_for_normalised(rel)
    return out


_LEGACY_5X5_MATRIX = {
    "1_1": "low",
    "1_2": "low",
    "1_3": "low",
    "1_4": "medium",
    "1_5": "medium",
    "2_1": "low",
    "2_2": "low",
    "2_3": "medium",
    "2_4": "medium",
    "2_5": "high",
    "3_1": "low",
    "3_2": "medium",
    "3_3": "medium",
    "3_4": "high",
    "3_5": "high",
    "4_1": "medium",
    "4_2": "medium",
    "4_3": "high",
    "4_4": "high",
    "4_5": "critical",
    "5_1": "medium",
    "5_2": "high",
    "5_3": "high",
    "5_4": "critical",
    "5_5": "critical",
}


def _default_dsfa_matrix() -> dict[str, str]:
    return dict(_LEGACY_5X5_MATRIX)


def _default_dsfa_matrix_3x3() -> dict[str, str]:
    return _default_dsfa_matrix_for_size(3)


def _default_dsfa_matrix_7x7() -> dict[str, str]:
    return _default_dsfa_matrix_for_size(7)


def _default_likelihood_labels(size: int) -> dict[int, str]:
    if size == 5:
        return {
            1: "sehr unwahrscheinlich",
            2: "unwahrscheinlich",
            3: "möglich",
            4: "wahrscheinlich",
            5: "sehr wahrscheinlich",
        }
    if size == 3:
        return {1: "unwahrscheinlich", 2: "möglich", 3: "wahrscheinlich"}
    if size == 7:
        return {
            1: "extrem unwahrscheinlich",
            2: "sehr unwahrscheinlich",
            3: "unwahrscheinlich",
            4: "möglich",
            5: "wahrscheinlich",
            6: "sehr wahrscheinlich",
            7: "fast sicher",
        }
    return {i: f"Stufe {i}" for i in range(1, size + 1)}


def _default_severity_labels(size: int) -> dict[int, str]:
    if size == 5:
        return {
            1: "vernachlässigbar",
            2: "begrenzt",
            3: "spürbar",
            4: "erheblich",
            5: "maximal",
        }
    if size == 3:
        return {1: "begrenzt", 2: "spürbar", 3: "erheblich"}
    if size == 7:
        return {
            1: "vernachlässigbar",
            2: "gering",
            3: "begrenzt",
            4: "spürbar",
            5: "erheblich",
            6: "schwer",
            7: "maximal",
        }
    return {i: f"Stufe {i}" for i in range(1, size + 1)}


def _default_dsfa_scale_labels() -> dict[str, dict[int, str]]:
    return {
        "likelihood": _default_likelihood_labels(5),
        "severity": _default_severity_labels(5),
    }


class DsfaAssessmentConfig(BaseModel):
    scale_type: str = Field(default="1-5", description="Skala: '1-3', '1-5' oder '1-7'")
    scale_labels: dict[str, dict[int, str]] = Field(
        default_factory=_default_dsfa_scale_labels
    )
    matrix: dict[str, str] = Field(default_factory=_default_dsfa_matrix)
    dpo_consultation_required_when_residual_in: list[str] = Field(
        default_factory=lambda: ["high", "critical"]
    )
    min_confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    @field_validator("scale_type")
    @classmethod
    def _scale_type_known(cls, v: str) -> str:
        if v not in _VALID_SCALE_TYPES:
            raise ValueError(f"scale_type must be one of {sorted(_VALID_SCALE_TYPES)}")
        return v

    @model_validator(mode="after")
    def _matrix_and_labels_match_scale(self) -> DsfaAssessmentConfig:
        size = _scale_size(self.scale_type)
        expected = {
            f"{lik}_{sev}" for lik in range(1, size + 1) for sev in range(1, size + 1)
        }

        if self.matrix == _LEGACY_5X5_MATRIX and size != 5:
            object.__setattr__(self, "matrix", _default_dsfa_matrix_for_size(size))

        actual = set(self.matrix.keys())
        missing = expected - actual
        if missing:
            raise ValueError(f"matrix is missing cells: {sorted(missing)}")
        extra = actual - expected
        if extra:
            raise ValueError(f"matrix has unexpected cells: {sorted(extra)}")
        invalid = {
            k: lvl for k, lvl in self.matrix.items() if lvl not in _VALID_RISK_LEVELS
        }
        if invalid:
            raise ValueError(f"matrix has invalid risk levels: {invalid}")

        if self.scale_labels == _default_dsfa_scale_labels() and size != 5:
            object.__setattr__(
                self,
                "scale_labels",
                {
                    "likelihood": _default_likelihood_labels(size),
                    "severity": _default_severity_labels(size),
                },
            )

        for axis_name in ("likelihood", "severity"):
            axis = self.scale_labels.get(axis_name) or {}
            for i in range(1, size + 1):
                if i not in axis:
                    raise ValueError(
                        f"scale_labels.{axis_name} is missing entry {i} for scale {self.scale_type!r}"
                    )

        return self

    @field_validator("dpo_consultation_required_when_residual_in")
    @classmethod
    def _dpo_levels_valid(cls, v: list[str]) -> list[str]:
        invalid = [lvl for lvl in v if lvl not in _VALID_RISK_LEVELS]
        if invalid:
            raise ValueError(
                f"dpo_consultation_required_when_residual_in has invalid levels: {invalid}"
            )
        return v

    @property
    def size(self) -> int:
        return _scale_size(self.scale_type)

    def risk_level_for(self, likelihood: int, severity: int) -> str:
        return self.matrix[f"{likelihood}_{severity}"]


# ---------------------------------------------------------------------------
# Section: Case score
# ---------------------------------------------------------------------------


class CaseScoreConfig(BaseModel):
    severity_weights: dict[str, int] = Field(
        default_factory=lambda: {
            "critical": 30,
            "high": 15,
            "medium": 5,
            "low": 0,
            "info": 0,
        }
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
        default_factory=lambda: {
            "vvt": 0.20,
            "dsfa": 0.20,
            "avv": 0.20,
            "tom": 0.20,
            "velocity": 0.20,
        }
    )
    velocity: MaturityVelocityConfig = Field(default_factory=MaturityVelocityConfig)


# ---------------------------------------------------------------------------
# Section: Risk velocity
# ---------------------------------------------------------------------------


class RiskVelocityConfig(BaseModel):
    enabled: bool = True
    window_days: int = Field(default=90, ge=1)
    significant_change_pct: float = Field(default=15.0, ge=0.0)

    def classify_trend(self, delta_pct: float) -> str:
        if abs(delta_pct) < self.significant_change_pct:
            return "stable"
        return "up" if delta_pct > 0 else "down"


# ---------------------------------------------------------------------------
# Section: Confidence policy
# ---------------------------------------------------------------------------

_VALID_FALLBACK_STRATEGIES = {"none", "rules", "escalate", "both"}


class ConfidencePolicyConfig(BaseModel):
    enabled: bool = Field(default=True)
    low_threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    fallback_strategy: str = Field(default="rules")
    escalation_event_type: str = Field(default="risk.fallback_triggered")

    @field_validator("fallback_strategy")
    @classmethod
    def _strategy_known(cls, v: str) -> str:
        if v not in _VALID_FALLBACK_STRATEGIES:
            raise ValueError(
                f"fallback_strategy must be one of {sorted(_VALID_FALLBACK_STRATEGIES)}"
            )
        return v

    @property
    def emits_audit_event(self) -> bool:
        return self.fallback_strategy in {"escalate", "both"}

    @property
    def uses_rule_fallback(self) -> bool:
        return self.fallback_strategy in {"rules", "both"}


# ---------------------------------------------------------------------------
# Section: Mitigation catalog
# ---------------------------------------------------------------------------

_VALID_MITIGATION_TARGETS = {"avv", "dsfa", "both"}


class MitigationReduction(BaseModel):
    score_delta: float = Field(
        default=0.0, le=0.0, description="AVV: delta on 1-5 avg score (≤0)"
    )
    dimension_deltas: dict[str, float] = Field(default_factory=dict)
    likelihood_delta: int = Field(default=0, le=0)
    severity_delta: int = Field(default=0, le=0)
    applicable_risk_keywords: list[str] = Field(default_factory=list)

    @field_validator("dimension_deltas")
    @classmethod
    def _dim_deltas_non_positive(cls, v: dict[str, float]) -> dict[str, float]:
        bad = {k: val for k, val in v.items() if val > 0}
        if bad:
            raise ValueError(f"dimension_deltas must be ≤ 0 (got positive: {bad})")
        return v


class MitigationConfig(BaseModel):
    id: str = Field(..., min_length=1, max_length=80)
    label: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    applies_to: str = Field(default="both")
    tom_category: str | None = Field(default=None)
    reduction: MitigationReduction = Field(default_factory=MitigationReduction)
    evidence_required: bool = Field(default=False)

    @field_validator("applies_to")
    @classmethod
    def _applies_to_known(cls, v: str) -> str:
        if v not in _VALID_MITIGATION_TARGETS:
            raise ValueError(
                f"applies_to must be one of {sorted(_VALID_MITIGATION_TARGETS)}"
            )
        return v


class MitigationCatalogConfig(BaseModel):
    enabled: bool = Field(default=True)
    min_likelihood: int = Field(default=1, ge=1, le=5)
    min_severity: int = Field(default=1, ge=1, le=5)
    min_avv_score: float = Field(default=1.0, ge=1.0, le=5.0)
    catalog: list[MitigationConfig] = Field(default_factory=list)

    @field_validator("catalog")
    @classmethod
    def _unique_ids(cls, v: list[MitigationConfig]) -> list[MitigationConfig]:
        ids = [m.id for m in v]
        if len(ids) != len(set(ids)):
            raise ValueError("mitigation catalog ids must be unique")
        return v

    def by_id(self, mitigation_id: str) -> MitigationConfig | None:
        for entry in self.catalog:
            if entry.id == mitigation_id:
                return entry
        return None

    def applicable(self, target: str) -> list[MitigationConfig]:
        if target not in {"avv", "dsfa"}:
            return []
        return [m for m in self.catalog if m.applies_to in (target, "both")]


# ---------------------------------------------------------------------------
# Section: TOM baseline
# ---------------------------------------------------------------------------

_VALID_TOM_BASELINE_SEVERITIES = {"info", "low", "medium", "high", "critical"}


class TomBaselineRequirement(BaseModel):
    id: str = Field(..., min_length=1, max_length=80)
    label: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    category: str = Field(..., description="TOMCategoryEnum value, e.g. encryption")
    severity: str = Field(default="high")
    keywords_title: list[str] = Field(default_factory=list)

    @field_validator("severity")
    @classmethod
    def _severity_known(cls, v: str) -> str:
        if v not in _VALID_TOM_BASELINE_SEVERITIES:
            raise ValueError(
                f"severity must be one of {sorted(_VALID_TOM_BASELINE_SEVERITIES)}"
            )
        return v


class TomBaselineConfig(BaseModel):
    enabled: bool = Field(default=True)
    requirements: list[TomBaselineRequirement] = Field(default_factory=list)

    @field_validator("requirements")
    @classmethod
    def _unique_ids(
        cls, v: list[TomBaselineRequirement]
    ) -> list[TomBaselineRequirement]:
        ids = [r.id for r in v]
        if len(ids) != len(set(ids)):
            raise ValueError("tom_baseline requirement ids must be unique")
        return v


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
    mitigations: MitigationCatalogConfig = Field(
        default_factory=MitigationCatalogConfig
    )
    confidence_policy: ConfidencePolicyConfig = Field(
        default_factory=ConfidencePolicyConfig
    )
    tom_baseline: TomBaselineConfig = Field(default_factory=TomBaselineConfig)
