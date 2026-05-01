import { Link, useNavigate } from "react-router";
import { logger } from "../lib/logger";
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
import { unarchiveCase, canEdit, type CasesFilter } from "../lib/api";
import { getStatsForCase, getDeadlineStatus, formatDeadline } from "../lib/case-utils";
import { useAuthOptional } from "../contexts/AuthContext";
import { useRunningChecks } from "../contexts/RunningChecksContext";
import { useCases, useArchivedCases, useInvalidateCases } from "../lib/queries/casesQueries";
import { Plus, FileText, CircleAlert, CheckCircle2, Clock, LayoutDashboard, Calendar, AlertTriangle, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { useState, useMemo } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { casesKeys } from "../lib/queries/casesQueries";

type TabValue = "list" | "dashboard" | "archived";

export function CasesPage() {
  const navigate = useNavigate();
  const auth = useAuthOptional();
  const { isRunning } = useRunningChecks();
  const queryClient = useQueryClient();
  const invalidateCases = useInvalidateCases();
  const [isNewCaseDialogOpen, setIsNewCaseDialogOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<TabValue>("list");
  const [filters, setFilters] = useState<CasesFilters>({
    searchQuery: "",
    status: "all",
    priority: "all",
    department: "all",
    hasDeadline: null,
    tags: [],
  });

  const apiFilter = useMemo<CasesFilter>(() => {
    const f: CasesFilter = {};
    if (filters.searchQuery) f.q = filters.searchQuery;
    if (filters.status !== "all") f.status = filters.status;
    if (filters.department !== "all") f.department = filters.department;
    if (filters.hasDeadline === false) f.deadline_overdue = false;
    else if (filters.hasDeadline === true) f.deadline_overdue = true;
    return f;
  }, [filters]);

  const { data: cases = [], isLoading, isError, error } = useCases(
    activeTab !== "archived" ? apiFilter : undefined,
  );
  const { data: archivedCases = [], isLoading: isLoadingArchived } = useArchivedCases(
    activeTab === "archived",
  );

  const displayedArchivedCases = useMemo(
    () => archivedCases.filter((c) => c.archivedAt),
    [archivedCases],
  );

  const availableDepartments = useMemo(
    () => [...new Set(cases.map((c) => c.department))].sort(),
    [cases],
  );

  const availableTags = useMemo(() => [] as string[], []);

  const filteredCases = useMemo(() => {
    if (filters.priority === "all") return cases;
    return cases.filter((c) => (c.priority ?? null) === filters.priority);
  }, [cases, filters.priority]);

  const loading = activeTab === "archived" ? isLoadingArchived : isLoading;

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

      <Tabs
        defaultValue="list"
        className="space-y-6"
        onValueChange={(val) => setActiveTab(val as TabValue)}
      >
        <TabsList>
          <TabsTrigger value="list" className="gap-2">
            <FileText className="size-4" />
            Vorgänge
          </TabsTrigger>
          <TabsTrigger value="dashboard" className="gap-2">
            <LayoutDashboard className="size-4" />
            Dashboard
          </TabsTrigger>
          <TabsTrigger value="archived" className="gap-2">
            <Clock className="size-4" />
            Archiviert
          </TabsTrigger>
        </TabsList>

        {/* List View */}
        <TabsContent value="list" className="space-y-6">
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

          {!loading && isError && (
            <Card>
              <CardContent className="py-12 text-center">
                <CircleAlert className="size-12 text-red-500 dark:text-red-400 mx-auto mb-4" />
                <p className="text-muted-foreground">
                  {error instanceof Error ? error.message : "Fehler beim Laden"}
                </p>
                <Button
                  className="mt-4"
                  variant="outline"
                  onClick={() =>
                    queryClient.invalidateQueries({ queryKey: casesKeys.list(apiFilter) })
                  }
                >
                  Erneut versuchen
                </Button>
              </CardContent>
            </Card>
          )}

          {!loading && !isError && (
            <div className="space-y-4">
              {filteredCases.map((caseItem) => {
                const stats = getStatsForCase(caseItem);
                const deadlineStatus = getDeadlineStatus(caseItem.deadline);
                return (
                  <Link key={caseItem.id} to={`/cases/${caseItem.id}`} className="block">
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
                                <Badge
                                  className={
                                    priorityColors[(caseItem as { priority: string }).priority]
                                  }
                                >
                                  {priorityLabels[(caseItem as { priority: string }).priority]}
                                </Badge>
                              )}
                              {isRunning(caseItem.id) && (
                                <Badge className="bg-blue-100 text-blue-700 dark:bg-blue-900/50 dark:text-blue-300 gap-1">
                                  <Loader2 className="size-3 animate-spin" />
                                  Prüfung läuft
                                </Badge>
                              )}
                            </div>
                            <CardDescription className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
                              <span>{caseItem.department}</span>
                              <span className="hidden sm:inline">&bull;</span>
                              <span>{caseItem.caseType}</span>
                              <span className="hidden sm:inline">&bull;</span>
                              <span>
                                Erstellt:{" "}
                                {new Date(caseItem.createdAt).toLocaleDateString("de-DE")}
                              </span>
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
                              <span className="text-muted-foreground">
                                {caseItem.documents.length} Dokumente
                              </span>
                            </div>
                            {stats.critical > 0 && (
                              <div className="flex items-center gap-2">
                                <CircleAlert className="size-4 text-red-600 dark:text-red-400" />
                                <span className="text-red-600 dark:text-red-400 font-medium">
                                  {stats.critical} kritisch
                                </span>
                              </div>
                            )}
                            {stats.high > 0 && (
                              <div className="flex items-center gap-2">
                                <CircleAlert className="size-4 text-orange-600 dark:text-orange-400" />
                                <span className="text-orange-600 dark:text-orange-400 font-medium">
                                  {stats.high} hoch
                                </span>
                              </div>
                            )}
                            {stats.fixed > 0 && (
                              <div className="flex items-center gap-2">
                                <CheckCircle2 className="size-4 text-green-600 dark:text-green-400" />
                                <span className="text-green-600 dark:text-green-400">
                                  {stats.fixed} behoben
                                </span>
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
                              <span className="text-muted-foreground">
                                Fällig:{" "}
                                {formatDeadline((caseItem as { deadline: string }).deadline)}
                              </span>
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

        <TabsContent value="archived" className="space-y-4">
          {isLoadingArchived ? (
            <div className="space-y-4">
              {[1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-32 w-full" />
              ))}
            </div>
          ) : displayedArchivedCases.length === 0 ? (
            <Card>
              <CardContent className="py-12 text-center">
                <Clock className="size-12 text-muted-foreground/30 mx-auto mb-4" />
                <p className="text-muted-foreground">Keine archivierten Vorgänge</p>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-4">
              {displayedArchivedCases.map((c) => (
                <Card key={c.id} className="opacity-75">
                  <CardHeader>
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <CardTitle className="text-base">{c.title}</CardTitle>
                        <CardDescription>
                          {c.department} · {c.caseType}
                        </CardDescription>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <Badge variant="secondary" className="text-xs">
                          Archiviert{" "}
                          {c.archivedAt
                            ? new Date(c.archivedAt).toLocaleDateString("de-DE")
                            : ""}
                        </Badge>
                        {canEdit(auth?.user ?? null) && (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={async () => {
                              try {
                                await unarchiveCase(c.id);
                                toast.success("Vorgang wiederhergestellt");
                                queryClient.invalidateQueries({
                                  queryKey: casesKeys.archived(),
                                });
                              } catch (e) {
                                toast.error(e instanceof Error ? e.message : "Fehler");
                                logger.error(
                                  "Fehler beim Wiederherstellen des Vorgangs",
                                  {},
                                  e,
                                );
                              }
                            }}
                          >
                            Wiederherstellen
                          </Button>
                        )}
                      </div>
                    </div>
                  </CardHeader>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>

      <NewCaseDialog
        open={isNewCaseDialogOpen}
        onOpenChange={setIsNewCaseDialogOpen}
        onSuccess={(newCase) => {
          setIsNewCaseDialogOpen(false);
          toast.success("Vorgang wurde erfolgreich angelegt");
          invalidateCases();
          navigate(`/cases/${newCase.id}`);
        }}
      />
    </AppLayout>
  );
}
