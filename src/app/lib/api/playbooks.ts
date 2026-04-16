/**
 * Playbooks API: CRUD, revisions, for-selection endpoint,
 * legal bases, departments, and VVT overview.
 */

import {
  API_BASE,
  API_PREFIX,
  authHeaders,
  deepSnakeToCamel,
  parseErrorResponse,
  request,
} from "./core";
import type { ApiPlaybook } from "./cases";

function mapPlaybook(d: Record<string, unknown>): Record<string, unknown> {
  const base = deepSnakeToCamel(d) as Record<string, unknown>;
  const content = d.content as Record<string, unknown> | undefined;
  base.checks = content && Array.isArray(content.checks) ? content.checks : [];
  base.status = d.is_active ? "active" : "archived";
  return base;
}

export async function getPlaybooks(): Promise<ApiPlaybook[]> {
  const list = (await request<Record<string, unknown>[]>("GET", "/playbooks")) ?? [];
  return list.map((p) => mapPlaybook(p) as ApiPlaybook);
}

export interface PlaybookMatchRow {
  playbook: ApiPlaybook;
  matchPriority: number;
}

export async function getPlaybooksForSelection(params: {
  department: string;
  processing_context?: string | null;
  case_type?: string | null;
  strict_case_type?: boolean;
}): Promise<PlaybookMatchRow[]> {
  const sp = new URLSearchParams();
  sp.set("department", params.department);
  if (params.processing_context != null && String(params.processing_context).trim() !== "") {
    sp.set("processing_context", String(params.processing_context).trim());
  }
  if (params.case_type != null && String(params.case_type).trim() !== "") {
    sp.set("case_type", String(params.case_type).trim());
  }
  if (params.strict_case_type) {
    sp.set("strict_case_type", "true");
  }
  const list =
    (await request<Record<string, unknown>[]>("GET", `/playbooks/for-selection?${sp.toString()}`)) ?? [];
  return list.map((row) => {
    const inner = row.playbook as Record<string, unknown> | undefined;
    return {
      matchPriority: typeof row.match_priority === "number" ? row.match_priority : 0,
      playbook: mapPlaybook(inner ?? {}) as ApiPlaybook,
    };
  });
}

export async function getPlaybook(id: string): Promise<ApiPlaybook> {
  const p = await request<Record<string, unknown>>("GET", `/playbooks/${id}`);
  return mapPlaybook(p) as ApiPlaybook;
}

export interface PlaybookCreatePayload {
  name: string;
  version: string;
  content: { checks: unknown[] };
  case_type?: string | null;
  department?: string | null;
}

export interface PlaybookUpdatePayload {
  name?: string;
  version?: string;
  content?: { checks: unknown[] };
  case_type?: string | null;
  department?: string | null;
  is_active?: boolean;
}

export async function createPlaybook(payload: PlaybookCreatePayload): Promise<ApiPlaybook> {
  const body = {
    name: payload.name,
    version: payload.version,
    content: payload.content,
    case_type: payload.case_type ?? null,
    department: payload.department ?? null,
  };
  const p = await request<Record<string, unknown>>("POST", "/playbooks", { body });
  return mapPlaybook(p) as ApiPlaybook;
}

export async function updatePlaybook(id: string, payload: PlaybookUpdatePayload): Promise<ApiPlaybook> {
  const body: Record<string, unknown> = {};
  if (payload.name !== undefined) body.name = payload.name;
  if (payload.version !== undefined) body.version = payload.version;
  if (payload.content !== undefined) body.content = payload.content;
  if (payload.case_type !== undefined) body.case_type = payload.case_type;
  if (payload.department !== undefined) body.department = payload.department;
  if (payload.is_active !== undefined) body.is_active = payload.is_active;
  const p = await request<Record<string, unknown>>("PATCH", `/playbooks/${id}`, { body });
  return mapPlaybook(p) as ApiPlaybook;
}

export async function deletePlaybook(id: string): Promise<void> {
  await request("DELETE", `/playbooks/${id}`);
}

// --- Playbook-Revisionen (Versions-Historie) ---
export interface ApiPlaybookRevision {
  id: string;
  playbookId: string;
  version: string;
  content: { checks: unknown[] };
  changedBy: string;
  createdAt: string;
}

