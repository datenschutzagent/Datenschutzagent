import { CheckCircle2, XCircle } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../ui/card";
import { Input } from "../ui/input";
import { Label } from "../ui/label";
import { Slider } from "../ui/slider";
import { Switch } from "../ui/switch";
import { useAdminRiskConfig } from "./AdminRiskConfigContext";

const SEVERITY_KEYS = ["critical", "high", "medium", "low", "info"] as const;
const MATURITY_KEYS = ["vvt", "dsfa", "avv", "tom", "velocity"] as const;

function deepClone<T>(v: T): T {
  return structuredClone(v);
}

export function AdminRiskConfigMaturitySection() {
  const { config, setConfig, maturityValid, velocityValid } = useAdminRiskConfig();

  const maturitySum = MATURITY_KEYS.reduce(
    (sum, k) => sum + (config.maturity.weights[k] ?? 0),
    0,
  );

  return (
    <>
      {/* Case-Score-Gewichte */}
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

      {/* Maturity */}
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

      {/* Risk-Velocity */}
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
    </>
  );
}
