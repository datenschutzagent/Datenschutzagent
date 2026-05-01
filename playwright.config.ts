import { defineConfig, devices } from "@playwright/test";

/**
 * E2E test configuration.
 *
 * Prerequisites:
 *   - Frontend dev server:  npm run dev   (http://localhost:3002)
 *   - Backend API server:   uvicorn ...   (http://localhost:8002)
 *
 * Run all tests:       npx playwright test
 * Run with UI:         npx playwright test --ui
 * Run single file:     npx playwright test e2e/cases.spec.ts
 * Show report:         npx playwright show-report
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: process.env.CI ? "github" : "html",
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
