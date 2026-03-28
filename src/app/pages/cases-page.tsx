import { Link, useNavigate } from "react-router";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { Skeleton } from "../components/ui/skeleton";
import { AppLayout } from "../components/app-layout";
import { PageHeader } from "../components/page-header";
import { DashboardStats } from "../components/dashboard-stats";
import { NewCaseDialog } from "../components/new-case-dialog";
import { CasesSearchFilter, CasesFilters } from "../components/cases-search-filter";
import { statusLabels, statusColors, priorityColors, priorityLabels } from "../lib/mock-data";
import { getCases, canEdit, type ApiCase } from "../lib/api";
import { useAuthOptional } from "../contexts/AuthContext";
import { Plus, FileText, CircleAlert, CheckCircle2, Clock, LayoutDashboard, Calendar, AlertTriangle } from "lucide-react";
import { toast } from "sonner";
import { useState, useMemo, useEffect } from "react";

export function CasesPage() {
  const navigate = useNavigate();
  const auth = useAuthOptional();
  const [cases, setCases] = useState<ApiCase[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isNewCaseDialogOpen, setIsNewCaseDialogOpen] = useState(false);
  const [filters, setFilters] = useState<CasesFilters>({
    searchQuery: "",
    status: "all",
    priority: "all",
    department: "all",
    hasDeadline: null,
    tags: [],
  });

  const loadCases = async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await getCases();
      setCases(list);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Fehler beim Laden");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCases();
  }, []);

  const availableDepartments = useMemo(
    () => [...new Set(cases.map(c => c.department))].sort(),
    [cases]
  );

  const availableTags = useMemo(
    () => [] as string[],
    []
  );

  const filteredCases = useMemo(() => {
    return cases.filter((c) => {
      if (filters.searchQuery) {
        const query = filters.searchQuery.toLowerCase();
        const matchesSearch =
          c.title.toLowerCase().includes(query) ||
          c.department.toLowerCase().includes(query) ||
          c.createdBy.toLowerCase().includes(query) ||
          c.id.toLowerCase().includes(query);
        if (!matchesSearch) return false;
      }
      if (filters.status !== "all" && c.status !== filters.status) return false;
      if (filters.department !== "all" && c.department !== filters.department) return false;
      return true;
    });
  }, [cases, filters]);

  const getStatsForCase = (caseItem: ApiCase) => {
    const critical = caseItem.findings.filter(f => f.severity === "critical" && f.status === "open").length;
    const high = caseItem.findings.filter(f => f.severity === "high" && f.status === "open").length;
    const fixed = caseItem.findings.filter(f => f.status === "fixed").length;
    return { critical, high, fixed, total: caseItem.findings.length };
  };

  // Check if deadline is overdue or soon
  const getDeadlineStatus = (deadline?: string) => {
    if (!deadline) return null;
    const today = new Date();
    const deadlineDate = new Date(deadline);
    const daysUntil = Math.ceil((deadlineDate.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
    
    if (daysUntil < 0) return "overdue";
    if (daysUntil <= 3) return "soon";
    return "ok";
  };

  const formatDeadline = (deadline: string) => {
    const date = new Date(deadline);
    return date.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" });
  };

  return (
    <AppLayout>
      <PageHeader
        title="Vorgänge"
        description={`${filteredCases.length} ${filteredCases.length === 1 ? "Vorgang" : "Vorgänge"}`}
        action={
          canEdit(auth?.user ?? null) ? (
            <Button className="gap-2" onClick={() => setIsNewCaseDialogOpen(true)}>
              <Plus className="size-4" />
              Neuer Vorgang
            </Button>
          ) : undefined
        }
      />

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
              <CasesSearchFilter
                filters={filters}
                onFiltersChange={setFilters}
                availableDepartments={availableDepartments}
                availableTags={availableTags}
              />
            </CardContent>
          </Card>

          {/* Loading State */}
          {loading && (
            <div className="space-y-4">
              {[1, 2, 3].map((i) => (
                <Card key={i}>
                  <CardHeader>
                    <div className="flex items-center gap-3 mb-2">
                      <Skeleton className="h-6 w-64" />
                      <Skeleton className="h-5 w-20" />
                    </div>
                    <Skeleton className="h-4 w-48" />
                  </CardHeader>
                  <CardContent>
                    <div className="flex items-center gap-6">
                      <Skeleton className="h-4 w-28" />
                      <Skeleton className="h-4 w-24" />
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}

          {/* Error State */}
          {!loading && error && (
            <Card>
              <CardContent className="py-12 text-center">
                <CircleAlert className="size-12 text-red-500 dark:text-red-400 mx-auto mb-4" />
                <p className="text-muted-foreground">{error}</p>
                <Button className="mt-4" variant="outline" onClick={loadCases}>Erneut versuchen</Button>
              </CardContent>
            </Card>
          )}

          {/* Cases List */}
          {!loading && !error && (
            <div className="space-y-4">
              {filteredCases.map((caseItem) => {
                const stats = getStatsForCase(caseItem);
                const deadlineStatus = getDeadlineStatus(caseItem.deadline);
                return (
                  <Link
                    key={caseItem.id}
                    to={`/cases/${caseItem.id}`}
                    className="block"
                  >
                    <Card className="hover:shadow-md transition-shadow">
                      <CardHeader>
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
                            <div className="flex items-center gap-3 mb-2 flex-wrap">
                              <CardTitle className="text-lg">{caseItem.title}</CardTitle>
                              <Badge className={statusColors[caseItem.status]}>
                                {statusLabels[caseItem.status]}
                              </Badge>
                              {(caseItem as { priority?: string }).priority && (
                                <Badge className={priorityColors[(caseItem as { priority: string }).priority]}>
                                  {priorityLabels[(caseItem as { priority: string }).priority]}
                                </Badge>
                              )}
                            </div>
                            <CardDescription className="flex items-center gap-4 text-sm">
                              <span>{caseItem.department}</span>
                              <span>&bull;</span>
                              <span>{caseItem.caseType}</span>
                              <span>&bull;</span>
                              <span>Erstellt: {new Date(caseItem.createdAt).toLocaleDateString("de-DE")}</span>
                            </CardDescription>
                            {(caseItem as { tags?: string[] }).tags?.length ? (
                              <div className="flex flex-wrap gap-2 mt-2">
                                {(caseItem as { tags: string[] }).tags.map((tag) => (
                                  <Badge key={tag} variant="outline" className="text-xs">
                                    {tag}
                                  </Badge>
                                ))}
                              </div>
                            ) : null}
                          </div>
                        </div>
                      </CardHeader>
                      <CardContent>
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-6 text-sm">
                            <div className="flex items-center gap-2">
                              <FileText className="size-4 text-muted-foreground/60" />
                              <span className="text-muted-foreground">{caseItem.documents.length} Dokumente</span>
                            </div>
                            {stats.critical > 0 && (
                              <div className="flex items-center gap-2">
                                <CircleAlert className="size-4 text-red-600 dark:text-red-400" />
                                <span className="text-red-600 dark:text-red-400 font-medium">{stats.critical} kritisch</span>
                              </div>
                            )}
                            {stats.high > 0 && (
                              <div className="flex items-center gap-2">
                                <CircleAlert className="size-4 text-orange-600 dark:text-orange-400" />
                                <span className="text-orange-600 dark:text-orange-400 font-medium">{stats.high} hoch</span>
                              </div>
                            )}
                            {stats.fixed > 0 && (
                              <div className="flex items-center gap-2">
                                <CheckCircle2 className="size-4 text-green-600 dark:text-green-400" />
                                <span className="text-green-600 dark:text-green-400">{stats.fixed} behoben</span>
                              </div>
                            )}
                          </div>
                          <div className="flex items-center gap-3 text-sm text-muted-foreground">
                            <Clock className="size-4" />
                            <span>Playbook: {caseItem.playbookVersion || "—"}</span>
                          </div>
                        </div>
                        {(caseItem as { deadline?: string }).deadline && (
                          <div className="mt-4">
                            <div className="flex items-center gap-2">
                              <Calendar className="size-4 text-muted-foreground/60" />
                              <span className="text-muted-foreground">Fällig: {formatDeadline((caseItem as { deadline: string }).deadline)}</span>
                            </div>
                            {deadlineStatus === "overdue" && (
                              <div className="mt-2">
                                <Badge className="bg-red-600 dark:bg-red-700 text-white">
                                  <AlertTriangle className="size-4 mr-1" />
                                  Überfällig
                                </Badge>
                              </div>
                            )}
                            {deadlineStatus === "soon" && (
                              <div className="mt-2">
                                <Badge className="bg-orange-600 dark:bg-orange-700 text-white">
                                  <AlertTriangle className="size-4 mr-1" />
                                  Bald fällig
                                </Badge>
                              </div>
                            )}
                          </div>
                        )}
                      </CardContent>
                    </Card>
                  </Link>
                );
              })}

              {filteredCases.length === 0 && (
                <Card>
                  <CardContent className="py-12 text-center">
                    <FileText className="size-12 text-muted-foreground/30 mx-auto mb-4" />
                    <p className="text-muted-foreground">Keine Vorgänge gefunden</p>
                    <p className="text-sm text-muted-foreground mt-1">
                      Versuchen Sie, Ihre Suchkriterien anzupassen
                    </p>
                  </CardContent>
                </Card>
              )}
            </div>
          )}
        </TabsContent>

        <TabsContent value="dashboard">
          <DashboardStats cases={cases} />
        </TabsContent>
      </Tabs>

      <NewCaseDialog
        open={isNewCaseDialogOpen}
        onOpenChange={setIsNewCaseDialogOpen}
        onSuccess={(newCase) => {
          setIsNewCaseDialogOpen(false);
          toast.success("Vorgang wurde erfolgreich angelegt");
          loadCases();
          navigate(`/cases/${newCase.id}`);
        }}
      />
    </AppLayout>
  );
}