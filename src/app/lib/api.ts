/**
 * API client for Datenschutzagent backend.
 * Uses VITE_API_URL or defaults to http://localhost:8000.
 */

const API_BASE = (import.meta as unknown as { env?: { VITE_API_URL?: string } }).env?.VITE_API_URL ?? "http://localhost:8000";
const API_PREFIX = "/api/v1";

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

/** Map API snake_case to frontend camelCase. */
function mapCase(d: Record<string, unknown>): Record<string, unknown> {
  return {
    id: d.id,
    title: d.title,
    department: d.department,
    caseType: d.case_type,
    status: d.status,
    language: d.language,
    createdAt: d.created_at,
    updatedAt: d.updated_at,
    createdBy: d.created_by,
    assignee: d.assignee,
    playbookVersion: d.playbook_version ?? "",
    documents: Array.isArray(d.documents) ? (d.documents as Record<string, unknown>[]).map(mapDocument) : [],
    findings: Array.isArray(d.findings) ? (d.findings as Record<string, unknown>[]).map(mapFinding) : [],
  };
}

function mapDocument(d: Record<string, unknown>): Record<string, unknown> {
  const sizeBytes = d.size_bytes as number | undefined;
  return {
    id: d.id,
    name: d.name,
    type: d.type,
    version: d.version,
    uploadedAt: d.uploaded_at,
    uploadedBy: d.uploaded_by,
    size: sizeBytes != null ? formatBytes(sizeBytes) : "",
    sizeBytes: sizeBytes,
    format: d.format,
    caseId: d.case_id,
  };
}

function mapFinding(d: Record<string, unknown>): Record<string, unknown> {
  return {
    id: d.id,
    checkName: d.check_name,
    severity: d.severity,
    status: d.status,
    category: d.category,
    description: d.description,
    evidence: d.evidence ?? [],
    recommendation: d.recommendation ?? "",
    documentId: d.document_id ?? undefined,
    caseId: d.case_id,
  };
}

function mapPlaybook(d: Record<string, unknown>): Record<string, unknown> {
  const content = d.content as Record<string, unknown> | undefined;
  const checks = content && Array.isArray(content.checks) ? content.checks : [];
  return {
    id: d.id,
    name: d.name,
    version: d.version,
    content: d.content,
    caseType: d.case_type ?? null,
    department: d.department ?? null,
    isActive: d.is_active ?? true,
    status: d.is_active ? "active" : "archived",
    createdAt: d.created_at,
    updatedAt: d.created_at,
    checks,
  };
}

