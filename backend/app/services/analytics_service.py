"""Cross-Module-Analytics: Pipeline (AVV/TOM/DSFA), Velocity (Time-to-X), Maturity (Reife).

Bundelt SQL-Aggregationen, die zuvor verstreut in den Routen-Dateien lagen, an einem Ort.
Jede Funktion liefert ein typisiertes Dict, das direkt in eine Pydantic-Response gegossen wird.
"""

from __future__ import annotations

import statistics
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.risk_config_loader import get_risk_config

# ---------------------------------------------------------------------------
# Maturity-Score: Gewichtung der Sub-Scores.
#
# Werte werden zur Laufzeit aus RiskConfig.maturity.weights gelesen, siehe
# risk_config_loader.py / risk_config.yaml. Die Konstante hier ist nur ein
# Fallback-Default, falls die Config nicht erreichbar ist (z.B. in Pure-Tests).
# ---------------------------------------------------------------------------

MATURITY_WEIGHTS: dict[str, float] = {
    "vvt": 0.20,
    "dsfa": 0.20,
    "avv": 0.20,
    "tom": 0.20,
    "velocity": 0.20,
}


def _velocity_score(median_days: float, optimal_days: int, worst_days: int) -> float:
    """Linear interpolation: optimal_days -> 100, worst_days -> 0."""
    span = worst_days - optimal_days
    if span <= 0:
        return 100.0 if median_days <= optimal_days else 0.0
    return max(0.0, min(100.0, 100.0 * (worst_days - median_days) / span))


# ---------------------------------------------------------------------------
# Pipeline (AVV / TOM / DSFA)
# ---------------------------------------------------------------------------


_AVV_BUCKETS: list[tuple[str, str]] = [
    ("overdue", "Überfällig"),
    ("0_30", "≤ 30 Tage"),
    ("31_90", "31–90 Tage"),
    ("91_180", "91–180 Tage"),
    ("180_plus", "> 180 Tage"),
    ("undated", "Unbefristet"),
]


def _avv_bucket(days_until: int | None, status: str) -> str:
    if status == "expired":
        return "overdue"
    if days_until is None:
        return "undated"
    if days_until < 0:
        return "overdue"
    if days_until <= 30:
        return "0_30"
    if days_until <= 90:
        return "31_90"
    if days_until <= 180:
        return "91_180"
    return "180_plus"