function mapPlaybookRevision(d: Record<string, unknown>): ApiPlaybookRevision {
  const content = d.content as Record<string, unknown> | undefined;
  return {
    id: (d.id as string) ?? "",
    playbookId: (d.playbook_id as string) ?? "",
    version: (d.version as string) ?? "",
    content: {
      checks: content && Array.isArray(content.checks) ? (content.checks as unknown[]) : [],
    },
    changedBy: (d.changed_by as string) ?? "",
    createdAt: (d.created_at as string) ?? "",
  };
}

export async function getPlaybookRevisions(
  id: string,
  limit = 20
): Promise<ApiPlaybookRevision[]> {
  const list =
    (await request<Record<string, unknown>[]>(
      "GET",
      `/playbooks/${id}/revisions?limit=${limit}`
    )) ?? [];
  return list.map(mapPlaybookRevision);
}

export async function restorePlaybookRevision(
  id: string,
  revisionId: string
): Promise<ApiPlaybook> {
  const p = await request<Record<string, unknown>>(
    "POST",
    `/playbooks/${id}/revisions/${revisionId}/restore`
  );
  return mapPlaybook(p) as ApiPlaybook;
}

// --- Departments (Fachbereiche) ---
export interface ApiDepartment {
  code: string;
  label: string;
  type: string;
  value: string;
}

export async function getDepartments(): Promise<ApiDepartment[]> {
  const list = (await request<Record<string, unknown>[]>("GET", "/departments")) ?? [];
  return list.map((d) => ({
    code: (d.code as string) ?? "",
    label: (d.label as string) ?? "",
    type: (d.type as string) ?? "",
    value: (d.value as string) ?? (d.label as string) ?? (d.code as string) ?? "",
  }));
}

// --- Legal Bases (Rechtsgrundlagen) ---
export interface ApiLegalBase {
  id: string;
  title: string;
  shortName: string | null;
  content: string;
  applicability: "always" | "conditional";
  departmentCodes: string[];
  caseTypes: string[];
  internalOnly: boolean;
  createdAt: string;
  updatedAt: string;
}

function mapLegalBase(d: Record<string, unknown>): ApiLegalBase {
  return {
    id: (d.id as string) ?? "",
    title: (d.title as string) ?? "",
    shortName: (d.short_name as string) ?? null,
    content: (d.content as string) ?? "",
    applicability: ((d.applicability as string) ?? "always") as "always" | "conditional",
    departmentCodes: Array.isArray(d.department_codes) ? (d.department_codes as string[]) : [],
    caseTypes: Array.isArray(d.case_types) ? (d.case_types as string[]) : [],
    internalOnly: (d.internal_only as boolean) ?? false,
    createdAt: (d.created_at as string) ?? "",
    updatedAt: (d.updated_at as string) ?? "",
  };
}

export async function getLegalBases(applicability?: "always" | "conditional"): Promise<ApiLegalBase[]> {
  const q = applicability ? `?applicability=${encodeURIComponent(applicability)}` : "";
  const list = (await request<Record<string, unknown>[]>("GET", `/legal-bases${q}`)) ?? [];
  return list.map((b) => mapLegalBase(b));
}

export async function getLegalBase(id: string): Promise<ApiLegalBase> {
  const b = await request<Record<string, unknown>>("GET", `/legal-bases/${id}`);
  return mapLegalBase(b);
}

export interface LegalBaseCreatePayload {
  title: string;
  short_name?: string | null;
  content?: string;
  applicability?: "always" | "conditional";
  department_codes?: string[] | null;
  case_types?: string[] | null;
  internal_only?: boolean;
}

export interface LegalBaseUpdatePayload {
  title?: string;
  short_name?: string | null;
  content?: string;
  applicability?: "always" | "conditional";
  department_codes?: string[] | null;
  case_types?: string[] | null;
  internal_only?: boolean;
}

export async function createLegalBase(payload: LegalBaseCreatePayload): Promise<ApiLegalBase> {
  const b = await request<Record<string, unknown>>("POST", "/legal-bases", { body: payload });
  return mapLegalBase(b);
}

export async function updateLegalBase(id: string, payload: LegalBaseUpdatePayload): Promise<ApiLegalBase> {
  const b = await request<Record<string, unknown>>("PATCH", `/legal-bases/${id}`, { body: payload });
  return mapLegalBase(b);
}

