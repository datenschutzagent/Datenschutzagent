import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";

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

import { listDSRRequests } from "../lib/api";
import { DSRPage } from "./dsr-page";

const mockList = vi.mocked(listDSRRequests);

const makeFakeDSR = (overrides: Record<string, unknown> = {}) => ({
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
  ...overrides,
});

function renderPage() {
  return render(
    <MemoryRouter>
      <DSRPage />
    </MemoryRouter>
  );
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
});
