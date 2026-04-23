/**
 * Core API infrastructure: error types, token management,
 * HTTP request helper, and shared utility functions.
 */

import { logger } from "../logger";

export const API_BASE = (import.meta as unknown as { env?: { VITE_API_URL?: string } }).env?.VITE_API_URL ?? "http://localhost:8002";
export const API_PREFIX = "/api/v1";

/**
 * Typed API error that includes the HTTP status code.
 * Callers can check `err instanceof ApiError && err.status === 401`
 * instead of parsing the error message string.
 */
export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** Token for authenticated requests (set by auth flow when OIDC is enabled). */
let accessToken: string | null = null;

/**
 * Enabled when the backend reports ``auth_session_cookie_enabled: true`` in
 * ``/auth/config``. When true, the SPA switches from the Bearer-token flow to
 * HttpOnly session cookies + CSRF double-submit.
 */
let sessionCookieMode = false;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

export function setSessionCookieMode(enabled: boolean): void {
  sessionCookieMode = enabled;
}

export function isSessionCookieMode(): boolean {
  return sessionCookieMode;
}

/** Name of the CSRF cookie the backend sets. Mirrors backend production /
 * development split (``__Host-ds_csrf`` vs ``ds_csrf``). The ``__Host-``
 * variant is used in production (Secure origins). */
function csrfCookieCandidates(): string[] {
  return ["__Host-ds_csrf", "ds_csrf"];
}

function readCookie(name: string): string | null {
  const prefix = `${name}=`;
  const parts = document.cookie.split(";");
  for (const raw of parts) {
    const trimmed = raw.trim();
    if (trimmed.startsWith(prefix)) {
      return decodeURIComponent(trimmed.slice(prefix.length));
    }
  }
  return null;
}

function readCsrfToken(): string | null {
  for (const name of csrfCookieCandidates()) {
    const v = readCookie(name);
    if (v) return v;
  }
  return null;
}

export function authHeaders(): Record<string, string> {
  const h: Record<string, string> = {};
  if (sessionCookieMode) {
    const csrf = readCsrfToken();
    if (csrf) h["X-CSRF-Token"] = csrf;
  } else if (accessToken) {
    h["Authorization"] = `Bearer ${accessToken}`;
  }
  return h;
}

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

// ---------------------------------------------------------------------------
// Generic snake_case → camelCase transformer
// ---------------------------------------------------------------------------

export function snakeToCamel(key: string): string {
  return key.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase());
}

export function deepSnakeToCamel(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(deepSnakeToCamel);
  if (value !== null && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>).map(([k, v]) => [
        snakeToCamel(k),
        deepSnakeToCamel(v),
      ])
    );
  }
  return value;
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

export async function request<T>(
  method: string,
  path: string,
  options?: { body?: unknown; formData?: FormData }
): Promise<T> {
  const url = `${API_BASE}${API_PREFIX}${path}`;
  const headers: Record<string, string> = { ...authHeaders() };
  let fetchBody: string | FormData | undefined;
  if (options?.formData) {
    fetchBody = options.formData;
  } else if (options?.body != null) {
    headers["Content-Type"] = "application/json";
    fetchBody = JSON.stringify(options.body);
  }

  let res: Response;
  const init: RequestInit = { method, headers, body: fetchBody };
  if (sessionCookieMode) {
    init.credentials = "include";
  }
  try {
    res = await fetch(url, init);
  } catch (networkErr) {
    logger.error("Network request failed", { method, path }, networkErr);
    throw new ApiError("Netzwerkfehler – bitte Verbindung prüfen.", 0);
  }

  if (!res.ok) {
    const detail = await parseErrorResponse(res);
    logger.warn("API request returned error", { method, path, status: res.status, detail });

    if (res.status === 401) {
      window.dispatchEvent(new CustomEvent("datenschutzagent:unauthorized"));
    }

    throw new ApiError(detail, res.status);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

/** Trigger download of a blob with suggested filename. */
export function downloadBlob(blob: Blob, filename: string): void {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}

/** Fetch a URL and return its body as a Blob. Throws ApiError on non-ok responses. */
export async function fetchBlob(url: string, method = "GET"): Promise<Blob> {
  const init: RequestInit = { method, headers: authHeaders() };
  if (sessionCookieMode) init.credentials = "include";
  const res = await fetch(url, init);
  if (!res.ok) {
    const detail = await parseErrorResponse(res);
    throw new ApiError(detail, res.status);
  }
  return res.blob();
}
