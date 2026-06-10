"""Offline extraction-quality eval: structure/table/column preservation.

Runs sample documents through the real ``extract_text`` and scores how much of the expected
content and structure survived. No LLM required.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import Evaluator, EvaluatorContext

from app.services.document_processor import extract_text
from evals._samples import SAMPLES


def extraction_task(sample_key: str) -> dict:
    """Build the sample document and extract it, returning text + quality signals."""
    sample = SAMPLES[sample_key]
    result = extract_text(sample.filename, sample.builder())
    return {
        "text": result.text,
        "method": result.extraction_method,
        "char_count": result.char_count or len(result.text or ""),
    }


@dataclass
class ExpectedTokensPresent(Evaluator):
    """Fraction of expected tokens present verbatim in the extracted text (0..1)."""

    def evaluate(self, ctx: EvaluatorContext) -> float:
        tokens = SAMPLES[ctx.inputs].expected_tokens
        if not tokens:
            return 1.0
        text = ctx.output["text"]
        return sum(1 for t in tokens if t in text) / len(tokens)


@dataclass
class ColumnStructurePreserved(Evaluator):
    """1.0 if the expected column/header signature survived extraction, else 0.0."""

    def evaluate(self, ctx: EvaluatorContext) -> float:
        header = SAMPLES[ctx.inputs].column_header
        if not header:
            return 1.0
        return 1.0 if header in ctx.output["text"] else 0.0


@dataclass
class MinCharCount(Evaluator):
    """1.0 if the extracted text meets the sample's minimum length, else 0.0."""

    def evaluate(self, ctx: EvaluatorContext) -> float:
        return 1.0 if ctx.output["char_count"] >= SAMPLES[ctx.inputs].min_chars else 0.0


def build_dataset() -> Dataset:
    cases = [
        Case(name=s.key, inputs=s.key, expected_output=None) for s in SAMPLES.values()
    ]
    return Dataset(
        name="extraction_quality",
        cases=cases,
        evaluators=[
            ExpectedTokensPresent(),
            ColumnStructurePreserved(),
            MinCharCount(),
        ],
    )
