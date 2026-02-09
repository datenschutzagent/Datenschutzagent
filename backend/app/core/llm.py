from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel

from app.config import settings


def _ollama_base_url() -> str:
    """Ollama OpenAI-compatible API is at /v1."""
    base = settings.ollama_base_url.rstrip("/")
    return f"{base}/v1" if not base.endswith("/v1") else base


def get_ollama_model() -> OpenAIModel:
    """Get configured Ollama model (OpenAI-compatible API) via Pydantic AI OpenAIModel."""
    return OpenAIModel(
        settings.ollama_model,
        base_url=_ollama_base_url(),
    )


def create_agent(system_prompt: str) -> Agent:
    """Create a new PydanticAI agent with the given system prompt."""
    return Agent(
        model=get_ollama_model(),
        system_prompt=system_prompt
    )
