"""Pydantic-Schemas fuer Cross-Module-Analytics (Pipeline, Velocity, Maturity)."""
from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# Pipeline (AVV / TOM / DSFA Lifecycle)
# ---------------------------------------------------------------------------


class AVVPipelineBucket(BaseModel):
    bucket: str
    label: str
    count: int
    avg_risk_score: float | None = None


class AVVPipelineExpiringItem(BaseModel):
    id: str
    partner_name: str
    department: str | None
    expiry_date: str | None
    days_until_expiry: int | None
    risk_level: str | None
    status: str


class AVVPipelineSection(BaseModel):
    buckets: list[AVVPipelineBucket]
    expiring_soon: list[AVVPipelineExpiringItem]
    total: int


class TOMReviewBucket(BaseModel):
    bucket: str
    label: str
    count: int


class TOMReviewByCategory(BaseModel):
    category: str
    overdue: int
    upcoming: int
    total: int


class TOMReviewSection(BaseModel):
    overdue_total: int
    upcoming_total: int
    no_review_date_total: int
    review_governance_pct: float
    by_category: list[TOMReviewByCategory]
    overdue_items: list[dict]


class DSFACoverageItem(BaseModel):
    case_id: str
    title: str
    department: str | None
    special_category_data: bool
    international_transfer: bool
    has_draft: bool


class DSFASection(BaseModel):
    high_risk_total: int
    with_finalized: int
    with_draft_only: int
    without_dsfa: int
    coverage_pct: float
    missing_items: list[DSFACoverageItem]


class PipelineStatsResponse(BaseModel):
    generated_at: str
    department_filter: str | None = None
    avv: AVVPipelineSection
    tom: TOMReviewSection
    dsfa: DSFASection


# ---------------------------------------------------------------------------
# Velocity (Time-to-X / Workflow)
# ---------------------------------------------------------------------------


class MttrHistogramBucket(BaseModel):
    bucket: str
    count: int


class MttrTrendItem(BaseModel):
    month: str
    median_days: float | None
    p90_days: float | None
    count: int


class DSRVelocity(BaseModel):
    sample_size: int
    median_days: float | None
    p90_days: float | None
    sla_compliance_pct: float | None
    histogram: list[MttrHistogramBucket]
    trend: list[MttrTrendItem]
    by_request_type: list[dict]


class BreachVelocity(BaseModel):
    sample_size: int
    median_hours_to_authority: float | None
    p90_hours_to_authority: float | None
    sla_72h_compliance_pct: float | None
    median_hours_to_subjects: float | None
    histogram_authority: list[MttrHistogramBucket]
    trend: list[MttrTrendItem]


class FindingVelocityItem(BaseModel):
    severity: str
    median_days: float | None
    p90_days: float | None
    sample_size: int


class WorkflowFunnelStep(BaseModel):
    transition: str
    avg_hours: float | None
    median_hours: float | None
    sample_size: int


class WorkflowFunnel(BaseModel):
    entity: str
    steps: list[WorkflowFunnelStep]


class VelocityStatsResponse(BaseModel):
    generated_at: str
    department_filter: str | None = None
    dsr: DSRVelocity
    breach: BreachVelocity
    findings: list[FindingVelocityItem]
    funnels: list[WorkflowFunnel]


# ---------------------------------------------------------------------------
# Maturity (Compliance-Reife)
# ---------------------------------------------------------------------------


class MaturitySubScores(BaseModel):
    vvt_score: float
    dsfa_score: float
    avv_score: float
    tom_score: float
    velocity_score: float


class MaturityDeptRow(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    department: str
    sub_scores: MaturitySubScores
    composite_score: float
    delta_3m: float | None = None


class MaturityTrendPoint(BaseModel):
    date: str
    composite_score: float
    department: str


class MaturityImproverItem(BaseModel):
    department: str
    delta: float
    current: float
    previous: float


class MaturityWeights(BaseModel):
    vvt: float
    dsfa: float
    avv: float
    tom: float
    velocity: float


class MaturityStatsResponse(BaseModel):
    generated_at: str
    department_filter: str | None = None
    weights: MaturityWeights
    departments: list[MaturityDeptRow]
    trend: list[MaturityTrendPoint]
    improvers: list[MaturityImproverItem]
    decliners: list[MaturityImproverItem]
    has_history: bool
