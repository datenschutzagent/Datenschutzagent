"""Unit tests for pure LLM-config helpers in app.core.llm (no network, no provider call).

Covers the model/cost levers added for Batch B: the optional analysis model, provider-aware
default model settings (incl. the Anthropic prompt-cache breakpoint) and the temperature override.
"""
from app.config import settings
from app.core import llm


def test_analysis_model_name_empty_is_none(monkeypatch):
    monkeypatch.setattr(settings, "llm_analysis_model", "", raising=False)
    assert llm._analysis_model_name() is None


def test_analysis_model_name_returns_configured(monkeypatch):
    monkeypatch.setattr(settings, "llm_analysis_model", "qwen2.5:14b", raising=False)
    assert llm._analysis_model_name() == "qwen2.5:14b"


def test_active_model_name_analysis_override(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "ollama", raising=False)
    monkeypatch.setattr(settings, "ollama_model", "llama3.2", raising=False)
    monkeypatch.setattr(settings, "llm_analysis_model", "qwen2.5:14b", raising=False)
    # Without analysis → provider default; with analysis → the override.
    assert llm.get_active_model_name() == "llama3.2"
    assert llm.get_active_model_name(analysis=True) == "qwen2.5:14b"


def test_active_model_name_analysis_falls_back_when_unset(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "ollama", raising=False)
    monkeypatch.setattr(settings, "ollama_model", "llama3.2", raising=False)
    monkeypatch.setattr(settings, "llm_analysis_model", "", raising=False)
    assert llm.get_active_model_name(analysis=True) == "llama3.2"


def test_default_model_settings_temperature(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "ollama", raising=False)
    monkeypatch.setattr(settings, "llm_temperature", 0.0, raising=False)
    monkeypatch.setattr(settings, "llm_max_tokens", None, raising=False)
    assert llm.default_model_settings()["temperature"] == 0.0
    # Explicit override (used by self-consistency sampling) takes precedence.
    assert llm.default_model_settings(temperature=0.5)["temperature"] == 0.5


def test_default_model_settings_anthropic_adds_cache_breakpoint(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "anthropic", raising=False)
    monkeypatch.setattr(settings, "anthropic_prompt_caching", True, raising=False)
    monkeypatch.setattr(settings, "llm_temperature", 0.0, raising=False)
    s = llm.default_model_settings()
    # pydantic-ai exposes the cache breakpoint as anthropic_cache_instructions on the settings dict.
    assert s.get("anthropic_cache_instructions") is True
    assert s["temperature"] == 0.0


def test_default_model_settings_anthropic_caching_disabled(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "anthropic", raising=False)
    monkeypatch.setattr(settings, "anthropic_prompt_caching", False, raising=False)
    s = llm.default_model_settings()
    assert "anthropic_cache_instructions" not in s
