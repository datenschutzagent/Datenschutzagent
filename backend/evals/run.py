"""Eval runner with threshold gating (CI-friendly).

Usage:
    python -m evals.run            # offline evals only (no LLM)
    python -m evals.run --llm      # additionally run LLM-backed evals (needs provider + DB)
    python -m evals.run --json     # machine-readable summary on stdout

Exits non-zero when any evaluator's mean score falls below its threshold, so it can gate CI.
"""

from __future__ import annotations

import argparse
import json
import sys

from pydantic_evals import Dataset

from evals import extraction_eval, grounding_eval

# Per-evaluator minimum mean score required to pass. Tightened over time as quality improves.
THRESHOLDS: dict[str, float] = {
    "ExpectedTokensPresent": 0.95,
    "ColumnStructurePreserved": 1.0,
    "MinCharCount": 1.0,
    "GroundingF1": 0.9,
    "VVTFieldRecall": 0.6,  # LLM-backed; looser because it depends on the model
    "CheckEvidenceGrounded": 0.8,
    "CheckVerdictAccuracy": 0.7,  # LLM-backed; right compliant/non-compliant verdict
    "CheckSeverityCloseness": 0.6,  # LLM-backed; severity near the expected rank
    "CheckConfidenceCalibration": 0.5,  # LLM-backed; Brier-style, looser by nature
    "OcrCharAccuracy": 0.8,  # OCR-backed (needs a vision model; --ocr)
}


def _evaluator_means(report) -> dict[str, float]:
    """Mean score per evaluator across all cases in a report."""
    sums: dict[str, float] = {}
    counts: dict[str, int] = {}
    for case in report.cases:
        for name, result in case.scores.items():
            sums[name] = sums.get(name, 0.0) + float(result.value)
            counts[name] = counts.get(name, 0) + 1
    return {name: sums[name] / counts[name] for name in sums}


def _run(dataset: Dataset, task, *, show_table: bool = True) -> dict[str, float]:
    report = dataset.evaluate_sync(task, progress=False)
    if show_table:
        report.print(include_input=False, include_output=False)
    return _evaluator_means(report)


def main() -> int:
    parser = argparse.ArgumentParser(description="Datenschutzagent quality evals")
    parser.add_argument(
        "--llm",
        action="store_true",
        help="also run LLM-backed evals (needs provider + DB)",
    )
    parser.add_argument(
        "--ocr",
        action="store_true",
        help="also run OCR-accuracy evals (needs a vision model)",
    )
    parser.add_argument(
        "--json", action="store_true", help="print a machine-readable summary"
    )
    args = parser.parse_args()

    show_table = not args.json
    means: dict[str, float] = {}
    means.update(
        _run(
            extraction_eval.build_dataset(),
            extraction_eval.extraction_task,
            show_table=show_table,
        )
    )
    means.update(
        _run(
            grounding_eval.build_dataset(),
            grounding_eval.grounding_task,
            show_table=show_table,
        )
    )

    if args.llm:
        try:
            from evals import llm_eval

            means.update(
                _run(llm_eval.build_dataset(), llm_eval.llm_task, show_table=show_table)
            )
        except Exception as exc:  # pragma: no cover - environment-dependent
            print(f"[warn] LLM evals skipped: {exc}", file=sys.stderr)

    if args.ocr:
        try:
            from evals import ocr_eval

            means.update(
                _run(ocr_eval.build_dataset(), ocr_eval.ocr_task, show_table=show_table)
            )
        except Exception as exc:  # pragma: no cover - environment-dependent
            print(f"[warn] OCR evals skipped: {exc}", file=sys.stderr)

    # Gate on thresholds.
    failures = {
        name: (score, THRESHOLDS[name])
        for name, score in means.items()
        if name in THRESHOLDS and score < THRESHOLDS[name]
    }

    if args.json:
        print(json.dumps({"means": means, "failures": failures}, indent=2))
    else:
        print("\n=== Eval summary (mean score per evaluator) ===")
        for name, score in sorted(means.items()):
            threshold = THRESHOLDS.get(name)
            flag = (
                ""
                if threshold is None
                else (" OK" if score >= threshold else f" FAIL (<{threshold})")
            )
            print(f"  {name:28s} {score:.3f}{flag}")

    if failures:
        print(f"\n{len(failures)} evaluator(s) below threshold.", file=sys.stderr)
        return 1
    print("\nAll evaluators passed their thresholds.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
