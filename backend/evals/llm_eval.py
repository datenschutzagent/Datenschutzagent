"""LLM-backed evals (opt-in via `--llm`): end-to-end check quality against the live provider.

Requires a reachable LLM provider (LLM_PROVIDER/OLLAMA_BASE_URL/…) and a database (the check
runner loads prompt templates). Beyond the anti-hallucination signal (evidence grounding) this
also measures whether the model reaches the *right* verdict and severity on labelled gold cases,
and whether its self-assessed confidence is calibrated (Brier-style) — the signals that tell us
whether a model/prompt change actually improves answer quality, not just format.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import Evaluator, EvaluatorContext

from app.core.grounding import grounding_ratio
from app.services.check_runner import _SEVERITY_RANK, run_check

# Gold cases: each carries the expected verdict and (for non-compliant cases) the expected
# severity, so a model/prompt regression in *judgement* — not just format — is caught.
_CASES = [
    {
        "name": "missing_retention",
        "doc": (
            "Datenschutzhinweise zur Lohnabrechnung. Verantwortlicher: Muster GmbH. "
            "Zweck: Lohn- und Gehaltsabrechnung. Rechtsgrundlage: Art. 6 Abs. 1 lit. c DSGVO."
        ),
        "requirement": "Das Dokument muss eine konkrete Speicherdauer/Löschfrist für die Daten angeben.",
        "expected_compliant": False,
        "expected_severity": "high",
    },
    {
        "name": "has_legal_basis",
        "doc": (
            "Verarbeitungstätigkeit Bewerbermanagement. Rechtsgrundlage: Art. 6 Abs. 1 lit. b DSGVO. "
            "Speicherdauer: 6 Monate nach Abschluss des Verfahrens."
        ),
        "requirement": "Das Dokument muss eine Rechtsgrundlage nach Art. 6 DSGVO nennen.",
        "expected_compliant": True,
        "expected_severity": "info",
    },
    {
        "name": "retention_present",
        "doc": (
            "Datenschutzhinweise zur Lohnabrechnung. Verantwortlicher: Muster GmbH. "
            "Zweck: Lohn- und Gehaltsabrechnung. Rechtsgrundlage: Art. 6 Abs. 1 lit. c DSGVO. "
            "Speicherdauer: 10 Jahre gemäß HGB und AO."
        ),
        "requirement": "Das Dokument muss eine konkrete Speicherdauer/Löschfrist für die Daten angeben.",
        "expected_compliant": True,
        "expected_severity": "info",
    },
    {
        "name": "missing_legal_basis",
        "doc": (
            "Verarbeitungstätigkeit Newsletter-Versand. Zweck: Direktwerbung an alle Kunden. "
            "Es werden Name und E-Mail-Adresse gespeichert. Eine Rechtsgrundlage wird nicht genannt."
        ),
        "requirement": "Das Dokument muss eine Rechtsgrundlage nach Art. 6 DSGVO nennen.",
        "expected_compliant": False,
        "expected_severity": "high",
    },
]
_BY_NAME = {c["name"]: c for c in _CASES}


def llm_task(name: str) -> dict:
    case = _BY_NAME[name]
    result = asyncio.run(run_check(case["doc"], case["requirement"], language="de"))
    return {
        "is_compliant": result.is_compliant,
        "severity": result.severity,
        "evidence": result.evidence,
        "confidence": result.confidence,
        "doc": case["doc"],
    }


@dataclass
class CheckEvidenceGrounded(Evaluator):
    """Fraction of the model's evidence quotes that are grounded in the source document."""

    def evaluate(self, ctx: EvaluatorContext) -> float:
        return grounding_ratio(ctx.output["evidence"], ctx.output["doc"])


@dataclass
class CheckVerdictAccuracy(Evaluator):
    """1.0 if the model's is_compliant verdict matches the gold label, else 0.0."""

    def evaluate(self, ctx: EvaluatorContext) -> float:
        expected = _BY_NAME[ctx.inputs]["expected_compliant"]
        return 1.0 if bool(ctx.output["is_compliant"]) == bool(expected) else 0.0


@dataclass
class CheckSeverityCloseness(Evaluator):
    """How close the reported severity is to the expected one (1.0 = exact), on the rank scale.

    Severity only matters for non-compliant cases; compliant gold cases score 1.0 when the model
    correctly returns the verdict (severity is then expected to be 'info').
    """

    def evaluate(self, ctx: EvaluatorContext) -> float:
        case = _BY_NAME[ctx.inputs]
        expected_rank = _SEVERITY_RANK.get(case["expected_severity"], 0)
        actual_rank = _SEVERITY_RANK.get(ctx.output["severity"], 0)
        max_dist = max(_SEVERITY_RANK.values()) - min(_SEVERITY_RANK.values())
        return 1.0 - abs(expected_rank - actual_rank) / max_dist


@dataclass
class CheckConfidenceCalibration(Evaluator):
    """Brier-style calibration: 1 - (confidence - correct)^2, where correct ∈ {0,1}.

    Rewards high confidence on correct verdicts and low confidence on wrong ones; a model that is
    confidently wrong scores near 0. Averaged across cases this is a calibration signal (1.0 = perfect).
    """

    def evaluate(self, ctx: EvaluatorContext) -> float:
        expected = _BY_NAME[ctx.inputs]["expected_compliant"]
        correct = 1.0 if bool(ctx.output["is_compliant"]) == bool(expected) else 0.0
        confidence = float(ctx.output["confidence"])
        return 1.0 - (confidence - correct) ** 2


def build_dataset() -> Dataset:
    cases = [
        Case(name=c["name"], inputs=c["name"], expected_output=None) for c in _CASES
    ]
    return Dataset(
        name="llm_check_quality",
        cases=cases,
        evaluators=[
            CheckEvidenceGrounded(),
            CheckVerdictAccuracy(),
            CheckSeverityCloseness(),
            CheckConfidenceCalibration(),
        ],
    )
