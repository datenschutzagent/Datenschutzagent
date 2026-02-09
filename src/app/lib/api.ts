/**
 * API client for Datenschutzagent backend.
 * Uses VITE_API_URL or defaults to http://localhost:8002.
 */

const API_BASE = (import.meta as unknown as { env?: { VITE_API_URL?: string } }).env?.VITE_API_URL ?? "http://localhost:8002";
const API_PREFIX = "/api/v1";

/** Token for authenticated requests (set by auth flow when OIDC is enabled). */
let accessToken: string | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

function authHeaders(): Record<string, string> {
  const h: Record<string, string> = {};
  if (accessToken) h["Authorization"] = `Bearer ${accessToken}`;
  return h;
}

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
    extractionMethod: d.extraction_method ?? undefined,
    extractionStatus: (d.extraction_status as "pending" | "processing" | "done" | "failed") ?? undefined,
    extractionError: (d.extraction_error as string) ?? undefined,
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
    sourceStrategy: d.source_strategy ?? undefined,
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

/** Parse error message from a non-ok Response (JSON detail or body text). */
export async function parseErrorResponse(res: Response): Promise<string> {
  const text = await res.text();
  try {
    const j = JSON.parse(text) as { detail?: string };
    return j.detail ?? text;
  } catch {
    return text;
  }
}

