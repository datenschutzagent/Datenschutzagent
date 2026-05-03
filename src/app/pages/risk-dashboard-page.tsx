import { useState, useEffect, useMemo } from "react";
import { AppLayout } from "../components/app-layout";
import { PageHeader } from "../components/page-header";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Skeleton } from "../components/ui/skeleton";
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from "recharts";
import { request } from "../lib/api/core";
import { toast } from "sonner";
import { AlertTriangle, ShieldAlert, Users, Globe, TrendingUp, Building2 } from "lucide-react";
import { DepartmentDrilldownPanel } from "../components/department-drilldown-panel";

interface DeptRiskRow {
  department: string;
  criticalOpenFindings: number;
  highOpenFindings: number;
  activeBreaches: number;
  overdueDsr: number;
  avgAvvRiskScore: number | null;
  specialCategoryCases: number;
  intlTransferCases: number;
  activeCases: number;
  compositeRiskScore: number;
}

interface TrendItem {
  month: string;
  critical: number;
  high: number;
  medium: number;
  low: number;
  info: number;
}

interface OrgRiskData {
  generatedAt: string;
  deptRisk: DeptRiskRow[];
  topRiskDepartments: string[];
  orgFindingsTrend: TrendItem[];
  totalOpenCritical: number;
  totalActiveBreaches: number;
  totalOverdueDsr: number;
  departmentsAtRisk: number;
}

function riskColor(score: number): string {
  if (score >= 75) return "text-red-600 dark:text-red-400";
  if (score >= 40) return "text-orange-600 dark:text-orange-400";
  if (score >= 15) return "text-yellow-600 dark:text-yellow-500";
  return "text-green-600 dark:text-green-400";
}

function riskBg(score: number): string {
  if (score >= 75) return "bg-red-100 dark:bg-red-900/30";
  if (score >= 40) return "bg-orange-100 dark:bg-orange-900/30";
  if (score >= 15) return "bg-yellow-100 dark:bg-yellow-900/30";
  return "bg-green-100 dark:bg-green-900/30";
}

function riskLabel(score: number): string {
  if (score >= 75) return "Kritisch";
  if (score >= 40) return "Hoch";
  if (score >= 15) return "Mittel";
  return "Niedrig";
}

function formatMonth(ym: string): string {
  const [year, month] = ym.split("-");
  const date = new Date(Number(year), Number(month) - 1, 1);
  return date.toLocaleDateString("de-DE", { month: "short", year: "2-digit" });
}

function toCamel(obj: Record<string, unknown>): Record<string, unknown> {
  const result: Record<string, unknown> = {};
  for (const [key, val] of Object.entries(obj)) {
    const camel = key.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase());
    if (val && typeof val === "object" && !Array.isArray(val)) {
      result[camel] = toCamel(val as Record<string, unknown>);
    } else if (Array.isArray(val)) {
      result[camel] = val.map((v) =>
        v && typeof v === "object" ? toCamel(v as Record<string, unknown>) : v
      );
    } else {
      result[camel] = val;
    }
  }
  return result;
}

