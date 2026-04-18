"""File storage abstraction (local filesystem or S3/MinIO).

Concrete backends implement StorageBackend. Call get_storage() to obtain
the backend selected by STORAGE_BACKEND env var.
"""
import io
import logging
import mimetypes
import uuid
from pathlib import Path
from typing import Protocol

from minio import Minio
from minio.error import S3Error

from app.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Backend Protocol
# ---------------------------------------------------------------------------

class StorageBackend(Protocol):
    def save(self, rel_path: str, content: bytes, filename: str) -> str: ...
    def get(self, storage_path: str) -> bytes: ...
    def delete(self, storage_path: str) -> None: ...


# ---------------------------------------------------------------------------
# Local filesystem backend
# ---------------------------------------------------------------------------

class _LocalBackend:
    def _resolve(self, storage_path: str) -> Path:
        root = Path(settings.storage_local_path).resolve()
        path = (root / storage_path).resolve()
        if not path.is_relative_to(root):
            logger.warning("Path traversal attempt denied", extra={"storage_path": storage_path})
            raise ValueError(f"Path traversal denied: {storage_path}")
        return path

    def save(self, rel_path: str, content: bytes, filename: str) -> str:
        root = Path(settings.storage_local_path)
        path = root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return rel_path

    def get(self, storage_path: str) -> bytes:
        path = self._resolve(storage_path)
        if not path.is_file():
            raise FileNotFoundError(storage_path)
        return path.read_bytes()

    def delete(self, storage_path: str) -> None:
        path = self._resolve(storage_path)
        if path.is_file():
            path.unlink()


# ---------------------------------------------------------------------------
# MinIO / S3 backend
# ---------------------------------------------------------------------------

class _MinioBackend:
    _client: Minio | None = None

    def _get_client(self) -> Minio:
        if self._client is None:
            if not settings.s3_endpoint_url:
                raise ValueError("S3_ENDPOINT_URL is not set")
            endpoint = settings.s3_endpoint_url.replace("http://", "").replace("https://", "")
            secure = settings.s3_endpoint_url.startswith("https://")
            self._client = Minio(
                endpoint,
                access_key=settings.s3_access_key,
                secret_key=settings.s3_secret_key,
                secure=secure,
            )
        return self._client

    def _ensure_bucket(self, client: Minio) -> None:
        bucket = settings.s3_bucket
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)

    def save(self, rel_path: str, content: bytes, filename: str) -> str:
        client = self._get_client()
        self._ensure_bucket(client)
        content_type, _ = mimetypes.guess_type(filename)
        try:
            client.put_object(
                settings.s3_bucket,
                rel_path,
                io.BytesIO(content),
                len(content),
                content_type=content_type or "application/octet-stream",
            )
        except Exception as exc:
            logger.error("Storage write failed (MinIO)", extra={"object_name": rel_path, "error": str(exc)})
            raise
        return rel_path

    def get(self, storage_path: str) -> bytes:
        client = self._get_client()
        try:
            response = client.get_object(settings.s3_bucket, storage_path)
            try:
                return response.read()
            finally:
                response.close()
                response.release_conn()
        except S3Error as e:
            if e.code == "NoSuchKey":
                raise FileNotFoundError(storage_path)
            raise

    def delete(self, storage_path: str) -> None:
        client = self._get_client()
        try:
            client.remove_object(settings.s3_bucket, storage_path)
        except S3Error as e:
            if e.code != "NoSuchKey":
                logger.warning("MinIO delete failed for %s: %s", storage_path, e)


# ---------------------------------------------------------------------------
# Backend factory (singleton per process)
# ---------------------------------------------------------------------------

_backend: StorageBackend | None = None


def get_storage() -> StorageBackend:
    global _backend
    if _backend is None:
        if settings.storage_backend == "minio":
            _backend = _MinioBackend()
        elif settings.storage_backend == "local":
            _backend = _LocalBackend()
        else:
            raise ValueError(f"Unsupported storage_backend: {settings.storage_backend}")
    return _backend


# ---------------------------------------------------------------------------
# Path builders
# ---------------------------------------------------------------------------

def _document_rel_path(case_id: uuid.UUID, document_id: uuid.UUID, filename: str) -> str:
    ext = Path(filename).suffix or ""
    return f"cases/{case_id}/{document_id}{ext}"


def _tom_rel_path(tom_id: uuid.UUID, attachment_id: uuid.UUID, filename: str) -> str:
    ext = Path(filename).suffix or ""
    return f"toms/{tom_id}/{attachment_id}{ext}"


# ---------------------------------------------------------------------------
# Public Interface — document storage
# ---------------------------------------------------------------------------

def save_file(case_id: uuid.UUID, document_id: uuid.UUID, filename: str, content: bytes) -> str:
    """Save document using configured backend. Returns storage_path for DB."""
    rel_path = _document_rel_path(case_id, document_id, filename)
    return get_storage().save(rel_path, content, filename)


def get_file(storage_path: str) -> bytes:
    """Read document by storage_path."""
    return get_storage().get(storage_path)


def delete_file(storage_path: str) -> None:
    """Delete document by storage_path."""
    get_storage().delete(storage_path)


# ---------------------------------------------------------------------------
# Public Interface — TOM attachment storage
# ---------------------------------------------------------------------------

def save_tom_file(tom_id: uuid.UUID, attachment_id: uuid.UUID, filename: str, content: bytes) -> str:
    """Save TOM attachment using configured backend. Returns storage_path for DB."""
    rel_path = _tom_rel_path(tom_id, attachment_id, filename)
    return get_storage().save(rel_path, content, filename)


def get_tom_file(storage_path: str) -> bytes:
    """Read TOM attachment."""
    return get_storage().get(storage_path)


def delete_tom_file(storage_path: str) -> None:
    """Delete TOM attachment."""
    get_storage().delete(storage_path)