async def pipeline_stats(
    db: AsyncSession, department: str | None = None
) -> dict[str, Any]:
    """AVV-Ablauf-Pipeline + TOM-Review-Pipeline + DSFA-Coverage fuer high-risk Cases."""
    today = date.today()

    dept_filter = ""
    if department:
        dept_filter = " AND department = :dept "

    # AVV: alle relevanten Vertrage holen, im Python in Buckets sortieren.
    avv_q = text(
        f"""
        SELECT id, partner_name, department, status, expiry_date, risk_level, risk_score
        FROM avv_contracts
        WHERE 1=1 {dept_filter}
    """
    )
    params: dict[str, Any] = {}
    if department:
        params["dept"] = department
    avv_rows = (await db.execute(avv_q, params)).fetchall()

    bucket_counts: dict[str, int] = {b[0]: 0 for b in _AVV_BUCKETS}
    bucket_risks: dict[str, list[int]] = {b[0]: [] for b in _AVV_BUCKETS}
    expiring_items: list[dict] = []

    for row in avv_rows:
        avv_id, partner, dept, status, expiry, risk_level, risk_score = row
        days_until: int | None = None
        if expiry is not None:
            days_until = (expiry - today).days
        bucket = _avv_bucket(days_until, status)
        bucket_counts[bucket] += 1
        if risk_score is not None:
            bucket_risks[bucket].append(int(risk_score))
        if (
            status not in ("terminated",)
            and days_until is not None
            and -30 <= days_until <= 180
        ):
            expiring_items.append(
                {
                    "id": str(avv_id),
                    "partner_name": partner,
                    "department": dept,
                    "expiry_date": expiry.isoformat() if expiry else None,
                    "days_until_expiry": days_until,
                    "risk_level": risk_level,
                    "status": status,
                }
            )

    expiring_items.sort(
        key=lambda r: (
            r["days_until_expiry"] if r["days_until_expiry"] is not None else 9999
        )
    )
    expiring_items = expiring_items[:10]

    avv_buckets = []
    for key, label in _AVV_BUCKETS:
        risks = bucket_risks[key]
        avv_buckets.append(
            {
                "bucket": key,
                "label": label,
                "count": bucket_counts[key],
                "avg_risk_score": round(sum(risks) / len(risks), 1) if risks else None,
            }
        )

    # TOM: Reviews nach Kategorie auswerten.
    tom_dept_filter = ""
    if department:
        tom_dept_filter = " AND :dept = ANY(department_codes) "
    tom_q = text(
        f"""
        SELECT category,
               implementation_status,
               review_date,
               title,
               id
        FROM tom_measures
        WHERE implementation_status != 'not_applicable' {tom_dept_filter}
    """
    )
    tom_rows = (await db.execute(tom_q, params)).fetchall()

    by_cat: dict[str, dict[str, int]] = {}
    overdue_total = 0
    upcoming_total = 0
    no_review_total = 0
    overdue_items: list[dict] = []

    for row in tom_rows:
        cat, status, review, title, tom_id = row
        cat = cat or "unknown"
        if cat not in by_cat:
            by_cat[cat] = {"overdue": 0, "upcoming": 0, "total": 0}
        by_cat[cat]["total"] += 1
        if review is None:
            no_review_total += 1
            continue
        days_until = (review - today).days
        if days_until < 0:
            by_cat[cat]["overdue"] += 1
            overdue_total += 1
            overdue_items.append(
                {
                    "id": str(tom_id),
                    "title": title,
                    "category": cat,
                    "review_date": review.isoformat(),
                    "days_overdue": -days_until,
                    "status": status,
                }
            )
        elif days_until <= 30:
            by_cat[cat]["upcoming"] += 1
            upcoming_total += 1

    overdue_items.sort(key=lambda r: r["days_overdue"], reverse=True)
    overdue_items = overdue_items[:10]

    by_category = [
        {"category": cat, **counts} for cat, counts in sorted(by_cat.items())
    ]

    total_tom_relevant = sum(c["total"] for c in by_cat.values())
    review_governance_pct = (
        ((total_tom_relevant - no_review_total) / total_tom_relevant * 100.0)
        if total_tom_relevant > 0
        else 0.0
    )

    # DSFA: high-risk Cases, die KEIN finalisiertes Assessment haben.
    case_dept_filter = ""
    if department:
        case_dept_filter = " AND c.department = :dept "
    dsfa_q = text(
        f"""
        SELECT c.id, c.title, c.department, c.special_category_data, c.international_transfer,
               d.status AS dsfa_status
        FROM cases c
        LEFT JOIN dsfa_assessments d ON d.case_id = c.id
        WHERE (c.special_category_data = TRUE OR c.international_transfer = TRUE)
          AND c.archived_at IS NULL
          {case_dept_filter}
    """
    )
    dsfa_rows = (await db.execute(dsfa_q, params)).fetchall()

    high_risk_total = len(dsfa_rows)
    with_finalized = 0
    with_draft_only = 0
    without_dsfa = 0
    missing_items: list[dict] = []

    for row in dsfa_rows:
        case_id, title, dept, special, intl, dsfa_status = row
        if dsfa_status == "finalized":
            with_finalized += 1
        elif dsfa_status == "draft":
            with_draft_only += 1
            missing_items.append(
                {
                    "case_id": str(case_id),
                    "title": title,
                    "department": dept,
                    "special_category_data": bool(special),
                    "international_transfer": bool(intl),
                    "has_draft": True,
                }
            )
        else:
            without_dsfa += 1
            missing_items.append(
                {
                    "case_id": str(case_id),
                    "title": title,
                    "department": dept,
                    "special_category_data": bool(special),
                    "international_transfer": bool(intl),
                    "has_draft": False,
                }
            )

    missing_items = missing_items[:25]
    coverage_pct = (
        (with_finalized / high_risk_total * 100.0) if high_risk_total > 0 else 100.0
    )

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "department_filter": department,
        "avv": {
            "buckets": avv_buckets,
            "expiring_soon": expiring_items,
            "total": len(avv_rows),
        },
        "tom": {
            "overdue_total": overdue_total,
            "upcoming_total": upcoming_total,
            "no_review_date_total": no_review_total,
            "review_governance_pct": round(review_governance_pct, 1),
            "by_category": by_category,
            "overdue_items": overdue_items,
        },
        "dsfa": {
            "high_risk_total": high_risk_total,
            "with_finalized": with_finalized,
            "with_draft_only": with_draft_only,
            "without_dsfa": without_dsfa,
            "coverage_pct": round(coverage_pct, 1),
            "missing_items": missing_items,
        },
    }


# ---------------------------------------------------------------------------
# Velocity (Time-to-X)
# ---------------------------------------------------------------------------


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


