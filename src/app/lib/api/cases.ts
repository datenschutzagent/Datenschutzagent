/**
 * Cases API: CRUD, run-checks, activities, DSB reports,
 * VVT normalization, annotated documents, risk scores,
 * similarity, audit export, and DSFA screening.
 */

import {
  API_BASE,
  API_PREFIX,
  authHeaders,
  deepSnakeToCamel,
  formatBytes,
  parseErrorResponse,
  request,
} from "./core";

// --- Shared types (referenced by documents.ts, findings.ts, compliance.ts) ---

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
  auto_run_checks?: boolean;
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
  /** Human-readable title of the associated case (populated by the list endpoint). */
  caseTitle?: string | null;
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

// --- DSB Report types ---
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

// ---------------------------------------------------------------------------
// Private mappers
// ---------------------------------------------------------------------------

function mapDocument(d: Record<string, unknown>): Record<string, unknown> {
  const base = deepSnakeToCamel(d) as Record<string, unknown>;
  const sizeBytes = d.size_bytes as number | undefined;
  base.size = sizeBytes != null ? formatBytes(sizeBytes) : "";
  return base;
}

function mapFinding(d: Record<string, unknown>): Record<string, unknown> {
  return deepSnakeToCamel(d) as Record<string, unknown>;
}

export function mapCase(d: Record<string, unknown>): Record<string, unknown> {
  const base = deepSnakeToCamel(d) as Record<string, unknown>;
  base.specialCategoryData = Boolean(d.special_category_data);
  base.internationalTransfer = Boolean(d.international_transfer);
  base.autoRunChecks = Boolean(d.auto_run_checks);
  base.playbookVersion = (d.playbook_version as string) ?? "";
  if (Array.isArray(d.documents)) {
    base.documents = (d.documents as Record<string, unknown>[]).map(mapDocument);
  }
  if (Array.isArray(d.findings)) {
    base.findings = (d.findings as Record<string, unknown>[]).map(mapFinding);
  }
  return base;
}

// ---------------------------------------------------------------------------
// Cases
// ---------------------------------------------------------------------------

export interface CasesFilter {
  q?: string;
  status?: string;
  department?: string;
  assignee?: string;
  created_by?: string;
  has_open_findings?: boolean;
  deadline_overdue?: boolean;
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
  autoRunChecks?: boolean;
  deadline?: string | null;
  archivedAt?: string | null;
  retentionMonths?: number | null;
  documents: ApiDocument[];
  findings: ApiFinding[];
  priority?: string;
}

export async function getCases(skip = 0, limit = 100, filter?: CasesFilter, includeArchived = false): Promise<ApiCase[]> {
  const params = new URLSearchParams({ skip: String(skip), limit: String(limit) });
  if (filter?.q) params.set("q", filter.q);
  if (filter?.status) params.set("status", filter.status);
  if (filter?.department) params.set("department", filter.department);
  if (filter?.assignee) params.set("assignee", filter.assignee);
  if (filter?.created_by) params.set("created_by", filter.created_by);
  if (filter?.has_open_findings !== undefined) params.set("has_open_findings", String(filter.has_open_findings));
  if (filter?.deadline_overdue !== undefined) params.set("deadline_overdue", String(filter.deadline_overdue));
  if (includeArchived) params.set("include_archived", "true");
  const data = await request<{ items?: Record<string, unknown>[]; total?: number } | Record<string, unknown>[]>("GET", `/cases?${params.toString()}`);
  const list: Record<string, unknown>[] = Array.isArray(data) ? data : ((data as { items?: Record<string, unknown>[] }).items ?? []);
  return list.map((c) => mapCase(c) as ApiCase);
}

export async function bulkUpdateCases(body: { case_ids: string[]; status?: string; archive?: boolean }): Promise<{ updated: number }> {
  return request<{ updated: number }>("PATCH", "/cases/bulk-update", { body });
}

export function getCasesExportUrl(filter?: CasesFilter, includeArchived = false, format: "csv" = "csv"): string {
  const params = new URLSearchParams({ format });
  if (filter?.q) params.set("q", filter.q);
  if (filter?.status) params.set("status", filter.status);
  if (filter?.department) params.set("department", filter.department);
  if (filter?.assignee) params.set("assignee", filter.assignee);
  if (filter?.created_by) params.set("created_by", filter.created_by);
  if (filter?.has_open_findings !== undefined) params.set("has_open_findings", String(filter.has_open_findings));
  if (includeArchived) params.set("include_archived", "true");
  return `${API_BASE}${API_PREFIX}/cases/export?${params.toString()}`;
}

export async function getCase(id: string): Promise<ApiCase> {
  const c = await request<Record<string, unknown>>("GET", `/cases/${id}`);
  return mapCase(c) as ApiCase;
}

export async function createCase(body: CaseCreateInput): Promise<ApiCase> {
  const c = await request<Record<string, unknown>>("POST", "/cases", { body });
  return mapCase(c) as ApiCase;
}

