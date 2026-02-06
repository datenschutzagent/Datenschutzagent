"""VVT normalization: map raw document text to canonical VVT model using LLM."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.core.llm import create_agent

# Canonical VVT field names (DSGVO Art. 30 / common ROPA/VVT templates)
CANONICAL_VVT_FIELD_NAMES = [
    "Zwecke der Verarbeitung",
    "Rechtsgrundlage",
    "Kategorien betroffener Personen",
    "Kategorien personenbezogener Daten",
    "Empfänger / Empfängerkategorien",
    "Drittlandtransfer",
    "Speicherdauer",
    "Technische und organisatorische Maßnahmen (TOMs)",
]


class _VVTExtractionField(BaseModel):
    """Single field as extracted by LLM (internal)."""
    field_name: str = Field(description="Exact name of the VVT field from the canonical list.")
    status: Literal["filled", "missing", "inconsistent"] = Field(
        description="One of: filled, missing, inconsistent"
    )
    canonical_value: str | None = Field(default=None, description="Extracted or normalized value if present.")
    evidence: str | None = Field(default=None, description="Where in the document this was found (e.g. sheet, row, column).")
    finding: str | None = Field(default=None, description="If inconsistent or problematic, short explanation.")


class _VVTExtractionResult(BaseModel):
    """Full extraction result from LLM (internal)."""
    source_template: str = Field(
        default="",
        description="Detected template variant, e.g. 'Variante A', 'Variante B (Psychologie)', 'Unbekannt'."
    )
    fields: list[_VVTExtractionField] = Field(
        default_factory=list,
        description="One entry per canonical VVT field with status and value."
    )


async def normalize_vvt(raw_text: str) -> _VVTExtractionResult:
    """
    Map raw VVT document text to the canonical VVT model using the LLM.
    Returns structured fields (filled/missing/inconsistent) and optional template detection.
    """
    agent = create_agent(
        system_prompt=(
            "You are a data protection expert. Your task is to analyze a German VVT/ROPA (Verzeichnis der "
            "Verarbeitungstätigkeiten / Record of Processing Activities) document text and extract structured "
            "information into the canonical VVT fields. For each of the required fields, set status to "
            "'filled' if the document contains a clear value, 'missing' if absent or empty, and 'inconsistent' "
            "if the value contradicts other documents or is legally problematic. Provide evidence (e.g. sheet name, "
            "row/column) and finding (e.g. short issue description) when relevant. Also detect the template "
            "variant if recognizable (e.g. Variante A, Variante B Psychologie, standard ROPA)."
        )
    )
    truncated = (raw_text or "")[:25000]
    field_list = ", ".join(f'"{n}"' for n in CANONICAL_VVT_FIELD_NAMES)
    prompt = f"""
Analyze the following VVT/ROPA document text and extract all canonical fields.

Required fields (use these exact names): {field_list}

Document text:
---
{truncated}
---

For each required field, provide: field_name (exactly as in the list), status (filled|missing|inconsistent), 
canonical_value (normalized German text or null if missing), evidence (where found, e.g. 'Sheet X, Zeile 12, Spalte C'), 
and finding (only if status is inconsistent or there is a problem).
Also set source_template to the detected template variant or 'Unbekannt'.
"""
    result = await agent.run(prompt, result_type=_VVTExtractionResult)
    data = result.data

    # Ensure we have one entry per canonical field; fill missing with "missing"
    seen = {f.field_name for f in data.fields}
    for name in CANONICAL_VVT_FIELD_NAMES:
        if name not in seen:
            data.fields.append(
                _VVTExtractionField(
                    field_name=name,
                    status="missing",
                    canonical_value=None,
                    evidence=None,
                    finding=None,
                )
            )
    # Sort to match canonical order
    name_to_idx = {n: i for i, n in enumerate(CANONICAL_VVT_FIELD_NAMES)}
    data.fields.sort(key=lambda f: name_to_idx.get(f.field_name, 999))
    return data
