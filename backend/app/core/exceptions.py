"""Domain-specific exception hierarchy for Datenschutzagent.

Using typed exceptions instead of bare Exception / ValueError lets callers
catch specific failure modes without accidentally swallowing unrelated errors.
"""


class DatenschutzAgentError(Exception):
    """Base class for all application-level exceptions."""


# ---------------------------------------------------------------------------
# LLM / Provider errors
# ---------------------------------------------------------------------------


class LLMProviderError(DatenschutzAgentError):
    """Raised when an LLM provider call fails (network, auth, quota, …)."""


class LLMRetryExhaustedError(LLMProviderError):
    """Raised when all retry attempts for an LLM call have been exhausted."""


# ---------------------------------------------------------------------------
# Security errors
# ---------------------------------------------------------------------------


class PromptInjectionError(DatenschutzAgentError):
    """Raised when a prompt injection pattern is detected and blocking is enabled."""


# ---------------------------------------------------------------------------
# Infrastructure errors
# ---------------------------------------------------------------------------


class RAGUnavailableError(DatenschutzAgentError):
    """Raised when the vector store (Weaviate) is unreachable and no fallback exists."""


class CacheError(DatenschutzAgentError):
    """Raised on unrecoverable LLM response cache failures."""
