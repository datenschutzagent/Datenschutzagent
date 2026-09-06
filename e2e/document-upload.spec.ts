import fs from "node:fs";
import { test, expect, expectNoErrorBoundary, csvDocument, uploadDocument } from "./fixtures";

/**
 * E2E: document upload and extraction status on the case detail page.
 *
 * The stack under test extracts CSV text synchronously when Celery is disabled
 * (CI) and asynchronously otherwise; both paths are accepted, "failed" is not.
 */
test.describe("Document Upload", () => {
  test("upload via file input shows the file name and an extraction status @smoke", async ({
    page,
    seededCase,
  }, testInfo) => {
    const doc = csvDocument("E2E-UI-Upload");
    const tmpFile = testInfo.outputPath(doc.name);
    fs.writeFileSync(tmpFile, doc.buffer);

    await page.goto(`/cases/${seededCase.id}?tab=documents`);
    await expect(page.getByRole("heading", { name: seededCase.title })).toBeVisible();
    await expect(page.getByTestId("case-tab-documents")).toContainText("Dokumente (0)");

    await page.getByTestId("document-upload-button").click();
    const dialog = page.getByTestId("document-upload-dialog");
    await expect(dialog).toBeVisible();
    await dialog.getByTestId("document-upload-input").setInputFiles(tmpFile);

    const item = dialog.getByTestId("document-upload-item");
    await expect(item).toHaveCount(1);
    await expect(item).toContainText(doc.name);
    await expect(item).toHaveAttribute("data-status", "success");

    // The submit button stays disabled until a document type is assigned.
    const submit = dialog.getByTestId("document-upload-submit");
    await expect(submit).toBeDisabled();
    await item.getByTestId("document-type-select").click();
    await page.getByRole("option", { name: "Sonstiges" }).click();
    await expect(submit).toBeEnabled();
    await submit.click();
    await expect(dialog).toBeHidden();

    const row = page.getByTestId("document-row").filter({ hasText: doc.name });
    await expect(row).toHaveCount(1);
    await expect(row).toContainText("Sonstiges");
    await expect(row).toContainText("v1");
    await expect(row).toHaveAttribute("data-extraction-status", /^(pending|processing|done)$/);
    await expect(row.getByText("Extraktion fehlgeschlagen")).toHaveCount(0);
    await expect(page.getByTestId("case-tab-documents")).toContainText("Dokumente (1)");
    await expectNoErrorBoundary(page);
  });

  test("API-seeded document is listed and its extracted text is viewable", async ({
    page,
    api,
    seededCase,
  }) => {
    const marker = `E2E-Marker-${Date.now()}`;
    const seededDoc = await uploadDocument(api, seededCase.id, csvDocument(marker), "vvt");
    expect(seededDoc.extractionStatus).not.toBe("failed");

    await page.goto(`/cases/${seededCase.id}?tab=documents`);
    const row = page.getByTestId("document-row").filter({ hasText: seededDoc.name });
    await expect(row).toHaveCount(1);
    await expect(row).toHaveAttribute("data-document-id", seededDoc.id);
    await expect(row).toContainText("VVT / ROPA");

    await row.getByTestId("document-view-button").click();
    const viewDialog = page.getByRole("dialog");
    await expect(viewDialog).toBeVisible();
    // Extraction may still be pending on stacks with Celery; the dialog polls until done.
    await expect(viewDialog.getByText(marker)).toBeVisible({ timeout: 20_000 });
    await expect(viewDialog.getByText("Kein Text extrahiert.")).toHaveCount(0);
    await expectNoErrorBoundary(page);
  });

  test("unsupported file formats are rejected before upload", async ({ page, seededCase }, testInfo) => {
    const tmpFile = testInfo.outputPath("notizen.txt");
    fs.writeFileSync(tmpFile, "Kein unterstütztes Format");

    await page.goto(`/cases/${seededCase.id}?tab=documents`);
    await page.getByTestId("document-upload-button").click();
    const dialog = page.getByTestId("document-upload-dialog");
    await dialog.getByTestId("document-upload-input").setInputFiles(tmpFile);

    const item = dialog.getByTestId("document-upload-item");
    await expect(item).toHaveAttribute("data-status", "error");
    await expect(item).toContainText("Nicht unterstütztes Format");
    await expect(dialog.getByTestId("document-upload-submit")).toBeDisabled();

    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden();
    await expect(page.getByTestId("case-tab-documents")).toContainText("Dokumente (0)");
  });
});
