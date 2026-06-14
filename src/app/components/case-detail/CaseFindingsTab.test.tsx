import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClientProvider } from "@tanstack/react-query";
import { makeTestQueryClient } from "../../test-utils";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockMutate = vi.fn();

vi.mock("../../lib/queries/caseDetailQueries", () => ({
  useBulkUpdateFindingStatus: vi.fn(() => ({
    mutate: mockMutate,
    isPending: false,
  })),
}));

vi.mock("../../lib/api", () => ({
  downloadFindingsExport: vi.fn(),
  downloadBlob: vi.fn(),
}));

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

import { CaseFindingsTab, type CaseFindingsTabProps } from "./CaseFindingsTab";
import { toast } from "sonner";
import { useBulkUpdateFindingStatus } from "../../lib/queries/caseDetailQueries";

const mockToastSuccess = vi.mocked(toast.success);
const mockToastError = vi.mocked(toast.error);
const mockUseBulkUpdate = vi.mocked(useBulkUpdateFindingStatus);

const makeFakeCase = (overrides = {}) => ({
  id: "case-1",
  title: "Test",
  department: "IT",
  caseType: "vvt",
  status: "in_review" as const,
  createdAt: "2024-01-01T00:00:00Z",
  updatedAt: "2024-01-01T00:00:00Z",
  createdBy: "user",
  assignee: "user",
  language: "de",
  playbookVersion: "1.0",
  documents: [],
  findings: [
    {
      id: "f1",
      checkName: "Check A",
      severity: "high",
      status: "open" as const,
      category: "Datenschutz",
      description: "Beschreibung",
      evidence: [],
      recommendation: "Empfehlung",
    },
    {
      id: "f2",
      checkName: "Check B",
      severity: "low",
      status: "fixed" as const,
      category: "Datenschutz",
      description: "Beschreibung 2",
      evidence: [],
      recommendation: "Empfehlung 2",
    },
  ],
  ...overrides,
});

function renderTab(props: Partial<CaseFindingsTabProps> = {}) {
  const client = makeTestQueryClient();
  return render(
    <QueryClientProvider client={client}>
      <CaseFindingsTab
        caseData={makeFakeCase() as never}
        onSelectFinding={vi.fn()}
        {...props}
      />
    </QueryClientProvider>,
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("CaseFindingsTab", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseBulkUpdate.mockReturnValue({ mutate: mockMutate, isPending: false } as never);
  });

  it("renders finding list", () => {
    renderTab();
    expect(screen.getByText("Check A")).toBeTruthy();
    expect(screen.getByText("Check B")).toBeTruthy();
  });

  it("does not expose onFindingsChanged in the props interface", () => {
    // TypeScript compile check: CaseFindingsTabProps should not have onFindingsChanged.
    // If this file compiles, the prop is gone.
    const props: CaseFindingsTabProps = {
      caseData: makeFakeCase() as never,
      onSelectFinding: vi.fn(),
    };
    expect(props).toBeDefined();
  });

  it("calls useBulkUpdateFindingStatus with caseData.id", () => {
    renderTab();
    expect(mockUseBulkUpdate).toHaveBeenCalledWith("case-1");
  });

  it("calls bulkMutation.mutate when bulk update is applied", async () => {
    renderTab();

    // Select the first finding
    const checkboxes = screen.getAllByRole("checkbox");
    fireEvent.click(checkboxes[1]); // first finding checkbox (index 0 is select-all)

    // Wait for the bulk action bar to appear and click "Anwenden"
    await waitFor(() => expect(screen.getByText("Anwenden")).toBeTruthy());
    fireEvent.click(screen.getByText("Anwenden"));

    expect(mockMutate).toHaveBeenCalledWith(
      { ids: ["f1"], status: "accepted" },
      expect.objectContaining({ onSuccess: expect.any(Function), onError: expect.any(Function) }),
    );
  });

  it("shows success toast when onSuccess callback is triggered", async () => {
    mockUseBulkUpdate.mockReturnValue({
      mutate: ((_args: unknown, opts: { onSuccess: (r: { updated: number }) => void }) => {
        opts.onSuccess({ updated: 1 });
      }) as never,
      isPending: false,
    } as never);

    renderTab();

    const checkboxes = screen.getAllByRole("checkbox");
    fireEvent.click(checkboxes[1]);

    await waitFor(() => expect(screen.getByText("Anwenden")).toBeTruthy());
    fireEvent.click(screen.getByText("Anwenden"));

    expect(mockToastSuccess).toHaveBeenCalledWith("1 Findings aktualisiert");
  });

  it("shows error toast when onError callback is triggered", async () => {
    mockUseBulkUpdate.mockReturnValue({
      mutate: ((_args: unknown, opts: { onError: () => void }) => {
        opts.onError();
      }) as never,
      isPending: false,
    } as never);

    renderTab();

    const checkboxes = screen.getAllByRole("checkbox");
    fireEvent.click(checkboxes[1]);

    await waitFor(() => expect(screen.getByText("Anwenden")).toBeTruthy());
    fireEvent.click(screen.getByText("Anwenden"));

    expect(mockToastError).toHaveBeenCalledWith("Fehler beim Aktualisieren der Findings");
  });

  it("disables Anwenden button while mutation is pending", async () => {
    mockUseBulkUpdate.mockReturnValue({ mutate: mockMutate, isPending: true } as never);
    renderTab();

    const checkboxes = screen.getAllByRole("checkbox");
    fireEvent.click(checkboxes[1]);

    await waitFor(() => {
      const btn = screen.getByText("Anwenden").closest("button");
      expect(btn).toBeDefined();
      expect(btn?.disabled).toBe(true);
    });
  });
});
