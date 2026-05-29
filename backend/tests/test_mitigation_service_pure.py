"""Pure unit tests for the mitigation engine (no DB, no LLM, no IO).

Covers:
  - AVV: score_delta + per-dimension reduction, floor clamping, multi-mitigation
  - DSFA: per-risk likelihood/severity reduction, keyword filter, floors,
    matrix lookup of the residual cell
  - Catalog helpers: by_id, applicable, unknown ids ignored
"""
from __future__ import annotations

import pytest

from app.services.mitigation_service import (
    apply_avv_mitigations,
    apply_dsfa_mitigations,
)
from app.services.risk_config_loader import (
    AvvRiskConfig,
    DsfaAssessmentConfig,
    MitigationCatalogConfig,
    MitigationConfig,
    MitigationReduction,
    RiskConfig,
)


# ---------------------------------------------------------------------------
# Catalog helpers
# ---------------------------------------------------------------------------


def _catalog(*entries: MitigationConfig, **kwargs) -> MitigationCatalogConfig:
    return MitigationCatalogConfig(catalog=list(entries), **kwargs)


def test_catalog_by_id_returns_entry():
    cat = _catalog(
        MitigationConfig(id="a", label="A"),
        MitigationConfig(id="b", label="B"),
    )
    assert cat.by_id("a").label == "A"
    assert cat.by_id("missing") is None


def test_catalog_applicable_filters_by_target():
    cat = _catalog(
        MitigationConfig(id="a", label="A", applies_to="avv"),
        MitigationConfig(id="b", label="B", applies_to="dsfa"),
        MitigationConfig(id="c", label="C", applies_to="both"),
    )
    avv_ids = [m.id for m in cat.applicable("avv")]
    dsfa_ids = [m.id for m in cat.applicable("dsfa")]
    assert avv_ids == ["a", "c"]
    assert dsfa_ids == ["b", "c"]
    assert cat.applicable("unknown") == []


def test_catalog_unique_ids_enforced():
    with pytest.raises(ValueError):
        _catalog(
            MitigationConfig(id="dup", label="A"),
            MitigationConfig(id="dup", label="B"),
        )


def test_dimension_deltas_must_be_non_positive():
    with pytest.raises(ValueError):
        MitigationReduction(dimension_deltas={"X": 0.5})


# ---------------------------------------------------------------------------
# AVV
# ---------------------------------------------------------------------------


def _dim(name: str, score: int) -> dict:
    return {"name": name, "score": score, "rationale": ""}


def test_avv_no_mitigations_is_identity():
    cat = _catalog()
    avv_cfg = AvvRiskConfig()
    dims = [_dim("Datensensitivität", 3), _dim("Drittlandrisiko", 3)]
    out = apply_avv_mitigations(dims, [], cat, avv_cfg)
    assert out["residual_avg_score"] == 3.0
    assert out["residual_risk_level"] == "high"  # 3 → high under default 1.5/2.5/3.5/5.0
    assert out["applied_effects"] == []
    # Each residual dimension carries inherent + delta + rationale.
    assert all("inherent_score" in d and "delta" in d for d in out["residual_dimensions"])


def test_avv_score_delta_reduces_average():
    cat = _catalog(
        MitigationConfig(id="m1", label="M1", applies_to="avv",
                         reduction=MitigationReduction(score_delta=-1.0)),
    )
    avv_cfg = AvvRiskConfig()
    dims = [_dim("A", 4), _dim("B", 4)]  # mean = 4
    out = apply_avv_mitigations(dims, ["m1"], cat, avv_cfg)
    assert out["residual_avg_score"] == 3.0
    assert out["residual_risk_level"] == "high"
    assert out["applied_effects"][0]["id"] == "m1"


def test_avv_dimension_delta_applied_before_mean():
    cat = _catalog(
        MitigationConfig(id="m1", label="M1", applies_to="avv",
                         reduction=MitigationReduction(dimension_deltas={"A": -2.0})),
    )
    avv_cfg = AvvRiskConfig()
    dims = [_dim("A", 5), _dim("B", 3)]  # inherent mean=4 → with reduction (A=3,B=3): mean=3
    out = apply_avv_mitigations(dims, ["m1"], cat, avv_cfg)
    assert out["residual_avg_score"] == 3.0
    # Dimension-level inherent_score preserved
    assert out["residual_dimensions"][0]["inherent_score"] == 5
    assert out["residual_dimensions"][0]["score"] == 3


