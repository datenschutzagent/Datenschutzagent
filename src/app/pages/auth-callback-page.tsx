import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router";
import { getAuthConfig, setAccessToken } from "../lib/api";
import { startSessionCookie } from "../lib/api/admin";
import { setSessionCookieMode } from "../lib/api/core";
import { getStoredCodeVerifier, clearStoredCodeVerifier, setStoredToken } from "../lib/auth";

const API_BASE = (import.meta as unknown as { env?: { VITE_API_URL?: string } }).env?.VITE_API_URL ?? "http://localhost:8002";

/**
 * Exchange authorization code for tokens via the backend (proxy) or directly.
 * Many IdPs require token_endpoint to be called from a confidential client.
 * We call the backend to exchange the code so client_secret is not exposed.
 * If the backend does not expose an exchange endpoint, we could exchange in the
 * frontend (only safe for public clients with PKCE). Here we try backend first.
 */
async function exchangeCodeViaBackend(
  code: string,
  redirectUri: string,
  codeVerifier: string
): Promise<{ access_token: string }> {
  const res = await fetch(`${API_BASE}/api/v1/auth/token`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code, redirect_uri: redirectUri, code_verifier: codeVerifier }),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || "Token exchange failed");
  }
  return res.json() as Promise<{ access_token: string }>;
}

/**
 * Exchange authorization code for tokens directly with the IdP (public client with PKCE).
 */
async function exchangeCodeDirect(
  tokenEndpoint: string,
  code: string,
  redirectUri: string,
  clientId: string,
  codeVerifier: string
): Promise<{ access_token: string }> {
  const body = new URLSearchParams({
    grant_type: "authorization_code",
    code,
    redirect_uri: redirectUri,
    client_id: clientId,
    code_verifier: codeVerifier,
  });
  const res = await fetch(tokenEndpoint, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: body.toString(),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || "Token exchange failed");
  }
  const data = (await res.json()) as { access_token?: string };
  if (!data.access_token) throw new Error("No access_token in response");
  return { access_token: data.access_token };
}

export function AuthCallbackPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [status, setStatus] = useState<"pending" | "ok" | "error">("pending");
  const [message, setMessage] = useState<string>("");

  useEffect(() => {
    let cancelled = false;
    const code = searchParams.get("code");
    const state = searchParams.get("state");
    const errorParam = searchParams.get("error");

    if (errorParam) {
      setMessage(searchParams.get("error_description") || errorParam);
      setStatus("error");
      return;
    }

    const storedState = sessionStorage.getItem("datenschutzagent_oauth_state");
    sessionStorage.removeItem("datenschutzagent_oauth_state");
    if (!code || state !== storedState) {
      setMessage("Invalid or missing state/code");
      setStatus("error");
      return;
    }

    const verifier = getStoredCodeVerifier();
    clearStoredCodeVerifier();
    if (!verifier) {
      setMessage("Missing code verifier");
      setStatus("error");
      return;
    }

    const redirectUri = `${window.location.origin}/auth/callback`;

    (async () => {
      try {
        const config = await getAuthConfig();
        // Session-cookie flow: backend performs the exchange and sets the
        // HttpOnly session cookie. No access token ever touches JS.
        if (config.auth_session_cookie_enabled) {
          setSessionCookieMode(true);
          await startSessionCookie({ code, redirect_uri: redirectUri, code_verifier: verifier });
          if (cancelled) return;
          window.dispatchEvent(new CustomEvent("datenschutzagent:token-set"));
          setStatus("ok");
          navigate("/", { replace: true });
          return;
        }
        if (!config.token_endpoint || !config.oidc_client_id) {
          setMessage("OIDC token endpoint not configured");
          setStatus("error");
          return;
        }
        let accessToken: string;
        try {
          const data = await exchangeCodeViaBackend(code, redirectUri, verifier);
          accessToken = data.access_token;
        } catch {
          accessToken = (
            await exchangeCodeDirect(
              config.token_endpoint,
              code,
              redirectUri,
              config.oidc_client_id,
              verifier
            )
          ).access_token;
        }
        if (cancelled) return;
        setStoredToken(accessToken);
        setAccessToken(accessToken);
        window.dispatchEvent(new CustomEvent("datenschutzagent:token-set"));
        setStatus("ok");
        navigate("/", { replace: true });
      } catch (e) {
        if (!cancelled) {
          setMessage(e instanceof Error ? e.message : "Login failed");
          setStatus("error");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [searchParams, navigate]);

  if (status === "pending") {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-muted-foreground">Anmeldung wird abgeschlossen…</p>
      </div>
    );
  }
  if (status === "error") {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4">
        <p className="text-destructive">{message}</p>
        <a href="/" className="text-primary underline">
          Zur Startseite
        </a>
      </div>
    );
  }
  return null;
}
