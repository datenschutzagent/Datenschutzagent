import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import {
  getAuthConfig,
  setAccessToken,
  getAccessToken,
  getCurrentUser,
  type AuthConfig,
  type ApiUser,
} from "../lib/api";
import { logger } from "../lib/logger";
import {
  clearStoredCodeVerifier,
  clearStoredToken,
  computeCodeChallenge,
  generateCodeVerifier,
  getStoredToken,
  setStoredCodeVerifier,
  setStoredToken,
} from "../lib/auth";

interface AuthContextValue {
  authConfig: AuthConfig | null;
  loading: boolean;
  error: string | null;
  isAuthenticated: boolean;
  user: ApiUser | null;
  login: () => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [authConfig, setAuthConfig] = useState<AuthConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [user, setUser] = useState<ApiUser | null>(null);

  const token = getAccessToken();
  const isAuthenticated = !!token;

  const refreshUser = useCallback(async () => {
    if (!getAccessToken()) return;
    try {
      const u = await getCurrentUser();
      setUser(u);
    } catch {
      setUser(null);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const config = await getAuthConfig();
        if (cancelled) return;
        setAuthConfig(config);
        const stored = getStoredToken();
        if (stored) {
          setAccessToken(stored);
        }
        if (stored || !config.oidc_enabled) {
          const u = await getCurrentUser();
          if (!cancelled) setUser(u);
        }
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "Failed to load auth config");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const onTokenSet = () => {
      refreshUser();
    };
    window.addEventListener("datenschutzagent:token-set", onTokenSet);
    return () => window.removeEventListener("datenschutzagent:token-set", onTokenSet);
  }, [refreshUser]);

  // React to 401 responses from the API: clear the session.
  // If OIDC is enabled, redirect to the IdP logout endpoint.
  // If OIDC is disabled, simply clear the token so the user is prompted again.
  useEffect(() => {
    const handleUnauthorized = () => {
      logger.warn("Received 401 – clearing session");
      setAccessToken(null);
      clearStoredToken();
      clearStoredCodeVerifier();
      setUser(null);
      const config = authConfig;
      if (config?.oidc_enabled && config?.end_session_endpoint) {
        const redirectUri = encodeURIComponent(window.location.origin + "/");
        window.location.href = `${config.end_session_endpoint}?post_logout_redirect_uri=${redirectUri}`;
      }
    };
    window.addEventListener("datenschutzagent:unauthorized", handleUnauthorized);
    return () => window.removeEventListener("datenschutzagent:unauthorized", handleUnauthorized);
  }, [authConfig]);

  const login = useCallback(async () => {
    const config = authConfig ?? (await getAuthConfig());
    if (!config.oidc_enabled || !config.authorization_endpoint || !config.oidc_client_id) {
      setError("OIDC not configured");
      return;
    }
    const verifier = generateCodeVerifier();
    const challenge = await computeCodeChallenge(verifier);
    setStoredCodeVerifier(verifier);
    const redirectUri = `${window.location.origin}/auth/callback`;
    const scope = (config.oidc_scopes ?? ["openid", "profile", "email"]).join(" ");
    const state = crypto.randomUUID();
    sessionStorage.setItem("datenschutzagent_oauth_state", state);
    const params = new URLSearchParams({
      response_type: "code",
      client_id: config.oidc_client_id,
      redirect_uri: redirectUri,
      scope,
      state,
      code_challenge: challenge,
      code_challenge_method: "S256",
    });
    window.location.href = `${config.authorization_endpoint}?${params.toString()}`;
  }, [authConfig]);

  const logout = useCallback(() => {
    setAccessToken(null);
    clearStoredToken();
    clearStoredCodeVerifier();
    setUser(null);
    const config = authConfig;
    if (config?.oidc_enabled && config?.end_session_endpoint) {
      const redirectUri = encodeURIComponent(window.location.origin + "/");
      window.location.href = `${config.end_session_endpoint}?post_logout_redirect_uri=${redirectUri}`;
    }
  }, [authConfig]);

  const value = useMemo<AuthContextValue>(
    () => ({
      authConfig,
      loading,
      error,
      isAuthenticated,
      user,
      login,
      logout,
      refreshUser,
    }),
    [authConfig, loading, error, isAuthenticated, user, login, logout, refreshUser]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

export function useAuthOptional(): AuthContextValue | null {
  return useContext(AuthContext);
}
