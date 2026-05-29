"""DSFA-Service: Datenschutz-Folgenabschätzung (Art. 35 DSGVO) per LLM generieren."""
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import FindingSeverity, FindingStatus
from app.core.llm import create_agent
from app.core.prompt_security import sanitize_prompt_field
from app.models.db import ActivityLogModel, CaseMitigationLinkModel, CaseModel, DSFAAssessmentModel, FindingModel
from app.services.mitigation_service import apply_dsfa_mitigations
from app.services.risk_config_loader import get_risk_config
from app.services.risk_fallback_service import compute_dsfa_fallback

logger = logging.getLogger(__name__)

_DSFA_SYSTEM_PROMPT = """Du bist ein Datenschutzexperte. Erstelle eine strukturierte Datenschutz-Folgenabschätzung (DSFA)
gemäß Art. 35 DSGVO auf Basis der bereitgestellten Informationen zum Verarbeitungsvorgang.

Analysiere:
1. Notwendigkeit und Verhältnismäßigkeit der Verarbeitung
2. Risiken für betroffene Personen — bewerte für jedes Risiko:
   - likelihood (Eintrittswahrscheinlichkeit) auf einer Skala von 1 (sehr unwahrscheinlich)
     bis 5 (sehr wahrscheinlich)
   - severity (Schwere) auf einer Skala von 1 (vernachlässigbar) bis 5 (maximal)
3. Maßnahmen zur Risikobeherrschung
4. Bewerte am Ende deine eigene Konfidenz (0.0-1.0). Niedrige Konfidenz ist
   akzeptabel, wenn Informationen unvollständig sind.

Das Risikolevel (low/medium/high/critical) wird automatisch aus der
Likelihood-×-Severity-Matrix abgeleitet — vergib also keine Levels selbst.

Antworte ausschließlich auf Deutsch."""

_DSFA_USER_TEMPLATE = """Erstelle eine DSFA für den folgenden Verarbeitungsvorgang:

**Titel**: {title}
**Abteilung**: {department}
**Vorgangstyp**: {case_type}
**Besondere Kategorien (Art. 9 DSGVO)**: {special_category}
**Internationaler Datentransfer**: {international_transfer}

**VVT-Informationen**:
{vvt_info}

**Offene Befunde (Kritisch/Hoch)**:
{findings_info}

Erstelle die DSFA strukturiert mit Bewertung von Notwendigkeit, Verhältnismäßigkeit, Risiken und Maßnahmen."""


# Mapping zwischen alter String-Skala und neuer numerischer Skala (1-5).
# 3 ist der Median; entspricht der ursprünglichen "medium"-Klassifikation.
_LEVEL_TO_SCORE = {"low": 1, "medium": 3, "high": 5, "critical": 5}
_SCORE_TO_LEVEL = {1: "low", 2: "low", 3: "medium", 4: "high", 5: "high"}

_RESIDUAL_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}

# Marker für die Soft-Migration. Records ohne scale_version sind aus der
# Zeit vor der numerischen Skala und werden beim Lesen normalisiert.
DSFA_SCALE_VERSION_LEGACY = "v1_string"
DSFA_SCALE_VERSION_NUMERIC = "v2_numeric"


def _to_score(value) -> int:
    """Normalize a likelihood/severity value to 1-5. Accepts int or legacy strings."""
    if isinstance(value, bool):  # bool is a subclass of int — exclude explicitly
        return 3
    if isinstance(value, int):
        return max(1, min(5, value))
    if isinstance(value, float):
        return max(1, min(5, int(round(value))))
    if isinstance(value, str):
        return _LEVEL_TO_SCORE.get(value.strip().lower(), 3)
    return 3


def _to_label(score: int) -> str:
    """Map a 1-5 score to a coarse low/medium/high label (for backward-compat)."""
    s = max(1, min(5, int(score)))
    return _SCORE_TO_LEVEL[s]


