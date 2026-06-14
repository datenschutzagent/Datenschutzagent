"""Vision-LLM OCR for PDF pages (scanned or image-heavy).

Provides the low-level OCR pipeline: page rendering, model resolution and
concurrent per-page extraction. No dependency on pdf_extractor or document_processor.
"""

import base64
import logging
import time
from concurrent.futures import ThreadPoolExecutor

import fitz  # PyMuPDF
import httpx

from app.config import settings

logger = logging.getLogger(__name__)

OCR_PROMPT = (
    "Extrahiere den gesamten Text aus diesem Bild als Markdown. "
    "Erhalte dabei Tabellen als Markdown-Tabellen und die Lesereihenfolge. "
    "Gib nur den extrahierten Inhalt zurück, keine Erklärungen oder Überschriften."
)


def _pdf_page_to_png_bytes(content: bytes, page_index: int, dpi: int = 150) -> bytes:
    """Render a single PDF page to PNG bytes."""
    with fitz.open(stream=content, filetype="pdf") as doc:
        page = doc[page_index]
        pix = page.get_pixmap(dpi=dpi, alpha=False)
        return pix.tobytes("png")


def _ocr_chat_endpoint() -> tuple[str, dict[str, str]]:
    """Resolve the OpenAI-compatible chat-completions URL and auth headers for OCR.

    Resolution order for the base URL: explicit ``ocr_base_url`` override → the custom server
    when ``llm_provider=openai_compatible`` → the Ollama server (default).
    """
    base = (getattr(settings, "ocr_base_url", "") or "").strip()
    api_key = (
        settings.ocr_api_key.get_secret_value()
        if hasattr(settings, "ocr_api_key")
        else ""
    )
    if not base:
        if (
            settings.llm_provider.lower() == "openai_compatible"
            and (settings.llm_base_url or "").strip()
        ):
            base = settings.llm_base_url
            api_key = api_key or settings.llm_api_key.get_secret_value()
        else:
            base = settings.ollama_base_url or ""
    base = base.rstrip("/")
    if not base.endswith("/v1"):
        base = f"{base}/v1"
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    return f"{base}/chat/completions", headers


def _ocr_model_name() -> str:
    """OCR vision model: explicit ``ocr_model`` override, else the legacy ``ollama_ocr_model``."""
    return (
        getattr(settings, "ocr_model", "") or ""
    ).strip() or settings.ollama_ocr_model


def _ocr_pages(content: bytes, page_indices: list[int]) -> dict[int, str]:
    """OCR the given PDF pages concurrently via a vision LLM. Returns {page_index: text}.

    Each page is retried up to ``ocr_retry_attempts`` times on a transient error or a
    near-empty response with DPI escalation across attempts.
    """
    chat_url, headers = _ocr_chat_endpoint()
    model = _ocr_model_name()
    timeout = httpx.Timeout(settings.ollama_timeout_seconds, connect=10.0)
    base_dpi = getattr(settings, "ocr_dpi", 300)
    max_dpi = max(base_dpi, getattr(settings, "ocr_max_dpi", 400))
    min_chars = getattr(settings, "ocr_min_chars_per_page", 50)
    concurrency = max(1, getattr(settings, "ocr_concurrency", 4))
    attempts = max(1, getattr(settings, "ocr_retry_attempts", 2))

    def _dpi_for_attempt(attempt: int) -> int:
        if attempts <= 1 or base_dpi >= max_dpi:
            return base_dpi
        step = (max_dpi - base_dpi) / (attempts - 1)
        return int(round(base_dpi + step * (attempt - 1)))

    def _ocr_one(i: int) -> tuple[int, str]:
        best = ""
        for attempt in range(1, attempts + 1):
            dpi = _dpi_for_attempt(attempt)
            try:
                png_bytes = _pdf_page_to_png_bytes(content, i, dpi=dpi)
                image_uri = (
                    f"data:image/png;base64,{base64.b64encode(png_bytes).decode()}"
                )
                payload = {
                    "model": model,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": OCR_PROMPT},
                                {"type": "image_url", "image_url": {"url": image_uri}},
                            ],
                        }
                    ],
                    "stream": False,
                    "temperature": 0,
                }
                resp = httpx.post(
                    chat_url, json=payload, headers=headers, timeout=timeout
                )
                resp.raise_for_status()
                data = resp.json()
                choices = data.get("choices") or []
                message = (choices[0].get("message") or {}) if choices else {}
                text = (message.get("content") or "").strip()
                if len(text) > len(best):
                    best = text
                if len(text.strip()) >= min_chars:
                    return i, text
                logger.warning(
                    "Vision OCR recovered little text for page %s at %d DPI (attempt %d/%d)",
                    i + 1,
                    dpi,
                    attempt,
                    attempts,
                )
            except Exception as exc:
                logger.warning(
                    "Vision OCR failed for page %s (attempt %d/%d): %s",
                    i + 1,
                    attempt,
                    attempts,
                    exc,
                )
            if attempt < attempts:
                time.sleep(attempt)
        return i, best

    results: dict[int, str] = {}
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        for i, text in pool.map(_ocr_one, page_indices):
            results[i] = text
    return results
