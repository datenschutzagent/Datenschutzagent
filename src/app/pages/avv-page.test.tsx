import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../test-utils";
import type { ApiAVVContract } from "../lib/api";

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

import { listAVVContracts, updateAVVContract, createAVVContract } from "../lib/api";
import { toast } from "sonner";
import { AVVPage } from "./avv-page";

const mockList = vi.mocked(listAVVContracts);
const mockUpdate = vi.mocked(updateAVVContract);
const mockCreate = vi.mocked(createAVVContract);
const mockToastSuccess = vi.mocked(toast.success);

const baseAVV: ApiAVVContract = {
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
  riskScore: null,
  riskLevel: null,
  riskAssessedAt: null,
  createdAt: "2026-01-01T10:00:00Z",
  updatedAt: "2026-01-01T10:00:00Z",
};

const makeFakeAVV = (overrides: Partial<ApiAVVContract> = {}): ApiAVVContract => ({
  ...baseAVV,
  ...overrides,
});

function renderPage() {
  return renderWithProviders(<AVVPage />);
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

  it("passes server-side filters to listAVVContracts", async () => {
    mockList.mockResolvedValue({ items: [], total: 0 });
    renderPage();
    await waitFor(() => expect(mockList).toHaveBeenCalledTimes(1));
    expect(mockList).toHaveBeenLastCalledWith({ status: undefined, expiringSoon: false });

    await userEvent.click(screen.getByLabelText("Bald ablaufend (90 Tage)"));
    await waitFor(() => expect(mockList).toHaveBeenCalledTimes(2));
    expect(mockList).toHaveBeenLastCalledWith({ status: undefined, expiringSoon: true });
  });

  it("shows an error state with retry and reloads on click", async () => {
    mockList
      .mockRejectedValueOnce(new Error("Netzwerkfehler"))
      .mockResolvedValue({ items: [makeFakeAVV()], total: 1 });
    renderPage();

    expect(await screen.findByText("AVV konnten nicht geladen werden.")).toBeTruthy();
    expect(screen.getByText("Netzwerkfehler")).toBeTruthy();
    expect(screen.queryByText("Cloud Corp GmbH")).toBeNull();

    await userEvent.click(screen.getByRole("button", { name: "Erneut versuchen" }));

    expect(await screen.findByText("Cloud Corp GmbH")).toBeTruthy();
    expect(mockList).toHaveBeenCalledTimes(2);
    expect(screen.queryByText("AVV konnten nicht geladen werden.")).toBeNull();
  });

  it("reloads the list after a status change in the detail dialog", async () => {
    mockList.mockResolvedValue({ items: [makeFakeAVV()], total: 1 });
    mockUpdate.mockResolvedValue(makeFakeAVV({ status: "pending" }));
    renderPage();

    await userEvent.click(await screen.findByText("Cloud Corp GmbH"));
    expect(await screen.findByText("Status ändern")).toBeTruthy();
    expect(mockList).toHaveBeenCalledTimes(1);

    await userEvent.click(screen.getByRole("button", { name: "Ausstehend" }));

    await waitFor(() => {
      expect(mockUpdate).toHaveBeenCalledWith("avv-1", { status: "pending" });
      expect(mockList).toHaveBeenCalledTimes(2);
    });
    expect(mockToastSuccess).toHaveBeenCalledWith("Status aktualisiert.");
  });

  it("reloads the list after creating a contract", async () => {
    mockList.mockResolvedValue({ items: [], total: 0 });
    mockCreate.mockResolvedValue(makeFakeAVV({ id: "avv-new", partnerName: "Neue Firma" }));
    renderPage();

    await screen.findByText(/Keine AVV/);
    await userEvent.click(screen.getByRole("button", { name: /AVV anlegen/ }));
    await userEvent.type(screen.getByLabelText("Partnername *"), "Neue Firma");
    await userEvent.click(screen.getByRole("button", { name: "Anlegen" }));

    await waitFor(() => {
      expect(mockCreate).toHaveBeenCalledTimes(1);
      expect(mockList).toHaveBeenCalledTimes(2);
    });
    expect(mockCreate.mock.calls[0][0]).toMatchObject({
      partner_name: "Neue Firma",
      partner_type: "processor",
    });
    expect(mockToastSuccess).toHaveBeenCalledWith("AVV angelegt.");
  });
});
