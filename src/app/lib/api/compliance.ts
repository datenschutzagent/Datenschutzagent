/**
 * Compliance API: data breaches, DSR requests, AVV contracts,
 * TOM catalog, case templates, privacy policies, and AVV risk assessment.
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
import { mapCase } from "./cases";
import type { ApiCase } from "./cases";

// ---------------------------------------------------------------------------
// Datenpannen-Management (Art. 33/34 DSGVO)
// ---------------------------------------------------------------------------

export interface ApiDataBreach {
  id: string;
  title: string;
  description: string | null;
  discoveredAt: string;
  notificationDeadline: string;
  breachType: "confidentiality" | "integrity" | "availability";
  affectedDataCategories: string[];
  affectedPersonsCount: number | null;
  department: string | null;
  assignee: string;
  status: "discovered" | "assessed" | "reported_to_authority" | "reported_to_subjects" | "closed" | "no_notification_required";
  riskLevel: "low" | "medium" | "high" | "critical" | null;
  authorityNotifiedAt: string | null;
  subjectsNotifiedAt: string | null;
  authorityReference: string | null;
  measuresTaken: string | null;
  draftNotification: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface ApiDataBreachActivity {
  id: string;
  breachId: string;
  eventType: string;
  payload: Record<string, unknown>;
  createdAt: string;
}

export interface DataBreachCreate {
  title: string;
  description?: string;
  discovered_at: string;
  breach_type: "confidentiality" | "integrity" | "availability";
  affected_data_categories?: string[];
  affected_persons_count?: number;
  department?: string;
  assignee?: string;
  risk_level?: "low" | "medium" | "high" | "critical";
  measures_taken?: string;
}

export interface DataBreachUpdate {
  title?: string;
  description?: string;
  status?: string;
  breach_type?: string;
  affected_data_categories?: string[];
  affected_persons_count?: number;
  department?: string;
  assignee?: string;
  risk_level?: string;
  authority_notified_at?: string;
  subjects_notified_at?: string;
  authority_reference?: string;
  measures_taken?: string;
}

function mapDataBreach(d: Record<string, unknown>): ApiDataBreach {
  return deepSnakeToCamel(d) as unknown as ApiDataBreach;
}

export async function listDataBreaches(params: {
  status?: string;
  riskLevel?: string;
  department?: string;
  overdueOnly?: boolean;
  skip?: number;
  limit?: number;
} = {}): Promise<{ items: ApiDataBreach[]; total: number }> {
  const q = new URLSearchParams();
  if (params.status) q.set("status", params.status);
  if (params.riskLevel) q.set("risk_level", params.riskLevel);
  if (params.department) q.set("department", params.department);
  if (params.overdueOnly) q.set("overdue_only", "true");
  if (params.skip != null) q.set("skip", String(params.skip));
  if (params.limit != null) q.set("limit", String(params.limit));
  const qs = q.toString();
  const r = await request<Record<string, unknown>>("GET", `/data-breaches${qs ? "?" + qs : ""}`);
  const items = ((r.items as Record<string, unknown>[]) ?? []).map(mapDataBreach);
  return { items, total: Number(r.total ?? 0) };
}

export async function createDataBreach(body: DataBreachCreate): Promise<ApiDataBreach> {
  return mapDataBreach(
    await request<Record<string, unknown>>("POST", "/data-breaches", { body })
  );
}

export async function getDataBreach(id: string): Promise<ApiDataBreach> {
  return mapDataBreach(await request<Record<string, unknown>>("GET", `/data-breaches/${id}`));
}

export async function updateDataBreach(id: string, body: DataBreachUpdate): Promise<ApiDataBreach> {
  return mapDataBreach(
    await request<Record<string, unknown>>("PATCH", `/data-breaches/${id}`, { body })
  );
}

export async function deleteDataBreach(id: string): Promise<void> {
  await request<void>("DELETE", `/data-breaches/${id}`);
}

export async function generateBreachNotification(id: string): Promise<ApiDataBreach> {
  return mapDataBreach(
    await request<Record<string, unknown>>("POST", `/data-breaches/${id}/generate-notification`)
  );
}

export async function getDataBreachActivity(id: string): Promise<ApiDataBreachActivity[]> {
  const list = (await request<Record<string, unknown>[]>("GET", `/data-breaches/${id}/activity`)) ?? [];
  return list.map((a) => deepSnakeToCamel(a) as unknown as ApiDataBreachActivity);
}

// ---------------------------------------------------------------------------
// Betroffenenrechte / DSR (Art. 15–22 DSGVO)
// ---------------------------------------------------------------------------

export type DSRRequestType = "access" | "rectification" | "erasure" | "portability" | "restriction" | "objection";
export type DSRStatus = "received" | "in_progress" | "response_sent" | "closed" | "denied";

export interface ApiDSRRequest {
  id: string;
  requestType: DSRRequestType;
  requestorName: string | null;
  requestorEmail: string | null;
  description: string | null;
  department: string | null;
  status: DSRStatus;
  assignee: string;
  receivedAt: string;
  responseDeadline: string;
  respondedAt: string | null;
  responseSummary: string | null;
  draftResponse: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface ApiDSRActivity {
  id: string;
  requestId: string;
  eventType: string;
  payload: Record<string, unknown>;
  createdAt: string;
}

export interface DSRRequestCreate {
  request_type: DSRRequestType;
  requestor_name?: string;
  requestor_email?: string;
  description?: string;
  department?: string;
  assignee?: string;
  received_at: string;
  deadline_extension_days?: number;
}

export interface DSRRequestUpdate {
  status?: DSRStatus;
  assignee?: string;
  response_summary?: string;
  responded_at?: string;
  department?: string;
}

function mapDSR(d: Record<string, unknown>): ApiDSRRequest {
  return deepSnakeToCamel(d) as unknown as ApiDSRRequest;
}

export async function listDSRRequests(params: {
  status?: string;
  requestType?: string;
  assignee?: string;
  overdueOnly?: boolean;
  skip?: number;
  limit?: number;
} = {}): Promise<{ items: ApiDSRRequest[]; total: number }> {
  const q = new URLSearchParams();
  if (params.status) q.set("status", params.status);
  if (params.requestType) q.set("request_type", params.requestType);
  if (params.assignee) q.set("assignee", params.assignee);
  if (params.overdueOnly) q.set("overdue_only", "true");
  if (params.skip != null) q.set("skip", String(params.skip));
  if (params.limit != null) q.set("limit", String(params.limit));
  const qs = q.toString();
  const r = await request<Record<string, unknown>>("GET", `/dsr${qs ? "?" + qs : ""}`);
  const items = ((r.items as Record<string, unknown>[]) ?? []).map(mapDSR);
  return { items, total: Number(r.total ?? 0) };
}

export async function createDSRRequest(body: DSRRequestCreate): Promise<ApiDSRRequest> {
  return mapDSR(await request<Record<string, unknown>>("POST", "/dsr", { body }));
}

export async function getDSRRequest(id: string): Promise<ApiDSRRequest> {
  return mapDSR(await request<Record<string, unknown>>("GET", `/dsr/${id}`));
}

export async function updateDSRRequest(id: string, body: DSRRequestUpdate): Promise<ApiDSRRequest> {
  return mapDSR(await request<Record<string, unknown>>("PATCH", `/dsr/${id}`, { body }));
}

export async function deleteDSRRequest(id: string): Promise<void> {
  await request<void>("DELETE", `/dsr/${id}`);
}

export async function generateDSRDraft(id: string): Promise<ApiDSRRequest> {
  return mapDSR(await request<Record<string, unknown>>("POST", `/dsr/${id}/generate-draft`));
}

export async function getDSRActivity(id: string): Promise<ApiDSRActivity[]> {
  const list = (await request<Record<string, unknown>[]>("GET", `/dsr/${id}/activity`)) ?? [];
  return list.map((a) => deepSnakeToCamel(a) as unknown as ApiDSRActivity);
}

// ---------------------------------------------------------------------------
// AVV-Management (Art. 28 DSGVO)
// ---------------------------------------------------------------------------

export interface ApiAVVContract {
  id: string;
  partnerName: string;
  partnerType: "processor" | "sub_processor";
  subjectMatter: string | null;
  department: string | null;
  status: "pending" | "under_review" | "signed" | "expired" | "terminated";
  contractDate: string | null;
  expiryDate: string | null;
  assignee: string;
  documentName: string | null;
  notes: string | null;
  checkResult: Record<string, unknown> | null;
  riskScore: number | null;
  riskLevel: "low" | "medium" | "high" | "critical" | null;
  inherentRiskScore?: number | null;
  inherentRiskLevel?: "low" | "medium" | "high" | "critical" | null;
  riskSource?: "llm" | "rules" | "hybrid" | null;
  riskConfidence?: number | null;
  riskAssessedAt: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface AVVCreate {
  partner_name: string;
  partner_type?: "processor" | "sub_processor";
  subject_matter?: string;
  department?: string;
  assignee?: string;
  contract_date?: string;
  expiry_date?: string;
  notes?: string;
}

export interface AVVUpdate {
  partner_name?: string;
  partner_type?: string;
  subject_matter?: string;
  department?: string;
  status?: string;
  assignee?: string;
  contract_date?: string;
  expiry_date?: string;
  notes?: string;
}

function mapAVV(d: Record<string, unknown>): ApiAVVContract {
  return deepSnakeToCamel(d) as unknown as ApiAVVContract;
}

export async function listAVVContracts(params: {
  status?: string;
  department?: string;
  partnerType?: string;
  expiringSoon?: boolean;
} = {}): Promise<{ items: ApiAVVContract[]; total: number }> {
  const q = new URLSearchParams();
  if (params.status) q.set("status", params.status);
  if (params.department) q.set("department", params.department);
  if (params.partnerType) q.set("partner_type", params.partnerType);
  if (params.expiringSoon) q.set("expiring_soon", "true");
  const qs = q.toString();
  const r = await request<Record<string, unknown>>("GET", `/avv${qs ? "?" + qs : ""}`);
  const items = ((r.items as Record<string, unknown>[]) ?? []).map(mapAVV);
  return { items, total: Number(r.total ?? 0) };
}

export async function createAVVContract(body: AVVCreate): Promise<ApiAVVContract> {
  return mapAVV(await request<Record<string, unknown>>("POST", "/avv", { body }));
}

export async function updateAVVContract(id: string, body: AVVUpdate): Promise<ApiAVVContract> {
  return mapAVV(await request<Record<string, unknown>>("PATCH", `/avv/${id}`, { body }));
}

export async function deleteAVVContract(id: string): Promise<void> {
  await request<void>("DELETE", `/avv/${id}`);
}

// ---------------------------------------------------------------------------
// TOM-Katalog (Art. 32 DSGVO)
// ---------------------------------------------------------------------------

export type TOMCategory =
  | "access_control" | "encryption" | "pseudonymization" | "availability"
  | "integrity" | "confidentiality" | "resilience" | "testing" | "incident_response" | "other";
export type TOMStatus = "planned" | "in_progress" | "implemented" | "not_applicable";

export interface ApiTOM {
  id: string;
  title: string;
  description: string | null;
  category: TOMCategory;
  implementationStatus: TOMStatus;
  responsible: string;
  reviewDate: string | null;
  evidence: string | null;
  departmentCodes: string[];
  createdAt: string;
  updatedAt: string;
}

export interface ApiTOMStats {
  total: number;
  byStatus: Record<string, number>;
  byCategory: Record<string, number>;
  implementationRate: number;
}

export interface TOMCreate {
  title: string;
  description?: string;
  category: TOMCategory;
  implementation_status?: TOMStatus;
  responsible?: string;
  review_date?: string;
  evidence?: string;
  department_codes?: string[];
}

export interface TOMUpdate {
  title?: string;
  description?: string;
  category?: TOMCategory;
  implementation_status?: TOMStatus;
  responsible?: string;
  review_date?: string;
  evidence?: string;
  department_codes?: string[];
}

export interface ApiTOMAttachment {
  id: string;
  tomId: string;
  name: string;
  format: string;
  sizeBytes: number;
  size: string;
  uploadedBy: string;
  uploadedAt: string;
}

function mapTOM(d: Record<string, unknown>): ApiTOM {
  return deepSnakeToCamel(d) as unknown as ApiTOM;
}

function mapTOMAttachment(d: Record<string, unknown>): ApiTOMAttachment {
  const base = deepSnakeToCamel(d) as unknown as ApiTOMAttachment;
  base.size = typeof d.size_bytes === "number" ? formatBytes(d.size_bytes) : "";
  return base;
}

export async function listTOMs(params: {
  category?: string;
  implementationStatus?: string;
  departmentCode?: string;
} = {}): Promise<{ items: ApiTOM[]; total: number }> {
  const q = new URLSearchParams();
  if (params.category) q.set("category", params.category);
  if (params.implementationStatus) q.set("implementation_status", params.implementationStatus);
  if (params.departmentCode) q.set("department_code", params.departmentCode);
  const qs = q.toString();
  const r = await request<Record<string, unknown>>("GET", `/tom${qs ? "?" + qs : ""}`);
  const items = ((r.items as Record<string, unknown>[]) ?? []).map(mapTOM);
  return { items, total: Number(r.total ?? 0) };
}

export async function getTOMStats(): Promise<ApiTOMStats> {
  const r = await request<Record<string, unknown>>("GET", "/tom/stats");
  return deepSnakeToCamel(r) as unknown as ApiTOMStats;
}

export async function createTOM(body: TOMCreate): Promise<ApiTOM> {
  return mapTOM(await request<Record<string, unknown>>("POST", "/tom", { body }));
}

export async function updateTOM(id: string, body: TOMUpdate): Promise<ApiTOM> {
  return mapTOM(await request<Record<string, unknown>>("PATCH", `/tom/${id}`, { body }));
}

export async function deleteTOM(id: string): Promise<void> {
  await request<void>("DELETE", `/tom/${id}`);
}

export async function listTOMAttachments(tomId: string): Promise<ApiTOMAttachment[]> {
  const list = await request<Record<string, unknown>[]>("GET", `/tom/${tomId}/attachments`);
  return (list ?? []).map(mapTOMAttachment);
}

export async function uploadTOMAttachment(
  tomId: string,
  file: File,
  uploadedBy: string,
): Promise<ApiTOMAttachment> {
  const form = new FormData();
  form.append("file", file);
  form.append("uploaded_by", uploadedBy);
  const d = await request<Record<string, unknown>>("POST", `/tom/${tomId}/attachments`, { formData: form });
  return mapTOMAttachment(d);
}

export async function getTOMAttachmentBlob(tomId: string, attachmentId: string): Promise<Blob> {
  const url = `${API_BASE}${API_PREFIX}/tom/${tomId}/attachments/${attachmentId}/download`;
  const res = await fetch(url, { headers: authHeaders() });
  if (!res.ok) {
    const detail = await parseErrorResponse(res);
    throw new Error(detail);
  }
  return res.blob();
}

export async function deleteTOMAttachment(tomId: string, attachmentId: string): Promise<void> {
  await request<void>("DELETE", `/tom/${tomId}/attachments/${attachmentId}`);
}

// ---------------------------------------------------------------------------
// Vorgangs-Vorlagen (Case Templates)
// ---------------------------------------------------------------------------

export interface ApiCaseTemplate {
  id: string;
  name: string;
  description: string | null;
  caseType: string;
  department: string | null;
  language: string;
  processingContext: string | null;
  specialCategoryData: boolean;
  internationalTransfer: boolean;
  isBuiltin: boolean;
  createdBy: string;
  createdAt: string;
  updatedAt: string;
}

export interface CaseTemplateCreate {
  name: string;
  description?: string;
  case_type: string;
  department?: string;
  language?: string;
  processing_context?: string;
  special_category_data?: boolean;
  international_transfer?: boolean;
}

export interface CaseTemplateApply {
  template_id: string;
  title: string;
  assignee?: string;
  deadline?: string;
}

function mapCaseTemplate(d: Record<string, unknown>): ApiCaseTemplate {
  return deepSnakeToCamel(d) as unknown as ApiCaseTemplate;
}

export async function listCaseTemplates(params: {
  caseType?: string;
  department?: string;
} = {}): Promise<ApiCaseTemplate[]> {
  const q = new URLSearchParams();
  if (params.caseType) q.set("case_type", params.caseType);
  if (params.department) q.set("department", params.department);
  const qs = q.toString();
  const list = (await request<Record<string, unknown>[]>("GET", `/case-templates${qs ? "?" + qs : ""}`)) ?? [];
  return list.map(mapCaseTemplate);
}

export async function createCaseTemplate(body: CaseTemplateCreate): Promise<ApiCaseTemplate> {
  return mapCaseTemplate(await request<Record<string, unknown>>("POST", "/case-templates", { body }));
}

export async function deleteCaseTemplate(id: string): Promise<void> {
  await request<void>("DELETE", `/case-templates/${id}`);
}

export async function applyCaseTemplate(body: CaseTemplateApply): Promise<ApiCase> {
  return mapCase(await request<Record<string, unknown>>("POST", "/case-templates/apply", { body })) as ApiCase;
}

// ---------------------------------------------------------------------------
// Datenschutzerklärung (Privacy Policy) – vorgangsspezifisch
// ---------------------------------------------------------------------------

export interface ApiPrivacyPolicy {
  id: string;
  case_id: string;
  version: number;
  title: string;
  content_markdown: string;
  version_note: string | null;
  generated_at: string;
  created_by: string;
}

/** Globale read-only Übersicht aller Datenschutzerklärungen (alle Cases). */
export async function listPrivacyPolicies(): Promise<ApiPrivacyPolicy[]> {
  return request<ApiPrivacyPolicy[]>("GET", "/privacy-policies");
}