def _normalize_dsfa_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize a DSFA payload so it always carries both string and numeric fields.

    Handles three input shapes:
      - Legacy v1 (string-only): likelihood/severity as 'low'/'medium'/'high'
      - New v2 (numeric-only): likelihood/severity as int 1-5
      - Mixed (numeric + string already present)

    Output payload always contains for each risk:
      - likelihood: legacy string (low/medium/high)
      - severity: legacy string
      - likelihood_score: int 1-5
      - severity_score: int 1-5
      - risk_level: low/medium/high/critical (deterministic from matrix if v2,
        else derived from max(likelihood, severity))

    Idempotent — safe to call on already-normalized payloads.
    """
    if not isinstance(payload, dict):
        return payload
    normalized = dict(payload)
    cfg = get_risk_config().dsfa_assessment

    raw_risks = normalized.get("risks") or []
    new_risks = []
    for r in raw_risks:
        if not isinstance(r, dict):
            new_risks.append(r)
            continue
        out = dict(r)
        lik_score = _to_score(out.get("likelihood_score", out.get("likelihood")))
        sev_score = _to_score(out.get("severity_score", out.get("severity")))
        out["likelihood_score"] = lik_score
        out["severity_score"] = sev_score
        # Always re-derive the coarse string from the numeric score.
        out["likelihood"] = _to_label(lik_score)
        out["severity"] = _to_label(sev_score)
        # Risk-level: prefer matrix lookup (v2); fall back to max of the two
        # coarse labels for legacy records.
        try:
            out["risk_level"] = cfg.risk_level_for(lik_score, sev_score)
        except KeyError:
            out["risk_level"] = max(out["likelihood"], out["severity"], key=lambda lv: _RESIDUAL_RANK.get(lv, 0))
        new_risks.append(out)
    normalized["risks"] = new_risks

    # Residualrisiko: bei Legacy-Records aus dem String-Feld lesen; sonst aus
    # dem Maximum der Einzelrisiken neu berechnen.
    if new_risks:
        max_level = max(
            (r.get("risk_level", "low") for r in new_risks if isinstance(r, dict)),
            key=lambda lv: _RESIDUAL_RANK.get(lv, 0),
            default="low",
        )
        normalized["residual_risk"] = max_level
        normalized["dpo_consultation_required"] = max_level in cfg.dpo_consultation_required_when_residual_in
    else:
        # Keine Risiken: bestehende Werte erhalten, aber String normalisieren.
        existing = (normalized.get("residual_risk") or "low").strip().lower()
        normalized["residual_risk"] = existing if existing in _RESIDUAL_RANK else "low"

    return normalized


class _DSFARiskLLM(BaseModel):
    description: str = Field(description="Beschreibung des Risikos")
    likelihood: int = Field(description="Eintrittswahrscheinlichkeit 1-5", ge=1, le=5)
    severity: int = Field(description="Schwere des Risikos 1-5", ge=1, le=5)
    mitigation: str = Field(description="Gegenmaßnahme zur Risikobeherrschung")


class _DSFAResult(BaseModel):
    necessity_assessment: str = Field(description="Bewertung der Notwendigkeit der Verarbeitung")
    proportionality_assessment: str = Field(description="Verhältnismäßigkeitsprüfung")
    risks: list[_DSFARiskLLM] = Field(description="Liste der identifizierten Risiken")
    measures: list[str] = Field(description="Liste der ergriffenen/empfohlenen Maßnahmen")
    confidence: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Selbsteinschätzung der LLM-Konfidenz (0=unsicher, 1=sicher)",
    )


async def generate_dsfa(case_id: UUID, db: AsyncSession) -> dict[str, Any]:
    """Generiert eine DSFA für den Vorgang und gibt das Payload-Dict zurück."""
    case_result = await db.execute(select(CaseModel).where(CaseModel.id == case_id))
    case = case_result.scalar_one_or_none()
    if not case:
        raise ValueError(f"Case {case_id} not found")

    logger.info("DSFA generation started", extra={"case_id": str(case_id)})

    # Offene Befunde mit hoher/kritischer Schwere laden
    findings_result = await db.execute(
        select(FindingModel).where(
            FindingModel.case_id == case_id,
            FindingModel.severity.in_([FindingSeverity.CRITICAL, FindingSeverity.HIGH]),
            FindingModel.status == FindingStatus.OPEN,
        ).limit(20)
    )
    findings = findings_result.scalars().all()

    # VVT-Info aus dem DSB-Report holen (falls vorhanden)
    vvt_info = "Keine VVT-Daten verfügbar."
    try:
        from app.models.db import DSBReportModel
        report_result = await db.execute(select(DSBReportModel).where(DSBReportModel.case_id == case_id))
        report_row = report_result.scalar_one_or_none()
        if report_row and report_row.payload:
            summary = report_row.payload.get("summary", {})
            vvt_available = summary.get("vvt_available", False)
            completeness = summary.get("vvt_completeness", 0)
            if vvt_available:
                vvt_info = f"VVT vorhanden, Vollständigkeit: {completeness}%"
    except Exception as exc:
        logger.warning("Could not load DSB report for DSFA context: %s", exc, extra={"case_id": str(case_id)})

    findings_info = "Keine kritischen/hohen offenen Befunde."
    if findings:
        lines = []
        for f in findings:
            lines.append(f"- [{f.severity.upper()}] {f.check_name}: {f.description[:200]}")
        findings_info = "\n".join(lines)

    user_content = _DSFA_USER_TEMPLATE.format(
        title=sanitize_prompt_field(case.title, max_chars=200),
        department=sanitize_prompt_field(case.department, max_chars=100),
        case_type=sanitize_prompt_field(case.case_type, max_chars=100),
        special_category="Ja" if case.special_category_data else "Nein",
        international_transfer="Ja" if case.international_transfer else "Nein",
        vvt_info=sanitize_prompt_field(vvt_info, max_chars=500),
        findings_info=sanitize_prompt_field(findings_info, max_chars=2000),
    )

    cfg = get_risk_config()
    dsfa_cfg = cfg.dsfa_assessment
    policy = cfg.confidence_policy
    source = "llm"
    llm_failed = False

    agent = create_agent(_DSFA_SYSTEM_PROMPT)
    try:
        result = await agent.run(user_content, output_type=_DSFAResult)
        data = result.output
    except Exception as exc:
        logger.error("DSFA LLM generation failed: %s", exc, extra={"case_id": str(case_id)})
        llm_failed = True
        if not (policy.enabled and policy.uses_rule_fallback):
            raise
        data = _dsfa_fallback_result(case, findings)
        source = "rules"

    # If the LLM produced output below the policy threshold, swap in the
    # heuristic. The "both" strategy emits an audit event but keeps the LLM result.
    if not llm_failed and policy.enabled and policy.uses_rule_fallback:
        if float(data.confidence) < policy.low_threshold:
            logger.warning(
                "DSFA LLM confidence below threshold — switching to rules fallback",
                extra={
                    "case_id": str(case_id),
                    "llm_confidence": float(data.confidence),
                    "low_threshold": policy.low_threshold,
                },
            )
            data = _dsfa_fallback_result(case, findings)
            source = "hybrid"

    # Matrix-Lookup pro Risiko: Likelihood × Severity → risk_level
    # (deterministisch aus der Config, nicht aus LLM-Self-Report).
    confidence = float(data.confidence)
    low_confidence = confidence < dsfa_cfg.min_confidence
    if low_confidence:
        logger.warning(
            "DSFA generation has low confidence",
            extra={
                "case_id": str(case_id),
                "confidence": confidence,
                "min_confidence": dsfa_cfg.min_confidence,
            },
        )

    # Emit an audit-log entry when the policy demands escalation or when the
    # source is non-LLM. Audit entry is best-effort — never lets the DSFA fail.
    if source != "llm" or policy.emits_audit_event:
        try:
            db.add(ActivityLogModel(
                case_id=case_id,
                event_type=policy.escalation_event_type,
                payload={
                    "kind": "dsfa",
                    "source": source,
                    "llm_failed": llm_failed,
                    "confidence": confidence,
                    "low_threshold": policy.low_threshold,
                    "strategy": policy.fallback_strategy,
                },
            ))
        except Exception as exc:  # noqa: BLE001 — audit must never break DSFA
            logger.debug("Audit-log emission for DSFA fallback failed: %s", exc, extra={"case_id": str(case_id)})

    inherent_risks_payload = []
    for r in data.risks:
        lik = max(1, min(5, int(r.likelihood)))
        sev = max(1, min(5, int(r.severity)))
        risk_level = dsfa_cfg.risk_level_for(lik, sev)
        inherent_risks_payload.append({
            "description": r.description,
            "likelihood": _to_label(lik),
            "severity": _to_label(sev),
            "likelihood_score": lik,
            "severity_score": sev,
            "risk_level": risk_level,
            "mitigation": r.mitigation,
        })

    # Inherent (vor Mitigation): höchstes Einzelrisiko.
    if inherent_risks_payload:
        inherent_residual = max(
            (r["risk_level"] for r in inherent_risks_payload),
            key=lambda lv: _RESIDUAL_RANK.get(lv, 0),
        )
    else:
        inherent_residual = "low"

    # Residual via Mitigation-Katalog. Wenn keine Mitigations verknüpft sind
    # ist residual == inherent — kompletter Backward-compat.
    applied_ids = await _load_case_mitigation_ids(case_id, db)
    if cfg.mitigations.enabled and applied_ids and inherent_risks_payload:
        residual = apply_dsfa_mitigations(
            inherent_risks=inherent_risks_payload,
            applied_mitigation_ids=applied_ids,
            catalog=cfg.mitigations,
            dsfa_cfg=dsfa_cfg,
        )
        risks_payload = residual["residual_risks"]
        residual_risk = residual["residual_overall_level"]
        applied_effects = residual["applied_effects"]
        dpo_required = residual["dpo_consultation_required"]
    else:
        # Keine Mitigations → spiegele inherent in residual + leeren Effekt-Trace.
        risks_payload = [
            {
                **r,
                "inherent_likelihood_score": r["likelihood_score"],
                "inherent_severity_score": r["severity_score"],
                "inherent_risk_level": r["risk_level"],
                "applied_mitigation_ids": [],
            }
            for r in inherent_risks_payload
        ]
        residual_risk = inherent_residual
        applied_effects = []
        dpo_required = residual_risk in dsfa_cfg.dpo_consultation_required_when_residual_in

    payload = {
        "necessity_assessment": data.necessity_assessment,
        "proportionality_assessment": data.proportionality_assessment,
        "risks": risks_payload,
        "inherent_risks": inherent_risks_payload,
        "inherent_residual_risk": inherent_residual,
        "residual_risk": residual_risk,
        "dpo_consultation_required": dpo_required,
        "measures": list(data.measures),
        "applied_mitigations": applied_ids,
        "applied_effects": applied_effects,
        "source": source,
        "confidence": confidence,
        "low_confidence": low_confidence,
        "scale_version": DSFA_SCALE_VERSION_NUMERIC,
    }
    logger.info(
        "DSFA generation complete",
        extra={
            "case_id": str(case_id),
            "residual_risk": payload["residual_risk"],
            "risk_count": len(risks_payload),
            "dpo_consultation_required": payload["dpo_consultation_required"],
        },
    )
    return payload


def _factor_met(factor, case, findings) -> bool:
    """Generic, declarative check for one DSFA-screening factor spec.

    A factor matches when ANY of its conditions is satisfied:
      - case_flag: attribute on case is truthy
      - keywords_processing_context: substring in case.processing_context (case-insensitive)
      - keywords_title: substring in case.title (case-insensitive)
      - findings_severity: at least one open finding has matching severity

    Replaces the hardcoded lambdas — see risk_config_loader.DsfaScreeningFactor
    and risk_config.yaml.
    """
    if factor.case_flag:
        if getattr(case, factor.case_flag, None):
            return True
    if factor.keywords_processing_context:
        ctx = (case.processing_context or "").lower()
        if any(kw in ctx for kw in factor.keywords_processing_context):
            return True
    if factor.keywords_title:
        title = (case.title or "").lower()
        if any(kw in title for kw in factor.keywords_title):
            return True
    if factor.findings_severity:
        allowed = {s.lower() for s in factor.findings_severity}
        if any((f.severity or "").lower() in allowed for f in findings):
            return True
    return False


# Default-Schwelle (EDSA-Leitlinien). Wird zur Laufzeit aus
# RiskConfig.dsfa_screening.required_threshold gelesen — siehe
# risk_config_loader.py / risk_config.yaml.
_DSFA_REQUIRED_THRESHOLD_DEFAULT = 2.0


async def screen_dsfa_requirement(case_id: UUID, db: AsyncSession) -> dict[str, Any]:
    """Prüft ob eine DSFA gemäß Art. 35 DSGVO erforderlich ist (EDSA-9-Faktoren-Test).

    Returns dict with:
      - required: bool (True wenn ≥2 Risikofaktoren)
      - score: int (Anzahl zutreffender Faktoren)
      - factors: list of dicts with id, label, met
      - recommendation: str
    """
    case_result = await db.execute(select(CaseModel).where(CaseModel.id == case_id))
    case = case_result.scalar_one_or_none()
    if not case:
        raise ValueError(f"Case {case_id} not found")

    findings_result = await db.execute(
        select(FindingModel).where(
            FindingModel.case_id == case_id,
            FindingModel.status == FindingStatus.OPEN,
        )
    )
    findings = findings_result.scalars().all()

    dsfa_cfg = get_risk_config().dsfa_screening
    # Only OPEN findings matter for the "critical_findings" factor.
    open_findings = [f for f in findings if f.status == FindingStatus.OPEN]
    factor_results = []
    score = 0.0
    for factor in dsfa_cfg.factors:
        try:
            met = _factor_met(factor, case, open_findings)
        except Exception as exc:  # noqa: BLE001 — never let a single factor crash screening
            logger.debug("DSFA screening factor '%s' check failed: %s", factor.id, exc, extra={"case_id": str(case_id)})
            met = False
        if met:
            score += factor.weight
        factor_results.append({
            "id": factor.id,
            "label": factor.label,
            "description": factor.description,
            "met": met,
            "weight": factor.weight,
        })

    threshold = dsfa_cfg.required_threshold
    required = score >= threshold
    logger.info(
        "DSFA screening complete",
        extra={"case_id": str(case_id), "score": score, "required": required, "threshold": threshold},
    )

    score_fmt = f"{score:g}"  # 2.0 -> "2", 3.5 -> "3.5"
    threshold_fmt = f"{threshold:g}"
    if score == 0:
        recommendation = "Keine Risikofaktoren identifiziert. DSFA aktuell nicht erforderlich."
    elif not required:
        recommendation = (
            f"Gewichteter Score {score_fmt}. DSFA empfohlen, aber gemäß "
            f"Org-Konfiguration erst ab ≥{threshold_fmt} verpflichtend. "
            f"Bitte regelmäßig neu bewerten."
        )
    elif score < 4:
        recommendation = (
            f"Gewichteter Score {score_fmt}. DSFA ist verpflichtend (Art. 35 DSGVO). "
            f"Bitte umgehend durchführen."
        )
    else:
        recommendation = (
            f"Gewichteter Score {score_fmt} – hohes Datenschutzrisiko. "
            f"DSFA ist dringend erforderlich und sollte vor Beginn der Verarbeitung abgeschlossen sein."
        )

    return {
        "case_id": str(case_id),
        "required": required,
        "score": score,
        "threshold": threshold,
        "factors": factor_results,
        "recommendation": recommendation,
    }


def _dsfa_fallback_result(case: CaseModel, findings) -> "_DSFAResult":
    """Build a ``_DSFAResult`` from the rule-based heuristic."""
    critical_count = sum(
        1 for f in findings
        if (f.severity or "").lower() in {FindingSeverity.CRITICAL, FindingSeverity.HIGH}
        and (f.status or "").lower() == FindingStatus.OPEN
    )
    raw = compute_dsfa_fallback(
        case_title=case.title or "",
        case_type=case.case_type or "",
        processing_context=case.processing_context,
        special_category_data=bool(case.special_category_data),
        international_transfer=bool(case.international_transfer),
        open_critical_findings=critical_count,
    )
    return _DSFAResult.model_validate(raw)


async def _load_case_mitigation_ids(case_id: UUID, db: AsyncSession) -> list[str]:
    """Return the catalog-ids of mitigations currently linked to a case (DSFA)."""
    result = await db.execute(
        select(CaseMitigationLinkModel.mitigation_id).where(
            CaseMitigationLinkModel.case_id == case_id
        )
    )
    return [row for row in result.scalars().all()]


async def save_dsfa(case_id: UUID, payload: dict[str, Any], db: AsyncSession) -> DSFAAssessmentModel:
    """Persistiert die DSFA. Überschreibt vorhandene."""
    model = DSFAAssessmentModel(
        case_id=case_id,
        status="draft",
        payload=payload,
        generated_at=datetime.now(UTC),
    )
    await db.merge(model)
    await db.flush()
    result = await db.execute(select(DSFAAssessmentModel).where(DSFAAssessmentModel.case_id == case_id))
    return result.scalar_one()
