"""Weaviate integration: chunk documents, embed via Ollama, index and query for RAG checks."""
import logging
from urllib.parse import urlparse
from uuid import UUID

from app.config import settings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "DocumentChunk"
LEGAL_BASE_CHUNK_COLLECTION = "LegalBaseChunk"


def chunk_text(
    text: str,
    *,
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> list[str]:
    """Split text into overlapping chunks. Returns list of chunk strings."""
    size = chunk_size or settings.weaviate_chunk_size_chars
    overlap_chars = overlap or settings.weaviate_chunk_overlap_chars
    if not text or size <= 0:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + size
        chunk = text[start:end]
        if not chunk.strip():
            start = end - overlap_chars
            continue
        chunks.append(chunk)
        start = end - overlap_chars
        if start >= len(text):
            break
    return chunks


def get_embedding(text: str) -> list[float]:
    """Get embedding vector for text via Ollama. Returns list of floats."""
    try:
        import ollama
    except ImportError:
        logger.warning("ollama package not available for embeddings")
        return []

    base = (settings.ollama_base_url or "").rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3]
    host = base or "http://localhost:11434"

    try:
        client = ollama.Client(host=host)
        response = client.embed(model=settings.ollama_embedding_model, input=text)
        # response can be EmbedResponse with 'embeddings' (list of list) or single list
        if isinstance(response, dict):
            embs = response.get("embeddings")
        else:
            embs = getattr(response, "embeddings", None)
        if embs and len(embs) > 0:
            return list(embs[0]) if isinstance(embs[0], (list, tuple)) else list(embs)
    except Exception as e:
        logger.warning("Ollama embed failed: %s", e)
    return []


def _weaviate_host_port():
    """Parse WEAVIATE_URL into (host, port)."""
    url = (settings.weaviate_url or "").strip()
    if not url:
        return None, None
    if not url.startswith(("http://", "https://")):
        url = "http://" + url
    parsed = urlparse(url)
    host = parsed.hostname or "localhost"
    port = parsed.port or (443 if parsed.scheme == "https" else 8080)
    return host, port


def get_weaviate_client():
    """Return Weaviate client instance; None if unavailable or disabled."""
    host, port = _weaviate_host_port()
    if not host or not port:
        return None
    try:
        import weaviate
    except ImportError:
        logger.warning("weaviate-client not installed")
        return None

    try:
        client = weaviate.connect_to_local(host=host, port=port, grpc_port=50051)
        return client
    except Exception as e:
        logger.warning("Weaviate connection failed: %s", e)
        return None


def _ensure_collection(client):
    """Create DocumentChunk collection if it does not exist (vectorizer none, we pass vectors)."""
    from weaviate.collections.classes.config import Configure, DataType, Property

    if client.collections.exists(COLLECTION_NAME):
        return
    client.collections.create(
        name=COLLECTION_NAME,
        properties=[
            Property(name="text", data_type=DataType.TEXT),
            Property(name="document_id", data_type=DataType.UUID),
            Property(name="case_id", data_type=DataType.UUID),
            Property(name="chunk_index", data_type=DataType.INT),
        ],
        vectorizer_config=Configure.Vectorizer.none(),
    )
    logger.info("Weaviate collection %s created", COLLECTION_NAME)


def _ensure_legal_base_collection(client):
    """Create LegalBaseChunk collection if it does not exist."""
    from weaviate.collections.classes.config import Configure, DataType, Property

    if client.collections.exists(LEGAL_BASE_CHUNK_COLLECTION):
        return
    client.collections.create(
        name=LEGAL_BASE_CHUNK_COLLECTION,
        properties=[
            Property(name="text", data_type=DataType.TEXT),
            Property(name="legal_base_id", data_type=DataType.UUID),
            Property(name="legal_base_title", data_type=DataType.TEXT),
            Property(name="chunk_index", data_type=DataType.INT),
        ],
        vectorizer_config=Configure.Vectorizer.none(),
    )
    logger.info("Weaviate collection %s created", LEGAL_BASE_CHUNK_COLLECTION)