/** Versionen einer Datenschutzerklärung für einen konkreten Vorgang. */
export async function listPrivacyPoliciesForCase(caseId: string): Promise<ApiPrivacyPolicy[]> {
  return request<ApiPrivacyPolicy[]>("GET", `/cases/${caseId}/privacy-policies`);
}

/** Neue, vorgangsspezifische Datenschutzerklärung generieren. */
export async function generatePrivacyPolicyForCase(
  caseId: string,
  body: { contact?: string; notes?: string } = {}
): Promise<ApiPrivacyPolicy> {
  return request<ApiPrivacyPolicy>("POST", `/cases/${caseId}/privacy-policies/generate`, { body });
}

export async function getPrivacyPolicy(id: string): Promise<ApiPrivacyPolicy> {
  return request<ApiPrivacyPolicy>("GET", `/privacy-policies/${id}`);
}

export async function updatePrivacyPolicy(
  id: string,
  body: { title?: string; content_markdown?: string; version_note?: string }
): Promise<ApiPrivacyPolicy> {
  return request<ApiPrivacyPolicy>("PATCH", `/privacy-policies/${id}`, { body });
}

export async function deletePrivacyPolicy(id: string): Promise<void> {
  await request<void>("DELETE", `/privacy-policies/${id}`);
}

