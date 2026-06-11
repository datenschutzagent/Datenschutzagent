"""Domain-specific exception hierarchy for Datenschutzagent.

Using typed exceptions instead of bare Exception / ValueError lets callers
catch specific failure modes without accidentally swallowing unrelated errors.
"""

from enum import StrEnum


class ErrorCode(StrEnum):
    """Machine-readable error codes for RFC 7807 Problem Details responses."""

    # Auth
    AUTH_NO_CREDENTIALS = "AUTH_NO_CREDENTIALS"
    AUTH_TOKEN_EXPIRED = "AUTH_TOKEN_EXPIRED"
    AUTH_TOKEN_INVALID = "AUTH_TOKEN_INVALID"
    AUTH_TOKEN_MISSING_KID = "AUTH_TOKEN_MISSING_KID"
    AUTH_SIGNING_KEY_NOT_FOUND = "AUTH_SIGNING_KEY_NOT_FOUND"
    AUTH_OIDC_UNAVAILABLE = "AUTH_OIDC_UNAVAILABLE"
    AUTH_SESSION_EXPIRED = "AUTH_SESSION_EXPIRED"

    # Authorization
    PERMISSION_DENIED = "PERMISSION_DENIED"

    # Resources
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"

    # Validation
    VALIDATION_ERROR = "VALIDATION_ERROR"
    UNSUPPORTED_MEDIA_TYPE = "UNSUPPORTED_MEDIA_TYPE"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"

    # Rate limiting
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"

    # LLM / AI
    LLM_UNAVAILABLE = "LLM_UNAVAILABLE"
    LLM_RETRY_EXHAUSTED = "LLM_RETRY_EXHAUSTED"

    # Generic
    INTERNAL_ERROR = "INTERNAL_ERROR"


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
