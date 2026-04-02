import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";
import { Badge } from "./ui/badge";
import { Progress } from "./ui/progress";
import {
  FileText,
  CircleAlert,
  CheckCircle2,
  Users,
  BookOpen,
  Calendar,
  AlertTriangle,
  Clock,
} from "lucide-react";
import { useState, useEffect, useMemo } from "react";
import { Link } from "react-router";
import { mockCases } from "../lib/mock-data";
import { getPlaybooks, type ApiCase, type ApiPlaybook } from "../lib/api";

interface DashboardStatsProps {
  cases?: ApiCase[];
}

const SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"] as const;
const STATUS_ORDER = ["open", "accepted", "overruled", "fixed"] as const;
const SEVERITY_LABELS: Record<string, string> = { critical: "Kritisch", high: "Hoch", medium: "Mittel", low: "Niedrig", info: "Info" };
const STATUS_LABELS: Record<string, string> = { open: "Offen", accepted: "Akzeptiert", overruled: "Überfahren", fixed: "Behoben" };

function complianceScore(casesForDept: ApiCase[]): number {
  const allFindings = casesForDept.flatMap((c) => c.findings);
  const total = allFindings.length;
  if (total === 0) return 100;
  const critOpen = allFindings.filter((f) => f.severity === "critical" && f.status === "open").length;
  const highOpen = allFindings.filter((f) => f.severity === "high" && f.status === "open").length;
  const medOpen = allFindings.filter((f) => f.severity === "medium" && f.status === "open").length;
  const penalty = (critOpen * 40 + highOpen * 20 + medOpen * 5) / Math.max(total, 1) * 100;
  return Math.max(0, Math.round(100 - penalty));
}

function scoreColor(score: number): string {
  if (score >= 80) return "text-green-700 dark:text-green-400";
  if (score >= 60) return "text-amber-700 dark:text-amber-400";
  return "text-red-700 dark:text-red-400";
}

function scoreBarColor(score: number): string {
  if (score >= 80) return "[&>div]:bg-green-500";
  if (score >= 60) return "[&>div]:bg-amber-500";
  return "[&>div]:bg-red-500";
}

