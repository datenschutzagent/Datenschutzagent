"""DSFA-Service: Datenschutz-Folgenabschätzung (Art. 35 DSGVO) per LLM generieren."""
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import create_agent
from app.models.db import CaseModel, DSFAAssessmentModel, DSFAJobModel, FindingModel
from app.models.schemas import DSFARisk

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

    # Offene Befunde mit hoher/kritischer Schwere laden
    findings_result = await db.execute(
        select(FindingModel).where(
            FindingModel.case_id == case_id,
            FindingModel.severity.in_(["critical", "high"]),
            FindingModel.status == "open",
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
    except Exception:
        pass

    findings_info = "Keine kritischen/hohen offenen Befunde."
    if findings:
        lines = []
        for f in findings:
            lines.append(f"- [{f.severity.upper()}] {f.check_name}: {f.description[:200]}")
        findings_info = "\n".join(lines)

    user_content = _DSFA_USER_TEMPLATE.format(
        title=case.title,
        department=case.department,
        case_type=case.case_type,
        special_category="Ja" if case.special_category_data else "Nein",
        international_transfer="Ja" if case.international_transfer else "Nein",
        vvt_info=vvt_info,
        findings_info=findings_info,
    )

    agent = create_agent(_DSFA_SYSTEM_PROMPT)
    result = await agent.run(user_content, result_type=_DSFAResult)
    data = result.data

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
    return payload


async def save_dsfa(case_id: UUID, payload: dict[str, Any], db: AsyncSession) -> DSFAAssessmentModel:
    """Persistiert die DSFA. Überschreibt vorhandene."""
    model = DSFAAssessmentModel(
        case_id=case_id,
        status="draft",
        payload=payload,
        generated_at=datetime.now(timezone.utc),
    )
    await db.merge(model)
    await db.flush()
    result = await db.execute(select(DSFAAssessmentModel).where(DSFAAssessmentModel.case_id == case_id))
    return result.scalar_one()
