"""File storage abstraction (local filesystem or S3/MinIO)."""
import io
import logging
import mimetypes
import uuid
from pathlib import Path

from minio import Minio
from minio.error import S3Error

from app.config import settings

logger = logging.getLogger(__name__)


# --- Local Storage ---

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
    root = Path(settings.storage_local_path).resolve()
    path = (root / storage_path).resolve()
    if not path.is_relative_to(root):
        raise ValueError(f"Path traversal denied: {storage_path}")
    if not path.is_file():
        raise FileNotFoundError(storage_path)
    return path.read_bytes()


def delete_file_local(storage_path: str) -> None:
    """Delete file from local storage."""
    root = Path(settings.storage_local_path).resolve()
    path = (root / storage_path).resolve()
    if not path.is_relative_to(root):
        raise ValueError(f"Path traversal denied: {storage_path}")
    if path.is_file():
        path.unlink()


# --- MinIO / S3 Storage ---

_minio_client = None

def _get_minio_client() -> Minio:
    global _minio_client
    if _minio_client is None:
        if not settings.s3_endpoint_url:
            raise ValueError("S3_ENDPOINT_URL is not set")
        
        # Parse endpoint to remove http/https if present for Minio client
        endpoint = settings.s3_endpoint_url.replace("http://", "").replace("https://", "")
        secure = settings.s3_endpoint_url.startswith("https://")

        _minio_client = Minio(
            endpoint,
            access_key=settings.s3_access_key,
            secret_key=settings.s3_secret_key,
            secure=secure
        )
    return _minio_client


def _ensure_bucket(client: Minio, bucket_name: str):
    if not client.bucket_exists(bucket_name):
        client.make_bucket(bucket_name)


def save_file_minio(case_id: uuid.UUID, document_id: uuid.UUID, filename: str, content: bytes) -> str:
    """Save file to MinIO. Returns object name."""
    client = _get_minio_client()
    bucket = settings.s3_bucket
    _ensure_bucket(client, bucket)

    ext = Path(filename).suffix or ""
    object_name = f"cases/{case_id}/{document_id}{ext}"
    
    content_type, _ = mimetypes.guess_type(filename)
    client.put_object(
        bucket,
        object_name,
        io.BytesIO(content),
        len(content),
        content_type=content_type or "application/octet-stream",
    )
    return object_name


def get_file_minio(storage_path: str) -> bytes:
    """Read file from MinIO."""
    client = _get_minio_client()
    bucket = settings.s3_bucket
    
    try:
        response = client.get_object(bucket, storage_path)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()
    except S3Error as e:
        if e.code == "NoSuchKey":
            raise FileNotFoundError(storage_path)
        raise


def delete_file_minio(storage_path: str) -> None:
    """Delete object from MinIO."""
    client = _get_minio_client()
    bucket = settings.s3_bucket
    try:
        client.remove_object(bucket, storage_path)
    except S3Error as e:
        if e.code != "NoSuchKey":
            logger.warning("MinIO delete failed for %s: %s", storage_path, e)


# --- Public Interface ---

def save_file(case_id: uuid.UUID, document_id: uuid.UUID, filename: str, content: bytes) -> str:
    """Save file using configured backend. Returns storage_path for DB."""
    if settings.storage_backend == "local":
        return save_file_local(case_id, document_id, filename, content)
    elif settings.storage_backend == "minio":
        return save_file_minio(case_id, document_id, filename, content)
    raise ValueError(f"Unsupported storage_backend: {settings.storage_backend}")


def get_file(storage_path: str) -> bytes:
    """Read file by storage_path."""
    if settings.storage_backend == "local":
        return get_file_local(storage_path)
    elif settings.storage_backend == "minio":
        return get_file_minio(storage_path)
    raise ValueError(f"Unsupported storage_backend: {settings.storage_backend}")


def delete_file(storage_path: str) -> None:
    """Delete file by storage_path."""
    if settings.storage_backend == "local":
        delete_file_local(storage_path)
    elif settings.storage_backend == "minio":
        delete_file_minio(storage_path)
    else:
        raise ValueError(f"Unsupported storage_backend: {settings.storage_backend}")


# --- TOM Attachment Storage ---

def _local_tom_path(tom_id: uuid.UUID, attachment_id: uuid.UUID, filename: str) -> Path:
    """Build path for TOM attachment: toms/{tom_id}/{attachment_id}.{ext}"""
    root = Path(settings.storage_local_path)
    root.mkdir(parents=True, exist_ok=True)
    base = root / "toms" / str(tom_id)
    base.mkdir(parents=True, exist_ok=True)
    ext = Path(filename).suffix or ""
    return base / f"{attachment_id}{ext}"


def save_tom_file_local(tom_id: uuid.UUID, attachment_id: uuid.UUID, filename: str, content: bytes) -> str:
    path = _local_tom_path(tom_id, attachment_id, filename)
    path.write_bytes(content)
    return str(path.relative_to(settings.storage_local_path))


def save_tom_file_minio(tom_id: uuid.UUID, attachment_id: uuid.UUID, filename: str, content: bytes) -> str:
    client = _get_minio_client()
    bucket = settings.s3_bucket
    _ensure_bucket(client, bucket)
    ext = Path(filename).suffix or ""
    object_name = f"toms/{tom_id}/{attachment_id}{ext}"
    content_type, _ = mimetypes.guess_type(filename)
    client.put_object(
        bucket,
        object_name,
        io.BytesIO(content),
        len(content),
        content_type=content_type or "application/octet-stream",
    )
    return object_name


def save_tom_file(tom_id: uuid.UUID, attachment_id: uuid.UUID, filename: str, content: bytes) -> str:
    """Save TOM attachment using configured backend. Returns storage_path for DB."""
    if settings.storage_backend == "local":
        return save_tom_file_local(tom_id, attachment_id, filename, content)
    elif settings.storage_backend == "minio":
        return save_tom_file_minio(tom_id, attachment_id, filename, content)
    raise ValueError(f"Unsupported storage_backend: {settings.storage_backend}")


def get_tom_file(storage_path: str) -> bytes:
    """Read TOM attachment. Delegates to backend-agnostic get_file."""
    return get_file(storage_path)


def delete_tom_file(storage_path: str) -> None:
    """Delete TOM attachment. Delegates to backend-agnostic delete_file."""
    delete_file(storage_path)
