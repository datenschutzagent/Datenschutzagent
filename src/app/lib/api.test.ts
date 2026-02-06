import { describe, it, expect } from "vitest";
import { parseErrorResponse } from "./api";

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
