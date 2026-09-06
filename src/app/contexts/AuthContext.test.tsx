import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import type { ApiUser, AuthConfig } from "../lib/api";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("../lib/api", () => {
  let token: string | null = null;
  return {
    getAuthConfig: vi.fn(),
    getCurrentUser: vi.fn(),
    setAccessToken: vi.fn((t: string | null) => {
      token = t;
    }),
    getAccessToken: vi.fn(() => token),
  };
});

vi.mock("../lib/api/admin", () => ({
  endSessionCookie: vi.fn(),
}));

vi.mock("../lib/logger", () => ({
  logger: { debug: vi.fn(), info: vi.fn(), warn: vi.fn(), error: vi.fn() },
}));

vi.mock("../lib/auth", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/auth")>();
  return {
    ...actual,
    generateCodeVerifier: vi.fn(() => "test-verifier"),
    computeCodeChallenge: vi.fn(async () => "test-challenge"),
  };
});

import { getAuthConfig, getCurrentUser, setAccessToken, getAccessToken } from "../lib/api";
import { endSessionCookie } from "../lib/api/admin";
import { setSessionCookieMode, isSessionCookieMode } from "../lib/api/core";
import { logger } from "../lib/logger";
import { getStoredCodeVerifier, setStoredToken } from "../lib/auth";
import { AuthProvider, useAuth, useAuthOptional } from "./AuthContext";

const mockGetAuthConfig = vi.mocked(getAuthConfig);
const mockGetCurrentUser = vi.mocked(getCurrentUser);
const mockSetAccessToken = vi.mocked(setAccessToken);
const mockEndSessionCookie = vi.mocked(endSessionCookie);
const mockLogger = vi.mocked(logger);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const ORIGIN = "http://localhost:3002";

const baseConfig: AuthConfig = {
  oidc_enabled: false,
  oidc_issuer_url: "",
  oidc_client_id: "",
  oidc_scopes: [],
};

const oidcConfig: AuthConfig = {
  oidc_enabled: true,
  oidc_issuer_url: "https://idp.example.org",
  oidc_client_id: "client-123",
  oidc_scopes: ["openid", "email"],
  authorization_endpoint: "https://idp.example.org/authorize",
  token_endpoint: "https://idp.example.org/token",
  end_session_endpoint: "https://idp.example.org/logout",
};

const fakeUser: ApiUser = {
  id: "u1",
  display_name: "Erika Muster",
  email: "erika@example.org",
  role: "admin",
  preferences: {},
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

function wrapper({ children }: { children: ReactNode }) {
  return <AuthProvider>{children}</AuthProvider>;
}

function renderAuth() {
  return renderHook(() => useAuth(), { wrapper });
}

/** Replace window.location with a plain object so href assignments are observable. */
function stubLocation() {
  const fake = { origin: ORIGIN, href: `${ORIGIN}/` };
  Object.defineProperty(window, "location", { configurable: true, writable: true, value: fake });
  return fake;
}

const originalLocation = window.location;

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

beforeEach(() => {
  sessionStorage.clear();
  setAccessToken(null);
  setSessionCookieMode(false);
  // Clear after the reset above so the reset call itself is not counted.
  vi.clearAllMocks();
  mockGetAuthConfig.mockResolvedValue(baseConfig);
  mockGetCurrentUser.mockResolvedValue(fakeUser);
});

afterEach(() => {
  Object.defineProperty(window, "location", { configurable: true, writable: true, value: originalLocation });
});

describe("useAuth / useAuthOptional", () => {
  it("useAuth throws when used outside AuthProvider", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => renderHook(() => useAuth())).toThrow("useAuth must be used within AuthProvider");
    spy.mockRestore();
  });

  it("useAuthOptional returns null outside AuthProvider", () => {
    const { result } = renderHook(() => useAuthOptional());
    expect(result.current).toBeNull();
  });

  it("useAuthOptional returns the context value inside AuthProvider", async () => {
    const { result } = renderHook(() => useAuthOptional(), { wrapper });
    await waitFor(() => expect(result.current?.loading).toBe(false));
    expect(result.current?.authConfig).toEqual(baseConfig);
  });
});

