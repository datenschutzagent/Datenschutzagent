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
    perfect = evaluator.evaluate(
        SimpleNamespace(output={"reference": ref, "text": ref})
    )
    empty = evaluator.evaluate(SimpleNamespace(output={"reference": ref, "text": ""}))
    assert perfect == 1.0
    assert empty == 0.0


# ---------------------------------------------------------------------------
# Runner (evals/run.py): thresholds, --strict, --out
# ---------------------------------------------------------------------------


def test_every_threshold_names_an_existing_evaluator():
    """A threshold for an evaluator that no longer exists gates nothing (dead entry)."""
    from evals import llm_eval, run

    evaluators = {
        cls.__name__
        for mod in (extraction_eval, grounding_eval, llm_eval, ocr_eval)
        for cls in vars(mod).values()
        if isinstance(cls, type) and cls.__module__ == mod.__name__
    }
    missing = set(run.THRESHOLDS) - evaluators
    assert not missing, f"thresholds without evaluator class: {sorted(missing)}"


def test_optional_suite_failure_warns_unless_strict(monkeypatch):
    from evals import run

    def broken_loader():
        raise RuntimeError("no provider configured")

    monkeypatch.setattr(run, "_load_llm", broken_loader)

    lenient = run.evaluate(llm=True, strict=False, show_table=False)
    assert lenient["skipped"] == {"llm": "RuntimeError: no provider configured"}
    assert lenient["failures"] == {}
    assert lenient["passed"] is True

    strict = run.evaluate(llm=True, strict=True, show_table=False)
    assert strict["skipped"] == lenient["skipped"]
    assert strict["passed"] is False


def test_main_writes_summary_file_and_exit_code(monkeypatch, tmp_path):
    from evals import run

    out = tmp_path / "nested" / "evals.json"
    monkeypatch.setattr(
        "sys.argv", ["evals.run", "--json", "--out", str(out), "--llm", "--strict"]
    )
    monkeypatch.setattr(
        run, "_load_llm", lambda: (_ for _ in ()).throw(RuntimeError("offline"))
    )
    assert run.main() == 1  # strict + skipped suite
    import json

    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["passed"] is False
    assert written["skipped"] == {"llm": "RuntimeError: offline"}
    assert written["means"]["GroundingF1"] == 1.0
    assert written["thresholds"]["GroundingF1"] == 0.9

    monkeypatch.setattr("sys.argv", ["evals.run", "--json"])
    assert run.main() == 0
