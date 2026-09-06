import { test, expect, expectNoErrorBoundary, deleteCase, uniqueTitle } from "./fixtures";

/**
 * E2E: cases list and the "Neuer Vorgang" wizard.
 *
 * Every test works on its own case seeded via API (see fixtures.ts) and makes hard
 * assertions against it; nothing here depends on pre-existing data in the stack.
 */
test.describe("Cases", () => {
  test("landing page loads and lists the seeded case @smoke", async ({ page, seededCase }) => {
    await page.goto("/");
    await expect(page).toHaveTitle(/DatenschutzAgent/);
    await expect(page.getByRole("heading", { name: "Vorgänge" })).toBeVisible();

    const card = page.getByTestId("case-card").filter({ has: page.getByText(seededCase.title) });
    await expect(card).toHaveCount(1);
    await expect(card).toHaveAttribute("data-case-id", seededCase.id);
    await expect(card).toContainText(seededCase.department);
    await expect(card).toContainText("0 Dokumente");
    await expectNoErrorBoundary(page);
  });

  test("new case wizard requires title and department before 'Weiter' @smoke", async ({ page }) => {
    await page.goto("/");
    await page.getByTestId("new-case-button").click();

    const dialog = page.getByTestId("new-case-dialog");
    await expect(dialog).toBeVisible();
    await expect(dialog).toHaveAttribute("data-step", "1");
    const next = dialog.getByTestId("new-case-next");
    await expect(next).toBeDisabled();

    // Title alone is not enough: the department is required as well.
    await dialog.getByLabel(/Titel des Vorgangs/).fill(uniqueTitle("Wizard"));
    await expect(next).toBeDisabled();

    await dialog.locator("#department").click();
    const firstDepartment = page.getByRole("option").first();
    await expect(firstDepartment).toBeVisible();
    await firstDepartment.click();
    await expect(next).toBeEnabled();

    await next.click();
    await expect(dialog).toHaveAttribute("data-step", "2");
    await expect(dialog.getByText("Case-Typ / Playbook auswählen")).toBeVisible();

    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden();
  });

  test("search filters the list down to the seeded case @smoke", async ({ page, seededCase }) => {
    await page.goto("/");
    const cards = page.getByTestId("case-card");
    await expect(cards.filter({ has: page.getByText(seededCase.title) })).toHaveCount(1);

    const search = page.getByTestId("cases-search-input");
    await search.fill(seededCase.title);
    await expect(cards).toHaveCount(1);
    await expect(cards.first()).toHaveAttribute("data-case-id", seededCase.id);

    await search.fill("nonexistent-case-xyz-12345");
    await expect(page.getByTestId("cases-empty-state")).toBeVisible();
    await expect(page.getByText("Keine Vorgänge gefunden")).toBeVisible();
    await expect(cards).toHaveCount(0);

    await search.fill("");
    await expect(cards.filter({ has: page.getByText(seededCase.title) })).toHaveCount(1);
  });

  test("wizard creates a case and navigates to its detail page", async ({ page, api }) => {
    const title = uniqueTitle("Wizard-Anlage");
    let createdId: string | null = null;
    try {
      await page.goto("/");
      await page.getByTestId("new-case-button").click();
      const dialog = page.getByTestId("new-case-dialog");
      await dialog.getByLabel(/Titel des Vorgangs/).fill(title);
      await dialog.locator("#department").click();
      await page.getByRole("option").first().click();
      await dialog.getByTestId("new-case-next").click();

      // Step 2: at least one active playbook must be offered; pick the first one.
      await expect(dialog).toHaveAttribute("data-step", "2");
      const options = dialog.locator("[data-testid^='playbook-option-']");
      await expect(options.first()).toBeVisible();
      await options.first().click();
      await expect(options.first()).toHaveAttribute("data-selected", "true");

      await dialog.getByTestId("new-case-submit-without-documents").click();
      await expect(page).toHaveURL(/\/cases\/[0-9a-f-]{36}$/);
      createdId = page.url().split("/cases/")[1] ?? null;
      await expect(page.getByRole("heading", { name: title })).toBeVisible();
      await expect(page.getByTestId("case-tab-documents")).toContainText("Dokumente (0)");
      await expectNoErrorBoundary(page);
    } finally {
      if (createdId) await deleteCase(api, createdId);
    }
  });
});