// ---------------------------------------------------------------------------
// AVV-Risikobewertung
// ---------------------------------------------------------------------------

export interface AvvRiskDimension {
  name: string;
  score: number;
  rationale: string;
}

export interface AvvRiskAssessment {
  contract_id: string;
  partner_name: string;
  risk_score: number;
  risk_level: "low" | "medium" | "high" | "critical";
  assessment: {
    dimensions: AvvRiskDimension[];
    main_risks: string[];
    recommended_measures: string[];
    summary: string;
    avg_dimension_score: number;
    confidence?: number;
    low_confidence?: boolean;
  };
  assessed_at: string;
}

export async function assessAvvRisk(contractId: string): Promise<AvvRiskAssessment> {
  return request<AvvRiskAssessment>("POST", `/avv/${contractId}/risk-assessment`);
}

// ---------------------------------------------------------------------------
// Stats-Endpunkte
// ---------------------------------------------------------------------------

export interface DSRMonthlyVolumeItem {
  month: string;
  count: number;
}

export interface DSRStats {
  total: number;
  byType: Record<string, number>;
  byStatus: Record<string, number>;
  avgResponseDays: number | null;
  onTimeRate: number | null;
  overdueCount: number;
  monthlyVolume: DSRMonthlyVolumeItem[];
}

