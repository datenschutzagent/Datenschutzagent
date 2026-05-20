"""AVV-Risikobewertung: Bewertet Supplier-/Auftragsverarbeiter-Risiko via LLM.

Führt eine strukturierte Risikobewertung durch basierend auf:
  - Vertragsgegenstand
  - Partnertyp (AV vs. Unter-AV)
  - Datenkategorien (aus Vertragsgegenstand abgeleitet)
  - Subauftragsverarbeiter-Risiko
  - Drittland-Risiko
"""
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import create_agent
from app.core.prompt_security import sanitize_prompt_field
from app.models.db import AVVContractModel
from app.services.risk_config_loader import get_risk_config

logger = logging.getLogger(__name__)


_AVV_RISK_SYSTEM = """Du bist ein Datenschutzexperte und bewertest Datenschutz-Risiken bei Auftragsverarbeitern (Art. 28 DSGVO).
Analysiere die bereitgestellten Vertragsinformationen und erstelle eine strukturierte Risikobewertung.
Bewerte folgende Risikodimensionen auf einer Skala von 1 (sehr gering) bis 5 (sehr hoch):
1. Datensensitivität (Art der verarbeiteten Daten)
2. Zugriffsumfang (Menge und Tiefe des Datenzugriffs)
3. Drittlandrisiko (Datenübermittlung außerhalb EU/EWR)
4. Subauftragsverarbeiter-Risiko (Weitergabe an Unterauftragnehmer)
5. Vertragliche Absicherung (Vollständigkeit der AVV-Klauseln)
Bewerte am Ende zusätzlich deine eigene Konfidenz in die Bewertung als Wert
zwischen 0.0 (sehr unsicher) und 1.0 (sehr sicher). Eine niedrige Konfidenz
ist akzeptabel, wenn die Vertragsinformationen unvollständig sind.
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
4. Empfohlene Maßnahmen (max. 5)
5. Konfidenz deiner Bewertung (0.0-1.0)"""


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
    confidence: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Selbsteinschätzung der LLM-Konfidenz (0=unsicher, 1=sicher)",
    )


def _weighted_average(dimensions: list["_AVVRiskDimension"], weights: dict[str, float]) -> float:
    """Weighted mean of dimension scores; falls back to arithmetic mean if no weights match."""
    if not dimensions:
        return 3.0
    if not weights:
        return sum(d.score for d in dimensions) / len(dimensions)
    total_weight = 0.0
    weighted_sum = 0.0
    for d in dimensions:
        w = weights.get(d.name, 1.0)
        total_weight += w
        weighted_sum += d.score * w
    if total_weight <= 0:
        return sum(d.score for d in dimensions) / len(dimensions)
    return weighted_sum / total_weight


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

    # Score normalisieren (gewichteter Durchschnitt der Dimensionen, skaliert auf 0-100)
    avv_cfg = get_risk_config().avv
    avg_score = _weighted_average(list(data.dimensions), avv_cfg.dimension_weights) if data.dimensions else 3.0
    risk_score = avv_cfg.normalize_to_percent(avg_score)

    # overall_risk_level normalisieren — Config-Thresholds als Quelle der Wahrheit
    valid_levels = {entry.level for entry in avv_cfg.level_thresholds}
    overall_level = data.overall_risk_level.lower().strip()
    if overall_level not in valid_levels:
        overall_level = avv_cfg.level_for_score(avg_score)

    confidence = float(data.confidence)
    low_confidence = confidence < avv_cfg.min_confidence
    if low_confidence:
        logger.warning(
            "AVV risk assessment has low confidence",
            extra={
                "contract_id": str(contract_id),
                "confidence": confidence,
                "min_confidence": avv_cfg.min_confidence,
            },
        )

    assessment = {
        "dimensions": [
            {"name": d.name, "score": d.score, "rationale": d.rationale}
            for d in data.dimensions
        ],
        "main_risks": list(data.main_risks),
        "recommended_measures": list(data.recommended_measures),
        "summary": data.summary,
        "avg_dimension_score": round(avg_score, 2),
        "confidence": confidence,
        "low_confidence": low_confidence,
    }

    # AVV-Modell aktualisieren
    contract.risk_score = risk_score
    contract.risk_level = overall_level
    contract.risk_assessment = assessment
    contract.risk_assessed_at = datetime.now(UTC)
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
