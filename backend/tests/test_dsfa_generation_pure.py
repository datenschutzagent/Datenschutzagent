"""Pure tests for the generate_dsfa building blocks (no DB, no LLM).

The LLM step, the confidence policy, the audit emission and the risk matrix are
separate functions since Qualitätsplan Phase 2 R7; each is pinned here.
"""

import uuid
from types import SimpleNamespace

import pytest

from app.services import dsfa_service as ds
from app.services.dsfa_service import _DSFAResult, _DSFARiskLLM
from app.services.risk_config_loader import get_risk_config


def _case():
    return SimpleNamespace(
        id=uuid.uuid4(),
        title="Videoüberwachung Eingang",
        case_type="Softwareeinführung",
        processing_context="Kameras am Empfang",
        special_category_data=True,
        international_transfer=False,
    )


def _policy(**overrides):
    base = {
        "enabled": True,
        "uses_rule_fallback": True,
        "low_threshold": 0.4,
        "emits_audit_event": False,
        "escalation_event_type": "dsfa_fallback",
        "fallback_strategy": "rules",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _llm_result(confidence: float) -> _DSFAResult:
    return _DSFAResult(
        necessity_assessment="n",
        proportionality_assessment="p",
        risks=[_DSFARiskLLM(description="r", likelihood=2, severity=4, mitigation="m")],
        measures=["m1"],
        confidence=confidence,
    )


class _Agent:
    def __init__(self, output=None, exc: Exception | None = None):
        self._output = output
        self._exc = exc

    async def run(self, user_content, output_type=None):
        if self._exc:
            raise self._exc
        return SimpleNamespace(output=self._output)


async def test_llm_result_kept_when_confident(monkeypatch):
    monkeypatch.setattr(ds, "create_agent", lambda *a, **k: _Agent(_llm_result(0.9)))
    data, source, failed = await ds._run_dsfa_llm(_case(), [], "prompt", _policy())
    assert (source, failed) == ("llm", False)
    assert data.confidence == 0.9


async def test_low_confidence_switches_to_rules_hybrid(monkeypatch):
    monkeypatch.setattr(ds, "create_agent", lambda *a, **k: _Agent(_llm_result(0.1)))
    data, source, failed = await ds._run_dsfa_llm(_case(), [], "prompt", _policy())
    assert (source, failed) == ("hybrid", False)
    assert isinstance(data, _DSFAResult)
    assert data.risks, "rule fallback yields at least one risk for Art. 9 data"


async def test_llm_failure_uses_rules_when_policy_allows(monkeypatch):
    monkeypatch.setattr(
        ds, "create_agent", lambda *a, **k: _Agent(exc=RuntimeError("down"))
    )
    data, source, failed = await ds._run_dsfa_llm(_case(), [], "prompt", _policy())
    assert (source, failed) == ("rules", True)
    assert isinstance(data, _DSFAResult)


async def test_llm_failure_raises_without_fallback(monkeypatch):
    monkeypatch.setattr(
        ds, "create_agent", lambda *a, **k: _Agent(exc=RuntimeError("down"))
    )
    with pytest.raises(RuntimeError):
        await ds._run_dsfa_llm(_case(), [], "prompt", _policy(uses_rule_fallback=False))


class _FakeDb:
    def __init__(self):
        self.added = []

    def add(self, obj):
        self.added.append(obj)


def test_audit_emitted_only_for_non_llm_or_policy():
    db = _FakeDb()
    ds._emit_dsfa_audit(
        db, uuid.uuid4(), _policy(), source="llm", llm_failed=False, confidence=0.9
    )
    assert db.added == []

    ds._emit_dsfa_audit(
        db, uuid.uuid4(), _policy(), source="rules", llm_failed=True, confidence=0.5
    )
    ds._emit_dsfa_audit(
        db,
        uuid.uuid4(),
        _policy(emits_audit_event=True),
        source="llm",
        llm_failed=False,
        confidence=0.9,
    )
    assert len(db.added) == 2
    assert db.added[0].event_type == "dsfa_fallback"
    assert db.added[0].payload["source"] == "rules"
    assert db.added[0].payload["llm_failed"] is True


def test_inherent_risks_use_matrix_and_clamp_scores():
    cfg = get_risk_config().dsfa_assessment
    data = _DSFAResult(
        necessity_assessment="n",
        proportionality_assessment="p",
        risks=[_DSFARiskLLM(description="r", likelihood=5, severity=5, mitigation="m")],
        measures=[],
    )
    (risk,) = ds._inherent_risks(data, cfg)
    assert risk["likelihood_score"] == 5 and risk["severity_score"] == 5
    assert risk["likelihood"] == "high" and risk["severity"] == "high"
    assert risk["risk_level"] == cfg.risk_level_for(5, 5)
    assert risk["mitigation"] == "m"


def test_residual_without_mitigations_mirrors_inherent():
    cfg = get_risk_config()
    inherent = [
        {
            "description": "r",
            "likelihood_score": 5,
            "severity_score": 5,
            "likelihood": "high",
            "severity": "high",
            "risk_level": "critical",
            "mitigation": "m",
        }
    ]
    residual = ds._residual_risks(cfg, inherent, applied_ids=[])
    assert residual["residual_overall_level"] == "critical"
    assert residual["applied_effects"] == []
    (risk,) = residual["residual_risks"]
    assert risk["inherent_risk_level"] == "critical"
    assert risk["applied_mitigation_ids"] == []
    assert residual["dpo_consultation_required"] == (
        "critical" in cfg.dsfa_assessment.dpo_consultation_required_when_residual_in
    )
    assert ds._max_risk_level([]) == "low"


def test_findings_info_and_scale_metadata():
    assert ds._format_findings_info([]).startswith("Keine")
    f = SimpleNamespace(severity="high", check_name="Check", description="d" * 300)
    line = ds._format_findings_info([f])
    assert line.startswith("- [HIGH] Check: ")
    assert len(line) < 300

    meta = ds._scale_metadata(get_risk_config().dsfa_assessment)
    assert meta["scale_version"] == ds.DSFA_SCALE_VERSION_NUMERIC
    assert set(meta["scale_labels"]) == {"likelihood", "severity"}
    assert all(isinstance(k, str) for k in meta["scale_labels"]["likelihood"])
