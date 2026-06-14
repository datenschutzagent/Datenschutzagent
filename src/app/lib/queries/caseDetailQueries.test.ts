import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { makeTestQueryClient } from "../../test-utils";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("../api/cases", () => ({
  getCase: vi.fn(),
  getRunChecksStatus: vi.fn(),
  getSimilarCases: vi.fn(),
  updateCase: vi.fn(),
  archiveCase: vi.fn(),
  unarchiveCase: vi.fn(),
}));

vi.mock("../api/findings", () => ({
  updateFindingStatus: vi.fn(),
  bulkUpdateFindingStatus: vi.fn(),
  getFindingComments: vi.fn(),
  createFindingComment: vi.fn(),
}));

vi.mock("./casesQueries", () => ({
  casesKeys: { all: ["cases"] },
}));

import {
  useCase,
  useRunChecksStatus,
  useFindingComments,
  useUpdateFindingStatus,
  useCreateFindingComment,
  useBulkUpdateFindingStatus,
  caseDetailKeys,
} from "./caseDetailQueries";
import { getCase, getRunChecksStatus } from "../api/cases";
import { updateFindingStatus, bulkUpdateFindingStatus, getFindingComments, createFindingComment } from "../api/findings";

const mockGetCase = vi.mocked(getCase);
const mockGetRunChecksStatus = vi.mocked(getRunChecksStatus);
const mockUpdateFindingStatus = vi.mocked(updateFindingStatus);
const mockBulkUpdateFindingStatus = vi.mocked(bulkUpdateFindingStatus);
const mockGetFindingComments = vi.mocked(getFindingComments);
const mockCreateFindingComment = vi.mocked(createFindingComment);

function makeWrapper(client?: QueryClient) {
  const qc = client ?? makeTestQueryClient();
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(QueryClientProvider, { client: qc }, children);
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("caseDetailKeys", () => {
  it("builds hierarchical keys so all invalidates correctly", () => {
    expect(caseDetailKeys.detail("abc")).toEqual(["case", "abc", "detail"]);
    expect(caseDetailKeys.riskScore("abc")).toEqual(["case", "abc", "risk-score"]);
    expect(caseDetailKeys.findingComments("f1")).toEqual(["finding", "f1", "comments"]);
  });
});

describe("useCase", () => {
  beforeEach(() => vi.clearAllMocks());

  it("fetches and returns case data", async () => {
    const fakeCase = { id: "c1", title: "Test", findings: [], documents: [] };
    mockGetCase.mockResolvedValue(fakeCase as never);

    const { result } = renderHook(() => useCase("c1"), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(fakeCase);
    expect(mockGetCase).toHaveBeenCalledWith("c1");
  });

  it("does not fetch when caseId is empty", () => {
    const { result } = renderHook(() => useCase(""), { wrapper: makeWrapper() });
    expect(result.current.fetchStatus).toBe("idle");
    expect(mockGetCase).not.toHaveBeenCalled();
  });
});

describe("useRunChecksStatus", () => {
  beforeEach(() => vi.clearAllMocks());

  it("fetches run-checks status", async () => {
    const fakeStatus = { status: "never_run", job_id: null };
    mockGetRunChecksStatus.mockResolvedValue(fakeStatus as never);

    const { result } = renderHook(() => useRunChecksStatus("c1"), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(fakeStatus);
  });
});

describe("useFindingComments", () => {
  beforeEach(() => vi.clearAllMocks());

  it("does not fetch when findingId is null", () => {
    const { result } = renderHook(() => useFindingComments(null), { wrapper: makeWrapper() });
    expect(result.current.fetchStatus).toBe("idle");
    expect(mockGetFindingComments).not.toHaveBeenCalled();
  });

  it("fetches comments when findingId is provided", async () => {
    const fakeComments = [{ id: "cm1", text: "hello", author: "user" }];
    mockGetFindingComments.mockResolvedValue(fakeComments as never);

    const { result } = renderHook(() => useFindingComments("f1"), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(fakeComments);
    expect(mockGetFindingComments).toHaveBeenCalledWith("f1");
  });
});

describe("useUpdateFindingStatus", () => {
  beforeEach(() => vi.clearAllMocks());

  it("calls updateFindingStatus and invalidates case detail on success", async () => {
    const client = makeTestQueryClient();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");
    mockUpdateFindingStatus.mockResolvedValue({ id: "f1", status: "fixed" } as never);

    const { result } = renderHook(() => useUpdateFindingStatus("c1"), { wrapper: makeWrapper(client) });

    result.current.mutate({ findingId: "f1", status: "fixed" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockUpdateFindingStatus).toHaveBeenCalledWith("f1", "fixed");
    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: caseDetailKeys.detail("c1") }),
    );
  });
});

describe("useBulkUpdateFindingStatus", () => {
  beforeEach(() => vi.clearAllMocks());

  it("calls bulkUpdateFindingStatus and invalidates case detail on success", async () => {
    const client = makeTestQueryClient();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");
    mockBulkUpdateFindingStatus.mockResolvedValue({ updated: 3 });

    const { result } = renderHook(() => useBulkUpdateFindingStatus("c1"), { wrapper: makeWrapper(client) });

    result.current.mutate({ ids: ["f1", "f2", "f3"], status: "accepted" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockBulkUpdateFindingStatus).toHaveBeenCalledWith(["f1", "f2", "f3"], "accepted");
    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: caseDetailKeys.detail("c1") }),
    );
  });
});

describe("useCreateFindingComment", () => {
  beforeEach(() => vi.clearAllMocks());

  it("calls createFindingComment and invalidates finding comments on success", async () => {
    const client = makeTestQueryClient();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");
    const fakeComment = { id: "cm1", text: "test", author: "user" };
    mockCreateFindingComment.mockResolvedValue(fakeComment as never);

    const { result } = renderHook(() => useCreateFindingComment("f1"), { wrapper: makeWrapper(client) });

    result.current.mutate("test");

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockCreateFindingComment).toHaveBeenCalledWith("f1", "test");
    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: caseDetailKeys.findingComments("f1") }),
    );
  });
});
