import { Link, useNavigate } from "react-router";
import { AppLayout } from "../components/app-layout";
import { PageHeader } from "../components/page-header";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { NewPlaybookDialog } from "../components/new-playbook-dialog";
import { Skeleton } from "../components/ui/skeleton";
import { getPlaybooks, canEdit, type ApiPlaybook } from "../lib/api";
import { useAuthOptional } from "../contexts/AuthContext";
import { toast } from "sonner";
import { logger } from "../lib/logger";
import { Plus, Search, Filter, BookOpen, CheckSquare, Archive } from "lucide-react";
import { useState, useEffect } from "react";

export function PlaybooksPage() {
  const navigate = useNavigate();
  const auth = useAuthOptional();
  const [playbooks, setPlaybooks] = useState<ApiPlaybook[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("active");
  const [newPlaybookOpen, setNewPlaybookOpen] = useState(false);

  const loadPlaybooks = () => {
    setLoading(true);
    getPlaybooks()
      .then(setPlaybooks)
      .catch((e) => {
        logger.error("Playbooks konnten nicht geladen werden", {}, e);
        toast.error("Playbooks konnten nicht geladen werden.");
        setPlaybooks([]);
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadPlaybooks();
  }, []);

  const filteredPlaybooks = playbooks.filter((pb) => {
    const matchesSearch =
      pb.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (pb.department ?? "").toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus = statusFilter === "all" || (pb.isActive ? "active" : "archived") === statusFilter;
    return matchesSearch && matchesStatus;
  });

  return (
    <AppLayout>
        <PageHeader
          title="Playbooks"
          description="Versionierte Prüfvorlagen für verschiedene Organisationseinheiten und Vorgangstypen"
          action={
            canEdit(auth?.user ?? null) ? (
              <Button className="gap-2" onClick={() => setNewPlaybookOpen(true)}>
                <Plus className="size-4" />
                Neues Playbook
              </Button>
            ) : undefined
          }
        />

        {/* Filters */}
        <Card className="mb-6">
          <CardContent className="pt-6">
            <div className="flex flex-col sm:flex-row gap-3">
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-slate-400 dark:text-slate-500" />
                <Input
                  placeholder="Suche nach Name oder Einheit..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-10"
                />
              </div>
              <Select value={statusFilter} onValueChange={setStatusFilter}>
                <SelectTrigger className="w-full sm:w-[200px]">
                  <Filter className="size-4 mr-2" />
                  <SelectValue placeholder="Status filtern" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Alle Status</SelectItem>
                  <SelectItem value="active">Aktiv</SelectItem>
                  <SelectItem value="archived">Archiviert</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </CardContent>
        </Card>

        {/* Playbooks Grid */}
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[1, 2, 3].map((i) => (
              <Card key={i}>
                <CardHeader>
                  <div className="flex items-start justify-between mb-2">
                    <Skeleton className="size-8 rounded" />
                    <Skeleton className="h-5 w-16" />
                  </div>
                  <Skeleton className="h-6 w-48 mb-1" />
                  <Skeleton className="h-4 w-36" />
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <Skeleton className="h-4 w-16" />
                      <Skeleton className="h-5 w-12" />
                    </div>
                    <div className="flex items-center justify-between">
                      <Skeleton className="h-4 w-12" />
                      <Skeleton className="h-5 w-8" />
                    </div>
                    <Skeleton className="h-3 w-32 mt-2" />
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredPlaybooks.map((playbook) => (
              <Link key={playbook.id} to={`/playbooks/${playbook.id}`} className="block">
              <Card className="hover:shadow-md transition-shadow h-full">
                <CardHeader>
                  <div className="flex items-start justify-between mb-2">
                    <BookOpen className="size-8 text-blue-600 dark:text-blue-400" />
                    {playbook.isActive ? (
                      <Badge className="bg-green-100 text-green-700 dark:bg-green-900/50 dark:text-green-300">Aktiv</Badge>
                    ) : (
                      <Badge className="bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300">
                        <Archive className="size-3 mr-1" />
                        Archiviert
                      </Badge>
                    )}
                  </div>
                  <CardTitle className="text-lg">{playbook.name}</CardTitle>
                  <CardDescription className="mt-2">
                    {playbook.department ?? "—"} • {playbook.caseType ?? "—"}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-slate-600 dark:text-slate-400">Version</span>
                      <Badge variant="outline">{playbook.version}</Badge>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-slate-600 dark:text-slate-400">Checks</span>
                      <div className="flex items-center gap-1">
                        <CheckSquare className="size-4 text-blue-600 dark:text-blue-400" />
                        <span className="font-medium">{playbook.checks?.length ?? 0}</span>
                      </div>
                    </div>
                    <div className="text-xs text-slate-500 dark:text-slate-400 pt-2 border-t border-border">
                      Erstellt: {new Date(playbook.createdAt).toLocaleDateString("de-DE")}
                    </div>
                  </div>
                </CardContent>
              </Card>
              </Link>
            ))}
          </div>
        )}
        {!loading && filteredPlaybooks.length === 0 && (
          <Card>
            <CardContent className="py-12 text-center">
              <BookOpen className="size-12 text-slate-300 dark:text-slate-500 mx-auto mb-4" />
              <p className="text-slate-600 dark:text-slate-400">Keine Playbooks gefunden</p>
              <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                Versuchen Sie, Ihre Suchkriterien anzupassen
              </p>
            </CardContent>
          </Card>
        )}
      <NewPlaybookDialog
        open={newPlaybookOpen}
        onOpenChange={setNewPlaybookOpen}
        onSuccess={(pb) => {
          toast.success("Playbook wurde erfolgreich angelegt");
          loadPlaybooks();
          navigate(`/playbooks/${pb.id}`);
        }}
      />
    </AppLayout>
  );
}
