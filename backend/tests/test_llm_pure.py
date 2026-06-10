"""Unit tests for pure LLM-config helpers in app.core.llm (no network, no provider call).

Covers the model/cost levers added for Batch B: the optional analysis model, provider-aware
default model settings (incl. the Anthropic prompt-cache breakpoint) and the temperature override.
"""
import pytest
from pydantic import BaseModel

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


# ---------------------------------------------------------------------------
# openai_compatible provider (llama.cpp / vLLM / LiteLLM …)
# ---------------------------------------------------------------------------


def test_ensure_v1_base_url_appends_missing_suffix():
    assert llm.ensure_v1_base_url("http://localhost:8080") == "http://localhost:8080/v1"
    assert llm.ensure_v1_base_url("http://localhost:8000/v1") == "http://localhost:8000/v1"
    assert llm.ensure_v1_base_url("http://localhost:8000/v1/") == "http://localhost:8000/v1"


def test_active_model_name_openai_compatible(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "openai_compatible", raising=False)
    monkeypatch.setattr(settings, "llm_model", "Qwen/Qwen2.5-14B-Instruct", raising=False)
    monkeypatch.setattr(settings, "llm_analysis_model", "", raising=False)
    assert llm.get_active_model_name() == "Qwen/Qwen2.5-14B-Instruct"


def test_openai_compatible_model_requires_base_url(monkeypatch):
    import pytest

    monkeypatch.setattr(settings, "llm_base_url", "", raising=False)
    with pytest.raises(RuntimeError, match="LLM_BASE_URL"):
        llm.get_openai_compatible_model()


def test_provider_info_openai_compatible_without_secrets(monkeypatch):
    from pydantic import SecretStr

    monkeypatch.setattr(settings, "llm_provider", "openai_compatible", raising=False)
    monkeypatch.setattr(settings, "llm_model", "qwen2.5-14b", raising=False)
    monkeypatch.setattr(settings, "llm_base_url", "http://vllm:8000/v1", raising=False)
    monkeypatch.setattr(settings, "llm_api_key", SecretStr("secret"), raising=False)
    monkeypatch.setattr(settings, "llm_structured_output_mode", "native", raising=False)
    info = llm.get_llm_provider_info()
    assert info["provider"] == "openai_compatible"
    assert info["model"] == "qwen2.5-14b"
    assert info["base_url"] == "http://vllm:8000/v1"
    assert info["api_key_configured"] is True
    assert info["structured_output_mode"] == "native"
    assert "secret" not in str(info)


# ---------------------------------------------------------------------------
# wrap_output_type — configurable structured-output mode
# ---------------------------------------------------------------------------


class _DummyOutput(BaseModel):
    value: str = ""


def test_wrap_output_type_tool_mode_is_passthrough(monkeypatch):
    monkeypatch.setattr(settings, "llm_structured_output_mode", "tool", raising=False)
    assert llm.wrap_output_type(_DummyOutput) is _DummyOutput


def test_wrap_output_type_native_mode_wraps(monkeypatch):
    from pydantic_ai import NativeOutput

    monkeypatch.setattr(settings, "llm_provider", "openai_compatible", raising=False)
    monkeypatch.setattr(settings, "llm_structured_output_mode", "native", raising=False)
    wrapped = llm.wrap_output_type(_DummyOutput)
    assert isinstance(wrapped, NativeOutput)


def test_wrap_output_type_prompted_mode_wraps(monkeypatch):
    from pydantic_ai import PromptedOutput

    monkeypatch.setattr(settings, "llm_provider", "ollama", raising=False)
    monkeypatch.setattr(settings, "llm_structured_output_mode", "prompted", raising=False)
    wrapped = llm.wrap_output_type(_DummyOutput)
    assert isinstance(wrapped, PromptedOutput)


def test_wrap_output_type_native_ignored_for_anthropic(monkeypatch):
    # Anthropic has no JSON-schema response_format; tool calling is its native mechanism.
    monkeypatch.setattr(settings, "llm_provider", "anthropic", raising=False)
    monkeypatch.setattr(settings, "llm_structured_output_mode", "native", raising=False)
    assert llm.wrap_output_type(_DummyOutput) is _DummyOutput


def test_wrap_output_type_str_and_wrapped_passthrough(monkeypatch):
    from pydantic_ai import NativeOutput

    monkeypatch.setattr(settings, "llm_provider", "ollama", raising=False)
    monkeypatch.setattr(settings, "llm_structured_output_mode", "native", raising=False)
    # Plain-text output stays plain text (e.g. finding chat).
    assert llm.wrap_output_type(str) is str
    # Already-wrapped marker objects are not double-wrapped.
    already = NativeOutput(_DummyOutput)
    assert llm.wrap_output_type(already) is already


# ---------------------------------------------------------------------------
# _get_llm_semaphore / gather_all — parallel LLM fan-out plumbing
# ---------------------------------------------------------------------------


def test_semaphore_none_when_unlimited(monkeypatch):
    monkeypatch.setattr(settings, "max_concurrent_llm_calls", 0, raising=False)
    # limit <= 0 short-circuits before touching the running loop.
    assert llm._get_llm_semaphore() is None


def test_semaphore_is_singleton_per_loop(monkeypatch):
    import asyncio

    monkeypatch.setattr(settings, "max_concurrent_llm_calls", 3, raising=False)

    async def main():
        a = llm._get_llm_semaphore()
        b = llm._get_llm_semaphore()
        return a, b

    a, b = asyncio.run(main())
    assert a is b
    assert a._value == 3  # initialized from the setting


def test_gather_all_preserves_order_and_runs_all_on_failure():
    import asyncio

    completed: list[int] = []

    async def ok(i):
        await asyncio.sleep(0.01 * (3 - i))  # later coros finish first without order guarantee
        completed.append(i)
        return i

    async def boom():
        await asyncio.sleep(0.005)
        completed.append(-1)
        raise RuntimeError("fragment failed")

    # Order is preserved despite reversed completion times.
    assert asyncio.run(llm.gather_all([ok(0), ok(1), ok(2)])) == [0, 1, 2]

    # On failure: every sibling still completes (no detached tasks), then the error re-raises.
    completed.clear()

    async def failing():
        await llm.gather_all([ok(0), boom(), ok(2)])

    with pytest.raises(RuntimeError, match="fragment failed"):
        asyncio.run(failing())
    assert set(completed) == {0, -1, 2}
