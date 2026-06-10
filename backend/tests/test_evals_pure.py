"""Smoke tests for the offline eval harness (no LLM, no DB)."""
from evals import extraction_eval, grounding_eval
from evals.run import _evaluator_means


def test_extraction_eval_perfect_on_gold_samples():
    ds = extraction_eval.build_dataset()
    report = ds.evaluate_sync(extraction_eval.extraction_task, progress=False)
    means = _evaluator_means(report)
    assert means["ExpectedTokensPresent"] == 1.0
    assert means["ColumnStructurePreserved"] == 1.0
    assert means["MinCharCount"] == 1.0


def test_grounding_eval_perfect_on_labelled_quotes():
    ds = grounding_eval.build_dataset()
    report = ds.evaluate_sync(grounding_eval.grounding_task, progress=False)
    means = _evaluator_means(report)
    assert means["GroundingF1"] == 1.0