export function RiskDashboardPage() {
  const [data, setData] = useState<OrgRiskData | null>(null);
  const [loading, setLoading] = useState(true);
  const [sortBy, setSortBy] = useState<keyof DeptRiskRow>("compositeRiskScore");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [drillDept, setDrillDept] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    request<Record<string, unknown>>("GET", "/analytics/org-risk")
      .then((raw) => setData(toCamel(raw) as unknown as OrgRiskData))
      .catch(() => toast.error("Risiko-Dashboard konnte nicht geladen werden."))
      .finally(() => setLoading(false));
  }, []);

  const sortedDepts = useMemo(() => {
    if (!data) return [];
    return [...data.deptRisk].sort((a, b) => {
      const av = a[sortBy] ?? 0;
      const bv = b[sortBy] ?? 0;
      if (typeof av === "string" && typeof bv === "string") {
        return sortDir === "asc" ? av.localeCompare(bv) : bv.localeCompare(av);
      }
      return sortDir === "asc" ? Number(av) - Number(bv) : Number(bv) - Number(av);
    });
  }, [data, sortBy, sortDir]);

  const trendData = useMemo(() => {
    if (!data?.orgFindingsTrend?.length) return null;
    return data.orgFindingsTrend.map((t) => ({ ...t, label: formatMonth(t.month) }));
  }, [data]);

  function toggleSort(col: keyof DeptRiskRow) {
    if (sortBy === col) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(col);
      setSortDir("desc");
    }
  }

  const SEVERITY_COLORS = {
    critical: "#dc2626",
    high: "#ea580c",
    medium: "#ca8a04",
    low: "#2563eb",
    info: "#6b7280",
  };

  return (
    <AppLayout>
      <PageHeader
        title="Risiko-Dashboard"
        description="Organisationsweite Risikolage über alle Compliance-Bereiche"
      />

      {loading ? (
        <div className="space-y-4">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-24 w-full" />)}
          </div>
          <Skeleton className="h-48 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      ) : !data ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            Risiko-Daten konnten nicht geladen werden.
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-6">
          {/* Org-weite KPIs */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <Card className={data.totalOpenCritical > 0 ? "border-red-300 dark:border-red-700" : ""}>
              <CardContent className="pt-4 pb-3">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs text-muted-foreground">Kritische Findings</span>
                  <ShieldAlert className="size-4 text-red-500" />
                </div>
                <div className={`text-2xl font-bold ${data.totalOpenCritical > 0 ? "text-red-600" : ""}`}>
                  {data.totalOpenCritical}
                </div>
              </CardContent>
            </Card>

            <Card className={data.totalActiveBreaches > 0 ? "border-orange-300 dark:border-orange-700" : ""}>
              <CardContent className="pt-4 pb-3">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs text-muted-foreground">Aktive Pannen</span>
                  <AlertTriangle className="size-4 text-orange-500" />
                </div>
                <div className={`text-2xl font-bold ${data.totalActiveBreaches > 0 ? "text-orange-600" : ""}`}>
                  {data.totalActiveBreaches}
                </div>
              </CardContent>
            </Card>

            <Card className={data.totalOverdueDsr > 0 ? "border-yellow-300 dark:border-yellow-700" : ""}>
              <CardContent className="pt-4 pb-3">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs text-muted-foreground">Überfällige DSR</span>
                  <Users className="size-4 text-yellow-600" />
                </div>
                <div className={`text-2xl font-bold ${data.totalOverdueDsr > 0 ? "text-yellow-600" : ""}`}>
                  {data.totalOverdueDsr}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-4 pb-3">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs text-muted-foreground">Abteilungen mit Risiko</span>
                  <Building2 className="size-4 text-muted-foreground" />
                </div>
                <div className="text-2xl font-bold">{data.departmentsAtRisk}</div>
                <div className="text-xs text-muted-foreground mt-0.5">von {data.deptRisk.length}</div>
              </CardContent>
            </Card>
          </div>

          {/* 6-Monats-Trend */}
          {trendData && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <TrendingUp className="size-4" /> Org-weiter Finding-Trend (6 Monate)
                </CardTitle>
                <CardDescription>Alle neuen Findings pro Monat nach Schweregrad</CardDescription>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={180}>
                  <AreaChart data={trendData} margin={{ top: 4, right: 4, bottom: 4, left: -20 }}>
                    <XAxis dataKey="label" tick={{ fontSize: 10 }} />
                    <YAxis tick={{ fontSize: 10 }} />
                    <Tooltip />
                    <Legend wrapperStyle={{ fontSize: 10 }} />
                    {(["critical", "high", "medium", "low"] as const).map((sev) => (
                      <Area
                        key={sev}
                        type="monotone"
                        dataKey={sev}
                        name={sev === "critical" ? "Kritisch" : sev === "high" ? "Hoch" : sev === "medium" ? "Mittel" : "Niedrig"}
                        stackId="1"
                        stroke={SEVERITY_COLORS[sev]}
                        fill={SEVERITY_COLORS[sev]}
                        fillOpacity={0.6}
                      />
                    ))}
                  </AreaChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          )}

          {/* Abteilungs-Risikotabelle */}
          {sortedDepts.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Risiko nach Abteilung</CardTitle>
                <CardDescription>Klick auf Spaltentitel zum Sortieren. Composite Score: kritische Findings ×25 + hohe ×10 + Pannen ×15 + überfällige DSR ×8 + AVV-Risiko ×0,3</CardDescription>
              </CardHeader>
              <CardContent className="p-0">
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border bg-muted/40 text-xs">
                        {[
                          { key: "department" as keyof DeptRiskRow, label: "Abteilung" },
                          { key: "compositeRiskScore" as keyof DeptRiskRow, label: "Risiko-Score" },
                          { key: "criticalOpenFindings" as keyof DeptRiskRow, label: "Krit. Findings" },
                          { key: "highOpenFindings" as keyof DeptRiskRow, label: "Hohe Findings" },
                          { key: "activeBreaches" as keyof DeptRiskRow, label: "Aktive Pannen" },
                          { key: "overdueDsr" as keyof DeptRiskRow, label: "Überfällige DSR" },
                          { key: "avgAvvRiskScore" as keyof DeptRiskRow, label: "AVV-Risiko Ø" },
                          { key: "specialCategoryCases" as keyof DeptRiskRow, label: "Art. 9" },
                          { key: "intlTransferCases" as keyof DeptRiskRow, label: "Drittland" },
                        ].map(({ key, label }) => (
                          <th
                            key={key}
                            onClick={() => toggleSort(key)}
                            className="text-left py-2.5 px-3 font-medium text-muted-foreground cursor-pointer hover:text-foreground select-none whitespace-nowrap"
                          >
                            {label}
                            {sortBy === key && (
                              <span className="ml-1">{sortDir === "desc" ? "↓" : "↑"}</span>
                            )}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {sortedDepts.map((dept) => (
                        <tr
                          key={dept.department}
                          onClick={() => setDrillDept(dept.department)}
                          className="border-b border-border last:border-0 hover:bg-muted/30 transition-colors cursor-pointer"
                          title="Klicken für Detail-Drilldown"
                        >
                          <td className="py-2.5 px-3 font-medium max-w-[160px] truncate" title={dept.department}>
                            {dept.department}
                          </td>
                          <td className="py-2.5 px-3">
                            <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold ${riskBg(dept.compositeRiskScore)} ${riskColor(dept.compositeRiskScore)}`}>
                              {dept.compositeRiskScore} — {riskLabel(dept.compositeRiskScore)}
                            </span>
                          </td>
                          <td className="py-2.5 px-3 text-center">
                            {dept.criticalOpenFindings > 0 ? (
                              <span className="font-semibold text-red-600">{dept.criticalOpenFindings}</span>
                            ) : <span className="text-muted-foreground">–</span>}
                          </td>
                          <td className="py-2.5 px-3 text-center">
                            {dept.highOpenFindings > 0 ? (
                              <span className="font-semibold text-orange-600">{dept.highOpenFindings}</span>
                            ) : <span className="text-muted-foreground">–</span>}
                          </td>
                          <td className="py-2.5 px-3 text-center">
                            {dept.activeBreaches > 0 ? (
                              <Badge className="bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300 text-xs">
                                {dept.activeBreaches}
                              </Badge>
                            ) : <span className="text-muted-foreground">–</span>}
                          </td>
                          <td className="py-2.5 px-3 text-center">
                            {dept.overdueDsr > 0 ? (
                              <Badge className="bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300 text-xs">
                                {dept.overdueDsr}
                              </Badge>
                            ) : <span className="text-muted-foreground">–</span>}
                          </td>
                          <td className="py-2.5 px-3 text-center text-muted-foreground">
                            {dept.avgAvvRiskScore != null ? dept.avgAvvRiskScore : "–"}
                          </td>
                          <td className="py-2.5 px-3 text-center">
                            {dept.specialCategoryCases > 0 ? (
                              <span className="text-orange-600 font-medium flex items-center justify-center gap-1">
                                <ShieldAlert className="size-3" />{dept.specialCategoryCases}
                              </span>
                            ) : <span className="text-muted-foreground">–</span>}
                          </td>
                          <td className="py-2.5 px-3 text-center">
                            {dept.intlTransferCases > 0 ? (
                              <span className="text-blue-600 font-medium flex items-center justify-center gap-1">
                                <Globe className="size-3" />{dept.intlTransferCases}
                              </span>
                            ) : <span className="text-muted-foreground">–</span>}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Handlungsempfehlungen */}
          {data.deptRisk.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Handlungsempfehlungen</CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2 text-sm">
                  {data.totalOpenCritical > 0 && (
                    <li className="flex items-start gap-2">
                      <AlertTriangle className="size-4 text-red-500 mt-0.5 flex-shrink-0" />
                      <span>
                        <strong>{data.totalOpenCritical} kritische Findings</strong> sind org-weit offen.{" "}
                        {data.topRiskDepartments.length > 0 && (
                          <>Schwerpunkt: {data.topRiskDepartments.slice(0, 3).join(", ")}.</>
                        )}
                      </span>
                    </li>
                  )}
                  {data.totalActiveBreaches > 0 && (
                    <li className="flex items-start gap-2">
                      <AlertTriangle className="size-4 text-orange-500 mt-0.5 flex-shrink-0" />
                      <span>
                        <strong>{data.totalActiveBreaches} aktive Datenpannen</strong> erfordern Aufmerksamkeit — 72h-Frist prüfen.
                      </span>
                    </li>
                  )}
                  {data.totalOverdueDsr > 0 && (
                    <li className="flex items-start gap-2">
                      <AlertTriangle className="size-4 text-yellow-600 mt-0.5 flex-shrink-0" />
                      <span>
                        <strong>{data.totalOverdueDsr} DSR-Anfragen</strong> sind überfällig (Frist Art. 12 Abs. 3 DSGVO überschritten).
                      </span>
                    </li>
                  )}
                  {data.deptRisk.some((d) => d.specialCategoryCases > 0) && (
                    <li className="flex items-start gap-2">
                      <ShieldAlert className="size-4 text-orange-500 mt-0.5 flex-shrink-0" />
                      <span>
                        Vorgänge mit <strong>besonderen Datenkategorien (Art. 9)</strong> erfordern erhöhte Schutzmaßnahmen und ggf. DSFA.
                      </span>
                    </li>
                  )}
                  {data.totalOpenCritical === 0 && data.totalActiveBreaches === 0 && data.totalOverdueDsr === 0 && (
                    <li className="text-green-600 dark:text-green-400">
                      Keine kritischen Handlungsbedarfe identifiziert.
                    </li>
                  )}
                </ul>
              </CardContent>
            </Card>
          )}

          <p className="text-xs text-muted-foreground text-right">
            Stand: {data.generatedAt ? new Date(data.generatedAt).toLocaleString("de-DE") : "–"}
          </p>
        </div>
      )}
      <DepartmentDrilldownPanel
        department={drillDept}
        open={drillDept !== null}
        onOpenChange={(o) => { if (!o) setDrillDept(null); }}
      />
    </AppLayout>
  );
}
