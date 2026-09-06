import { describe, expect, it } from "vitest";
import { ApiError } from "./api/core";
import { errorMessage } from "./errors";

describe("errorMessage", () => {
  it("includes the HTTP status for API errors", () => {
    expect(errorMessage(new ApiError("Vorgang nicht gefunden", 404))).toBe(
      "Vorgang nicht gefunden (HTTP 404)",
    );
  });

  it("omits the status for network failures (status 0)", () => {
    expect(errorMessage(new ApiError("Netzwerkfehler", 0))).toBe("Netzwerkfehler");
  });

  it("uses the message of plain errors and strings", () => {
    expect(errorMessage(new Error(" kaputt "))).toBe("kaputt");
    expect(errorMessage("als Text")).toBe("als Text");
  });

  it("falls back for unknown values and empty messages", () => {
    expect(errorMessage(undefined)).toBe("Unbekannter Fehler.");
    expect(errorMessage(new Error(""), "Eigener Fallback")).toBe("Eigener Fallback");
    expect(errorMessage({ weird: true })).toBe("Unbekannter Fehler.");
  });

  it("truncates very long details", () => {
    const long = "x".repeat(1000);
    const out = errorMessage(new Error(long));
    expect(out.length).toBe(300);
    expect(out.endsWith("…")).toBe(true);
  });
});
