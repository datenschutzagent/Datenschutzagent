import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../test-utils";
import type { ApiDSRRequest } from "../lib/api";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("../lib/api", () => ({
  listDSRRequests: vi.fn(),
  createDSRRequest: vi.fn(),
  updateDSRRequest: vi.fn(),
  deleteDSRRequest: vi.fn(),
  generateDSRDraft: vi.fn(),
  getDSRActivity: vi.fn(),
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

import { listDSRRequests, updateDSRRequest, getDSRActivity } from "../lib/api";
import { toast } from "sonner";
import { DSRPage } from "./dsr-page";

const mockList = vi.mocked(listDSRRequests);
const mockUpdate = vi.mocked(updateDSRRequest);
const mockActivity = vi.mocked(getDSRActivity);

const baseDSR: ApiDSRRequest = {
  id: "dsr-1",
  requestType: "access",
  requestorName: "Max Mustermann",
  requestorEmail: "max@example.com",
  description: "Auskunft über gespeicherte Daten",
  department: "IT",
  status: "received",
  assignee: "DSB Team",
  receivedAt: "2026-04-14",
  responseDeadline: "2026-05-14",
  respondedAt: null,
  responseSummary: null,
  draftResponse: null,
  createdAt: "2026-04-14T10:00:00Z",
  updatedAt: "2026-04-14T10:00:00Z",
};

const makeFakeDSR = (overrides: Partial<ApiDSRRequest> = {}): ApiDSRRequest => ({
  ...baseDSR,
  ...overrides,
});

function renderPage() {
  return renderWithProviders(<DSRPage />);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("DSRPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows a loading skeleton while requests are being fetched", () => {
    mockList.mockReturnValue(new Promise(() => {}));
    renderPage();
    const skeletons = document.querySelectorAll("[data-slot='skeleton']");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("renders DSR request names after loading", async () => {
    mockList.mockResolvedValue({
      items: [
        makeFakeDSR({ requestorName: "Erika Musterfrau" }),
        makeFakeDSR({ id: "dsr-2", requestorName: "Hans Schmidt" }),
      ],
      total: 2,
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Erika Musterfrau")).toBeTruthy();
      expect(screen.getByText("Hans Schmidt")).toBeTruthy();
    });
  });

  it("shows empty state when no requests exist", async () => {
    mockList.mockResolvedValue({ items: [], total: 0 });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/Keine Betroffenenrechts-Anfragen/)).toBeTruthy();
    });
  });

  it("calls listDSRRequests on mount", async () => {
    mockList.mockResolvedValue({ items: [], total: 0 });
    renderPage();
    await waitFor(() => {
      expect(mockList).toHaveBeenCalledTimes(1);
    });
  });

  it("renders request type badge", async () => {
    mockList.mockResolvedValue({
      items: [makeFakeDSR({ requestType: "erasure" })],
      total: 1,
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Löschung (Art. 17)")).toBeTruthy();
    });
  });

  it("shows anonymous label when requestorName is null", async () => {
    mockList.mockResolvedValue({
      items: [makeFakeDSR({ requestorName: null })],
      total: 1,
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Anonyme Anfrage")).toBeTruthy();
    });
  });

  it("shows an error state with retry when the list query fails", async () => {
    mockList.mockRejectedValueOnce(new Error("Netzwerkfehler"));
    mockList.mockResolvedValueOnce({ items: [makeFakeDSR()], total: 1 });
    renderPage();

    await screen.findByText("Anfragen konnten nicht geladen werden.");
    expect(toast.error).toHaveBeenCalledWith(
      "Anfragen konnten nicht geladen werden.",
      expect.objectContaining({ description: "Netzwerkfehler" }),
    );

    await userEvent.click(screen.getByRole("button", { name: "Erneut versuchen" }));
    await screen.findByText("Max Mustermann");
    expect(mockList).toHaveBeenCalledTimes(2);
  });

  it("loads the activity log and updates the status from the detail dialog", async () => {
    mockList.mockResolvedValue({ items: [makeFakeDSR()], total: 1 });
    mockActivity.mockResolvedValue([
      { id: "act-1", requestId: "dsr-1", eventType: "created", payload: {}, createdAt: "2026-04-14T10:00:00Z" },
    ]);
    mockUpdate.mockResolvedValue(makeFakeDSR({ status: "in_progress" }));
    renderPage();

    await userEvent.click(await screen.findByText("Max Mustermann"));
    await screen.findByText("created");
    expect(mockActivity).toHaveBeenCalledWith("dsr-1");

    await userEvent.click(screen.getByRole("button", { name: "In Bearbeitung" }));
    await waitFor(() => {
      expect(mockUpdate).toHaveBeenCalledWith("dsr-1", { status: "in_progress" });
    });
    expect(toast.success).toHaveBeenCalledWith("Status aktualisiert.");
    // Mutation invalidates the list and the activity log
    await waitFor(() => {
      expect(mockList).toHaveBeenCalledTimes(2);
      expect(mockActivity).toHaveBeenCalledTimes(2);
    });
  });
});
