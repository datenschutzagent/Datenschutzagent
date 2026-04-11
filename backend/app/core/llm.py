"""LLM-Provider-Abstraktion: Ollama, OpenAI und Anthropic.

Der aktive Provider wird über die Einstellung LLM_PROVIDER gesteuert:
  - "ollama"    → lokales Ollama (Standard, kein API-Key erforderlich)
  - "openai"    → OpenAI API (OPENAI_API_KEY erforderlich)
  - "anthropic" → Anthropic API (ANTHROPIC_API_KEY erforderlich, 'anthropic'-Package nötig)
"""
import httpx
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

from app.config import settings


def _ollama_base_url() -> str:
    """Ollama OpenAI-compatible API is at /v1."""
    base = settings.ollama_base_url.rstrip("/")
    return f"{base}/v1" if not base.endswith("/v1") else base


def get_ollama_model() -> OpenAIModel:
    """Get configured Ollama model (OpenAI-compatible API) via Pydantic AI OpenAIModel."""
    timeout = settings.ollama_timeout_seconds
    http_client = httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=10.0))
    provider = OpenAIProvider(base_url=_ollama_base_url(), http_client=http_client)
    return OpenAIModel(settings.ollama_model, provider=provider)


def get_openai_model() -> OpenAIModel:
    """Get configured OpenAI model via Pydantic AI OpenAIModel."""
    if not settings.openai_api_key:
        raise RuntimeError(
            "LLM_PROVIDER=openai erfordert OPENAI_API_KEY. "
            "Bitte in der .env-Datei setzen."
        )
    provider = OpenAIProvider(api_key=settings.openai_api_key)
    return OpenAIModel(settings.openai_model, provider=provider)


def get_anthropic_model():
    """Get configured Anthropic model via Pydantic AI AnthropicModel.

    Requires the 'anthropic' package: pip install anthropic
    """
    if not settings.anthropic_api_key:
        raise RuntimeError(
            "LLM_PROVIDER=anthropic erfordert ANTHROPIC_API_KEY. "
            "Bitte in der .env-Datei setzen."
        )
    try:
        from pydantic_ai.models.anthropic import AnthropicModel
        from pydantic_ai.providers.anthropic import AnthropicProvider
        provider = AnthropicProvider(api_key=settings.anthropic_api_key)
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
        info["api_key_configured"] = bool(settings.openai_api_key)
    elif provider == "anthropic":
        info["model"] = settings.anthropic_model
        info["api_key_configured"] = bool(settings.anthropic_api_key)
    else:
        info["model"] = settings.ollama_model
        info["base_url"] = settings.ollama_base_url
        info["api_key_configured"] = True  # Ollama braucht keinen Key
    return info
