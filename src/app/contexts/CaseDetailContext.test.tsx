import { describe, it, expect, vi, beforeEach } from "vitest";
import { act, waitFor } from "@testing-library/react";
import { Route, Routes } from "react-router";
import { renderWithProviders, makeTestQueryClient } from "../test-utils";
import type {
  ApiCase,
  ApiPlaybook,
  CaseRiskScore,
  CaseSimilarityResult,
  PlaybookCoverage,
  RunningCheckJob,
} from "../lib/api";
import { caseDetailKeys } from "../lib/queries/caseDetailQueries";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("../lib/api/cases", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/api/cases")>();
  return {
    ...actual,
    runChecks: vi.fn(),
    getCaseRiskScore: vi.fn(),
    getSimilarCases: vi.fn(),
  };
});

vi.mock("../lib/api/playbooks", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/api/playbooks")>();
  return {
    ...actual,
    getPlaybooks: vi.fn(),
    getPlaybooksForSelection: vi.fn(),
  };
});

vi.mock("../lib/api/findings", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/api/findings")>();
  return {
    ...actual,
    getPlaybookCoveragePreview: vi.fn(),
  };
});

vi.mock("../lib/logger", () => ({
  logger: { debug: vi.fn(), info: vi.fn(), warn: vi.fn(), error: vi.fn() },
}));

const mockRegisterJob = vi.fn();
const mockGetJob = vi.fn<(caseId: string) => RunningCheckJob | undefined>();

vi.mock("./RunningChecksContext", () => ({
  useRunningChecks: () => ({
    jobs: [],
    registerJob: mockRegisterJob,
    isRunning: () => false,
    getJob: mockGetJob,
    dismissJob: vi.fn(),
    runningCount: 0,
  }),
}));

import { runChecks, getCaseRiskScore, getSimilarCases } from "../lib/api/cases";
import { getPlaybooks, getPlaybooksForSelection } from "../lib/api/playbooks";
import { getPlaybookCoveragePreview } from "../lib/api/findings";
import { logger } from "../lib/logger";
import { CaseDetailProvider, useCaseDetail } from "./CaseDetailContext";

const mockRunChecks = vi.mocked(runChecks);
const mockGetCaseRiskScore = vi.mocked(getCaseRiskScore);
const mockGetSimilarCases = vi.mocked(getSimilarCases);
const mockGetPlaybooks = vi.mocked(getPlaybooks);
const mockGetPlaybooksForSelection = vi.mocked(getPlaybooksForSelection);
const mockGetCoverage = vi.mocked(getPlaybookCoveragePreview);
const mockLogger = vi.mocked(logger);

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const CASE_ID = "case-1";

const fakeCase: ApiCase = {
  id: CASE_ID,
  title: "Testvorgang",
  department: "IT",
  caseType: "dsfa",
  status: "in_review",
  createdAt: "2026-01-01T00:00:00Z",
  updatedAt: "2026-01-01T00:00:00Z",
  createdBy: "u1",
  assignee: "DSB Team",
  language: "de",
  playbookVersion: "1.0",
  processingContext: "  cloud  ",
  documents: [],
  findings: [],
};

function makePlaybook(id: string, name: string): ApiPlaybook {
  return {
    id,
    name,
    version: "1",
    content: {},
    caseType: null,
    department: null,
    isActive: true,
    status: "active",
    createdAt: "2026-01-01T00:00:00Z",
    updatedAt: "2026-01-01T00:00:00Z",
    checks: [],
  };
}

const pbA = makePlaybook("pb-a", "Playbook A");
const pbB = makePlaybook("pb-b", "Playbook B");

const fakeRisk: CaseRiskScore = { case_id: CASE_ID, score: 42, history: [] };
const fakeSimilar: CaseSimilarityResult[] = [
  {
    case_id: "case-2",
    title: "Ähnlich",
    department: "IT",
    case_type: "dsfa",
    status: "open",
    overlap_score: 0.8,
    shared_check_names: ["c1"],
    resolution_summary: {},
  },
];
const fakeCoverage: PlaybookCoverage = {
  playbook_id: "pb-a",
  case_id: CASE_ID,
  total_checks: 3,
  applicable_count: 2,
  checks: [],
  missing_document_types: [],
};

