/**
 * Findings API: CRUD, bulk status updates, exports, due dates,
 * comments, playbook coverage preview, and case similarity.
 */

import {
  API_BASE,
  API_PREFIX,
  authHeaders,
  deepSnakeToCamel,
  parseErrorResponse,
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
  const url = `${API_BASE}${API_PREFIX}/findings/export?${q.toString()}`;
  const res = await fetch(url, { headers: { ...authHeaders() } });
  if (!res.ok) {
    const detail = await parseErrorResponse(res);
    throw new Error(detail);
  }
  return res.blob();
}

export async function downloadAllFindingsExport(
  filters?: { severity?: string; status?: string; category?: string; format?: "csv" | "docx" }
): Promise<Blob> {
  const q = new URLSearchParams();
  if (filters?.severity) q.set("severity", filters.severity);
  if (filters?.status) q.set("status", filters.status);
  if (filters?.category) q.set("category", filters.category);
  if (filters?.format) q.set("format", filters.format);
  const url = `${API_BASE}${API_PREFIX}/findings/export?${q.toString()}`;
  const res = await fetch(url, { headers: { ...authHeaders() } });
  if (!res.ok) {
    const detail = await parseErrorResponse(res);
    throw new Error(detail);
  }
  return res.blob();
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
