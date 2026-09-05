"""Pure tests for case_risk_service (risk-score history, similar-case ranking)."""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

from app.constants import FindingStatus
from app.services.case_risk_service import (
    open_check_names,
    rank_similar_cases,
    risk_score_response,
    score_from_payload,
)
from app.services.risk_config_models import CaseScoreConfig

CFG = CaseScoreConfig(
    severity_weights={"critical": 30, "high": 15, "medium": 5}, max_score=100
)


def test_score_from_payload_weights_and_caps():
    assert score_from_payload(None, CFG) == (0, 0, 0, 0)
    assert score_from_payload(
        {"critical_findings": 1, "high_findings": 2, "medium_findings": 3}, CFG
    ) == (1, 2, 3, 75)
    # Capped at max_score.
    assert score_from_payload({"critical_findings": 10}, CFG)[3] == 100


def _job(created: int, **payload):
    return SimpleNamespace(
        id=uuid.uuid4(),
        created_at=datetime(2026, 1, created, tzinfo=UTC),
        findings_count=sum(payload.values()),
        result_payload=payload or None,
    )


def test_risk_score_history_is_chronological_and_current_is_latest():
    case_id = uuid.uuid4()
    newest_first = [_job(3, high_findings=1), _job(2), _job(1, critical_findings=1)]
    resp = risk_score_response(case_id, newest_first, CFG)
    assert resp.case_id == case_id
    assert [h.score for h in resp.history] == [30, 0, 15]
    assert resp.score == 15
    assert resp.history[0].critical == 1 and resp.history[2].high == 1


def test_risk_score_without_jobs_is_zero():
    resp = risk_score_response(uuid.uuid4(), [], CFG)
    assert resp.score == 0 and resp.history == []


def _finding(check_name: str, status: str = FindingStatus.OPEN):
    return SimpleNamespace(check_name=check_name, status=status)


def _case(title: str, findings):
    return SimpleNamespace(
        id=uuid.uuid4(),
        title=title,
        department="IT",
        case_type="Software",
        status="intake",
        findings=findings,
    )


def test_open_check_names_ignores_resolved():
    case = _case("A", [_finding("x"), _finding("y", FindingStatus.FIXED)])
    assert open_check_names(case) == {"x"}


def test_rank_similar_cases_orders_by_overlap_and_summarises_resolution():
    current = {"a", "b"}
    full_match = _case(
        "Full",
        [_finding("a", FindingStatus.FIXED), _finding("b", FindingStatus.ACCEPTED)],
    )
    half_match = _case("Half", [_finding("a"), _finding("zzz", FindingStatus.FIXED)])
    no_match = _case("None", [_finding("q")])

    ranked = rank_similar_cases(current, [no_match, half_match, full_match], limit=5)

    assert [r.title for r in ranked] == ["Full", "Half"]
    assert ranked[0].overlap_score == 1.0 and ranked[1].overlap_score == 0.5
    assert ranked[0].shared_check_names == ["a", "b"]
    assert ranked[0].resolution_summary == {"fixed": 1, "accepted": 1, "overruled": 0}
    # Unrelated resolved findings of the candidate do not count.
    assert ranked[1].resolution_summary == {"fixed": 0, "accepted": 0, "overruled": 0}


def test_rank_similar_cases_respects_limit_and_empty_input():
    current = {"a"}
    cands = [_case(str(i), [_finding("a")]) for i in range(4)]
    assert len(rank_similar_cases(current, cands, limit=2)) == 2
    assert rank_similar_cases(set(), cands, limit=2) == []
