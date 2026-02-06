"""File storage abstraction (local filesystem or S3/MinIO)."""
import os
import uuid
from pathlib import Path

from app.config import settings


def _local_path(case_id: uuid.UUID, document_id: uuid.UUID, filename: str) -> Path:
    """Build relative path under storage root: cases/{case_id}/{document_id}_{filename}."""
    root = Path(settings.storage_local_path)
    root.mkdir(parents=True, exist_ok=True)
    base = root / "cases" / str(case_id)
    base.mkdir(parents=True, exist_ok=True)
    # Keep extension, sanitize name
    ext = Path(filename).suffix or ""
    safe_name = f"{document_id}{ext}"
    return base / safe_name


def save_file_local(case_id: uuid.UUID, document_id: uuid.UUID, filename: str, content: bytes) -> str:
    """Save file to local storage. Returns path relative to storage root for DB."""
    path = _local_path(case_id, document_id, filename)
    path.write_bytes(content)
    return str(path.relative_to(settings.storage_local_path))


def get_file_local(storage_path: str) -> bytes:
    """Read file from local storage. storage_path is relative to storage_local_path."""
    path = Path(settings.storage_local_path) / storage_path
    if not path.is_file():
        raise FileNotFoundError(storage_path)
    return path.read_bytes()


def save_file(case_id: uuid.UUID, document_id: uuid.UUID, filename: str, content: bytes) -> str:
    """Save file using configured backend. Returns storage_path for DB."""
    if settings.storage_backend == "local":
        return save_file_local(case_id, document_id, filename, content)
    raise ValueError(f"Unsupported storage_backend: {settings.storage_backend}")


def get_file(storage_path: str) -> bytes:
    """Read file by storage_path."""
    if settings.storage_backend == "local":
        return get_file_local(storage_path)
    raise ValueError(f"Unsupported storage_backend: {settings.storage_backend}")
