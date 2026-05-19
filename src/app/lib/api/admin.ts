/**
 * Auth, user profile, and admin management API.
 * Covers: OIDC config, current user, admin settings, connections,
 * prompt templates, user management, retention, notifications, webhooks.
 */

import { API_BASE, API_PREFIX, deepSnakeToCamel, parseErrorResponse, request } from "./core";

// --- Auth config (public, no token) ---
export interface AuthConfig {
  oidc_enabled: boolean;
  oidc_issuer_url: string;
  oidc_client_id: string;
  oidc_scopes: string[];
  authorization_endpoint?: string;
  token_endpoint?: string;
  end_session_endpoint?: string;
  /**
   * When true, the SPA uses the HttpOnly session-cookie flow. Instead of
   * exchanging the PKCE code for an access token and storing it in JS, the
   * frontend POSTs the code to ``/auth/session`` and the backend sets the
   * session + CSRF cookies. All subsequent API calls use ``credentials:
   * 'include'`` and echo the CSRF cookie in an ``X-CSRF-Token`` header.
   */
  auth_session_cookie_enabled?: boolean;
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

// --- Session-cookie flow (opt-in via auth_session_cookie_enabled) ---

export async function startSessionCookie(body: {
  code: string;
  redirect_uri: string;
  code_verifier: string;
}): Promise<void> {
  const url = `${API_BASE}${API_PREFIX}/auth/session`;
  const res = await fetch(url, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await parseErrorResponse(res);
    throw new Error(detail || "Session exchange failed");
  }
}

export async function endSessionCookie(): Promise<void> {
  const url = `${API_BASE}${API_PREFIX}/auth/logout`;
  await fetch(url, { method: "POST", credentials: "include" });
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
  max_context_chars_per_doc?: number;
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

// --- Admin: User management ---
export async function listAdminUsers(): Promise<ApiUser[]> {
  return request<ApiUser[]>("GET", "/admin/users");
}

export async function updateAdminUserRole(userId: string, role: UserRole): Promise<ApiUser> {
  return request<ApiUser>("PATCH", `/admin/users/${userId}/role`, { body: { role } });
}

// --- Admin: Retention Management ---
export interface ApiRetentionPreviewItem {
  case_id: string;
  title: string;
  department: string;
  retention_months: number;
  updated_at: string | null;
}

export interface ApiRetentionPreviewResponse {
  would_archive_count: number;
  items: ApiRetentionPreviewItem[];
}

export interface ApiRetentionScanResponse {
  archived_count: number;
  archived: ApiRetentionPreviewItem[];
}

export async function getRetentionPreview(): Promise<ApiRetentionPreviewResponse> {
  return request<ApiRetentionPreviewResponse>("GET", "/admin/retention/preview");
}

export async function triggerRetentionScan(): Promise<ApiRetentionScanResponse> {
  return request<ApiRetentionScanResponse>("POST", "/admin/retention/scan");
}

// --- Admin: Notifications ---
export interface ApiNotificationTestResponse {
  smtp_enabled: boolean;
  status: string;
  detail?: string | null;
}

export async function testSmtp(): Promise<ApiNotificationTestResponse> {
  return request<ApiNotificationTestResponse>("GET", "/admin/notifications/test-smtp");
}

export async function triggerDeadlineNotifications(): Promise<{ sent_count: number; checked_count?: number }> {
  return request<{ sent_count: number; checked_count?: number }>("POST", "/admin/notifications/scan-deadlines");
}

// --- Webhooks ---
export interface ApiWebhook {
  id: string;
  name: string;
  url: string;
  hasSecret: boolean;
  events: string[];
  isActive: boolean;
  createdBy: string;
}

export interface ApiWebhookDelivery {
  id: string;
  webhookId: string;
  eventType: string;
  status: string;
  httpStatus: number | null;
  error: string | null;
  attempts: number;
  deliveredAt: string | null;
}

function mapWebhook(d: Record<string, unknown>): ApiWebhook {
  return deepSnakeToCamel(d) as unknown as ApiWebhook;
}

export async function listWebhooks(): Promise<ApiWebhook[]> {
  const list = await request<Record<string, unknown>[]>("GET", "/admin/webhooks");
  return list.map(mapWebhook);
}

export async function createWebhook(body: {
  name: string;
  url: string;
  secret?: string;
  events?: string[];
}): Promise<ApiWebhook> {
  return mapWebhook(await request<Record<string, unknown>>("POST", "/admin/webhooks", { body }));
}

export async function updateWebhook(
  id: string,
  body: { name?: string; url?: string; secret?: string; events?: string[]; is_active?: boolean }
): Promise<ApiWebhook> {
  return mapWebhook(await request<Record<string, unknown>>("PATCH", `/admin/webhooks/${id}`, { body }));
}

export async function deleteWebhook(id: string): Promise<void> {
  await request<void>("DELETE", `/admin/webhooks/${id}`);
}

export async function testWebhook(id: string): Promise<{ success: boolean; http_status: number | null; error: string | null }> {
  return request("POST", `/admin/webhooks/${id}/test`);
}

export async function getWebhookEvents(): Promise<string[]> {
  return request<string[]>("GET", "/admin/webhooks/events");
}

// ---------------------------------------------------------------------------
// Risk-Config admin endpoints (Phase C / Item 13)
// ---------------------------------------------------------------------------

import type {
  AdminRiskConfigPreviewResponse,
  AdminRiskConfigResponse,
  RiskConfig,
} from "./types/risk-config";

export async function getAdminRiskConfig(): Promise<AdminRiskConfigResponse> {
  return request<AdminRiskConfigResponse>("GET", "/admin/risk-config");
}

export async function updateAdminRiskConfig(
  config: RiskConfig
): Promise<AdminRiskConfigResponse> {
  return request<AdminRiskConfigResponse>("PUT", "/admin/risk-config", {
    body: { config },
  });
}

export async function reloadAdminRiskConfig(): Promise<{ reloaded: boolean }> {
  return request<{ reloaded: boolean }>("POST", "/admin/risk-config/reload");
}

export async function previewAdminRiskConfig(
  config: RiskConfig
): Promise<AdminRiskConfigPreviewResponse> {
  return request<AdminRiskConfigPreviewResponse>("POST", "/admin/risk-config/preview", {
    body: { config },
  });
}
