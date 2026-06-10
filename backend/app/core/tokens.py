"""Heuristic token estimation and token-based context budgets.

All context limits in this codebase are character-based (``max_context_chars_*``). Local
OpenAI-compatible servers (vLLM, llama.cpp) however budget in tokens, and llama.cpp silently
truncates context on overflow. This module provides a lightweight, provider-independent
heuristic (no tokenizer dependency): a configurable characters-per-token ratio
(``llm_chars_per_token``, default 3.5 — typical for German prose; English is closer to 4).

When ``llm_context_token_budget`` > 0, :func:`effective_context_chars` derives ONE character
limit from the budget for all pipeline kinds — the budget expresses "max document-content
tokens per call" regardless of pipeline; keeping the legacy 15k/20k/25k ratios under a single
budget would invent per-kind weights with no principled values. Budget 0 (default) keeps the
legacy per-kind character limits unchanged.
"""
from __future__ import annotations

import math
from typing import Literal

from app.config import settings

ContextKind = Literal["per_doc", "rag", "vvt"]

_KIND_TO_SETTING: dict[str, tuple[str, int]] = {
    "per_doc": ("max_context_chars_per_doc", 15000),
    "rag": ("max_context_chars_rag", 20000),
    "vvt": ("max_context_chars_vvt", 25000),
}


def _chars_per_token() -> float:
    ratio = getattr(settings, "llm_chars_per_token", 3.5) or 3.5
    return ratio if ratio > 0 else 3.5


def estimate_tokens(text: str | None) -> int:
    """Heuristic token count for ``text`` (ceil of chars / chars-per-token)."""
    if not text:
        return 0
    return math.ceil(len(text) / _chars_per_token())


def token_budget_to_chars(tokens: int) -> int:
    """Convert a token budget into the equivalent character budget."""
    return int(tokens * _chars_per_token())


def effective_context_chars(kind: ContextKind) -> int:
    """Character limit for the given pipeline kind, honoring the optional token budget.

    ``llm_context_token_budget`` > 0 → uniform derived char limit for every kind (overrides
    the ``max_context_chars_*`` settings); otherwise the legacy per-kind setting.
    """
    budget = getattr(settings, "llm_context_token_budget", 0) or 0
    if budget > 0:
        return token_budget_to_chars(budget)
    setting_name, default = _KIND_TO_SETTING[kind]
    return getattr(settings, setting_name, default)
