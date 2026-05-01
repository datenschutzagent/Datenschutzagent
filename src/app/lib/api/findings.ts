/**
 * Findings API: CRUD, bulk status updates, exports, due dates,
 * comments, playbook coverage preview, and case similarity.
 */

import {
  API_BASE,
  API_PREFIX,
  deepSnakeToCamel,
  fetchBlob,
  request,
} from "./core";
import type { ApiFinding, FindingStatus } from "./cases";

function mapFinding(d: Record<string, unknown>): Record<string, unknown> {
  return deepSnakeToCamel(d) as Record<string, unknown>;
}

export async function updateFindingStatus(findingId: string, status: FindingStatus): Promise<ApiFinding> {
  const f = await request<Record<string, unknown>>("PATCH", `/findings/${findingId}`, {
    body: { status },
  });
  return mapFinding(f) as ApiFinding;
}

export interface FindingListParams {
  case_id?: string;
  severity?: string;
  status?: string;
  category?: string;
  limit?: number;
  offset?: number;
}

export interface FindingListResult {
  items: ApiFinding[];
  total: number;
}

export async function listFindings(params: FindingListParams): Promise<FindingListResult> {
  const q = new URLSearchParams();
  if (params.case_id) q.set("case_id", params.case_id);
  if (params.severity) q.set("severity", params.severity);
  if (params.status) q.set("status", params.status);
  if (params.category) q.set("category", params.category);
  if (params.limit != null) q.set("limit", String(params.limit));
  if (params.offset != null) q.set("offset", String(params.offset));
  const raw = await request<{ items: Record<string, unknown>[]; total: number }>(
    "GET",
    `/findings?${q.toString()}`
  );
  return {
    items: raw.items.map((f) => mapFinding(f) as ApiFinding),
    total: raw.total,
  };
}

export async function bulkUpdateFindingStatus(
  findingIds: string[],
  status: FindingStatus
): Promise<{ updated: number }> {
  return request<{ updated: number }>("PATCH", "/findings/bulk-update", {
    body: { finding_ids: findingIds, status },
  });
}

export async function downloadFindingsExport(
  caseId: string,
  filters?: { severity?: string; status?: string; category?: string; format?: "csv" | "docx" }
): Promise<Blob> {
  const q = new URLSearchParams({ case_id: caseId });
  if (filters?.severity) q.set("severity", filters.severity);
  if (filters?.status) q.set("status", filters.status);
  if (filters?.category) q.set("category", filters.category);
  if (filters?.format) q.set("format", filters.format);
  return fetchBlob(`${API_BASE}${API_PREFIX}/findings/export?${q.toString()}`);
}

export async function downloadAllFindingsExport(
  filters?: { severity?: string; status?: string; category?: string; format?: "csv" | "docx" }
): Promise<Blob> {
  const q = new URLSearchParams();
  if (filters?.severity) q.set("severity", filters.severity);
  if (filters?.status) q.set("status", filters.status);
  if (filters?.category) q.set("category", filters.category);
  if (filters?.format) q.set("format", filters.format);
  return fetchBlob(`${API_BASE}${API_PREFIX}/findings/export?${q.toString()}`);
}

// --- Finding due date ---
export async function updateFindingDueDate(findingId: string, status: FindingStatus, dueDate: string | null): Promise<ApiFinding> {
  const body: Record<string, unknown> = { status };
  if (dueDate !== undefined) body.due_date = dueDate;
  const f = await request<Record<string, unknown>>("PATCH", `/findings/${findingId}`, { body });
  return mapFinding(f) as ApiFinding;
}

// --- Finding comments ---
export interface ApiFindingComment {
  id: string;
  finding_id: string;
  case_id: string;
  author: string;
  user_id: string | null;
  text: string;
  created_at: string;
}

