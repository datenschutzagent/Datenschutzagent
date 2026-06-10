"""Weaviate integration: chunk documents, embed via Ollama, index and query for RAG checks."""
import logging
import re
from urllib.parse import urlparse
from uuid import UUID

from app.config import settings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "DocumentChunk"
LEGAL_BASE_CHUNK_COLLECTION = "LegalBaseChunk"

# Sentence boundary: ends with . ! ? followed by whitespace or end-of-string,
# or a blank line (paragraph boundary).
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+|(?:\n\s*\n)")


def _split_sentences(text: str) -> list[str]:
    """Split text into sentence-level fragments preserving paragraph structure."""
    parts = _SENTENCE_BOUNDARY.split(text)
    return [p.strip() for p in parts if p and p.strip()]


# Markdown table / sheet-label recognisers. The extractor (document_processor) emits XLSX sheets
# and DOCX tables as Markdown pipe-tables and labels XLSX sheets with "--- Sheet: <name> ---".
_SHEET_LABEL = re.compile(r"^---\s*Sheet:.*---\s*$")


def _is_table_row(line: str) -> bool:
    s = line.strip()
    return len(s) >= 2 and s.startswith("|") and s.endswith("|")


def _is_separator_row(line: str) -> bool:
    """True for a Markdown header-separator row like ``| --- | --- |``."""
    s = line.strip().strip("|")
    cells = s.split("|")
    return bool(cells) and all("-" in c and set(c.strip()) <= set("-: ") for c in cells)


def _chunk_prose(text: str, size: int, overlap_chars: int) -> list[str]:
    """Sentence-aware overlapping chunking for free text (no Markdown tables).

    Respects sentence/paragraph boundaries so context windows receive complete thoughts. When a
    single sentence exceeds ``size`` it is emitted as its own chunk.
    """
    sentences = _split_sentences(text)
    if not sentences:
        return []

    chunks: list[str] = []
    current_parts: list[str] = []
    current_len = 0

    for sentence in sentences:
        sentence_len = len(sentence)

        # Sentence fits in current chunk
        if current_len + (1 if current_parts else 0) + sentence_len <= size:
            current_parts.append(sentence)
            current_len += (1 if len(current_parts) > 1 else 0) + sentence_len
        else:
            # Flush current chunk
            if current_parts:
                chunks.append(" ".join(current_parts))

            # Start next chunk: prepend overlap tail from previous chunk
            if chunks and overlap_chars > 0:
                overlap_text = chunks[-1][-overlap_chars:]
                current_parts = [overlap_text, sentence]
                current_len = len(overlap_text) + 1 + sentence_len
            else:
                current_parts = [sentence]
                current_len = sentence_len

            # If single sentence still exceeds chunk_size, emit it as-is
            if sentence_len > size:
                chunks.append(" ".join(current_parts))
                current_parts = []
                current_len = 0

    if current_parts:
        chunks.append(" ".join(current_parts))

    return [c for c in chunks if c.strip()]


def _chunk_table(label: str | None, header: str, sep: str, body_rows: list[str], size: int) -> list[str]:
    """Split a Markdown table into chunks, repeating the (sheet label +) header on each chunk.

    Repeating the column-letter / column-name header on every chunk is what keeps coordinate-based
    evidence (e.g. "Sheet X, Spalte C, Zeile 12") meaningful after a large table is split.
    """
    prefix_lines = ([label] if label else []) + [header, sep]
    prefix = "\n".join(prefix_lines)
    if not body_rows:
        return [prefix]

    chunks: list[str] = []
    batch: list[str] = []
    cur_len = len(prefix)
    for row in body_rows:
        add = len(row) + 1
        if batch and cur_len + add > size:
            chunks.append(prefix + "\n" + "\n".join(batch))
            batch = [row]
            cur_len = len(prefix) + add
        else:
            batch.append(row)
            cur_len += add
    if batch:
        chunks.append(prefix + "\n" + "\n".join(batch))
    return chunks


