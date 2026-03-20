import { useState, useEffect } from "react";
import { AppLayout } from "../components/app-layout";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { RadioGroup, RadioGroupItem } from "../components/ui/radio-group";
import { usePreferences } from "../contexts/PreferencesContext";
import { toast } from "sonner";
import {
  updateCurrentUser,
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
      toast.success("Profil gespeichert");
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setSaveError(msg);
    } finally {
      setSaving(false);
    }
  };

  return (
    <AppLayout maxWidth="max-w-2xl">
      <h2 className="text-xl font-semibold text-foreground mb-6">Mein Profil</h2>

      {loading && !user && (
        <p className="text-muted-foreground">Profil wird geladen…</p>
      )}
      {error && (
        <p className="text-red-600 dark:text-red-400 mb-4">{error}</p>
      )}

      {user && (
        <Card>
          <CardHeader>
            <CardTitle>Persönliche Einstellungen</CardTitle>
            <CardDescription>
              Anzeigename und UI-Präferenzen (Theme und Sprache werden app-weit angewendet).
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-2">
              <Label htmlFor="display_name">Anzeigename</Label>
              <Input
                id="display_name"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
              />
            </div>

            <div className="space-y-3">
              <Label>Theme</Label>
              <RadioGroup
                value={theme}
                onValueChange={(v) => setTheme(v as UserTheme)}
                className="flex flex-col gap-2"
              >
                {(["light", "dark", "system"] as const).map((t) => (
                  <div key={t} className="flex items-center space-x-2">
                    <RadioGroupItem value={t} id={`theme-${t}`} />
                    <Label htmlFor={`theme-${t}`} className="font-normal cursor-pointer">
                      {themeLabels[t]}
                    </Label>
                  </div>
                ))}
              </RadioGroup>
            </div>

            <div className="space-y-3">
              <Label>Sprache</Label>
              <RadioGroup
                value={language}
                onValueChange={(v) => setLanguage(v as UserUILanguage)}
                className="flex flex-col gap-2"
              >
                {(["de", "en"] as const).map((l) => (
                  <div key={l} className="flex items-center space-x-2">
                    <RadioGroupItem value={l} id={`lang-${l}`} />
                    <Label htmlFor={`lang-${l}`} className="font-normal cursor-pointer">
                      {languageLabels[l]}
                    </Label>
                  </div>
                ))}
              </RadioGroup>
            </div>

            <div className="text-sm text-muted-foreground">
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
    </AppLayout>
  );
}