def index_legal_base(legal_base_id: UUID, title: str, content: str) -> bool:
    """
    Chunk legal base content, embed via Ollama, and upsert into Weaviate (replace existing chunks for legal_base_id).
    Returns True on success, False on skip/failure.
    """
    if not settings.weaviate_indexing_enabled:
        return False

    client = get_weaviate_client()
    if not client:
        return False

    content = (content or "").strip()
    if not content:
        delete_legal_base_chunks(legal_base_id)
        return True

    try:
        from weaviate.collections.classes.filters import Filter

        _ensure_legal_base_collection(client)
        collection = client.collections.get(LEGAL_BASE_CHUNK_COLLECTION)
        collection.data.delete_many(where=Filter.by_property("legal_base_id").equal(legal_base_id))

        chunks = chunk_text(content)
        if not chunks:
            return True

        title_display = (title or "").strip() or "Rechtsgrundlage"
        for i, chunk in enumerate(chunks):
            vector = get_embedding(chunk)
            if not vector:
                logger.warning("Skipping legal base chunk %s for %s (no embedding)", i, legal_base_id)
                continue
            collection.data.insert(
                properties={
                    "text": chunk,
                    "legal_base_id": legal_base_id,
                    "legal_base_title": title_display,
                    "chunk_index": i,
                },
                vector=vector,
            )

        return True
    except Exception as e:
        logger.exception("Weaviate index_legal_base failed: %s", e)
        return False
    finally:
        try:
            client.close()
        except Exception:
            pass


def delete_legal_base_chunks(legal_base_id: UUID) -> bool:
    """Remove all chunks for a legal base. Returns True if client available and delete ran."""
    from weaviate.collections.classes.filters import Filter

    client = get_weaviate_client()
    if not client:
        return False
    try:
        if not client.collections.exists(LEGAL_BASE_CHUNK_COLLECTION):
            return True
        collection = client.collections.get(LEGAL_BASE_CHUNK_COLLECTION)
        collection.data.delete_many(where=Filter.by_property("legal_base_id").equal(legal_base_id))
        return True
    except Exception as e:
        logger.warning("Weaviate delete_legal_base_chunks failed: %s", e)
        return False
    finally:
        try:
            client.close()
        except Exception:
            pass


def get_relevant_legal_base_chunks(
    legal_base_ids: list[UUID],
    query_text: str,
    *,
    top_k: int | None = None,
    include_source: bool = True,
) -> list[str]:
    """
    Return list of chunk text strings from the given legal bases most relevant to query_text.
    If include_source is True, each string is prefixed with "[Quelle: <title>] " for attribution.
    """
    if not legal_base_ids or not (query_text or "").strip():
        return []

    k = top_k or getattr(settings, "weaviate_legal_bases_top_k", 8)
    client = get_weaviate_client()
    if not client:
        return []

    query_vector = get_embedding(query_text)
    if not query_vector:
        return []

    try:
        from weaviate.collections.classes.filters import Filter

        if not client.collections.exists(LEGAL_BASE_CHUNK_COLLECTION):
            return []
        collection = client.collections.get(LEGAL_BASE_CHUNK_COLLECTION)
        response = collection.query.near_vector(
            near_vector=query_vector,
            limit=k,
            filters=Filter.by_property("legal_base_id").contains_any(legal_base_ids),
        )
        result: list[str] = []
        for obj in response.objects:
            props = obj.properties or {}
            text = props.get("text") or ""
            if not text:
                continue
            if include_source:
                title = (props.get("legal_base_title") or "").strip() or "Rechtsgrundlage"
                result.append(f"[Quelle: {title}]\n{text}")
            else:
                result.append(text)
        return result
    except Exception as e:
        logger.warning("Weaviate get_relevant_legal_base_chunks failed: %s", e)
        return []
    finally:
        try:
            client.close()
        except Exception:
            pass


