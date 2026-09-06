import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { makeTestQueryClient } from "../../test-utils";

vi.mock("../api", () => ({
  listTOMs: vi.fn(),
  getTOMStats: vi.fn(),
  createTOM: vi.fn(),
  updateTOM: vi.fn(),
  deleteTOM: vi.fn(),
  listTOMAttachments: vi.fn(),
  uploadTOMAttachment: vi.fn(),
  deleteTOMAttachment: vi.fn(),
}));

import { listTOMs, createTOM, listTOMAttachments, uploadTOMAttachment } from "../api";
import {
  tomKeys,
  useTOMs,
  useTOMAttachments,
  useCreateTOM,
  useUploadTOMAttachment,
} from "./tomQueries";

const mockList = vi.mocked(listTOMs);
const mockCreate = vi.mocked(createTOM);
const mockAttachments = vi.mocked(listTOMAttachments);
const mockUpload = vi.mocked(uploadTOMAttachment);

function makeWrapper(client?: QueryClient) {
  const qc = client ?? makeTestQueryClient();
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(QueryClientProvider, { client: qc }, children);
  };
}

describe("tomKeys", () => {
  it("builds hierarchical keys so lists() covers every filter", () => {
    expect(tomKeys.list()).toEqual(["tom", "list", {}]);
    expect(tomKeys.list({ category: "encryption" })).toEqual(["tom", "list", { category: "encryption" }]);
    expect(tomKeys.lists()).toEqual(["tom", "list"]);
    expect(tomKeys.stats()).toEqual(["tom", "stats"]);
    expect(tomKeys.attachments("t1")).toEqual(["tom", "attachments", "t1"]);
  });
});

describe("useTOMs", () => {
  beforeEach(() => vi.clearAllMocks());

  it("passes the filter through to listTOMs", async () => {
    mockList.mockResolvedValue({ items: [], total: 0 });
    const { result } = renderHook(
      () => useTOMs({ category: "encryption", implementationStatus: "planned" }),
      { wrapper: makeWrapper() },
    );
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockList).toHaveBeenCalledWith({ category: "encryption", implementationStatus: "planned" });
  });
});

describe("useTOMAttachments", () => {
  beforeEach(() => vi.clearAllMocks());

  it("does not fetch without a TOM id", () => {
    const { result } = renderHook(() => useTOMAttachments(null), { wrapper: makeWrapper() });
    expect(result.current.fetchStatus).toBe("idle");
    expect(mockAttachments).not.toHaveBeenCalled();
  });
});

describe("useCreateTOM", () => {
  beforeEach(() => vi.clearAllMocks());

  it("invalidates lists and stats on success", async () => {
    const client = makeTestQueryClient();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");
    mockCreate.mockResolvedValue({ id: "t1", title: "X" } as never);

    const { result } = renderHook(() => useCreateTOM(), { wrapper: makeWrapper(client) });
    result.current.mutate({ title: "X", category: "encryption" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockCreate).toHaveBeenCalledWith({ title: "X", category: "encryption" });
    expect(invalidateSpy).toHaveBeenCalledWith(expect.objectContaining({ queryKey: tomKeys.lists() }));
    expect(invalidateSpy).toHaveBeenCalledWith(expect.objectContaining({ queryKey: tomKeys.stats() }));
  });
});

describe("useUploadTOMAttachment", () => {
  beforeEach(() => vi.clearAllMocks());

  it("uploads for the given TOM and invalidates its attachments", async () => {
    const client = makeTestQueryClient();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");
    mockUpload.mockResolvedValue({ id: "a1", name: "f.pdf" } as never);
    const file = new File(["x"], "f.pdf", { type: "application/pdf" });

    const { result } = renderHook(() => useUploadTOMAttachment("t1"), { wrapper: makeWrapper(client) });
    result.current.mutate({ file, uploadedBy: "Test User" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockUpload).toHaveBeenCalledWith("t1", file, "Test User");
    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: tomKeys.attachments("t1") }),
    );
  });
});
