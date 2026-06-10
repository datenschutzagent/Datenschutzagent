"""VVT normalization: map raw document text to canonical VVT model using LLM.

Large ROPA documents no longer lose content to hard truncation: when the text exceeds
``max_context_chars_vvt`` the extraction runs over sentence-aware fragments (map-reduce)
and the per-fragment fields are merged (filled beats missing; conflicting values become
``inconsistent``). Extracted values are additionally grounded against the source text so
fabricated entries are either self-corrected (ModelRetry) or flagged for review.
"""
from __future__ import annotations

import difflib
import logging
import re
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, Field
from pydantic_ai import ModelRetry

from app.config import settings
from app.core.grounding import grounding_ratio, partition_grounded
from app.core.llm import create_agent, llm_retry_call
from app.core.prompt_security import sanitize_prompt_field
from app.services.document_processor import detect_language
from app.services.org_profile_loader import DEFAULT_VVT_FIELD_NAMES, get_vvt_field_names
from app.services.prompt_template_service import get_active_template, render
from app.services.weaviate_service import build_context_windows, truncate_sentence_aware

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
canonical_value (normalized text or null if missing), evidence (where found — use the row numbers from the
'Zeile' column and page anchors '[Seite N]' when present, e.g. 'Sheet X, Zeile 12, Spalte C' or 'Seite 3'),
and finding (only if status is inconsistent or there is a problem).
Also set source_template to the detected template variant or 'Unbekannt'.
"""

# Appended to the system prompt when extraction runs over a document fragment (map-reduce), so
# the model only reports what the fragment contains instead of guessing document-wide values.
_VVT_FRAGMENT_SUFFIX = (
    "\n\nNOTE: You are seeing ONE fragment of a larger document. Extract only what is present in "
    "this fragment and set status 'missing' for every field this fragment does not contain — the "
    "field may appear in another fragment and the results are merged afterwards. Never invent values."
)


# ---------------------------------------------------------------------------
# Evidence grounding for extracted values
# ---------------------------------------------------------------------------

# Reviewer-facing note appended to ``finding`` when a filled value cannot be located in the
# source text (possible hallucination that survived the self-correction retries).
UNVERIFIED_VALUE_NOTE = "Wert konnte nicht im Dokumenttext verifiziert werden (bitte prüfen)."

_VALUE_PART_SPLIT = re.compile(r"[;,]")


def _value_grounded(value: str | None, source_text: str, threshold: float) -> bool:
    """Best-effort check that an extracted value is supported by the source text.

    ``canonical_value`` is a *normalized* extraction — not a verbatim quote — so this is
    deliberately lenient: the whole value counts, or at least half of its comma/semicolon-
    separated parts must (fuzzily) appear in the source. Very short values/parts auto-pass
    (see the grounding module), so only wholesale fabrication is flagged.
    """
    if not value or not value.strip() or not source_text or not source_text.strip():
        return True
    if grounding_ratio([value], source_text, threshold) >= 1.0:
        return True
    parts = [p.strip() for p in _VALUE_PART_SPLIT.split(value) if p.strip()]
    if len(parts) <= 1:
        return False
    grounded, ungrounded = partition_grounded(parts, source_text, threshold)
    total = len(grounded) + len(ungrounded)
    return total == 0 or (len(grounded) / total) >= 0.5


def _make_vvt_grounding_validator(source_text: str):
    """Build a Pydantic AI output validator that requests self-correction on fabricated output.

    Only the egregious case triggers a ``ModelRetry``: at least two fields are 'filled' yet NONE
    of their values can be located in the source text — a clear hallucination signal. Individual
    ungrounded values are handled more gently in :func:`_apply_vvt_grounding` (reviewer note),
    because a normalized value may legitimately differ from the document wording.
    """
    def _validate(ctx, output: _VVTExtractionResult) -> _VVTExtractionResult:
        if not settings.evidence_grounding_enabled:
            return output
        if ctx.retry >= settings.llm_output_retries:
            return output  # never hard-fail on the final allowed attempt
        filled = [f for f in output.fields if f.status == "filled" and (f.canonical_value or "").strip()]
        if len(filled) < 2:
            return output
        threshold = settings.evidence_grounding_threshold
        if not any(_value_grounded(f.canonical_value, source_text, threshold) for f in filled):
            raise ModelRetry(
                "None of the extracted 'filled' values appear in the provided document text. "
                "Extract values from the document only — never invent content. Use status "
                "'missing' for every field the document does not contain."
            )
        return output

    return _validate


def _apply_vvt_grounding(result: _VVTExtractionResult, source_text: str) -> _VVTExtractionResult:
    """Annotate filled fields whose value cannot be located in the source (possible hallucination).

    The value is kept (it may be a legitimate normalization), but the reviewer-facing ``finding``
    gets a verification note so the field is not silently trusted.
    """
    if not settings.evidence_grounding_enabled or not source_text or not source_text.strip():
        return result
    threshold = settings.evidence_grounding_threshold
    for f in result.fields:
        if f.status != "filled" or not (f.canonical_value or "").strip():
            continue
        if _value_grounded(f.canonical_value, source_text, threshold):
            continue
        f.finding = f"{f.finding} | {UNVERIFIED_VALUE_NOTE}" if (f.finding or "").strip() else UNVERIFIED_VALUE_NOTE
        logger.warning(
            "VVT grounding: value for field '%s' not found in source text — flagged for review",
            f.field_name,
        )
    return result


# ---------------------------------------------------------------------------
# Map-reduce merge of per-fragment extractions
# ---------------------------------------------------------------------------


def _norm_value(value: str | None) -> str:
    return " ".join((value or "").lower().split())


def _values_equivalent(a: str | None, b: str | None) -> bool:
    """True when two extracted values describe the same content (normalized equal/containment)."""
    na, nb = _norm_value(a), _norm_value(b)
    if not na or not nb:
        return na == nb
    return na == nb or na in nb or nb in na


def _join_unique(*parts: str | None, sep: str = "; ") -> str | None:
    seen: list[str] = []
    for p in parts:
        p = (p or "").strip()
        if p and p not in seen:
            seen.append(p)
    return sep.join(seen) if seen else None


def _merge_two(a: _VVTExtractionField, b: _VVTExtractionField) -> _VVTExtractionField:
    """Merge two extractions of the same field from different fragments.

    Precedence: inconsistent > filled > missing. Two fragments filling the field with
    conflicting values become 'inconsistent' with a finding naming both values — a real
    signal on ROPA sheets (e.g. two processing activities with contradicting retention
    periods), not an extraction artifact to hide.
    """
    if a.status == "inconsistent" or b.status == "inconsistent":
        primary = a if a.status == "inconsistent" else b
        return _VVTExtractionField(
            field_name=a.field_name,
            status="inconsistent",
            canonical_value=primary.canonical_value or a.canonical_value or b.canonical_value,
            evidence=_join_unique(a.evidence, b.evidence),
            finding=_join_unique(a.finding, b.finding),
        )
    if a.status == "filled" and b.status == "filled":
        if _values_equivalent(a.canonical_value, b.canonical_value):
            richer = a if len(a.canonical_value or "") >= len(b.canonical_value or "") else b
            return _VVTExtractionField(
                field_name=a.field_name,
                status="filled",
                canonical_value=richer.canonical_value,
                evidence=_join_unique(a.evidence, b.evidence),
                finding=_join_unique(a.finding, b.finding),
            )
        conflict = (
            f"Widersprüchliche Werte in verschiedenen Dokumentteilen: "
            f"'{a.canonical_value}' vs. '{b.canonical_value}'"
        )
        return _VVTExtractionField(
            field_name=a.field_name,
            status="inconsistent",
            canonical_value=a.canonical_value,
            evidence=_join_unique(a.evidence, b.evidence),
            finding=_join_unique(a.finding, b.finding, conflict),
        )
    if a.status == "filled" or b.status == "filled":
        filled = a if a.status == "filled" else b
        other = b if a.status == "filled" else a
        return _VVTExtractionField(
            field_name=a.field_name,
            status="filled",
            canonical_value=filled.canonical_value,
            evidence=filled.evidence,
            finding=_join_unique(filled.finding, other.finding),
        )
    # Both missing.
    return _VVTExtractionField(
        field_name=a.field_name,
        status="missing",
        canonical_value=None,
        evidence=None,
        finding=_join_unique(a.finding, b.finding),
    )


def _merge_extractions(results: list[_VVTExtractionResult]) -> _VVTExtractionResult:
    """Reduce step of the VVT map-reduce: merge per-fragment results into one extraction.

    Field names must already be normalized to canonical names (the merge keys on them).
    The detected template is the first concrete (non-'Unbekannt') one across fragments.
    """
    by_name: dict[str, _VVTExtractionField] = {}
    for res in results:
        for f in res.fields:
            cur = by_name.get(f.field_name)
            by_name[f.field_name] = f if cur is None else _merge_two(cur, f)
    template = ""
    for res in results:
        t = (res.source_template or "").strip()
        if t and t.lower() != "unbekannt":
            template = t
            break
        if t and not template:
            template = t
    return _VVTExtractionResult(source_template=template, fields=list(by_name.values()))


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------


async def _extract_fragment(
    system: str,
    document_text: str,
    field_list: str,
    canonical_fields: list[str],
    user_tpl: str | None,
    vvt_limit: int,
) -> _VVTExtractionResult:
    """Run one extraction call over ``document_text`` with grounding (validator + annotation)."""
    agent = create_agent(
        system_prompt=system,
        analysis=True,  # VVT/ROPA normalization is a complex extraction → optional stronger model
        output_validator=_make_vvt_grounding_validator(document_text),
    )
    user_content = render(
        user_tpl or DEFAULT_VVT_USER,
        {
            # document_text is already limited by construction (window / sentence-aware
            # truncation); the small headroom keeps the appended truncation marker intact.
            "field_list": field_list,
            "document_text": sanitize_prompt_field(document_text, max_chars=vvt_limit + 200),
        },
    )
    result = await llm_retry_call(agent, user_content, output_type=_VVTExtractionResult)
    data = result.output
    # Normalize LLM-returned field names to canonical names via fuzzy matching (the
    # map-reduce merge keys on field_name, so this must happen before merging).
    for f in data.fields:
        f.field_name = _normalize_field_name(f.field_name, canonical_fields)
    return _apply_vvt_grounding(data, document_text)


async def normalize_vvt(
    raw_text: str,
    language: str | None = None,
    field_names: list[str] | None = None,
) -> _VVTExtractionResult:
    """
    Map raw VVT document text to the canonical VVT model using the LLM.
    Returns structured fields (filled/missing/inconsistent) and optional template detection.

    Documents longer than ``max_context_chars_vvt`` are processed in sentence-aware fragments
    (map-reduce) and merged, so processing activities beyond the context limit are no longer
    silently dropped. Disable via ``vvt_map_reduce_enabled=false`` for the legacy truncation.

    Args:
        raw_text: Raw extracted text of the VVT/ROPA document.
        language: Optional case language (de, en, de_en) for LLM output language hint.
        field_names: Optional custom list of canonical VVT field names.
                     Falls back to DEFAULT_VVT_FIELD_NAMES when None.
    """
    canonical_fields = field_names if field_names else list(DEFAULT_VVT_FIELD_NAMES)
    language = language or detect_language(raw_text)
    language_hint = _vvt_language_hint(language) if language else ""
    system_tpl = await get_active_template("vvt_system")
    system = render(system_tpl or DEFAULT_VVT_SYSTEM, {"language_hint": language_hint})
    user_tpl = await get_active_template("vvt_user")
    vvt_limit = getattr(settings, "max_context_chars_vvt", 25000)
    field_list = ", ".join(f'"{n}"' for n in canonical_fields)
    raw = raw_text or ""

    if len(raw) > vvt_limit and getattr(settings, "vvt_map_reduce_enabled", True):
        max_chunks = getattr(settings, "vvt_max_chunks", 8)
        windows = build_context_windows(raw, vvt_limit, max_chunks)
        logger.info(
            "VVT map-reduce: %d chars → %d fragment(s) (limit %d chars each)",
            len(raw), len(windows), vvt_limit,
        )
        frag_system = system + _VVT_FRAGMENT_SUFFIX
        results = [
            await _extract_fragment(frag_system, window, field_list, canonical_fields, user_tpl, vvt_limit)
            for window in windows
        ]
        data = _merge_extractions(results) if results else _VVTExtractionResult()
    else:
        truncated, was_truncated = truncate_sentence_aware(raw, vvt_limit)
        if was_truncated:
            logger.info("VVT text truncated (sentence-aware): %d → ~%d chars", len(raw), vvt_limit)
            truncated = truncated + f"\n\n[... truncated, {len(raw)} chars total ...]"
        data = await _extract_fragment(system, truncated, field_list, canonical_fields, user_tpl, vvt_limit)

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
