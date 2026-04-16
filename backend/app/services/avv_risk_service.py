"""AVV-Risikobewertung: Bewertet Supplier-/Auftragsverarbeiter-Risiko via LLM.

Führt eine strukturierte Risikobewertung durch basierend auf:
  - Vertragsgegenstand
  - Partnertyp (AV vs. Unter-AV)
  - Datenkategorien (aus Vertragsgegenstand abgeleitet)
  - Subauftragsverarbeiter-Risiko
  - Drittland-Risiko
"""
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import create_agent
from app.core.prompt_security import sanitize_prompt_field
from app.models.db import AVVContractModel

logger = logging.getLogger(__name__)


_AVV_RISK_SYSTEM = """Du bist ein Datenschutzexperte und bewertest Datenschutz-Risiken bei Auftragsverarbeitern (Art. 28 DSGVO).
Analysiere die bereitgestellten Vertragsinformationen und erstelle eine strukturierte Risikobewertung.
Bewerte folgende Risikodimensionen auf einer Skala von 1 (sehr gering) bis 5 (sehr hoch):
1. Datensensitivität (Art der verarbeiteten Daten)
2. Zugriffsumfang (Menge und Tiefe des Datenzugriffs)
3. Drittlandrisiko (Datenübermittlung außerhalb EU/EWR)
4. Subauftragsverarbeiter-Risiko (Weitergabe an Unterauftragnehmer)
5. Vertragliche Absicherung (Vollständigkeit der AVV-Klauseln)
Antworte ausschließlich auf Deutsch."""

_AVV_RISK_USER_TEMPLATE = """Bewerte das Datenschutz-Risiko für folgenden Auftragsverarbeiter:

**Partnername**: {partner_name}
**Partnertyp**: {partner_type}
**Vertragsgegenstand**: {subject_matter}
**Abteilung**: {department}
**Notizen**: {notes}

Erstelle eine Risikobewertung mit:
1. Scores für alle 5 Risikodimensionen (1-5)
2. Gesamtrisikobewertung
3. Hauptrisiken (max. 3)
4. Empfohlene Maßnahmen (max. 5)"""


class _AVVRiskDimension(BaseModel):
    name: str = Field(description="Name der Risikodimension")
    score: int = Field(description="Risikoscore 1-5", ge=1, le=5)
    rationale: str = Field(description="Begründung des Scores")


class _AVVRiskResult(BaseModel):
    dimensions: list[_AVVRiskDimension] = Field(description="Bewertete Risikodimensionen")
    overall_risk_level: str = Field(description="Gesamtrisiko: low, medium, high oder critical")
    main_risks: list[str] = Field(description="Hauptrisiken (max. 3)")
    recommended_measures: list[str] = Field(description="Empfohlene Maßnahmen")
    summary: str = Field(description="Kurze Zusammenfassung der Bewertung")


def _risk_level_from_score(score: float) -> str:
    if score <= 1.5:
        return "low"
    if score <= 2.5:
        return "medium"
    if score <= 3.5:
        return "high"
    return "critical"


async def assess_avv_risk(contract_id: UUID, db: AsyncSession) -> dict[str, Any]:
    """Führt eine LLM-gestützte Risikobewertung für einen AVV durch.

    Returns dict mit score (0-100), risk_level, dimensions, recommendations.
    """
    result = await db.execute(select(AVVContractModel).where(AVVContractModel.id == contract_id))
    contract = result.scalar_one_or_none()
    if not contract:
        raise ValueError(f"AVV {contract_id} not found")

    logger.info("AVV risk assessment started", extra={"contract_id": str(contract_id)})

    partner_type_label = (
        "Auftragsverarbeiter (direkter AV)" if contract.partner_type == "processor"
        else "Unter-Auftragsverarbeiter (Sub-AV, höheres Risiko)"
    )

    user_content = _AVV_RISK_USER_TEMPLATE.format(
        partner_name=sanitize_prompt_field(contract.partner_name, max_chars=200),
        partner_type=partner_type_label,
        subject_matter=sanitize_prompt_field(contract.subject_matter or "Nicht angegeben", max_chars=2000),
        department=sanitize_prompt_field(contract.department or "Nicht angegeben", max_chars=200),
        notes=sanitize_prompt_field(contract.notes or "Keine Notizen", max_chars=1000),
    )

    agent = create_agent(_AVV_RISK_SYSTEM)
    try:
        llm_result = await agent.run(user_content, output_type=_AVVRiskResult)
    except Exception as exc:
        logger.error(
            "AVV risk assessment LLM call failed: %s", exc,
            extra={"contract_id": str(contract_id)},
        )
        raise
    data = llm_result.output

    # Score normalisieren (Durchschnitt der Dimensionen, skaliert auf 0-100)
    scores = [d.score for d in data.dimensions] if data.dimensions else [3]
    avg_score = sum(scores) / len(scores)
    risk_score = min(100, max(0, int((avg_score - 1) / 4 * 100)))

    # overall_risk_level normalisieren
    valid_levels = {"low", "medium", "high", "critical"}
    overall_level = data.overall_risk_level.lower().strip()
    if overall_level not in valid_levels:
        overall_level = _risk_level_from_score(avg_score)

    assessment = {
        "dimensions": [
            {"name": d.name, "score": d.score, "rationale": d.rationale}
            for d in data.dimensions
        ],
        "main_risks": list(data.main_risks),
        "recommended_measures": list(data.recommended_measures),
        "summary": data.summary,
        "avg_dimension_score": round(avg_score, 2),
    }

    # AVV-Modell aktualisieren
    contract.risk_score = risk_score
    contract.risk_level = overall_level
    contract.risk_assessment = assessment
    contract.risk_assessed_at = datetime.now(timezone.utc)
    await db.flush()

    logger.info(
        "AVV risk assessment complete",
        extra={"contract_id": str(contract_id), "risk_score": risk_score, "risk_level": overall_level},
    )

    return {
        "contract_id": str(contract_id),
        "partner_name": contract.partner_name,
        "risk_score": risk_score,
        "risk_level": overall_level,
        "assessment": assessment,
        "assessed_at": contract.risk_assessed_at.isoformat(),
    }
