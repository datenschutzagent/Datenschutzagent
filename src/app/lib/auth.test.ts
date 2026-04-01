import { describe, it, expect, beforeEach } from "vitest";
import {
  generateCodeVerifier,
  computeCodeChallenge,
  getStoredCodeVerifier,
  setStoredCodeVerifier,
  clearStoredCodeVerifier,
  getStoredToken,
  setStoredToken,
  clearStoredToken,
} from "./auth";

describe("PKCE helpers", () => {
  describe("generateCodeVerifier", () => {
    it("returns a non-empty string", () => {
      const verifier = generateCodeVerifier();
      expect(typeof verifier).toBe("string");
      expect(verifier.length).toBeGreaterThan(0);
    });

    it("returns a base64url-safe string (no +, /, =)", () => {
      const verifier = generateCodeVerifier();
      expect(verifier).not.toMatch(/[+/=]/);
    });

    it("returns a different value each time (probabilistic)", () => {
      const a = generateCodeVerifier();
      const b = generateCodeVerifier();
      expect(a).not.toBe(b);
    });

    it("returns a string of expected length (~43 chars for 32 bytes)", () => {
      const verifier = generateCodeVerifier();
      // 32 bytes base64url-encoded = 43 chars (without padding)
      expect(verifier.length).toBeGreaterThanOrEqual(40);
      expect(verifier.length).toBeLessThanOrEqual(50);
    });
  });

  describe("computeCodeChallenge", () => {
    it("returns a non-empty string", async () => {
      const verifier = generateCodeVerifier();
      const challenge = await computeCodeChallenge(verifier);
      expect(typeof challenge).toBe("string");
      expect(challenge.length).toBeGreaterThan(0);
    });

    it("returns a base64url-safe string (no +, /, =)", async () => {
      const verifier = generateCodeVerifier();
      const challenge = await computeCodeChallenge(verifier);
      expect(challenge).not.toMatch(/[+/=]/);
    });

    it("returns a consistent result for the same verifier", async () => {
      const verifier = "fixed-test-verifier-string-for-determinism";
      const c1 = await computeCodeChallenge(verifier);
      const c2 = await computeCodeChallenge(verifier);
      expect(c1).toBe(c2);
    });

    it("returns a different challenge for different verifiers", async () => {
      const c1 = await computeCodeChallenge("verifier-a");
      const c2 = await computeCodeChallenge("verifier-b");
      expect(c1).not.toBe(c2);
    });
  });
});

describe("sessionStorage wrappers — code verifier", () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  it("getStoredCodeVerifier returns null when not set", () => {
    expect(getStoredCodeVerifier()).toBeNull();
  });

  it("setStoredCodeVerifier stores the value", () => {
    setStoredCodeVerifier("my-verifier");
    expect(getStoredCodeVerifier()).toBe("my-verifier");
  });

  it("clearStoredCodeVerifier removes the value", () => {
    setStoredCodeVerifier("my-verifier");
    clearStoredCodeVerifier();
    expect(getStoredCodeVerifier()).toBeNull();
  });

  it("overwriting the verifier replaces the previous value", () => {
    setStoredCodeVerifier("first");
    setStoredCodeVerifier("second");
    expect(getStoredCodeVerifier()).toBe("second");
  });
});

describe("sessionStorage wrappers — access token", () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  it("getStoredToken returns null when not set", () => {
    expect(getStoredToken()).toBeNull();
  });

  it("setStoredToken stores the token", () => {
    setStoredToken("eyJhbGciOiJSUzI1NiJ9.test");
    expect(getStoredToken()).toBe("eyJhbGciOiJSUzI1NiJ9.test");
  });

  it("clearStoredToken removes the token", () => {
    setStoredToken("some-token");
    clearStoredToken();
    expect(getStoredToken()).toBeNull();
  });

  it("token and verifier are stored independently", () => {
    setStoredToken("my-token");
    setStoredCodeVerifier("my-verifier");
    clearStoredToken();
    expect(getStoredToken()).toBeNull();
    expect(getStoredCodeVerifier()).toBe("my-verifier");
  });
});
