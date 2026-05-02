"""Application-wide constants and enumerations.

Centralises magic strings used across models, services, and routes so that
changes only need to be made in one place.
"""
from enum import StrEnum


class CaseStatus(StrEnum):
    INTAKE = "intake"
    IN_REVIEW = "in_review"
    QUESTIONS_PENDING = "questions_pending"
    REVISION = "revision"
    READY_FOR_DECISION = "ready_for_decision"
    COMPLETED = "completed"


class FindingStatus(StrEnum):
    OPEN = "open"
    ACCEPTED = "accepted"
    OVERRULED = "overruled"
    FIXED = "fixed"


class FindingSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class DocumentExtractionStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class DocumentExtractionMethod(StrEnum):
    TEXT = "text"
    OCR = "ocr"


class UserRole(StrEnum):
    VIEWER = "viewer"
    EDITOR = "editor"
    ADMIN = "admin"


class CheckStrategy(StrEnum):
    FULL_TEXT = "full_text"
    RAG = "rag"


class LegalBaseApplicability(StrEnum):
    ALWAYS = "always"
    CONDITIONAL = "conditional"


class JobStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class WebhookDeliveryStatus(StrEnum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
