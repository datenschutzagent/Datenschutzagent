"""VVT normalization: map raw document text to canonical VVT model using LLM."""
from __future__ import annotations

import difflib
import logging
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, Field

from app.config import settings
from app.core.llm import create_agent, llm_retry_call
from app.services.org_profile_loader import DEFAULT_VVT_FIELD_NAMES, get_vvt_field_names
from app.services.prompt_template_service import get_active_template, render

logger = logging.getLogger(__name__)


def _normalize_field_name(name: str, canonical_fields: list[str], cutoff: float = 0.8) -> str:
    """Return the closest canonical field name for `name` using fuzzy matching.

    Falls back to the original name if no close match is found (cutoff ≥ 0.8 by default).
    """
    if name in canonical_fields:
        return name
    matches = difflib.get_close_matches(name, canonical_fields, n=1, cutoff=cutoff)
    if matches:
        logger.debug("VVT fuzzy-match: '%s' → '%s'", name, matches[0])
        return matches[0]
    return name


def _coerce_canonical_value(v: str | list[str] | None) -> str | None:
    """Accept str or list[str] from LLM and normalize to str | None."""
    if v is None:
        return None
    if isinstance(v, list):
        return ", ".join(str(x).strip() for x in v if x) if v else None
    return v if isinstance(v, str) else str(v)

# Backwards-compatible alias — use get_vvt_field_names(settings) for configurable access
CANONICAL_VVT_FIELD_NAMES = DEFAULT_VVT_FIELD_NAMES


_CanonicalValue = Annotated[str | None, BeforeValidator(_coerce_canonical_value)]


class _VVTExtractionField(BaseModel):
    """Single field as extracted by LLM (internal)."""
    field_name: str = Field(description="Exact name of the VVT field from the canonical list.")
    status: Literal["filled", "missing", "inconsistent"] = Field(
        description="One of: filled, missing, inconsistent"
    )
    canonical_value: _CanonicalValue = Field(default=None, description="Extracted or normalized value if present.")
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


def _vvt_language_hint(language: str | None) -> str:
    """Return instruction for VVT extraction language (DE/EN)."""
    if not language or language == "de":
        return "The document and field values are in German. Use German for canonical_value, evidence, and finding."
    if language == "en":
        return "The document and field values are in English. Use English for canonical_value, evidence, and finding."
    return "The document may be in German or English. Use the same language as the document for canonical_value, evidence, and finding."


DEFAULT_VVT_SYSTEM = (
    "You are a data protection expert. Your task is to analyze a VVT/ROPA (Verzeichnis der "
    "Verarbeitungstätigkeiten / Record of Processing Activities) document text and extract structured "
    "information into the canonical VVT fields. For each of the required fields, set status to "
    "'filled' if the document contains a clear value, 'missing' if absent or empty, and 'inconsistent' "
    "if the value contradicts other documents or is legally problematic. Provide evidence (e.g. sheet name, "
    "row/column) and finding (e.g. short issue description) when relevant. Also detect the template "
    "variant if recognizable (e.g. Variante A, Variante B Psychologie, standard ROPA). {language_hint}"
)
DEFAULT_VVT_USER = """Analyze the following VVT/ROPA document text and extract all canonical fields.

Required fields (use these exact names): {field_list}

Document text:
---
{document_text}
---

For each required field, provide: field_name (exactly as in the list), status (filled|missing|inconsistent), 
canonical_value (normalized text or null if missing), evidence (where found, e.g. 'Sheet X, Zeile 12, Spalte C'), 
and finding (only if status is inconsistent or there is a problem).
Also set source_template to the detected template variant or 'Unbekannt'.
"""


async def normalize_vvt(
    raw_text: str,
    language: str | None = None,
    field_names: list[str] | None = None,
) -> _VVTExtractionResult:
    """
    Map raw VVT document text to the canonical VVT model using the LLM.
    Returns structured fields (filled/missing/inconsistent) and optional template detection.

    Args:
        raw_text: Raw extracted text of the VVT/ROPA document.
        language: Optional case language (de, en, de_en) for LLM output language hint.
        field_names: Optional custom list of canonical VVT field names.
                     Falls back to DEFAULT_VVT_FIELD_NAMES when None.
    """
    canonical_fields = field_names if field_names else list(DEFAULT_VVT_FIELD_NAMES)
    language_hint = _vvt_language_hint(language) if language else ""
    system_tpl = await get_active_template("vvt_system")
    system = render(system_tpl or DEFAULT_VVT_SYSTEM, {"language_hint": language_hint})
    agent = create_agent(system_prompt=system)
    vvt_limit = getattr(settings, "max_context_chars_vvt", 25000)
    raw = raw_text or ""
    if len(raw) > vvt_limit:
        logger.info("VVT text truncated: %d → %d chars", len(raw), vvt_limit)
        truncated = raw[:vvt_limit] + f"\n\n[... truncated, {len(raw)} chars total ...]"
    else:
        truncated = raw
    field_list = ", ".join(f'"{n}"' for n in canonical_fields)
    user_tpl = await get_active_template("vvt_user")
    user_content = render(
        user_tpl or DEFAULT_VVT_USER,
        {"field_list": field_list, "document_text": truncated},
    )
    result = await llm_retry_call(agent, user_content, output_type=_VVTExtractionResult)
    data = result.output

    # Normalize LLM-returned field names to canonical names via fuzzy matching
    for f in data.fields:
        f.field_name = _normalize_field_name(f.field_name, canonical_fields)

    # Ensure we have one entry per canonical field; fill missing with "missing"
    seen = {f.field_name for f in data.fields}
    for name in canonical_fields:
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
    name_to_idx = {n: i for i, n in enumerate(canonical_fields)}
    data.fields.sort(key=lambda f: name_to_idx.get(f.field_name, 999))
    return data
