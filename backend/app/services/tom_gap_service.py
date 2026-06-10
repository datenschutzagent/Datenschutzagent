"""TOM-Gap-Analyse: vergleicht TOM-Inventar gegen Baseline aus risk_config.

Ein Gap entsteht, wenn keine TOM in der geforderten Kategorie den Status
``implemented`` trägt — oder, falls Keywords definiert sind, wenn keine
implementierte TOM einen der Keywords im Titel führt. Das Ergebnis treibt
den TOM-Gap-Tab im Frontend und fließt in Stufe-5-Reports ein.

Reine Logik vom DB-Lookup getrennt: ``analyse_gaps`` ist pure, ``load_*``
und der Endpoint-Wrapper liegen in der API-Schicht.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass

from app.services.risk_config_loader import TomBaselineConfig, TomBaselineRequirement

logger = logging.getLogger(__name__)


# Severity → numeric rank (for sorting and aggregation).
_SEVERITY_RANK = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}


@dataclass(frozen=True)
class _TOMRow:
    """Minimal view of a TOM row for gap evaluation — keeps the engine pure."""

    title: str
    category: str
    implementation_status: str


def _row_from_tom(tom) -> _TOMRow:
    """Map an ORM TOMModel (or any duck-typed object) to a pure row."""
    return _TOMRow(
        title=str(getattr(tom, "title", "") or ""),
        category=str(getattr(tom, "category", "") or ""),
        implementation_status=str(getattr(tom, "implementation_status", "") or ""),
    )


def _meets_requirement(
    req: TomBaselineRequirement, toms: Iterable[_TOMRow]
) -> tuple[bool, list[str]]:
    """Return (met, matching TOM titles) for a single requirement.

    A requirement is met when AT LEAST ONE TOM:
      - has the requested category, AND
      - has implementation_status == 'implemented', AND
      - if keywords_title is non-empty: title contains one of those substrings (case-insensitive).
    """
    keywords_lc = [kw.lower() for kw in req.keywords_title]
    matches: list[str] = []
    for row in toms:
        if row.category != req.category:
            continue
        if row.implementation_status != "implemented":
            continue
        if keywords_lc:
            title_lc = row.title.lower()
            if not any(kw in title_lc for kw in keywords_lc):
                continue
        matches.append(row.title)
    return (len(matches) > 0, matches)


def analyse_gaps(
    baseline: TomBaselineConfig,
    toms: Iterable,
) -> dict:
    """Compute gaps. Pure: takes the baseline and a list of TOM rows; no DB.

    Returns:
        {
            "enabled": bool,                # baseline enabled?
            "requirements": [
                {
                    "id": "...",
                    "label": "...",
                    "description": "...",
                    "category": "...",
                    "severity": "...",
                    "met": bool,
                    "matching_toms": ["..."],  # TOM titles that satisfied it
                },
                ...
            ],
            "summary": {
                "total": int,
                "met": int,
                "missing": int,
                "coverage_pct": float,
                "missing_by_severity": {"high": 2, ...},
            },
        }
    """
    if not baseline.enabled or not baseline.requirements:
        return {
            "enabled": baseline.enabled,
            "requirements": [],
            "summary": {
                "total": 0,
                "met": 0,
                "missing": 0,
                "coverage_pct": 100.0,
                "missing_by_severity": {},
            },
        }

    rows = [_row_from_tom(t) for t in toms]
    req_results: list[dict] = []
    met = 0
    missing_by_sev: dict[str, int] = {}
    for req in baseline.requirements:
        is_met, matching = _meets_requirement(req, rows)
        if is_met:
            met += 1
        else:
            missing_by_sev[req.severity] = missing_by_sev.get(req.severity, 0) + 1
        req_results.append(
            {
                "id": req.id,
                "label": req.label,
                "description": req.description,
                "category": req.category,
                "severity": req.severity,
                "met": is_met,
                "matching_toms": matching,
            }
        )

    # Sort gaps first (so users see what's missing), then by severity rank desc.
    req_results.sort(
        key=lambda r: (r["met"], -_SEVERITY_RANK.get(r["severity"], 0), r["id"])
    )

    total = len(req_results)
    missing = total - met
    coverage_pct = round(met / total * 100.0, 1) if total else 100.0

    return {
        "enabled": True,
        "requirements": req_results,
        "summary": {
            "total": total,
            "met": met,
            "missing": missing,
            "coverage_pct": coverage_pct,
            "missing_by_severity": missing_by_sev,
        },
    }


__all__ = ["analyse_gaps", "_TOMRow"]
