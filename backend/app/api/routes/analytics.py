"""Cross-Module-Analytics: org-Risiko, Pipeline (AVV/TOM/DSFA), Velocity, Maturity."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_roles
from app.database import get_db
from app.models.schemas import (
    MaturityStatsResponse,
    PipelineStatsResponse,
    VelocityStatsResponse,
)
from app.services.maturity_service import compute_risk_velocity, maturity_stats
from app.services.pipeline_service import pipeline_stats
from app.services.velocity_service import velocity_stats

router = APIRouter()


@router.get("/org-risk", summary="Organisations-Risikolage abrufen")
async def get_org_risk_dashboard(
    department: str | None = Query(
        default=None, description="Optional: Nur ein Department auswerten."
    ),
    db: AsyncSession = Depends(get_db),
    _user=require_roles("viewer", "editor", "admin"),
):
    """Cross-module Risiko-Aggregation pro Abteilung und org-weite KPIs."""
    params: dict = {}
    dept_filter_findings = ""
    dept_filter_breach = ""
    dept_filter_dsr = ""
    dept_filter_avv = ""
    dept_filter_cases = ""
    if department:
        params["dept"] = department
        dept_filter_findings = " AND c.department = :dept "
        dept_filter_breach = " AND department = :dept "
        dept_filter_dsr = " AND department = :dept "
        dept_filter_avv = " AND department = :dept "
        dept_filter_cases = " AND department = :dept "

    result = await db.execute(
        text(
            f"""
        WITH dept_findings AS (
            SELECT c.department,
                   SUM(CASE WHEN f.severity = 'critical' THEN 1 ELSE 0 END) AS critical_open,
                   SUM(CASE WHEN f.severity = 'high'     THEN 1 ELSE 0 END) AS high_open,
                   COUNT(*) AS total_findings
            FROM findings f
            JOIN cases c ON c.id = f.case_id
            WHERE f.status = 'open' AND c.department IS NOT NULL {dept_filter_findings}
            GROUP BY c.department
        ),
        dept_breaches AS (
            SELECT COALESCE(department, 'Unbekannt') AS department,
                   COUNT(*) AS breach_count,
                   SUM(CASE WHEN risk_level IN ('high', 'critical') THEN 1 ELSE 0 END) AS high_risk_breaches
            FROM data_breaches
            WHERE status NOT IN ('closed', 'no_notification_required')
              AND department IS NOT NULL {dept_filter_breach}
            GROUP BY department
        ),
        dept_dsr AS (
            SELECT COALESCE(department, 'Unbekannt') AS department,
                   COUNT(*) AS overdue_dsr
            FROM dsr_requests
            WHERE status NOT IN ('response_sent', 'closed', 'denied')
              AND response_deadline < CURRENT_DATE
              AND department IS NOT NULL {dept_filter_dsr}
            GROUP BY department
        ),
        dept_avv AS (
            SELECT COALESCE(department, 'Unbekannt') AS department,
                   AVG(risk_score)::float AS avg_avv_risk
            FROM avv_contracts
            WHERE department IS NOT NULL AND risk_score IS NOT NULL {dept_filter_avv}
            GROUP BY department
        ),
        dept_cases AS (
            SELECT department,
                   COUNT(*) FILTER (WHERE special_category_data)    AS special_category_count,
                   COUNT(*) FILTER (WHERE international_transfer)   AS intl_transfer_count,
                   COUNT(*) AS active_cases
            FROM cases
            WHERE status != 'completed' AND department IS NOT NULL {dept_filter_cases}
            GROUP BY department
        ),
        all_depts AS (
            SELECT department FROM dept_findings
            UNION SELECT department FROM dept_breaches
            UNION SELECT department FROM dept_dsr
            UNION SELECT department FROM dept_cases
        ),
        org_trend AS (
            SELECT TO_CHAR(DATE_TRUNC('month', f.created_at), 'YYYY-MM') AS month,
                   SUM(CASE WHEN f.severity = 'critical' THEN 1 ELSE 0 END) AS critical,
                   SUM(CASE WHEN f.severity = 'high'     THEN 1 ELSE 0 END) AS high,
                   SUM(CASE WHEN f.severity = 'medium'   THEN 1 ELSE 0 END) AS medium,
                   SUM(CASE WHEN f.severity = 'low'      THEN 1 ELSE 0 END) AS low,
                   SUM(CASE WHEN f.severity = 'info'     THEN 1 ELSE 0 END) AS info
            FROM findings f
            JOIN cases c ON c.id = f.case_id
            WHERE f.created_at >= NOW() - INTERVAL '6 months' {dept_filter_findings}
            GROUP BY DATE_TRUNC('month', f.created_at)
            ORDER BY 1 ASC
        )
        SELECT 'dept' AS qname,
               d.department,
               COALESCE(df.critical_open, 0)       AS critical_open,
               COALESCE(df.high_open, 0)            AS high_open,
               COALESCE(db.breach_count, 0)         AS active_breaches,
               COALESCE(dd.overdue_dsr, 0)          AS overdue_dsr,
               da.avg_avv_risk,
               COALESCE(dc.special_category_count, 0) AS special_category,
               COALESCE(dc.intl_transfer_count, 0)  AS intl_transfer,
               COALESCE(dc.active_cases, 0)         AS active_cases
        FROM all_depts d
        LEFT JOIN dept_findings  df ON df.department  = d.department
        LEFT JOIN dept_breaches  db ON db.department  = d.department
        LEFT JOIN dept_dsr       dd ON dd.department  = d.department
        LEFT JOIN dept_avv       da ON da.department  = d.department
        LEFT JOIN dept_cases     dc ON dc.department  = d.department
        UNION ALL
        SELECT 'trend', month,
               critical, high, medium, low, info, 0, 0, 0
        FROM org_trend
    """
        ),
        params,
    )
    rows = result.fetchall()

    dept_rows = []
    trend: list[dict] = []
    total_critical = 0
    total_breaches = 0
    total_overdue_dsr = 0

    for row in rows:
        qname = row[0]
        if qname == "dept":
            (
                _,
                dept,
                crit,
                high,
                breaches,
                overdue,
                avg_avv,
                special_cat,
                intl,
                active_cases,
            ) = row
            composite = min(
                100,
                int(
                    (crit or 0) * 25
                    + (high or 0) * 10
                    + (breaches or 0) * 15
                    + (overdue or 0) * 8
                    + ((avg_avv or 0) * 0.3)
                ),
            )
            dept_rows.append(
                {
                    "department": dept,
                    "critical_open_findings": int(crit or 0),
                    "high_open_findings": int(high or 0),
                    "active_breaches": int(breaches or 0),
                    "overdue_dsr": int(overdue or 0),
                    "avg_avv_risk_score": (
                        round(float(avg_avv), 1) if avg_avv is not None else None
                    ),
                    "special_category_cases": int(special_cat or 0),
                    "intl_transfer_cases": int(intl or 0),
                    "active_cases": int(active_cases or 0),
                    "composite_risk_score": composite,
                }
            )
            total_critical += int(crit or 0)
            total_breaches += int(breaches or 0)
            total_overdue_dsr += int(overdue or 0)
        elif qname == "trend":
            _, month, critical, high, medium, low, info, *_ = row
            trend.append(
                {
                    "month": month,
                    "critical": int(critical or 0),
                    "high": int(high or 0),
                    "medium": int(medium or 0),
                    "low": int(low or 0),
                    "info": int(info or 0),
                }
            )

    dept_rows.sort(key=lambda r: r["composite_risk_score"], reverse=True)
    top_risk_departments = [
        r["department"] for r in dept_rows[:5] if r["composite_risk_score"] > 0
    ]

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "department_filter": department,
        "dept_risk": dept_rows,
        "top_risk_departments": top_risk_departments,
        "org_findings_trend": trend,
        "total_open_critical": total_critical,
        "total_active_breaches": total_breaches,
        "total_overdue_dsr": total_overdue_dsr,
        "departments_at_risk": sum(
            1 for r in dept_rows if r["composite_risk_score"] >= 25
        ),
    }


@router.get(
    "/pipeline",
    response_model=PipelineStatsResponse,
    summary="Lifecycle-Pipeline (AVV/TOM/DSFA) abrufen",
)
async def get_pipeline_stats(
    department: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _user=require_roles("viewer", "editor", "admin"),
):
    """AVV-Ablauf-Pipeline + TOM-Reviews + DSFA-Coverage fuer high-risk Cases."""
    return PipelineStatsResponse(**await pipeline_stats(db, department=department))


@router.get(
    "/velocity",
    response_model=VelocityStatsResponse,
    summary="Bearbeitungs-Velocity (Time-to-X) abrufen",
)
async def get_velocity_stats(
    department: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _user=require_roles("viewer", "editor", "admin"),
):
    """DSR-MTTR + Breach-Notification-Speed + Findings-Resolution + Workflow-Funnels."""
    return VelocityStatsResponse(**await velocity_stats(db, department=department))


@router.get(
    "/maturity",
    response_model=MaturityStatsResponse,
    summary="Compliance-Reife pro Abteilung abrufen",
)
async def get_maturity_stats(
    department: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _user=require_roles("viewer", "editor", "admin"),
):
    """Maturity-Score (5 Sub-Scores, gewichtet) + 6-Monats-Trend aus taeglichen Snapshots."""
    return MaturityStatsResponse(**await maturity_stats(db, department=department))


@router.get(
    "/risk-velocity",
    summary="Risiko-Trend pro Abteilung (Composite + Sub-Scores)",
)
async def get_risk_velocity(
    department: str | None = Query(
        default=None, description="Optional: Nur ein Department auswerten."
    ),
    window_days: int | None = Query(
        default=None,
        ge=1,
        le=365,
        description="Vergleichsfenster in Tagen (überschreibt risk_velocity.window_days).",
    ),
    db: AsyncSession = Depends(get_db),
    _user=require_roles("viewer", "editor", "admin"),
):
    """Vergleicht den aktuellen Compliance-Reife-Score gegen den Wert vor
    `window_days` (Default aus `risk_config.yaml -> risk_velocity.window_days`).

    Antwort enthält pro Department Composite-Score plus Trend (up/down/stable)
    für jeden Sub-Score (vvt/dsfa/avv/tom/velocity). Datenquelle:
    `compliance_maturity_snapshots`.
    """
    return await compute_risk_velocity(
        db, department=department, window_days=window_days
    )
