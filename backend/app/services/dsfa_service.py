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
from app.models.db import CaseModel, DSFAAssessmentModel, FindingModel
from app.services.risk_config_loader import get_risk_config

logger = logging.getLogger(__name__)

_DSFA_SYSTEM_PROMPT = """Du bist ein Datenschutzexperte. Erstelle eine strukturierte Datenschutz-Folgenabschätzung (DSFA)
gemäß Art. 35 DSGVO auf Basis der bereitgestellten Informationen zum Verarbeitungsvorgang.

Analysiere:
1. Notwendigkeit und Verhältnismäßigkeit der Verarbeitung
2. Risiken für betroffene Personen (Eintrittswahrscheinlichkeit und Schwere)
3. Maßnahmen zur Risikobeherrschung
4. Verbleibendes Restrisiko

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


class _DSFARiskLLM(BaseModel):
    description: str = Field(description="Beschreibung des Risikos")
    likelihood: str = Field(description="Eintrittswahrscheinlichkeit: low, medium oder high")
    severity: str = Field(description="Schwere des Risikos: low, medium oder high")
    mitigation: str = Field(description="Gegenmaßnahme zur Risikobeherrschung")


class _DSFAResult(BaseModel):
    necessity_assessment: str = Field(description="Bewertung der Notwendigkeit der Verarbeitung")
    proportionality_assessment: str = Field(description="Verhältnismäßigkeitsprüfung")
    risks: list[_DSFARiskLLM] = Field(description="Liste der identifizierten Risiken")
    residual_risk: str = Field(description="Verbleibendes Restrisiko: low, medium oder high")
    dpo_consultation_required: bool = Field(description="Ob DSB-Konsultation erforderlich ist")
    measures: list[str] = Field(description="Liste der ergriffenen/empfohlenen Maßnahmen")


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

    agent = create_agent(_DSFA_SYSTEM_PROMPT)
    try:
        result = await agent.run(user_content, output_type=_DSFAResult)
    except Exception as exc:
        logger.error("DSFA LLM generation failed: %s", exc, extra={"case_id": str(case_id)})
        raise
    data = result.output

    # Normalisiere Werte (LLM könnte abweichende Strings liefern)
    valid_levels = {"low", "medium", "high"}

    def _normalize_level(val: str) -> str:
        v = str(val).strip().lower()
        return v if v in valid_levels else "medium"

    risks_payload = [
        {
            "description": r.description,
            "likelihood": _normalize_level(r.likelihood),
            "severity": _normalize_level(r.severity),
            "mitigation": r.mitigation,
        }
        for r in data.risks
    ]

    payload = {
        "necessity_assessment": data.necessity_assessment,
        "proportionality_assessment": data.proportionality_assessment,
        "risks": risks_payload,
        "residual_risk": _normalize_level(data.residual_risk),
        "dpo_consultation_required": bool(data.dpo_consultation_required),
        "measures": list(data.measures),
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
