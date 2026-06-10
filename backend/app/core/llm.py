"""LLM-Provider-Abstraktion: Ollama, OpenAI, Anthropic und OpenAI-kompatible Server.

Der aktive Provider wird über die Einstellung LLM_PROVIDER gesteuert:
  - "ollama"            → lokales Ollama (Standard, kein API-Key erforderlich)
  - "openai"            → OpenAI API (OPENAI_API_KEY erforderlich)
  - "anthropic"         → Anthropic API (ANTHROPIC_API_KEY erforderlich, 'anthropic'-Package nötig)
  - "openai_compatible" → beliebiger OpenAI-kompatibler Server (llama.cpp, vLLM, LiteLLM, TGI, …;
                          LLM_BASE_URL + LLM_MODEL erforderlich, LLM_API_KEY optional)
"""
import asyncio
import contextlib
import logging
import threading
import time
from collections.abc import Callable

import httpx
from pydantic_ai import Agent, NativeOutput, PromptedOutput
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings

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


def wrap_output_type(output_type):
    """Apply the configured structured-output mode (LLM_STRUCTURED_OUTPUT_MODE) to an output type.

    "tool" (default) returns the type unchanged — Pydantic AI then enforces the schema via
    tool/function calling. "native" wraps it in ``NativeOutput`` → ``response_format`` with a JSON
    schema, i.e. constrained decoding on vLLM (guided decoding), llama.cpp (json_schema/GBNF) and
    Ollama (structured outputs) — the model cannot emit schema-invalid JSON. "prompted" wraps in
    ``PromptedOutput`` (schema only described in the prompt) for servers without either mechanism.

    Plain-text outputs (``str``) and already-wrapped marker objects pass through unchanged.
    Anthropic ignores "native" (no JSON-schema response_format; tool calling is its native path).
    """
    mode = (getattr(settings, "llm_structured_output_mode", "tool") or "tool").lower()
    if mode == "tool" or output_type is str:
        return output_type
    if not isinstance(output_type, type):
        return output_type  # already a NativeOutput/PromptedOutput/ToolOutput wrapper
    if mode == "native":
        if settings.llm_provider.lower() == "anthropic":
            return output_type
        return NativeOutput(output_type)
    if mode == "prompted":
        return PromptedOutput(output_type)
    return output_type


async def llm_retry_call(agent: Agent, user_content: str, output_type, *, request_id: str = ""):
    """Run an LLM agent call with exponential backoff retry on transient errors.

    Checks the circuit breaker before each attempt; if the breaker is OPEN,
    raises LLMProviderError immediately without spending retry delays. On
    success, records a success on the breaker; on exhaustion, records a
    failure and raises LLMRetryExhaustedError.

    The output type is passed through :func:`wrap_output_type`, so the configured
    structured-output mode applies to every call going through this helper.
    """
    from app.core.metrics import llm_call_duration_seconds, record_llm_usage
    provider = settings.llm_provider.lower()
    output_type = wrap_output_type(output_type)

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
            # Token/cost accounting (best-effort; never breaks the request path).
            with contextlib.suppress(Exception):
                record_llm_usage(provider, get_active_model_name(), result.usage())
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


def ensure_v1_base_url(base_url: str) -> str:
    """Normalize an OpenAI-compatible base URL: strip trailing slash, append /v1 if missing."""
    base = (base_url or "").rstrip("/")
    return f"{base}/v1" if not base.endswith("/v1") else base


def _ollama_base_url() -> str:
    """Ollama OpenAI-compatible API is at /v1."""
    return ensure_v1_base_url(settings.ollama_base_url)


_local_http_client: httpx.AsyncClient | None = None


def _get_local_http_client() -> httpx.AsyncClient:
    """Return a process-wide shared httpx client for local providers (lazy init, one per worker)."""
    global _local_http_client
    if _local_http_client is None or _local_http_client.is_closed:
        timeout = settings.ollama_timeout_seconds
        _local_http_client = httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=10.0))
    return _local_http_client


async def aclose_ollama_http_client() -> None:
    """Close the shared local-provider httpx client (app/test shutdown)."""
    global _local_http_client
    if _local_http_client is not None and not _local_http_client.is_closed:
        await _local_http_client.aclose()
    _local_http_client = None


def get_ollama_model(model_name: str | None = None) -> OpenAIChatModel:
    """Get configured Ollama model (OpenAI-compatible API) via Pydantic AI OpenAIChatModel."""
    provider = OpenAIProvider(base_url=_ollama_base_url(), http_client=_get_local_http_client())
    return OpenAIChatModel(model_name or settings.ollama_model, provider=provider)


def get_openai_compatible_model(model_name: str | None = None) -> OpenAIChatModel:
    """Get a model served by a custom OpenAI-compatible server (llama.cpp, vLLM, LiteLLM, …).

    Uses LLM_BASE_URL (with /v1 appended when missing) and the optional LLM_API_KEY — vLLM is
    frequently run with ``--api-key``; without one a placeholder key is sent, which local servers
    ignore.
    """
    base_url = (settings.llm_base_url or "").strip()
    if not base_url:
        raise RuntimeError(
            "LLM_PROVIDER=openai_compatible erfordert LLM_BASE_URL. Bitte in der .env-Datei setzen."
        )
    api_key = settings.llm_api_key.get_secret_value() or "api-key-not-set"
    provider = OpenAIProvider(
        base_url=ensure_v1_base_url(base_url),
        api_key=api_key,
        http_client=_get_local_http_client(),
    )
    return OpenAIChatModel(model_name or settings.llm_model, provider=provider)


