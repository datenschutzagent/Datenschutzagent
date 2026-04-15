/**
 * Documents API: upload, download, CRUD, comments, and app config.
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
import type { ApiDocument, DocumentType } from "./cases";

// Private mapper
function mapDocument(d: Record<string, unknown>): Record<string, unknown> {
  const base = deepSnakeToCamel(d) as Record<string, unknown>;
  const sizeBytes = d.size_bytes as number | undefined;
  base.size = sizeBytes != null ? formatBytes(sizeBytes) : "";
  return base;
}

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

/** Upload multiple documents in one request. Same documentType and uploadedBy for all. */
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

export async function updateDocument(
  documentId: string,
  body: { content?: string }
): Promise<ApiDocument> {
  const d = await request<Record<string, unknown>>("PATCH", `/documents/${documentId}`, { body });
  return mapDocument(d) as ApiDocument;
}

export async function getDocumentDownloadBlob(documentId: string): Promise<Blob> {
  const url = `${API_BASE}${API_PREFIX}/documents/${documentId}/download`;
  const res = await fetch(url, { headers: authHeaders() });
  if (!res.ok) {
    const detail = await parseErrorResponse(res);
    throw new Error(detail);
  }
  return res.blob();
}

export interface DocumentContentResponse {
  content: string;
  extractionStatus?: "pending" | "processing" | "done" | "failed";
  extractionError?: string;
}

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
