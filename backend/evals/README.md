# Quality evals

A lightweight [pydantic-evals](https://ai.pydantic.dev/evals/) harness to measure and gate the
quality of document extraction and LLM checks.

## Running

```bash
cd backend
python -m evals.run          # offline evals (no LLM provider needed) — CI-friendly
python -m evals.run --json   # machine-readable summary
python -m evals.run --llm    # also run LLM-backed evals (needs a provider + database)
python -m evals.run --ocr    # also run OCR-accuracy evals (needs a vision model, e.g. Ollama)
```

The runner exits non-zero when any evaluator's mean score falls below its threshold
(see `THRESHOLDS` in `run.py`), so it can gate CI.

## What is measured

| Eval | LLM? | Evaluators |
|------|------|-----------|
| `extraction_eval` | no | `ExpectedTokensPresent` (content survives extraction, incl. a digital PDF sample), `ColumnStructurePreserved` (table/column signature preserved), `MinCharCount` |
| `grounding_eval` | no | `GroundingF1` (precision/recall of grounded-vs-hallucinated quote detection) |
| `llm_eval` | yes (`--llm`) | `CheckEvidenceGrounded` (evidence actually present in the document), `CheckVerdictAccuracy` (right compliant/non-compliant verdict), `CheckSeverityCloseness` (severity near the expected rank), `CheckConfidenceCalibration` (Brier-style confidence calibration) |
| `ocr_eval` | yes (`--ocr`) | `OcrCharAccuracy` (character accuracy `1 - CER` of the vision-OCR path on a rendered scan) |

## Gold data

Sample documents are generated programmatically in `_samples.py` (no binary fixtures), so the
gold set is transparent and diffable. Add new samples there with their expected tokens / column
signatures; add LLM cases in `llm_eval.py`. Tighten thresholds in `run.py` as quality improves.
