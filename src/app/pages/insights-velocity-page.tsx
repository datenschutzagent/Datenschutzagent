import { useEffect, useState, useMemo } from "react";
import { AppLayout } from "../components/app-layout";
import { PageHeader } from "../components/page-header";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Skeleton } from "../components/ui/skeleton";
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from "recharts";
import { toast } from "sonner";
import { Clock, Zap, AlertCircle, GitBranch, TrendingUp, TrendingDown, Minus } from "lucide-react";
import {
  fetchRiskVelocity,
  fetchVelocityStats,
  type RiskTrend,
  type RiskVelocityResponse,
  type VelocityStats,
} from "../lib/api/insights";

function formatMonthLabel(ym: string): string {
  const [y, m] = ym.split("-");
  return new Date(Number(y), Number(m) - 1, 1).toLocaleDateString("de-DE", { month: "short", year: "2-digit" });
}

function fmtNum(n: number | null, suffix: string = ""): string {
  if (n == null) return "–";
  return `${n.toFixed(n < 10 ? 1 : 0)}${suffix}`;
}

const SEVERITY_LABEL: Record<string, string> = {
  critical: "Kritisch", high: "Hoch", medium: "Mittel", low: "Niedrig", info: "Info",
};

const SUBSCORE_LABEL: Record<string, string> = {
  vvt: "VVT",
  dsfa: "DSFA",
  avv: "AVV",
  tom: "TOM",
  velocity: "Velocity",
};

function TrendIndicator({ trend, delta }: { trend: RiskTrend; delta: number | null }) {
  if (trend === "unknown" || delta == null) {
    return <span className="text-xs text-muted-foreground">Kein Vergleichswert</span>;
  }
  if (trend === "up") {
    return (
      <span className="text-xs text-green-600 dark:text-green-400 font-medium inline-flex items-center gap-1">
        <TrendingUp className="size-3" /> +{delta.toFixed(1)}
      </span>
    );
  }
  if (trend === "down") {
    return (
      <span className="text-xs text-red-600 dark:text-red-400 font-medium inline-flex items-center gap-1">
        <TrendingDown className="size-3" /> {delta.toFixed(1)}
      </span>
    );
  }
  return (
    <span className="text-xs text-muted-foreground inline-flex items-center gap-1">
      <Minus className="size-3" /> {delta.toFixed(1)}
    </span>
  );
}