async def velocity_stats(
    db: AsyncSession, department: str | None = None
) -> dict[str, Any]:
    """DSR-MTTR + Breach-Notification-Speed + Findings-Resolution + Workflow-Funnels."""
    params: dict[str, Any] = {}
    dept_filter_dsr = ""
    if department:
        dept_filter_dsr = " AND department = :dept "
        params["dept"] = department

    # --- DSR-MTTR ---
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

    # Trend: pro Monat der letzten 6 Monate.
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

    # --- Breach Notification Speed ---
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

    # --- Findings Resolution Velocity ---
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

    # --- Workflow-Funnels aus Activity-Logs ---
    funnels = await _compute_funnels(db, department=department)

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "department_filter": department,
        "dsr": dsr_section,
        "breach": breach_section,
        "findings": findings_section,
        "funnels": funnels,
    }


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


# ---------------------------------------------------------------------------
# Maturity (Compliance-Reife)
# ---------------------------------------------------------------------------


async def compute_maturity_scores(db: AsyncSession) -> list[dict[str, Any]]:
    """Berechnet pro Department alle Sub-Scores + Composite (live, ohne Snapshots)."""
    # Alle Departments einsammeln, die in irgendeinem relevanten Modell vorkommen.
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

    # 1) VVT-Coverage: Cases mit `has_vvt`-Flag — naehere uns ueber Cases-Status / VVT-Dokumente.
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

    # 2) DSFA-Coverage: high-risk Cases mit finalisierter DSFA.
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
        # Wenn keine high-risk Cases existieren, ist die Coverage 100% (kein Defizit).
        dsfa_map[dept] = (with_dsfa / hr * 100.0) if hr > 0 else 100.0

    # 3) AVV-Status: Anteil aktive Vertraege mit aktueller Risikobewertung (<= 12 Monate).
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

    # 4) TOM-Implementation: Anteil 'implemented' an relevanten TOMs (excl. not_applicable).
    #    Gewichtet ueber department_codes (ARRAY).
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

    # 5) Velocity: Score 100 bei Median DSR <= optimal_days, 0 bei >= worst_days
    # (linear interpoliert). Schwellen aus RiskConfig.maturity.velocity.
    maturity_cfg = get_risk_config().maturity
    # received_at/responded_at are DATE columns: date - date already yields whole days
    # (integer) in Postgres; EXTRACT(EPOCH FROM ...) on that integer is an error.
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

    # Trend aus Snapshot-Tabelle.
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

    # Improver/Decliner: Δ ggue. Wert vor 90 Tagen.
    if has_history:
        ninety_days_ago = date.today() - timedelta(days=90)
        # Pro Dept den jeweils naechstgelegenen Snapshot vor 90 Tagen.
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


# ---------------------------------------------------------------------------
# Risk-Velocity (historische Trend-Analyse pro Sub-Score)
# ---------------------------------------------------------------------------

_RISK_VELOCITY_SUBSCORES = ("vvt", "dsfa", "avv", "tom", "velocity")


def _classify_trend(delta_pct: float, threshold_pct: float) -> str:
    """Return 'up' | 'down' | 'stable' depending on whether |delta| exceeds threshold."""
    if abs(delta_pct) < threshold_pct:
        return "stable"
    return "up" if delta_pct > 0 else "down"


async def compute_risk_velocity(
    db: AsyncSession,
    department: str | None = None,
    window_days: int | None = None,
) -> dict[str, Any]:
    """Vergleicht aktuellen Composite/Sub-Score mit dem Wert vor window_days.

    Datenquelle: `compliance_maturity_snapshots`. Pro Department wird der
    jüngste Snapshot und der dem cutoff am nächsten liegende ältere Snapshot
    geladen. Bewegungen über `risk_velocity.significant_change_pct` werden
    als up/down klassifiziert, sonst stable.

    Returns dict mit Feldern `generated_at`, `window_days`, `enabled`,
    `significant_change_pct` und `departments` (Liste mit current/previous/
    delta/trend pro Sub-Score).
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

    # Jüngster Snapshot pro Department (immer im Vergleichsfenster).
    current_q = text(
        f"""
        SELECT DISTINCT ON (department) department, snapshot_date,
            composite_score, {score_columns}
        FROM compliance_maturity_snapshots
        WHERE 1=1 {dept_filter}
        ORDER BY department, snapshot_date DESC
    """
    )
    # Ältester Snapshot pro Department vor/an der cutoff-Linie.
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

    departments: list[dict[str, Any]] = []
    for dept in sorted(current_map.keys()):
        cur = current_map[dept]
        prev = previous_map.get(dept)
        if prev is None:
            # Kein Vergleichswert vorhanden — Trend "unknown", stable.
            departments.append(
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
        departments.append(
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
        "departments": departments,
    }