export async function getDSRStats(): Promise<DSRStats> {
  const r = await request<Record<string, unknown>>("GET", "/dsr/stats");
  return deepSnakeToCamel(r) as unknown as DSRStats;
}

export interface DataBreachMonthlyItem {
  month: string;
  count: number;
  totalPersons: number;
}

export interface DataBreachStats {
  total: number;
  byStatus: Record<string, number>;
  byRiskLevel: Record<string, number>;
  byBreachType: Record<string, number>;
  notificationComplianceRate: number | null;
  avgAffectedPersons: number | null;
  monthlyTrend: DataBreachMonthlyItem[];
}

export async function getDataBreachStats(): Promise<DataBreachStats> {
  const r = await request<Record<string, unknown>>("GET", "/data-breaches/stats");
  return deepSnakeToCamel(r) as unknown as DataBreachStats;
}

export interface AVVStats {
  total: number;
  byStatus: Record<string, number>;
  expiringSoon: number;
  expired: number;
  avgRiskScore: number | null;
  byRiskLevel: Record<string, number>;
}

export async function getAVVStats(): Promise<AVVStats> {
  const r = await request<Record<string, unknown>>("GET", "/avv/stats");
  return deepSnakeToCamel(r) as unknown as AVVStats;
}

// ---------------------------------------------------------------------------
// Mitigation-Katalog & -Verknüpfungen (Art. 32 / Art. 35 DSGVO)
// ---------------------------------------------------------------------------

