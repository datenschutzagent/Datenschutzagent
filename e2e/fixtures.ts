import { test as base, expect, type APIRequestContext, type Page } from "@playwright/test";

/**
 * Shared E2E fixtures: every test gets its own case, seeded through the REST API
 * (not through the UI), and the case is deleted again when the test is done.
 *
 * Environment:
 *   E2E_BASE_URL  frontend (default http://localhost:3002, see playwright.config.ts)
 *   E2E_API_URL   backend  (default http://localhost:8002)
 *
 * The backend is expected to run with OIDC disabled and RBAC_DEFAULT_ROLE=admin
 * (as in the CI docker stack), so requests need no bearer token. If the default
 * user lacks edit rights the seeding fails loudly with the 403 body instead of
 * silently skipping.
 */

export const API_URL = (process.env.E2E_API_URL ?? "http://localhost:8002").replace(/\/$/, "");
export const API_PREFIX = "/api/v1";

/** Department value used for all seeded cases. */
export const E2E_DEPARTMENT = "E2E Testabteilung";
/** Matches the case_type of the YAML-seeded default playbooks (default_dsgvo_art30.yaml). */
export const E2E_CASE_TYPE = "Allgemein";

/** Text rendered by the React ErrorBoundary / route fallback when a subtree crashes. */
export const ERROR_BOUNDARY_TEXTS = [
  "Dieser Bereich konnte nicht geladen werden.",
  "Diese Seite konnte nicht angezeigt werden.",
];

export interface SeededCase {
  id: string;
  title: string;
  department: string;
  caseType: string;
}

export interface SeededDocument {
  id: string;
  name: string;
  extractionStatus: string;
}

interface CaseResponseRaw {
  id: string;
  title: string;
  department: string;
  case_type: string;
}

interface DocumentResponseRaw {
  id: string;
  name: string;
  extraction_status?: string | null;
}

interface PlaybookRaw {
  id: string;
  name: string;
  is_active: boolean;
}

/** Unique, human-readable title so the case can be found by search and identified in the DB. */
export function uniqueTitle(label: string): string {
  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
  const rand = Math.random().toString(36).slice(2, 8);
  return `E2E ${label} ${stamp} ${rand}`;
}

async function expectOk(res: { ok(): boolean; status(): number; text(): Promise<string> }, what: string) {
  if (!res.ok()) {
    throw new Error(`${what} failed: HTTP ${res.status()} ${await res.text()}`);
  }
}

export async function createCase(
  api: APIRequestContext,
  overrides: Partial<{ title: string; department: string; case_type: string }> = {},
): Promise<SeededCase> {
  const res = await api.post(`${API_PREFIX}/cases`, {
    data: {
      title: overrides.title ?? uniqueTitle("Vorgang"),
      department: overrides.department ?? E2E_DEPARTMENT,
      case_type: overrides.case_type ?? E2E_CASE_TYPE,
      language: "de",
      created_by: "e2e",
      assignee: "E2E Bot",
    },
  });
  await expectOk(res, "POST /cases");
  const raw = (await res.json()) as CaseResponseRaw;
  return { id: raw.id, title: raw.title, department: raw.department, caseType: raw.case_type };
}

export async function deleteCase(api: APIRequestContext, caseId: string): Promise<void> {
  const res = await api.delete(`${API_PREFIX}/cases/${caseId}`);
  // 404 is fine: the test may have deleted/archived the case itself.
  if (!res.ok() && res.status() !== 404) {
    throw new Error(`DELETE /cases/${caseId} failed: HTTP ${res.status()} ${await res.text()}`);
  }
}

/** Small CSV body; CSV is one of the formats the backend accepts and extracts synchronously. */
export function csvDocument(marker: string): { name: string; mimeType: string; buffer: Buffer } {
  const body = ["Feld;Wert", `Verantwortlicher;${marker}`, "Zweck;E2E-Testdokument", ""].join("\n");
  return { name: `e2e-dokument-${Date.now()}.csv`, mimeType: "text/csv", buffer: Buffer.from(body, "utf8") };
}

export async function uploadDocument(
  api: APIRequestContext,
  caseId: string,
  file: { name: string; mimeType: string; buffer: Buffer },
  documentType = "other",
): Promise<SeededDocument> {
  const res = await api.post(`${API_PREFIX}/documents`, {
    multipart: {
      case_id: caseId,
      document_type: documentType,
      uploaded_by: "e2e",
      file,
    },
  });
  await expectOk(res, "POST /documents");
  const raw = (await res.json()) as DocumentResponseRaw;
  return { id: raw.id, name: raw.name, extractionStatus: raw.extraction_status ?? "unknown" };
}

export async function listActivePlaybooks(api: APIRequestContext): Promise<PlaybookRaw[]> {
  const res = await api.get(`${API_PREFIX}/playbooks`);
  await expectOk(res, "GET /playbooks");
  const all = (await res.json()) as PlaybookRaw[];
  return all.filter((p) => p.is_active);
}

/** Hard assertion that no React error boundary fallback is rendered anywhere on the page. */
export async function expectNoErrorBoundary(page: Page): Promise<void> {
  for (const text of ERROR_BOUNDARY_TEXTS) {
    await expect(page.getByText(text)).toHaveCount(0);
  }
}

interface Fixtures {
  /** Request context against the backend (E2E_API_URL), independent of the frontend baseURL. */
  api: APIRequestContext;
  /** A case created via API before the test and deleted afterwards. */
  seededCase: SeededCase;
  /**
   * Auto fixture: a rate-limited API response (HTTP 429, e.g. /auth/config at 30/min)
   * silently degrades the SPA to a read-only view, which would otherwise surface as an
   * unrelated locator timeout. Fail with the real cause instead.
   */
  failOnRateLimit: void;
}

export const test = base.extend<Fixtures>({
  api: async ({ playwright }, use) => {
    const ctx = await playwright.request.newContext({ baseURL: API_URL });
    await use(ctx);
    await ctx.dispose();
  },
  failOnRateLimit: [
    async ({ page }, use) => {
      const rateLimited: string[] = [];
      page.on("response", (res) => {
        if (res.status() === 429) rateLimited.push(`${res.request().method()} ${res.url()}`);
      });
      await use();
      if (rateLimited.length > 0) {
        throw new Error(
          `Backend rate limit hit during the test (the SPA then hides edit actions): ${rateLimited.join(", ")}. ` +
            "Wait a minute before re-running the suite.",
        );
      }
    },
    { auto: true },
  ],
  seededCase: async ({ api }, use, testInfo) => {
    const label = testInfo.title.replace(/@\w+/g, "").trim().slice(0, 40);
    const seeded = await createCase(api, { title: uniqueTitle(label) });
    await use(seeded);
    await deleteCase(api, seeded.id);
  },
});

export { expect };
