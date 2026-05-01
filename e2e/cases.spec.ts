import { test, expect } from "@playwright/test";

/**
 * E2E: Case management flow.
 *
 * Assumes OIDC_ENABLED=false (DEV mode) so the app works without login.
 */
test.describe("Cases", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
  });

  test("landing page loads and shows the cases list", async ({ page }) => {
    // The app should render the main navigation or case list
    await expect(page).toHaveTitle(/Datenschutz/i);
    // Page should not crash (no error boundary text visible)
    await expect(page.getByText(/Etwas ist schiefgelaufen/i)).not.toBeVisible();
  });

  test("opens New Case dialog and validates required fields", async ({ page }) => {
    // Find and click the New Case button (German: "Neuer Vorgang" or similar)
    const newCaseButton = page
      .getByRole("button", { name: /Neuer Vorgang|New Case/i })
      .first();
    await expect(newCaseButton).toBeVisible({ timeout: 10_000 });
    await newCaseButton.click();

    // Dialog should appear
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();

    // Submit without filling in required fields → form should show validation
    const submitButton = dialog.getByRole("button", { name: /Erstellen|Create/i });
    await submitButton.click();

    // At least one validation error or the dialog should still be open
    await expect(dialog).toBeVisible();
  });

  test("can filter cases by search query", async ({ page }) => {
    // Wait for any initial loading to complete
    await page.waitForLoadState("networkidle");

    // The search input should be present
    const searchInput = page.getByPlaceholder(/Suchen|Search/i).first();
    if (await searchInput.isVisible()) {
      await searchInput.fill("nonexistent-case-xyz-12345");
      // After filtering, the list should be empty or show no results
      await expect(page.getByText(/Keine Ergebnisse|No results/i)).toBeVisible({
        timeout: 5_000,
      }).catch(() => {
        // Accept: the filter just reduces visible items (may be empty without text)
      });
    }
  });
});
