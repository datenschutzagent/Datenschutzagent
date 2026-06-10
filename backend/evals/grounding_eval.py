"""Offline grounding eval: precision/recall of evidence-grounding detection.

Labelled (quote, should_be_grounded) pairs measure whether ``partition_grounded`` correctly
keeps verbatim quotes and rejects hallucinated ones. No LLM required.
"""
from __future__ import annotations

from dataclasses import dataclass

from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import Evaluator, EvaluatorContext

from app.core.grounding import partition_grounded

# Each case: a source text plus quotes labelled as grounded (True) or hallucinated (False).
_SOURCE = (
    "Die Verarbeitung der Beschäftigtendaten erfolgt zur Lohnabrechnung. "
    "Rechtsgrundlage ist Art. 6 Abs. 1 lit. b und c DSGVO. "
    "Die Speicherdauer der Lohnunterlagen betraegt zehn Jahre gemaess HGB und AO. "
    "Eine Uebermittlung in Drittlaender findet nicht statt."
)

_LABELLED: list[tuple[str, str, dict[str, bool]]] = [
    (
        "grounded_quotes",
        _SOURCE,
        {
            "Die Speicherdauer der Lohnunterlagen betraegt zehn Jahre": True,
            "Eine Uebermittlung in Drittlaender findet nicht statt": True,
            "Daten werden an einen US-Cloud-Anbieter ohne Garantien weitergegeben": False,
            "Es existiert keinerlei Rechtsgrundlage fuer die Verarbeitung": False,
        },
    ),
]


def grounding_task(source: str) -> dict:
    """Partition a fixed quote set for the given source into grounded/ungrounded."""
    quotes = list(_QUOTES_BY_SOURCE[source].keys())
    grounded, ungrounded = partition_grounded(quotes, source)
    return {"grounded": grounded, "ungrounded": ungrounded}


_QUOTES_BY_SOURCE = {source: labels for _, source, labels in _LABELLED}


@dataclass
class GroundingF1(Evaluator):
    """F1 of the 'grounded' decision against the gold labels (treats grounded as the positive class)."""

    def evaluate(self, ctx: EvaluatorContext) -> float:
        labels = _QUOTES_BY_SOURCE[ctx.inputs]
        predicted_grounded = set(ctx.output["grounded"])
        tp = sum(1 for q, g in labels.items() if g and q in predicted_grounded)
        fp = sum(1 for q, g in labels.items() if not g and q in predicted_grounded)
        fn = sum(1 for q, g in labels.items() if g and q not in predicted_grounded)
        precision = tp / (tp + fp) if (tp + fp) else 1.0
        recall = tp / (tp + fn) if (tp + fn) else 1.0
        if precision + recall == 0:
            return 0.0
        return 2 * precision * recall / (precision + recall)


def build_dataset() -> Dataset:
    cases = [Case(name=name, inputs=source, expected_output=None) for name, source, _ in _LABELLED]
    return Dataset(name="evidence_grounding", cases=cases, evaluators=[GroundingF1()])
