import { describe, it, expect, vi, beforeEach, beforeAll } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../test-utils";
import type { ApiTOM, ApiTOMStats, ApiTOMAttachment } from "../lib/api";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("../lib/api", () => ({
  listTOMs: vi.fn(),
  getTOMStats: vi.fn(),
  createTOM: vi.fn(),
  updateTOM: vi.fn(),
  deleteTOM: vi.fn(),
  listTOMAttachments: vi.fn(),
  uploadTOMAttachment: vi.fn(),
  getTOMAttachmentBlob: vi.fn(),
  deleteTOMAttachment: vi.fn(),
  downloadBlob: vi.fn(),
  getCurrentUser: vi.fn(),
  canEdit: vi.fn(() => true),
  isAdmin: vi.fn(() => false),
}));

vi.mock("../contexts/AuthContext", () => ({
  useAuthOptional: vi.fn(() => ({ user: null })),
}));

vi.mock("../contexts/AppConfigContext", () => ({
  useAppConfig: vi.fn(() => ({
    app_name: "Datenschutzagent",
    org_name: "Testorg",
    org_profile: "default",
    processing_context_options: [],
  })),
}));

vi.mock("../contexts/RunningChecksContext", () => ({
  useRunningChecks: vi.fn(() => ({
    jobs: [],
    registerJob: vi.fn(),
    isRunning: vi.fn(() => false),
    getJob: vi.fn(),
    dismissJob: vi.fn(),
    runningCount: 0,
  })),
}));

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

// Baseline card fetches its own endpoint and is not under test here.
vi.mock("../components/tom-baseline-gaps", () => ({
  TomBaselineGaps: () => null,
}));

import {
  listTOMs,
  getTOMStats,
  createTOM,
  updateTOM,
  deleteTOM,
  listTOMAttachments,
  getCurrentUser,
} from "../lib/api";
import { toast } from "sonner";
import { TOMPage } from "./tom-page";

const mockList = vi.mocked(listTOMs);
const mockStats = vi.mocked(getTOMStats);
const mockCreate = vi.mocked(createTOM);
const mockUpdate = vi.mocked(updateTOM);
const mockDelete = vi.mocked(deleteTOM);
const mockAttachments = vi.mocked(listTOMAttachments);
const mockCurrentUser = vi.mocked(getCurrentUser);

const baseTOM: ApiTOM = {
  id: "tom-1",
  title: "Zwei-Faktor-Authentifizierung",
  description: "MFA für alle Admin-Zugänge",
  category: "access_control",
  implementationStatus: "planned",
  responsible: "IT-Sicherheit",
  reviewDate: null,
  evidence: null,
  departmentCodes: [],
  createdAt: "2026-04-14T10:00:00Z",
  updatedAt: "2026-04-14T10:00:00Z",
};

const makeFakeTOM = (overrides: Partial<ApiTOM> = {}): ApiTOM => ({ ...baseTOM, ...overrides });

const fakeStats: ApiTOMStats = {
  total: 4,
  byStatus: { planned: 1, in_progress: 0, implemented: 3, not_applicable: 0 },
  byCategory: { access_control: 4 },
  implementationRate: 75,
};

const fakeAttachment: ApiTOMAttachment = {
  id: "att-1",
  tomId: "tom-1",
  name: "Richtlinie.pdf",
  format: "pdf",
  sizeBytes: 2048,
  size: "2.0 KB",
  uploadedBy: "Test User",
  uploadedAt: "2026-04-14T10:00:00Z",
};