export function InsightsVelocityPage() {
  const [data, setData] = useState<VelocityStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [riskVelocity, setRiskVelocity] = useState<RiskVelocityResponse | null>(null);

  useEffect(() => {
    setLoading(true);
    fetchVelocityStats()
      .then(setData)
      .catch(() => toast.error("Velocity-Daten konnten nicht geladen werden."))
      .finally(() => setLoading(false));
    fetchRiskVelocity()
      .then(setRiskVelocity)
      .catch(() => {
        // Optional — silent fail; Karte zeigt dann nichts.
      });
  }, []);

  const dsrTrend = useMemo(() => {
    if (!data) return [];
    return data.dsr.trend.map((t) => ({ ...t, label: formatMonthLabel(t.month) }));
  }, [data]);

  const breachTrend = useMemo(() => {
    if (!data) return [];
    return data.breach.trend.map((t) => ({ ...t, label: formatMonthLabel(t.month) }));
  }, [data]);

  return (
    <AppLayout>
      <PageHeader
        title="Bearbeitungs-Velocity"
        description="Time-to-X für DSR, Datenpannen, Findings sowie Workflow-Funnels aus den Aktivitätsprotokollen."
      />
      {loading ? (
        <div className="space-y-4">
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      ) : !data ? (
        <Card><CardContent className="py-12 text-center text-muted-foreground">Keine Daten geladen.</CardContent></Card>
      ) : (
        <div className="space-y-6">
          {/* Risk-Velocity (Compliance-Reife-Trend pro Abteilung) */}
          {riskVelocity && riskVelocity.enabled && riskVelocity.departments.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <TrendingUp className="size-4" /> Compliance-Reife-Trend
                </CardTitle>
                <CardDescription>
                  Veränderung des Composite-Scores pro Abteilung gegenüber dem Wert vor {riskVelocity.windowDays} Tagen.
                  Trend gilt als signifikant ab {riskVelocity.significantChangePct} Punkten Delta.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-xs text-muted-foreground text-left border-b">
                        <th className="py-2 pr-3 font-medium">Abteilung</th>
                        <th className="py-2 pr-3 font-medium">Aktuell</th>
                        <th className="py-2 pr-3 font-medium">Vorher</th>
                        <th className="py-2 pr-3 font-medium">Trend</th>
                        {Object.keys(SUBSCORE_LABEL).map((key) => (
                          <th key={key} className="py-2 pr-3 font-medium hidden md:table-cell">
                            {SUBSCORE_LABEL[key]}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {riskVelocity.departments.map((row) => (
                        <tr key={row.department} className="border-b last:border-0">
                          <td className="py-2 pr-3 font-medium">{row.department}</td>
                          <td className="py-2 pr-3">{row.currentComposite.toFixed(1)}</td>
                          <td className="py-2 pr-3 text-muted-foreground">
                            {row.previousComposite != null ? row.previousComposite.toFixed(1) : "–"}
                          </td>
                          <td className="py-2 pr-3">
                            <TrendIndicator trend={row.trend} delta={row.delta} />
                          </td>
                          {Object.keys(SUBSCORE_LABEL).map((key) => {
                            const sub = row.subScores[key as keyof typeof row.subScores];
                            return (
                              <td key={key} className="py-2 pr-3 hidden md:table-cell">
                                <TrendIndicator trend={sub.trend} delta={sub.delta} />
                              </td>
                            );
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          )}

          {/* DSR-MTTR */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <Clock className="size-4" /> DSR-Bearbeitungsdauer
              </CardTitle>
              <CardDescription>
                Median {fmtNum(data.dsr.medianDays, " Tage")} · P90 {fmtNum(data.dsr.p90Days, " Tage")} · {data.dsr.sampleSize} beantwortete Anfragen
                {data.dsr.slaCompliancePct != null && <> · <span className={data.dsr.slaCompliancePct >= 95 ? "text-green-600 font-medium" : data.dsr.slaCompliancePct >= 80 ? "text-yellow-600 font-medium" : "text-red-600 font-medium"}>{data.dsr.slaCompliancePct}% innerhalb 30 Tage</span></>}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid md:grid-cols-2 gap-4">
                <div>
                  <div className="text-sm font-medium mb-2">Verteilung</div>
                  <ResponsiveContainer width="100%" height={170}>
                    <BarChart data={data.dsr.histogram} margin={{ top: 4, right: 4, bottom: 4, left: -20 }}>
                      <XAxis dataKey="bucket" tick={{ fontSize: 11 }} />
                      <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                      <Tooltip />
                      <Bar dataKey="count" fill="#2563eb" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
                {dsrTrend.length > 0 && (
                  <div>
                    <div className="text-sm font-medium mb-2">Median über die letzten Monate</div>
                    <ResponsiveContainer width="100%" height={170}>
                      <LineChart data={dsrTrend} margin={{ top: 4, right: 4, bottom: 4, left: -20 }}>
                        <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                        <YAxis tick={{ fontSize: 11 }} />
                        <Tooltip />
                        <Line type="monotone" dataKey="medianDays" name="Median (Tage)" stroke="#2563eb" />
                        <Line type="monotone" dataKey="p90Days" name="P90 (Tage)" stroke="#ea580c" strokeDasharray="3 3" />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                )}
              </div>
              {data.dsr.byRequestType.length > 0 && (
                <div className="mt-4">
                  <div className="text-sm font-medium mb-2">Nach Anfrage-Typ</div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="border-b border-border bg-muted/40 text-xs">
                        <tr>
                          <th className="text-left py-2 px-3 font-medium text-muted-foreground">Typ</th>
                          <th className="text-right py-2 px-3 font-medium text-muted-foreground">Anzahl</th>
                          <th className="text-right py-2 px-3 font-medium text-muted-foreground">Median (Tage)</th>
                          <th className="text-right py-2 px-3 font-medium text-muted-foreground">P90 (Tage)</th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.dsr.byRequestType.map((t) => (
                          <tr key={t.requestType} className="border-b border-border last:border-0 hover:bg-muted/30">
                            <td className="py-2 px-3 font-medium">{t.requestType}</td>
                            <td className="py-2 px-3 text-right">{t.sampleSize}</td>
                            <td className="py-2 px-3 text-right">{fmtNum(t.medianDays)}</td>
                            <td className="py-2 px-3 text-right">{fmtNum(t.p90Days)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Breach Notification Speed */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <Zap className="size-4" /> Datenpannen-Meldegeschwindigkeit
              </CardTitle>
              <CardDescription>
                Median {fmtNum(data.breach.medianHoursToAuthority, " h")} bis Behörde · P90 {fmtNum(data.breach.p90HoursToAuthority, " h")} · {data.breach.sampleSize} gemeldete Pannen
                {data.breach.sla72hCompliancePct != null && <> · <span className={data.breach.sla72hCompliancePct >= 95 ? "text-green-600 font-medium" : data.breach.sla72hCompliancePct >= 80 ? "text-yellow-600 font-medium" : "text-red-600 font-medium"}>{data.breach.sla72hCompliancePct}% innerhalb 72h</span></>}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid md:grid-cols-2 gap-4">
                <div>
                  <div className="text-sm font-medium mb-2">Stunden bis Behördenmeldung</div>
                  <ResponsiveContainer width="100%" height={170}>
                    <BarChart data={data.breach.histogramAuthority} margin={{ top: 4, right: 4, bottom: 4, left: -20 }}>
                      <XAxis dataKey="bucket" tick={{ fontSize: 11 }} />
                      <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                      <Tooltip />
                      <Bar dataKey="count" fill="#ea580c" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
                {breachTrend.length > 0 && (
                  <div>
                    <div className="text-sm font-medium mb-2">Median Stunden im Zeitverlauf</div>
                    <ResponsiveContainer width="100%" height={170}>
                      <LineChart data={breachTrend} margin={{ top: 4, right: 4, bottom: 4, left: -20 }}>
                        <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                        <YAxis tick={{ fontSize: 11 }} />
                        <Tooltip />
                        <Legend wrapperStyle={{ fontSize: 11 }} />
                        <Line type="monotone" dataKey="medianDays" name="Median (h)" stroke="#ea580c" />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                )}
              </div>
              {data.breach.medianHoursToSubjects != null && (
                <p className="text-xs text-muted-foreground mt-3">
                  Median Stunden bis Betroffenen-Benachrichtigung: <strong>{fmtNum(data.breach.medianHoursToSubjects, " h")}</strong>
                </p>
              )}
            </CardContent>
          </Card>

          {/* Findings Resolution Velocity */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <AlertCircle className="size-4" /> Findings-Resolution-Velocity
              </CardTitle>
              <CardDescription>Tage von „open" bis „fixed/accepted/overruled" pro Schweregrad.</CardDescription>
            </CardHeader>
            <CardContent>
              {data.findings.length === 0 ? (
                <p className="text-sm text-muted-foreground">Noch keine geschlossenen Findings.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="border-b border-border bg-muted/40 text-xs">
                      <tr>
                        <th className="text-left py-2 px-3 font-medium text-muted-foreground">Schweregrad</th>
                        <th className="text-right py-2 px-3 font-medium text-muted-foreground">Anzahl</th>
                        <th className="text-right py-2 px-3 font-medium text-muted-foreground">Median (Tage)</th>
                        <th className="text-right py-2 px-3 font-medium text-muted-foreground">P90 (Tage)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.findings.map((f) => (
                        <tr key={f.severity} className="border-b border-border last:border-0 hover:bg-muted/30">
                          <td className="py-2 px-3 font-medium">{SEVERITY_LABEL[f.severity] ?? f.severity}</td>
                          <td className="py-2 px-3 text-right">{f.sampleSize}</td>
                          <td className="py-2 px-3 text-right">{fmtNum(f.medianDays)}</td>
                          <td className="py-2 px-3 text-right">{fmtNum(f.p90Days)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Workflow-Funnels */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <GitBranch className="size-4" /> Workflow-Übergänge
              </CardTitle>
              <CardDescription>
                Durchschnittliche Stunden zwischen aufeinanderfolgenden Aktivitäts-Events – identifiziert, wo Vorgänge hängenbleiben.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {data.funnels.map((f) => (
                <div key={f.entity}>
                  <div className="text-sm font-medium mb-2">{f.entity}</div>
                  {f.steps.length === 0 ? (
                    <p className="text-xs text-muted-foreground">Keine Übergänge protokolliert.</p>
                  ) : (
                    <ul className="space-y-1.5 text-sm">
                      {f.steps.map((s) => (
                        <li key={s.transition} className="flex items-center justify-between gap-3 px-3 py-1.5 rounded border border-border">
                          <span className="font-mono text-xs truncate">{s.transition}</span>
                          <span className="text-xs text-muted-foreground whitespace-nowrap">
                            ⌀ {fmtNum(s.avgHours, " h")} · Median {fmtNum(s.medianHours, " h")} · n={s.sampleSize}
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              ))}
            </CardContent>
          </Card>

          <p className="text-xs text-muted-foreground text-right">
            Stand: {new Date(data.generatedAt).toLocaleString("de-DE")}
          </p>
        </div>
      )}
    </AppLayout>
  );
}
