import { useState, useEffect, useMemo } from "react";
import { AppLayout } from "../components/app-layout";
import { PageHeader } from "../components/page-header";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Skeleton } from "../components/ui/skeleton";
import { Link } from "react-router";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  AreaChart, Area, Legend,
} from "recharts";
import {
  listFindings,
  downloadAllFindingsExport,
  downloadBlob,
  getFindingStats,
  type ApiFinding,
  type FindingStatsResult,
} from "../lib/api";
import { severityColors, severityLabels, findingStatusLabels } from "../lib/mock-data";
import type { FindingSeverity } from "../lib/mock-data";
import { Download, Loader2, ShieldAlert, AlertTriangle, AlertCircle, Info, TrendingUp } from "lucide-react";
import { toast } from "sonner";

const SEVERITY_ORDER: FindingSeverity[] = ["critical", "high", "medium", "low", "info"];
const SEVERITY_CHART_COLORS: Record<string, string> = {
  critical: "#dc2626",
  high: "#ea580c",
  medium: "#ca8a04",
  low: "#2563eb",
  info: "#6b7280",
};

function SeverityIcon({ severity }: { severity: FindingSeverity }) {
  switch (severity) {
    case "critical": return <ShieldAlert className="size-3.5" />;
    case "high": return <AlertTriangle className="size-3.5" />;
    case "medium": return <AlertCircle className="size-3.5" />;
    default: return <Info className="size-3.5" />;
  }
}

function formatMonth(ym: string): string {
  const [year, month] = ym.split("-");
  const date = new Date(Number(year), Number(month) - 1, 1);
  return date.toLocaleDateString("de-DE", { month: "short", year: "2-digit" });
}

