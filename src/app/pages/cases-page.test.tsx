import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders } from "../test-utils";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("../lib/queries/casesQueries", () => ({
  useCases: vi.fn(),
  useArchivedCases: vi.fn(),
  useInvalidateCases: vi.fn(() => vi.fn()),
  casesKeys: {
    all: ["cases"],
    list: (f?: unknown) => ["cases", "list", f ?? {}],
    archived: () => ["cases", "archived"],
  },
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

// Stub heavy sub-components that are not under test
vi.mock("../components/dashboard-stats", () => ({
  DashboardStats: () => null,
}));
vi.mock("../components/new-case-dialog", () => ({
  NewCaseDialog: () => null,
}));
vi.mock("../components/cases-search-filter", () => ({
  CasesSearchFilter: () => null,
}));
vi.mock("../lib/api", () => ({
  unarchiveCase: vi.fn(),
  canEdit: vi.fn(() => true),
  isAdmin: vi.fn(() => false),
}));

import { useCases, useArchivedCases } from "../lib/queries/casesQueries";
import { CasesPage } from "./cases-page";

const mockUseCases = vi.mocked(useCases);
const mockUseArchivedCases = vi.mocked(useArchivedCases);

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

const loadingState = { data: undefined, isLoading: true, isError: false, error: null };
const emptyState = { data: [], isLoading: false, isError: false, error: null };

function renderPage() {
  return renderWithProviders(<CasesPage />);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("CasesPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseArchivedCases.mockReturnValue(emptyState as ReturnType<typeof useArchivedCases>);
  });

  it("shows a loading skeleton while cases are being fetched", () => {
    mockUseCases.mockReturnValue(loadingState as ReturnType<typeof useCases>);
    renderPage();
    const skeletons = document.querySelectorAll("[data-slot='skeleton']");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("renders case titles after loading", async () => {
    mockUseCases.mockReturnValue({
      data: [
        makeFakeCase({ title: "Datenschutzfall Alpha" }),
        makeFakeCase({ id: "case-2", title: "Datenschutzfall Beta" }),
      ],
      isLoading: false,
      isError: false,
      error: null,
    } as ReturnType<typeof useCases>);

    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Datenschutzfall Alpha")).toBeTruthy();
      expect(screen.getByText("Datenschutzfall Beta")).toBeTruthy();
    });
  });

  it("shows an error message when the query fails", async () => {
    mockUseCases.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: new Error("Netzwerkfehler"),
    } as ReturnType<typeof useCases>);

    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/Netzwerkfehler/i)).toBeTruthy();
    });
  });

  it("shows empty state when no cases exist", async () => {
    mockUseCases.mockReturnValue(emptyState as ReturnType<typeof useCases>);
    renderPage();
    await waitFor(() => {
      expect(screen.queryByText("Datenschutzfall")).toBeNull();
    });
  });

  it("renders department badge for each case", async () => {
    mockUseCases.mockReturnValue({
      data: [makeFakeCase({ department: "Personalabteilung" })],
      isLoading: false,
      isError: false,
      error: null,
    } as ReturnType<typeof useCases>);

    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Personalabteilung")).toBeTruthy();
    });
  });
});
