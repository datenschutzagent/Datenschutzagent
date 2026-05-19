import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import {
  AlertTriangle,
  CheckCircle2,
  Eye,
  Loader2,
  RefreshCw,
  RotateCcw,
  Save,
  Trash2,
  XCircle,
} from "lucide-react";

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
import { Checkbox } from "../ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "../ui/dialog";
import { Input } from "../ui/input";
import { Label } from "../ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../ui/select";
import { Slider } from "../ui/slider";
import { Switch } from "../ui/switch";

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
  RiskLevel,
} from "../../lib/api/types/risk-config";

const RISK_LEVELS: RiskLevel[] = ["low", "medium", "high", "critical"];

const LEVEL_BG: Record<RiskLevel, string> = {
  low: "bg-blue-100 dark:bg-blue-900/40",
  medium: "bg-yellow-100 dark:bg-yellow-900/40",
  high: "bg-orange-100 dark:bg-orange-900/40",
  critical: "bg-red-100 dark:bg-red-900/40",
};

const SEVERITY_KEYS = ["critical", "high", "medium", "low", "info"] as const;
const MATURITY_KEYS = ["vvt", "dsfa", "avv", "tom", "velocity"] as const;

function deepClone<T>(v: T): T {
  return JSON.parse(JSON.stringify(v)) as T;
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
    [config, original]
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

  // Maturity-Summe live berechnen
  const maturitySum = MATURITY_KEYS.reduce(
    (sum, k) => sum + (config.maturity.weights[k] ?? 0),
    0
  );
  const maturityValid = Math.abs(maturitySum - 1.0) < 0.01;

  // AVV-Thresholds aufsteigend?
  const thresholdsAscending = config.avv.level_thresholds.every(
    (t, i, arr) => i === 0 || t.max_score >= arr[i - 1].max_score
  );

  // Velocity worst > optimal?
  const velocityValid =
    config.maturity.velocity.worst_days > config.maturity.velocity.optimal_days;

  // Score-Range valide?
  const scoreRangeValid =
    config.avv.score_normalization.score_max > config.avv.score_normalization.score_min;

  const canSave = dirty && maturityValid && thresholdsAscending && velocityValid && scoreRangeValid;

  return (
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
            <Button size="sm" variant="outline" onClick={handleReload} disabled={reloading}>
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

      {/* Section 1: AVV-Risiko */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">AVV-Risiko (Auftragsverarbeiter)</CardTitle>
          <CardDescription>
            Schwellenwerte für die LLM-bewertete Risikoskala 1-5 und Dimensions-Gewichtungen.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <Label className="text-sm font-medium">Schwellenwerte (Score → Level)</Label>
            <div className="mt-2 space-y-2">
              {config.avv.level_thresholds.map((t, idx) => (
                <div key={idx} className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground w-16">max_score ≤</span>
                  <Input
                    type="number"
                    step="0.1"
                    min="0"
                    max="10"
                    value={t.max_score}
                    onChange={(e) => {
                      const v = parseFloat(e.target.value);
                      setConfig((c) => {
                        if (!c) return c;
                        const next = deepClone(c);
                        next.avv.level_thresholds[idx].max_score = Number.isNaN(v) ? 0 : v;
                        return next;
                      });
                    }}
                    className="w-24"
                  />
                  <Select
                    value={t.level}
                    onValueChange={(v) => {
                      setConfig((c) => {
                        if (!c) return c;
                        const next = deepClone(c);
                        next.avv.level_thresholds[idx].level = v as RiskLevel;
                        return next;
                      });
                    }}
                  >
                    <SelectTrigger className="w-32">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {RISK_LEVELS.map((lv) => (
                        <SelectItem key={lv} value={lv}>
                          {lv}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => {
                      setConfig((c) => {
                        if (!c) return c;
                        const next = deepClone(c);
                        next.avv.level_thresholds.splice(idx, 1);
                        return next;
                      });
                    }}
                  >
                    <Trash2 className="size-4" />
                  </Button>
                </div>
              ))}
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  setConfig((c) => {
                    if (!c) return c;
                    const next = deepClone(c);
                    next.avv.level_thresholds.push({ max_score: 5.0, level: "critical" });
                    return next;
                  });
                }}
              >
                + Schwelle hinzufügen
              </Button>
              {!thresholdsAscending && (
                <p className="text-xs text-red-600 dark:text-red-400 flex items-center gap-1">
                  <XCircle className="size-3" /> Schwellen müssen aufsteigend sortiert sein.
                </p>
              )}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 max-w-md">
            <div>
              <Label className="text-xs">Score-Min</Label>
              <Input
                type="number"
                step="0.5"
                value={config.avv.score_normalization.score_min}
                onChange={(e) =>
                  setConfig((c) => {
                    if (!c) return c;
                    const next = deepClone(c);
                    next.avv.score_normalization.score_min = parseFloat(e.target.value) || 0;
                    return next;
                  })
                }
              />
            </div>
            <div>
              <Label className="text-xs">Score-Max</Label>
              <Input
                type="number"
                step="0.5"
                value={config.avv.score_normalization.score_max}
                onChange={(e) =>
                  setConfig((c) => {
                    if (!c) return c;
                    const next = deepClone(c);
                    next.avv.score_normalization.score_max = parseFloat(e.target.value) || 0;
                    return next;
                  })
                }
              />
            </div>
          </div>
          {!scoreRangeValid && (
            <p className="text-xs text-red-600 dark:text-red-400 flex items-center gap-1">
              <XCircle className="size-3" /> Score-Max muss größer als Score-Min sein.
            </p>
          )}

          <div>
            <Label className="text-xs">Mindest-Konfidenz (0-1)</Label>
            <div className="flex items-center gap-3 mt-1 max-w-md">
              <Slider
                value={[config.avv.min_confidence * 100]}
                onValueChange={(values) =>
                  setConfig((c) => {
                    if (!c) return c;
                    const next = deepClone(c);
                    next.avv.min_confidence = (values[0] ?? 0) / 100;
                    return next;
                  })
                }
                min={0}
                max={100}
                step={5}
                className="flex-1"
              />
              <span className="text-sm tabular-nums w-12 text-right">
                {Math.round(config.avv.min_confidence * 100)}%
              </span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Section 2: DSFA-Screening */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">DSFA-Screening</CardTitle>
          <CardDescription>
            Gewichtete Mindestsumme der erfüllten EDSA-Faktoren, ab der eine DSFA verpflichtend ist.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="max-w-md">
            <Label className="text-xs">Pflicht-Schwelle (gewichtet)</Label>
            <Input
              type="number"
              step="0.5"
              min="0"
              value={config.dsfa_screening.required_threshold}
              onChange={(e) =>
                setConfig((c) => {
                  if (!c) return c;
                  const next = deepClone(c);
                  next.dsfa_screening.required_threshold = parseFloat(e.target.value) || 0;
                  return next;
                })
              }
              className="max-w-[120px]"
            />
          </div>

          <div>
            <Label className="text-sm font-medium">Faktoren ({config.dsfa_screening.factors.length})</Label>
            <p className="text-xs text-muted-foreground mb-2">
              Faktor-IDs müssen eindeutig sein. Keywords werden case-insensitiv geprüft.
            </p>
            <div className="overflow-x-auto rounded-md border">
              <table className="w-full text-sm">
                <thead className="bg-muted/40 text-xs">
                  <tr>
                    <th className="px-2 py-2 text-left font-medium">ID</th>
                    <th className="px-2 py-2 text-left font-medium">Label</th>
                    <th className="px-2 py-2 text-left font-medium">Gewicht</th>
                    <th className="px-2 py-2 text-left font-medium">case_flag</th>
                    <th className="px-2 py-2 text-left font-medium">Keywords (context, kommagetrennt)</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {config.dsfa_screening.factors.map((f, idx) => (
                    <tr key={idx}>
                      <td className="px-2 py-1">
                        <Input
                          value={f.id}
                          onChange={(e) =>
                            setConfig((c) => {
                              if (!c) return c;
                              const next = deepClone(c);
                              next.dsfa_screening.factors[idx].id = e.target.value;
                              return next;
                            })
                          }
                          className="h-8 text-xs"
                        />
                      </td>
                      <td className="px-2 py-1">
                        <Input
                          value={f.label}
                          onChange={(e) =>
                            setConfig((c) => {
                              if (!c) return c;
                              const next = deepClone(c);
                              next.dsfa_screening.factors[idx].label = e.target.value;
                              return next;
                            })
                          }
                          className="h-8 text-xs"
                        />
                      </td>
                      <td className="px-2 py-1">
                        <Input
                          type="number"
                          step="0.5"
                          min="0"
                          value={f.weight}
                          onChange={(e) =>
                            setConfig((c) => {
                              if (!c) return c;
                              const next = deepClone(c);
                              next.dsfa_screening.factors[idx].weight = parseFloat(e.target.value) || 0;
                              return next;
                            })
                          }
                          className="h-8 text-xs w-20"
                        />
                      </td>
                      <td className="px-2 py-1">
                        <Input
                          value={f.case_flag ?? ""}
                          placeholder="z.B. special_category_data"
                          onChange={(e) =>
                            setConfig((c) => {
                              if (!c) return c;
                              const next = deepClone(c);
                              next.dsfa_screening.factors[idx].case_flag =
                                e.target.value.trim() || null;
                              return next;
                            })
                          }
                          className="h-8 text-xs"
                        />
                      </td>
                      <td className="px-2 py-1">
                        <Input
                          value={f.keywords_processing_context.join(", ")}
                          onChange={(e) =>
                            setConfig((c) => {
                              if (!c) return c;
                              const next = deepClone(c);
                              next.dsfa_screening.factors[idx].keywords_processing_context = e.target.value
                                .split(",")
                                .map((s) => s.trim())
                                .filter(Boolean);
                              return next;
                            })
                          }
                          className="h-8 text-xs"
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Section 3: DSFA-Matrix */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">DSFA-Bewertung (ISO 27005 Matrix)</CardTitle>
          <CardDescription>
            5×5-Matrix für Likelihood × Severity → Risikolevel. DPO-Konsultations-Pflicht
            triggert bei Residualrisiko in den ausgewählten Levels.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="overflow-x-auto">
            <table className="text-xs">
              <thead>
                <tr>
                  <th></th>
                  {[1, 2, 3, 4, 5].map((s) => (
                    <th key={`hdr-${s}`} className="px-2 py-1 text-center font-medium text-muted-foreground">
                      S={s}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {[5, 4, 3, 2, 1].map((lik) => (
                  <tr key={`row-${lik}`}>
                    <th className="px-2 py-1 text-right font-medium text-muted-foreground">L={lik}</th>
                    {[1, 2, 3, 4, 5].map((sev) => {
                      const key = `${lik}_${sev}`;
                      const level = (config.dsfa_assessment.matrix[key] ?? "low") as RiskLevel;
                      return (
                        <td key={key} className="px-1 py-1">
                          <Select
                            value={level}
                            onValueChange={(v) =>
                              setConfig((c) => {
                                if (!c) return c;
                                const next = deepClone(c);
                                next.dsfa_assessment.matrix[key] = v as RiskLevel;
                                return next;
                              })
                            }
                          >
                            <SelectTrigger className={`h-9 w-24 ${LEVEL_BG[level]}`}>
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              {RISK_LEVELS.map((lv) => (
                                <SelectItem key={lv} value={lv}>
                                  {lv}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div>
            <Label className="text-sm font-medium">DSB-Konsultation erforderlich bei Residualrisiko in:</Label>
            <div className="flex flex-wrap gap-3 mt-2">
              {RISK_LEVELS.map((lv) => {
                const checked = config.dsfa_assessment.dpo_consultation_required_when_residual_in.includes(lv);
                return (
                  <label key={lv} className="flex items-center gap-2 text-sm cursor-pointer">
                    <Checkbox
                      checked={checked}
                      onCheckedChange={(state) =>
                        setConfig((c) => {
                          if (!c) return c;
                          const next = deepClone(c);
                          const set = new Set(next.dsfa_assessment.dpo_consultation_required_when_residual_in);
                          if (state === true) set.add(lv);
                          else set.delete(lv);
                          next.dsfa_assessment.dpo_consultation_required_when_residual_in = Array.from(set);
                          return next;
                        })
                      }
                    />
                    {lv}
                  </label>
                );
              })}
            </div>
          </div>

          <div className="max-w-md">
            <Label className="text-xs">Mindest-Konfidenz (DSFA)</Label>
            <div className="flex items-center gap-3 mt-1">
              <Slider
                value={[config.dsfa_assessment.min_confidence * 100]}
                onValueChange={(values) =>
                  setConfig((c) => {
                    if (!c) return c;
                    const next = deepClone(c);
                    next.dsfa_assessment.min_confidence = (values[0] ?? 0) / 100;
                    return next;
                  })
                }
                min={0}
                max={100}
                step={5}
                className="flex-1"
              />
              <span className="text-sm tabular-nums w-12 text-right">
                {Math.round(config.dsfa_assessment.min_confidence * 100)}%
              </span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Section 4: Case-Score-Gewichte */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Case-Score-Gewichte</CardTitle>
          <CardDescription>Strafpunkte pro Finding-Severity (kappt sich am max_score).</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 max-w-3xl">
            {SEVERITY_KEYS.map((sev) => (
              <div key={sev}>
                <Label className="text-xs capitalize">{sev}</Label>
                <Input
                  type="number"
                  min="0"
                  value={config.case_score.severity_weights[sev] ?? 0}
                  onChange={(e) =>
                    setConfig((c) => {
                      if (!c) return c;
                      const next = deepClone(c);
                      next.case_score.severity_weights[sev] = parseInt(e.target.value, 10) || 0;
                      return next;
                    })
                  }
                />
              </div>
            ))}
          </div>
          <div className="max-w-md">
            <Label className="text-xs">max_score</Label>
            <Input
              type="number"
              min="1"
              value={config.case_score.max_score}
              onChange={(e) =>
                setConfig((c) => {
                  if (!c) return c;
                  const next = deepClone(c);
                  next.case_score.max_score = parseInt(e.target.value, 10) || 1;
                  return next;
                })
              }
              className="max-w-[120px]"
            />
          </div>
        </CardContent>
      </Card>

      {/* Section 5: Maturity */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Compliance-Reife (Maturity)</CardTitle>
          <CardDescription>
            Gewichte der fünf Sub-Scores müssen sich auf 1.0 summieren. Velocity-Score wird
            linear interpoliert von optimal_days (=100) bis worst_days (=0).
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <Label className="text-sm font-medium">Sub-Score-Gewichte</Label>
            <div className="grid md:grid-cols-5 gap-3 mt-2">
              {MATURITY_KEYS.map((k) => (
                <div key={k}>
                  <Label className="text-xs uppercase">{k}</Label>
                  <Input
                    type="number"
                    step="0.05"
                    min="0"
                    max="1"
                    value={config.maturity.weights[k] ?? 0}
                    onChange={(e) =>
                      setConfig((c) => {
                        if (!c) return c;
                        const next = deepClone(c);
                        next.maturity.weights[k] = parseFloat(e.target.value) || 0;
                        return next;
                      })
                    }
                  />
                </div>
              ))}
            </div>
            <div className="mt-2 flex items-center gap-2 text-sm">
              <span className="text-muted-foreground">Summe:</span>
              <span
                className={`tabular-nums font-medium ${
                  maturityValid ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"
                }`}
              >
                {maturitySum.toFixed(2)}
              </span>
              {maturityValid ? (
                <CheckCircle2 className="size-4 text-green-600 dark:text-green-400" />
              ) : (
                <XCircle className="size-4 text-red-600 dark:text-red-400" />
              )}
              {!maturityValid && (
                <span className="text-xs text-red-600 dark:text-red-400">muss 1.00 betragen</span>
              )}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 max-w-md">
            <div>
              <Label className="text-xs">Velocity optimal_days (Score=100)</Label>
              <Input
                type="number"
                min="0"
                value={config.maturity.velocity.optimal_days}
                onChange={(e) =>
                  setConfig((c) => {
                    if (!c) return c;
                    const next = deepClone(c);
                    next.maturity.velocity.optimal_days = parseInt(e.target.value, 10) || 0;
                    return next;
                  })
                }
              />
            </div>
            <div>
              <Label className="text-xs">Velocity worst_days (Score=0)</Label>
              <Input
                type="number"
                min="1"
                value={config.maturity.velocity.worst_days}
                onChange={(e) =>
                  setConfig((c) => {
                    if (!c) return c;
                    const next = deepClone(c);
                    next.maturity.velocity.worst_days = parseInt(e.target.value, 10) || 1;
                    return next;
                  })
                }
              />
            </div>
          </div>
          {!velocityValid && (
            <p className="text-xs text-red-600 dark:text-red-400 flex items-center gap-1">
              <XCircle className="size-3" /> worst_days muss größer als optimal_days sein.
            </p>
          )}
        </CardContent>
      </Card>

      {/* Section 6: Risk-Velocity */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Risk-Velocity (Trend-Analyse)</CardTitle>
          <CardDescription>
            Vergleichsfenster und Schwelle für die Trend-Klassifikation up/down/stable im
            `/analytics/risk-velocity`-Endpoint.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-3">
            <Switch
              checked={config.risk_velocity.enabled}
              onCheckedChange={(checked) =>
                setConfig((c) => {
                  if (!c) return c;
                  const next = deepClone(c);
                  next.risk_velocity.enabled = checked;
                  return next;
                })
              }
            />
            <Label className="text-sm">Risk-Velocity-Endpoint aktiv</Label>
          </div>

          <div className="max-w-md space-y-3">
            <div>
              <Label className="text-xs">Vergleichsfenster (Tage)</Label>
              <div className="flex items-center gap-3 mt-1">
                <Slider
                  value={[config.risk_velocity.window_days]}
                  onValueChange={(values) =>
                    setConfig((c) => {
                      if (!c) return c;
                      const next = deepClone(c);
                      next.risk_velocity.window_days = values[0] ?? 90;
                      return next;
                    })
                  }
                  min={7}
                  max={365}
                  step={1}
                  className="flex-1"
                />
                <span className="text-sm tabular-nums w-14 text-right">
                  {config.risk_velocity.window_days} d
                </span>
              </div>
            </div>
            <div>
              <Label className="text-xs">Signifikanz-Schwelle (Punkte Delta)</Label>
              <div className="flex items-center gap-3 mt-1">
                <Slider
                  value={[config.risk_velocity.significant_change_pct]}
                  onValueChange={(values) =>
                    setConfig((c) => {
                      if (!c) return c;
                      const next = deepClone(c);
                      next.risk_velocity.significant_change_pct = values[0] ?? 15;
                      return next;
                    })
                  }
                  min={1}
                  max={50}
                  step={1}
                  className="flex-1"
                />
                <span className="text-sm tabular-nums w-14 text-right">
                  {config.risk_velocity.significant_change_pct}
                </span>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

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
  );
}
