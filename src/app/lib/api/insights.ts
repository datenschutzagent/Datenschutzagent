/**
 * Insights API: Pipeline (AVV/TOM/DSFA), Velocity (Time-to-X), Maturity (Reife).
 * Dunne Wrapper auf /analytics/* mit camelCase-Konvertierung.
 */

import { deepSnakeToCamel, request } from "./core";

// ---------------------------------------------------------------------------
// Pipeline
// ---------------------------------------------------------------------------

export interface AvvBucket {
  bucket: string;
  label: string;
  count: number;
  avgRiskScore: number | null;
}

export interface AvvExpiringItem {
  id: string;
  partnerName: string;
  department: string | null;
  expiryDate: string | null;
  daysUntilExpiry: number | null;
  riskLevel: string | null;
  status: string;
}

export interface TomReviewByCategory {
  category: string;
  overdue: number;
  upcoming: number;
  total: number;
}

export interface TomOverdueItem {
  id: string;
  title: string;
  category: string;
  reviewDate: string;
  daysOverdue: number;
  status: string;
}

export interface DsfaCoverageItem {
  caseId: string;
  title: string;
  department: string | null;
  specialCategoryData: boolean;
  internationalTransfer: boolean;
  hasDraft: boolean;
}

export interface PipelineStats {
  generatedAt: string;
  departmentFilter: string | null;
  avv: {
    buckets: AvvBucket[];
    expiringSoon: AvvExpiringItem[];
    total: number;
  };
  tom: {
    overdueTotal: number;
    upcomingTotal: number;
    noReviewDateTotal: number;
    reviewGovernancePct: number;
    byCategory: TomReviewByCategory[];
    overdueItems: TomOverdueItem[];
  };
  dsfa: {
    highRiskTotal: number;
    withFinalized: number;
    withDraftOnly: number;
    withoutDsfa: number;
    coveragePct: number;
    missingItems: DsfaCoverageItem[];
  };
}

// ---------------------------------------------------------------------------
// Velocity
// ---------------------------------------------------------------------------

export interface MttrHistogramBucket {
  bucket: string;
  count: number;
}

export interface MttrTrendItem {
  month: string;
  medianDays: number | null;
  p90Days: number | null;
  count: number;
}

export interface DsrByRequestType {
  requestType: string;
  sampleSize: number;
  medianDays: number | null;
  p90Days: number | null;
}

export interface DsrVelocity {
  sampleSize: number;
  medianDays: number | null;
  p90Days: number | null;
  slaCompliancePct: number | null;
  histogram: MttrHistogramBucket[];
  trend: MttrTrendItem[];
  byRequestType: DsrByRequestType[];
}

export interface BreachVelocity {
  sampleSize: number;
  medianHoursToAuthority: number | null;
  p90HoursToAuthority: number | null;
  sla72hCompliancePct: number | null;
  medianHoursToSubjects: number | null;
  histogramAuthority: MttrHistogramBucket[];
  trend: MttrTrendItem[];
}

export interface FindingVelocityItem {
  severity: string;
  medianDays: number | null;
  p90Days: number | null;
  sampleSize: number;
}

export interface WorkflowFunnelStep {
  transition: string;
  avgHours: number | null;
  medianHours: number | null;
  sampleSize: number;
}

export interface WorkflowFunnel {
  entity: string;
  steps: WorkflowFunnelStep[];
}

export interface VelocityStats {
  generatedAt: string;
  departmentFilter: string | null;
  dsr: DsrVelocity;
  breach: BreachVelocity;
  findings: FindingVelocityItem[];
  funnels: WorkflowFunnel[];
}

// ---------------------------------------------------------------------------
// Maturity
// ---------------------------------------------------------------------------

export interface MaturitySubScores {
  vvtScore: number;
  dsfaScore: number;
  avvScore: number;
  tomScore: number;
  velocityScore: number;
}

export interface MaturityDeptRow {
  department: string;
  subScores: MaturitySubScores;
  compositeScore: number;
  delta3m: number | null;
}

export interface MaturityTrendPoint {
  date: string;
  compositeScore: number;
  department: string;
}

export interface MaturityImproverItem {
  department: string;
  delta: number;
  current: number;
  previous: number;
}

export interface MaturityWeights {
  vvt: number;
  dsfa: number;
  avv: number;
  tom: number;
  velocity: number;
}

export interface MaturityStats {
  generatedAt: string;
  departmentFilter: string | null;
  weights: MaturityWeights;
  departments: MaturityDeptRow[];
  trend: MaturityTrendPoint[];
  improvers: MaturityImproverItem[];
  decliners: MaturityImproverItem[];
  hasHistory: boolean;
}

// ---------------------------------------------------------------------------
// API
// ---------------------------------------------------------------------------

function buildPath(base: string, department?: string | null): string {
  if (!department) return base;
  return `${base}?department=${encodeURIComponent(department)}`;
}

export async function fetchPipelineStats(department?: string | null): Promise<PipelineStats> {
  const raw = await request<Record<string, unknown>>("GET", buildPath("/analytics/pipeline", department));
  return deepSnakeToCamel(raw) as unknown as PipelineStats;
}

export async function fetchVelocityStats(department?: string | null): Promise<VelocityStats> {
  const raw = await request<Record<string, unknown>>("GET", buildPath("/analytics/velocity", department));
  return deepSnakeToCamel(raw) as unknown as VelocityStats;
}

export async function fetchMaturityStats(department?: string | null): Promise<MaturityStats> {
  const raw = await request<Record<string, unknown>>("GET", buildPath("/analytics/maturity", department));
  return deepSnakeToCamel(raw) as unknown as MaturityStats;
}

// ---------------------------------------------------------------------------
// Risk-Velocity (Compliance-Reife-Trend pro Department)
// ---------------------------------------------------------------------------

export type RiskTrend = "up" | "down" | "stable" | "unknown";

export interface RiskVelocitySubScore {
  current: number;
  previous: number | null;
  delta: number | null;
  trend: RiskTrend;
}

export interface RiskVelocityRow {
  department: string;
  currentComposite: number;
  previousComposite: number | null;
  delta: number | null;
  trend: RiskTrend;
  significant: boolean;
  currentSnapshotDate: string;
  previousSnapshotDate: string | null;
  subScores: {
    vvt: RiskVelocitySubScore;
    dsfa: RiskVelocitySubScore;
    avv: RiskVelocitySubScore;
    tom: RiskVelocitySubScore;
    velocity: RiskVelocitySubScore;
  };
}

export interface RiskVelocityResponse {
  generatedAt: string;
  windowDays: number;
  enabled: boolean;
  significantChangePct: number;
  departmentFilter: string | null;
  departments: RiskVelocityRow[];
}

export async function fetchRiskVelocity(opts?: {
  department?: string | null;
  windowDays?: number | null;
}): Promise<RiskVelocityResponse> {
  const params = new URLSearchParams();
  if (opts?.department) params.set("department", opts.department);
  if (opts?.windowDays != null) params.set("window_days", String(opts.windowDays));
  const qs = params.toString();
  const path = qs ? `/analytics/risk-velocity?${qs}` : "/analytics/risk-velocity";
  const raw = await request<Record<string, unknown>>("GET", path);
  return deepSnakeToCamel(raw) as unknown as RiskVelocityResponse;
}
