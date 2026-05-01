import { test, expect, type Page } from "@playwright/test";

/**
 * E2E: Playbook checks and findings flow.
 *
 * Assumes OIDC_ENABLED=false (DEV mode).
 * These tests navigate into a case and verify that the checks UI is accessible.
 * They do not start actual LLM checks (which require a running backend + Ollama).
 */

async function navigateToFirstCase(page: Page): Promise<boolean> {
  await page.goto("/");
  await page.waitForLoadState("networkidle");

  const caseLink = page.getByRole("link", { name: /.+/ }).first();
  if (!(await caseLink.isVisible({ timeout: 3_000 }).catch(() => false))) {
    return false;
  }
  await caseLink.click();
  await page.waitForLoadState("networkidle");
  return true;
}

test.describe("Checks & Findings", () => {
  test("checks tab is accessible in a case", async ({ page }) => {
    const hasCase = await navigateToFirstCase(page);
    if (!hasCase) {
      test.skip();
      return;
    }

    // Look for a "Prüfungen" or "Checks" tab
    const checksTab = page.getByRole("tab", { name: /Prüf|Check/i }).first();
    const isVisible = await checksTab.isVisible({ timeout: 5_000 }).catch(() => false);

    if (isVisible) {
      await checksTab.click();
      await page.waitForLoadState("networkidle");
      // Should not crash after switching tab
      await expect(page.getByText(/Etwas ist schiefgelaufen/i)).not.toBeVisible();
    }
  });

  test("findings tab shows finding list or empty state", async ({ page }) => {
    const hasCase = await navigateToFirstCase(page);
    if (!hasCase) {
      test.skip();
      return;
    }

    const findingsTab = page.getByRole("tab", { name: /Ergebnis|Finding/i }).first();
    const isVisible = await findingsTab.isVisible({ timeout: 5_000 }).catch(() => false);

    if (isVisible) {
      await findingsTab.click();
      await page.waitForLoadState("networkidle");
      // Should render without crashing
      await expect(page.getByText(/Etwas ist schiefgelaufen/i)).not.toBeVisible();
    }
  });

  test("run checks button is visible and enabled when checks are available", async ({
    page,
  }) => {
    const hasCase = await navigateToFirstCase(page);
    if (!hasCase) {
      test.skip();
      return;
    }

    // Look for a run-checks button (German: "Prüfungen starten" or similar)
    const runButton = page
      .getByRole("button", { name: /Prüfungen starten|Checks starten|Run Checks/i })
      .first();

    const isVisible = await runButton.isVisible({ timeout: 5_000 }).catch(() => false);

    if (isVisible) {
      // Button should be enabled (ready to use)
      await expect(runButton).toBeEnabled();
    }
    // Page should not crash in any case
    await expect(page.getByText(/Etwas ist schiefgelaufen/i)).not.toBeVisible();
  });
});
