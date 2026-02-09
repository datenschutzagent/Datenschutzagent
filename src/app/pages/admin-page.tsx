import { Link, useNavigate } from "react-router";
import { useState, useEffect } from "react";
import { AppHeaderUser } from "../components/app-header-user";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Alert, AlertDescription } from "../components/ui/alert";
import {
  getAdminSettings,
  getConnectionsStatus,
  getAdminPromptTemplates,
  getAdminPromptTemplateKeys,
  getAdminPromptTemplateVersions,
  createAdminPromptTemplate,
  setActivePromptTemplate,
  isAdmin,
  type ApiAdminSettings,
  type ApiConnectionsStatus,
  type ApiPromptTemplate,
  type ApiPromptTemplateKeyMeta,
} from "../lib/api";
import { useAuthOptional } from "../contexts/AuthContext";
import { CheckCircle2, XCircle, HelpCircle, Loader2, CircleAlert, Pencil, History } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "../components/ui/dialog";
import { Button } from "../components/ui/button";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Checkbox } from "../components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select";

const connectionLabels: Record<keyof ApiConnectionsStatus, string> = {
  ollama: "Ollama",
  weaviate: "Weaviate",
  minio: "MinIO / S3",
  postgres: "Postgres",
  redis: "Redis",
};

function ConnectionStatus({ status, message }: { status: string; message?: string }) {
  if (status === "ok") {
    return (
      <span className="inline-flex items-center gap-1 text-green-600 dark:text-green-400">
        <CheckCircle2 className="size-4" />
        Erreichbar
      </span>
    );
  }
  if (status === "disabled" || status === "not_configured") {
    return (
      <span className="inline-flex items-center gap-1 text-slate-500 dark:text-slate-400">
        <HelpCircle className="size-4" />
        {status === "not_configured" ? "Nicht konfiguriert" : "Deaktiviert"}
        {message ? ` – ${message}` : ""}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 text-red-600 dark:text-red-400">
      <XCircle className="size-4" />
      Nicht erreichbar
      {message ? ` – ${message}` : ""}
    </span>
  );
}

export function AdminPage() {
  const navigate = useNavigate();
  const auth = useAuthOptional();
  const [settings, setSettings] = useState<ApiAdminSettings | null>(null);
  const [connections, setConnections] = useState<ApiConnectionsStatus | null>(null);
  const [loadingSettings, setLoadingSettings] = useState(true);
  const [loadingConnections, setLoadingConnections] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [promptTemplates, setPromptTemplates] = useState<ApiPromptTemplate[]>([]);
  const [promptKeys, setPromptKeys] = useState<ApiPromptTemplateKeyMeta[]>([]);
  const [loadingPrompts, setLoadingPrompts] = useState(true);
  const [editOpen, setEditOpen] = useState(false);
  const [editKey, setEditKey] = useState("");
  const [editContent, setEditContent] = useState("");
  const [editVersion, setEditVersion] = useState("");
  const [editSetActive, setEditSetActive] = useState(true);
  const [savingPrompt, setSavingPrompt] = useState(false);
  const [versionsKey, setVersionsKey] = useState<string | null>(null);
  const [versionsList, setVersionsList] = useState<ApiPromptTemplate[]>([]);
  const [loadingVersions, setLoadingVersions] = useState(false);

  if (auth?.user && !isAdmin(auth.user)) {
    return (
      <div className="min-h-screen bg-slate-50">
        <header className="bg-white border-b border-slate-200">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex justify-between items-center">
            <h1 className="text-2xl font-semibold text-slate-900">Datenschutz-Agent</h1>
            <AppHeaderUser />
          </div>
        </header>
        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <Alert className="border-amber-200 bg-amber-50">
            <CircleAlert className="size-4 text-amber-600" />
            <AlertDescription className="text-amber-800">
              Sie haben keine Berechtigung für die Verwaltung. Nur Nutzer mit der Rolle „Admin“ können diese Seite aufrufen.
            </AlertDescription>
          </Alert>
          <Button className="mt-4" variant="outline" onClick={() => navigate("/")}>
            Zurück zur Startseite
          </Button>
        </main>
      </div>
    );
  }

  useEffect(() => {
    let cancelled = false;
    setLoadingSettings(true);
    setError(null);
    getAdminSettings()
      .then((s) => {
        if (!cancelled) setSettings(s);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (!cancelled) setLoadingSettings(false);
      });
    return () => { cancelled = true; };
  }, []);

  const runConnectionChecks = async () => {
    setLoadingConnections(true);
    setError(null);
    try {
      const c = await getConnectionsStatus();
      setConnections(c);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoadingConnections(false);
    }
  };

  useEffect(() => {
    runConnectionChecks();
  }, []);

  const loadPromptData = async () => {
    setLoadingPrompts(true);
    setError(null);
    try {
      const [templates, keys] = await Promise.all([
        getAdminPromptTemplates(),
        getAdminPromptTemplateKeys(),
      ]);
      setPromptTemplates(templates);
      setPromptKeys(keys);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoadingPrompts(false);
    }
  };

  useEffect(() => {
    if (auth?.user && isAdmin(auth.user)) {
      loadPromptData();
    }
  }, [auth?.user]);

  const openEdit = (key: string, content: string) => {
    setEditKey(key);
    setEditContent(content);
    setEditVersion("");
    setEditSetActive(true);
    setEditOpen(true);
  };

  const handleSavePrompt = async () => {
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
      await loadPromptData();
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
      await loadPromptData();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const activeByKey = new Map(promptTemplates.filter((t) => t.is_active).map((t) => [t.key, t]));

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 transition-colors">
      <header className="bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 transition-colors">
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
              <Link to="/vvt-overview" className="text-sm font-medium text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100">
                VVT-Übersicht
              </Link>
              <Link to="/playbooks" className="text-sm font-medium text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100">
                Playbooks
              </Link>
              <Link to="/legal-bases" className="text-sm font-medium text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100">
                Rechtsgrundlagen
              </Link>
              <Link to="/profile" className="text-sm font-medium text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100">
                Mein Profil
              </Link>
              <Link to="/admin" className="text-sm font-medium text-blue-600 dark:text-blue-400">
                Verwaltung
              </Link>
              <AppHeaderUser />
            </nav>
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100 mb-6">Verwaltung</h2>

        {error && (
          <p className="text-red-600 dark:text-red-400 mb-4">{error}</p>
        )}

        {/* Read-only settings */}
        <Card className="mb-8 dark:bg-slate-900 dark:border-slate-800">
          <CardHeader>
            <CardTitle className="dark:text-slate-100">Generelle Einstellungen</CardTitle>
            <CardDescription className="dark:text-slate-400">
              Werte aus der Konfiguration (nur Leseansicht). Änderungen über Umgebungsvariablen bzw. Deployment.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {loadingSettings ? (
              <p className="text-slate-600 dark:text-slate-400">Lade Einstellungen…</p>
            ) : settings ? (
              <dl className="grid gap-2 text-sm">
                <div className="flex gap-2">
                  <dt className="font-medium text-slate-600 dark:text-slate-400 w-48">App-Name</dt>
                  <dd className="text-slate-900 dark:text-slate-100">{settings.app_name}</dd>
                </div>
                <div className="flex gap-2">
                  <dt className="font-medium text-slate-600 dark:text-slate-400 w-48">Ollama URL</dt>
                  <dd className="text-slate-900 dark:text-slate-100">{settings.ollama_base_url}</dd>
                </div>
                <div className="flex gap-2">
                  <dt className="font-medium text-slate-600 dark:text-slate-400 w-48">Ollama aktiv</dt>
                  <dd>{settings.ollama_enabled ? "Ja" : "Nein"}</dd>
                </div>
                <div className="flex gap-2">
                  <dt className="font-medium text-slate-600 dark:text-slate-400 w-48">Ollama-Modell</dt>
                  <dd className="text-slate-900 dark:text-slate-100">{settings.ollama_model}</dd>
                </div>
                <div className="flex gap-2">
                  <dt className="font-medium text-slate-600 dark:text-slate-400 w-48">Weaviate URL</dt>
                  <dd className="text-slate-900 dark:text-slate-100">{settings.weaviate_url}</dd>
                </div>
                <div className="flex gap-2">
                  <dt className="font-medium text-slate-600 dark:text-slate-400 w-48">Weaviate-Indexierung</dt>
                  <dd>{settings.weaviate_indexing_enabled ? "Aktiv" : "Aus"}</dd>
                </div>
                <div className="flex gap-2">
                  <dt className="font-medium text-slate-600 dark:text-slate-400 w-48">Storage-Backend</dt>
                  <dd className="text-slate-900 dark:text-slate-100">{settings.storage_backend}</dd>
                </div>
                {settings.storage_local_path != null && (
                  <div className="flex gap-2">
                    <dt className="font-medium text-slate-600 dark:text-slate-400 w-48">Lokaler Storage-Pfad</dt>
                    <dd className="text-slate-900 dark:text-slate-100">{settings.storage_local_path}</dd>
                  </div>
                )}
                <div className="flex gap-2">
                  <dt className="font-medium text-slate-600 dark:text-slate-400 w-48">S3 konfiguriert</dt>
                  <dd>{settings.s3_configured ? "Ja" : "Nein"}</dd>
                </div>
                {settings.s3_bucket != null && (
                  <div className="flex gap-2">
                    <dt className="font-medium text-slate-600 dark:text-slate-400 w-48">S3-Bucket</dt>
                    <dd className="text-slate-900 dark:text-slate-100">{settings.s3_bucket}</dd>
                  </div>
                )}
                <div className="flex gap-2">
                  <dt className="font-medium text-slate-600 dark:text-slate-400 w-48">Celery aktiv</dt>
                  <dd>{settings.celery_enabled ? "Ja" : "Nein"}</dd>
                </div>
                <div className="flex gap-2">
                  <dt className="font-medium text-slate-600 dark:text-slate-400 w-48">Redis-Broker</dt>
                  <dd>{settings.celery_broker_configured ? "Konfiguriert" : "Nicht konfiguriert"}</dd>
                </div>
              </dl>
            ) : null}
          </CardContent>
        </Card>

        {/* Prompt-Vorlagen */}
        <Card className="mb-8 dark:bg-slate-900 dark:border-slate-800">
          <CardHeader>
            <CardTitle className="dark:text-slate-100">Prompt-Vorlagen</CardTitle>
            <CardDescription className="dark:text-slate-400">
              Versionierbare System- und User-Prompts für Checks und VVT. Platzhalter z. B. {"{requirement}"}, {"{document_text}"}, {"{language_hint}"}.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {loadingPrompts ? (
              <p className="text-slate-600 dark:text-slate-400">Lade Vorlagen…</p>
            ) : (
              <div className="space-y-3">
                {promptKeys.map((meta) => {
                  const active = activeByKey.get(meta.key);
                  const raw = active?.content ?? "";
                  const preview = raw ? (raw.length > 80 ? raw.slice(0, 80) + "…" : raw) : "—";
                  return (
                    <div
                      key={meta.key}
                      className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-slate-200 dark:border-slate-700 p-3"
                    >
                      <div className="min-w-0 flex-1">
                        <p className="font-medium text-slate-900 dark:text-slate-100 truncate">{meta.key}</p>
                        <p className="text-xs text-slate-500 dark:text-slate-400">{meta.description}</p>
                        <p className="mt-1 text-xs text-slate-600 dark:text-slate-300 truncate">
                          {active ? `Aktiv: ${active.version}` : "Keine aktive Version"}
                        </p>
                        <p className="text-xs text-slate-500 dark:text-slate-400 truncate">{preview}…</p>
                      </div>
                      <div className="flex items-center gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => openVersions(meta.key)}
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

        {/* Connection checks */}
        <Card className="dark:bg-slate-900 dark:border-slate-800">
          <CardHeader>
            <CardTitle className="dark:text-slate-100">Verbindungen testen</CardTitle>
            <CardDescription className="dark:text-slate-400">
              Status der Anbindungen zu Ollama, Weaviate, MinIO, Postgres und Redis.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button
              onClick={runConnectionChecks}
              disabled={loadingConnections}
              className="mb-4"
              variant="outline"
            >
              {loadingConnections ? (
                <>
                  <Loader2 className="size-4 mr-2 animate-spin" />
                  Prüfe…
                </>
              ) : (
                "Verbindungen prüfen"
              )}
            </Button>
            {connections ? (
              <ul className="space-y-2">
                {(Object.keys(connectionLabels) as (keyof ApiConnectionsStatus)[]).map((key) => (
                  <li key={key} className="flex items-center justify-between py-1">
                    <span className="font-medium text-slate-700 dark:text-slate-300">
                      {connectionLabels[key]}
                    </span>
                    <ConnectionStatus
                      status={connections[key].status}
                      message={connections[key].message}
                    />
                  </li>
                ))}
              </ul>
            ) : !loadingConnections && !error ? (
              <p className="text-slate-600 dark:text-slate-400">Klicken Sie auf „Verbindungen prüfen“.</p>
            ) : null}
          </CardContent>
        </Card>

        {/* Edit Prompt Dialog */}
        <Dialog open={editOpen} onOpenChange={setEditOpen}>
          <DialogContent className="max-w-2xl max-h-[90vh] flex flex-col">
            <DialogHeader>
              <DialogTitle>Vorlage bearbeiten (neue Version)</DialogTitle>
              <DialogDescription>
                Key: {editKey}. Verfügbare Platzhalter:{" "}
                {promptKeys.find((k) => k.key === editKey)?.placeholders.map((p) => `{${p}}`).join(", ") ?? "—"}
              </DialogDescription>
            </DialogHeader>
            <div className="flex flex-col gap-4 flex-1 min-h-0">
              <div className="space-y-2">
                <Label>Inhalt</Label>
                <Textarea
                  value={editContent}
                  onChange={(e) => setEditContent(e.target.value)}
                  className="min-h-[200px] font-mono text-sm"
                  placeholder="z. B. You are a strict data protection auditor. {language_hint}"
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
                <label htmlFor="set-active" className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
                  Als aktive Version setzen
                </label>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setEditOpen(false)}>
                Abbrechen
              </Button>
              <Button onClick={handleSavePrompt} disabled={savingPrompt || !editContent.trim()}>
                {savingPrompt ? "Speichern…" : "Speichern (neue Version)"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Versions Dialog */}
        <Dialog open={versionsKey !== null} onOpenChange={(open) => !open && setVersionsKey(null)}>
          <DialogContent className="max-w-xl">
            <DialogHeader>
              <DialogTitle>Versionen: {versionsKey}</DialogTitle>
              <DialogDescription>Eine Version aktivieren oder im Bearbeiten-Dialog eine neue Version anlegen.</DialogDescription>
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
                        <span className="ml-2 text-green-600 dark:text-green-400 font-medium">Aktiv</span>
                      )}
                      <span className="ml-2 text-slate-500 text-xs">
                        {new Date(t.created_at).toLocaleString("de-DE")}
                      </span>
                    </span>
                    {!t.is_active && (
                      <Button variant="outline" size="sm" onClick={() => handleSetActive(t.id)}>
                        Aktivieren
                      </Button>
                    )}
                  </li>
                ))}
                {versionsList.length === 0 && (
                  <p className="text-slate-500 text-sm">Keine Versionen. Über „Bearbeiten“ eine neue anlegen.</p>
                )}
              </ul>
            )}
          </DialogContent>
        </Dialog>
      </main>
    </div>
  );
}
