import { Link, useNavigate } from "react-router";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { DashboardStats } from "../components/dashboard-stats";
import { NewCaseDialog } from "../components/new-case-dialog";
import { mockCases, statusLabels, statusColors } from "../lib/mock-data";
import { Plus, Search, Filter, FileText, AlertCircle, CheckCircle2, Clock, LayoutDashboard } from "lucide-react";
import { useState } from "react";

export function CasesPage() {
  const navigate = useNavigate();
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [isNewCaseDialogOpen, setIsNewCaseDialogOpen] = useState(false);

  const filteredCases = mockCases.filter((c) => {
    const matchesSearch = c.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         c.department.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus = statusFilter === "all" || c.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const getStatsForCase = (caseItem: typeof mockCases[0]) => {
    const critical = caseItem.findings.filter(f => f.severity === "critical" && f.status === "open").length;
    const high = caseItem.findings.filter(f => f.severity === "high" && f.status === "open").length;
    const fixed = caseItem.findings.filter(f => f.status === "fixed").length;
    return { critical, high, fixed, total: caseItem.findings.length };
  };

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <header className="bg-white border-b border-slate-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-semibold text-slate-900">Datenschutz-Agent</h1>
              <p className="text-sm text-slate-600 mt-1">Universität • Forschungsvorhaben</p>
            </div>
            <nav className="flex items-center gap-6">
              <Link to="/" className="text-sm font-medium text-blue-600">
                Vorgänge
              </Link>
              <Link to="/playbooks" className="text-sm font-medium text-slate-600 hover:text-slate-900">
                Playbooks
              </Link>
              <div className="h-6 w-px bg-slate-300" />
              <div className="flex items-center gap-2">
                <div className="size-8 rounded-full bg-blue-600 flex items-center justify-center text-white text-sm font-medium">
                  DS
                </div>
                <span className="text-sm text-slate-700">DSB Team</span>
              </div>
            </nav>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Page Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-xl font-semibold text-slate-900">Vorgänge</h2>
            <p className="text-sm text-slate-600 mt-1">
              {filteredCases.length} {filteredCases.length === 1 ? "Vorgang" : "Vorgänge"}
            </p>
          </div>
          <Button className="gap-2" onClick={() => setIsNewCaseDialogOpen(true)}>
            <Plus className="size-4" />
            Neuer Vorgang
          </Button>
        </div>

        {/* Tabs for Dashboard vs List View */}
        <Tabs defaultValue="list" className="space-y-6">
          <TabsList>
            <TabsTrigger value="list" className="gap-2">
              <FileText className="size-4" />
              Vorgänge
            </TabsTrigger>
            <TabsTrigger value="dashboard" className="gap-2">
              <LayoutDashboard className="size-4" />
              Dashboard
            </TabsTrigger>
          </TabsList>

          {/* List View */}
          <TabsContent value="list" className="space-y-6">
            {/* Filters */}
            <Card>
              <CardContent className="pt-6">
                <div className="flex gap-4">
                  <div className="flex-1 relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-slate-400" />
                    <Input
                      placeholder="Suche nach Titel oder Fachbereich..."
                      value={searchTerm}
                      onChange={(e) => setSearchTerm(e.target.value)}
                      className="pl-10"
                    />
                  </div>
                  <Select value={statusFilter} onValueChange={setStatusFilter}>
                    <SelectTrigger className="w-[200px]">
                      <Filter className="size-4 mr-2" />
                      <SelectValue placeholder="Status filtern" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">Alle Status</SelectItem>
                      <SelectItem value="intake">Intake</SelectItem>
                      <SelectItem value="in_review">In Vorprüfung</SelectItem>
                      <SelectItem value="questions_pending">Rückfragen ausstehend</SelectItem>
                      <SelectItem value="revision">Revision</SelectItem>
                      <SelectItem value="ready_for_decision">Entscheidungsvorlage</SelectItem>
                      <SelectItem value="completed">Abgeschlossen</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </CardContent>
            </Card>

            {/* Cases List */}
            <div className="space-y-4">
              {filteredCases.map((caseItem) => {
                const stats = getStatsForCase(caseItem);
                return (
                  <Card
                    key={caseItem.id}
                    className="hover:shadow-md transition-shadow cursor-pointer"
                    onClick={() => navigate(`/cases/${caseItem.id}`)}
                  >
                    <CardHeader>
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center gap-3 mb-2">
                            <CardTitle className="text-lg">{caseItem.title}</CardTitle>
                            <Badge className={statusColors[caseItem.status]}>
                              {statusLabels[caseItem.status]}
                            </Badge>
                          </div>
                          <CardDescription className="flex items-center gap-4 text-sm">
                            <span>{caseItem.department}</span>
                            <span>•</span>
                            <span>{caseItem.caseType}</span>
                            <span>•</span>
                            <span>Erstellt: {new Date(caseItem.createdAt).toLocaleDateString("de-DE")}</span>
                          </CardDescription>
                        </div>
                      </div>
                    </CardHeader>
                    <CardContent>
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-6 text-sm">
                          <div className="flex items-center gap-2">
                            <FileText className="size-4 text-slate-400" />
                            <span className="text-slate-600">{caseItem.documents.length} Dokumente</span>
                          </div>
                          {stats.critical > 0 && (
                            <div className="flex items-center gap-2">
                              <AlertCircle className="size-4 text-red-600" />
                              <span className="text-red-600 font-medium">{stats.critical} kritisch</span>
                            </div>
                          )}
                          {stats.high > 0 && (
                            <div className="flex items-center gap-2">
                              <AlertCircle className="size-4 text-orange-600" />
                              <span className="text-orange-600 font-medium">{stats.high} hoch</span>
                            </div>
                          )}
                          {stats.fixed > 0 && (
                            <div className="flex items-center gap-2">
                              <CheckCircle2 className="size-4 text-green-600" />
                              <span className="text-green-600">{stats.fixed} behoben</span>
                            </div>
                          )}
                        </div>
                        <div className="flex items-center gap-3 text-sm text-slate-600">
                          <Clock className="size-4" />
                          <span>Playbook: {caseItem.playbookVersion}</span>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>

            {filteredCases.length === 0 && (
              <Card>
                <CardContent className="py-12 text-center">
                  <FileText className="size-12 text-slate-300 mx-auto mb-4" />
                  <p className="text-slate-600">Keine Vorgänge gefunden</p>
                  <p className="text-sm text-slate-500 mt-1">
                    Versuchen Sie, Ihre Suchkriterien anzupassen
                  </p>
                </CardContent>
              </Card>
            )}
          </TabsContent>

          {/* Dashboard View */}
          <TabsContent value="dashboard">
            <DashboardStats />
          </TabsContent>
        </Tabs>
      </main>

      {/* New Case Dialog */}
      <NewCaseDialog open={isNewCaseDialogOpen} onOpenChange={setIsNewCaseDialogOpen} />
    </div>
  );
}