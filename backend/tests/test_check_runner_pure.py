"""Unit tests for pure helper functions in check_runner.py.

Tests _language_hint() and _legal_bases_section() — no LLM, Weaviate, or DB needed.
"""
from uuid import uuid4

from app.services.check_runner import (
    CONTEXT_CHARS_PER_DOC,
    _cache_key,
    _language_hint,
    _legal_bases_section,
)


# ---------------------------------------------------------------------------
# _language_hint
# ---------------------------------------------------------------------------


def test_language_hint_none_returns_german():
    result = _language_hint(None)
    assert "DE" in result
    assert "German" in result


def test_language_hint_de_returns_german():
    result = _language_hint("de")
    assert "DE" in result
    assert "German" in result


def test_language_hint_en_returns_english():
    result = _language_hint("en")
    assert "EN" in result
    assert "English" in result


def test_language_hint_de_en_returns_mixed():
    result = _language_hint("de_en")
    assert "DE/EN" in result or "mixed" in result.lower()


def test_language_hint_empty_string_returns_german():
    result = _language_hint("")
    assert "German" in result


def test_language_hint_unknown_returns_mixed_hint():
    result = _language_hint("fr")
    assert result  # Non-empty
    assert "DE" in result or "language" in result.lower()


def test_language_hint_returns_nonempty_string_for_all_known():
    for lang in ("de", "en", "de_en"):
        assert _language_hint(lang)


# ---------------------------------------------------------------------------
# _legal_bases_section
# ---------------------------------------------------------------------------


def test_legal_bases_section_none_returns_empty():
    assert _legal_bases_section(None) == ""


def test_legal_bases_section_empty_string_returns_empty():
    assert _legal_bases_section("") == ""


def test_legal_bases_section_whitespace_only_returns_empty():
    assert _legal_bases_section("   \n\t  ") == ""


def test_legal_bases_section_with_content_returns_formatted_block():
    result = _legal_bases_section("§ 4 DSGVO – Definitionen")
    assert "§ 4 DSGVO" in result
    assert "---" in result
    assert "legal requirements" in result.lower() or "Relevant" in result


def test_legal_bases_section_strips_surrounding_whitespace():
    content = "  some legal text  "
    result = _legal_bases_section(content)
    assert "some legal text" in result
    # Leading/trailing whitespace is stripped
    assert result.count("  some legal text  ") == 0


def test_legal_bases_section_ends_with_double_newline():
    result = _legal_bases_section("content")
    assert result.endswith("\n\n")


# ---------------------------------------------------------------------------
# CONTEXT_CHARS_PER_DOC constant
# ---------------------------------------------------------------------------


def test_context_chars_per_doc_is_positive():
    assert CONTEXT_CHARS_PER_DOC > 0


def test_context_chars_per_doc_reasonable_size():
    # Should be large enough for meaningful documents but bounded for context limits
    assert 1000 < CONTEXT_CHARS_PER_DOC <= 100_000


# ---------------------------------------------------------------------------
# _cache_key — scoped by case_id + org_profile
# ---------------------------------------------------------------------------


def test_cache_key_is_deterministic_for_same_inputs():
    case = uuid4()
    assert _cache_key("sys", "user", case) == _cache_key("sys", "user", case)


def test_cache_key_differs_between_cases():
    case_a, case_b = uuid4(), uuid4()
    assert _cache_key("sys", "user", case_a) != _cache_key("sys", "user", case_b)


def test_cache_key_differs_for_different_prompts():
    case = uuid4()
    assert _cache_key("sys-a", "user", case) != _cache_key("sys-b", "user", case)
    assert _cache_key("sys", "user-a", case) != _cache_key("sys", "user-b", case)


def test_cache_key_accepts_none_case():
    # Some callers (legacy paths) may not have a case; scoping still yields a stable key.
    k1 = _cache_key("sys", "user", None)
    k2 = _cache_key("sys", "user", None)
    assert k1 == k2
    assert k1.startswith("llm_cache:")


def test_cache_key_includes_org_profile_scope():
    """Changing org_profile must invalidate the cache (multi-tenant isolation)."""
    from app.services import check_runner
    case = uuid4()
    check_runner._org_profile_hash_cached = None
    from app.config import settings
    original = settings.org_profile
    try:
        settings.org_profile = "tenant-a"
        check_runner._org_profile_hash_cached = None
        key_a = _cache_key("sys", "user", case)
        settings.org_profile = "tenant-b"
        check_runner._org_profile_hash_cached = None
        key_b = _cache_key("sys", "user", case)
        assert key_a != key_b
    finally:
        settings.org_profile = original
        check_runner._org_profile_hash_cached = None
