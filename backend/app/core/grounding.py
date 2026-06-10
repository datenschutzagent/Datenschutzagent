"""Evidence grounding: verify that LLM-quoted evidence actually appears in the source.

The compliance checks ask the model to return ``evidence`` quotes from the document.
A strict auditor must not act on fabricated quotes, so this module checks whether each
quote is present in the source text — exactly after whitespace/case normalization, or
approximately via the longest common substring ratio (tolerates minor OCR/formatting
differences). Used both as a Pydantic AI ``@output_validator`` (self-correction loop) and
as a post-processing step that drops ungrounded quotes and lowers the result confidence.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

# Quotes shorter than this are treated as grounded without checking: they are too
# generic (e.g. "Ja", "Art. 6") to verify meaningfully and would cause false alarms.
_MIN_QUOTE_LEN = 12

_WS_RE = re.compile(r"\s+")


def _normalize(text: str) -> str:
    """Lowercase and collapse all whitespace runs to single spaces."""
    return _WS_RE.sub(" ", (text or "")).strip().lower()


def is_grounded(quote: str, source_norm: str, threshold: float = 0.85) -> bool:
    """Return True if ``quote`` appears (exactly or approximately) in normalized source.

    ``source_norm`` must already be normalized via :func:`_normalize` (the caller
    normalizes once and reuses it across all quotes for efficiency).
    """
    q = _normalize(quote)
    if not q:
        return True  # nothing to verify
    if len(q) < _MIN_QUOTE_LEN:
        return True  # too short to verify reliably
    if not source_norm:
        return True  # no source to check against → do not penalize
    if q in source_norm:
        return True
    # Approximate match: longest common contiguous block relative to the quote length.
    match = SequenceMatcher(None, q, source_norm, autojunk=False).find_longest_match(
        0, len(q), 0, len(source_norm)
    )
    return (match.size / len(q)) >= threshold


def partition_grounded(
    quotes: list[str], source_text: str, threshold: float = 0.85
) -> tuple[list[str], list[str]]:
    """Split quotes into (grounded, ungrounded) lists, preserving order.

    Empty/whitespace-only quotes are dropped entirely (neither grounded nor ungrounded).
    """
    source_norm = _normalize(source_text)
    grounded: list[str] = []
    ungrounded: list[str] = []
    for q in quotes or []:
        if not q or not q.strip():
            continue
        if is_grounded(q, source_norm, threshold):
            grounded.append(q)
        else:
            ungrounded.append(q)
    return grounded, ungrounded


def grounding_ratio(
    quotes: list[str], source_text: str, threshold: float = 0.85
) -> float:
    """Fraction of non-empty quotes that are grounded (1.0 if there are no quotes)."""
    grounded, ungrounded = partition_grounded(quotes, source_text, threshold)
    total = len(grounded) + len(ungrounded)
    if total == 0:
        return 1.0
    return len(grounded) / total
