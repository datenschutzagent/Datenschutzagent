"""Pure unit tests for the heuristic token budget (app.core.tokens — no LLM, no DB)."""
from app.config import settings
from app.core.tokens import effective_context_chars, estimate_tokens, token_budget_to_chars


def test_estimate_tokens_ceils(monkeypatch):
    monkeypatch.setattr(settings, "llm_chars_per_token", 3.5, raising=False)
    assert estimate_tokens("") == 0
    assert estimate_tokens(None) == 0
    assert estimate_tokens("abc") == 1       # 3 / 3.5 → ceil = 1
    assert estimate_tokens("a" * 35) == 10   # exactly 10 tokens
    assert estimate_tokens("a" * 36) == 11   # one char over → next token


def test_token_budget_to_chars_uses_ratio(monkeypatch):
    monkeypatch.setattr(settings, "llm_chars_per_token", 4.0, raising=False)
    assert token_budget_to_chars(1000) == 4000


def test_effective_context_chars_legacy_defaults_when_budget_disabled(monkeypatch):
    monkeypatch.setattr(settings, "llm_context_token_budget", 0, raising=False)
    monkeypatch.setattr(settings, "max_context_chars_per_doc", 15000, raising=False)
    monkeypatch.setattr(settings, "max_context_chars_rag", 20000, raising=False)
    monkeypatch.setattr(settings, "max_context_chars_vvt", 25000, raising=False)
    assert effective_context_chars("per_doc") == 15000
    assert effective_context_chars("rag") == 20000
    assert effective_context_chars("vvt") == 25000


def test_effective_context_chars_budget_overrides_all_kinds(monkeypatch):
    monkeypatch.setattr(settings, "llm_context_token_budget", 6000, raising=False)
    monkeypatch.setattr(settings, "llm_chars_per_token", 3.5, raising=False)
    expected = int(6000 * 3.5)
    assert effective_context_chars("per_doc") == expected
    assert effective_context_chars("rag") == expected
    assert effective_context_chars("vvt") == expected


def test_invalid_ratio_falls_back_safely(monkeypatch):
    # Defensive: a zero/negative ratio at runtime must not divide by zero.
    monkeypatch.setattr(settings, "llm_chars_per_token", 0, raising=False)
    assert estimate_tokens("abcdefg") > 0


def test_check_runner_helpers_honor_budget(monkeypatch):
    from app.services.check_runner import _context_chars_per_doc, _rag_context_chars

    monkeypatch.setattr(settings, "llm_context_token_budget", 2000, raising=False)
    monkeypatch.setattr(settings, "llm_chars_per_token", 3.5, raising=False)
    assert _context_chars_per_doc() == 7000
    assert _rag_context_chars() == 7000
