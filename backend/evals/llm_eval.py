"""LLM-backed evals (opt-in via `--llm`): end-to-end check quality against the live provider.

Requires a reachable LLM provider (LLM_PROVIDER/OLLAMA_BASE_URL/…) and a database (the check
runner loads prompt templates). Scores whether the model's returned evidence is actually
grounded in the document — the key anti-hallucination signal for the whole pipeline.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import Evaluator, EvaluatorContext

from app.core.grounding import grounding_ratio
from app.services.check_runner import run_check

_CASES = [
    {
        "name": "missing_retention",
        "doc": (
            "Datenschutzhinweise zur Lohnabrechnung. Verantwortlicher: Muster GmbH. "
            "Zweck: Lohn- und Gehaltsabrechnung. Rechtsgrundlage: Art. 6 Abs. 1 lit. c DSGVO."
        ),
        "requirement": "Das Dokument muss eine konkrete Speicherdauer/Löschfrist für die Daten angeben.",
    },
    {
        "name": "has_legal_basis",
        "doc": (
            "Verarbeitungstätigkeit Bewerbermanagement. Rechtsgrundlage: Art. 6 Abs. 1 lit. b DSGVO. "
            "Speicherdauer: 6 Monate nach Abschluss des Verfahrens."
        ),
        "requirement": "Das Dokument muss eine Rechtsgrundlage nach Art. 6 DSGVO nennen.",
    },
]
_BY_NAME = {c["name"]: c for c in _CASES}


def llm_task(name: str) -> dict:
    case = _BY_NAME[name]
    result = asyncio.run(run_check(case["doc"], case["requirement"], language="de"))
    return {
        "is_compliant": result.is_compliant,
        "evidence": result.evidence,
        "confidence": result.confidence,
        "doc": case["doc"],
    }


@dataclass
class CheckEvidenceGrounded(Evaluator):
    """Fraction of the model's evidence quotes that are grounded in the source document."""

    def evaluate(self, ctx: EvaluatorContext) -> float:
        return grounding_ratio(ctx.output["evidence"], ctx.output["doc"])


def build_dataset() -> Dataset:
    cases = [Case(name=c["name"], inputs=c["name"], expected_output=None) for c in _CASES]
    return Dataset(name="llm_check_quality", cases=cases, evaluators=[CheckEvidenceGrounded()])
