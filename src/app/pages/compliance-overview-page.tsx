import { useState, useEffect, useMemo } from "react";
import { AppLayout } from "../components/app-layout";
import { PageHeader } from "../components/page-header";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Skeleton } from "../components/ui/skeleton";
import { Link } from "react-router";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import {
  listFindings,
  downloadAllFindingsExport,
  downloadBlob,
  type ApiFinding,
} from "../lib/api";
import { severityColors, severityLabels, findingStatusLabels } from "../lib/mock-data";
import type { FindingSeverity } from "../lib/mock-data";
import { Download, Loader2, ShieldAlert, AlertTriangle, AlertCircle, Info } from "lucide-react";
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

export function ComplianceOverviewPage() {
  const [findings, setFindings] = useState<ApiFinding[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [exportLoading, setExportLoading] = useState(false);
  const [severityFilter, setSeverityFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("open");
  const [offset, setOffset] = useState(0);
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

  const chartData = useMemo(() => {
    return SEVERITY_ORDER.map((sev) => ({
      name: severityLabels[sev],
      count: findings.filter((f) => f.severity === sev).length,
      severity: sev,
    }));
  }, [findings]);

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

      {/* Summary chart */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Findings nach Schweregrad</CardTitle>
            <CardDescription>Aktuelle Filterung ({total} Findings gesamt)</CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={160}>
              <BarChart data={chartData} margin={{ top: 4, right: 4, bottom: 4, left: -20 }}>
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v: number) => [v, "Findings"]} />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {chartData.map((entry) => (
                    <Cell key={entry.severity} fill={SEVERITY_CHART_COLORS[entry.severity] ?? "#6b7280"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Schnellübersicht</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {SEVERITY_ORDER.map((sev) => {
              const count = findings.filter((f) => f.severity === sev).length;
              return (
                <div key={sev} className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Badge className={severityColors[sev]}>{severityLabels[sev]}</Badge>
                  </div>
                  <span className="text-sm font-medium">{count}</span>
                </div>
              );
            })}
          </CardContent>
        </Card>
      </div>

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