def _segment_blocks(lines: list[str]) -> list[tuple[str, object]]:
    """Segment lines into ordered ("prose", text) and ("table", (label, header, sep, rows)) blocks."""
    blocks: list[tuple[str, object]] = []
    prose: list[str] = []
    pending_label: str | None = None  # a "--- Sheet: ... ---" line awaiting its table
    i = 0
    n = len(lines)

    def _flush_prose() -> None:
        nonlocal prose
        if prose:
            text = "\n".join(prose).strip()
            if text:
                blocks.append(("prose", text))
            prose = []

    while i < n:
        line = lines[i]
        # A table starts where a row is followed by a separator row.
        if _is_table_row(line) and i + 1 < n and _is_separator_row(lines[i + 1]):
            _flush_prose()
            header, sep = line, lines[i + 1]
            j = i + 2
            rows: list[str] = []
            while j < n and _is_table_row(lines[j]) and not _is_separator_row(lines[j]):
                rows.append(lines[j])
                j += 1
            blocks.append(("table", (pending_label, header, sep, rows)))
            pending_label = None
            i = j
            continue
        if _SHEET_LABEL.match(line):
            # Attach to the immediately following table; otherwise keep as prose.
            _flush_prose()
            pending_label = line
            i += 1
            continue
        if pending_label is not None:
            # Label was not directly followed by a table → treat it as prose after all.
            prose.append(pending_label)
            pending_label = None
        prose.append(line)
        i += 1

    if pending_label is not None:
        prose.append(pending_label)
    _flush_prose()
    return blocks


def chunk_text(
    text: str,
    *,
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> list[str]:
    """Split text into structure-aware overlapping chunks.

    Free text is chunked on sentence/paragraph boundaries (complete thoughts, with character
    overlap between chunks). Markdown tables — as emitted for XLSX sheets and DOCX tables by the
    extractor — are kept intact: never split mid-row, and when a table exceeds ``chunk_size`` it
    is split into header-carrying chunks so column/row coordinates survive indexing.

    Args:
        text: Source text to chunk.
        chunk_size: Target maximum characters per chunk (defaults to
            ``settings.weaviate_chunk_size_chars``).
        overlap: Number of *trailing characters* from the previous (prose) chunk to prepend to
            the next (defaults to ``settings.weaviate_chunk_overlap_chars``).
    """
    size = chunk_size or settings.weaviate_chunk_size_chars
    overlap_chars = overlap or settings.weaviate_chunk_overlap_chars
    if not text or size <= 0:
        return []

    blocks = _segment_blocks(text.split("\n"))
    if not blocks:
        return []

    chunks: list[str] = []
    for kind, payload in blocks:
        if kind == "table":
            label, header, sep, rows = payload  # type: ignore[misc]
            chunks.extend(_chunk_table(label, header, sep, rows, size))
        else:
            chunks.extend(_chunk_prose(payload, size, overlap_chars))  # type: ignore[arg-type]

    return [c for c in chunks if c.strip()]


def truncate_sentence_aware(text: str, limit: int) -> tuple[str, bool]:
    """Truncate ``text`` to <= ``limit`` chars on sentence/paragraph boundaries.

    Returns (text, truncated_flag). Unlike raw ``text[:limit]`` this never cuts a sentence in
    half; when even the first chunk exceeds ``limit`` it falls back to a hard character cut.
    """
    text = text or ""
    if len(text) <= limit:
        return text, False
    out: list[str] = []
    total = 0
    for chunk in chunk_text(text):
        if total + len(chunk) + 2 > limit:
            break
        out.append(chunk)
        total += len(chunk) + 2
    truncated = "\n\n".join(out) if out else text[:limit]
    return truncated, True


def build_context_windows(text: str, limit: int, max_windows: int) -> list[str]:
    """Group sentence-aware chunks into <= max_windows windows of up to ``limit`` chars each.

    The map step of long-document map-reduce (compliance checks, VVT normalization): each window
    respects sentence/table boundaries via :func:`chunk_text`, so no fragment cuts mid-sentence.
    """
    windows: list[str] = []
    current = ""
    for chunk in chunk_text(text or ""):
        if current and len(current) + len(chunk) + 2 > limit:
            windows.append(current)
            current = chunk
            if len(windows) >= max_windows:
                return windows
        else:
            current = f"{current}\n\n{chunk}" if current else chunk
    if current and len(windows) < max_windows:
        windows.append(current)
    return windows[:max_windows]


_ollama_embed_client = None


def _ollama_embed_host() -> str:
    base = (settings.ollama_base_url or "").rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3]
    return base or "http://localhost:11434"


def _get_ollama_embed_client():
    """Return a process-wide shared Ollama client for embeddings."""
    global _ollama_embed_client
    if _ollama_embed_client is None:
        try:
            import ollama
        except ImportError:
            return None
        _ollama_embed_client = ollama.Client(host=_ollama_embed_host())
    return _ollama_embed_client


