"""Compliance-Maturity scores, daily snapshots and risk-velocity trend analysis."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.risk_config_loader import get_risk_config

MATURITY_WEIGHTS: dict[str, float] = {
    "vvt": 0.20,
    "dsfa": 0.20,
    "avv": 0.20,
    "tom": 0.20,
    "velocity": 0.20,
}

_RISK_VELOCITY_SUBSCORES = ("vvt", "dsfa", "avv", "tom", "velocity")


def _velocity_score(median_days: float, optimal_days: int, worst_days: int) -> float:
    """Linear interpolation: optimal_days -> 100, worst_days -> 0."""
    span = worst_days - optimal_days
    if span <= 0:
        return 100.0 if median_days <= optimal_days else 0.0
    return max(0.0, min(100.0, 100.0 * (worst_days - median_days) / span))


def _percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return float(values[0])
    s = sorted(values)
    idx = max(0, min(len(s) - 1, int(round((p / 100.0) * (len(s) - 1)))))
    return float(s[idx])


def _classify_trend(delta_pct: float, threshold_pct: float) -> str:
    """Return 'up' | 'down' | 'stable' depending on whether |delta| exceeds threshold."""
    if abs(delta_pct) < threshold_pct:
        return "stable"
    return "up" if delta_pct > 0 else "down"


async def compute_maturity_scores(db: AsyncSession) -> list[dict[str, Any]]:
    """Berechnet pro Department alle Sub-Scores + Composite (live, ohne Snapshots)."""
    depts_q = text(
        """
        SELECT DISTINCT department FROM cases             WHERE department IS NOT NULL AND department != ''
        UNION
        SELECT DISTINCT department FROM avv_contracts     WHERE department IS NOT NULL AND department != ''
        UNION
        SELECT DISTINCT department FROM dsr_requests      WHERE department IS NOT NULL AND department != ''
        UNION
        SELECT DISTINCT department FROM data_breaches     WHERE department IS NOT NULL AND department != ''
    """
    )
    departments = [r[0] for r in (await db.execute(depts_q)).fetchall()]

    vvt_q = text(
        """
        SELECT c.department,
               COUNT(*)                                           AS total,
               COUNT(*) FILTER (WHERE EXISTS (
                   SELECT 1 FROM documents d
                   WHERE d.case_id = c.id AND d.type = 'vvt'
               ))                                                 AS with_vvt
        FROM cases c
        WHERE c.archived_at IS NULL AND c.department IS NOT NULL
        GROUP BY c.department
    """
    )
    vvt_map: dict[str, float] = {}
    for row in (await db.execute(vvt_q)).fetchall():
        dept, total, with_vvt = row
        total = int(total or 0)
        with_vvt = int(with_vvt or 0)
        vvt_map[dept] = (with_vvt / total * 100.0) if total > 0 else 100.0

    dsfa_q = text(
        """
        SELECT c.department,
               COUNT(*) FILTER (WHERE c.special_category_data OR c.international_transfer) AS high_risk_total,
               COUNT(*) FILTER (
                   WHERE (c.special_category_data OR c.international_transfer)
                     AND EXISTS (
                         SELECT 1 FROM dsfa_assessments d
                         WHERE d.case_id = c.id AND d.status = 'finalized'
                     )
               ) AS with_dsfa
        FROM cases c
        WHERE c.archived_at IS NULL AND c.department IS NOT NULL
        GROUP BY c.department
    """
    )
    dsfa_map: dict[str, float] = {}
    for row in (await db.execute(dsfa_q)).fetchall():
        dept, hr, with_dsfa = row
        hr = int(hr or 0)
        with_dsfa = int(with_dsfa or 0)
        dsfa_map[dept] = (with_dsfa / hr * 100.0) if hr > 0 else 100.0

    avv_q = text(
        """
        SELECT department,
               COUNT(*) AS total,
               COUNT(*) FILTER (
                   WHERE status = 'signed'
                     AND risk_assessed_at IS NOT NULL
                     AND risk_assessed_at >= NOW() - INTERVAL '12 months'
               ) AS healthy
        FROM avv_contracts
        WHERE department IS NOT NULL
        GROUP BY department
    """
    )
    avv_map: dict[str, float] = {}
    for row in (await db.execute(avv_q)).fetchall():
        dept, total, healthy = row
        total = int(total or 0)
        healthy = int(healthy or 0)
        avv_map[dept] = (healthy / total * 100.0) if total > 0 else 100.0

    tom_q = text(
        """
        SELECT department_code,
               COUNT(*)                                                 AS total,
               COUNT(*) FILTER (WHERE implementation_status = 'implemented') AS implemented
        FROM (
            SELECT unnest(department_codes) AS department_code, implementation_status
            FROM tom_measures
            WHERE implementation_status != 'not_applicable'
              AND department_codes IS NOT NULL
        ) t
        GROUP BY department_code
    """
    )
    tom_map: dict[str, float] = {}
    for row in (await db.execute(tom_q)).fetchall():
        dept, total, implemented = row
        total = int(total or 0)
        implemented = int(implemented or 0)
        tom_map[dept] = (implemented / total * 100.0) if total > 0 else 100.0

    maturity_cfg = get_risk_config().maturity
    vel_q = text(
        """
        SELECT department, (responded_at - received_at)::float AS days
        FROM dsr_requests
        WHERE responded_at IS NOT NULL AND department IS NOT NULL
    """
    )
    by_dept: dict[str, list[float]] = {}
    for row in (await db.execute(vel_q)).fetchall():
        dept, d = row
        if d is None or d < 0:
            continue
        by_dept.setdefault(dept, []).append(float(d))
    vel_map: dict[str, float] = {}
    for dept, days in by_dept.items():
        med = _percentile(days, 50)
        if med is None:
            vel_map[dept] = 100.0
        else:
            vel_map[dept] = _velocity_score(
                med,
                maturity_cfg.velocity.optimal_days,
                maturity_cfg.velocity.worst_days,
            )

    weights = maturity_cfg.weights
    rows: list[dict[str, Any]] = []
    for dept in sorted(departments):
        sub = {
            "vvt_score": round(vvt_map.get(dept, 100.0), 1),
            "dsfa_score": round(dsfa_map.get(dept, 100.0), 1),
            "avv_score": round(avv_map.get(dept, 100.0), 1),
            "tom_score": round(tom_map.get(dept, 100.0), 1),
            "velocity_score": round(vel_map.get(dept, 100.0), 1),
        }
        composite = (
            sub["vvt_score"] * weights.get("vvt", MATURITY_WEIGHTS["vvt"])
            + sub["dsfa_score"] * weights.get("dsfa", MATURITY_WEIGHTS["dsfa"])
            + sub["avv_score"] * weights.get("avv", MATURITY_WEIGHTS["avv"])
            + sub["tom_score"] * weights.get("tom", MATURITY_WEIGHTS["tom"])
            + sub["velocity_score"]
            * weights.get("velocity", MATURITY_WEIGHTS["velocity"])
        )
        rows.append(
            {
                "department": dept,
                "sub_scores": sub,
                "composite_score": round(composite, 1),
                "delta_3m": None,
            }
        )
    return rows


async def maturity_stats(
    db: AsyncSession, department: str | None = None
) -> dict[str, Any]:
    """Maturity-Score live + 6-Monats-Trend aus Snapshots."""
    departments = await compute_maturity_scores(db)
    if department:
        departments = [d for d in departments if d["department"] == department]

    six_months_ago = date.today() - timedelta(days=180)
    trend_params: dict[str, Any] = {"since": six_months_ago}
    trend_filter = ""
    if department:
        trend_filter = " AND department = :dept "
        trend_params["dept"] = department
    trend_q = text(
        f"""
        SELECT department, snapshot_date, composite_score
        FROM compliance_maturity_snapshots
        WHERE snapshot_date >= :since {trend_filter}
        ORDER BY department ASC, snapshot_date ASC
    """
    )
    trend_rows = (await db.execute(trend_q, trend_params)).fetchall()
    trend = [
        {
            "department": r[0],
            "date": r[1].isoformat(),
            "composite_score": float(r[2]),
        }
        for r in trend_rows
    ]
    has_history = len(trend) > 0

    if has_history:
        ninety_days_ago = date.today() - timedelta(days=90)
        prev_q = text(
            f"""
            SELECT DISTINCT ON (department) department, composite_score, snapshot_date
            FROM compliance_maturity_snapshots
            WHERE snapshot_date <= :cut {trend_filter}
            ORDER BY department, snapshot_date DESC
        """
        )
        prev_params = {"cut": ninety_days_ago}
        if department:
            prev_params["dept"] = department
        prev_map: dict[str, float] = {
            r[0]: float(r[1])
            for r in (await db.execute(prev_q, prev_params)).fetchall()
        }
        for d in departments:
            prev = prev_map.get(d["department"])
            if prev is not None:
                d["delta_3m"] = round(d["composite_score"] - prev, 1)

    deltas = [d for d in departments if d.get("delta_3m") is not None]
    improvers = sorted(deltas, key=lambda d: d["delta_3m"], reverse=True)[:3]
    decliners = sorted(deltas, key=lambda d: d["delta_3m"])[:3]

    def _to_imp(d: dict) -> dict:
        return {
            "department": d["department"],
            "delta": d["delta_3m"],
            "current": d["composite_score"],
            "previous": round(d["composite_score"] - d["delta_3m"], 1),
        }

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "department_filter": department,
        "weights": get_risk_config().maturity.weights,
        "departments": departments,
        "trend": trend,
        "improvers": [_to_imp(d) for d in improvers if d["delta_3m"] > 0],
        "decliners": [_to_imp(d) for d in decliners if d["delta_3m"] < 0],
        "has_history": has_history,
    }


async def write_maturity_snapshot(
    db: AsyncSession, snapshot_date: date | None = None
) -> int:
    """Schreibt heutige Sub-Scores pro Department als Snapshot. Idempotent dank UniqueConstraint."""
    snapshot_date = snapshot_date or date.today()
    rows = await compute_maturity_scores(db)
    inserted = 0
    for r in rows:
        sub = r["sub_scores"]
        await db.execute(
            text(
                """
                INSERT INTO compliance_maturity_snapshots
                    (id, department, snapshot_date, vvt_score, dsfa_score, avv_score,
                     tom_score, velocity_score, composite_score)
                VALUES
                    (gen_random_uuid(), :dept, :date, :vvt, :dsfa, :avv, :tom, :vel, :comp)
                ON CONFLICT (department, snapshot_date) DO UPDATE SET
                    vvt_score = EXCLUDED.vvt_score,
                    dsfa_score = EXCLUDED.dsfa_score,
                    avv_score = EXCLUDED.avv_score,
                    tom_score = EXCLUDED.tom_score,
                    velocity_score = EXCLUDED.velocity_score,
                    composite_score = EXCLUDED.composite_score
            """
            ),
            {
                "dept": r["department"],
                "date": snapshot_date,
                "vvt": sub["vvt_score"],
                "dsfa": sub["dsfa_score"],
                "avv": sub["avv_score"],
                "tom": sub["tom_score"],
                "vel": sub["velocity_score"],
                "comp": r["composite_score"],
            },
        )
        inserted += 1
    return inserted


async def compute_risk_velocity(
    db: AsyncSession,
    department: str | None = None,
    window_days: int | None = None,
) -> dict[str, Any]:
    """Vergleicht aktuellen Composite/Sub-Score mit dem Wert vor window_days.

    Datenquelle: `compliance_maturity_snapshots`.
    """
    rv_cfg = get_risk_config().risk_velocity
    effective_window = window_days if window_days is not None else rv_cfg.window_days
    today = date.today()
    cutoff = today - timedelta(days=effective_window)

    dept_filter = ""
    params: dict[str, Any] = {"cutoff": cutoff}
    if department:
        dept_filter = " AND department = :dept "
        params["dept"] = department

    score_columns = ", ".join(
        f"{name}_score" if name != "velocity" else "velocity_score"
        for name in _RISK_VELOCITY_SUBSCORES
    )

    current_q = text(
        f"""
        SELECT DISTINCT ON (department) department, snapshot_date,
            composite_score, {score_columns}
        FROM compliance_maturity_snapshots
        WHERE 1=1 {dept_filter}
        ORDER BY department, snapshot_date DESC
    """
    )
    previous_q = text(
        f"""
        SELECT DISTINCT ON (department) department, snapshot_date,
            composite_score, {score_columns}
        FROM compliance_maturity_snapshots
        WHERE snapshot_date <= :cutoff {dept_filter}
        ORDER BY department, snapshot_date DESC
    """
    )

    current_rows = (
        await db.execute(current_q, {k: v for k, v in params.items() if k != "cutoff"})
    ).fetchall()
    previous_rows = (await db.execute(previous_q, params)).fetchall()

    def _row_to_dict(row) -> dict[str, Any]:
        dept, snap_date, composite = row[0], row[1], float(row[2])
        sub = {
            name: float(row[3 + idx])
            for idx, name in enumerate(_RISK_VELOCITY_SUBSCORES)
        }
        return {
            "department": dept,
            "snapshot_date": snap_date,
            "composite_score": composite,
            "sub_scores": sub,
        }

    current_map = {r[0]: _row_to_dict(r) for r in current_rows}
    previous_map = {r[0]: _row_to_dict(r) for r in previous_rows}

    result_departments: list[dict[str, Any]] = []
    for dept in sorted(current_map.keys()):
        cur = current_map[dept]
        prev = previous_map.get(dept)
        if prev is None:
            result_departments.append(
                {
                    "department": dept,
                    "current_composite": round(cur["composite_score"], 1),
                    "previous_composite": None,
                    "delta": None,
                    "trend": "unknown",
                    "significant": False,
                    "current_snapshot_date": cur["snapshot_date"].isoformat(),
                    "previous_snapshot_date": None,
                    "sub_scores": {
                        name: {
                            "current": round(cur["sub_scores"][name], 1),
                            "previous": None,
                            "delta": None,
                            "trend": "unknown",
                        }
                        for name in _RISK_VELOCITY_SUBSCORES
                    },
                }
            )
            continue

        delta = cur["composite_score"] - prev["composite_score"]
        sub_trends = {}
        for name in _RISK_VELOCITY_SUBSCORES:
            sub_delta = cur["sub_scores"][name] - prev["sub_scores"][name]
            sub_trends[name] = {
                "current": round(cur["sub_scores"][name], 1),
                "previous": round(prev["sub_scores"][name], 1),
                "delta": round(sub_delta, 1),
                "trend": _classify_trend(sub_delta, rv_cfg.significant_change_pct),
            }
        result_departments.append(
            {
                "department": dept,
                "current_composite": round(cur["composite_score"], 1),
                "previous_composite": round(prev["composite_score"], 1),
                "delta": round(delta, 1),
                "trend": _classify_trend(delta, rv_cfg.significant_change_pct),
                "significant": abs(delta) >= rv_cfg.significant_change_pct,
                "current_snapshot_date": cur["snapshot_date"].isoformat(),
                "previous_snapshot_date": prev["snapshot_date"].isoformat(),
                "sub_scores": sub_trends,
            }
        )

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "window_days": effective_window,
        "enabled": rv_cfg.enabled,
        "significant_change_pct": rv_cfg.significant_change_pct,
        "department_filter": department,
        "departments": result_departments,
    }