describe("AuthProvider – initial load", () => {
  it("starts in loading state and resolves to authenticated when OIDC is disabled", async () => {
    const { result } = renderAuth();

    expect(result.current.loading).toBe(true);
    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.user).toBeNull();

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(mockGetAuthConfig).toHaveBeenCalledTimes(1);
    expect(mockGetCurrentUser).toHaveBeenCalledTimes(1);
    expect(result.current.authConfig).toEqual(baseConfig);
    expect(result.current.user).toEqual(fakeUser);
    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.error).toBeNull();
    expect(isSessionCookieMode()).toBe(false);
  });

  it("stays unauthenticated when OIDC is enabled and no token is stored", async () => {
    mockGetAuthConfig.mockResolvedValue(oidcConfig);
    const { result } = renderAuth();

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(mockGetCurrentUser).not.toHaveBeenCalled();
    expect(mockSetAccessToken).not.toHaveBeenCalled();
    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.user).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it("restores a stored token and loads the user when OIDC is enabled", async () => {
    mockGetAuthConfig.mockResolvedValue(oidcConfig);
    setStoredToken("stored-token");
    const { result } = renderAuth();

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(mockSetAccessToken).toHaveBeenCalledWith("stored-token");
    expect(getAccessToken()).toBe("stored-token");
    expect(mockGetCurrentUser).toHaveBeenCalledTimes(1);
    expect(result.current.user).toEqual(fakeUser);
    expect(result.current.isAuthenticated).toBe(true);
  });

  it("switches to session-cookie mode and ignores stored tokens in the cookie flow", async () => {
    mockGetAuthConfig.mockResolvedValue({ ...oidcConfig, auth_session_cookie_enabled: true });
    setStoredToken("should-be-ignored");
    const { result } = renderAuth();

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(isSessionCookieMode()).toBe(true);
    expect(mockSetAccessToken).not.toHaveBeenCalled();
    expect(mockGetCurrentUser).toHaveBeenCalledTimes(1);
    expect(result.current.user).toEqual(fakeUser);
    expect(result.current.isAuthenticated).toBe(true);
  });

  it("stays signed out without error when the cookie is missing on first load (cookie flow)", async () => {
    mockGetAuthConfig.mockResolvedValue({ ...oidcConfig, auth_session_cookie_enabled: true });
    mockGetCurrentUser.mockRejectedValue(new Error("401"));
    const { result } = renderAuth();

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error).toBeNull();
    expect(result.current.user).toBeNull();
    expect(result.current.isAuthenticated).toBe(false);
  });

  it("reports an error when the current user cannot be loaded outside the cookie flow", async () => {
    mockGetCurrentUser.mockRejectedValue(new Error("boom"));
    const { result } = renderAuth();

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error).toBe("Failed to load current user");
    expect(result.current.user).toBeNull();
  });

  it("exposes the auth-config error message when getAuthConfig rejects with an Error", async () => {
    mockGetAuthConfig.mockRejectedValue(new Error("config down"));
    const { result } = renderAuth();

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error).toBe("config down");
    expect(result.current.authConfig).toBeNull();
    expect(mockGetCurrentUser).not.toHaveBeenCalled();
  });

  it("falls back to a generic message when getAuthConfig rejects with a non-Error", async () => {
    mockGetAuthConfig.mockRejectedValue("nope");
    const { result } = renderAuth();

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error).toBe("Failed to load auth config");
  });

  it("ignores results that arrive after unmount", async () => {
    let resolveConfig: (c: AuthConfig) => void = () => {};
    mockGetAuthConfig.mockReturnValue(
      new Promise<AuthConfig>((resolve) => {
        resolveConfig = resolve;
      }),
    );
    const { result, unmount } = renderAuth();
    expect(result.current.loading).toBe(true);

    unmount();
    await act(async () => {
      resolveConfig(baseConfig);
    });

    // No user fetch happens for a cancelled effect.
    expect(mockGetCurrentUser).not.toHaveBeenCalled();
  });
});