async function request<T>(
  method: string,
  path: string,
  options?: { body?: unknown; formData?: FormData }
): Promise<T> {
  const url = `${API_BASE}${API_PREFIX}${path}`;
  const headers: Record<string, string> = {};
  let fetchBody: string | FormData | undefined;
  if (options?.formData) {
    fetchBody = options.formData;
  } else if (options?.body != null) {
    headers["Content-Type"] = "application/json";
    fetchBody = JSON.stringify(options.body);
  }
  const res = await fetch(url, { method, headers, body: fetchBody });
  if (!res.ok) {
    const text = await res.text();
    let detail = text;
    try {
      const j = JSON.parse(text);
      detail = j.detail ?? text;
    } catch {
      // use text
    }
    throw new Error(detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// --- Types (aligned with backend and mock-data) ---
export type CaseStatus =
  | "intake"
  | "in_review"
  | "questions_pending"
  | "revision"
  | "ready_for_decision"
  | "completed";

export type DocumentType =
  | "vvt"
  | "screening"
  | "info_sheet_de"
  | "info_sheet_en"
  | "dsfa"
  | "avv"
  | "other";

export type FindingStatus = "open" | "accepted" | "overruled" | "fixed";

export type VVTFieldStatus = "filled" | "missing" | "inconsistent";

export interface ApiVVTField {
  fieldName: string;
  required: boolean;
  status: VVTFieldStatus;
  sourceTemplate: string;
  canonicalValue?: string;
  evidence?: string;
  finding?: string;
}

export interface ApiVVTNormalization {
  documentId: string | null;
  documentName: string;
  sourceTemplate: string;
  fields: ApiVVTField[];
}

export interface CaseCreateInput {
  title: string;
  department: string;
  case_type: string;
  language?: "de" | "en" | "de_en";
  created_by?: string;
  assignee?: string;
}

export interface CaseUpdateInput {
  title?: string;
  department?: string;
  case_type?: string;
  status?: CaseStatus;
  language?: "de" | "en" | "de_en";
  assignee?: string;
  playbook_version?: string;
}

export interface ApiCase {
  id: string;
  title: string;
  department: string;
  caseType: string;
  status: CaseStatus;
  createdAt: string;
  updatedAt: string;
  createdBy: string;
  assignee: string;
  language: string;
  playbookVersion: string;
  documents: ApiDocument[];
  findings: ApiFinding[];
  priority?: string;
  deadline?: string;
}

export interface ApiDocument {
  id: string;
  name: string;
  type: DocumentType;
  version: number;
  uploadedAt: string;
  uploadedBy: string;
  size: string;
  sizeBytes?: number;
  format: string;
  caseId?: string;
}

export interface ApiFinding {
  id: string;
  checkName: string;
  severity: string;
  status: FindingStatus;
  category: string;
  description: string;
  evidence: string[];
  recommendation: string;
  documentId?: string;
  caseId?: string;
}

export interface ApiPlaybook {
  id: string;
  name: string;
  version: string;
  content: Record<string, unknown>;
  caseType: string | null;
  department: string | null;
  isActive: boolean;
  status: string;
  createdAt: string;
  updatedAt: string;
  checks: unknown[];
}

// --- Cases ---
export async function getCases(skip = 0, limit = 100): Promise<ApiCase[]> {
  const list = (await request<Record<string, unknown>[]>("GET", `/cases?skip=${skip}&limit=${limit}`)) ?? [];
  return list.map((c) => mapCase(c) as ApiCase);
}

export async function getCase(id: string): Promise<ApiCase> {
  const c = await request<Record<string, unknown>>("GET", `/cases/${id}`);
  return mapCase(c) as ApiCase;
}

export async function createCase(body: CaseCreateInput): Promise<ApiCase> {
  const c = await request<Record<string, unknown>>("POST", "/cases", { body });
  return mapCase(c) as ApiCase;
}

export async function updateCase(id: string, body: CaseUpdateInput): Promise<ApiCase> {
  const c = await request<Record<string, unknown>>("PATCH", `/cases/${id}`, { body });
  return mapCase(c) as ApiCase;
}

export async function deleteCase(id: string): Promise<void> {
  await request("DELETE", `/cases/${id}`);
}

export async function runChecks(caseId: string, playbookId: string): Promise<ApiCase> {
  const c = await request<Record<string, unknown>>("POST", `/cases/${caseId}/run-checks`, {
    body: { playbook_id: playbookId },
  });
  return mapCase(c) as ApiCase;
}

// --- Documents ---
export async function getDocuments(caseId?: string): Promise<ApiDocument[]> {
  const q = caseId ? `?case_id=${caseId}` : "";
  const list = (await request<Record<string, unknown>[]>("GET", `/documents${q}`)) ?? [];
  return list.map((d) => mapDocument(d) as ApiDocument);
}

export async function uploadDocument(
  caseId: string,
  file: File,
  documentType: string,
  uploadedBy: string
): Promise<ApiDocument> {
  const form = new FormData();
  form.append("case_id", caseId);
  form.append("file", file);
  form.append("document_type", documentType);
  form.append("uploaded_by", uploadedBy);
  const d = await request<Record<string, unknown>>("POST", "/documents", { formData: form });
  return mapDocument(d) as ApiDocument;
}

export async function deleteDocument(id: string): Promise<void> {
  await request("DELETE", `/documents/${id}`);
}

// --- Findings ---
export async function updateFindingStatus(findingId: string, status: FindingStatus): Promise<ApiFinding> {
  const f = await request<Record<string, unknown>>("PATCH", `/findings/${findingId}`, {
    body: { status },
  });
  return mapFinding(f) as ApiFinding;
}

// --- Playbooks ---
export async function getPlaybooks(): Promise<ApiPlaybook[]> {
  const list = (await request<Record<string, unknown>[]>("GET", "/playbooks")) ?? [];
  return list.map((p) => mapPlaybook(p) as ApiPlaybook);
}

export async function getPlaybook(id: string): Promise<ApiPlaybook> {
  const p = await request<Record<string, unknown>>("GET", `/playbooks/${id}`);
  return mapPlaybook(p) as ApiPlaybook;
}

// --- VVT Normalization ---
function mapVVTField(d: Record<string, unknown>): ApiVVTField {
  return {
    fieldName: (d.field_name as string) ?? "",
    required: (d.required as boolean) ?? true,
    status: (d.status as ApiVVTField["status"]) ?? "missing",
    sourceTemplate: (d.source_template as string) ?? "",
    canonicalValue: d.canonical_value as string | undefined,
    evidence: d.evidence as string | undefined,
    finding: d.finding as string | undefined,
  };
}

export async function getVVTNormalization(
  caseId: string,
  documentId?: string
): Promise<ApiVVTNormalization> {
  const q = documentId ? `?document_id=${documentId}` : "";
  const r = await request<Record<string, unknown>>(
    "GET",
    `/cases/${caseId}/vvt-normalization${q}`
  );
  const fields = Array.isArray(r.fields)
    ? (r.fields as Record<string, unknown>[]).map(mapVVTField)
    : [];
  return {
    documentId: (r.document_id as string) ?? null,
    documentName: (r.document_name as string) ?? "",
    sourceTemplate: (r.source_template as string) ?? "",
    fields,
  };
}
