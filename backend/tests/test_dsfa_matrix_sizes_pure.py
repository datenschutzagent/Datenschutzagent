"""Pure tests for variable DSFA matrix sizes + boolean screening rules.

Covers:
  - Default 5×5 matrix is bit-for-bit identical to the legacy hardcoded one.
  - 3×3 and 7×7 default matrices have correct dimensions and corner labels.
  - scale_type validator rejects unknown values.
  - Custom matrices are validated for completeness against the scale size.
  - Auto-fill: when only scale_type is set, matrix + labels are auto-generated.
  - Boolean rules: unknown factor ids are rejected at load time.
"""

from __future__ import annotations

import pytest

from app.services.risk_config_loader import (
    DsfaAssessmentConfig,
    DsfaScreeningConfig,
    DsfaScreeningFactor,
    DsfaScreeningRule,
    RiskConfig,
    _default_dsfa_matrix_for_size,
)

_LEGACY_5X5 = {
    "1_1": "low",
    "1_2": "low",
    "1_3": "low",
    "1_4": "medium",
    "1_5": "medium",
    "2_1": "low",
    "2_2": "low",
    "2_3": "medium",
    "2_4": "medium",
    "2_5": "high",
    "3_1": "low",
    "3_2": "medium",
    "3_3": "medium",
    "3_4": "high",
    "3_5": "high",
    "4_1": "medium",
    "4_2": "medium",
    "4_3": "high",
    "4_4": "high",
    "4_5": "critical",
    "5_1": "medium",
    "5_2": "high",
    "5_3": "high",
    "5_4": "critical",
    "5_5": "critical",
}


# ---------------------------------------------------------------------------
# Matrix defaults
# ---------------------------------------------------------------------------


def test_default_5x5_matches_legacy():
    """The default matrix MUST be byte-identical to the legacy hardcoded one."""
    cfg = DsfaAssessmentConfig()
    assert cfg.matrix == _LEGACY_5X5


def test_default_3x3_has_9_cells():
    cfg = DsfaAssessmentConfig(scale_type="1-3")
    assert cfg.size == 3
    assert len(cfg.matrix) == 9
    # Corners
    assert cfg.matrix["1_1"] == "low"
    assert cfg.matrix["3_3"] == "critical"


def test_default_7x7_has_49_cells_with_critical_corner():
    cfg = DsfaAssessmentConfig(scale_type="1-7")
    assert cfg.size == 7
    assert len(cfg.matrix) == 49
    assert cfg.matrix["1_1"] == "low"
    assert cfg.matrix["7_7"] == "critical"


def test_default_matrix_for_size_helper_handles_all_sizes():
    for size in (3, 5, 7):
        m = _default_dsfa_matrix_for_size(size)
        assert len(m) == size * size
        assert m["1_1"] == "low"
        assert m[f"{size}_{size}"] == "critical"


# ---------------------------------------------------------------------------
# scale_type validation
# ---------------------------------------------------------------------------


def test_scale_type_validator_rejects_unknown():
    with pytest.raises(ValueError):
        DsfaAssessmentConfig(scale_type="1-9")


def test_scale_type_accepts_all_three_supported_sizes():
    for st in ("1-3", "1-5", "1-7"):
        cfg = DsfaAssessmentConfig(scale_type=st)
        assert cfg.scale_type == st


# ---------------------------------------------------------------------------
# Custom matrix validation
# ---------------------------------------------------------------------------


def test_custom_matrix_with_missing_cells_rejected_for_3x3():
    with pytest.raises(ValueError):
        DsfaAssessmentConfig(
            scale_type="1-3",
            matrix={"1_1": "low", "2_2": "medium"},  # incomplete
        )


def test_custom_matrix_with_extra_cells_rejected():
    incomplete_3x3 = _default_dsfa_matrix_for_size(3)
    incomplete_3x3["9_9"] = "critical"  # bogus cell
    with pytest.raises(ValueError):
        DsfaAssessmentConfig(scale_type="1-3", matrix=incomplete_3x3)


def test_custom_matrix_with_invalid_level_rejected():
    bad = _default_dsfa_matrix_for_size(3)
    bad["1_1"] = "unknown_level"
    with pytest.raises(ValueError):
        DsfaAssessmentConfig(scale_type="1-3", matrix=bad)


