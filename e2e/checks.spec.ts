import { test, expect, expectNoErrorBoundary, listActivePlaybooks, csvDocument, uploadDocument } from "./fixtures";

/**
 * E2E: case detail page, tab navigation and the run-checks dialog.
 *
 * Checks are never actually started here: they need an LLM provider, which the
 * CI stack does not have. The tests assert that the UI is wired correctly up to
 * the point of submission and that no run-checks request leaves the browser.
 */
test.describe("Checks & Findings", () => {
  test("detail page opens and the main tabs render without an error boundary @smoke", async ({
    page,
    seededCase,
  }) => {
    await page.goto(`/cases/${seededCase.id}`);
    await expect(page.getByRole("heading", { name: seededCase.title })).toBeVisible();
    await expect(page.getByText(seededCase.department)).toBeVisible();
    await expect(page.getByText(seededCase.caseType)).toBeVisible();

    const overview = page.getByTestId("case-tab-overview");
    await expect(overview).toHaveAttribute("data-state", "active");
    await expect(page.getByRole("heading", { name: "Aktionen" })).toBeVisible();

    await page.getByTestId("case-tab-documents").click();
    await expect(page.getByTestId("case-tab-documents")).toHaveAttribute("data-state", "active");
    await expect(page.getByRole("heading", { name: "Dokumente", exact: true })).toBeVisible();
    await expect(page.getByTestId("document-upload-button")).toBeVisible();
    await expectNoErrorBoundary(page);

    await page.getByTestId("case-tab-findings").click();
    await expect(page.getByTestId("case-tab-findings")).toHaveAttribute("data-state", "active");
    await expect(page.getByText("Keine Findings für die gewählten Filter.")).toBeVisible();
    await expectNoErrorBoundary(page);

    await page.getByTestId("case-tab-audit").click();
    await expect(page.getByRole("heading", { name: "Audit Trail" })).toBeVisible();
    await expectNoErrorBoundary(page);
  });

  test("run-checks dialog enables 'Checks starten' once a playbook is selected @smoke", async ({
    page,
    api,
    seededCase,
  }) => {
    const activePlaybooks = await listActivePlaybooks(api);
    expect(activePlaybooks.length, "YAML-seeded playbooks must be present").toBeGreaterThan(0);

    const runChecksRequests: string[] = [];
    page.on("request", (req) => {
      if (req.method() === "POST" && req.url().includes("/run-checks")) runChecksRequests.push(req.url());
    });

    await page.goto(`/cases/${seededCase.id}`);
    await page.getByTestId("run-checks-button").click();
    const dialog = page.getByTestId("run-checks-dialog");
    await expect(dialog).toBeVisible();

    const submit = dialog.getByTestId("run-checks-submit");
    await expect(submit).toBeDisabled();

    const select = dialog.locator("#run-checks-playbook");
    // Option 0 is the placeholder; at least one real playbook must be offered.
    await expect(select.locator("option")).not.toHaveCount(1);
    const firstPlaybook = await select.locator("option").nth(1).getAttribute("value");
    expect(firstPlaybook).toBeTruthy();
    await select.selectOption(firstPlaybook as string);
    await expect(select).toHaveValue(firstPlaybook as string);
    await expect(submit).toBeEnabled();

    await dialog.getByRole("button", { name: "Abbrechen" }).click();
    await expect(dialog).toBeHidden();
    expect(runChecksRequests, "no run-checks request may be sent").toEqual([]);
    await expectNoErrorBoundary(page);
  });

  test("findings tab reports no findings and no stale warning for a fresh case", async ({
    page,
    api,
    seededCase,
  }) => {
    await uploadDocument(api, seededCase.id, csvDocument("E2E-Findings"), "vvt");

    await page.goto(`/cases/${seededCase.id}?tab=findings`);
    await expect(page.getByTestId("case-tab-findings")).toHaveAttribute("data-state", "active");
    await expect(page.getByTestId("case-tab-findings")).toContainText("Findings (0)");
    await expect(page.getByText("Keine Findings für die gewählten Filter.")).toBeVisible();
    // No run has happened yet, so the "documents changed since last run" hint must not appear.
    await expect(page.getByText("Dokumente wurden seit der letzten Prüfung aktualisiert")).toHaveCount(0);
    await expectNoErrorBoundary(page);
  });

  test("overview statistics reflect the seeded documents", async ({ page, api, seededCase }) => {
    await uploadDocument(api, seededCase.id, csvDocument("E2E-Stat-1"), "vvt");
    await uploadDocument(api, seededCase.id, csvDocument("E2E-Stat-2"), "other");

    await page.goto(`/cases/${seededCase.id}`);
    await expect(page.getByTestId("case-tab-documents")).toContainText("Dokumente (2)");
    const statistik = page.locator("[data-slot='card']").filter({ hasText: "Statistik" });
    await expect(statistik).toHaveCount(1);
    await expect(statistik.locator("div").filter({ hasText: /^Dokumente/ }).first()).toContainText("2");
    await expect(statistik.locator("div").filter({ hasText: /^Findings gesamt/ }).first()).toContainText("0");
    await expectNoErrorBoundary(page);
  });
});
