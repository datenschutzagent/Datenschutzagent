import { Link } from "react-router";
import { useState, useEffect } from "react";
import { AppHeaderUser } from "../components/app-header-user";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { RadioGroup, RadioGroupItem } from "../components/ui/radio-group";
import { usePreferences } from "../contexts/PreferencesContext";
import {
  updateCurrentUser,
  isAdmin,
  type UserTheme,
  type UserUILanguage,
  type UserUpdateInput,
} from "../lib/api";
const themeLabels: Record<UserTheme, string> = {
  light: "Hell",
  dark: "Dunkel",
  system: "System",
};

const languageLabels: Record<UserUILanguage, string> = {
  de: "Deutsch",
  en: "English",
};

export function ProfilePage() {
  const { user, loading, error, refreshUser } = usePreferences();
  const [displayName, setDisplayName] = useState("");
  const [theme, setTheme] = useState<UserTheme>("system");
  const [language, setLanguage] = useState<UserUILanguage>("de");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    if (user) {
      setDisplayName(user.display_name ?? "");
      const prefs = user.preferences && typeof user.preferences === "object" ? user.preferences : {};
      setTheme((prefs.theme as UserTheme) ?? "system");
      setLanguage((prefs.language as UserUILanguage) ?? "de");
    }
  }, [user]);

  const handleSave = async () => {
    setSaving(true);
    setSaveError(null);
    try {
      const body: UserUpdateInput = {
        display_name: displayName,
        preferences: { theme, language },
      };
      await updateCurrentUser(body);
      await refreshUser();
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setSaveError(msg);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950">
      <header className="bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">Datenschutz-Agent</h1>
              <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">Universität • Forschungsvorhaben</p>
            </div>
            <nav className="flex items-center gap-6">
              <Link to="/" className="text-sm font-medium text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100">
                Vorgänge
              </Link>
              <Link to="/playbooks" className="text-sm font-medium text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100">
                Playbooks
              </Link>
              <Link to="/profile" className="text-sm font-medium text-blue-600 dark:text-blue-400">
                Mein Profil
              </Link>
              {user && isAdmin(user) && (
                <Link to="/admin" className="text-sm font-medium text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100">
                  Verwaltung
                </Link>
              )}
              <AppHeaderUser />
            </nav>
          </div>
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100 mb-6">Mein Profil</h2>

        {loading && !user && (
          <p className="text-slate-600 dark:text-slate-400">Profil wird geladen…</p>
        )}
        {error && (
          <p className="text-red-600 dark:text-red-400 mb-4">{error}</p>
        )}

        {user && (
          <Card className="dark:bg-slate-900 dark:border-slate-800">
            <CardHeader>
              <CardTitle className="dark:text-slate-100">Persönliche Einstellungen</CardTitle>
              <CardDescription className="dark:text-slate-400">
                Anzeigename und UI-Präferenzen (Theme und Sprache werden app-weit angewendet).
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-2">
                <Label htmlFor="display_name" className="dark:text-slate-300">Anzeigename</Label>
                <Input
                  id="display_name"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  className="dark:bg-slate-800 dark:border-slate-700 dark:text-slate-100"
                />
              </div>

              <div className="space-y-3">
                <Label className="dark:text-slate-300">Theme</Label>
                <RadioGroup
                  value={theme}
                  onValueChange={(v) => setTheme(v as UserTheme)}
                  className="flex flex-col gap-2"
                >
                  {(["light", "dark", "system"] as const).map((t) => (
                    <div key={t} className="flex items-center space-x-2">
                      <RadioGroupItem value={t} id={`theme-${t}`} />
                      <Label htmlFor={`theme-${t}`} className="font-normal cursor-pointer dark:text-slate-300">
                        {themeLabels[t]}
                      </Label>
                    </div>
                  ))}
                </RadioGroup>
              </div>

              <div className="space-y-3">
                <Label className="dark:text-slate-300">Sprache</Label>
                <RadioGroup
                  value={language}
                  onValueChange={(v) => setLanguage(v as UserUILanguage)}
                  className="flex flex-col gap-2"
                >
                  {(["de", "en"] as const).map((l) => (
                    <div key={l} className="flex items-center space-x-2">
                      <RadioGroupItem value={l} id={`lang-${l}`} />
                      <Label htmlFor={`lang-${l}`} className="font-normal cursor-pointer dark:text-slate-300">
                        {languageLabels[l]}
                      </Label>
                    </div>
                  ))}
                </RadioGroup>
              </div>

              <div className="text-sm text-slate-500 dark:text-slate-400">
                Benachrichtigungen: in Kürze verfügbar.
              </div>

              {saveError && (
                <p className="text-red-600 dark:text-red-400 text-sm">{saveError}</p>
              )}

              <Button onClick={handleSave} disabled={saving}>
                {saving ? "Speichern…" : "Speichern"}
              </Button>
            </CardContent>
          </Card>
        )}
      </main>
    </div>
  );
}