function makeJob(overrides: Partial<RunningCheckJob> = {}): RunningCheckJob {
  return {
    jobId: "job-1",
    caseId: CASE_ID,
    caseTitle: "Testvorgang",
    playbookName: null,
    status: "running",
    checksDone: 2,
    checksTotal: 5,
    createdAt: null,
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Harness
// ---------------------------------------------------------------------------

type Ctx = ReturnType<typeof useCaseDetail>;

function renderProvider(caseData: ApiCase | null = fakeCase, route = `/cases/${CASE_ID}`) {
  const queryClient = makeTestQueryClient();
  let ctx: Ctx | undefined;

  function Probe() {
    ctx = useCaseDetail();
    return null;
  }

  const ui = (
    <Routes>
      <Route
        path="/cases/:caseId"
        element={
          <CaseDetailProvider caseData={caseData}>
            <Probe />
          </CaseDetailProvider>
        }
      />
      <Route
        path="/no-case"
        element={
          <CaseDetailProvider caseData={caseData}>
            <Probe />
          </CaseDetailProvider>
        }
      />
    </Routes>
  );

  const view = renderWithProviders(ui, { queryClient, routerProps: { initialEntries: [route] } });

  return {
    queryClient,
    rerender: () => view.rerender(ui),
    get ctx(): Ctx {
      if (!ctx) throw new Error("CaseDetailProvider did not render the probe");
      return ctx;
    },
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.clearAllMocks();
  mockGetJob.mockReturnValue(undefined);
  mockGetCaseRiskScore.mockResolvedValue(fakeRisk);
  mockGetSimilarCases.mockResolvedValue(fakeSimilar);
  mockGetCoverage.mockResolvedValue(fakeCoverage);
  mockGetPlaybooksForSelection.mockResolvedValue([
    { playbook: pbA, matchPriority: 1 },
    { playbook: pbB, matchPriority: 2 },
  ]);
  mockGetPlaybooks.mockResolvedValue([pbA, pbB]);
});

describe("useCaseDetail", () => {
  it("throws when used outside CaseDetailProvider", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    function Bare() {
      useCaseDetail();
      return null;
    }
    expect(() => renderWithProviders(<Bare />)).toThrow("useCaseDetail must be used inside CaseDetailProvider");
    spy.mockRestore();
  });
});

describe("CaseDetailProvider – initial state and derived data", () => {
  it("exposes idle defaults", () => {
    const h = renderProvider();
    expect(h.ctx.runChecksOpen).toBe(false);
    expect(h.ctx.playbooks).toEqual([]);
    expect(h.ctx.selectedPlaybookId).toBe("");
    expect(h.ctx.runChecksStrategy).toBe("full_text");
    expect(h.ctx.runChecksLoading).toBe(false);
    expect(h.ctx.runChecksStatus).toBe("idle");
    expect(h.ctx.runChecksError).toBeNull();
    expect(h.ctx.runChecksProgress).toEqual({ done: 0, total: 0 });
    expect(h.ctx.coveragePreview).toBeNull();
    expect(h.ctx.similarCases).toEqual([]);
    expect(h.ctx.riskScore).toBeNull();
  });

  it("loads risk score and similar cases for the route's caseId", async () => {
    const h = renderProvider();

    await waitFor(() => expect(h.ctx.riskScore).toEqual(fakeRisk));
    await waitFor(() => expect(h.ctx.similarCases).toEqual(fakeSimilar));

    expect(mockGetCaseRiskScore).toHaveBeenCalledWith(CASE_ID);
    expect(mockGetSimilarCases).toHaveBeenCalledWith(CASE_ID);
  });

  it("does not fetch anything without a caseId in the route", () => {
    const h = renderProvider(fakeCase, "/no-case");
    expect(h.ctx.riskScore).toBeNull();
    expect(mockGetCaseRiskScore).not.toHaveBeenCalled();
    expect(mockGetSimilarCases).not.toHaveBeenCalled();
    expect(mockGetJob).not.toHaveBeenCalled();
  });

  it("derives status and progress from the running job", () => {
    mockGetJob.mockReturnValue(makeJob({ status: "running", checksDone: 2, checksTotal: 5 }));
    const h = renderProvider();
    expect(mockGetJob).toHaveBeenCalledWith(CASE_ID);
    expect(h.ctx.runChecksStatus).toBe("running");
    expect(h.ctx.runChecksProgress).toEqual({ done: 2, total: 5 });
  });

  it("maps a failed job to status 'failed' and other statuses to 'idle'", () => {
    mockGetJob.mockReturnValue(makeJob({ status: "failed" }));
    expect(renderProvider().ctx.runChecksStatus).toBe("failed");

    mockGetJob.mockReturnValue(makeJob({ status: "completed" }));
    expect(renderProvider().ctx.runChecksStatus).toBe("idle");
  });

  it("updates strategy via setRunChecksStrategy", () => {
    const h = renderProvider();
    act(() => h.ctx.setRunChecksStrategy("rag"));
    expect(h.ctx.runChecksStrategy).toBe("rag");
  });
});

describe("CaseDetailProvider – playbook loading", () => {
  it("does not load playbooks until the dialog is opened", () => {
    renderProvider();
    expect(mockGetPlaybooksForSelection).not.toHaveBeenCalled();
    expect(mockGetPlaybooks).not.toHaveBeenCalled();
  });

  it("loads matching playbooks with trimmed processing context when opened", async () => {
    const h = renderProvider();

    act(() => h.ctx.setRunChecksOpen(true));
    expect(h.ctx.runChecksOpen).toBe(true);

    await waitFor(() => expect(h.ctx.playbooks).toEqual([pbA, pbB]));
    expect(mockGetPlaybooksForSelection).toHaveBeenCalledWith({
      department: "IT",
      processing_context: "cloud",
      case_type: "dsfa",
      strict_case_type: true,
    });
    expect(mockGetPlaybooks).not.toHaveBeenCalled();
  });

  it("passes an undefined processing context when the case has none", async () => {
    const h = renderProvider({ ...fakeCase, processingContext: "   " });
    act(() => h.ctx.setRunChecksOpen(true));

    await waitFor(() => expect(mockGetPlaybooksForSelection).toHaveBeenCalled());
    expect(mockGetPlaybooksForSelection.mock.calls[0][0].processing_context).toBeUndefined();
  });

  it("falls back to the full list when no playbook matches", async () => {
    mockGetPlaybooksForSelection.mockResolvedValue([]);
    mockGetPlaybooks.mockResolvedValue([pbB]);
    const h = renderProvider();

    act(() => h.ctx.setRunChecksOpen(true));

    await waitFor(() => expect(h.ctx.playbooks).toEqual([pbB]));
    expect(mockGetPlaybooks).toHaveBeenCalledTimes(1);
  });

  it("warns and falls back to the full list when the selection endpoint fails", async () => {
    const failure = new Error("selection down");
    mockGetPlaybooksForSelection.mockRejectedValue(failure);
    mockGetPlaybooks.mockResolvedValue([pbA]);
    const h = renderProvider();

    act(() => h.ctx.setRunChecksOpen(true));

    await waitFor(() => expect(h.ctx.playbooks).toEqual([pbA]));
    expect(mockLogger.warn).toHaveBeenCalledWith(
      "Playbook selection failed; falling back to the full list",
      {},
      failure,
    );
  });

  it("ends with an empty list (and a second warning) when both endpoints fail", async () => {
    mockGetPlaybooksForSelection.mockRejectedValue(new Error("selection down"));
    const listFailure = new Error("list down");
    mockGetPlaybooks.mockRejectedValue(listFailure);
    const h = renderProvider();

    act(() => h.ctx.setRunChecksOpen(true));

    await waitFor(() =>
      expect(mockLogger.warn).toHaveBeenCalledWith("Playbook list failed; no playbooks available", {}, listFailure),
    );
    expect(h.ctx.playbooks).toEqual([]);
  });

  it("does not load playbooks when no case data is available", () => {
    const h = renderProvider(null);
    act(() => h.ctx.setRunChecksOpen(true));
    expect(mockGetPlaybooksForSelection).not.toHaveBeenCalled();
  });

  it("fetches the coverage preview once a playbook is selected", async () => {
    const h = renderProvider();
    expect(mockGetCoverage).not.toHaveBeenCalled();

    act(() => h.ctx.setSelectedPlaybookId("pb-a"));

    await waitFor(() => expect(h.ctx.coveragePreview).toEqual(fakeCoverage));
    expect(mockGetCoverage).toHaveBeenCalledWith("pb-a", CASE_ID);
  });
});

describe("CaseDetailProvider – handleRunChecks", () => {
  it("does nothing without a selected playbook", () => {
    const h = renderProvider();
    act(() => h.ctx.handleRunChecks());
    expect(mockRunChecks).not.toHaveBeenCalled();
  });

  it("registers a background job when the backend accepts asynchronously", async () => {
    mockRunChecks.mockResolvedValue({ accepted: true, jobId: "job-9", status: "running" });
    const h = renderProvider();

    act(() => h.ctx.setRunChecksOpen(true));
    await waitFor(() => expect(h.ctx.playbooks).toHaveLength(2));

    act(() => {
      h.ctx.setSelectedPlaybookId("pb-b");
      h.ctx.setRunChecksStrategy("both");
    });
    act(() => h.ctx.handleRunChecks());

    await waitFor(() => expect(mockRegisterJob).toHaveBeenCalledTimes(1));
    expect(mockRunChecks).toHaveBeenCalledWith(CASE_ID, "pb-b", ["full_text", "rag"]);
    expect(mockRegisterJob).toHaveBeenCalledWith(CASE_ID, "job-9", "Testvorgang", "Playbook B");
    // Dialog stays open while the job runs in the background
    expect(h.ctx.runChecksOpen).toBe(true);
    expect(h.ctx.selectedPlaybookId).toBe("pb-b");
    expect(h.ctx.runChecksLoading).toBe(false);
  });

  it("passes the single selected strategy through", async () => {
    mockRunChecks.mockResolvedValue({ accepted: true, jobId: "job-1", status: "running" });
    const h = renderProvider();
    act(() => {
      h.ctx.setSelectedPlaybookId("pb-a");
      h.ctx.setRunChecksStrategy("rag");
    });
    act(() => h.ctx.handleRunChecks());

    await waitFor(() => expect(mockRunChecks).toHaveBeenCalledWith(CASE_ID, "pb-a", ["rag"]));
  });

  it("invalidates case queries and closes the dialog on a synchronous result", async () => {
    mockRunChecks.mockResolvedValue(fakeCase);
    const h = renderProvider();
    const invalidateSpy = vi.spyOn(h.queryClient, "invalidateQueries");

    act(() => h.ctx.setRunChecksOpen(true));
    act(() => h.ctx.setSelectedPlaybookId("pb-a"));
    act(() => h.ctx.handleRunChecks());

    await waitFor(() => expect(h.ctx.runChecksOpen).toBe(false));
    expect(h.ctx.selectedPlaybookId).toBe("");
    expect(mockRegisterJob).not.toHaveBeenCalled();
    for (const key of [
      caseDetailKeys.detail(CASE_ID),
      caseDetailKeys.riskScore(CASE_ID),
      caseDetailKeys.runChecksStatus(CASE_ID),
    ]) {
      expect(invalidateSpy).toHaveBeenCalledWith(expect.objectContaining({ queryKey: key }));
    }
  });

  it("exposes the mutation error message and allows resetting it", async () => {
    mockRunChecks.mockRejectedValue(new Error("LLM nicht erreichbar"));
    const h = renderProvider();

    act(() => h.ctx.setSelectedPlaybookId("pb-a"));
    act(() => h.ctx.handleRunChecks());

    await waitFor(() => expect(h.ctx.runChecksError).toBe("LLM nicht erreichbar"));
    expect(h.ctx.runChecksLoading).toBe(false);

    act(() => h.ctx.setRunChecksError(null));
    await waitFor(() => expect(h.ctx.runChecksError).toBeNull());
  });

  it("uses a generic message when the mutation rejects with a non-Error", async () => {
    mockRunChecks.mockRejectedValue("kaputt");
    const h = renderProvider();

    act(() => h.ctx.setSelectedPlaybookId("pb-a"));
    act(() => h.ctx.handleRunChecks());

    await waitFor(() => expect(h.ctx.runChecksError).toBe("Checks fehlgeschlagen."));
  });

  it("lets callers set a custom error that takes precedence", () => {
    const h = renderProvider();
    act(() => h.ctx.setRunChecksError("Eigener Fehler"));
    expect(h.ctx.runChecksError).toBe("Eigener Fehler");
  });
});

describe("CaseDetailProvider – job status transitions", () => {
  it("invalidates queries and closes the dialog when a running job completes", async () => {
    mockGetJob.mockReturnValue(makeJob({ status: "running" }));
    const h = renderProvider();
    const invalidateSpy = vi.spyOn(h.queryClient, "invalidateQueries");

    act(() => {
      h.ctx.setRunChecksOpen(true);
      h.ctx.setSelectedPlaybookId("pb-a");
    });
    expect(h.ctx.runChecksStatus).toBe("running");

    mockGetJob.mockReturnValue(makeJob({ status: "completed" }));
    act(() => h.rerender());

    await waitFor(() => expect(h.ctx.runChecksOpen).toBe(false));
    expect(h.ctx.selectedPlaybookId).toBe("");
    expect(h.ctx.runChecksStatus).toBe("idle");
    for (const key of [
      caseDetailKeys.detail(CASE_ID),
      caseDetailKeys.riskScore(CASE_ID),
      caseDetailKeys.runChecksStatus(CASE_ID),
    ]) {
      expect(invalidateSpy).toHaveBeenCalledWith(expect.objectContaining({ queryKey: key }));
    }
  });

  it("sets a job error when a running job fails", async () => {
    mockGetJob.mockReturnValue(makeJob({ status: "running" }));
    const h = renderProvider();
    expect(h.ctx.runChecksError).toBeNull();

    mockGetJob.mockReturnValue(makeJob({ status: "failed" }));
    act(() => h.rerender());

    await waitFor(() => expect(h.ctx.runChecksError).toBe("Checks fehlgeschlagen."));
    expect(h.ctx.runChecksStatus).toBe("failed");
  });

  it("does not react to a job that was already completed on mount", () => {
    mockGetJob.mockReturnValue(makeJob({ status: "completed" }));
    const h = renderProvider();
    const invalidateSpy = vi.spyOn(h.queryClient, "invalidateQueries");

    act(() => h.ctx.setRunChecksOpen(true));
    act(() => h.rerender());

    expect(h.ctx.runChecksOpen).toBe(true);
    expect(invalidateSpy).not.toHaveBeenCalled();
  });
});