export function ComplianceOverviewPage() {
  const [findings, setFindings] = useState<ApiFinding[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [exportLoading, setExportLoading] = useState(false);
  const [severityFilter, setSeverityFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("open");
  const [offset, setOffset] = useState(0);
  const [stats, setStats] = useState<FindingStatsResult | null>(null);
  const PAGE_SIZE = 50;

  const loadFindings = async (newOffset = 0, sev = severityFilter, st = statusFilter) => {
    setLoading(true);
    try {
      const result = await listFindings({
        severity: sev !== "all" ? sev : undefined,
        status: st !== "all" ? st : undefined,
        limit: PAGE_SIZE,
        offset: newOffset,
      });
      setFindings(result.items);
      setTotal(result.total);
      setOffset(newOffset);
    } catch {
      toast.error("Findings konnten nicht geladen werden");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadFindings(0, severityFilter, statusFilter);
  }, [severityFilter, statusFilter]);

  useEffect(() => {
    getFindingStats()
      .then(setStats)
      .catch(() => {/* stats sind optional */});
  }, []);

  const orgWideSeverityData = useMemo(() => {
    if (!stats) return null;
    return SEVERITY_ORDER.map((sev) => ({
      name: severityLabels[sev],
      count: stats.bySeverity[sev] ?? 0,
      severity: sev,
    }));
  }, [stats]);

  const trendData = useMemo(() => {
    if (!stats?.trend?.length) return null;
    return stats.trend.map((t) => ({ ...t, label: formatMonth(t.month) }));
  }, [stats]);

  const handleExport = async () => {
    setExportLoading(true);
    try {
      const blob = await downloadAllFindingsExport({
        severity: severityFilter !== "all" ? severityFilter : undefined,
        status: statusFilter !== "all" ? statusFilter : undefined,
        format: "csv",
      });
      const date = new Date().toISOString().slice(0, 10);
      downloadBlob(blob, `Compliance-Findings-${date}.csv`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Export fehlgeschlagen");
    } finally {
      setExportLoading(false);
    }
  };

  return (
    <AppLayout>
      <PageHeader
        title="Compliance-Übersicht"
        description="Organisationsweite Findings über alle Vorgänge"
      />

      {/* Org-wide severity stats + trend */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Offene Findings nach Schweregrad</CardTitle>
            <CardDescription>Org-weite Gesamtzahlen (alle Vorgänge)</CardDescription>
          </CardHeader>
          <CardContent>
            {!stats ? (
              <Skeleton className="h-40 w-full" />
            ) : (
              <ResponsiveContainer width="100%" height={160}>
                <BarChart data={orgWideSeverityData!} margin={{ top: 4, right: 4, bottom: 4, left: -20 }}>
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip formatter={(v: number) => [v, "Findings"]} />
                  <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                    {orgWideSeverityData!.map((entry) => (
                      <Cell key={entry.severity} fill={SEVERITY_CHART_COLORS[entry.severity] ?? "#6b7280"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <TrendingUp className="size-4" />
              6-Monats-Trend
            </CardTitle>
            <CardDescription>Neue Findings pro Monat nach Schweregrad</CardDescription>
          </CardHeader>
          <CardContent>
            {!stats ? (
              <Skeleton className="h-40 w-full" />
            ) : !trendData ? (
              <div className="h-40 flex items-center justify-center text-sm text-muted-foreground">
                Noch keine Trend-Daten verfügbar
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={160}>
                <AreaChart data={trendData} margin={{ top: 4, right: 4, bottom: 4, left: -20 }}>
                  <XAxis dataKey="label" tick={{ fontSize: 10 }} />
                  <YAxis tick={{ fontSize: 10 }} />
                  <Tooltip />
                  <Legend wrapperStyle={{ fontSize: 10 }} />
                  {(["critical", "high", "medium", "low"] as FindingSeverity[]).map((sev) => (
                    <Area
                      key={sev}
                      type="monotone"
                      dataKey={sev}
                      name={severityLabels[sev]}
                      stackId="1"
                      stroke={SEVERITY_CHART_COLORS[sev]}
                      fill={SEVERITY_CHART_COLORS[sev]}
                      fillOpacity={0.6}
                    />
                  ))}
                </AreaChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Department breakdown + Top failing checks */}
      {stats && (stats.byDepartment.length > 0 || stats.topFailingChecks.length > 0) && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          {stats.byDepartment.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Findings nach Abteilung</CardTitle>
                <CardDescription>Offene Findings (top {stats.byDepartment.length})</CardDescription>
              </CardHeader>
              <CardContent className="p-0">
                <div className="divide-y divide-border">
                  {stats.byDepartment.slice(0, 8).map((dept) => (
                    <div key={dept.department} className="flex items-center justify-between px-4 py-2.5 text-sm">
                      <span className="font-medium truncate max-w-[160px]" title={dept.department}>
                        {dept.department || "–"}
                      </span>
                      <div className="flex items-center gap-1.5 flex-shrink-0">
                        {dept.critical > 0 && (
                          <Badge className={`${severityColors.critical} text-xs px-1.5 py-0`}>{dept.critical}</Badge>
                        )}
                        {dept.high > 0 && (
                          <Badge className={`${severityColors.high} text-xs px-1.5 py-0`}>{dept.high}</Badge>
                        )}
                        {dept.medium > 0 && (
                          <Badge className={`${severityColors.medium} text-xs px-1.5 py-0`}>{dept.medium}</Badge>
                        )}
                        <span className="text-muted-foreground ml-1">{dept.total}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {stats.topFailingChecks.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Häufigste offene Checks</CardTitle>
                <CardDescription>Top {stats.topFailingChecks.length} nach Häufigkeit</CardDescription>
              </CardHeader>
              <CardContent className="p-0">
                <div className="divide-y divide-border">
                  {stats.topFailingChecks.map((check, i) => (
                    <div key={check.checkName} className="flex items-start justify-between px-4 py-2.5 text-sm gap-2">
                      <div className="flex items-start gap-2 min-w-0">
                        <span className="text-muted-foreground text-xs mt-0.5 w-4 flex-shrink-0">{i + 1}.</span>
                        <div className="min-w-0">
                          <p className="font-medium truncate" title={check.checkName}>{check.checkName}</p>
                          <p className="text-xs text-muted-foreground">{check.category}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-1.5 flex-shrink-0">
                        {(check.severityBreakdown.critical ?? 0) > 0 && (
                          <Badge className={`${severityColors.critical} text-xs px-1.5 py-0`}>
                            {check.severityBreakdown.critical}
                          </Badge>
                        )}
                        {(check.severityBreakdown.high ?? 0) > 0 && (
                          <Badge className={`${severityColors.high} text-xs px-1.5 py-0`}>
                            {check.severityBreakdown.high}
                          </Badge>
                        )}
                        <span className="text-muted-foreground font-medium">{check.count}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* Resolution velocity */}
      {stats && stats.resolutionVelocity.length > 0 && (
        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="text-base">Behebungsgeschwindigkeit</CardTitle>
            <CardDescription>Ø Tage vom Fund bis zur Behebung (nach Schweregrad)</CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-muted/40">
                    <th className="text-left py-2 px-4 font-medium text-muted-foreground">Schweregrad</th>
                    <th className="text-right py-2 px-4 font-medium text-muted-foreground">Ø Tage bis Behebung</th>
                    <th className="text-right py-2 px-4 font-medium text-muted-foreground">Stichprobe</th>
                  </tr>
                </thead>
                <tbody>
                  {["critical", "high", "medium", "low", "info"]
                    .map((sev) => stats.resolutionVelocity.find((v) => v.severity === sev))
                    .filter(Boolean)
                    .map((v) => (
                      <tr key={v!.severity} className="border-b border-border last:border-0">
                        <td className="py-2 px-4">
                          <Badge className={severityColors[v!.severity as FindingSeverity]}>
                            {severityLabels[v!.severity as FindingSeverity]}
                          </Badge>
                        </td>
                        <td className="py-2 px-4 text-right font-mono font-semibold">
                          {v!.avgDaysToFix}d
                        </td>
                        <td className="py-2 px-4 text-right text-muted-foreground">
                          {v!.sampleSize}
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Filters + export */}
      <div className="flex flex-col sm:flex-row sm:flex-wrap sm:items-center gap-3 mb-4">
        <Select value={severityFilter} onValueChange={(v) => setSeverityFilter(v)}>
          <SelectTrigger className="w-full sm:w-44">
            <SelectValue placeholder="Schweregrad" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Alle Schweregrade</SelectItem>
            {SEVERITY_ORDER.map((sev) => (
              <SelectItem key={sev} value={sev}>{severityLabels[sev]}</SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select value={statusFilter} onValueChange={(v) => setStatusFilter(v)}>
          <SelectTrigger className="w-full sm:w-44">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Alle Status</SelectItem>
            <SelectItem value="open">Offen</SelectItem>
            <SelectItem value="accepted">Akzeptiert</SelectItem>
            <SelectItem value="overruled">Überfahren</SelectItem>
            <SelectItem value="fixed">Behoben</SelectItem>
          </SelectContent>
        </Select>

        <div className="sm:ml-auto">
          <Button variant="outline" size="sm" className="w-full sm:w-auto" onClick={handleExport} disabled={exportLoading}>
            {exportLoading ? <Loader2 className="size-4 mr-2 animate-spin" /> : <Download className="size-4 mr-2" />}
            CSV exportieren
          </Button>
        </div>
      </div>

      {/* Findings table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            Findings
            <span className="ml-2 text-sm font-normal text-muted-foreground">({total} gesamt)</span>
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {loading ? (
            <div className="p-6 space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : findings.length === 0 ? (
            <div className="p-8 text-center text-muted-foreground">
              Keine Findings für die gewählten Filter.
            </div>
          ) : (
            <>
              {/* Mobile card view (< md) */}
              <div className="md:hidden divide-y divide-border">
                {findings.map((f) => (
                  <div key={f.id} className="p-4 space-y-2">
                    <div className="flex items-center justify-between gap-2 flex-wrap">
                      <Badge className={`${severityColors[f.severity]} flex items-center gap-1 w-fit`}>
                        <SeverityIcon severity={f.severity as FindingSeverity} />
                        {severityLabels[f.severity as FindingSeverity]}
                      </Badge>
                      <Badge variant="outline">{findingStatusLabels[f.status] ?? f.status}</Badge>
                    </div>
                    <p className="font-medium text-sm">{f.checkName}</p>
                    {f.description && (
                      <p className="text-xs text-muted-foreground line-clamp-2">{f.description}</p>
                    )}
                    <div className="flex items-center justify-between text-xs text-muted-foreground">
                      <span>{f.category}</span>
                      {f.caseId && (
                        <Link
                          to={`/cases/${f.caseId}`}
                          className="text-blue-600 dark:text-blue-400 hover:underline truncate max-w-[160px]"
                        >
                          {f.caseTitle ?? f.caseId.slice(0, 8)}
                        </Link>
                      )}
                    </div>
                  </div>
                ))}
              </div>

              {/* Desktop table view (≥ md) */}
              <div className="hidden md:block overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border bg-muted/40">
                      <th className="text-left py-3 px-4 font-medium text-muted-foreground">Schweregrad</th>
                      <th className="text-left py-3 px-4 font-medium text-muted-foreground">Checkname</th>
                      <th className="text-left py-3 px-4 font-medium text-muted-foreground">Kategorie</th>
                      <th className="text-left py-3 px-4 font-medium text-muted-foreground">Status</th>
                      <th className="text-left py-3 px-4 font-medium text-muted-foreground">Vorgang</th>
                    </tr>
                  </thead>
                  <tbody>
                    {findings.map((f) => (
                      <tr key={f.id} className="border-b border-border last:border-0 hover:bg-muted/30 transition-colors">
                        <td className="py-3 px-4">
                          <Badge className={`${severityColors[f.severity]} flex items-center gap-1 w-fit`}>
                            <SeverityIcon severity={f.severity as FindingSeverity} />
                            {severityLabels[f.severity as FindingSeverity]}
                          </Badge>
                        </td>
                        <td className="py-3 px-4 max-w-xs">
                          <p className="font-medium truncate">{f.checkName}</p>
                          <p className="text-xs text-muted-foreground truncate">{f.description}</p>
                        </td>
                        <td className="py-3 px-4 text-muted-foreground">{f.category}</td>
                        <td className="py-3 px-4">
                          <Badge variant="outline">{findingStatusLabels[f.status] ?? f.status}</Badge>
                        </td>
                        <td className="py-3 px-4">
                          {f.caseId && (
                            <Link
                              to={`/cases/${f.caseId}`}
                              className="text-blue-600 dark:text-blue-400 hover:underline text-xs truncate block max-w-[180px]"
                            >
                              {f.caseTitle ?? f.caseId.slice(0, 8)}
                            </Link>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
          {/* Pagination */}
          {total > PAGE_SIZE && (
            <div className="flex items-center justify-between p-4 border-t border-border">
              <span className="text-sm text-muted-foreground">
                {offset + 1}–{Math.min(offset + PAGE_SIZE, total)} von {total}
              </span>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={offset === 0 || loading}
                  onClick={() => loadFindings(offset - PAGE_SIZE)}
                >
                  Zurück
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={offset + PAGE_SIZE >= total || loading}
                  onClick={() => loadFindings(offset + PAGE_SIZE)}
                >
                  Weiter
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </AppLayout>
  );
}
