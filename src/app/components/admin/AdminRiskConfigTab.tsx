import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { AlertTriangle, Eye, Loader2, RefreshCw, RotateCcw, Save } from "lucide-react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "../ui/alert-dialog";
import { Alert, AlertDescription } from "../ui/alert";
import { Button } from "../ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../ui/card";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "../ui/dialog";
import {
  getAdminRiskConfig,
  previewAdminRiskConfig,
  reloadAdminRiskConfig,
  updateAdminRiskConfig,
} from "../../lib/api/admin";
import type {
  AdminRiskConfigPreviewResponse,
  AdminRiskConfigResponse,
  RiskConfig,
} from "../../lib/api/types/risk-config";
import { AdminRiskConfigContext } from "./AdminRiskConfigContext";
import { AdminRiskConfigAvvSection } from "./AdminRiskConfigAvvSection";
import { AdminRiskConfigDsfaSection } from "./AdminRiskConfigDsfaSection";
import { AdminRiskConfigMaturitySection } from "./AdminRiskConfigMaturitySection";

function deepClone<T>(v: T): T {
  return structuredClone(v);
}

function deepEqual(a: unknown, b: unknown): boolean {
  return JSON.stringify(a) === JSON.stringify(b);
}

export function AdminRiskConfigTab() {
  const [meta, setMeta] = useState<AdminRiskConfigResponse | null>(null);
  const [config, setConfig] = useState<RiskConfig | null>(null);
  const [original, setOriginal] = useState<RiskConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [reloading, setReloading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewData, setPreviewData] = useState<AdminRiskConfigPreviewResponse | null>(null);
  const [previewing, setPreviewing] = useState(false);

  const [confirmSaveOpen, setConfirmSaveOpen] = useState(false);

  const dirty = useMemo(
    () => config !== null && original !== null && !deepEqual(config, original),
    [config, original],
  );

  const fetchConfig = useCallback(async () => {
    setError(null);
    try {
      const data = await getAdminRiskConfig();
      setMeta(data);
      setConfig(deepClone(data.config));
      setOriginal(deepClone(data.config));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    fetchConfig().finally(() => setLoading(false));
  }, [fetchConfig]);

  async function handleReload() {
    setReloading(true);
    try {
      await reloadAdminRiskConfig();
      await fetchConfig();
      toast.success("Risk-Config aus Datei neu geladen.");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : String(err));
    } finally {
      setReloading(false);
    }
  }

  async function handlePreview() {
    if (!config) return;
    setPreviewing(true);
    try {
      const data = await previewAdminRiskConfig(config);
      setPreviewData(data);
      setPreviewOpen(true);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : String(err));
    } finally {
      setPreviewing(false);
    }
  }

  async function handleSave() {
    if (!config) return;
    setSaving(true);
    try {
      const data = await updateAdminRiskConfig(config);
      setMeta(data);
      setConfig(deepClone(data.config));
      setOriginal(deepClone(data.config));
      setConfirmSaveOpen(false);
      toast.success("Risk-Config gespeichert und Cache neu geladen.");
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      toast.error(`Speichern fehlgeschlagen: ${msg}`);
    } finally {
      setSaving(false);
    }
  }

  function handleReset() {
    if (original) setConfig(deepClone(original));
  }

  if (loading) {
    return (
      <Card>
        <CardContent className="py-10 text-center text-muted-foreground">
          <Loader2 className="size-5 animate-spin mx-auto mb-2" />
          Lade Risk-Config…
        </CardContent>
      </Card>
    );
  }

  if (error && !config) {
    return (
      <Alert variant="destructive">
        <AlertTriangle className="size-4" />
        <AlertDescription>Risk-Config konnte nicht geladen werden: {error}</AlertDescription>
      </Alert>
    );
  }

  if (!config || !meta) return null;

  const maturitySum = ["vvt", "dsfa", "avv", "tom", "velocity"].reduce(
    (sum, k) => sum + (config.maturity.weights[k as keyof typeof config.maturity.weights] ?? 0),
    0,
  );
  const maturityValid = Math.abs(maturitySum - 1.0) < 0.01;
  const thresholdsAscending = config.avv.level_thresholds.every(
    (t, i, arr) => i === 0 || t.max_score >= arr[i - 1].max_score,
  );
  const velocityValid =
    config.maturity.velocity.worst_days > config.maturity.velocity.optimal_days;
  const scoreRangeValid =
    config.avv.score_normalization.score_max > config.avv.score_normalization.score_min;
  const canSave = dirty && maturityValid && thresholdsAscending && velocityValid && scoreRangeValid;

  return (
    <AdminRiskConfigContext.Provider
      value={{ config, setConfig, meta, dirty, maturityValid, thresholdsAscending, velocityValid, scoreRangeValid, canSave }}
    >
      <div className="space-y-6 mb-8">
        {/* Header */}
        <Card>
          <CardHeader>
            <CardTitle>Risiko-Konfiguration</CardTitle>
            <CardDescription>
              Schwellenwerte, Gewichte und Matrizen der fünf Risiko-Modelle. Änderungen schreiben
              die YAML-Datei für das aktive Org-Profil und laden den Cache live nach.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="text-sm space-y-1">
              <p>
                <span className="text-muted-foreground">Profil:</span>{" "}
                <span className="font-medium">{meta.profile}</span>
                {meta.is_default && (
                  <span className="ml-2 text-xs text-muted-foreground">(Defaults — noch keine YAML)</span>
                )}
              </p>
              {meta.path && (
                <p className="text-xs text-muted-foreground truncate" title={meta.path}>
                  YAML: {meta.path}
                </p>
              )}
            </div>
            <div className="flex gap-2">
              <Button size="sm" variant="outline" onClick={() => void handleReload()} disabled={reloading}>
                {reloading ? (
                  <Loader2 className="size-4 animate-spin mr-1" />
                ) : (
                  <RefreshCw className="size-4 mr-1" />
                )}
                Aus Datei neu laden
              </Button>
            </div>
            {error && (
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
          </CardContent>
        </Card>

        <AdminRiskConfigAvvSection />
        <AdminRiskConfigDsfaSection />
        <AdminRiskConfigMaturitySection />

        {/* Action-Footer */}
        <div className="sticky bottom-0 z-10 -mx-4 px-4 py-3 border-t bg-background/95 backdrop-blur flex flex-wrap items-center justify-between gap-3">
          <div className="text-xs text-muted-foreground">
            {dirty ? "Ungespeicherte Änderungen" : "Keine Änderungen"}
          </div>
          <div className="flex gap-2 flex-wrap">
            <Button variant="outline" size="sm" onClick={() => void handlePreview()} disabled={previewing || !dirty}>
              {previewing ? (
                <Loader2 className="size-4 animate-spin mr-1" />
              ) : (
                <Eye className="size-4 mr-1" />
              )}
              Vorschau (Dry-Run)
            </Button>
            <Button variant="ghost" size="sm" onClick={handleReset} disabled={!dirty}>
              <RotateCcw className="size-4 mr-1" /> Zurücksetzen
            </Button>
            <Button size="sm" onClick={() => setConfirmSaveOpen(true)} disabled={!canSave}>
              <Save className="size-4 mr-1" /> Speichern
            </Button>
          </div>
        </div>

        {/* Preview-Dialog */}
        <Dialog open={previewOpen} onOpenChange={setPreviewOpen}>
          <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Vorschau: Auswirkungen der Änderungen</DialogTitle>
              <DialogDescription>
                Vergleich der aktuellen vs. neuen Konfiguration für synthetische Beispiel-Inputs.
                Es werden keine echten Daten verändert.
              </DialogDescription>
            </DialogHeader>
            {previewData && previewData.samples.length > 0 ? (
              <div className="space-y-3">
                {previewData.samples.map((s, idx) => (
                  <div key={idx} className="rounded border p-3">
                    <p className="text-sm font-medium">{s.name}</p>
                    <p className="text-xs text-muted-foreground mb-2">
                      Inputs: {JSON.stringify(s.inputs)}
                    </p>
                    <div className="grid grid-cols-2 gap-2 text-xs">
                      <div className="rounded bg-muted/40 p-2">
                        <div className="font-medium mb-1 text-muted-foreground">Aktuell</div>
                        <pre className="whitespace-pre-wrap">{JSON.stringify(s.current, null, 2)}</pre>
                      </div>
                      <div className="rounded bg-blue-50 dark:bg-blue-900/20 p-2">
                        <div className="font-medium mb-1 text-blue-700 dark:text-blue-300">Mit neuen Werten</div>
                        <pre className="whitespace-pre-wrap">{JSON.stringify(s.preview, null, 2)}</pre>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">Keine Vergleichsdaten verfügbar.</p>
            )}
          </DialogContent>
        </Dialog>

        {/* Speichern-Bestätigung */}
        <AlertDialog open={confirmSaveOpen} onOpenChange={setConfirmSaveOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Risk-Config wirklich speichern?</AlertDialogTitle>
              <AlertDialogDescription>
                Die Datei {meta.path ?? "(Profilpfad)"} wird überschrieben. Der vorherige Stand
                wird als <code>.bak.{`{timestamp}`}</code> gesichert.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel disabled={saving}>Abbrechen</AlertDialogCancel>
              <AlertDialogAction
                onClick={(e) => {
                  e.preventDefault();
                  void handleSave();
                }}
                disabled={saving}
              >
                {saving ? <Loader2 className="size-4 animate-spin mr-1" /> : null}
                Speichern
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </AdminRiskConfigContext.Provider>
  );
}
