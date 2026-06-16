"""DSR-MTTR, breach notification speed, findings resolution and workflow funnels."""

from __future__ import annotations

import statistics
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return float(values[0])
    s = sorted(values)
    idx = max(0, min(len(s) - 1, int(round((p / 100.0) * (len(s) - 1)))))
    return float(s[idx])


def _histogram_days(values: list[float]) -> list[dict]:
    buckets = [
        ("0-7", 0, 7),
        ("8-14", 8, 14),
        ("15-30", 15, 30),
        ("31-60", 31, 60),
        ("61+", 61, None),
    ]
    counts = {b[0]: 0 for b in buckets}
    for v in values:
        for label, lo, hi in buckets:
            if v >= lo and (hi is None or v <= hi):
                counts[label] += 1
                break
    return [{"bucket": b[0], "count": counts[b[0]]} for b in buckets]


def _histogram_hours(values: list[float]) -> list[dict]:
    buckets = [
        ("0-24h", 0.0, 24.0),
        ("24-48h", 24.0, 48.0),
        ("48-72h", 48.0, 72.0),
        ("72-168h", 72.0, 168.0),
        (">168h", 168.0, None),
    ]
    counts = {b[0]: 0 for b in buckets}
    for v in values:
        for label, lo, hi in buckets:
            if v >= lo and (hi is None or v < hi):
                counts[label] += 1
                break
    return [{"bucket": b[0], "count": counts[b[0]]} for b in buckets]


def _summarize_funnel(label: str, rows: list[Any]) -> dict:
    by_transition: dict[str, list[float]] = {}
    for row in rows:
        prev, curr, hours = row
        if hours is None or hours < 0:
            continue
        key = f"{prev} → {curr}"
        by_transition.setdefault(key, []).append(float(hours))
    steps = []
    for key, vs in sorted(by_transition.items(), key=lambda kv: -len(kv[1])):
        steps.append(
            {
                "transition": key,
                "avg_hours": round(statistics.fmean(vs), 1) if vs else None,
                "median_hours": _percentile(vs, 50),
                "sample_size": len(vs),
            }
        )
    return {"entity": label, "steps": steps[:8]}


async def _compute_funnels(db: AsyncSession, department: str | None) -> list[dict]:
    """Mittlere/Median Stunden zwischen aufeinanderfolgenden Activity-Log-Events."""
    funnels: list[dict] = []
    params: dict[str, Any] = {}
    dept_join_dsr = ""
    if department:
        dept_join_dsr = (
            " JOIN dsr_requests r ON r.id = a.request_id AND r.department = :dept "
        )
        params["dept"] = department
    dsr_funnel_q = text(
        f"""
        WITH ordered AS (
            SELECT a.request_id,
                   a.event_type,
                   a.created_at,
                   LAG(a.event_type)  OVER w AS prev_event,
                   LAG(a.created_at) OVER w AS prev_at
            FROM dsr_activity_log a
            {dept_join_dsr}
            WINDOW w AS (PARTITION BY a.request_id ORDER BY a.created_at)
        )
        SELECT prev_event, event_type,
               EXTRACT(EPOCH FROM (created_at - prev_at))/3600.0 AS hours
        FROM ordered
        WHERE prev_event IS NOT NULL
    """
    )
    rows = (await db.execute(dsr_funnel_q, params)).fetchall()
    funnels.append(_summarize_funnel("DSR", rows))

    dept_join_breach = ""
    if department:
        dept_join_breach = (
            " JOIN data_breaches b ON b.id = a.breach_id AND b.department = :dept "
        )
    breach_funnel_q = text(
        f"""
        WITH ordered AS (
            SELECT a.breach_id,
                   a.event_type,
                   a.created_at,
                   LAG(a.event_type)  OVER w AS prev_event,
                   LAG(a.created_at) OVER w AS prev_at
            FROM data_breach_activity_log a
            {dept_join_breach}
            WINDOW w AS (PARTITION BY a.breach_id ORDER BY a.created_at)
        )
        SELECT prev_event, event_type,
               EXTRACT(EPOCH FROM (created_at - prev_at))/3600.0 AS hours
        FROM ordered
        WHERE prev_event IS NOT NULL
    """
    )
    rows = (await db.execute(breach_funnel_q, params)).fetchall()
    funnels.append(_summarize_funnel("Datenpanne", rows))
    return funnels