def get_openai_model(model_name: str | None = None) -> OpenAIChatModel:
    """Get configured OpenAI model via Pydantic AI OpenAIChatModel."""
    api_key = settings.openai_api_key.get_secret_value()
    if not api_key:
        raise RuntimeError(
            "LLM_PROVIDER=openai erfordert OPENAI_API_KEY. "
            "Bitte in der .env-Datei setzen."
        )
    provider = OpenAIProvider(api_key=api_key)
    return OpenAIChatModel(model_name or settings.openai_model, provider=provider)


def get_anthropic_model(model_name: str | None = None):
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
        return AnthropicModel(model_name or settings.anthropic_model, provider=provider)
    except ImportError as exc:
        raise RuntimeError(
            "LLM_PROVIDER=anthropic erfordert das 'anthropic'-Package: pip install anthropic"
        ) from exc


def _analysis_model_name() -> str | None:
    """Override model id for complex analyses, or None to use the provider default."""
    name = (getattr(settings, "llm_analysis_model", "") or "").strip()
    return name or None


def get_active_model(model_name: str | None = None):
    """Return the configured LLM model based on LLM_PROVIDER, optionally overriding the model id."""
    provider = settings.llm_provider.lower()
    if provider == "openai":
        return get_openai_model(model_name)
    if provider == "anthropic":
        return get_anthropic_model(model_name)
    if provider == "openai_compatible":
        return get_openai_compatible_model(model_name)
    # Default: Ollama
    return get_ollama_model(model_name)


def get_active_model_name(*, analysis: bool = False) -> str:
    """Return the configured model identifier for the active provider (for logging/metrics)."""
    if analysis and _analysis_model_name():
        return _analysis_model_name()
    provider = settings.llm_provider.lower()
    if provider == "openai":
        return settings.openai_model
    if provider == "anthropic":
        return settings.anthropic_model
    if provider == "openai_compatible":
        return settings.llm_model
    return settings.ollama_model


def default_model_settings(*, temperature: float | None = None) -> ModelSettings:
    """Build ModelSettings from config: temperature (default 0.0 = deterministic) + optional max_tokens.

    When the active provider is Anthropic and ``anthropic_prompt_caching`` is enabled, a cache
    breakpoint is placed on the system prompt/instructions so the large, repeated check prompt is
    served from Anthropic's prompt cache on subsequent calls (lower cost + latency).
    """
    kwargs: dict = {"temperature": settings.llm_temperature if temperature is None else temperature}
    if settings.llm_max_tokens:
        kwargs["max_tokens"] = settings.llm_max_tokens
    if settings.llm_provider.lower() == "anthropic" and getattr(settings, "anthropic_prompt_caching", True):
        try:
            from pydantic_ai.models.anthropic import AnthropicModelSettings

            return AnthropicModelSettings(anthropic_cache_instructions=True, **kwargs)
        except Exception as exc:  # pragma: no cover - depends on optional 'anthropic' extra
            logger.debug("Anthropic prompt caching unavailable, using plain ModelSettings: %s", exc)
    return ModelSettings(**kwargs)


def create_agent(
    system_prompt: str,
    *,
    output_validator: Callable | None = None,
    output_retries: int | None = None,
    model_settings: ModelSettings | None = None,
    analysis: bool = False,
    temperature: float | None = None,
) -> Agent:
    """Create a new PydanticAI agent with the given system prompt using the active provider.

    Args:
        system_prompt: System prompt for the agent.
        output_validator: Optional Pydantic AI output validator (may raise ModelRetry to
            request self-correction, e.g. for evidence grounding).
        output_retries: How often the model may self-correct on output-validation failure.
            Defaults to settings.llm_output_retries.
        model_settings: Override sampling settings; defaults to default_model_settings()
            (temperature from settings.llm_temperature, deterministic by default).
        analysis: Use the optional ``llm_analysis_model`` (stronger model for complex analyses
            like VVT/DSFA/AVV) when configured; otherwise the provider default model.
        temperature: Override the sampling temperature (e.g. for self-consistency sampling).
            Ignored when an explicit ``model_settings`` is passed.
    """
    model_name = _analysis_model_name() if analysis else None
    agent = Agent(
        model=get_active_model(model_name),
        system_prompt=system_prompt,
        model_settings=model_settings or default_model_settings(temperature=temperature),
        output_retries=output_retries if output_retries is not None else settings.llm_output_retries,
    )
    if output_validator is not None:
        agent.output_validator(output_validator)
    return agent


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
    elif provider == "openai_compatible":
        info["model"] = settings.llm_model
        info["base_url"] = settings.llm_base_url
        info["api_key_configured"] = bool(settings.llm_api_key.get_secret_value())
        info["structured_output_mode"] = settings.llm_structured_output_mode
    else:
        info["model"] = settings.ollama_model
        info["base_url"] = settings.ollama_base_url
        info["api_key_configured"] = True  # Ollama braucht keinen Key
    return info
