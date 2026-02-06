from openai import AsyncOpenAI

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from app.config import settings


def _ollama_base_url() -> str:
    """Ollama OpenAI-compatible API is at /v1."""
    base = settings.ollama_base_url.rstrip("/")
    return f"{base}/v1" if not base.endswith("/v1") else base


def get_ollama_model() -> OpenAIChatModel:
    """Get configured Ollama model (OpenAI-compatible API)."""
    client = AsyncOpenAI(
        base_url=_ollama_base_url(),
        api_key="ollama",  # Ollama doesn't validate; client often requires a value
    )
    return OpenAIChatModel(
        settings.ollama_model,
        provider=OpenAIProvider(openai_client=client),
    )


def create_agent(system_prompt: str) -> Agent:
    """Create a new PydanticAI agent with the given system prompt."""
    return Agent(
        model=get_ollama_model(),
        system_prompt=system_prompt
    )