def test_custom_matrix_accepted_when_complete_and_valid():
    custom = _default_dsfa_matrix_for_size(3)
    custom["3_3"] = "high"
    cfg = DsfaAssessmentConfig(scale_type="1-3", matrix=custom)
    assert cfg.matrix["3_3"] == "high"


# ---------------------------------------------------------------------------
# Auto-fill labels
# ---------------------------------------------------------------------------


def test_labels_autofilled_for_3x3_when_caller_uses_defaults():
    cfg = DsfaAssessmentConfig(scale_type="1-3")
    assert set(cfg.scale_labels["likelihood"].keys()) == {1, 2, 3}
    assert set(cfg.scale_labels["severity"].keys()) == {1, 2, 3}


def test_labels_autofilled_for_7x7():
    cfg = DsfaAssessmentConfig(scale_type="1-7")
    assert set(cfg.scale_labels["likelihood"].keys()) == {1, 2, 3, 4, 5, 6, 7}


def test_custom_partial_labels_rejected_for_7x7():
    with pytest.raises(ValueError):
        DsfaAssessmentConfig(
            scale_type="1-7",
            scale_labels={
                "likelihood": {i: f"L{i}" for i in range(1, 7)},  # missing 7
                "severity": {i: f"S{i}" for i in range(1, 8)},
            },
        )


# ---------------------------------------------------------------------------
# Boolean screening rules
# ---------------------------------------------------------------------------


def _factor(id: str) -> DsfaScreeningFactor:
    return DsfaScreeningFactor.model_validate({"id": id, "label": id})


def test_rule_with_known_factor_ids_accepted():
    cfg = DsfaScreeningConfig(
        factors=[_factor("a"), _factor("b")],
        rules=[
            DsfaScreeningRule(
                id="r1",
                label="R1",
                expression="a AND b",
                action="require_dsfa",
            )
        ],
    )
    assert len(cfg.rules) == 1


def test_rule_with_unknown_factor_id_rejected():
    with pytest.raises(ValueError) as exc:
        DsfaScreeningConfig(
            factors=[_factor("a")],
            rules=[
                DsfaScreeningRule(
                    id="r1",
                    label="R1",
                    expression="a AND nonexistent",
                    action="require_dsfa",
                )
            ],
        )
    assert "nonexistent" in str(exc.value)


def test_rule_with_invalid_action_rejected():
    with pytest.raises(ValueError):
        DsfaScreeningRule(id="r", label="R", expression="a", action="bump_severity")


def test_rule_with_invalid_expression_rejected_at_field_validator():
    with pytest.raises(ValueError):
        DsfaScreeningRule(id="r", label="R", expression="a AND", action="require_dsfa")


def test_duplicate_rule_ids_rejected():
    with pytest.raises(ValueError):
        DsfaScreeningConfig(
            factors=[_factor("a")],
            rules=[
                DsfaScreeningRule(id="dup", label="R1", expression="a"),
                DsfaScreeningRule(id="dup", label="R2", expression="a"),
            ],
        )


# ---------------------------------------------------------------------------
# Full RiskConfig with everything
# ---------------------------------------------------------------------------


def test_riskconfig_loads_with_3x3_and_rules():
    cfg = RiskConfig.model_validate(
        {
            "dsfa_assessment": {"scale_type": "1-3"},
            "dsfa_screening": {
                "factors": [
                    {"id": "profiling", "label": "P"},
                    {"id": "special_categories", "label": "S"},
                ],
                "rules": [
                    {
                        "id": "edsa_combo",
                        "label": "EDSA-Combo",
                        "expression": "profiling AND special_categories",
                        "action": "require_dsfa",
                    }
                ],
            },
        }
    )
    assert cfg.dsfa_assessment.size == 3
    assert len(cfg.dsfa_screening.rules) == 1
    # Risk-level for 1_1 / 3_3 from auto-generated 3×3 default.
    assert cfg.dsfa_assessment.risk_level_for(1, 1) == "low"
    assert cfg.dsfa_assessment.risk_level_for(3, 3) == "critical"