def _openai_embedding_endpoint() -> tuple[str, dict[str, str]] | None:
    """Return (URL, headers) of the OpenAI-compatible /v1/embeddings API, or None when unset.

    Configured via ``embedding_base_url`` (+ optional ``embedding_api_key``); a missing ``/v1``
    suffix is appended. None means the legacy native Ollama client path is used.
    """
    base = (getattr(settings, "embedding_base_url", "") or "").strip()
    if not base:
        return None
    base = base.rstrip("/")
    if not base.endswith("/v1"):
        base = f"{base}/v1"
    api_key = settings.embedding_api_key.get_secret_value() if hasattr(settings, "embedding_api_key") else ""
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    return f"{base}/embeddings", headers


def _embedding_model_name() -> str:
    """Embedding model: explicit ``embedding_model`` override, else the legacy ``ollama_embedding_model``."""
    return (getattr(settings, "embedding_model", "") or "").strip() or settings.ollama_embedding_model


def _get_embedding_openai_compatible(text: str, url: str, headers: dict[str, str]) -> list[float]:
    """Embed via the OpenAI-compatible /v1/embeddings API (vLLM, llama.cpp, TEI/Infinity, …)."""
    import httpx

    try:
        resp = httpx.post(
            url,
            json={"model": _embedding_model_name(), "input": text},
            headers=headers,
            timeout=httpx.Timeout(settings.llm_request_timeout_seconds or 30.0, connect=10.0),
        )
        resp.raise_for_status()
        items = resp.json().get("data") or []
        if items:
            emb = items[0].get("embedding")
            if emb:
                return list(emb)
    except Exception as e:
        logger.warning("OpenAI-compatible embedding call failed: %s", e)
    return []


def get_embedding(text: str, *, client=None) -> list[float]:
    """Get embedding vector for text. Returns list of floats (empty on failure).

    When ``embedding_base_url`` is configured, the OpenAI-compatible /v1/embeddings API is used
    (works with vLLM, llama.cpp, TEI/Infinity). Otherwise the native Ollama client embeds via
    ``ollama_base_url`` as before. An explicitly passed ``client`` (Ollama) is only honoured on
    the native path.
    """
    endpoint = _openai_embedding_endpoint()
    if endpoint is not None:
        url, headers = endpoint
        return _get_embedding_openai_compatible(text, url, headers)

    try:
        import ollama  # noqa: F401 — availability check
    except ImportError:
        logger.warning("ollama package not available for embeddings")
        return []

    embed_client = client if client is not None else _get_ollama_embed_client()
    if embed_client is None:
        return []

    try:
        response = embed_client.embed(model=settings.ollama_embedding_model, input=text)
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
        from weaviate.auth import AuthApiKey
    except ImportError:
        logger.warning("weaviate-client not installed")
        return None

    try:
        api_key = settings.weaviate_api_key.get_secret_value()
        auth = AuthApiKey(api_key=api_key) if api_key else None
        client = weaviate.connect_to_local(
            host=host,
            port=port,
            grpc_port=50051,
            auth_credentials=auth,
        )
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
    except (ConnectionError, OSError, TimeoutError) as e:
        logger.warning("Weaviate-Netzwerkfehler in index_legal_base: %s", e)
        return False
    except Exception as e:
        logger.exception("Weaviate index_legal_base fehlgeschlagen: %s", e)
        return False
    finally:
        try:
            client.close()
        except Exception as _close_err:
            logger.debug("Weaviate client.close() fehlgeschlagen: %s", _close_err)


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
        except Exception as _close_err:
            logger.debug("Weaviate client.close() fehlgeschlagen: %s", _close_err)


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
        except Exception as _close_err:
            logger.debug("Weaviate client.close() fehlgeschlagen: %s", _close_err)


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

        # Native Ollama client only needed when no OpenAI-compatible endpoint is configured.
        embed_client = None if _openai_embedding_endpoint() is not None else _get_ollama_embed_client()
        for i, chunk in enumerate(chunks):
            vector = get_embedding(chunk, client=embed_client)
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
    except (ConnectionError, OSError, TimeoutError) as e:
        logger.warning("Weaviate-Netzwerkfehler in index_document_chunks: %s", e)
        return False
    except Exception as e:
        logger.exception("Weaviate index_document_chunks fehlgeschlagen: %s", e)
        return False
    finally:
        try:
            client.close()
        except Exception as _close_err:
            logger.debug("Weaviate client.close() fehlgeschlagen: %s", _close_err)


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
        except Exception as _close_err:
            logger.debug("Weaviate client.close() fehlgeschlagen: %s", _close_err)


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
        except Exception as _close_err:
            logger.debug("Weaviate client.close() fehlgeschlagen: %s", _close_err)


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
        except Exception as _close_err:
            logger.debug("Weaviate client.close() fehlgeschlagen: %s", _close_err)


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
        except Exception as _close_err:
            logger.debug("Weaviate client.close() fehlgeschlagen: %s", _close_err)