describe("login()", () => {
  it("redirects to the authorization endpoint with PKCE parameters", async () => {
    const loc = stubLocation();
    mockGetAuthConfig.mockResolvedValue(oidcConfig);
    const { result } = renderAuth();
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.login();
    });

    const url = new URL(loc.href);
    expect(`${url.origin}${url.pathname}`).toBe("https://idp.example.org/authorize");
    expect(url.searchParams.get("response_type")).toBe("code");
    expect(url.searchParams.get("client_id")).toBe("client-123");
    expect(url.searchParams.get("redirect_uri")).toBe(`${ORIGIN}/auth/callback`);
    expect(url.searchParams.get("scope")).toBe("openid email");
    expect(url.searchParams.get("code_challenge")).toBe("test-challenge");
    expect(url.searchParams.get("code_challenge_method")).toBe("S256");

    const state = url.searchParams.get("state");
    expect(state).toBeTruthy();
    expect(sessionStorage.getItem("datenschutzagent_oauth_state")).toBe(state);
    expect(getStoredCodeVerifier()).toBe("test-verifier");
    expect(result.current.error).toBeNull();
  });

  it("uses default scopes when the config provides none", async () => {
    const loc = stubLocation();
    mockGetAuthConfig.mockResolvedValue({ ...oidcConfig, oidc_scopes: undefined as unknown as string[] });
    const { result } = renderAuth();
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.login();
    });

    expect(new URL(loc.href).searchParams.get("scope")).toBe("openid profile email");
  });

  it("sets an error and does not redirect when OIDC is not configured", async () => {
    const loc = stubLocation();
    const { result } = renderAuth();
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.login();
    });

    expect(result.current.error).toBe("OIDC not configured");
    expect(loc.href).toBe(`${ORIGIN}/`);
    expect(getStoredCodeVerifier()).toBeNull();
  });

  it("re-fetches the auth config when none was loaded yet", async () => {
    const loc = stubLocation();
    mockGetAuthConfig.mockRejectedValueOnce(new Error("first load failed"));
    const { result } = renderAuth();
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.authConfig).toBeNull();

    mockGetAuthConfig.mockResolvedValue(oidcConfig);
    await act(async () => {
      await result.current.login();
    });

    expect(mockGetAuthConfig).toHaveBeenCalledTimes(2);
    expect(loc.href.startsWith("https://idp.example.org/authorize?")).toBe(true);
  });
});

describe("logout()", () => {
  it("clears token, verifier and user; redirects to the IdP end-session endpoint", async () => {
    const loc = stubLocation();
    mockGetAuthConfig.mockResolvedValue(oidcConfig);
    setStoredToken("stored-token");
    sessionStorage.setItem("datenschutzagent_pkce_verifier", "v");
    const { result } = renderAuth();
    await waitFor(() => expect(result.current.user).toEqual(fakeUser));

    await act(async () => {
      await result.current.logout();
    });

    expect(mockSetAccessToken).toHaveBeenLastCalledWith(null);
    expect(getAccessToken()).toBeNull();
    expect(sessionStorage.getItem("datenschutzagent_access_token")).toBeNull();
    expect(getStoredCodeVerifier()).toBeNull();
    expect(result.current.user).toBeNull();
    expect(result.current.isAuthenticated).toBe(false);
    expect(mockEndSessionCookie).not.toHaveBeenCalled();
    expect(loc.href).toBe(
      `https://idp.example.org/logout?post_logout_redirect_uri=${encodeURIComponent(`${ORIGIN}/`)}`,
    );
  });

  it("does not redirect when OIDC is disabled", async () => {
    const loc = stubLocation();
    const { result } = renderAuth();
    await waitFor(() => expect(result.current.user).toEqual(fakeUser));

    await act(async () => {
      await result.current.logout();
    });

    expect(result.current.user).toBeNull();
    expect(loc.href).toBe(`${ORIGIN}/`);
  });

  it("ends the backend session in cookie mode", async () => {
    stubLocation();
    mockGetAuthConfig.mockResolvedValue({ ...baseConfig, auth_session_cookie_enabled: true });
    mockEndSessionCookie.mockResolvedValue(undefined);
    const { result } = renderAuth();
    await waitFor(() => expect(result.current.user).toEqual(fakeUser));

    await act(async () => {
      await result.current.logout();
    });

    expect(mockEndSessionCookie).toHaveBeenCalledTimes(1);
    expect(result.current.user).toBeNull();
  });

  it("logs a warning but still signs out when the backend logout fails", async () => {
    stubLocation();
    mockGetAuthConfig.mockResolvedValue({ ...baseConfig, auth_session_cookie_enabled: true });
    mockEndSessionCookie.mockRejectedValue(new Error("redis down"));
    const { result } = renderAuth();
    await waitFor(() => expect(result.current.user).toEqual(fakeUser));

    await act(async () => {
      await result.current.logout();
    });

    expect(mockLogger.warn).toHaveBeenCalledWith("Backend logout failed", { error: "redis down" });
    expect(result.current.user).toBeNull();
  });
});

