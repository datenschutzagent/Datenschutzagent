"""AVV/TOM/DSFA lifecycle-pipeline statistics."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

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