def index_document_chunks(document_id: UUID, case_id: UUID, text: str) -> bool:
    """
    Chunk text, embed via Ollama, and upsert into Weaviate (replace existing chunks for document_id).
    Returns True on success, False on skip/failure.
    """
    if not settings.weaviate_indexing_enabled or not text:
        return False

    client = get_weaviate_client()
    if not client:
        return False

    try:
        _ensure_collection(client)
        collection = client.collections.get(COLLECTION_NAME)

        # Delete existing chunks for this document (idempotent replace)
        from weaviate.collections.classes.filters import Filter

        collection.data.delete_many(where=Filter.by_property("document_id").equal(document_id))

        chunks = chunk_text(text)
        if not chunks:
            return True

        for i, chunk in enumerate(chunks):
            vector = get_embedding(chunk)
            if not vector:
                logger.warning("Skipping chunk %s for document %s (no embedding)", i, document_id)
                continue
            collection.data.insert(
                properties={
                    "text": chunk,
                    "document_id": document_id,
                    "case_id": case_id,
                    "chunk_index": i,
                },
                vector=vector,
            )

        return True
    except Exception as e:
        logger.exception("Weaviate index_document_chunks failed: %s", e)
        return False
    finally:
        try:
            client.close()
        except Exception:
            pass


def delete_chunks_by_document_id(document_id: UUID) -> bool:
    """Remove all chunks for a document. Returns True if client available and delete ran."""
    from weaviate.collections.classes.filters import Filter

    client = get_weaviate_client()
    if not client:
        return False
    try:
        if not client.collections.exists(COLLECTION_NAME):
            return True
        collection = client.collections.get(COLLECTION_NAME)
        collection.data.delete_many(where=Filter.by_property("document_id").equal(document_id))
        return True
    except Exception as e:
        logger.warning("Weaviate delete_chunks_by_document_id failed: %s", e)
        return False
    finally:
        try:
            client.close()
        except Exception:
            pass


def delete_chunks_by_case_id(case_id: UUID) -> bool:
    """Remove all chunks for a case. Returns True if client available and delete ran."""
    from weaviate.collections.classes.filters import Filter

    client = get_weaviate_client()
    if not client:
        return False
    try:
        if not client.collections.exists(COLLECTION_NAME):
            return True
        collection = client.collections.get(COLLECTION_NAME)
        collection.data.delete_many(where=Filter.by_property("case_id").equal(case_id))
        return True
    except Exception as e:
        logger.warning("Weaviate delete_chunks_by_case_id failed: %s", e)
        return False
    finally:
        try:
            client.close()
        except Exception:
            pass


def get_relevant_chunks(
    document_id: UUID,
    query_text: str,
    *,
    top_k: int | None = None,
) -> list[str]:
    """
    Return list of chunk text strings most relevant to query_text for the given document.
    Uses query embedding and vector search scoped to document_id.
    """
    k = top_k or settings.weaviate_top_k
    client = get_weaviate_client()
    if not client:
        return []

    query_vector = get_embedding(query_text)
    if not query_vector:
        return []

    try:
        from weaviate.collections.classes.filters import Filter

        if not client.collections.exists(COLLECTION_NAME):
            return []
        collection = client.collections.get(COLLECTION_NAME)
        response = collection.query.near_vector(
            near_vector=query_vector,
            limit=k,
            filters=Filter.by_property("document_id").equal(document_id),
        )
        return [obj.properties["text"] for obj in response.objects if obj.properties.get("text")]
    except Exception as e:
        logger.warning("Weaviate get_relevant_chunks failed: %s", e)
        return []
    finally:
        try:
            client.close()
        except Exception:
            pass


def get_relevant_chunks_for_case(
    case_id: UUID,
    query_text: str,
    *,
    top_k_per_doc: int | None = None,
) -> list[str]:
    """
    Return list of chunk text strings most relevant to query_text across all documents of the case.
    """
    k = top_k_per_doc or settings.weaviate_top_k
    client = get_weaviate_client()
    if not client:
        return []

    query_vector = get_embedding(query_text)
    if not query_vector:
        return []

    try:
        from weaviate.collections.classes.filters import Filter

        if not client.collections.exists(COLLECTION_NAME):
            return []
        collection = client.collections.get(COLLECTION_NAME)
        response = collection.query.near_vector(
            near_vector=query_vector,
            limit=min(50, k * 5),
            filters=Filter.by_property("case_id").equal(case_id),
        )
        return [obj.properties["text"] for obj in response.objects if obj.properties.get("text")]
    except Exception as e:
        logger.warning("Weaviate get_relevant_chunks_for_case failed: %s", e)
        return []
    finally:
        try:
            client.close()
        except Exception:
            pass