export async function getFindingComments(findingId: string): Promise<ApiFindingComment[]> {
  const list = (await request<Record<string, unknown>[]>("GET", `/findings/${findingId}/comments`)) ?? [];
  return list.map((c) => ({
    id: c.id as string,
    finding_id: c.finding_id as string,
    case_id: c.case_id as string,
    author: (c.author as string) ?? "",
    user_id: (c.user_id as string) ?? null,
    text: (c.text as string) ?? "",
    created_at: (c.created_at as string) ?? "",
  }));
}

export async function createFindingComment(findingId: string, text: string): Promise<ApiFindingComment> {
  const c = await request<Record<string, unknown>>("POST", `/findings/${findingId}/comments`, { body: { text } });
  return {
    id: c.id as string,
    finding_id: c.finding_id as string,
    case_id: c.case_id as string,
    author: (c.author as string) ?? "",
    user_id: (c.user_id as string) ?? null,
    text: (c.text as string) ?? "",
    created_at: (c.created_at as string) ?? "",
  };
}

// --- Findings stats ---

export interface FindingTrendItem {
  month: string;
  critical: number;
  high: number;
  medium: number;
  low: number;
  info: number;
}

export interface FindingsByDepartment {
  department: string;
  total: number;
  critical: number;
  high: number;
  medium: number;
  low: number;
  info: number;
}

export interface TopFailingCheck {
  checkName: string;
  category: string;
  count: number;
  severityBreakdown: Record<string, number>;
}

export interface ResolutionVelocityItem {
  severity: string;
  avgDaysToFix: number;
  sampleSize: number;
}

export interface FindingStatsResult {
  bySeverity: Record<string, number>;
  byCategory: Record<string, number>;
  byDepartment: FindingsByDepartment[];
  topFailingChecks: TopFailingCheck[];
  trend: FindingTrendItem[];
  resolutionVelocity: ResolutionVelocityItem[];
}

export async function getFindingStats(): Promise<FindingStatsResult> {
  const raw = await request<Record<string, unknown>>("GET", "/findings/stats");
  return {
    bySeverity: (raw.by_severity ?? {}) as Record<string, number>,
    byCategory: (raw.by_category ?? {}) as Record<string, number>,
    byDepartment: ((raw.by_department ?? []) as Record<string, unknown>[]).map((d) => ({
      department: d.department as string,
      total: Number(d.total ?? 0),
      critical: Number(d.critical ?? 0),
      high: Number(d.high ?? 0),
      medium: Number(d.medium ?? 0),
      low: Number(d.low ?? 0),
      info: Number(d.info ?? 0),
    })),
    topFailingChecks: ((raw.top_failing_checks ?? []) as Record<string, unknown>[]).map((c) => ({
      checkName: c.check_name as string,
      category: c.category as string,
      count: Number(c.count ?? 0),
      severityBreakdown: (c.severity_breakdown ?? {}) as Record<string, number>,
    })),
    trend: ((raw.trend ?? []) as Record<string, unknown>[]).map((t) => ({
      month: t.month as string,
      critical: Number(t.critical ?? 0),
      high: Number(t.high ?? 0),
      medium: Number(t.medium ?? 0),
      low: Number(t.low ?? 0),
      info: Number(t.info ?? 0),
    })),
    resolutionVelocity: ((raw.resolution_velocity ?? []) as Record<string, unknown>[]).map((v) => ({
      severity: v.severity as string,
      avgDaysToFix: Number(v.avg_days_to_fix ?? 0),
      sampleSize: Number(v.sample_size ?? 0),
    })),
  };
}

// --- Playbook coverage preview ---
export interface PlaybookCoverageItem {
  name: string;
  category: string;
  scope: string;
  applicable: boolean;
  reason: string;
}

export interface PlaybookCoverage {
  playbook_id: string;
  case_id: string;
  total_checks: number;
  applicable_count: number;
  checks: PlaybookCoverageItem[];
  missing_document_types: string[];
}

export async function getPlaybookCoveragePreview(playbookId: string, caseId: string): Promise<PlaybookCoverage> {
  return request<PlaybookCoverage>("GET", `/playbooks/${playbookId}/coverage-preview?case_id=${caseId}`);
}
