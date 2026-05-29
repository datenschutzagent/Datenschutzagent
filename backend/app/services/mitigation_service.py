"""Mitigation engine: maps inherent risks to residual risks via active mitigations.

Pure functions — no DB, no IO. The AVV/DSFA services pass in inherent
values plus the list of currently linked mitigation ids; the engine returns
the residual values plus a per-mitigation effect trace for UI display.

See risk_config_loader.MitigationCatalogConfig for the catalog schema.
"""
from __future__ import annotations

from typing import Any

from app.services.risk_config_loader import (
    AvvRiskConfig,
    DsfaAssessmentConfig,
    MitigationCatalogConfig,
    MitigationConfig,
)


def _clamp_score(value: float, floor: float, ceil: float = 5.0) -> float:
    if value < floor:
        return floor
    if value > ceil:
        return ceil
    return value


def _clamp_int(value: int, floor: int, ceil: int = 5) -> int:
    if value < floor:
        return floor
    if value > ceil:
        return ceil
    return value


# ---------------------------------------------------------------------------
# AVV
# ---------------------------------------------------------------------------


def apply_avv_mitigations(
    inherent_dimensions: list[dict[str, Any]],
    applied_mitigation_ids: list[str],
    catalog: MitigationCatalogConfig,
    avv_cfg: AvvRiskConfig,
) -> dict[str, Any]:
    """Compute residual AVV scoring from inherent dimensions and active mitigations.

    Parameters
    ----------
    inherent_dimensions: list of dicts as emitted by the LLM. Each dict has
        keys 'name' (str), 'score' (1-5 int), 'rationale' (str).
    applied_mitigation_ids: ids of mitigations currently linked to the case.
    catalog: full mitigation catalog (only entries that apply_to avv/both
        are evaluated).
    avv_cfg: used for level threshold lookup and percent normalization.

    Returns
    -------
    dict with:
        residual_dimensions: same shape as input, with adjusted scores
        residual_avg_score: weighted-mean score after reductions (clamped)
        residual_risk_score: 0..100 percent
        residual_risk_level: low|medium|high|critical
        applied_effects: list of {id, label, score_delta, dimension_deltas}
            actually applied (filtered by applies_to).
    """
    floor = catalog.min_avv_score
    active = _resolve_active(catalog.applicable("avv"), applied_mitigation_ids)

    applied_effects: list[dict[str, Any]] = []
    # Aggregate per-dimension and global score deltas across all active mitigations.
    dim_total_delta: dict[str, float] = {}
    score_total_delta = 0.0
    for m in active:
        dim_deltas = dict(m.reduction.dimension_deltas)
        score_delta = m.reduction.score_delta
        if not dim_deltas and score_delta == 0.0:
            # AVV not actually affected by this mitigation (e.g. DSFA-only fields).
            continue
        for dim, delta in dim_deltas.items():
            dim_total_delta[dim] = dim_total_delta.get(dim, 0.0) + delta
        score_total_delta += score_delta
        applied_effects.append({
            "id": m.id,
            "label": m.label,
            "score_delta": round(score_delta, 3),
            "dimension_deltas": {k: round(v, 3) for k, v in dim_deltas.items()},
        })

    residual_dimensions: list[dict[str, Any]] = []
    for d in inherent_dimensions:
        name = d.get("name", "")
        inh_score = float(d.get("score", 3))
        delta = dim_total_delta.get(name, 0.0)
        new_score = _clamp_score(inh_score + delta, floor=floor, ceil=5.0)
        residual_dimensions.append({
            "name": name,
            "score": round(new_score, 2),
            "inherent_score": int(inh_score) if inh_score == int(inh_score) else round(inh_score, 2),
            "delta": round(delta, 3),
            "rationale": d.get("rationale", ""),
        })

    # Weighted mean (matches avv_risk_service._weighted_average semantics).
    weights = avv_cfg.dimension_weights or {}
    if residual_dimensions:
        if weights:
            total_w = 0.0
            weighted = 0.0
            for d in residual_dimensions:
                w = float(weights.get(d["name"], 1.0))
                total_w += w
                weighted += float(d["score"]) * w
            mean = (weighted / total_w) if total_w > 0 else (
                sum(float(d["score"]) for d in residual_dimensions) / len(residual_dimensions)
            )
        else:
            mean = sum(float(d["score"]) for d in residual_dimensions) / len(residual_dimensions)
    else:
        mean = 3.0

    residual_avg = _clamp_score(mean + score_total_delta, floor=floor, ceil=5.0)
    residual_pct = avv_cfg.normalize_to_percent(residual_avg)
    residual_level = avv_cfg.level_for_score(residual_avg)

    return {
        "residual_dimensions": residual_dimensions,
        "residual_avg_score": round(residual_avg, 2),
        "residual_risk_score": residual_pct,
        "residual_risk_level": residual_level,
        "applied_effects": applied_effects,
    }


