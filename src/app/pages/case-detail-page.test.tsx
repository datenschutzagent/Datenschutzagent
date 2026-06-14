import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router";
import { makeTestQueryClient } from "../test-utils";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("../lib/queries/caseDetailQueries", () => ({
  useCase: vi.fn(),
  useRunChecksStatus: vi.fn(() => ({ data: undefined })),
  useFindingComments: vi.fn(() => ({ data: [] })),
  useUpdateFindingStatus: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
  useCreateFindingComment: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
  useArchiveCase: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
  useUnarchiveCase: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
  caseDetailKeys: {
    all: (id: string) => ["case", id],
    detail: (id: string) => ["case", id, "detail"],
    runChecksStatus: (id: string) => ["case", id, "run-checks-status"],
    riskScore: (id: string) => ["case", id, "risk-score"],
    similarCases: (id: string) => ["case", id, "similar"],
    findingComments: (id: string) => ["finding", id, "comments"],
  },
}));

// Mock the context so CaseDetailProvider does not make real API calls
vi.mock("../contexts/CaseDetailContext", () => ({
  CaseDetailProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  useCaseDetail: vi.fn(() => ({
    runChecksOpen: false,
    setRunChecksOpen: vi.fn(),
    playbooks: [],
    selectedPlaybookId: "",
    setSelectedPlaybookId: vi.fn(),
    runChecksStrategy: "full_text" as const,
    setRunChecksStrategy: vi.fn(),
    runChecksLoading: false,
    runChecksStatus: "idle" as const,
    runChecksError: null,
    setRunChecksError: vi.fn(),
    runChecksProgress: { done: 0, total: 0 },
    coveragePreview: null,
    similarCases: [],
    riskScore: null,
    handleRunChecks: vi.fn(),
  })),
}));

vi.mock("../lib/api", () => ({
  canEdit: vi.fn(() => false),
  isAdmin: vi.fn(() => false),
  getAuditTrailExportBlob: vi.fn(),
  downloadAuditPackage: vi.fn(),
  downloadBlob: vi.fn(),
  downloadAuditTrail: vi.fn(),
  downloadRopaExport: vi.fn(),
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

// Stub heavy sub-components to keep tests fast and focused
vi.mock("../components/vvt-normalization-view", () => ({
  VVTNormalizationView: () => <div data-testid="vvt-view" />,
}));
vi.mock("../components/dsb-report-view", () => ({
  DSBReportView: () => <div data-testid="dsb-view" />,
}));
vi.mock("../components/annotated-documents-view", () => ({
  AnnotatedDocumentsView: () => <div data-testid="annotated-view" />,
}));
vi.mock("../components/activity-timeline", () => ({
  ActivityTimeline: () => <div data-testid="activity-timeline" />,
}));
vi.mock("../components/case-detail/CaseOverviewTab", () => ({
  CaseOverviewTab: () => <div data-testid="overview-tab" />,
}));
vi.mock("../components/case-detail/CaseDocumentsTab", () => ({
  CaseDocumentsTab: () => <div data-testid="documents-tab" />,
}));
vi.mock("../components/case-detail/CaseFindingsTab", () => ({
  CaseFindingsTab: () => <div data-testid="findings-tab" />,
}));

import { useCase } from "../lib/queries/caseDetailQueries";
import { CaseDetailPage } from "./case-detail-page";

const mockUseCase = vi.mocked(useCase);

const makeFakeCase = (overrides: Record<string, unknown> = {}) => ({
  id: "case-42",
  title: "DSGVO-Prüfung Testfall",
  department: "IT-Sicherheit",
  caseType: "vvt",
  status: "in_review" as const,
  createdAt: "2024-03-01T10:00:00Z",
  updatedAt: "2024-03-15T12:00:00Z",
  createdBy: "user-1",
  assignee: "Erika Muster",
  language: "de",
  playbookVersion: "1.0",
  specialCategoryData: false,
  internationalTransfer: false,
  autoRunChecks: false,
  documents: [],
  findings: [],
  ...overrides,
});

function renderPage(caseId = "case-42") {
  const client = makeTestQueryClient();
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/cases/${caseId}`]}>
        <Routes>
          <Route path="/cases/:caseId" element={<CaseDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("CaseDetailPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows loading spinner before case data arrives", () => {
    mockUseCase.mockReturnValue({ data: undefined, isLoading: true, error: null } as never);
    renderPage();
    const loaders = document.querySelectorAll("[class*='animate-spin']");
    expect(loaders.length).toBeGreaterThan(0);
  });

  it("renders case title after loading", async () => {
    mockUseCase.mockReturnValue({ data: makeFakeCase(), isLoading: false, error: null } as never);
    renderPage();
    await waitFor(() => {
      expect(screen.getAllByText("DSGVO-Prüfung Testfall").length).toBeGreaterThan(0);
    });
  });

  it("renders department in breadcrumb/header area", async () => {
    mockUseCase.mockReturnValue({
      data: makeFakeCase({ department: "Rechtsabteilung" }),
      isLoading: false,
      error: null,
    } as never);
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Rechtsabteilung")).toBeTruthy();
    });
  });

  it("renders tab navigation", async () => {
    mockUseCase.mockReturnValue({ data: makeFakeCase(), isLoading: false, error: null } as never);
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Überblick")).toBeTruthy();
      expect(screen.getAllByText(/Dokumente/).length).toBeGreaterThan(0);
      expect(screen.getAllByText(/Findings/).length).toBeGreaterThan(0);
    });
  });

  it("shows error message when useCase returns an error", async () => {
    mockUseCase.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error("Vorgang nicht gefunden"),
    } as never);
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/Vorgang nicht gefunden/i)).toBeTruthy();
    });
  });

  it("calls useCase with the correct ID from URL params", async () => {
    mockUseCase.mockReturnValue({ data: makeFakeCase({ id: "case-99" }), isLoading: false, error: null } as never);
    renderPage("case-99");
    await waitFor(() => {
      expect(mockUseCase).toHaveBeenCalledWith("case-99");
    });
  });

  it("renders overview tab content by default", async () => {
    mockUseCase.mockReturnValue({ data: makeFakeCase(), isLoading: false, error: null } as never);
    renderPage();
    await waitFor(() => {
      expect(screen.getByTestId("overview-tab")).toBeTruthy();
    });
  });
});