async function request<T>(
  method: string,
  path: string,
  options?: { body?: unknown; formData?: FormData }
): Promise<T> {
  const url = `${API_BASE}${API_PREFIX}${path}`;
  const headers: Record<string, string> = {};
  if (accessToken) {
    headers["Authorization"] = `Bearer ${accessToken}`;
  }
  let fetchBody: string | FormData | undefined;
  if (options?.formData) {
    fetchBody = options.formData;
  } else if (options?.body != null) {
    headers["Content-Type"] = "application/json";
    fetchBody = JSON.stringify(options.body);
  }
  const res = await fetch(url, { method, headers, body: fetchBody });
  if (!res.ok) {
    const detail = await parseErrorResponse(res);
    throw new Error(detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// --- Auth config (public, no token) ---
export interface AuthConfig {
  oidc_enabled: boolean;
  oidc_issuer_url: string;
  oidc_client_id: string;
  oidc_scopes: string[];
  authorization_endpoint?: string;
  token_endpoint?: string;
  end_session_endpoint?: string;
}

export async function getAuthConfig(): Promise<AuthConfig> {
  const url = `${API_BASE}${API_PREFIX}/auth/config`;
  const res = await fetch(url);
  if (!res.ok) {
    const detail = await parseErrorResponse(res);
    throw new Error(detail);
  }
  return res.json() as Promise<AuthConfig>;
}

// --- User / Me (profile and preferences) ---
export type UserTheme = "light" | "dark" | "system";
export type UserUILanguage = "de" | "en";

export interface UserPreferences {
  theme?: UserTheme;
  language?: UserUILanguage;
  notifications?: Record<string, unknown>;
}

export type UserRole = "viewer" | "editor" | "admin";

export interface ApiUser {
  id: string;
  display_name: string;
  email: string | null;
  role?: UserRole;
  preferences: UserPreferences | Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

/** True if user can create/edit/delete cases, documents, playbooks, run checks, update finding status. */
export function canEdit(user: ApiUser | null): boolean {
  return user?.role === "editor" || user?.role === "admin";
}

/** True if user can access admin endpoints (settings, connections). */
export function isAdmin(user: ApiUser | null): boolean {
  return user?.role === "admin";
}

export interface UserUpdateInput {
  display_name?: string;
  email?: string | null;
  preferences?: UserPreferences | Record<string, unknown>;
}

export async function getCurrentUser(): Promise<ApiUser> {
  return request<ApiUser>("GET", "/me");
}

export async function updateCurrentUser(body: UserUpdateInput): Promise<ApiUser> {
  return request<ApiUser>("PATCH", "/me", { body });
}

// --- Admin (read-only settings and connection status) ---
export interface ApiAdminSettings {
  app_name: string;
  ollama_base_url: string;
  ollama_enabled: boolean;
  ollama_model: string;
  weaviate_url: string;
  weaviate_indexing_enabled: boolean;
  storage_backend: string;
  storage_local_path: string | null;
  s3_configured: boolean;
  s3_bucket: string | null;
  celery_enabled: boolean;
  celery_broker_configured: boolean;
}

export interface ApiConnectionStatus {
  status: "ok" | "disabled" | "not_configured" | "unreachable";
  message?: string;
}

export interface ApiConnectionsStatus {
  ollama: ApiConnectionStatus;
  weaviate: ApiConnectionStatus;
  minio: ApiConnectionStatus;
  postgres: ApiConnectionStatus;
  redis: ApiConnectionStatus;
}

export async function getAdminSettings(): Promise<ApiAdminSettings> {
  return request<ApiAdminSettings>("GET", "/admin/settings");
}

export async function getConnectionsStatus(): Promise<ApiConnectionsStatus> {
  return request<ApiConnectionsStatus>("GET", "/admin/connections");
}

// --- Admin: Prompt templates (versioned) ---
export interface ApiPromptTemplate {
  id: string;
  key: string;
  version: string;
  content: string;
  is_active: boolean;
  created_at: string;
}

export interface ApiPromptTemplateKeyMeta {
  key: string;
  description: string;
  placeholders: string[];
}

export async function getAdminPromptTemplates(key?: string): Promise<ApiPromptTemplate[]> {
  const q = key ? `?key=${encodeURIComponent(key)}` : "";
  return request<ApiPromptTemplate[]>("GET", `/admin/prompt-templates${q}`);
}

export async function getAdminPromptTemplateVersions(key: string): Promise<ApiPromptTemplate[]> {
  return request<ApiPromptTemplate[]>("GET", `/admin/prompt-templates/versions?key=${encodeURIComponent(key)}`);
}

export async function getAdminPromptTemplateKeys(): Promise<ApiPromptTemplateKeyMeta[]> {
  return request<ApiPromptTemplateKeyMeta[]>("GET", "/admin/prompt-templates/keys");
}

export async function createAdminPromptTemplate(body: {
  key: string;
  version?: string;
  content: string;
  set_active?: boolean;
}): Promise<ApiPromptTemplate> {
  return request<ApiPromptTemplate>("POST", "/admin/prompt-templates", { body });
}

export async function setActivePromptTemplate(id: string, isActive: boolean): Promise<ApiPromptTemplate> {
  return request<ApiPromptTemplate>("PATCH", `/admin/prompt-templates/${id}`, {
    body: { is_active: isActive },
  });
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
  /** "ocr" when text was extracted via Ollama Vision (scanned PDFs); "text" or undefined otherwise */
  extractionMethod?: "text" | "ocr";
  /** Async extraction state: pending | processing | done | failed */
  extractionStatus?: "pending" | "processing" | "done" | "failed";
  /** Error message when extractionStatus === "failed" */
  extractionError?: string;
}

/** "full_text" | "rag" – which run-checks strategy produced this finding */
export type SourceStrategy = "full_text" | "rag";

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
  sourceStrategy?: SourceStrategy;
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

// --- DSB Report (API returns snake_case; we map to camelCase for UI) ---
export type DSFAAssessment = "required" | "not_required" | "unclear";

export interface ApiDSBReportSummary {
  total_documents: number;
  total_findings: number;
  critical_findings: number;
  high_findings: number;
  dsfa_required: boolean;
  dsfa_assessment?: DSFAAssessment;
  vvt_completeness: number;
  vvt_available?: boolean;
}

export interface ApiDSBReportRisk {
  title: string;
  severity: "critical" | "high" | "medium" | "low" | "info";
  description: string;
}

export interface ApiDSBReport {
  case_id: string;
  case_title: string;
  generated_at: string;
  playbook_version: string;
  status: string;
  summary: ApiDSBReportSummary;
  risks: ApiDSBReportRisk[];
  open_questions: string[];
  recommendations: string[];
  next_steps: string[];
  next_steps_is_suggested?: boolean;
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

export type RunChecksStrategy = "full_text" | "rag";

/** When POST run-checks returns 202, the job was queued (Celery). */
export interface RunChecksAcceptedResponse {
  accepted: true;
  jobId: string;
  status: "running";
}

/** Response of GET /cases/:id/run-checks/status */
export interface RunChecksStatusResponse {
  status: "never_run" | "running" | "completed" | "failed";
  job_id: string | null;
  playbook_name: string | null;
  findings_count: number | null;
  error: string | null;
  last_run: { id: string; case_id: string; event_type: string; payload: Record<string, unknown>; created_at: string } | null;
}

export async function runChecks(
  caseId: string,
  playbookId: string,
  strategies: RunChecksStrategy[] = ["full_text"],
): Promise<ApiCase | RunChecksAcceptedResponse> {
  const url = `${API_BASE}${API_PREFIX}/cases/${caseId}/run-checks`;
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (accessToken) headers["Authorization"] = `Bearer ${accessToken}`;
  const res = await fetch(url, {
    method: "POST",
    headers,
    body: JSON.stringify({ playbook_id: playbookId, strategies }),
  });
  if (!res.ok) {
    const detail = await parseErrorResponse(res);
    throw new Error(detail);
  }
  const data = (await res.json()) as Record<string, unknown>;
  if (res.status === 202) {
    return {
      accepted: true,
      jobId: (data.job_id as string) ?? "",
      status: "running",
    };
  }
  return mapCase(data) as ApiCase;
}

export async function getRunChecksStatus(caseId: string): Promise<RunChecksStatusResponse> {
  const raw = await request<{
    status: string;
    job_id: string | null;
    playbook_name: string | null;
    findings_count: number | null;
    error: string | null;
    last_run: RunChecksStatusResponse["last_run"];
  }>("GET", `/cases/${caseId}/run-checks/status`);
  return {
    status: raw.status as RunChecksStatusResponse["status"],
    job_id: raw.job_id,
    playbook_name: raw.playbook_name,
    findings_count: raw.findings_count,
    error: raw.error,
    last_run: raw.last_run,
  };
}

// --- Case Activities (Audit Log) ---
export interface ApiActivity {
  id: string;
  case_id: string;
  event_type: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface TimelineActivity {
  id: string;
  caseId: string;
  type: "playbook_run" | "finding_status_changed";
  timestamp: string;
  performedBy: string;
  description: string;
  metadata?: { oldValue?: string; newValue?: string; documentName?: string; findingId?: string; comment?: string };
}

function mapApiActivityToTimeline(a: ApiActivity): TimelineActivity {
  const caseId = typeof a.case_id === "string" ? a.case_id : (a.case_id as { toString: () => string }).toString();
  const timestamp = typeof a.created_at === "string" ? a.created_at : new Date((a.created_at as Date).valueOf()).toISOString();
  if (a.event_type === "run_checks") {
    const playbookName = (a.payload?.playbook_name as string) ?? "Playbook";
    const count = (a.payload?.findings_count as number) ?? 0;
    return {
      id: a.id,
      caseId,
      type: "playbook_run",
      timestamp,
      performedBy: "System",
      description: `Playbook „${playbookName}" ausgeführt, ${count} Finding(s) erstellt.`,
    };
  }
  if (a.event_type === "finding_status_updated") {
    const oldStatus = (a.payload?.old_status as string) ?? "";
    const newStatus = (a.payload?.new_status as string) ?? "";
    return {
      id: a.id,
      caseId,
      type: "finding_status_changed",
      timestamp,
      performedBy: "System",
      description: "Finding-Status geändert",
      metadata: { oldValue: oldStatus, newValue: newStatus },
    };
  }
  return {
    id: a.id,
    caseId,
    type: "playbook_run",
    timestamp,
    performedBy: "System",
    description: a.event_type,
  };
}

export async function getCaseActivities(caseId: string): Promise<TimelineActivity[]> {
  const list = (await request<ApiActivity[]>("GET", `/cases/${caseId}/activities`)) ?? [];
  return list.map(mapApiActivityToTimeline);
}

// --- DSB Report ---
export interface DSBReportViewData {
  caseId: string;
  caseTitle: string;
  generatedAt: string;
  playbookVersion: string;
  status: string;
  summary: {
    totalDocuments: number;
    totalFindings: number;
    criticalFindings: number;
    highFindings: number;
    dsfaRequired: boolean;
    dsfaAssessment: DSFAAssessment;
    vvtCompleteness: number;
    vvtAvailable: boolean;
  };
  risks: ApiDSBReportRisk[];
  openQuestions: string[];
  recommendations: string[];
  nextSteps: string[];
  next_steps_is_suggested?: boolean;
  reportStale?: boolean;
  staleReason?: string | null;
}

function mapDSBReport(
  r: ApiDSBReport & { report_stale?: boolean; stale_reason?: string | null }
): DSBReportViewData {
  const s = r.summary;
  return {
    caseId: r.case_id,
    caseTitle: r.case_title,
    generatedAt: r.generated_at,
    playbookVersion: r.playbook_version ?? "",
    status: r.status,
    summary: {
      totalDocuments: s?.total_documents ?? 0,
      totalFindings: s?.total_findings ?? 0,
      criticalFindings: s?.critical_findings ?? 0,
      highFindings: s?.high_findings ?? 0,
      dsfaRequired: s?.dsfa_required ?? false,
      dsfaAssessment: (s?.dsfa_assessment as DSFAAssessment) ?? "unclear",
      vvtCompleteness: s?.vvt_completeness ?? 0,
      vvtAvailable: s?.vvt_available ?? false,
    },
    risks: r.risks ?? [],
    openQuestions: r.open_questions ?? [],
    recommendations: r.recommendations ?? [],
    nextSteps: r.next_steps ?? [],
    next_steps_is_suggested: r.next_steps_is_suggested ?? true,
    reportStale: r.report_stale,
    staleReason: r.stale_reason ?? null,
  };
}

/** Fetches report if it exists; returns null on 404 (no report yet). */
export async function getDSBReportIfExists(caseId: string): Promise<DSBReportViewData | null> {
  const url = `${API_BASE}${API_PREFIX}/cases/${caseId}/dsb-report?format=json`;
  const res = await fetch(url, { headers: authHeaders() });
  if (res.status === 404) return null;
  if (!res.ok) {
    const detail = await parseErrorResponse(res);
    throw new Error(detail);
  }
  const r = (await res.json()) as ApiDSBReport & { report_stale?: boolean; stale_reason?: string | null };
  return mapDSBReport(r);
}

export async function getDSBReport(caseId: string): Promise<DSBReportViewData> {
  const r = await request<ApiDSBReport>("GET", `/cases/${caseId}/dsb-report?format=json`);
  return mapDSBReport(r);
}

/** Status of report generation for polling. */
export interface DSBReportStatusResponse {
  status: "no_report" | "running" | "completed" | "failed";
  job_id: string | null;
  error: string | null;
}

export async function getDSBReportStatus(caseId: string): Promise<DSBReportStatusResponse> {
  return request<DSBReportStatusResponse>("GET", `/cases/${caseId}/dsb-report/status`);
}

/** Start report generation. Returns 202 payload when queued (job_id), 200 when sync. */
export async function generateDSBReport(caseId: string): Promise<
  | { status: "running"; job_id: string; message?: string }
  | { status: "completed"; message?: string; generated_at?: string }
> {
  const url = `${API_BASE}${API_PREFIX}/cases/${caseId}/dsb-report/generate`;
  const res = await fetch(url, { method: "POST", headers: authHeaders() });
  if (!res.ok) {
    const detail = await parseErrorResponse(res);
    throw new Error(detail);
  }
  const data = (await res.json()) as Record<string, unknown>;
  if (res.status === 202) {
    return { status: "running", job_id: (data.job_id as string) ?? "", message: data.message as string | undefined };
  }
  return {
    status: "completed",
    message: data.message as string | undefined,
    generated_at: data.generated_at as string | undefined,
  };
}

export async function getDSBReportBlob(
  caseId: string,
  format: "markdown" | "json"
): Promise<Blob> {
  const url = `${API_BASE}${API_PREFIX}/cases/${caseId}/dsb-report?format=${format}`;
  const res = await fetch(url, { headers: authHeaders() });
  if (!res.ok) {
    const detail = await parseErrorResponse(res);
    throw new Error(detail);
  }
  return res.blob();
}

/** Trigger download of a blob with suggested filename. */
export function downloadBlob(blob: Blob, filename: string): void {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}

// --- Documents ---
export async function getDocuments(caseId?: string, documentType?: string): Promise<ApiDocument[]> {
  const params = new URLSearchParams();
  if (caseId) params.set("case_id", caseId);
  if (documentType) params.set("document_type", documentType);
  const q = params.toString() ? `?${params.toString()}` : "";
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

/** Upload multiple documents in one request. Same documentType and uploadedBy for all. Returns list of created documents. */
export async function uploadDocumentsBulk(
  caseId: string,
  files: File[],
  documentType: string,
  uploadedBy: string
): Promise<ApiDocument[]> {
  const form = new FormData();
  form.append("case_id", caseId);
  form.append("document_type", documentType);
  form.append("uploaded_by", uploadedBy);
  for (const file of files) {
    form.append("files", file);
  }
  const url = `${API_BASE}${API_PREFIX}/documents/bulk`;
  const res = await fetch(url, { method: "POST", body: form, headers: authHeaders() });
  if (!res.ok) {
    const detail = await parseErrorResponse(res);
    throw new Error(detail);
  }
  const list = (await res.json()) as Record<string, unknown>[];
  return list.map((d) => mapDocument(d) as ApiDocument);
}

export async function deleteDocument(id: string): Promise<void> {
  await request("DELETE", `/documents/${id}`);
}

/** Update document (e.g. extracted content). Editor/admin only. */
export async function updateDocument(
  documentId: string,
  body: { content?: string }
): Promise<ApiDocument> {
  const d = await request<Record<string, unknown>>("PATCH", `/documents/${documentId}`, {
    body,
  });
  return mapDocument(d) as ApiDocument;
}

/** Download the original document file as a blob (for save/open). */
export async function getDocumentDownloadBlob(documentId: string): Promise<Blob> {
  const url = `${API_BASE}${API_PREFIX}/documents/${documentId}/download`;
  const res = await fetch(url, { headers: authHeaders() });
  if (!res.ok) {
    const detail = await parseErrorResponse(res);
    throw new Error(detail);
  }
  return res.blob();
}

/** Response of GET /documents/:id/content (extracted text and extraction state). */
export interface DocumentContentResponse {
  content: string;
  extractionStatus?: "pending" | "processing" | "done" | "failed";
  extractionError?: string;
}

/** Get extracted text content of a document (for in-app display). Includes extraction status for UI. */
export async function getDocumentContent(documentId: string): Promise<DocumentContentResponse> {
  const raw = await request<{
    content: string;
    extraction_status?: string;
    extraction_error?: string;
  }>("GET", `/documents/${documentId}/content`);
  return {
    content: raw.content ?? "",
    extractionStatus: raw.extraction_status as DocumentContentResponse["extractionStatus"] | undefined,
    extractionError: raw.extraction_error,
  };
}

// --- Document comments ---
export interface ApiDocumentComment {
  id: string;
  document_id: string;
  case_id: string;
  author: string;
  user_id: string | null;
  text: string;
  created_at: string;
}

export async function getDocumentComments(documentId: string): Promise<ApiDocumentComment[]> {
  const list = (await request<Record<string, unknown>[]>("GET", `/documents/${documentId}/comments`)) ?? [];
  return list.map((c) => ({
    id: c.id as string,
    document_id: c.document_id as string,
    case_id: c.case_id as string,
    author: (c.author as string) ?? "",
    user_id: (c.user_id as string) ?? null,
    text: (c.text as string) ?? "",
    created_at: (c.created_at as string) ?? "",
  }));
}

export async function createDocumentComment(
  documentId: string,
  text: string
): Promise<ApiDocumentComment> {
  const c = await request<Record<string, unknown>>("POST", `/documents/${documentId}/comments`, {
    body: { text },
  });
  return {
    id: c.id as string,
    document_id: c.document_id as string,
    case_id: c.case_id as string,
    author: (c.author as string) ?? "",
    user_id: (c.user_id as string) ?? null,
    text: (c.text as string) ?? "",
    created_at: (c.created_at as string) ?? "",
  };
}

// --- Findings ---
export async function updateFindingStatus(findingId: string, status: FindingStatus): Promise<ApiFinding> {
  const f = await request<Record<string, unknown>>("PATCH", `/findings/${findingId}`, {
    body: { status },
  });
  return mapFinding(f) as ApiFinding;
}

// --- Departments (Fachbereiche and central institutions) ---
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

// --- Playbooks ---
export async function getPlaybooks(): Promise<ApiPlaybook[]> {
  const list = (await request<Record<string, unknown>[]>("GET", "/playbooks")) ?? [];
  return list.map((p) => mapPlaybook(p) as ApiPlaybook);
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

export async function getVVTExportBlob(
  caseId: string,
  documentId?: string,
  format: "csv" = "csv"
): Promise<Blob> {
  const params = new URLSearchParams({ format });
  if (documentId) params.set("document_id", documentId);
  const url = `${API_BASE}${API_PREFIX}/cases/${caseId}/vvt-normalization/export?${params}`;
  const res = await fetch(url, { headers: authHeaders() });
  if (!res.ok) {
    const detail = await parseErrorResponse(res);
    throw new Error(detail);
  }
  return res.blob();
}

// --- Annotated Documents (DOCX with findings) ---
export interface ApiAnnotatedDocumentItem {
  document_id: string;
  document_name: string;
  finding_count: number;
}

export async function getAnnotatedDocuments(caseId: string): Promise<ApiAnnotatedDocumentItem[]> {
  const list =
    (await request<Record<string, unknown>[]>("GET", `/cases/${caseId}/annotated-documents`)) ?? [];
  return list.map((d) => ({
    document_id: d.document_id as string,
    document_name: (d.document_name as string) ?? "",
    finding_count: (d.finding_count as number) ?? 0,
  }));
}

export async function getAnnotatedDocumentBlob(
  caseId: string,
  documentId: string
): Promise<Blob> {
  const url = `${API_BASE}${API_PREFIX}/cases/${caseId}/annotated-documents/${documentId}`;
  const res = await fetch(url, { headers: authHeaders() });
  if (!res.ok) {
    const detail = await parseErrorResponse(res);
    throw new Error(detail);
  }
  return res.blob();
}
