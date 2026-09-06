import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { makeTestQueryClient } from "../../test-utils";

vi.mock("../api", () => ({
  listDSRRequests: vi.fn(),
  createDSRRequest: vi.fn(),
  updateDSRRequest: vi.fn(),
  deleteDSRRequest: vi.fn(),
  generateDSRDraft: vi.fn(),
  getDSRActivity: vi.fn(),
}));

import { listDSRRequests, updateDSRRequest, getDSRActivity } from "../api";
import { dsrKeys, useDSRRequests, useDSRActivity, useUpdateDSRRequest } from "./dsrQueries";

const mockList = vi.mocked(listDSRRequests);
const mockUpdate = vi.mocked(updateDSRRequest);
const mockActivity = vi.mocked(getDSRActivity);

function makeWrapper(client?: QueryClient) {
  const qc = client ?? makeTestQueryClient();
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(QueryClientProvider, { client: qc }, children);
  };
}

describe("dsrKeys", () => {
  it("builds hierarchical keys so lists() covers every filter", () => {
    expect(dsrKeys.list()).toEqual(["dsr", "list", {}]);
    expect(dsrKeys.list({ status: "received" })).toEqual(["dsr", "list", { status: "received" }]);
    expect(dsrKeys.lists()).toEqual(["dsr", "list"]);
    expect(dsrKeys.activity("d1")).toEqual(["dsr", "activity", "d1"]);
  });
});

describe("useDSRRequests", () => {
  beforeEach(() => vi.clearAllMocks());

  it("passes the filter through to listDSRRequests", async () => {
    mockList.mockResolvedValue({ items: [], total: 0 });
    const { result } = renderHook(
      () => useDSRRequests({ status: "received", overdueOnly: true }),
      { wrapper: makeWrapper() },
    );
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockList).toHaveBeenCalledWith({ status: "received", overdueOnly: true });
  });
});

describe("useDSRActivity", () => {
  beforeEach(() => vi.clearAllMocks());

  it("does not fetch without an id", () => {
    const { result } = renderHook(() => useDSRActivity(null), { wrapper: makeWrapper() });
    expect(result.current.fetchStatus).toBe("idle");
    expect(mockActivity).not.toHaveBeenCalled();
  });
});

describe("useUpdateDSRRequest", () => {
  beforeEach(() => vi.clearAllMocks());

  it("invalidates the lists and the request's activity on success", async () => {
    const client = makeTestQueryClient();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");
    mockUpdate.mockResolvedValue({ id: "d1", status: "closed" } as never);

    const { result } = renderHook(() => useUpdateDSRRequest(), { wrapper: makeWrapper(client) });
    result.current.mutate({ id: "d1", body: { status: "closed" } });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockUpdate).toHaveBeenCalledWith("d1", { status: "closed" });
    expect(invalidateSpy).toHaveBeenCalledWith(expect.objectContaining({ queryKey: dsrKeys.lists() }));
    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: dsrKeys.activity("d1") }),
    );
  });
});