export interface ApiMitigationReduction {
  scoreDelta: number;
  dimensionDeltas: Record<string, number>;
  likelihoodDelta: number;
  severityDelta: number;
  applicableRiskKeywords: string[];
}

export interface ApiMitigationCatalogEntry {
  id: string;
  label: string;
  description: string;
  appliesTo: "avv" | "dsfa" | "both";
  tomCategory: string | null;
  evidenceRequired: boolean;
  reduction: ApiMitigationReduction;
}

export interface ApiMitigationCatalog {
  enabled: boolean;
  minLikelihood: number;
  minSeverity: number;
  minAvvScore: number;
  catalog: ApiMitigationCatalogEntry[];
}

export interface ApiMitigationLink {
  id: string;
  mitigationId: string;
  tomId: string | null;
  appliedBy: string;
  notes: string | null;
  appliedAt: string;
  catalogEntry: ApiMitigationCatalogEntry | null;
}

export interface ApiCaseMitigationLink extends ApiMitigationLink {
  caseId: string;
  evidenceDocId: string | null;
}

export interface ApiAvvMitigationLink extends ApiMitigationLink {
  avvContractId: string;
}

export interface MitigationLinkRequest {
  mitigation_id: string;
  tom_id?: string | null;
  evidence_doc_id?: string | null;
  notes?: string | null;
}

