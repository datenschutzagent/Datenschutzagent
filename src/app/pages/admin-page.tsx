import { Link, useNavigate } from "react-router";
import { useState, useEffect } from "react";
import { AppLayout } from "../components/app-layout";
import { PageHeader } from "../components/page-header";
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
  listAdminUsers,
  updateAdminUserRole,
  getRetentionPreview,
  triggerRetentionScan,
  testSmtp,
  triggerDeadlineNotifications,
  isAdmin,
  type ApiAdminSettings,
  type ApiConnectionsStatus,
  type ApiPromptTemplate,
  type ApiPromptTemplateKeyMeta,
  type ApiUser,
  type UserRole,
  type ApiRetentionPreviewResponse,
  type ApiRetentionScanResponse,
  type ApiNotificationTestResponse,
} from "../lib/api";
import { useAuthOptional } from "../contexts/AuthContext";
import { CheckCircle2, XCircle, HelpCircle, Loader2, CircleAlert, Pencil, History, Archive, Mail, Play, TriangleAlert } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "../components/ui/dialog";
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

  const [users, setUsers] = useState<ApiUser[]>([]);
  const [loadingUsers, setLoadingUsers] = useState(false);
  const [savingRoleId, setSavingRoleId] = useState<string | null>(null);

  const [retentionPreview, setRetentionPreview] = useState<ApiRetentionPreviewResponse | null>(null);
  const [retentionScanResult, setRetentionScanResult] = useState<ApiRetentionScanResponse | null>(null);
  const [loadingRetentionPreview, setLoadingRetentionPreview] = useState(false);
  const [loadingRetentionScan, setLoadingRetentionScan] = useState(false);
  const [confirmRetentionScan, setConfirmRetentionScan] = useState(false);

  const [smtpResult, setSmtpResult] = useState<ApiNotificationTestResponse | null>(null);
  const [deadlineResult, setDeadlineResult] = useState<{ sent_count: number; checked_count?: number } | null>(null);
  const [loadingSmtp, setLoadingSmtp] = useState(false);
  const [loadingDeadlines, setLoadingDeadlines] = useState(false);

  if (auth?.user && !isAdmin(auth.user)) {
    return (
      <AppLayout maxWidth="max-w-4xl">
        <Alert className="border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-900/30">
          <CircleAlert className="size-4 text-amber-600 dark:text-amber-400" />
          <AlertDescription className="text-amber-800 dark:text-amber-200">
            Sie haben keine Berechtigung fuer die Verwaltung. Nur Nutzer mit der Rolle "Admin" koennen diese Seite aufrufen.
          </AlertDescription>
        </Alert>
        <Button className="mt-4" variant="outline" onClick={() => navigate("/")}>
          Zurück zur Startseite
        </Button>
      </AppLayout>
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

  const loadUsers = async () => {
    setLoadingUsers(true);
    try {
      const list = await listAdminUsers();
      setUsers(list);
    } catch {
      // Silently fail – non-critical
    } finally {
      setLoadingUsers(false);
    }
  };

  useEffect(() => {
    if (auth?.user && isAdmin(auth.user)) {
      loadUsers();
    }
  }, [auth?.user]);

  const handleRoleChange = async (userId: string, role: UserRole) => {
    setSavingRoleId(userId);
    try {
      const updated = await updateAdminUserRole(userId, role);
      setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSavingRoleId(null);
    }
  };

  const handleRetentionPreview = async () => {
    setLoadingRetentionPreview(true);
    setRetentionPreview(null);
    setRetentionScanResult(null);
    setConfirmRetentionScan(false);
    setError(null);
    try {
      const result = await getRetentionPreview();
      setRetentionPreview(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoadingRetentionPreview(false);
    }
  };

  const handleRetentionScan = async () => {
    setLoadingRetentionScan(true);
    setRetentionScanResult(null);
    setError(null);
    try {
      const result = await triggerRetentionScan();
      setRetentionScanResult(result);
      setRetentionPreview(null);
      setConfirmRetentionScan(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoadingRetentionScan(false);
    }
  };

  const handleTestSmtp = async () => {
    setLoadingSmtp(true);
    setSmtpResult(null);
    setError(null);
    try {
      const result = await testSmtp();
      setSmtpResult(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoadingSmtp(false);
    }
  };

  const handleDeadlineNotifications = async () => {
    setLoadingDeadlines(true);
    setDeadlineResult(null);
    setError(null);
    try {
      const result = await triggerDeadlineNotifications();
      setDeadlineResult(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoadingDeadlines(false);
    }
  };

  const activeByKey = new Map(promptTemplates.filter((t) => t.is_active).map((t) => [t.key, t]));

  return (
    <AppLayout maxWidth="max-w-4xl">
        <PageHeader title="Verwaltung" />

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
                {settings.max_context_chars_per_doc != null && (
                  <div className="flex gap-2">
                    <dt className="font-medium text-slate-600 dark:text-slate-400 w-48">Kontext-Limit / Dok.</dt>
                    <dd className="text-slate-900 dark:text-slate-100">{settings.max_context_chars_per_doc.toLocaleString()} Zeichen</dd>
                  </div>
                )}
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

        {/* User management */}
        <Card className="mb-8 dark:bg-slate-900 dark:border-slate-800">
          <CardHeader>
            <CardTitle className="dark:text-slate-100">Benutzerverwaltung</CardTitle>
            <CardDescription className="dark:text-slate-400">
              Rollen der registrierten Nutzer anpassen (viewer, editor, admin).
            </CardDescription>
          </CardHeader>
          <CardContent>
            {loadingUsers ? (
              <p className="text-slate-600 dark:text-slate-400">Lade Nutzer…</p>
            ) : users.length === 0 ? (
              <p className="text-slate-500 dark:text-slate-400 text-sm">Keine Nutzer gefunden.</p>
            ) : (
              <div className="space-y-2">
                {users.map((u) => (
                  <div
                    key={u.id}
                    className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-slate-200 dark:border-slate-700 p-3"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="font-medium text-slate-900 dark:text-slate-100 truncate">
                        {u.display_name || "—"}
                      </p>
                      <p className="text-xs text-slate-500 dark:text-slate-400 truncate">
                        {u.email ?? "Keine E-Mail"} · ID: {u.id.slice(0, 8)}…
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      {savingRoleId === u.id ? (
                        <Loader2 className="size-4 animate-spin text-slate-500" />
                      ) : (
                        <Select
                          value={u.role ?? "viewer"}
                          onValueChange={(value) => handleRoleChange(u.id, value as UserRole)}
                        >
                          <SelectTrigger className="w-32">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="viewer">Viewer</SelectItem>
                            <SelectItem value="editor">Editor</SelectItem>
                            <SelectItem value="admin">Admin</SelectItem>
                          </SelectContent>
                        </Select>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Retention Management */}
        <Card className="mb-8 dark:bg-slate-900 dark:border-slate-800">
          <CardHeader>
            <CardTitle className="dark:text-slate-100">Aufbewahrungsfristen</CardTitle>
            <CardDescription className="dark:text-slate-400">
              Vorgänge, deren Aufbewahrungsfrist abgelaufen ist, können archiviert werden. Zuerst Vorschau laden, dann Scan ausführen.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2 mb-4">
              <Button
                variant="outline"
                onClick={handleRetentionPreview}
                disabled={loadingRetentionPreview || loadingRetentionScan}
              >
                {loadingRetentionPreview ? (
                  <><Loader2 className="size-4 mr-2 animate-spin" />Prüfe…</>
                ) : (
                  <><Archive className="size-4 mr-2" />Vorschau anzeigen</>
                )}
              </Button>
              {retentionPreview && retentionPreview.would_archive_count > 0 && !confirmRetentionScan && (
                <Button
                  variant="outline"
                  className="border-amber-400 text-amber-700 dark:text-amber-400 hover:bg-amber-50 dark:hover:bg-amber-900/20"
                  onClick={() => setConfirmRetentionScan(true)}
                >
                  <TriangleAlert className="size-4 mr-2" />
                  {retentionPreview.would_archive_count} Vorgang/Vorgänge archivieren
                </Button>
              )}
              {confirmRetentionScan && (
                <>
                  <Button
                    variant="destructive"
                    onClick={handleRetentionScan}
                    disabled={loadingRetentionScan}
                  >
                    {loadingRetentionScan ? (
                      <><Loader2 className="size-4 mr-2 animate-spin" />Archiviere…</>
                    ) : (
                      <><Play className="size-4 mr-2" />Jetzt archivieren (bestätigen)</>
                    )}
                  </Button>
                  <Button variant="ghost" onClick={() => setConfirmRetentionScan(false)}>
                    Abbrechen
                  </Button>
                </>
              )}
            </div>

            {retentionPreview && (
              retentionPreview.would_archive_count === 0 ? (
                <p className="text-sm text-slate-500 dark:text-slate-400 flex items-center gap-1">
                  <CheckCircle2 className="size-4 text-green-600 dark:text-green-400" />
                  Keine Vorgänge fällig – alle Aufbewahrungsfristen eingehalten.
                </p>
              ) : (
                <div className="space-y-1">
                  <p className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                    {retentionPreview.would_archive_count} Vorgang/Vorgänge würden archiviert:
                  </p>
                  <div className="rounded-md border border-slate-200 dark:border-slate-700 overflow-hidden">
                    <table className="w-full text-sm">
                      <thead className="bg-slate-50 dark:bg-slate-800">
                        <tr>
                          <th className="px-3 py-2 text-left font-medium text-slate-600 dark:text-slate-400">Titel</th>
                          <th className="px-3 py-2 text-left font-medium text-slate-600 dark:text-slate-400">Abteilung</th>
                          <th className="px-3 py-2 text-left font-medium text-slate-600 dark:text-slate-400">Frist (Monate)</th>
                          <th className="px-3 py-2 text-left font-medium text-slate-600 dark:text-slate-400">Zuletzt geändert</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
                        {retentionPreview.items.map((item) => (
                          <tr key={item.case_id} className="hover:bg-slate-50 dark:hover:bg-slate-800/50">
                            <td className="px-3 py-2 text-slate-900 dark:text-slate-100 max-w-[200px] truncate">{item.title}</td>
                            <td className="px-3 py-2 text-slate-600 dark:text-slate-400">{item.department}</td>
                            <td className="px-3 py-2 text-slate-600 dark:text-slate-400">{item.retention_months}</td>
                            <td className="px-3 py-2 text-slate-500 dark:text-slate-400 text-xs">
                              {item.updated_at ? new Date(item.updated_at).toLocaleString("de-DE") : "—"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )
            )}

            {retentionScanResult && (
              <p className="text-sm text-green-700 dark:text-green-400 flex items-center gap-1">
                <CheckCircle2 className="size-4" />
                {retentionScanResult.archived_count} Vorgang/Vorgänge erfolgreich archiviert.
              </p>
            )}
          </CardContent>
        </Card>

        {/* Notifications */}
        <Card className="mb-8 dark:bg-slate-900 dark:border-slate-800">
          <CardHeader>
            <CardTitle className="dark:text-slate-100">Benachrichtigungen</CardTitle>
            <CardDescription className="dark:text-slate-400">
              SMTP-Verbindung testen und Frist-Benachrichtigungen manuell auslösen (unabhängig vom automatischen Celery-Job).
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap items-center gap-4">
              <Button
                variant="outline"
                onClick={handleTestSmtp}
                disabled={loadingSmtp}
              >
                {loadingSmtp ? (
                  <><Loader2 className="size-4 mr-2 animate-spin" />Teste…</>
                ) : (
                  <><Mail className="size-4 mr-2" />SMTP testen</>
                )}
              </Button>
              {smtpResult && (
                <span className={`text-sm flex items-center gap-1 ${smtpResult.status === "ok" ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}`}>
                  {smtpResult.status === "ok" ? <CheckCircle2 className="size-4" /> : <XCircle className="size-4" />}
                  {smtpResult.smtp_enabled
                    ? smtpResult.status === "ok" ? "SMTP erreichbar" : `SMTP-Fehler${smtpResult.detail ? `: ${smtpResult.detail}` : ""}`
                    : "SMTP nicht konfiguriert"}
                </span>
              )}
            </div>

            <div className="flex flex-wrap items-center gap-4">
              <Button
                variant="outline"
                onClick={handleDeadlineNotifications}
                disabled={loadingDeadlines}
              >
                {loadingDeadlines ? (
                  <><Loader2 className="size-4 mr-2 animate-spin" />Sende…</>
                ) : (
                  <><Play className="size-4 mr-2" />Fristen-Benachrichtigungen jetzt senden</>
                )}
              </Button>
              {deadlineResult && (
                <span className="text-sm text-green-600 dark:text-green-400 flex items-center gap-1">
                  <CheckCircle2 className="size-4" />
                  {deadlineResult.sent_count} Benachrichtigung(en) versendet
                  {deadlineResult.checked_count != null ? ` (${deadlineResult.checked_count} geprüft)` : ""}
                </span>
              )}
            </div>
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
    </AppLayout>
  );
}