def test_avv_floor_prevents_score_below_min():
    cat = _catalog(
        MitigationConfig(id="m1", label="M1", applies_to="avv",
                         reduction=MitigationReduction(score_delta=-5.0)),
        min_avv_score=1.0,
    )
    avv_cfg = AvvRiskConfig()
    dims = [_dim("A", 2)]
    out = apply_avv_mitigations(dims, ["m1"], cat, avv_cfg)
    assert out["residual_avg_score"] == 1.0
    assert out["residual_risk_level"] == "low"


def test_avv_multiple_mitigations_compose():
    cat = _catalog(
        MitigationConfig(id="m1", label="M1", applies_to="avv",
                         reduction=MitigationReduction(score_delta=-0.5)),
        MitigationConfig(id="m2", label="M2", applies_to="avv",
                         reduction=MitigationReduction(dimension_deltas={"A": -1.0})),
    )
    avv_cfg = AvvRiskConfig()
    dims = [_dim("A", 4), _dim("B", 4)]  # inherent mean=4 → A=3,B=4 → mean=3.5 → -0.5 = 3.0
    out = apply_avv_mitigations(dims, ["m1", "m2"], cat, avv_cfg)
    assert out["residual_avg_score"] == 3.0
    assert {e["id"] for e in out["applied_effects"]} == {"m1", "m2"}


def test_avv_dsfa_only_mitigation_is_filtered_out():
    """A mitigation with applies_to='dsfa' must not affect the AVV side."""
    cat = _catalog(
        MitigationConfig(id="dsfa_only", label="DSFA only", applies_to="dsfa",
                         reduction=MitigationReduction(likelihood_delta=-2)),
    )
    avv_cfg = AvvRiskConfig()
    dims = [_dim("A", 4)]
    out = apply_avv_mitigations(dims, ["dsfa_only"], cat, avv_cfg)
    assert out["residual_avg_score"] == 4.0
    assert out["applied_effects"] == []


def test_avv_unknown_mitigation_id_is_ignored():
    cat = _catalog(
        MitigationConfig(id="m1", label="M1", applies_to="avv",
                         reduction=MitigationReduction(score_delta=-1.0)),
    )
    avv_cfg = AvvRiskConfig()
    dims = [_dim("A", 3)]
    out = apply_avv_mitigations(dims, ["m1", "does_not_exist"], cat, avv_cfg)
    # Only the known one applies.
    assert out["residual_avg_score"] == 2.0
    assert len(out["applied_effects"]) == 1


def test_avv_weighted_average_with_dimension_weights():
    cat = _catalog()
    avv_cfg = AvvRiskConfig(dimension_weights={"A": 3.0, "B": 1.0})
    dims = [_dim("A", 4), _dim("B", 2)]
    out = apply_avv_mitigations(dims, [], cat, avv_cfg)
    # weighted mean: (4*3 + 2*1)/4 = 3.5
    assert out["residual_avg_score"] == 3.5


# ---------------------------------------------------------------------------
# DSFA
# ---------------------------------------------------------------------------


def _risk(desc: str, lik: int, sev: int, level: str = "medium") -> dict:
    return {
        "description": desc,
        "likelihood_score": lik,
        "severity_score": sev,
        "risk_level": level,
        "mitigation": "",
    }


def test_dsfa_no_mitigations_returns_inherent():
    cat = _catalog()
    cfg = DsfaAssessmentConfig()
    risks = [_risk("R1", 3, 3, "medium")]
    out = apply_dsfa_mitigations(risks, [], cat, cfg)
    assert out["residual_overall_level"] == "medium"
    assert out["residual_risks"][0]["likelihood_score"] == 3
    assert out["residual_risks"][0]["inherent_likelihood_score"] == 3
    assert out["applied_effects"] == []


def test_dsfa_likelihood_delta_reduces_matrix_cell():
    cat = _catalog(
        MitigationConfig(id="m1", label="M1", applies_to="dsfa",
                         reduction=MitigationReduction(likelihood_delta=-1)),
    )
    cfg = DsfaAssessmentConfig()
    # 4_4 = high → after lik -1 → 3_4 = high (default matrix)
    # 5_5 = critical → 4_5 = critical
    # Use 4_5 = critical → 3_5 = high.
    risks = [_risk("R1", 4, 5, "critical")]
    out = apply_dsfa_mitigations(risks, ["m1"], cat, cfg)
    assert out["residual_risks"][0]["likelihood_score"] == 3
    assert out["residual_risks"][0]["severity_score"] == 5
    assert out["residual_risks"][0]["risk_level"] == "high"
    assert out["residual_overall_level"] == "high"
    assert out["inherent_overall_level"] == "critical"


