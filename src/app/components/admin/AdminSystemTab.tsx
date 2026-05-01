import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../ui/card";
import { Button } from "../ui/button";
import {
  getAdminSettings,
  getConnectionsStatus,
  getRetentionPreview,
  triggerRetentionScan,
  testSmtp,
  triggerDeadlineNotifications,
  type ApiAdminSettings,
  type ApiConnectionsStatus,
  type ApiRetentionPreviewResponse,
  type ApiRetentionScanResponse,
  type ApiNotificationTestResponse,
} from "../../lib/api";
import {
  CheckCircle2,
  XCircle,
  HelpCircle,
  Loader2,
  Archive,
  Mail,
  Play,
  TriangleAlert,
} from "lucide-react";

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

export function AdminSystemTab() {
  const [settings, setSettings] = useState<ApiAdminSettings | null>(null);
  const [loadingSettings, setLoadingSettings] = useState(true);

  const [connections, setConnections] = useState<ApiConnectionsStatus | null>(null);
  const [loadingConnections, setLoadingConnections] = useState(false);

  const [retentionPreview, setRetentionPreview] =
    useState<ApiRetentionPreviewResponse | null>(null);
  const [retentionScanResult, setRetentionScanResult] =
    useState<ApiRetentionScanResponse | null>(null);
  const [loadingRetentionPreview, setLoadingRetentionPreview] = useState(false);
  const [loadingRetentionScan, setLoadingRetentionScan] = useState(false);
  const [confirmRetentionScan, setConfirmRetentionScan] = useState(false);

  const [smtpResult, setSmtpResult] = useState<ApiNotificationTestResponse | null>(null);
  const [deadlineResult, setDeadlineResult] = useState<{
    sent_count: number;
    checked_count?: number;
  } | null>(null);
  const [loadingSmtp, setLoadingSmtp] = useState(false);
  const [loadingDeadlines, setLoadingDeadlines] = useState(false);

  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getAdminSettings()
      .then((s) => { if (!cancelled) setSettings(s); })
      .catch((e) => { if (!cancelled) setError(e instanceof Error ? e.message : String(e)); })
      .finally(() => { if (!cancelled) setLoadingSettings(false); });
    return () => { cancelled = true; };
  }, []);

  const runConnectionChecks = async () => {
    setLoadingConnections(true);
    setError(null);
    try {
      setConnections(await getConnectionsStatus());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoadingConnections(false);
    }
  };

  useEffect(() => { void runConnectionChecks(); }, []);

  const handleRetentionPreview = async () => {
    setLoadingRetentionPreview(true);
    setRetentionPreview(null);
    setRetentionScanResult(null);
    setConfirmRetentionScan(false);
    setError(null);
    try {
      setRetentionPreview(await getRetentionPreview());
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
      setRetentionScanResult(await triggerRetentionScan());
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
      setSmtpResult(await testSmtp());
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
      setDeadlineResult(await triggerDeadlineNotifications());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoadingDeadlines(false);
    }
  };

  return (
    <>
      {error && <p className="text-red-600 dark:text-red-400 mb-4 text-sm">{error}</p>}

      {/* Settings */}
      <Card className="mb-8 dark:bg-slate-900 dark:border-slate-800">
        <CardHeader>
          <CardTitle className="dark:text-slate-100">Generelle Einstellungen</CardTitle>
          <CardDescription className="dark:text-slate-400">
            Werte aus der Konfiguration (nur Leseansicht). Änderungen über Umgebungsvariablen
            bzw. Deployment.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loadingSettings ? (
            <p className="text-slate-600 dark:text-slate-400">Lade Einstellungen…</p>
          ) : settings ? (
            <dl className="grid gap-2 text-sm">
              {[
                ["App-Name", settings.app_name],
                ["Ollama URL", settings.ollama_base_url],
                ["Ollama aktiv", settings.ollama_enabled ? "Ja" : "Nein"],
                ["Ollama-Modell", settings.ollama_model],
                ["Weaviate URL", settings.weaviate_url],
                [
                  "Weaviate-Indexierung",
                  settings.weaviate_indexing_enabled ? "Aktiv" : "Aus",
                ],
                ["Storage-Backend", settings.storage_backend],
                ...(settings.storage_local_path != null
                  ? [["Lokaler Storage-Pfad", settings.storage_local_path]]
                  : []),
                ["S3 konfiguriert", settings.s3_configured ? "Ja" : "Nein"],
                ...(settings.s3_bucket != null
                  ? [["S3-Bucket", settings.s3_bucket]]
                  : []),
                ["Celery aktiv", settings.celery_enabled ? "Ja" : "Nein"],
                [
                  "Redis-Broker",
                  settings.celery_broker_configured ? "Konfiguriert" : "Nicht konfiguriert",
                ],
                ...(settings.max_context_chars_per_doc != null
                  ? [
                      [
                        "Kontext-Limit / Dok.",
                        `${settings.max_context_chars_per_doc.toLocaleString()} Zeichen`,
                      ],
                    ]
                  : []),
              ].map(([label, value]) => (
                <div key={label as string} className="flex gap-2">
                  <dt className="font-medium text-slate-600 dark:text-slate-400 w-48">
                    {label}
                  </dt>
                  <dd className="text-slate-900 dark:text-slate-100">{value}</dd>
                </div>
              ))}
            </dl>
          ) : null}
        </CardContent>
      </Card>

      {/* Retention */}
      <Card className="mb-8 dark:bg-slate-900 dark:border-slate-800">
        <CardHeader>
          <CardTitle className="dark:text-slate-100">Aufbewahrungsfristen</CardTitle>
          <CardDescription className="dark:text-slate-400">
            Vorgänge, deren Aufbewahrungsfrist abgelaufen ist, können archiviert werden.
            Zuerst Vorschau laden, dann Scan ausführen.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2 mb-4">
            <Button
              variant="outline"
              onClick={() => void handleRetentionPreview()}
              disabled={loadingRetentionPreview || loadingRetentionScan}
            >
              {loadingRetentionPreview ? (
                <>
                  <Loader2 className="size-4 mr-2 animate-spin" />
                  Prüfe…
                </>
              ) : (
                <>
                  <Archive className="size-4 mr-2" />
                  Vorschau anzeigen
                </>
              )}
            </Button>
            {retentionPreview &&
              retentionPreview.would_archive_count > 0 &&
              !confirmRetentionScan && (
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
                  onClick={() => void handleRetentionScan()}
                  disabled={loadingRetentionScan}
                >
                  {loadingRetentionScan ? (
                    <>
                      <Loader2 className="size-4 mr-2 animate-spin" />
                      Archiviere…
                    </>
                  ) : (
                    <>
                      <Play className="size-4 mr-2" />
                      Jetzt archivieren (bestätigen)
                    </>
                  )}
                </Button>
                <Button variant="ghost" onClick={() => setConfirmRetentionScan(false)}>
                  Abbrechen
                </Button>
              </>
            )}
          </div>

          {retentionPreview &&
            (retentionPreview.would_archive_count === 0 ? (
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
                        <th className="px-3 py-2 text-left font-medium text-slate-600 dark:text-slate-400">
                          Titel
                        </th>
                        <th className="px-3 py-2 text-left font-medium text-slate-600 dark:text-slate-400">
                          Abteilung
                        </th>
                        <th className="px-3 py-2 text-left font-medium text-slate-600 dark:text-slate-400">
                          Frist (Monate)
                        </th>
                        <th className="px-3 py-2 text-left font-medium text-slate-600 dark:text-slate-400">
                          Zuletzt geändert
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
                      {retentionPreview.items.map((item) => (
                        <tr
                          key={item.case_id}
                          className="hover:bg-slate-50 dark:hover:bg-slate-800/50"
                        >
                          <td className="px-3 py-2 text-slate-900 dark:text-slate-100 max-w-[200px] truncate">
                            {item.title}
                          </td>
                          <td className="px-3 py-2 text-slate-600 dark:text-slate-400">
                            {item.department}
                          </td>
                          <td className="px-3 py-2 text-slate-600 dark:text-slate-400">
                            {item.retention_months}
                          </td>
                          <td className="px-3 py-2 text-slate-500 dark:text-slate-400 text-xs">
                            {item.updated_at
                              ? new Date(item.updated_at).toLocaleString("de-DE")
                              : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}

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
            SMTP-Verbindung testen und Frist-Benachrichtigungen manuell auslösen (unabhängig
            vom automatischen Celery-Job).
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-center gap-4">
            <Button variant="outline" onClick={() => void handleTestSmtp()} disabled={loadingSmtp}>
              {loadingSmtp ? (
                <>
                  <Loader2 className="size-4 mr-2 animate-spin" />
                  Teste…
                </>
              ) : (
                <>
                  <Mail className="size-4 mr-2" />
                  SMTP testen
                </>
              )}
            </Button>
            {smtpResult && (
              <span
                className={`text-sm flex items-center gap-1 ${
                  smtpResult.status === "ok"
                    ? "text-green-600 dark:text-green-400"
                    : "text-red-600 dark:text-red-400"
                }`}
              >
                {smtpResult.status === "ok" ? (
                  <CheckCircle2 className="size-4" />
                ) : (
                  <XCircle className="size-4" />
                )}
                {smtpResult.smtp_enabled
                  ? smtpResult.status === "ok"
                    ? "SMTP erreichbar"
                    : `SMTP-Fehler${smtpResult.detail ? `: ${smtpResult.detail}` : ""}`
                  : "SMTP nicht konfiguriert"}
              </span>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-4">
            <Button
              variant="outline"
              onClick={() => void handleDeadlineNotifications()}
              disabled={loadingDeadlines}
            >
              {loadingDeadlines ? (
                <>
                  <Loader2 className="size-4 mr-2 animate-spin" />
                  Sende…
                </>
              ) : (
                <>
                  <Play className="size-4 mr-2" />
                  Fristen-Benachrichtigungen jetzt senden
                </>
              )}
            </Button>
            {deadlineResult && (
              <span className="text-sm text-green-600 dark:text-green-400 flex items-center gap-1">
                <CheckCircle2 className="size-4" />
                {deadlineResult.sent_count} Benachrichtigung(en) versendet
                {deadlineResult.checked_count != null
                  ? ` (${deadlineResult.checked_count} geprüft)`
                  : ""}
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
            onClick={() => void runConnectionChecks()}
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
          ) : !loadingConnections ? (
            <p className="text-slate-600 dark:text-slate-400">
              Klicken Sie auf „Verbindungen prüfen".
            </p>
          ) : null}
        </CardContent>
      </Card>
    </>
  );
}
