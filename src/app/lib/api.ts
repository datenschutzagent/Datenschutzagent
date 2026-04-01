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
    processingContext: (d.processing_context as string) ?? null,
    specialCategoryData: Boolean(d.special_category_data),
    internationalTransfer: Boolean(d.international_transfer),
    deadline: (d.deadline as string) ?? null,
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
    dueDate: (d.due_date as string) ?? null,
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
    updatedAt: d.updated_at ?? d.created_at,
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
  processing_context?: string | null;
  special_category_data?: boolean;
  international_transfer?: boolean;
}

export interface CaseUpdateInput {
  title?: string;
  department?: string;
  case_type?: string;
  status?: CaseStatus;
  language?: "de" | "en" | "de_en";
  assignee?: string;
  playbook_version?: string;
  processing_context?: string | null;
  special_category_data?: boolean;
  international_transfer?: boolean;
  deadline?: string | null;
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
  processingContext?: string | null;
  specialCategoryData?: boolean;
  internationalTransfer?: boolean;
  deadline?: string | null;
  documents: ApiDocument[];
  findings: ApiFinding[];
  priority?: string;
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
  dueDate?: string | null;
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
  documents_changed_since_last_run?: boolean;
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
    documents_changed_since_last_run: raw.documents_changed_since_last_run ?? false,
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
  const headers: Record<string, string> = { ...authHeaders() };
  const res = await fetch(url, { headers });
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

// --- Case risk score (Verbesserung 3) ---
export interface CaseRiskScoreHistoryItem {
  job_id: string;
  created_at: string;
  score: number;
  findings_count: number;
  critical: number;
  high: number;
  medium: number;
}

export interface CaseRiskScore {
  case_id: string;
  score: number;
  history: CaseRiskScoreHistoryItem[];
}

export async function getCaseRiskScore(caseId: string, limit = 10): Promise<CaseRiskScore> {
  return request<CaseRiskScore>("GET", `/cases/${caseId}/risk-score?limit=${limit}`);
}

// --- Playbook coverage preview (Verbesserung 6) ---
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

// --- Case similarity (Verbesserung 7) ---
export interface CaseSimilarityResult {
  case_id: string;
  title: string;
  department: string;
  case_type: string;
  status: string;
  overlap_score: number;
  shared_check_names: string[];
  resolution_summary: Record<string, number>;
}

export async function getSimilarCases(caseId: string, limit = 5): Promise<CaseSimilarityResult[]> {
  return request<CaseSimilarityResult[]>("GET", `/cases/${caseId}/similar?limit=${limit}`);
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

// --- Playbooks ---
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

// --- App Config (public, no auth required) ---
export interface ApiAppConfig {
  app_name: string;
  org_name: string;
  org_profile: string;
  processing_context_options: { value: string; label: string }[];
}

export async function getAppConfig(): Promise<ApiAppConfig> {
  const url = `${API_BASE}${API_PREFIX}/config`;
  const res = await fetch(url);
  if (!res.ok) throw new Error("Failed to load app config");
  return res.json() as Promise<ApiAppConfig>;
}
