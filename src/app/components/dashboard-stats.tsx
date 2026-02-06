import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";
import { Badge } from "./ui/badge";
import { 
  TrendingUp, 
  TrendingDown,
  FileText, 
  AlertCircle, 
  CheckCircle2, 
  Clock,
  Users,
  BookOpen
} from "lucide-react";
import { useState, useEffect } from "react";
import { mockCases } from "../lib/mock-data";
import { getPlaybooks, type ApiCase, type ApiPlaybook } from "../lib/api";

interface DashboardStatsProps {
  cases?: ApiCase[];
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

  return (
    <div className="space-y-6">
      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Aktive Vorgänge</CardTitle>
            <FileText className="size-4 text-slate-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-semibold">{activeCases}</div>
            <p className="text-xs text-slate-600 mt-1">
              von {totalCases} gesamt
            </p>
            <div className="flex items-center gap-1 mt-2">
              <TrendingUp className="size-3 text-green-600" />
              <span className="text-xs text-green-600">+2 seit letzter Woche</span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Kritische Findings</CardTitle>
            <AlertCircle className="size-4 text-red-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-semibold text-red-600">{criticalFindings}</div>
            <p className="text-xs text-slate-600 mt-1">
              von {totalFindings} gesamt
            </p>
            <div className="flex items-center gap-1 mt-2">
              <TrendingDown className="size-3 text-green-600" />
              <span className="text-xs text-green-600">-3 seit letzter Woche</span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Entscheidungsvorlage</CardTitle>
            <CheckCircle2 className="size-4 text-green-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-semibold">{readyForDecision}</div>
            <p className="text-xs text-slate-600 mt-1">
              bereit für Freigabe
            </p>
            <div className="flex items-center gap-1 mt-2">
              <Clock className="size-3 text-slate-400" />
              <span className="text-xs text-slate-600">Ø 3.5 Tage in Review</span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Aktive Playbooks</CardTitle>
            <BookOpen className="size-4 text-blue-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-semibold">{activePlaybooks}</div>
            <p className="text-xs text-slate-600 mt-1">
              {playbooks.length} gesamt
            </p>
            <div className="flex items-center gap-1 mt-2">
              <span className="text-xs text-slate-600">Für {playbookDepartments} Fachbereiche</span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Status Overview */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Vorgänge nach Status</CardTitle>
            <CardDescription>Verteilung aller Forschungsvorhaben</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {[
                { status: "in_review", label: "In Vorprüfung", count: cases.filter(c => c.status === "in_review").length, color: "bg-blue-100 text-blue-700" },
                { status: "questions_pending", label: "Rückfragen ausstehend", count: cases.filter(c => c.status === "questions_pending").length, color: "bg-amber-100 text-amber-700" },
                { status: "revision", label: "Revision", count: cases.filter(c => c.status === "revision").length, color: "bg-purple-100 text-purple-700" },
                { status: "ready_for_decision", label: "Entscheidungsvorlage", count: cases.filter(c => c.status === "ready_for_decision").length, color: "bg-green-100 text-green-700" },
                { status: "completed", label: "Abgeschlossen", count: completedCases, color: "bg-gray-100 text-gray-600" },
              ].map((item) => (
                <div key={item.status} className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Badge className={item.color}>{item.label}</Badge>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="w-32 bg-slate-100 rounded-full h-2">
                      <div 
                        className={`h-2 rounded-full ${item.color.replace('text-', 'bg-').split(' ')[0]}`}
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
                { 
                  severity: "critical", 
                  label: "Kritisch", 
                  count: cases.reduce((sum, c) => sum + c.findings.filter(f => f.severity === "critical" && f.status === "open").length, 0),
                  color: "bg-red-100 text-red-700" 
                },
                { 
                  severity: "high", 
                  label: "Hoch", 
                  count: cases.reduce((sum, c) => sum + c.findings.filter(f => f.severity === "high" && f.status === "open").length, 0),
                  color: "bg-orange-100 text-orange-700" 
                },
                { 
                  severity: "medium", 
                  label: "Mittel", 
                  count: cases.reduce((sum, c) => sum + c.findings.filter(f => f.severity === "medium" && f.status === "open").length, 0),
                  color: "bg-yellow-100 text-yellow-700" 
                },
                { 
                  severity: "low", 
                  label: "Niedrig", 
                  count: cases.reduce((sum, c) => sum + c.findings.filter(f => f.severity === "low" && f.status === "open").length, 0),
                  color: "bg-blue-100 text-blue-700" 
                },
              ].map((item) => (
                <div key={item.severity} className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Badge className={item.color}>{item.label}</Badge>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="w-32 bg-slate-100 rounded-full h-2">
                      <div 
                        className={`h-2 rounded-full ${item.color.replace('text-', 'bg-').split(' ')[0]}`}
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

      {/* Recent Activity */}
      <Card>
        <CardHeader>
          <CardTitle>Kürzlich aktualisiert</CardTitle>
          <CardDescription>Die 5 zuletzt bearbeiteten Vorgänge</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {recentCases.map((caseItem) => (
              <div key={caseItem.id} className="flex items-start gap-4 pb-4 border-b last:border-0 last:pb-0">
                <div className="size-2 rounded-full bg-blue-600 mt-2" />
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <h4 className="font-medium text-slate-900">{caseItem.title}</h4>
                    <Badge variant="outline" className="text-xs">{caseItem.department}</Badge>
                  </div>
                  <p className="text-sm text-slate-600">
                    {caseItem.findings.filter(f => f.status === "open").length} offene Findings
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-xs text-slate-500">
                    {new Date(caseItem.updatedAt).toLocaleDateString("de-DE")}
                  </p>
                  <p className="text-xs text-slate-500">
                    {new Date(caseItem.updatedAt).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Department Overview */}
      <Card>
        <CardHeader>
          <CardTitle>Vorgänge nach Fachbereich</CardTitle>
          <CardDescription>Verteilung über alle Fachbereiche</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {Array.from(new Set(cases.map(c => c.department))).map((dept) => {
              const deptCases = cases.filter(c => c.department === dept);
              const deptActiveCases = deptCases.filter(c => 
                c.status === "in_review" || c.status === "questions_pending" || c.status === "revision"
              ).length;
              return (
                <div key={dept} className="p-4 border rounded-lg">
                  <div className="flex items-center gap-2 mb-2">
                    <Users className="size-4 text-blue-600" />
                    <h4 className="font-medium text-slate-900">{dept}</h4>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-slate-600">Aktiv:</span>
                    <span className="font-medium">{deptActiveCases}</span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-slate-600">Gesamt:</span>
                    <span className="font-medium">{deptCases.length}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
