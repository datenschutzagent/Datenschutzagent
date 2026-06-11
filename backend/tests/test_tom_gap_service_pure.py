"""Pure tests for the TOM-gap analyser (no DB, no ORM dependency)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.risk_config_loader import (
    TomBaselineConfig,
    TomBaselineRequirement,
)
from app.services.tom_gap_service import analyse_gaps


def _tom(title: str, category: str, status: str = "implemented") -> SimpleNamespace:
    """Duck-typed stand-in for a TOMModel row."""
    return SimpleNamespace(title=title, category=category, implementation_status=status)


def _baseline(*reqs: TomBaselineRequirement, enabled: bool = True) -> TomBaselineConfig:
    return TomBaselineConfig(enabled=enabled, requirements=list(reqs))


# ---------------------------------------------------------------------------
# Empty / disabled baselines
# ---------------------------------------------------------------------------


def test_disabled_baseline_returns_empty_with_full_coverage():
    out = analyse_gaps(_baseline(enabled=False), [])
    assert out["enabled"] is False
    assert out["summary"]["total"] == 0
    assert out["summary"]["coverage_pct"] == 100.0


def test_empty_baseline_returns_full_coverage():
    out = analyse_gaps(_baseline(), [])
    assert out["summary"]["total"] == 0
    assert out["summary"]["coverage_pct"] == 100.0


# ---------------------------------------------------------------------------
# Category match
# ---------------------------------------------------------------------------


def test_requirement_met_when_implemented_tom_in_category_exists():
    out = analyse_gaps(
        _baseline(TomBaselineRequirement(id="enc", label="Enc", category="encryption")),
        [_tom("AES-256 at rest", "encryption")],
    )
    assert out["summary"]["met"] == 1
    req = out["requirements"][0]
    assert req["met"] is True
    assert req["matching_toms"] == ["AES-256 at rest"]


def test_requirement_missed_when_no_tom_in_category():
    out = analyse_gaps(
        _baseline(TomBaselineRequirement(id="enc", label="Enc", category="encryption")),
        [_tom("Some access control", "access_control")],
    )
    assert out["summary"]["missing"] == 1
    assert out["summary"]["missing_by_severity"] == {"high": 1}  # default severity
    assert out["requirements"][0]["met"] is False


def test_planned_tom_does_not_count_as_implemented():
    out = analyse_gaps(
        _baseline(TomBaselineRequirement(id="enc", label="Enc", category="encryption")),
        [_tom("AES-256 (geplant)", "encryption", status="planned")],
    )
    assert out["summary"]["missing"] == 1


# ---------------------------------------------------------------------------
# Keyword filter
# ---------------------------------------------------------------------------


def test_keyword_filter_blocks_generic_tom_in_same_category():
    """A baseline with keywords_title=['at rest'] must NOT accept an
    in-transit-only encryption TOM."""
    out = analyse_gaps(
        _baseline(
            TomBaselineRequirement(
                id="enc_rest",
                label="At-rest",
                category="encryption",
                keywords_title=["at rest", "ruhend"],
            )
        ),
        [_tom("TLS for ingress", "encryption")],  # no keyword match
    )
    assert out["summary"]["missing"] == 1


def test_keyword_filter_accepts_when_any_keyword_matches_case_insensitively():
    out = analyse_gaps(
        _baseline(
            TomBaselineRequirement(
                id="enc_rest",
                label="At-rest",
                category="encryption",
                keywords_title=["at rest", "ruhend"],
            )
        ),
        [_tom("Verschlüsselung Ruhender Daten", "encryption")],  # case-insensitive
    )
    assert out["summary"]["met"] == 1


# ---------------------------------------------------------------------------
# Severity aggregation + sort
# ---------------------------------------------------------------------------


def test_missing_by_severity_aggregates_correctly():
    out = analyse_gaps(
        _baseline(
            TomBaselineRequirement(
                id="a", label="A", category="encryption", severity="critical"
            ),
            TomBaselineRequirement(
                id="b", label="B", category="encryption", severity="critical"
            ),
            TomBaselineRequirement(
                id="c", label="C", category="encryption", severity="medium"
            ),
        ),
        [],  # nothing implemented
    )
    assert out["summary"]["missing_by_severity"] == {"critical": 2, "medium": 1}


def test_gaps_sorted_before_met_then_by_severity_desc():
    out = analyse_gaps(
        _baseline(
            TomBaselineRequirement(
                id="z_low", label="Low gap", category="other", severity="low"
            ),
            TomBaselineRequirement(
                id="a_crit", label="Crit gap", category="other", severity="critical"
            ),
            TomBaselineRequirement(
                id="m_met", label="Met", category="testing", severity="high"
            ),
        ),
        [_tom("Pentest 2025", "testing")],
    )
    ids = [r["id"] for r in out["requirements"]]
    # Gaps first (False sorts before True), within gaps higher severity first.
    assert ids == ["a_crit", "z_low", "m_met"]


# ---------------------------------------------------------------------------
# Coverage percentage
# ---------------------------------------------------------------------------


def test_coverage_pct_50_when_half_met():
    out = analyse_gaps(
        _baseline(
            TomBaselineRequirement(id="a", label="A", category="encryption"),
            TomBaselineRequirement(id="b", label="B", category="testing"),
        ),
        [_tom("AES-256", "encryption")],
    )
    assert out["summary"]["coverage_pct"] == 50.0


def test_invalid_severity_rejected_at_load():
    with pytest.raises(ValueError):
        TomBaselineRequirement(
            id="x", label="X", category="encryption", severity="bogus"
        )


def test_duplicate_ids_rejected():
    with pytest.raises(ValueError):
        TomBaselineConfig(
            requirements=[
                TomBaselineRequirement(id="dup", label="A", category="encryption"),
                TomBaselineRequirement(id="dup", label="B", category="testing"),
            ]
        )
