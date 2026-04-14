import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("../lib/api", () => ({
  getCases: vi.fn(),
  archiveCase: vi.fn(),
  unarchiveCase: vi.fn(),
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

import { getCases } from "../lib/api";
import { CasesPage } from "./cases-page";

const mockGetCases = vi.mocked(getCases);

const makeFakeCase = (overrides: Record<string, unknown> = {}) => ({
  id: "case-1",
  title: "Test-Vorgang",
  department: "IT",
  caseType: "vvt",
  status: "intake" as const,
  createdAt: "2024-01-01T00:00:00Z",
  updatedAt: "2024-01-01T00:00:00Z",
  createdBy: "user-1",
  assignee: "",
  language: "de",
  playbookVersion: "",
  specialCategoryData: false,
  internationalTransfer: false,
  autoRunChecks: false,
  documents: [],
  findings: [],
  ...overrides,
});

function renderPage() {
  return render(
    <MemoryRouter>
      <CasesPage />
    </MemoryRouter>
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("CasesPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows a loading skeleton while cases are being fetched", () => {
    // Never resolves — keeps component in loading state
    mockGetCases.mockReturnValue(new Promise(() => {}));
    renderPage();
    // Skeleton elements should be present (the component renders them during load)
    const skeletons = document.querySelectorAll("[data-slot='skeleton']");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("renders case titles after loading", async () => {
    mockGetCases.mockResolvedValue([
      makeFakeCase({ title: "Datenschutzfall Alpha" }),
      makeFakeCase({ id: "case-2", title: "Datenschutzfall Beta" }),
    ]);
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Datenschutzfall Alpha")).toBeTruthy();
      expect(screen.getByText("Datenschutzfall Beta")).toBeTruthy();
    });
  });

  it("shows an error message when getCases rejects", async () => {
    mockGetCases.mockRejectedValue(new Error("Netzwerkfehler"));
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/Netzwerkfehler/i)).toBeTruthy();
    });
  });

  it("shows empty state when no cases exist", async () => {
    mockGetCases.mockResolvedValue([]);
    renderPage();
    await waitFor(() => {
      // Should not show any case cards but page should be rendered
      expect(screen.queryByText("Datenschutzfall")).toBeNull();
    });
  });

  it("calls getCases on mount", async () => {
    mockGetCases.mockResolvedValue([]);
    renderPage();
    await waitFor(() => {
      expect(mockGetCases).toHaveBeenCalledTimes(1);
    });
  });

  it("renders department badge for each case", async () => {
    mockGetCases.mockResolvedValue([
      makeFakeCase({ department: "Personalabteilung" }),
    ]);
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Personalabteilung")).toBeTruthy();
    });
  });
});