export async function deleteLegalBase(id: string): Promise<void> {
  await request("DELETE", `/legal-bases/${id}`);
}

// --- VVT Overview (organisation-level) ---
export interface ApiVVTOverviewItem {
  case_id: string;
  title: string;
  department: string;
  case_type: string;
  status: string;
  updated_at: string;
  has_vvt_document: boolean;
  vvt_completeness: number | null;
  vvt_document_name: string | null;
}

export interface ApiVVTOverviewStatsGroup {
  name: string;
  total_cases: number;
  with_vvt: number;
  without_vvt: number;
  avg_completeness: number | null;
}

export interface ApiVVTOverviewStats {
  total_cases: number;
  with_vvt: number;
  without_vvt: number;
  avg_completeness: number | null;
  by_department: ApiVVTOverviewStatsGroup[];
  by_case_type: ApiVVTOverviewStatsGroup[];
}

export interface VVTOverviewParams {
  department?: string;
  case_type?: string;
  status?: string;
  has_vvt?: boolean;
  skip?: number;
  limit?: number;
}

function buildVvtOverviewQuery(params: VVTOverviewParams = {}): string {
  const sp = new URLSearchParams();
  if (params.department != null) sp.set("department", params.department);
  if (params.case_type != null) sp.set("case_type", params.case_type);
  if (params.status != null) sp.set("status", params.status);
  if (params.has_vvt !== undefined) sp.set("has_vvt", String(params.has_vvt));
  if (params.skip != null) sp.set("skip", String(params.skip));
  if (params.limit != null) sp.set("limit", String(params.limit));
  const q = sp.toString();
  return q ? `?${q}` : "";
}

export async function getVvtOverview(params: VVTOverviewParams = {}): Promise<ApiVVTOverviewItem[]> {
  const list =
    (await request<Record<string, unknown>[]>("GET", `/vvt-overview${buildVvtOverviewQuery(params)}`)) ?? [];
  return list.map((row) => ({
    case_id: (row.case_id as string) ?? "",
    title: (row.title as string) ?? "",
    department: (row.department as string) ?? "",
    case_type: (row.case_type as string) ?? "",
    status: (row.status as string) ?? "",
    updated_at: (row.updated_at as string) ?? "",
    has_vvt_document: Boolean(row.has_vvt_document),
    vvt_completeness: row.vvt_completeness != null ? Number(row.vvt_completeness) : null,
    vvt_document_name: row.vvt_document_name != null ? (row.vvt_document_name as string) : null,
  }));
}

export async function getVvtOverviewStats(): Promise<ApiVVTOverviewStats> {
  const r = await request<Record<string, unknown>>("GET", "/vvt-overview/stats");
  const byDep = (r.by_department as Record<string, unknown>[]) ?? [];
  const byType = (r.by_case_type as Record<string, unknown>[]) ?? [];
  return {
    total_cases: Number(r.total_cases ?? 0),
    with_vvt: Number(r.with_vvt ?? 0),
    without_vvt: Number(r.without_vvt ?? 0),
    avg_completeness: r.avg_completeness != null ? Number(r.avg_completeness) : null,
    by_department: byDep.map((g) => ({
      name: (g.name as string) ?? "",
      total_cases: Number(g.total_cases ?? 0),
      with_vvt: Number(g.with_vvt ?? 0),
      without_vvt: Number(g.without_vvt ?? 0),
      avg_completeness: g.avg_completeness != null ? Number(g.avg_completeness) : null,
    })),
    by_case_type: byType.map((g) => ({
      name: (g.name as string) ?? "",
      total_cases: Number(g.total_cases ?? 0),
      with_vvt: Number(g.with_vvt ?? 0),
      without_vvt: Number(g.without_vvt ?? 0),
      avg_completeness: g.avg_completeness != null ? Number(g.avg_completeness) : null,
    })),
  };
}

export async function getVvtOverviewExportBlob(
  params: VVTOverviewParams = {},
  format: "csv" = "csv"
): Promise<Blob> {
  const q = buildVvtOverviewQuery({ ...params });
  const url = `${API_BASE}${API_PREFIX}/vvt-overview/export${q ? q + "&" : "?"}format=${format}`;
  const res = await fetch(url, { headers: authHeaders() });
  if (!res.ok) {
    const detail = await parseErrorResponse(res);
    throw new Error(detail);
  }
  return res.blob();
}
