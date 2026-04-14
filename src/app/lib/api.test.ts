import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { parseErrorResponse, ApiError } from "./api";

// ── parseErrorResponse ────────────────────────────────────────────────────────

describe("parseErrorResponse", () => {
  it("returns JSON detail when response has JSON body with detail", async () => {
    const res = new Response(JSON.stringify({ detail: "Not found" }), {
      status: 404,
      headers: { "Content-Type": "application/json" },
    });
    const msg = await parseErrorResponse(res);
    expect(msg).toBe("Not found");
  });

  it("returns full text when response is plain text", async () => {
    const res = new Response("Server error", { status: 500 });
    const msg = await parseErrorResponse(res);
    expect(msg).toBe("Server error");
  });

  it("returns text when JSON parse fails", async () => {
    const res = new Response("not json {", { status: 400 });
    const msg = await parseErrorResponse(res);
    expect(msg).toBe("not json {");
  });
});

// ── ApiError ──────────────────────────────────────────────────────────────────

describe("ApiError", () => {
  it("is an instance of Error", () => {
    const err = new ApiError("Nicht gefunden", 404);
    expect(err).toBeInstanceOf(Error);
  });

  it("carries the HTTP status code", () => {
    const err = new ApiError("Nicht autorisiert", 401);
    expect(err.status).toBe(401);
  });

  it("carries the error message", () => {
    const err = new ApiError("Verboten", 403);
    expect(err.message).toBe("Verboten");
  });

  it("has name ApiError", () => {
    const err = new ApiError("Fehler", 500);
    expect(err.name).toBe("ApiError");
  });

  it("can be distinguished from a plain Error by instanceof check", () => {
    const apiErr = new ApiError("API", 422);
    const plainErr = new Error("plain");
    expect(apiErr instanceof ApiError).toBe(true);
    expect(plainErr instanceof ApiError).toBe(false);
  });
});

// ── 401 unauthorized event ────────────────────────────────────────────────────

describe("request – 401 dispatches unauthorized event", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    // Stub fetch so we control the response without a real server.
    global.fetch = vi.fn();
  });

  afterEach(() => {
    global.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it("dispatches datenschutzagent:unauthorized on 401 response", async () => {
    vi.mocked(global.fetch).mockResolvedValue(
      new Response(JSON.stringify({ detail: "Unauthorized" }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      })
    );

    const eventSpy = vi.fn();
    window.addEventListener("datenschutzagent:unauthorized", eventSpy);

    // We import dynamically so the module-level fetch stub is picked up.
    const { getCurrentUser } = await import("./api");

    await expect(getCurrentUser()).rejects.toBeInstanceOf(ApiError);
    expect(eventSpy).toHaveBeenCalledTimes(1);

    window.removeEventListener("datenschutzagent:unauthorized", eventSpy);
  });

  it("does NOT dispatch unauthorized event on 403 response", async () => {
    vi.mocked(global.fetch).mockResolvedValue(
      new Response(JSON.stringify({ detail: "Forbidden" }), {
        status: 403,
        headers: { "Content-Type": "application/json" },
      })
    );

    const eventSpy = vi.fn();
    window.addEventListener("datenschutzagent:unauthorized", eventSpy);

    const { getCurrentUser } = await import("./api");

    await expect(getCurrentUser()).rejects.toBeInstanceOf(ApiError);
    expect(eventSpy).not.toHaveBeenCalled();

    window.removeEventListener("datenschutzagent:unauthorized", eventSpy);
  });

  it("throws ApiError with correct status on 500", async () => {
    vi.mocked(global.fetch).mockResolvedValue(
      new Response("Internal Server Error", { status: 500 })
    );

    const { getCurrentUser } = await import("./api");

    await expect(getCurrentUser()).rejects.toMatchObject({
      status: 500,
    });
  });

  it("throws ApiError with status 0 on network failure", async () => {
    vi.mocked(global.fetch).mockRejectedValue(new TypeError("Failed to fetch"));

    const { getCurrentUser } = await import("./api");

    const err = await getCurrentUser().catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).status).toBe(0);
  });
});