describe("refreshUser()", () => {
  it("does nothing without a token outside cookie mode", async () => {
    mockGetAuthConfig.mockResolvedValue(oidcConfig);
    const { result } = renderAuth();
    await waitFor(() => expect(result.current.loading).toBe(false));
    mockGetCurrentUser.mockClear();

    await act(async () => {
      await result.current.refreshUser();
    });

    expect(mockGetCurrentUser).not.toHaveBeenCalled();
    expect(result.current.user).toBeNull();
  });

  it("loads the user when a token is present", async () => {
    mockGetAuthConfig.mockResolvedValue(oidcConfig);
    const { result } = renderAuth();
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.user).toBeNull();

    setAccessToken("fresh-token");
    await act(async () => {
      await result.current.refreshUser();
    });

    expect(mockGetCurrentUser).toHaveBeenCalledTimes(1);
    expect(result.current.user).toEqual(fakeUser);
  });

  it("warns and treats the user as signed out when the request fails (no throw)", async () => {
    const { result } = renderAuth();
    await waitFor(() => expect(result.current.user).toEqual(fakeUser));

    setAccessToken("token");
    const failure = new Error("expired");
    mockGetCurrentUser.mockRejectedValueOnce(failure);

    await act(async () => {
      await expect(result.current.refreshUser()).resolves.toBeUndefined();
    });

    expect(mockLogger.warn).toHaveBeenCalledWith(
      "Current user could not be refreshed; treating as signed out",
      {},
      failure,
    );
    expect(result.current.user).toBeNull();
  });

  it("is triggered by the datenschutzagent:token-set event", async () => {
    mockGetAuthConfig.mockResolvedValue(oidcConfig);
    const { result } = renderAuth();
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.user).toBeNull();

    setAccessToken("token-from-callback");
    await act(async () => {
      window.dispatchEvent(new CustomEvent("datenschutzagent:token-set"));
    });

    await waitFor(() => expect(result.current.user).toEqual(fakeUser));
  });
});

describe("401 handling (datenschutzagent:unauthorized)", () => {
  it("clears the session and redirects to the end-session endpoint when OIDC is enabled", async () => {
    const loc = stubLocation();
    mockGetAuthConfig.mockResolvedValue(oidcConfig);
    setStoredToken("stored-token");
    const { result } = renderAuth();
    await waitFor(() => expect(result.current.user).toEqual(fakeUser));

    await act(async () => {
      window.dispatchEvent(new CustomEvent("datenschutzagent:unauthorized"));
    });

    expect(mockLogger.warn).toHaveBeenCalledWith("Received 401 – clearing session");
    expect(getAccessToken()).toBeNull();
    expect(sessionStorage.getItem("datenschutzagent_access_token")).toBeNull();
    expect(result.current.user).toBeNull();
    expect(loc.href.startsWith("https://idp.example.org/logout?")).toBe(true);
  });

  it("only clears the session when OIDC is disabled", async () => {
    const loc = stubLocation();
    const { result } = renderAuth();
    await waitFor(() => expect(result.current.user).toEqual(fakeUser));

    await act(async () => {
      window.dispatchEvent(new CustomEvent("datenschutzagent:unauthorized"));
    });

    expect(result.current.user).toBeNull();
    expect(result.current.isAuthenticated).toBe(false);
    expect(loc.href).toBe(`${ORIGIN}/`);
  });
});