export interface ApiRiskDeltaSide {
  riskScore: number | null;
  riskLevel: string | null;
}

export interface ApiRiskDelta {
  targetType: "avv" | "dsfa";
  targetId: string;
  inherent: ApiRiskDeltaSide;
  residual: ApiRiskDeltaSide;
  appliedMitigations: string[];
  appliedEffects: Record<string, unknown>[];
  assessedAt: string | null;
}

export async function getMitigationCatalog(): Promise<ApiMitigationCatalog> {
  const r = await request<Record<string, unknown>>("GET", "/mitigations/catalog");
  return deepSnakeToCamel(r) as unknown as ApiMitigationCatalog;
}

export async function listCaseMitigations(caseId: string): Promise<ApiCaseMitigationLink[]> {
  const r = await request<Record<string, unknown>[]>("GET", `/cases/${caseId}/mitigations`);
  return (r ?? []).map((row) => deepSnakeToCamel(row) as unknown as ApiCaseMitigationLink);
}

export async function linkCaseMitigation(
  caseId: string,
  body: MitigationLinkRequest,
): Promise<ApiCaseMitigationLink> {
  const r = await request<Record<string, unknown>>("POST", `/cases/${caseId}/mitigations`, { body });
  return deepSnakeToCamel(r) as unknown as ApiCaseMitigationLink;
}

export async function unlinkCaseMitigation(caseId: string, mitigationId: string): Promise<void> {
  await request<void>("DELETE", `/cases/${caseId}/mitigations/${encodeURIComponent(mitigationId)}`);
}

export async function getCaseRiskDelta(caseId: string): Promise<ApiRiskDelta> {
  const r = await request<Record<string, unknown>>("GET", `/cases/${caseId}/risk-delta`);
  return deepSnakeToCamel(r) as unknown as ApiRiskDelta;
}

export async function listAvvMitigations(contractId: string): Promise<ApiAvvMitigationLink[]> {
  const r = await request<Record<string, unknown>[]>("GET", `/avv/${contractId}/mitigations`);
  return (r ?? []).map((row) => deepSnakeToCamel(row) as unknown as ApiAvvMitigationLink);
}

export async function linkAvvMitigation(
  contractId: string,
  body: MitigationLinkRequest,
): Promise<ApiAvvMitigationLink> {
  const r = await request<Record<string, unknown>>("POST", `/avv/${contractId}/mitigations`, { body });
  return deepSnakeToCamel(r) as unknown as ApiAvvMitigationLink;
}

export async function unlinkAvvMitigation(contractId: string, mitigationId: string): Promise<void> {
  await request<void>("DELETE", `/avv/${contractId}/mitigations/${encodeURIComponent(mitigationId)}`);
}

export async function getAvvRiskDelta(contractId: string): Promise<ApiRiskDelta> {
  const r = await request<Record<string, unknown>>("GET", `/avv/${contractId}/risk-delta`);
  return deepSnakeToCamel(r) as unknown as ApiRiskDelta;
}
