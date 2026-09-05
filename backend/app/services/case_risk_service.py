"""Case risk scoring history and similar-case ranking.

Pure ranking/scoring logic that used to live in the cases route module; the route
loads the rows and delegates here so the formulas are unit-testable without HTTP.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from app.constants import FindingStatus
from app.models.db import CaseModel, RunChecksJobModel
from app.models.schemas import (
    CaseRiskScoreHistoryItem,
    CaseRiskScoreResponse,
    CaseSimilarityResult,
)
from app.services.risk_config_models import CaseScoreConfig


def score_from_payload(
    payload: dict | None, case_score_cfg: CaseScoreConfig
) -> tuple[int, int, int, int]:
    """Extract (critical, high, medium, score) from a run_checks result payload.

    Severity weights and max score come from RiskConfig.case_score so that each
    org-profile can tune the risk model without code changes. Score 0 = no open
    issues, max_score = maximum risk; the formula mirrors the dashboard
    complianceScore.
    """
    if payload:
        critical = int(payload.get("critical_findings", 0))
        high = int(payload.get("high_findings", 0))
        medium = int(payload.get("medium_findings", 0))
    else:
        critical = high = medium = 0
    weights = case_score_cfg.severity_weights
    penalty = (
        critical * weights.get("critical", 0)
        + high * weights.get("high", 0)
        + medium * weights.get("medium", 0)
    )
    return critical, high, medium, min(case_score_cfg.max_score, penalty)


def risk_score_response(
    case_id,
    jobs_newest_first: Sequence[RunChecksJobModel],
    case_score_cfg: CaseScoreConfig,
) -> CaseRiskScoreResponse:
    """Chronological score history from completed run_checks jobs; current = latest."""
    history: list[CaseRiskScoreHistoryItem] = []
    for job in reversed(jobs_newest_first):
        critical, high, medium, score = score_from_payload(
            job.result_payload, case_score_cfg
        )
        history.append(
            CaseRiskScoreHistoryItem(
                job_id=job.id,
                created_at=job.created_at,
                score=score,
                findings_count=job.findings_count,
                critical=critical,
                high=high,
                medium=medium,
            )
        )
    current_score = history[-1].score if history else 0
    return CaseRiskScoreResponse(case_id=case_id, score=current_score, history=history)


def open_check_names(case: CaseModel) -> set[str]:
    return {f.check_name for f in case.findings if f.status == FindingStatus.OPEN}


def rank_similar_cases(
    current_check_names: set[str], candidates: Iterable[CaseModel], limit: int
) -> list[CaseSimilarityResult]:
    """Rank candidates by the share of the current case's open checks they also hit.

    ``resolution_summary`` counts how the candidate resolved the shared checks, so a
    reviewer can see which outcome (fixed/accepted/overruled) was chosen elsewhere.
    """
    if not current_check_names:
        return []
    scored: list[tuple[float, CaseModel]] = []
    for candidate in candidates:
        shared = current_check_names & {f.check_name for f in candidate.findings}
        if shared:
            scored.append((len(shared) / len(current_check_names), candidate))
    scored.sort(key=lambda x: x[0], reverse=True)

    results: list[CaseSimilarityResult] = []
    for overlap_score, cand in scored[:limit]:
        shared_check_names = sorted(
            current_check_names & {f.check_name for f in cand.findings}
        )
        resolution: dict[str, int] = {
            str(FindingStatus.FIXED): 0,
            str(FindingStatus.ACCEPTED): 0,
            str(FindingStatus.OVERRULED): 0,
        }
        for f in cand.findings:
            if f.check_name in shared_check_names and f.status in resolution:
                resolution[f.status] += 1
        results.append(
            CaseSimilarityResult(
                case_id=cand.id,
                title=cand.title,
                department=cand.department,
                case_type=cand.case_type,
                status=cand.status,
                overlap_score=round(overlap_score, 2),
                shared_check_names=shared_check_names,
                resolution_summary=resolution,
            )
        )
    return results