export async function archiveCase(id: string): Promise<ApiCase> {
  const c = await request<Record<string, unknown>>("POST", `/cases/${id}/archive`);
  return mapCase(c) as ApiCase;
}

export async function unarchiveCase(id: string): Promise<ApiCase> {
  const c = await request<Record<string, unknown>>("POST", `/cases/${id}/unarchive`);
  return mapCase(c) as ApiCase;
}

export async function updateCase(id: string, body: CaseUpdateInput): Promise<ApiCase> {
  const c = await request<Record<string, unknown>>("PATCH", `/cases/${id}`, { body });
  return mapCase(c) as ApiCase;
}

export async function deleteCase(id: string): Promise<void> {
  await request("DELETE", `/cases/${id}`);
}

// --- Run Checks ---
export type RunChecksStrategy = "full_text" | "rag";

export interface RunningCheckJob {
  jobId: string;
  caseId: string;
  caseTitle: string;
  playbookName: string | null;
  status: string;
  checksTotal: number;
  checksDone: number;
  createdAt: string | null;
}

export async function getRunningChecks(): Promise<RunningCheckJob[]> {
  const raw = await request<
    Array<{
      job_id: string;
      case_id: string;
      case_title: string;
      playbook_name: string | null;
      status: string;
      checks_total: number;
      checks_done: number;
      created_at: string | null;
    }>
  >("GET", "/cases/running-checks");
  return raw.map((r) => ({
    jobId: r.job_id,
    caseId: r.case_id,
    caseTitle: r.case_title,
    playbookName: r.playbook_name,
    status: r.status,
    checksTotal: r.checks_total,
    checksDone: r.checks_done,
    createdAt: r.created_at,
  }));
}

export interface RunChecksAcceptedResponse {
  accepted: true;
  jobId: string;
  status: "running";
}

export interface RunChecksStatusResponse {
  status: "never_run" | "running" | "completed" | "failed";
  job_id: string | null;
  playbook_name: string | null;
  findings_count: number | null;
  error: string | null;
  last_run: { id: string; case_id: string; event_type: string; payload: Record<string, unknown>; created_at: string } | null;
  documents_changed_since_last_run?: boolean;
  checks_total: number;
  checks_done: number;
}

export async function runChecks(
  caseId: string,
  playbookId: string,
  strategies: RunChecksStrategy[] = ["full_text"],
): Promise<ApiCase | RunChecksAcceptedResponse> {
  const url = `${API_BASE}${API_PREFIX}/cases/${caseId}/run-checks`;
  const headers: Record<string, string> = { ...authHeaders(), "Content-Type": "application/json" };
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
    documents_changed_since_last_run?: boolean;
    checks_total?: number;
    checks_done?: number;
  }>("GET", `/cases/${caseId}/run-checks/status`);
  return {
    status: raw.status as RunChecksStatusResponse["status"],
    job_id: raw.job_id,
    playbook_name: raw.playbook_name,
    findings_count: raw.findings_count,
    error: raw.error,
    last_run: raw.last_run,
    documents_changed_since_last_run: raw.documents_changed_since_last_run ?? false,
    checks_total: raw.checks_total ?? 0,
    checks_done: raw.checks_done ?? 0,
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

export interface DSBReportStatusResponse {
  status: "no_report" | "running" | "completed" | "failed";
  job_id: string | null;
  error: string | null;
}

export async function getDSBReportStatus(caseId: string): Promise<DSBReportStatusResponse> {
  return request<DSBReportStatusResponse>("GET", `/cases/${caseId}/dsb-report/status`);
}

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

// --- Case risk score ---
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

// --- Case similarity ---
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

// --- Audit Trail Export ---
export async function getAuditTrailExportBlob(caseId: string): Promise<Blob> {
  const url = `${API_BASE}${API_PREFIX}/cases/${caseId}/activities/export`;
  const res = await fetch(url, { headers: authHeaders() });
  if (!res.ok) {
    const detail = await parseErrorResponse(res);
    throw new Error(detail);
  }
  return res.blob();
}

export async function downloadAuditPackage(caseId: string): Promise<Blob> {
  const url = `${API_BASE}${API_PREFIX}/cases/${caseId}/audit-export`;
  const res = await fetch(url, { method: "POST", headers: authHeaders() });
  if (!res.ok) {
    const detail = await parseErrorResponse(res);
    throw new Error(detail);
  }
  return res.blob();
}

// --- DSFA Screening ---
export interface DsfaScreeningFactor {
  id: string;
  label: string;
  description: string;
  met: boolean;
}

export interface DsfaScreeningResult {
  case_id: string;
  required: boolean;
  score: number;
  threshold: number;
  factors: DsfaScreeningFactor[];
  recommendation: string;
}

export async function getDsfaScreening(caseId: string): Promise<DsfaScreeningResult> {
  return request<DsfaScreeningResult>("GET", `/cases/${caseId}/dsfa/screening`);
}