export function DashboardStats({ cases: casesProp }: DashboardStatsProps = {}) {
  const cases = casesProp ?? (mockCases as unknown as ApiCase[]);
  const [playbooks, setPlaybooks] = useState<ApiPlaybook[]>([]);

  useEffect(() => {
    getPlaybooks().then(setPlaybooks).catch(() => setPlaybooks([]));
  }, []);

  const totalCases = cases.length;
  const activeCases = cases.filter(c =>
    c.status === "in_review" || c.status === "questions_pending" || c.status === "revision"
  ).length;
  const completedCases = cases.filter(c => c.status === "completed").length;
  const readyForDecision = cases.filter(c => c.status === "ready_for_decision").length;

  const totalFindings = cases.reduce((sum, c) => sum + c.findings.length, 0);
  const criticalFindings = cases.reduce((sum, c) =>
    sum + c.findings.filter(f => f.severity === "critical" && f.status === "open").length, 0
  );
  const fixedFindings = cases.reduce((sum, c) =>
    sum + c.findings.filter(f => f.status === "fixed").length, 0
  );

  const totalDocuments = cases.reduce((sum, c) => sum + c.documents.length, 0);
  const activePlaybooks = playbooks.filter(pb => pb.isActive).length;
  const playbookDepartments = new Set(playbooks.map(pb => pb.department).filter(Boolean)).size;

  const recentCases = [...cases]
    .sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime())
    .slice(0, 5);

  // Findings-Matrix: severity × status counts
  const findingsMatrix = useMemo(() => {
    return STATUS_ORDER.map((status) => ({
      status,
      counts: SEVERITY_ORDER.map((severity) =>
        cases.reduce(
          (sum, c) => sum + c.findings.filter((f) => f.severity === severity && f.status === status).length,
          0
        )
      ),
    }));
  }, [cases]);

  // Deadline analysis
  const deadlineStats = useMemo(() => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const in7Days = new Date(today);
    in7Days.setDate(today.getDate() + 7);
    const activeCaseList = cases.filter((c) => c.status !== "completed");
    const overdue = activeCaseList.filter((c) => c.deadline && new Date(c.deadline) < today);
    const dueThisWeek = activeCaseList.filter((c) => {
      if (!c.deadline) return false;
      const d = new Date(c.deadline);
      return d >= today && d <= in7Days;
    });
    const noDeadline = activeCaseList.filter((c) => !c.deadline);
    return { overdue, dueThisWeek, noDeadline };
  }, [cases]);

  // Compliance-Score pro Abteilung
  const departmentScores = useMemo(() => {
    const depts = Array.from(new Set(cases.map((c) => c.department))).sort();
    return depts.map((dept) => {
      const deptCases = cases.filter((c) => c.department === dept);
      const score = complianceScore(deptCases);
      const openCritical = deptCases.flatMap((c) => c.findings).filter((f) => f.severity === "critical" && f.status === "open").length;
      return { dept, score, caseCount: deptCases.length, openCritical };
    }).sort((a, b) => a.score - b.score);
  }, [cases]);

  return (
    <div className="space-y-6">
      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Aktive Vorgänge</CardTitle>
            <FileText className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-semibold">{activeCases}</div>
            <p className="text-xs text-muted-foreground mt-1">
              von {totalCases} gesamt
            </p>
            <div className="flex items-center gap-1 mt-2">
              <span className="text-xs text-muted-foreground">{completedCases} abgeschlossen</span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Kritische Findings</CardTitle>
            <CircleAlert className="size-4 text-red-600 dark:text-red-400" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-semibold text-red-600 dark:text-red-400">{criticalFindings}</div>
            <p className="text-xs text-muted-foreground mt-1">
              von {totalFindings} gesamt
            </p>
            <div className="flex items-center gap-1 mt-2">
              <span className="text-xs text-muted-foreground">{fixedFindings} behoben</span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Entscheidungsvorlage</CardTitle>
            <CheckCircle2 className="size-4 text-green-600 dark:text-green-400" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-semibold">{readyForDecision}</div>
            <p className="text-xs text-muted-foreground mt-1">
              bereit für Freigabe
            </p>
            <div className="flex items-center gap-1 mt-2">
              <span className="text-xs text-muted-foreground">bereit für Freigabe</span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Aktive Playbooks</CardTitle>
            <BookOpen className="size-4 text-blue-600 dark:text-blue-400" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-semibold">{activePlaybooks}</div>
            <p className="text-xs text-muted-foreground mt-1">
              {playbooks.length} gesamt
            </p>
            <div className="flex items-center gap-1 mt-2">
              <span className="text-xs text-muted-foreground">Für {playbookDepartments} Einheiten</span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Deadline overview */}
      {(deadlineStats.overdue.length > 0 || deadlineStats.dueThisWeek.length > 0) && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card className={deadlineStats.overdue.length > 0 ? "border-red-300 dark:border-red-700" : ""}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-red-700 dark:text-red-400">Überfällig</CardTitle>
              <AlertTriangle className="size-4 text-red-600 dark:text-red-400" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-semibold text-red-600 dark:text-red-400">{deadlineStats.overdue.length}</div>
              <p className="text-xs text-muted-foreground mt-1">aktive Vorgänge</p>
              {deadlineStats.overdue.length > 0 && (
                <ul className="mt-2 space-y-1">
                  {deadlineStats.overdue.slice(0, 3).map((c) => (
                    <li key={c.id} className="text-xs">
                      <Link to={`/cases/${c.id}`} className="text-red-700 dark:text-red-400 hover:underline truncate block">
                        {c.title}
                      </Link>
                      <span className="text-muted-foreground">
                        {new Date(c.deadline!).toLocaleDateString("de-DE")}
                      </span>
                    </li>
                  ))}
                  {deadlineStats.overdue.length > 3 && (
                    <li className="text-xs text-muted-foreground">+{deadlineStats.overdue.length - 3} weitere</li>
                  )}
                </ul>
              )}
            </CardContent>
          </Card>

          <Card className={deadlineStats.dueThisWeek.length > 0 ? "border-amber-300 dark:border-amber-700" : ""}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-amber-700 dark:text-amber-400">Diese Woche fällig</CardTitle>
              <Clock className="size-4 text-amber-600 dark:text-amber-400" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-semibold text-amber-600 dark:text-amber-400">{deadlineStats.dueThisWeek.length}</div>
              <p className="text-xs text-muted-foreground mt-1">in den nächsten 7 Tagen</p>
              {deadlineStats.dueThisWeek.length > 0 && (
                <ul className="mt-2 space-y-1">
                  {deadlineStats.dueThisWeek.slice(0, 3).map((c) => (
                    <li key={c.id} className="text-xs">
                      <Link to={`/cases/${c.id}`} className="text-amber-700 dark:text-amber-400 hover:underline truncate block">
                        {c.title}
                      </Link>
                      <span className="text-muted-foreground">
                        {new Date(c.deadline!).toLocaleDateString("de-DE")}
                      </span>
                    </li>
                  ))}
                  {deadlineStats.dueThisWeek.length > 3 && (
                    <li className="text-xs text-muted-foreground">+{deadlineStats.dueThisWeek.length - 3} weitere</li>
                  )}
                </ul>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Ohne Frist</CardTitle>
              <Calendar className="size-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-semibold">{deadlineStats.noDeadline.length}</div>
              <p className="text-xs text-muted-foreground mt-1">aktive Vorgänge ohne Fristangabe</p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Status Overview */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Vorgänge nach Status</CardTitle>
            <CardDescription>Verteilung aller Vorgänge</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {[
                { status: "in_review", label: "In Vorprüfung", count: cases.filter(c => c.status === "in_review").length, color: "bg-blue-100 text-blue-700 dark:bg-blue-900/50 dark:text-blue-300", bar: "bg-blue-100 dark:bg-blue-500" },
                { status: "questions_pending", label: "Rückfragen ausstehend", count: cases.filter(c => c.status === "questions_pending").length, color: "bg-amber-100 text-amber-700 dark:bg-amber-900/50 dark:text-amber-300", bar: "bg-amber-100 dark:bg-amber-500" },
                { status: "revision", label: "Revision", count: cases.filter(c => c.status === "revision").length, color: "bg-purple-100 text-purple-700 dark:bg-purple-900/50 dark:text-purple-300", bar: "bg-purple-100 dark:bg-purple-500" },
                { status: "ready_for_decision", label: "Entscheidungsvorlage", count: cases.filter(c => c.status === "ready_for_decision").length, color: "bg-green-100 text-green-700 dark:bg-green-900/50 dark:text-green-300", bar: "bg-green-100 dark:bg-green-500" },
                { status: "completed", label: "Abgeschlossen", count: completedCases, color: "bg-gray-100 text-gray-600 dark:bg-slate-800 dark:text-slate-400", bar: "bg-gray-100 dark:bg-slate-500" },
              ].map((item) => (
                <div key={item.status} className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Badge className={item.color}>{item.label}</Badge>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="w-32 bg-muted rounded-full h-2">
                      <div
                        className={`h-2 rounded-full ${item.bar ?? item.color.replace('text-', 'bg-').split(' ')[0]}`}
                        style={{ width: `${(item.count / totalCases) * 100}%` }}
                      />
                    </div>
                    <span className="text-sm font-medium w-8 text-right">{item.count}</span>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Findings nach Schweregrad</CardTitle>
            <CardDescription>Nur offene Findings</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {[
                { severity: "critical", label: "Kritisch", count: cases.reduce((sum, c) => sum + c.findings.filter(f => f.severity === "critical" && f.status === "open").length, 0), color: "bg-red-100 text-red-700 dark:bg-red-900/50 dark:text-red-300", bar: "bg-red-100 dark:bg-red-500" },
                { severity: "high", label: "Hoch", count: cases.reduce((sum, c) => sum + c.findings.filter(f => f.severity === "high" && f.status === "open").length, 0), color: "bg-orange-100 text-orange-700 dark:bg-orange-900/50 dark:text-orange-300", bar: "bg-orange-100 dark:bg-orange-500" },
                { severity: "medium", label: "Mittel", count: cases.reduce((sum, c) => sum + c.findings.filter(f => f.severity === "medium" && f.status === "open").length, 0), color: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/50 dark:text-yellow-300", bar: "bg-yellow-100 dark:bg-yellow-500" },
                { severity: "low", label: "Niedrig", count: cases.reduce((sum, c) => sum + c.findings.filter(f => f.severity === "low" && f.status === "open").length, 0), color: "bg-blue-100 text-blue-700 dark:bg-blue-900/50 dark:text-blue-300", bar: "bg-blue-100 dark:bg-blue-500" },
              ].map((item) => (
                <div key={item.severity} className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Badge className={item.color}>{item.label}</Badge>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="w-32 bg-muted rounded-full h-2">
                      <div
                        className={`h-2 rounded-full ${item.bar ?? item.color.replace('text-', 'bg-').split(' ')[0]}`}
                        style={{ width: `${item.count > 0 ? (item.count / (criticalFindings + 10)) * 100 : 0}%` }}
                      />
                    </div>
                    <span className="text-sm font-medium w-8 text-right">{item.count}</span>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Findings-Matrix: severity × status */}
      {totalFindings > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Findings-Matrix</CardTitle>
            <CardDescription>Anzahl der Findings nach Schweregrad und Status</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr>
                    <th className="text-left py-2 pr-4 font-medium text-muted-foreground w-28">Status</th>
                    {SEVERITY_ORDER.map((sev) => (
                      <th key={sev} className="text-center py-2 px-3 font-medium text-muted-foreground">{SEVERITY_LABELS[sev]}</th>
                    ))}
                    <th className="text-center py-2 px-3 font-medium text-muted-foreground">Gesamt</th>
                  </tr>
                </thead>
                <tbody>
                  {findingsMatrix.map(({ status, counts }) => {
                    const rowTotal = counts.reduce((s, n) => s + n, 0);
                    return (
                      <tr key={status} className="border-t border-border">
                        <td className="py-2 pr-4 font-medium text-foreground">{STATUS_LABELS[status]}</td>
                        {counts.map((count, i) => {
                          const sev = SEVERITY_ORDER[i];
                          const isHot = status === "open" && (sev === "critical" || sev === "high");
                          return (
                            <td key={sev} className="text-center py-2 px-3">
                              {count > 0 ? (
                                <span className={`inline-block min-w-[1.75rem] rounded px-1.5 py-0.5 font-semibold ${isHot ? "bg-red-100 text-red-700 dark:bg-red-900/50 dark:text-red-300" : "bg-muted text-foreground"}`}>
                                  {count}
                                </span>
                              ) : (
                                <span className="text-muted-foreground">–</span>
                              )}
                            </td>
                          );
                        })}
                        <td className="text-center py-2 px-3 font-semibold text-foreground">{rowTotal > 0 ? rowTotal : "–"}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Recent Activity */}
      <Card>
        <CardHeader>
          <CardTitle>Kürzlich aktualisiert</CardTitle>
          <CardDescription>Die 5 zuletzt bearbeiteten Vorgänge</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {recentCases.map((caseItem) => (
              <div key={caseItem.id} className="flex items-start gap-4 pb-4 border-b border-border last:border-0 last:pb-0">
                <div className="size-2 rounded-full bg-blue-600 dark:bg-blue-500 mt-2" />
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <h4 className="font-medium text-foreground">{caseItem.title}</h4>
                    <Badge variant="outline" className="text-xs">{caseItem.department}</Badge>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    {caseItem.findings.filter(f => f.status === "open").length} offene Findings
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-xs text-muted-foreground">
                    {new Date(caseItem.updatedAt).toLocaleDateString("de-DE")}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {new Date(caseItem.updatedAt).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Department Compliance Score */}
      {departmentScores.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Compliance-Score nach Organisationseinheit</CardTitle>
            <CardDescription>
              Basierend auf offenen kritischen/hohen/mittleren Findings. Grün ≥ 80, Gelb ≥ 60, Rot &lt; 60.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {departmentScores.map(({ dept, score, caseCount, openCritical }) => (
                <div key={dept} className="space-y-1">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 min-w-0">
                      <Users className="size-4 text-muted-foreground shrink-0" />
                      <span className="font-medium text-foreground truncate">{dept}</span>
                      <span className="text-xs text-muted-foreground shrink-0">({caseCount} {caseCount === 1 ? "Vorgang" : "Vorgänge"})</span>
                    </div>
                    <div className="flex items-center gap-2 shrink-0 ml-4">
                      {openCritical > 0 && (
                        <Badge className="bg-red-100 text-red-700 dark:bg-red-900/50 dark:text-red-300 text-xs">
                          {openCritical} krit.
                        </Badge>
                      )}
                      <span className={`text-sm font-semibold w-12 text-right ${scoreColor(score)}`}>{score}%</span>
                    </div>
                  </div>
                  <Progress value={score} className={`h-2 ${scoreBarColor(score)}`} />
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
