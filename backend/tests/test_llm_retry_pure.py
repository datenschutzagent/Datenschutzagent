"""Retry classification, circuit-breaker accounting and the per-job call budget
(Phase 2 R4). No provider is contacted: the agent is a mock."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from pydantic_ai.exceptions import ModelHTTPError, UsageLimitExceeded

from app.core import llm
from app.core.exceptions import (
    LLMBudgetExceededError,
    LLMProviderError,
    LLMRetryExhaustedError,
)


@pytest.fixture(autouse=True)
def _fast_and_isolated(monkeypatch):
    monkeypatch.setattr(llm, "LLM_RETRY_DELAYS", [0, 0, 0])
    monkeypatch.setattr(llm, "_circuit_breaker", None)  # fresh breaker per test
    monkeypatch.setattr(llm.settings, "llm_circuit_breaker_threshold", 5, raising=False)
    monkeypatch.setattr(llm.settings, "max_concurrent_llm_calls", 0, raising=False)
    monkeypatch.setattr(
        llm.settings, "llm_structured_output_mode", "tool", raising=False
    )


def _agent(*outcomes):
    agent = MagicMock()
    agent.run = AsyncMock(side_effect=list(outcomes))
    return agent


def _ok():
    r = MagicMock()
    r.output = "fine"
    r.usage.return_value = None
    return r


# --- classification ---------------------------------------------------------


@pytest.mark.parametrize(
    "exc, expected",
    [
        (ModelHTTPError(status_code=429, model_name="m"), True),
        (ModelHTTPError(status_code=503, model_name="m"), True),
        (ModelHTTPError(status_code=401, model_name="m"), False),
        (ModelHTTPError(status_code=400, model_name="m"), False),
        (httpx.ConnectTimeout("t"), True),
        (TimeoutError(), True),
        (UsageLimitExceeded("limit"), False),
        (TypeError("bug"), False),
        (ValueError("bad json"), False),
        (LLMProviderError("provider down"), True),
        (RuntimeError("unknown"), True),
    ],
)
def test_is_retryable_llm_error(exc, expected):
    assert llm.is_retryable_llm_error(exc) is expected


# --- retry loop --------------------------------------------------------------


@pytest.mark.asyncio
async def test_transient_error_is_retried_then_succeeds():
    agent = _agent(ModelHTTPError(status_code=503, model_name="m"), _ok())
    result = await llm.llm_retry_call(agent, "hi", output_type=str)
    assert result.output == "fine"
    assert agent.run.await_count == 2


@pytest.mark.asyncio
async def test_non_retryable_error_fails_fast_without_backoff():
    agent = _agent(ModelHTTPError(status_code=401, model_name="m"))
    with pytest.raises(LLMProviderError, match="non-retryable"):
        await llm.llm_retry_call(agent, "hi", output_type=str)
    assert agent.run.await_count == 1


@pytest.mark.asyncio
async def test_exhausted_retries_raise_retry_exhausted():
    agent = _agent(*[httpx.ConnectError("down")] * 3)
    with pytest.raises(LLMRetryExhaustedError):
        await llm.llm_retry_call(agent, "hi", output_type=str)
    assert agent.run.await_count == 3


@pytest.mark.asyncio
async def test_breaker_counts_every_failed_attempt(monkeypatch):
    monkeypatch.setattr(llm.settings, "llm_circuit_breaker_threshold", 3, raising=False)
    agent = _agent(*[httpx.ConnectError("down")] * 3)
    with pytest.raises(LLMRetryExhaustedError):
        await llm.llm_retry_call(agent, "hi", output_type=str)
    # Three failed attempts → breaker open; the next call is refused immediately.
    assert llm.get_circuit_breaker().is_open()
    fresh = _agent(_ok())
    with pytest.raises(LLMProviderError, match="circuit breaker"):
        await llm.llm_retry_call(fresh, "hi", output_type=str)
    fresh.run.assert_not_awaited()


# --- budget ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_budget_caps_attempts_including_retries():
    budget = llm.LLMCallBudget(2, label="test")
    token = llm.set_llm_budget(budget)
    try:
        agent = _agent(*[httpx.ConnectError("down")] * 5)
        with pytest.raises(LLMBudgetExceededError):
            await llm.llm_retry_call(agent, "hi", output_type=str)
    finally:
        llm.reset_llm_budget(token)
    assert agent.run.await_count == 2
    assert budget.exhausted


@pytest.mark.asyncio
async def test_budget_is_scoped_to_context():
    token = llm.set_llm_budget(llm.LLMCallBudget(1))
    llm.reset_llm_budget(token)
    assert llm.current_llm_budget() is None
    agent = _agent(_ok(), _ok())
    await llm.llm_retry_call(agent, "a", output_type=str)
    await llm.llm_retry_call(agent, "b", output_type=str)  # unlimited without budget


def test_unlimited_budget():
    b = llm.LLMCallBudget(0)
    for _ in range(50):
        b.consume()
    assert not b.exhausted


def test_active_model_name_is_str(monkeypatch):
    monkeypatch.setattr(llm.settings, "llm_provider", "ollama", raising=False)
    monkeypatch.setattr(llm.settings, "ollama_model", "llama3", raising=False)
    monkeypatch.setattr(llm.settings, "llm_analysis_model", "", raising=False)
    assert llm.get_active_model_name(analysis=True) == "llama3"