async def velocity_stats(
    db: AsyncSession, department: str | None = None
) -> dict[str, Any]:
    """DSR-MTTR + Breach-Notification-Speed + Findings-Resolution + Workflow-Funnels."""
    params: dict[str, Any] = {}
    dept_filter_dsr = ""
    if department:
        dept_filter_dsr = " AND department = :dept "
        params["dept"] = department

    dsr_q = text(
        f"""
        SELECT (responded_at - received_at) AS days, request_type, received_at
        FROM dsr_requests
        WHERE responded_at IS NOT NULL {dept_filter_dsr}
    """
    )
    dsr_rows = (await db.execute(dsr_q, params)).fetchall()
    dsr_days = [float(r[0]) for r in dsr_rows if r[0] is not None]
    dsr_total = len(dsr_days)
    dsr_under_30 = sum(1 for d in dsr_days if d <= 30)
    sla_pct = (dsr_under_30 / dsr_total * 100.0) if dsr_total else None

    by_type_map: dict[str, list[float]] = {}
    for row in dsr_rows:
        d, typ, _ = row
        if d is None:
            continue
        by_type_map.setdefault(typ, []).append(float(d))
    by_request_type = [
        {
            "request_type": t,
            "sample_size": len(vs),
            "median_days": _percentile(vs, 50),
            "p90_days": _percentile(vs, 90),
        }
        for t, vs in sorted(by_type_map.items())
    ]

    six_months = (date.today().replace(day=1) - timedelta(days=1)).replace(
        day=1
    ) - timedelta(days=140)
    months: dict[str, list[float]] = {}
    for row in dsr_rows:
        d, _, received = row
        if d is None or received is None or received < six_months:
            continue
        key = f"{received.year:04d}-{received.month:02d}"
        months.setdefault(key, []).append(float(d))
    dsr_trend = [
        {
            "month": k,
            "median_days": _percentile(v, 50),
            "p90_days": _percentile(v, 90),
            "count": len(v),
        }
        for k, v in sorted(months.items())
    ]

    dsr_section = {
        "sample_size": dsr_total,
        "median_days": _percentile(dsr_days, 50),
        "p90_days": _percentile(dsr_days, 90),
        "sla_compliance_pct": round(sla_pct, 1) if sla_pct is not None else None,
        "histogram": _histogram_days(dsr_days),
        "trend": dsr_trend,
        "by_request_type": by_request_type,
    }

    dept_filter_breach = ""
    if department:
        dept_filter_breach = " AND department = :dept "
    breach_q = text(
        f"""
        SELECT EXTRACT(EPOCH FROM (authority_notified_at - discovered_at))/3600.0 AS hours_auth,
               EXTRACT(EPOCH FROM (subjects_notified_at - discovered_at))/3600.0 AS hours_subj,
               discovered_at, risk_level
        FROM data_breaches
        WHERE authority_notified_at IS NOT NULL {dept_filter_breach}
    """
    )
    breach_rows = (await db.execute(breach_q, params)).fetchall()
    auth_hours = [float(r[0]) for r in breach_rows if r[0] is not None and r[0] >= 0]
    subj_hours = [float(r[1]) for r in breach_rows if r[1] is not None and r[1] >= 0]
    breach_total = len(auth_hours)
    under_72 = sum(1 for h in auth_hours if h <= 72)
    breach_sla = (under_72 / breach_total * 100.0) if breach_total else None

    breach_months: dict[str, list[float]] = {}
    for row in breach_rows:
        h_auth, _, discovered, _ = row
        if (
            h_auth is None
            or h_auth < 0
            or discovered is None
            or discovered.date() < six_months
        ):
            continue
        key = f"{discovered.year:04d}-{discovered.month:02d}"
        breach_months.setdefault(key, []).append(float(h_auth))
    breach_trend = [
        {
            "month": k,
            "median_days": _percentile(v, 50),
            "p90_days": _percentile(v, 90),
            "count": len(v),
        }
        for k, v in sorted(breach_months.items())
    ]

    breach_section = {
        "sample_size": breach_total,
        "median_hours_to_authority": _percentile(auth_hours, 50),
        "p90_hours_to_authority": _percentile(auth_hours, 90),
        "sla_72h_compliance_pct": (
            round(breach_sla, 1) if breach_sla is not None else None
        ),
        "median_hours_to_subjects": _percentile(subj_hours, 50),
        "histogram_authority": _histogram_hours(auth_hours),
        "trend": breach_trend,
    }

    dept_filter_find = ""
    if department:
        dept_filter_find = " AND c.department = :dept "
    find_q = text(
        f"""
        SELECT f.severity, EXTRACT(EPOCH FROM (f.updated_at - f.created_at))/86400.0 AS days
        FROM findings f
        JOIN cases c ON c.id = f.case_id
        WHERE f.status IN ('fixed', 'accepted', 'overruled') {dept_filter_find}
    """
    )
    find_rows = (await db.execute(find_q, params)).fetchall()
    by_sev: dict[str, list[float]] = {}
    for row in find_rows:
        sev, d = row
        if d is None or d < 0:
            continue
        by_sev.setdefault(sev, []).append(float(d))
    findings_section = [
        {
            "severity": sev,
            "median_days": _percentile(vs, 50),
            "p90_days": _percentile(vs, 90),
            "sample_size": len(vs),
        }
        for sev, vs in sorted(by_sev.items())
    ]

    funnels = await _compute_funnels(db, department=department)

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "department_filter": department,
        "dsr": dsr_section,
        "breach": breach_section,
        "findings": findings_section,
        "funnels": funnels,
    }
