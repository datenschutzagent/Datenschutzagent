import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../test-utils";
import type { ApiDataBreach } from "../lib/api";

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

import {
  listDataBreaches,
  updateDataBreach,
  createDataBreach,
  getDataBreachActivity,
} from "../lib/api";
import { toast } from "sonner";
import { DataBreachesPage } from "./data-breaches-page";

const mockList = vi.mocked(listDataBreaches);
const mockUpdate = vi.mocked(updateDataBreach);
const mockCreate = vi.mocked(createDataBreach);
const mockActivity = vi.mocked(getDataBreachActivity);
const mockToastSuccess = vi.mocked(toast.success);

const baseBreach: ApiDataBreach = {
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
};

const makeFakeBreach = (overrides: Partial<ApiDataBreach> = {}): ApiDataBreach => ({
  ...baseBreach,
  ...overrides,
});

function renderPage() {
  return renderWithProviders(<DataBreachesPage />);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("DataBreachesPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockActivity.mockResolvedValue([]);
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

  it("passes server-side filters to listDataBreaches", async () => {
    mockList.mockResolvedValue({ items: [], total: 0 });
    renderPage();
    await waitFor(() => expect(mockList).toHaveBeenCalledTimes(1));
    expect(mockList).toHaveBeenLastCalledWith({ status: undefined, overdueOnly: false });

    await userEvent.click(screen.getByLabelText("Nur überfällige"));
    await waitFor(() => expect(mockList).toHaveBeenCalledTimes(2));
    expect(mockList).toHaveBeenLastCalledWith({ status: undefined, overdueOnly: true });
  });

  it("shows an error state with retry and reloads on click", async () => {
    mockList
      .mockRejectedValueOnce(new Error("Netzwerkfehler"))
      .mockResolvedValue({ items: [makeFakeBreach()], total: 1 });
    renderPage();

    expect(await screen.findByText("Datenpannen konnten nicht geladen werden.")).toBeTruthy();
    expect(screen.getByText("Netzwerkfehler")).toBeTruthy();
    expect(screen.queryByText("Test-Datenpanne")).toBeNull();

    await userEvent.click(screen.getByRole("button", { name: "Erneut versuchen" }));

    expect(await screen.findByText("Test-Datenpanne")).toBeTruthy();
    expect(mockList).toHaveBeenCalledTimes(2);
    expect(screen.queryByText("Datenpannen konnten nicht geladen werden.")).toBeNull();
  });

  it("reloads the list after a status change in the detail dialog", async () => {
    mockList.mockResolvedValue({ items: [makeFakeBreach()], total: 1 });
    mockUpdate.mockResolvedValue(makeFakeBreach({ status: "assessed" }));
    renderPage();

    await userEvent.click(await screen.findByText("Test-Datenpanne"));
    expect(await screen.findByText("Status ändern")).toBeTruthy();
    await waitFor(() => expect(mockActivity).toHaveBeenCalledWith("breach-1"));
    expect(mockList).toHaveBeenCalledTimes(1);

    await userEvent.click(screen.getByRole("button", { name: "Bewertet" }));

    await waitFor(() => {
      expect(mockUpdate).toHaveBeenCalledWith("breach-1", { status: "assessed" });
      expect(mockList).toHaveBeenCalledTimes(2);
    });
    expect(mockToastSuccess).toHaveBeenCalledWith("Status aktualisiert.");
  });

  it("reloads the list after creating a breach", async () => {
    mockList.mockResolvedValue({ items: [], total: 0 });
    mockCreate.mockResolvedValue(makeFakeBreach({ id: "breach-new", title: "Neue Panne" }));
    renderPage();

    await screen.findByText(/Keine Datenpannen/);
    await userEvent.click(screen.getByRole("button", { name: /Datenpanne erfassen/ }));
    await userEvent.type(screen.getByLabelText("Titel *"), "Neue Panne");
    await userEvent.click(screen.getByRole("button", { name: "Erfassen" }));

    await waitFor(() => {
      expect(mockCreate).toHaveBeenCalledTimes(1);
      expect(mockList).toHaveBeenCalledTimes(2);
    });
    expect(mockCreate.mock.calls[0][0]).toMatchObject({
      title: "Neue Panne",
      breach_type: "confidentiality",
    });
    expect(mockToastSuccess).toHaveBeenCalledWith("Datenpanne erfasst.");
  });
});
