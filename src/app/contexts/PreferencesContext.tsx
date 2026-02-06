/**
 * Preferences context: loads current user and applies theme + language from profile app-wide.
 * Theme and language are applied to the document and updated when the user saves on the profile page.
 */
import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import {
  type ApiUser,
  type UserTheme,
  type UserUILanguage,
  getCurrentUser,
} from "../lib/api";

type PreferencesContextValue = {
  user: ApiUser | null;
  loading: boolean;
  error: string | null;
  refreshUser: () => Promise<void>;
  theme: UserTheme;
  language: UserUILanguage;
};

const defaults = {
  theme: "system" as UserTheme,
  language: "de" as UserUILanguage,
};

function applyTheme(theme: UserTheme) {
  const root = document.documentElement;
  const isDark =
    theme === "dark" ||
    (theme === "system" && typeof window !== "undefined" && window.matchMedia("(prefers-color-scheme: dark)").matches);
  if (isDark) {
    root.classList.add("dark");
  } else {
    root.classList.remove("dark");
  }
}

function applyLanguage(language: UserUILanguage) {
  document.documentElement.lang = language;
}

const PreferencesContext = createContext<PreferencesContextValue | null>(null);

export function PreferencesProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<ApiUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const theme = useMemo((): UserTheme => {
    const t = user?.preferences && typeof user.preferences === "object" && "theme" in user.preferences
      ? (user.preferences.theme as UserTheme)
      : defaults.theme;
    return t === "light" || t === "dark" || t === "system" ? t : "system";
  }, [user?.preferences]);

  const language = useMemo((): UserUILanguage => {
    const l = user?.preferences && typeof user.preferences === "object" && "language" in user.preferences
      ? (user.preferences.language as UserUILanguage)
      : defaults.language;
    return l === "de" || l === "en" ? l : "de";
  }, [user?.preferences]);

  const loadUser = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const u = await getCurrentUser();
      setUser(u);
      const prefs = u.preferences && typeof u.preferences === "object" ? u.preferences : {};
      const t = (prefs.theme as UserTheme) ?? defaults.theme;
      const l = (prefs.language as UserUILanguage) ?? defaults.language;
      applyTheme(t === "light" || t === "dark" || t === "system" ? t : "system");
      applyLanguage(l === "de" || l === "en" ? l : "de");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      applyTheme(defaults.theme);
      applyLanguage(defaults.language);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadUser();
  }, [loadUser]);

  useEffect(() => {
    applyTheme(theme);
    applyLanguage(language);
  }, [theme, language]);

  useEffect(() => {
    if (theme !== "system") return;
    const m = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = () => applyTheme("system");
    m.addEventListener("change", handler);
    return () => m.removeEventListener("change", handler);
  }, [theme]);

  const refreshUser = useCallback(async () => {
    await loadUser();
  }, [loadUser]);

  const value = useMemo<PreferencesContextValue>(
    () => ({
      user,
      loading,
      error,
      refreshUser,
      theme,
      language,
    }),
    [user, loading, error, refreshUser, theme, language]
  );

  return (
    <PreferencesContext.Provider value={value}>
      {children}
    </PreferencesContext.Provider>
  );
}

export function usePreferences(): PreferencesContextValue {
  const ctx = useContext(PreferencesContext);
  if (!ctx) {
    throw new Error("usePreferences must be used within PreferencesProvider");
  }
  return ctx;
}
