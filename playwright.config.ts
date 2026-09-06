import { defineConfig, devices } from "@playwright/test";

/**
 * E2E test configuration.
 *
 * Prerequisites:
 *   - Frontend dev server:  npm run dev   (http://localhost:3002)
 *   - Backend API server:   uvicorn ...   (http://localhost:8002) with OIDC disabled
 *     and RBAC_DEFAULT_ROLE=admin, so the tests can seed data via the REST API.
 *
 * Environment:
 *   E2E_BASE_URL   frontend URL used for page navigation (default http://localhost:3002)
 *   E2E_API_URL    backend URL used by e2e/fixtures.ts to seed and clean up test data
 *                  via the REST API (default http://localhost:8002)
 *   CI             enables retries, the GitHub + HTML reporters and disables the dev server
 *
 * Run all tests:       npx playwright test
 * Smoke set only:      npx playwright test --grep @smoke
 * Run with UI:         npx playwright test --ui
 * Run single file:     npx playwright test e2e/cases.spec.ts
 * Show report:         npx playwright show-report
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "html",
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3002",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "off",
    // OIDC is typically disabled in E2E test environments (DEV mode)
    ignoreHTTPSErrors: true,
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  // Automatically start the dev server when running locally
  webServer: process.env.CI
    ? undefined
    : {
        command: "npm run dev",
        url: "http://localhost:3002",
        reuseExistingServer: true,
        timeout: 30_000,
      },
  timeout: 30_000,
  expect: { timeout: 10_000 },
});
