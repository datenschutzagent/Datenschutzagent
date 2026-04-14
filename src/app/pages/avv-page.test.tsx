import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("../lib/api", () => ({
  listAVVContracts: vi.fn(),
  createAVVContract: vi.fn(),
  updateAVVContract: vi.fn(),
  deleteAVVContract: vi.fn(),
  assessAvvRisk: vi.fn(),
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

import { listAVVContracts } from "../lib/api";
import { AVVPage } from "./avv-page";

const mockList = vi.mocked(listAVVContracts);

const makeFakeAVV = (overrides: Record<string, unknown> = {}) => ({
  id: "avv-1",
  partnerName: "Cloud Corp GmbH",
  partnerType: "processor",
  subjectMatter: "Cloud-Hosting",
  department: "IT",
  status: "signed",
  contractDate: "2026-01-01",
  expiryDate: "2027-01-01",
  assignee: "DSB Team",
  documentName: null,
  notes: null,
  checkResult: null,
  createdAt: "2026-01-01T10:00:00Z",
  updatedAt: "2026-01-01T10:00:00Z",
  ...overrides,
});

function renderPage() {
  return render(
    <MemoryRouter>
      <AVVPage />
    </MemoryRouter>
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("AVVPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows a loading skeleton while contracts are being fetched", () => {
    mockList.mockReturnValue(new Promise(() => {}));
    renderPage();
    const skeletons = document.querySelectorAll("[data-slot='skeleton']");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("renders partner names after loading", async () => {
    mockList.mockResolvedValue({
      items: [
        makeFakeAVV({ partnerName: "Firma Alpha" }),
        makeFakeAVV({ id: "avv-2", partnerName: "Firma Beta" }),
      ],
      total: 2,
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Firma Alpha")).toBeTruthy();
      expect(screen.getByText("Firma Beta")).toBeTruthy();
    });
  });

  it("shows empty state when no contracts exist", async () => {
    mockList.mockResolvedValue({ items: [], total: 0 });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/Keine AVV/)).toBeTruthy();
    });
  });

  it("calls listAVVContracts on mount", async () => {
    mockList.mockResolvedValue({ items: [], total: 0 });
    renderPage();
    await waitFor(() => {
      expect(mockList).toHaveBeenCalledTimes(1);
    });
  });

  it("renders status badge for signed contracts", async () => {
    mockList.mockResolvedValue({
      items: [makeFakeAVV({ status: "signed" })],
      total: 1,
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Unterzeichnet")).toBeTruthy();
    });
  });
});