def test_dsfa_keyword_filter_only_matches_relevant_risks():
    cat = _catalog(
        MitigationConfig(id="m1", label="M1", applies_to="dsfa",
                         reduction=MitigationReduction(
                             severity_delta=-2,
                             applicable_risk_keywords=["leak"],
                         )),
    )
    cfg = DsfaAssessmentConfig()
    risks = [
        _risk("Datenleak möglich", 3, 5, "high"),    # matches keyword
        _risk("System fällt aus", 3, 5, "high"),     # does NOT match
    ]
    out = apply_dsfa_mitigations(risks, ["m1"], cat, cfg)
    assert out["residual_risks"][0]["severity_score"] == 3  # 5 - 2
    assert out["residual_risks"][1]["severity_score"] == 5  # unaffected


def test_dsfa_floor_prevents_below_one():
    cat = _catalog(
        MitigationConfig(id="m1", label="M1", applies_to="dsfa",
                         reduction=MitigationReduction(
                             likelihood_delta=-5,
                             severity_delta=-5,
                         )),
        min_likelihood=1,
        min_severity=1,
    )
    cfg = DsfaAssessmentConfig()
    risks = [_risk("R1", 2, 2, "low")]
    out = apply_dsfa_mitigations(risks, ["m1"], cat, cfg)
    assert out["residual_risks"][0]["likelihood_score"] == 1
    assert out["residual_risks"][0]["severity_score"] == 1
    assert out["residual_risks"][0]["risk_level"] == "low"


def test_dsfa_dpo_required_propagates_from_residual():
    """DPO consultation must flip OFF when mitigations push residual below high."""
    cat = _catalog(
        MitigationConfig(id="m1", label="M1", applies_to="dsfa",
                         reduction=MitigationReduction(
                             likelihood_delta=-2,
                             severity_delta=-2,
                         )),
    )
    cfg = DsfaAssessmentConfig()  # default: dpo when residual in {high, critical}
    risks = [_risk("R1", 5, 5, "critical")]
    out_pre = apply_dsfa_mitigations(risks, [], cat, cfg)
    out_post = apply_dsfa_mitigations(risks, ["m1"], cat, cfg)
    assert out_pre["dpo_consultation_required"] is True
    # 5-2=3, 5-2=3 → matrix 3_3 = medium → DPO no longer required
    assert out_post["residual_risks"][0]["risk_level"] == "medium"
    assert out_post["dpo_consultation_required"] is False


def test_dsfa_inherent_vs_residual_traces_both_per_risk():
    cat = _catalog(
        MitigationConfig(id="m1", label="M1", applies_to="dsfa",
                         reduction=MitigationReduction(likelihood_delta=-1)),
    )
    cfg = DsfaAssessmentConfig()
    risks = [_risk("R1", 4, 4, "high")]
    out = apply_dsfa_mitigations(risks, ["m1"], cat, cfg)
    r = out["residual_risks"][0]
    assert r["inherent_likelihood_score"] == 4
    assert r["inherent_severity_score"] == 4
    assert r["likelihood_score"] == 3
    assert r["applied_mitigation_ids"] == ["m1"]


# ---------------------------------------------------------------------------
# RiskConfig integration
# ---------------------------------------------------------------------------


def test_riskconfig_defaults_has_empty_catalog_but_enabled():
    """Built-in defaults must keep mitigations off-by-effect (empty catalog) but
    not disabled, so loading a YAML that adds entries works out of the box."""
    cfg = RiskConfig()
    assert cfg.mitigations.enabled is True
    assert cfg.mitigations.catalog == []
    assert cfg.mitigations.min_avv_score == 1.0


def test_riskconfig_validates_unique_catalog_ids_via_top_level():
    with pytest.raises(ValueError):
        RiskConfig.model_validate({
            "mitigations": {
                "catalog": [
                    {"id": "dup", "label": "A"},
                    {"id": "dup", "label": "B"},
                ]
            }
        })
