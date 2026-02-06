import { Link } from "react-router";
import { useState, useEffect } from "react";
import { AppHeaderUser } from "../components/app-header-user";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { getAdminSettings, getConnectionsStatus, type ApiAdminSettings, type ApiConnectionsStatus } from "../lib/api";
import { CheckCircle2, XCircle, HelpCircle, Loader2 } from "lucide-react";

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
  const [settings, setSettings] = useState<ApiAdminSettings | null>(null);
  const [connections, setConnections] = useState<ApiConnectionsStatus | null>(null);
  const [loadingSettings, setLoadingSettings] = useState(true);
  const [loadingConnections, setLoadingConnections] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
      </main>
    </div>
  );
}
