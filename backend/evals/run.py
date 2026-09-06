"""Eval runner with threshold gating (CI-friendly).

Usage:
    python -m evals.run                  # offline evals only (no LLM)
    python -m evals.run --llm            # additionally run LLM-backed evals (needs provider + DB)
    python -m evals.run --ocr            # additionally run OCR evals (needs a vision model)
    python -m evals.run --strict         # a suite that cannot run counts as a failure
    python -m evals.run --out evals.json # also write the summary to a file
    python -m evals.run --json           # machine-readable summary on stdout

Exits non-zero when any evaluator's mean score falls below its threshold, so it can gate CI.
Without ``--strict`` an optional suite (``--llm``/``--ocr``) that fails to run – no provider,
no database – only warns; the nightly workflow passes ``--strict`` so a silently skipped
suite cannot look green.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pydantic_evals import Dataset

from evals import extraction_eval, grounding_eval

# Per-evaluator minimum mean score required to pass. Tightened over time as quality improves.
# Every key must correspond to an evaluator class in evals/*.py (checked by tests/test_evals_pure.py).
THRESHOLDS: dict[str, float] = {
    "ExpectedTokensPresent": 0.95,
    "ColumnStructurePreserved": 1.0,
    "MinCharCount": 1.0,
    "GroundingF1": 0.9,
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


def _run_optional(
    name: str, load, *, show_table: bool, strict: bool
) -> tuple[dict[str, float], str | None]:
    """Run an environment-dependent suite.

    Returns the evaluator means and, when the suite could not run, the reason.
    Import and execution errors are environment problems (missing provider, DB,
    model); they are reported instead of raised so the offline suites still gate.
    """
    try:
        dataset, task = load()
        return _run(dataset, task, show_table=show_table), None
    except Exception as exc:  # any failure means "suite unavailable"
        reason = f"{type(exc).__name__}: {exc}"
        level = "error" if strict else "warn"
        print(f"[{level}] {name} evals skipped: {reason}", file=sys.stderr)
        return {}, reason


def _load_llm():
    from evals import llm_eval

    return llm_eval.build_dataset(), llm_eval.llm_task


def _load_ocr():
    from evals import ocr_eval

    return ocr_eval.build_dataset(), ocr_eval.ocr_task


def evaluate(
    *, llm: bool = False, ocr: bool = False, strict: bool = False, show_table: bool
) -> dict:
    """Run the selected suites and build the summary dict (also used by tests)."""
    means: dict[str, float] = {}
    skipped: dict[str, str] = {}
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
    for enabled, name, load in ((llm, "llm", _load_llm), (ocr, "ocr", _load_ocr)):
        if not enabled:
            continue
        suite_means, reason = _run_optional(
            name, load, show_table=show_table, strict=strict
        )
        means.update(suite_means)
        if reason is not None:
            skipped[name] = reason

    failures = {
        name: {"score": score, "threshold": THRESHOLDS[name]}
        for name, score in means.items()
        if name in THRESHOLDS and score < THRESHOLDS[name]
    }
    passed = not failures and not (strict and skipped)
    return {
        "means": means,
        "thresholds": {k: THRESHOLDS[k] for k in means if k in THRESHOLDS},
        "failures": failures,
        "skipped": skipped,
        "strict": strict,
        "passed": passed,
    }


def _print_summary(summary: dict) -> None:
    print("\n=== Eval summary (mean score per evaluator) ===")
    for name, score in sorted(summary["means"].items()):
        threshold = THRESHOLDS.get(name)
        flag = (
            ""
            if threshold is None
            else (" OK" if score >= threshold else f" FAIL (<{threshold})")
        )
        print(f"  {name:28s} {score:.3f}{flag}")
    for name, reason in summary["skipped"].items():
        print(f"  [{name} suite skipped] {reason}")


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
        "--strict",
        action="store_true",
        help="fail when a requested optional suite (--llm/--ocr) cannot run",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        metavar="FILE",
        help="write the JSON summary to FILE (in addition to the console output)",
    )
    parser.add_argument(
        "--json", action="store_true", help="print a machine-readable summary"
    )
    args = parser.parse_args()

    summary = evaluate(
        llm=args.llm, ocr=args.ocr, strict=args.strict, show_table=not args.json
    )

    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        _print_summary(summary)

    failures = summary["failures"]
    if failures:
        print(f"\n{len(failures)} evaluator(s) below threshold.", file=sys.stderr)
        return 1
    if args.strict and summary["skipped"]:
        print(
            f"\n{len(summary['skipped'])} requested suite(s) could not run (--strict).",
            file=sys.stderr,
        )
        return 1
    print("\nAll evaluators passed their thresholds.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
