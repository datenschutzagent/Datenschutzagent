import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../ui/card";
import { Checkbox } from "../ui/checkbox";
import { Input } from "../ui/input";
import { Label } from "../ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../ui/select";
import { Slider } from "../ui/slider";
import type { RiskLevel } from "../../lib/api/types/risk-config";
import { useAdminRiskConfig } from "./AdminRiskConfigContext";

const RISK_LEVELS: RiskLevel[] = ["low", "medium", "high", "critical"];

const LEVEL_BG: Record<RiskLevel, string> = {
  low: "bg-blue-100 dark:bg-blue-900/40",
  medium: "bg-yellow-100 dark:bg-yellow-900/40",
  high: "bg-orange-100 dark:bg-orange-900/40",
  critical: "bg-red-100 dark:bg-red-900/40",
};

function deepClone<T>(v: T): T {
  return structuredClone(v);
}

export function AdminRiskConfigDsfaSection() {
  const { config, setConfig } = useAdminRiskConfig();

  return (
    <>
      {/* DSFA-Screening */}
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

      {/* DSFA-Matrix */}
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
    </>
  );
}