function renderPage() {
  return renderWithProviders(<TOMPage />);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("TOMPage", () => {
  beforeAll(() => {
    // jsdom lacks the pointer-capture API that Radix Select relies on.
    Element.prototype.hasPointerCapture =
      Element.prototype.hasPointerCapture ?? (() => false);
    Element.prototype.setPointerCapture =
      Element.prototype.setPointerCapture ?? (() => undefined);
    Element.prototype.releasePointerCapture =
      Element.prototype.releasePointerCapture ?? (() => undefined);
    Element.prototype.scrollIntoView = Element.prototype.scrollIntoView ?? (() => undefined);
  });

  beforeEach(() => {
    vi.clearAllMocks();
    mockStats.mockResolvedValue(fakeStats);
    mockAttachments.mockResolvedValue([]);
    mockCurrentUser.mockResolvedValue({
      id: "u1",
      display_name: "Test User",
      role: "editor",
    } as never);
  });

  it("shows a loading skeleton while TOMs are being fetched", () => {
    mockList.mockReturnValue(new Promise(() => {}));
    mockStats.mockReturnValue(new Promise(() => {}));
    renderPage();
    const skeletons = document.querySelectorAll("[data-slot='skeleton']");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("renders TOMs grouped by category after loading", async () => {
    mockList.mockResolvedValue({
      items: [
        makeFakeTOM(),
        makeFakeTOM({ id: "tom-2", title: "Festplattenverschlüsselung", category: "encryption" }),
      ],
      total: 2,
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Zwei-Faktor-Authentifizierung")).toBeTruthy();
      expect(screen.getByText("Festplattenverschlüsselung")).toBeTruthy();
    });
    expect(screen.getByText("Zugriffskontrolle (1)")).toBeTruthy();
    expect(screen.getByText("Verschlüsselung (1)")).toBeTruthy();
    expect(mockList).toHaveBeenCalledWith({ category: undefined, implementationStatus: undefined });
  });

  it("renders the implementation stats card", async () => {
    mockList.mockResolvedValue({ items: [], total: 0 });
    renderPage();
    await screen.findByText("Implementierungsstand");
    expect(screen.getByText("75%")).toBeTruthy();
    expect(mockStats).toHaveBeenCalledTimes(1);
  });

  it("shows empty state when no TOMs exist", async () => {
    mockList.mockResolvedValue({ items: [], total: 0 });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Keine TOMs gefunden.")).toBeTruthy();
    });
  });

  it("passes the status filter to the list query", async () => {
    mockList.mockResolvedValue({ items: [makeFakeTOM()], total: 1 });
    renderPage();
    await screen.findByText("Zwei-Faktor-Authentifizierung");

    const statusTrigger = screen.getAllByRole("combobox")[1];
    await userEvent.click(statusTrigger);
    await userEvent.click(await screen.findByRole("option", { name: "Umgesetzt" }));

    await waitFor(() => {
      expect(mockList).toHaveBeenCalledWith({ category: undefined, implementationStatus: "implemented" });
    });
  });

  it("shows an error state with retry when the list query fails", async () => {
    mockList.mockRejectedValueOnce(new Error("Netzwerkfehler"));
    mockList.mockResolvedValueOnce({ items: [makeFakeTOM()], total: 1 });
    renderPage();

    await screen.findByText("TOMs konnten nicht geladen werden.");
    expect(toast.error).toHaveBeenCalledWith(
      "TOMs konnten nicht geladen werden.",
      expect.objectContaining({ description: "Netzwerkfehler" }),
    );

    await userEvent.click(screen.getByRole("button", { name: "Erneut versuchen" }));
    await screen.findByText("Zwei-Faktor-Authentifizierung");
    expect(mockList).toHaveBeenCalledTimes(2);
  });

  it("shows an error state with retry when the stats query fails", async () => {
    mockList.mockResolvedValue({ items: [], total: 0 });
    mockStats.mockRejectedValueOnce(new Error("Stats kaputt"));
    mockStats.mockResolvedValueOnce(fakeStats);
    renderPage();

    await screen.findByText("Implementierungsstand konnte nicht geladen werden.");
    await userEvent.click(screen.getByRole("button", { name: "Erneut versuchen" }));
    await screen.findByText("75%");
    expect(mockStats).toHaveBeenCalledTimes(2);
  });

  it("creates a TOM through the dialog and reloads the list", async () => {
    mockList.mockResolvedValue({ items: [], total: 0 });
    mockCreate.mockResolvedValue(makeFakeTOM({ title: "Neue Maßnahme" }));
    renderPage();
    await screen.findByText("Keine TOMs gefunden.");

    await userEvent.click(screen.getByRole("button", { name: /TOM anlegen/ }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.type(within(dialog).getByLabelText("Titel *"), "Neue Maßnahme");
    await userEvent.type(within(dialog).getByLabelText("Zuständig"), "DSB");
    await userEvent.click(within(dialog).getByRole("button", { name: "Anlegen" }));

    await waitFor(() => {
      expect(mockCreate).toHaveBeenCalledWith({
        title: "Neue Maßnahme",
        description: undefined,
        category: "access_control",
        implementation_status: "planned",
        responsible: "DSB",
        review_date: undefined,
        evidence: undefined,
      });
    });
    expect(toast.success).toHaveBeenCalledWith("TOM angelegt.");
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).toBeNull();
      // list + stats invalidated after the mutation
      expect(mockList).toHaveBeenCalledTimes(2);
      expect(mockStats).toHaveBeenCalledTimes(2);
    });
  });

  it("rejects creating a TOM without a title", async () => {
    mockList.mockResolvedValue({ items: [], total: 0 });
    renderPage();
    await screen.findByText("Keine TOMs gefunden.");

    await userEvent.click(screen.getByRole("button", { name: /TOM anlegen/ }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Anlegen" }));

    expect(toast.error).toHaveBeenCalledWith("Titel erforderlich.");
    expect(mockCreate).not.toHaveBeenCalled();
  });

  it("changes the implementation status from the detail dialog", async () => {
    mockList.mockResolvedValue({ items: [makeFakeTOM()], total: 1 });
    mockUpdate.mockResolvedValue(makeFakeTOM({ implementationStatus: "implemented" }));
    renderPage();

    await userEvent.click(await screen.findByText("Zwei-Faktor-Authentifizierung"));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Umgesetzt" }));

    await waitFor(() => {
      expect(mockUpdate).toHaveBeenCalledWith("tom-1", { implementation_status: "implemented" });
    });
    expect(toast.success).toHaveBeenCalledWith("Status aktualisiert.");
    // Dialog reflects the updated status: "Umgesetzt" is no longer offered as a target
    await waitFor(() => {
      expect(within(dialog).queryByRole("button", { name: "Umgesetzt" })).toBeNull();
      expect(within(dialog).getByRole("button", { name: "Geplant" })).toBeTruthy();
    });
    await waitFor(() => expect(mockList).toHaveBeenCalledTimes(2));
  });

  it("loads attachments for the selected TOM", async () => {
    mockList.mockResolvedValue({ items: [makeFakeTOM()], total: 1 });
    mockAttachments.mockResolvedValue([fakeAttachment]);
    renderPage();

    await userEvent.click(await screen.findByText("Zwei-Faktor-Authentifizierung"));
    await screen.findByText("Richtlinie.pdf");
    expect(mockAttachments).toHaveBeenCalledWith("tom-1");
    expect(screen.getByText("2.0 KB")).toBeTruthy();
  });

  it("deletes a TOM after confirming and closes the detail dialog", async () => {
    mockList.mockResolvedValue({ items: [makeFakeTOM()], total: 1 });
    mockDelete.mockResolvedValue(undefined);
    renderPage();

    await userEvent.click(await screen.findByText("Zwei-Faktor-Authentifizierung"));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: /Löschen/ }));
    const confirm = await screen.findByRole("alertdialog");
    await userEvent.click(within(confirm).getByRole("button", { name: "Löschen" }));

    await waitFor(() => expect(mockDelete).toHaveBeenCalledWith("tom-1"));
    expect(toast.success).toHaveBeenCalledWith("TOM gelöscht.");
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });
});
