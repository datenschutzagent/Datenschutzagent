import { Trash2, XCircle } from "lucide-react";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Label } from "../ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../ui/select";
import { Slider } from "../ui/slider";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../ui/card";
import type { RiskLevel } from "../../lib/api/types/risk-config";
import { useAdminRiskConfig } from "./AdminRiskConfigContext";

const RISK_LEVELS: RiskLevel[] = ["low", "medium", "high", "critical"];

function deepClone<T>(v: T): T {
  return structuredClone(v);
}

export function AdminRiskConfigAvvSection() {
  const { config, setConfig, thresholdsAscending, scoreRangeValid } = useAdminRiskConfig();

  return (
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
  );
}
