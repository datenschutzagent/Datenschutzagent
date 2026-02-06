from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel

from app.config import settings


def _ollama_base_url() -> str:
    """Ollama OpenAI-compatible API is at /v1."""
    base = settings.ollama_base_url.rstrip("/")
    return f"{base}/v1" if not base.endswith("/v1") else base


def get_ollama_model() -> OpenAIModel:
    """Get configured Ollama model via Pydantic AI Ollama provider (uses OLLAMA_BASE_URL with /v1)."""
    import os
    # OllamaProvider reads OLLAMA_BASE_URL; ensure it has /v1 for OpenAI-compatible API
    os.environ.setdefault("OLLAMA_BASE_URL", _ollama_base_url())
    return OpenAIModel(settings.ollama_model, provider="ollama")


def create_agent(system_prompt: str) -> Agent:
    """Create a new PydanticAI agent with the given system prompt."""
    return Agent(
        model=get_ollama_model(),
        system_prompt=system_prompt
    )
