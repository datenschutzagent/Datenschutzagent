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
from app.models.db import AVVContractModel, AvvMitigationLinkModel
from app.services.mitigation_service import apply_avv_mitigations
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

    # Inherent Score: gewichteter Mittelwert der LLM-Dimensions-Scores (1-5)
    # → 0-100 + level.
    cfg = get_risk_config()
    avv_cfg = cfg.avv
    inherent_avg = _weighted_average(list(data.dimensions), avv_cfg.dimension_weights) if data.dimensions else 3.0
    inherent_pct = avv_cfg.normalize_to_percent(inherent_avg)
    inherent_level = avv_cfg.level_for_score(inherent_avg)

    # LLM-vorgeschlagenes Level wird nur akzeptiert, wenn es ein gültiges
    # Config-Level ist und für den inherent score plausibel — sonst Config-Wahrheit.
    valid_levels = {entry.level for entry in avv_cfg.level_thresholds}
    llm_level = (data.overall_risk_level or "").lower().strip()
    if llm_level not in valid_levels:
        llm_level = inherent_level

    # Residual via Mitigation-Katalog (falls aktiviert + aktive Links).
    applied_ids = await _load_applied_mitigation_ids(contract_id, db)
    inherent_dimensions = [
        {"name": d.name, "score": d.score, "rationale": d.rationale}
        for d in data.dimensions
    ]
    if cfg.mitigations.enabled and applied_ids:
        residual = apply_avv_mitigations(
            inherent_dimensions=inherent_dimensions,
            applied_mitigation_ids=applied_ids,
            catalog=cfg.mitigations,
            avv_cfg=avv_cfg,
        )
        residual_dimensions = residual["residual_dimensions"]
        residual_pct = residual["residual_risk_score"]
        residual_level = residual["residual_risk_level"]
        residual_avg = residual["residual_avg_score"]
        applied_effects = residual["applied_effects"]
    else:
        # Keine Mitigations → residual = inherent.
        residual_dimensions = inherent_dimensions
        residual_pct = inherent_pct
        residual_level = inherent_level
        residual_avg = inherent_avg
        applied_effects = []

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
        # Inherent (pre-mitigation).
        "inherent": {
            "dimensions": inherent_dimensions,
            "avg_dimension_score": round(inherent_avg, 2),
            "risk_score": inherent_pct,
            "risk_level": inherent_level,
        },
        # Residual (post-mitigation) – equals inherent when no mitigations linked.
        "residual": {
            "dimensions": residual_dimensions,
            "avg_dimension_score": round(residual_avg, 2),
            "risk_score": residual_pct,
            "risk_level": residual_level,
        },
        "applied_mitigations": applied_ids,
        "applied_effects": applied_effects,
        # LLM context (unchanged shape for backward-compat consumers).
        "dimensions": inherent_dimensions,
        "main_risks": list(data.main_risks),
        "recommended_measures": list(data.recommended_measures),
        "summary": data.summary,
        "avg_dimension_score": round(inherent_avg, 2),
        "confidence": confidence,
        "low_confidence": low_confidence,
    }

    # AVV-Modell aktualisieren: risk_score / risk_level immer = residual,
    # damit bestehende Konsumenten der API unverändert weiterarbeiten.
    contract.inherent_risk_score = inherent_pct
    contract.inherent_risk_level = inherent_level
    contract.risk_score = residual_pct
    contract.risk_level = residual_level
    contract.risk_assessment = assessment
    contract.risk_assessed_at = datetime.now(UTC)
    await db.flush()

    logger.info(
        "AVV risk assessment complete",
        extra={
            "contract_id": str(contract_id),
            "inherent_risk_score": inherent_pct,
            "residual_risk_score": residual_pct,
            "applied_mitigations": len(applied_ids),
        },
    )

    return {
        "contract_id": str(contract_id),
        "partner_name": contract.partner_name,
        "risk_score": residual_pct,
        "risk_level": residual_level,
        "inherent_risk_score": inherent_pct,
        "inherent_risk_level": inherent_level,
        "assessment": assessment,
        "assessed_at": contract.risk_assessed_at.isoformat(),
    }


async def _load_applied_mitigation_ids(contract_id: UUID, db: AsyncSession) -> list[str]:
    """Return the catalog-ids of mitigations currently linked to an AVV contract."""
    result = await db.execute(
        select(AvvMitigationLinkModel.mitigation_id).where(
            AvvMitigationLinkModel.avv_contract_id == contract_id
        )
    )
    return [row for row in result.scalars().all()]