# ---------------------------------------------------------------------------
# DSFA
# ---------------------------------------------------------------------------


def apply_dsfa_mitigations(
    inherent_risks: list[dict[str, Any]],
    applied_mitigation_ids: list[str],
    catalog: MitigationCatalogConfig,
    dsfa_cfg: DsfaAssessmentConfig,
) -> dict[str, Any]:
    """Compute residual DSFA risks from inherent risks and active mitigations.

    Each risk dict is expected to have ``likelihood_score`` (1-5) and
    ``severity_score`` (1-5); the matrix lookup produces ``risk_level``.

    A mitigation applies to a risk if:
      - its applicable_risk_keywords list is empty, or
      - any keyword (case-insensitive) is a substring of risk['description'].

    The deltas of all matching mitigations are summed, clamped at the
    catalog floors, and the new matrix cell is looked up.
    """
    floor_lik = catalog.min_likelihood
    floor_sev = catalog.min_severity
    active = _resolve_active(catalog.applicable("dsfa"), applied_mitigation_ids)

    residual_risks: list[dict[str, Any]] = []
    # Track effects across all risks for the global summary panel.
    effect_index: dict[str, dict[str, Any]] = {}

    for r in inherent_risks:
        description = str(r.get("description", "")).lower()
        inh_lik = int(r.get("likelihood_score", 3))
        inh_sev = int(r.get("severity_score", 3))
        lik_delta_sum = 0
        sev_delta_sum = 0
        per_risk_effects: list[str] = []
        for m in active:
            if m.reduction.likelihood_delta == 0 and m.reduction.severity_delta == 0:
                continue
            kws = [kw.lower() for kw in m.reduction.applicable_risk_keywords]
            if kws and not any(kw in description for kw in kws):
                continue
            lik_delta_sum += m.reduction.likelihood_delta
            sev_delta_sum += m.reduction.severity_delta
            per_risk_effects.append(m.id)
            effect_index.setdefault(m.id, {
                "id": m.id,
                "label": m.label,
                "likelihood_delta": m.reduction.likelihood_delta,
                "severity_delta": m.reduction.severity_delta,
                "applied_to_risks": [],
            })
            effect_index[m.id]["applied_to_risks"].append(r.get("description", "")[:120])

        new_lik = _clamp_int(inh_lik + lik_delta_sum, floor=floor_lik, ceil=5)
        new_sev = _clamp_int(inh_sev + sev_delta_sum, floor=floor_sev, ceil=5)
        try:
            new_level = dsfa_cfg.risk_level_for(new_lik, new_sev)
        except KeyError:
            new_level = r.get("risk_level", "medium")

        residual_risks.append({
            **r,
            "likelihood_score": new_lik,
            "severity_score": new_sev,
            "risk_level": new_level,
            "inherent_likelihood_score": inh_lik,
            "inherent_severity_score": inh_sev,
            "inherent_risk_level": r.get("risk_level", new_level),
            "applied_mitigation_ids": per_risk_effects,
        })

    residual_overall = _max_level(residual_risks) if residual_risks else "low"
    inherent_overall = _max_level(inherent_risks) if inherent_risks else "low"

    return {
        "residual_risks": residual_risks,
        "residual_overall_level": residual_overall,
        "inherent_overall_level": inherent_overall,
        "dpo_consultation_required": residual_overall in dsfa_cfg.dpo_consultation_required_when_residual_in,
        "applied_effects": list(effect_index.values()),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_LEVEL_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def _max_level(risks: list[dict[str, Any]]) -> str:
    """Return the highest risk_level across a list of risk dicts."""
    if not risks:
        return "low"
    return max(
        (r.get("risk_level", "low") for r in risks if isinstance(r, dict)),
        key=lambda lv: _LEVEL_RANK.get(lv, 0),
        default="low",
    )


def _resolve_active(applicable: list[MitigationConfig], applied_ids: list[str]) -> list[MitigationConfig]:
    """Return catalog entries whose id is in applied_ids, preserving order.

    Silently ignores ids not found in the catalog — they may refer to
    deactivated entries; callers can still display them via the link table.
    """
    if not applied_ids:
        return []
    wanted = set(applied_ids)
    return [m for m in applicable if m.id in wanted]
