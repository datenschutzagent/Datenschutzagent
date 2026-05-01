import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../ui/card";
import { Button } from "../ui/button";
import { Label } from "../ui/label";
import { Textarea } from "../ui/textarea";
import { Checkbox } from "../ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "../ui/dialog";
import {
  getAdminPromptTemplates,
  getAdminPromptTemplateKeys,
  getAdminPromptTemplateVersions,
  createAdminPromptTemplate,
  setActivePromptTemplate,
  type ApiPromptTemplate,
  type ApiPromptTemplateKeyMeta,
} from "../../lib/api";
import { useAuthOptional } from "../../contexts/AuthContext";
import { isAdmin } from "../../lib/api";
import { Pencil, History } from "lucide-react";

export function AdminPromptsTab() {
  const auth = useAuthOptional();
  const [templates, setTemplates] = useState<ApiPromptTemplate[]>([]);
  const [keys, setKeys] = useState<ApiPromptTemplateKeyMeta[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [editOpen, setEditOpen] = useState(false);
  const [editKey, setEditKey] = useState("");
  const [editContent, setEditContent] = useState("");
  const [editVersion, setEditVersion] = useState("");
  const [editSetActive, setEditSetActive] = useState(true);
  const [savingPrompt, setSavingPrompt] = useState(false);

  const [versionsKey, setVersionsKey] = useState<string | null>(null);
  const [versionsList, setVersionsList] = useState<ApiPromptTemplate[]>([]);
  const [loadingVersions, setLoadingVersions] = useState(false);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [t, k] = await Promise.all([
        getAdminPromptTemplates(),
        getAdminPromptTemplateKeys(),
      ]);
      setTemplates(t);
      setKeys(k);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (auth?.user && isAdmin(auth.user)) {
      void loadData();
    }
  }, [auth?.user]);

  const openEdit = (key: string, content: string) => {
    setEditKey(key);
    setEditContent(content);
    setEditVersion("");
    setEditSetActive(true);
    setEditOpen(true);
  };

  const handleSave = async () => {
    if (!editKey || !editContent.trim()) return;
    setSavingPrompt(true);
    setError(null);
    try {
      await createAdminPromptTemplate({
        key: editKey,
        version: editVersion.trim() || undefined,
        content: editContent.trim(),
        set_active: editSetActive,
      });
      setEditOpen(false);
      await loadData();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSavingPrompt(false);
    }
  };

  const openVersions = async (key: string) => {
    setVersionsKey(key);
    setLoadingVersions(true);
    try {
      const list = await getAdminPromptTemplateVersions(key);
      setVersionsList(list);
    } finally {
      setLoadingVersions(false);
    }
  };

  const handleSetActive = async (id: string) => {
    setError(null);
    try {
      await setActivePromptTemplate(id, true);
      setVersionsKey(null);
      await loadData();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const activeByKey = new Map(
    templates.filter((t) => t.is_active).map((t) => [t.key, t]),
  );

  return (
    <>
      <Card className="mb-8 dark:bg-slate-900 dark:border-slate-800">
        <CardHeader>
          <CardTitle className="dark:text-slate-100">Prompt-Vorlagen</CardTitle>
          <CardDescription className="dark:text-slate-400">
            Versionierbare System- und User-Prompts für Checks und VVT. Platzhalter z. B.{" "}
            {"{requirement}"}, {"{document_text}"}, {"{language_hint}"}.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {error && <p className="text-red-600 dark:text-red-400 mb-3 text-sm">{error}</p>}
          {loading ? (
            <p className="text-slate-600 dark:text-slate-400">Lade Vorlagen…</p>
          ) : (
            <div className="space-y-3">
              {keys.map((meta) => {
                const active = activeByKey.get(meta.key);
                const raw = active?.content ?? "";
                const preview = raw ? (raw.length > 80 ? raw.slice(0, 80) + "…" : raw) : "—";
                return (
                  <div
                    key={meta.key}
                    className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-slate-200 dark:border-slate-700 p-3"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="font-medium text-slate-900 dark:text-slate-100 truncate">
                        {meta.key}
                      </p>
                      <p className="text-xs text-slate-500 dark:text-slate-400">
                        {meta.description}
                      </p>
                      <p className="mt-1 text-xs text-slate-600 dark:text-slate-300 truncate">
                        {active ? `Aktiv: ${active.version}` : "Keine aktive Version"}
                      </p>
                      <p className="text-xs text-slate-500 dark:text-slate-400 truncate">
                        {preview}…
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => void openVersions(meta.key)}
                      >
                        <History className="size-4 mr-1" />
                        Versionen
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => openEdit(meta.key, active?.content ?? "")}
                      >
                        <Pencil className="size-4 mr-1" />
                        Bearbeiten
                      </Button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Edit Dialog */}
      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] flex flex-col">
          <DialogHeader>
            <DialogTitle>Vorlage bearbeiten (neue Version)</DialogTitle>
            <DialogDescription>
              Key: {editKey}. Verfügbare Platzhalter:{" "}
              {keys
                .find((k) => k.key === editKey)
                ?.placeholders.map((p) => `{${p}}`)
                .join(", ") ?? "—"}
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-4 flex-1 min-h-0">
            <div className="space-y-2">
              <Label>Inhalt</Label>
              <Textarea
                value={editContent}
                onChange={(e) => setEditContent(e.target.value)}
                className="min-h-[200px] font-mono text-sm"
                placeholder='z. B. You are a strict data protection auditor. {language_hint}'
              />
            </div>
            <div className="space-y-2">
              <Label>Version (leer = Auto)</Label>
              <input
                type="text"
                value={editVersion}
                onChange={(e) => setEditVersion(e.target.value)}
                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                placeholder="1.1 oder leer"
              />
            </div>
            <div className="flex items-center space-x-2">
              <Checkbox
                id="set-active"
                checked={editSetActive}
                onCheckedChange={(c) => setEditSetActive(c === true)}
              />
              <label
                htmlFor="set-active"
                className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
              >
                Als aktive Version setzen
              </label>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditOpen(false)}>
              Abbrechen
            </Button>
            <Button onClick={() => void handleSave()} disabled={savingPrompt || !editContent.trim()}>
              {savingPrompt ? "Speichern…" : "Speichern (neue Version)"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Versions Dialog */}
      <Dialog
        open={versionsKey !== null}
        onOpenChange={(open) => !open && setVersionsKey(null)}
      >
        <DialogContent className="max-w-xl">
          <DialogHeader>
            <DialogTitle>Versionen: {versionsKey}</DialogTitle>
            <DialogDescription>
              Eine Version aktivieren oder im Bearbeiten-Dialog eine neue Version anlegen.
            </DialogDescription>
          </DialogHeader>
          {loadingVersions ? (
            <p className="text-slate-600 dark:text-slate-400">Lade…</p>
          ) : (
            <ul className="space-y-2 max-h-60 overflow-auto">
              {versionsList.map((t) => (
                <li
                  key={t.id}
                  className="flex items-center justify-between rounded border border-slate-200 dark:border-slate-700 p-2"
                >
                  <span className="text-sm">
                    {t.version}
                    {t.is_active && (
                      <span className="ml-2 text-green-600 dark:text-green-400 font-medium">
                        Aktiv
                      </span>
                    )}
                    <span className="ml-2 text-slate-500 text-xs">
                      {new Date(t.created_at).toLocaleString("de-DE")}
                    </span>
                  </span>
                  {!t.is_active && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => void handleSetActive(t.id)}
                    >
                      Aktivieren
                    </Button>
                  )}
                </li>
              ))}
              {versionsList.length === 0 && (
                <p className="text-slate-500 text-sm">
                  Keine Versionen. Über „Bearbeiten" eine neue anlegen.
                </p>
              )}
            </ul>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
