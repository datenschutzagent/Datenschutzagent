import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("../lib/api", () => ({
  listDataBreaches: vi.fn(),
  createDataBreach: vi.fn(),
  updateDataBreach: vi.fn(),
  deleteDataBreach: vi.fn(),
  generateBreachNotification: vi.fn(),
  getDataBreachActivity: vi.fn(),
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

import { listDataBreaches } from "../lib/api";
import { DataBreachesPage } from "./data-breaches-page";

const mockList = vi.mocked(listDataBreaches);

const makeFakeBreach = (overrides: Record<string, unknown> = {}) => ({
  id: "breach-1",
  title: "Test-Datenpanne",
  description: "E-Mail an falschen Empfänger",
  discoveredAt: "2026-04-14T10:00:00Z",
  notificationDeadline: "2026-04-17T10:00:00Z",
  breachType: "confidentiality",
  affectedDataCategories: ["name", "email"],
  affectedPersonsCount: 50,
  department: "HR",
  assignee: "DSB Team",
  status: "discovered",
  riskLevel: "medium",
  authorityNotifiedAt: null,
  subjectsNotifiedAt: null,
  authorityReference: null,
  measuresTaken: null,
  draftNotification: null,
  createdAt: "2026-04-14T10:00:00Z",
  updatedAt: "2026-04-14T10:00:00Z",
  ...overrides,
});

function renderPage() {
  return render(
    <MemoryRouter>
      <DataBreachesPage />
    </MemoryRouter>
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("DataBreachesPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows a loading skeleton while breaches are being fetched", () => {
    mockList.mockReturnValue(new Promise(() => {}));
    renderPage();
    const skeletons = document.querySelectorAll("[data-slot='skeleton']");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("renders breach titles after loading", async () => {
    mockList.mockResolvedValue({
      items: [
        makeFakeBreach({ title: "Datenpanne Alpha" }),
        makeFakeBreach({ id: "breach-2", title: "Datenpanne Beta" }),
      ],
      total: 2,
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Datenpanne Alpha")).toBeTruthy();
      expect(screen.getByText("Datenpanne Beta")).toBeTruthy();
    });
  });

  it("shows empty state when no breaches exist", async () => {
    mockList.mockResolvedValue({ items: [], total: 0 });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/Keine Datenpannen/)).toBeTruthy();
    });
  });

  it("calls listDataBreaches on mount", async () => {
    mockList.mockResolvedValue({ items: [], total: 0 });
    renderPage();
    await waitFor(() => {
      expect(mockList).toHaveBeenCalledTimes(1);
    });
  });

  it("renders risk level badge", async () => {
    mockList.mockResolvedValue({
      items: [makeFakeBreach({ riskLevel: "high" })],
      total: 1,
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Hoch")).toBeTruthy();
    });
  });
});
