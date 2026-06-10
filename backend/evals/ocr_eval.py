"""OCR-accuracy eval (opt-in via `--ocr`): measures how faithfully the vision-OCR path recovers
text from scanned pages.

A known reference text is rendered to an image (no text layer), then run through the real
``extract_text`` image→PDF→Ollama-Vision pipeline. The recovered text is compared to the
reference via the character error rate (CER); the score is the character accuracy ``1 - CER``.

Requires a reachable Ollama vision model (``OLLAMA_OCR_*``), so it is gated behind ``--ocr`` in
``evals.run`` and skipped when no provider is available — analogous to the ``--llm`` evals.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import Evaluator, EvaluatorContext

from app.services.document_processor import extract_text

# Short, OCR-friendly reference texts. Kept compact so a single rendered page suffices and the
# eval stays fast against a local vision model.
_REFERENCES: dict[str, str] = {
    "legal_basis_line": "Rechtsgrundlage: Art. 6 Abs. 1 lit. c DSGVO",
    "retention_line": "Speicherdauer: 10 Jahre gemaess HGB und AO",
    "controller_line": "Verantwortlicher: Muster GmbH, Musterstrasse 1, 60311 Frankfurt",
}


def _render_text_to_png(text: str) -> bytes:
    """Render a single line of text to a PNG image with no text layer (forces the OCR path)."""
    import fitz  # PyMuPDF

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 144), text, fontsize=20)
    # Rasterize the page at OCR resolution, then return a pure image (no selectable text).
    pix = page.get_pixmap(dpi=200, alpha=False)
    png = pix.tobytes("png")
    doc.close()
    return png


def _levenshtein(a: str, b: str) -> int:
    """Edit distance between two strings (iterative two-row DP)."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        cur = [i]
        for j, cb in enumerate(b, start=1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _normalize(text: str) -> str:
    """Collapse whitespace so OCR line-wrapping/spacing differences do not dominate the CER."""
    return " ".join((text or "").split())


def ocr_task(name: str) -> dict:
    png = _render_text_to_png(_REFERENCES[name])
    result = extract_text("scan.png", png)
    return {"text": result.text, "reference": _REFERENCES[name]}


@dataclass
class OcrCharAccuracy(Evaluator):
    """Character accuracy ``1 - CER`` of the OCR'd text against the reference (1.0 = perfect)."""

    def evaluate(self, ctx: EvaluatorContext) -> float:
        ref = _normalize(ctx.output["reference"])
        hyp = _normalize(ctx.output["text"])
        if not ref:
            return 1.0
        distance = _levenshtein(ref, hyp)
        return max(0.0, 1.0 - distance / len(ref))


def build_dataset() -> Dataset:
    cases = [Case(name=n, inputs=n, expected_output=None) for n in _REFERENCES]
    return Dataset(name="ocr_accuracy", cases=cases, evaluators=[OcrCharAccuracy()])
