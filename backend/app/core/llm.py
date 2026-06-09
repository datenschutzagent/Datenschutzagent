"""LLM-Provider-Abstraktion: Ollama, OpenAI und Anthropic.

Der aktive Provider wird über die Einstellung LLM_PROVIDER gesteuert:
  - "ollama"    → lokales Ollama (Standard, kein API-Key erforderlich)
  - "openai"    → OpenAI API (OPENAI_API_KEY erforderlich)
  - "anthropic" → Anthropic API (ANTHROPIC_API_KEY erforderlich, 'anthropic'-Package nötig)
"""
import asyncio
import logging
import threading
import time

import httpx
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from app.config import settings
from app.core.exceptions import LLMProviderError, LLMRetryExhaustedError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LLM-Retry-Konfiguration
# ---------------------------------------------------------------------------

LLM_RETRY_ATTEMPTS = 3
LLM_RETRY_DELAYS = [2, 4, 8]  # seconds between attempts


# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------

class _CircuitState:
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Minimal per-process circuit breaker for LLM provider calls.

    States:
    - CLOSED: normal operation; failures are counted.
    - OPEN: provider is assumed down; calls fail immediately without retry.
    - HALF_OPEN: one probe is allowed through after the cooldown period.

    Thread-safe via threading.Lock (works for both sync Celery workers and
    async FastAPI because the lock is only held for microseconds).
    """

    def __init__(self, threshold: int, cooldown: float):
        self._threshold = threshold
        self._cooldown = cooldown
        self._state = _CircuitState.CLOSED
        self._failure_count = 0
        self._opened_at: float | None = None
        self._lock = threading.Lock()

    @property
    def state(self) -> str:
        with self._lock:
            if self._state == _CircuitState.OPEN:
                if self._opened_at and (time.monotonic() - self._opened_at) >= self._cooldown:
                    self._state = _CircuitState.HALF_OPEN
            return self._state

    def record_success(self) -> None:
        with self._lock:
            self._failure_count = 0
            self._opened_at = None
            self._state = _CircuitState.CLOSED

    def record_failure(self) -> None:
        with self._lock:
            self._failure_count += 1
            if self._failure_count >= self._threshold:
                self._state = _CircuitState.OPEN
                self._opened_at = time.monotonic()
                logger.error(
                    "LLM circuit breaker OPENED after %d consecutive failures",
                    self._failure_count,
                )

    def is_open(self) -> bool:
        return self.state == _CircuitState.OPEN


# Module-level circuit breaker instance (one per worker process).
_circuit_breaker: CircuitBreaker | None = None


def get_circuit_breaker() -> CircuitBreaker:
    global _circuit_breaker
    if _circuit_breaker is None:
        threshold = getattr(settings, "llm_circuit_breaker_threshold", 5)
        cooldown = getattr(settings, "llm_circuit_breaker_cooldown_seconds", 60.0)
        _circuit_breaker = CircuitBreaker(threshold=threshold, cooldown=cooldown)
    return _circuit_breaker


async def llm_retry_call(agent: Agent, user_content: str, output_type, *, request_id: str = ""):
    """Run an LLM agent call with exponential backoff retry on transient errors.

    Checks the circuit breaker before each attempt; if the breaker is OPEN,
    raises LLMProviderError immediately without spending retry delays. On
    success, records a success on the breaker; on exhaustion, records a
    failure and raises LLMRetryExhaustedError.
    """
    from app.core.metrics import llm_call_duration_seconds
    provider = settings.llm_provider.lower()

    cb = get_circuit_breaker()
    last_exc: Exception | None = None
    t0 = time.monotonic()
    for attempt, delay in enumerate(
        [0] + LLM_RETRY_DELAYS[: LLM_RETRY_ATTEMPTS - 1], start=1
    ):
        if cb.is_open():
            logger.warning(
                "LLM circuit breaker is OPEN — skipping call  [request_id=%s]", request_id
            )
            llm_call_duration_seconds.labels(provider=provider, status="circuit_open").observe(0)
            raise LLMProviderError("LLM provider circuit breaker is open; provider assumed unavailable")
        if delay:
            await asyncio.sleep(delay)
        try:
            result = await agent.run(user_content, output_type=output_type)
            elapsed = round(time.monotonic() - t0, 2)
            logger.info(
                "LLM call succeeded (attempt %d/%d) elapsed=%.2fs prompt_chars=%d  [request_id=%s]",
                attempt, LLM_RETRY_ATTEMPTS, elapsed, len(user_content), request_id,
            )
            cb.record_success()
            llm_call_duration_seconds.labels(provider=provider, status="success").observe(elapsed)
            return result
        except Exception as exc:
            last_exc = exc
            logger.warning(
                "LLM call failed (attempt %d/%d): %s  [request_id=%s]",
                attempt, LLM_RETRY_ATTEMPTS, exc, request_id,
            )
    elapsed = round(time.monotonic() - t0, 2)
    logger.error(
        "LLM call exhausted all retries elapsed=%.2fs  [request_id=%s]",
        elapsed, request_id,
    )
    cb.record_failure()
    llm_call_duration_seconds.labels(provider=provider, status="error").observe(elapsed)
    raise LLMRetryExhaustedError(f"All {LLM_RETRY_ATTEMPTS} LLM retry attempts failed") from last_exc


def _ollama_base_url() -> str:
    """Ollama OpenAI-compatible API is at /v1."""
    base = settings.ollama_base_url.rstrip("/")
    return f"{base}/v1" if not base.endswith("/v1") else base


_ollama_http_client: httpx.AsyncClient | None = None


def _get_ollama_http_client() -> httpx.AsyncClient:
    """Return a process-wide shared httpx client for Ollama (lazy init, one per worker)."""
    global _ollama_http_client
    if _ollama_http_client is None or _ollama_http_client.is_closed:
        timeout = settings.ollama_timeout_seconds
        _ollama_http_client = httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=10.0))
    return _ollama_http_client


async def aclose_ollama_http_client() -> None:
    """Close the shared Ollama httpx client (app/test shutdown)."""
    global _ollama_http_client
    if _ollama_http_client is not None and not _ollama_http_client.is_closed:
        await _ollama_http_client.aclose()
    _ollama_http_client = None


def get_ollama_model() -> OpenAIChatModel:
    """Get configured Ollama model (OpenAI-compatible API) via Pydantic AI OpenAIChatModel."""
    provider = OpenAIProvider(base_url=_ollama_base_url(), http_client=_get_ollama_http_client())
    return OpenAIChatModel(settings.ollama_model, provider=provider)


def get_openai_model() -> OpenAIChatModel:
    """Get configured OpenAI model via Pydantic AI OpenAIChatModel."""
    api_key = settings.openai_api_key.get_secret_value()
    if not api_key:
        raise RuntimeError(
            "LLM_PROVIDER=openai erfordert OPENAI_API_KEY. "
            "Bitte in der .env-Datei setzen."
        )
    provider = OpenAIProvider(api_key=api_key)
    return OpenAIChatModel(settings.openai_model, provider=provider)


def get_anthropic_model():
    """Get configured Anthropic model via Pydantic AI AnthropicModel.

    Requires the 'anthropic' package: pip install anthropic
    """
    api_key = settings.anthropic_api_key.get_secret_value()
    if not api_key:
        raise RuntimeError(
            "LLM_PROVIDER=anthropic erfordert ANTHROPIC_API_KEY. "
            "Bitte in der .env-Datei setzen."
        )
    try:
        from pydantic_ai.models.anthropic import AnthropicModel
        from pydantic_ai.providers.anthropic import AnthropicProvider
        provider = AnthropicProvider(api_key=api_key)
        return AnthropicModel(settings.anthropic_model, provider=provider)
    except ImportError as exc:
        raise RuntimeError(
            "LLM_PROVIDER=anthropic erfordert das 'anthropic'-Package: pip install anthropic"
        ) from exc


def get_active_model():
    """Return the currently configured LLM model based on LLM_PROVIDER setting."""
    provider = settings.llm_provider.lower()
    if provider == "openai":
        return get_openai_model()
    if provider == "anthropic":
        return get_anthropic_model()
    # Default: Ollama
    return get_ollama_model()


def create_agent(system_prompt: str) -> Agent:
    """Create a new PydanticAI agent with the given system prompt using the active provider."""
    return Agent(
        model=get_active_model(),
        system_prompt=system_prompt,
    )


def get_llm_provider_info() -> dict:
    """Return current LLM provider configuration (ohne Secrets) für Admin-Anzeige."""
    provider = settings.llm_provider.lower()
    info: dict = {"provider": provider}
    if provider == "openai":
        info["model"] = settings.openai_model
        info["api_key_configured"] = bool(settings.openai_api_key.get_secret_value())
    elif provider == "anthropic":
        info["model"] = settings.anthropic_model
        info["api_key_configured"] = bool(settings.anthropic_api_key.get_secret_value())
    else:
        info["model"] = settings.ollama_model
        info["base_url"] = settings.ollama_base_url
        info["api_key_configured"] = True  # Ollama braucht keinen Key
    return info
