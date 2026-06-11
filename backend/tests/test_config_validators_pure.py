"""Pure unit tests for Settings validators (no DB, no SMTP needed)."""

import pytest

from app.config import Settings

# The legacy "timeout misconfiguration" warning validator is gone by design:
# check_timeout_seconds and ollama_timeout_seconds are now *derived* from
# LLM_REQUEST_TIMEOUT_SECONDS, so a check timeout below the HTTP timeout
# cannot be configured anymore. These tests pin that invariant instead.


def test_check_timeout_is_derived_with_buffer():
    s = Settings(llm_request_timeout_seconds=120.0)
    assert s.ollama_timeout_seconds == 120.0
    assert s.check_timeout_seconds == 130.0  # always 10s above the HTTP timeout


def test_check_timeout_disabled_when_request_timeout_disabled():
    s = Settings(llm_request_timeout_seconds=0)
    assert s.check_timeout_seconds == 0.0


def test_timeout_kwargs_cannot_be_set_directly():
    # The derived properties are not settable fields — misconfiguration is rejected.
    with pytest.raises(ValueError):
        Settings(check_timeout_seconds=30.0)


def test_openai_compatible_requires_base_url():
    with pytest.raises(ValueError, match="LLM_BASE_URL"):
        Settings(llm_provider="openai_compatible", llm_model="qwen2.5-14b")


def test_openai_compatible_requires_model():
    with pytest.raises(ValueError, match="LLM_MODEL"):
        Settings(
            llm_provider="openai_compatible", llm_base_url="http://localhost:8000/v1"
        )


def test_openai_compatible_accepts_base_url_and_model():
    s = Settings(
        llm_provider="openai_compatible",
        llm_base_url="http://localhost:8080",
        llm_model="Qwen/Qwen2.5-14B-Instruct",
    )
    assert s.llm_structured_output_mode == "tool"  # default keeps existing behaviour
