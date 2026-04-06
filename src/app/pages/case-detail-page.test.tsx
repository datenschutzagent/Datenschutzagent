import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("../lib/api", () => ({
  getCase: vi.fn(),
  getPlaybooks: vi.fn(() => Promise.resolve([])),
  getPlaybooksForSelection: vi.fn(() => Promise.resolve([])),
  runChecks: vi.fn(),
  getRunChecksStatus: vi.fn(() =>
    Promise.resolve({
      status: "never_run",
      job_id: null,
      playbook_name: null,
      findings_count: null,
      error: null,
      last_run: null,
      documents_changed_since_last_run: false,
      checks_total: 0,
      checks_done: 0,
    })
  ),
  updateFindingStatus: vi.fn(),
  getFindingComments: vi.fn(() => Promise.resolve([])),
  createFindingComment: vi.fn(),
  getPlaybookCoveragePreview: vi.fn(() => Promise.resolve(null)),
  getSimilarCases: vi.fn(() => Promise.resolve([])),
  getCaseRiskScore: vi.fn(() => Promise.resolve(null)),
  archiveCase: vi.fn(),
  unarchiveCase: vi.fn(),
  canEdit: vi.fn(() => false),
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

import { getCase } from "../lib/api";
import { CaseDetailPage } from "./case-detail-page";

const mockGetCase = vi.mocked(getCase);

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
  return render(
    <MemoryRouter initialEntries={[`/cases/${caseId}`]}>
      <Routes>
        <Route path="/cases/:caseId" element={<CaseDetailPage />} />
      </Routes>
    </MemoryRouter>
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
    mockGetCase.mockReturnValue(new Promise(() => {}));
    renderPage();
    // Should render loading indicator
    const loaders = document.querySelectorAll("[class*='animate-spin']");
    expect(loaders.length).toBeGreaterThan(0);
  });

  it("renders case title after loading", async () => {
    mockGetCase.mockResolvedValue(makeFakeCase() as never);
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("DSGVO-Prüfung Testfall")).toBeTruthy();
    });
  });

  it("renders department in breadcrumb/header area", async () => {
    mockGetCase.mockResolvedValue(makeFakeCase({ department: "Rechtsabteilung" }) as never);
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Rechtsabteilung")).toBeTruthy();
    });
  });

  it("renders tab navigation", async () => {
    mockGetCase.mockResolvedValue(makeFakeCase() as never);
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Übersicht")).toBeTruthy();
      expect(screen.getByText("Dokumente")).toBeTruthy();
      expect(screen.getByText("Findings")).toBeTruthy();
    });
  });

  it("shows error message when getCase rejects", async () => {
    mockGetCase.mockRejectedValue(new Error("Vorgang nicht gefunden"));
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/Vorgang nicht gefunden/i)).toBeTruthy();
    });
  });

  it("calls getCase with the correct ID from URL params", async () => {
    mockGetCase.mockResolvedValue(makeFakeCase({ id: "case-99" }) as never);
    renderPage("case-99");
    await waitFor(() => {
      expect(mockGetCase).toHaveBeenCalledWith("case-99");
    });
  });

  it("renders overview tab content by default", async () => {
    mockGetCase.mockResolvedValue(makeFakeCase() as never);
    renderPage();
    await waitFor(() => {
      expect(screen.getByTestId("overview-tab")).toBeTruthy();
    });
  });
});
