"""Smoke tests for the offline eval harness (no LLM, no DB)."""
from types import SimpleNamespace

from evals import extraction_eval, grounding_eval, ocr_eval
from evals.run import _evaluator_means


def test_extraction_eval_perfect_on_gold_samples():
    ds = extraction_eval.build_dataset()
    report = ds.evaluate_sync(extraction_eval.extraction_task, progress=False)
    means = _evaluator_means(report)
    assert means["ExpectedTokensPresent"] == 1.0
    assert means["ColumnStructurePreserved"] == 1.0
    assert means["MinCharCount"] == 1.0


def test_extraction_eval_covers_digital_pdf_sample():
    # The PDF path is the most common upload format; the gold set must exercise it offline.
    assert "digital_pdf" in extraction_eval.SAMPLES
    out = extraction_eval.extraction_task("digital_pdf")
    assert "Muster GmbH" in out["text"]
    assert "Art. 6 Abs. 1 lit. c DSGVO" in out["text"]


def test_extraction_eval_covers_pptx_and_csv_samples():
    # PPTX (slide anchors, table, speaker notes) and CSV (Zeile/column-letter table shape).
    assert "tom_pptx" in extraction_eval.SAMPLES
    out = extraction_eval.extraction_task("tom_pptx")
    assert "[Folie 2]" in out["text"]
    assert "AVV mit Hosting-Anbieter" in out["text"]
    assert "vvt_csv" in extraction_eval.SAMPLES
    out = extraction_eval.extraction_task("vvt_csv")
    assert "| Zeile | A | B | C |" in out["text"]
    assert "Lohnabrechnung" in out["text"]


def test_grounding_eval_perfect_on_labelled_quotes():
    ds = grounding_eval.build_dataset()
    report = ds.evaluate_sync(grounding_eval.grounding_task, progress=False)
    means = _evaluator_means(report)
    assert means["GroundingF1"] == 1.0


def test_ocr_levenshtein_and_normalize():
    assert ocr_eval._levenshtein("abc", "abc") == 0
    assert ocr_eval._levenshtein("abc", "abd") == 1
    assert ocr_eval._levenshtein("", "abc") == 3
    # Whitespace differences must not inflate the CER.
    assert ocr_eval._normalize("Art. 6   Abs.\n1") == "Art. 6 Abs. 1"


def test_ocr_char_accuracy_scoring():
    evaluator = ocr_eval.OcrCharAccuracy()
    ref = "Rechtsgrundlage: Art. 6 DSGVO"
    # Perfect recovery → accuracy 1.0; empty recovery → 0.0.
    perfect = evaluator.evaluate(SimpleNamespace(output={"reference": ref, "text": ref}))
    empty = evaluator.evaluate(SimpleNamespace(output={"reference": ref, "text": ""}))
    assert perfect == 1.0
    assert empty == 0.0
