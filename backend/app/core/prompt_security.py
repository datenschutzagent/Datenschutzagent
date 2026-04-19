"""Utility functions for securing user-controlled input before LLM prompt interpolation.

Addresses OWASP A03 (Injection) – prompt injection risk in LLM-integrated services.
User-controlled fields (case titles, descriptions, department names, etc.) must be
sanitized before being interpolated into LLM prompts to prevent adversarial manipulation
of AI-generated compliance assessments.
"""
import logging
import re

from app.config import settings
from app.core.exceptions import PromptInjectionError

logger = logging.getLogger("app.security")

# Default maximum characters for a single user-controlled field in a prompt
_DEFAULT_MAX_FIELD_CHARS = 2000

# Patterns commonly used in prompt injection attacks
_INJECTION_PATTERN = re.compile(
    r"(ignore\s+(previous|above|all|prior)\s+instructions?"
    r"|disregard\s+(the\s+)?(above|previous|prior|all)"
    r"|you\s+are\s+now\s+(a\s+)?"
    r"|act\s+as\s+(a\s+)?"
    r"|new\s+persona"
    r"|###\s*(system|instructions?|prompt)"
    r"|<\|im_start\|>"
    r"|<\|im_end\|>"
    r"|\[INST\]"
    r"|<system>"
    r")",
    re.IGNORECASE,
)


def sanitize_prompt_field(value: str | None, max_chars: int = _DEFAULT_MAX_FIELD_CHARS) -> str:
    """Sanitize a user-controlled value before interpolation into an LLM prompt.

    - Handles None gracefully
    - Truncates to max_chars
    - Escapes Python format-string braces ({ → {{, } → }}) to prevent accidental
      or malicious format-string injection when the result is passed to .format()
    - Logs a warning (but does NOT block) if prompt injection patterns are detected

    Args:
        value: The user-controlled string to sanitize.
        max_chars: Maximum characters to allow (excess is truncated).

    Returns:
        Sanitized string safe for interpolation into LLM prompts via .format().
    """
    if value is None:
        return ""

    text = str(value)

    # Truncate to maximum length
    if len(text) > max_chars:
        text = text[:max_chars]

    # Escape Python format-string syntax to prevent .format() injection.
    # E.g. a user who enters "{instructions}" as a case title would otherwise
    # cause a KeyError or inject an unintended placeholder.
    text = text.replace("{", "{{").replace("}", "}}")

    # Detect common prompt injection patterns.
    # When PROMPT_INJECTION_BLOCK=true the request is rejected; otherwise it is
    # only logged so operators can monitor suspicious inputs without breaking
    # legitimate edge-case content.
    if _INJECTION_PATTERN.search(text):
        logger.warning(
            "Potential prompt injection pattern detected in user input",
            extra={
                "event": "prompt_injection_attempt",
                "value_preview": text[:100],
                "blocked": settings.prompt_injection_block,
            },
        )
        if settings.prompt_injection_block:
            raise PromptInjectionError(
                "Input rejected: potential prompt injection pattern detected. "
                "Remove instructions that attempt to override system behaviour."
            )

    return text
