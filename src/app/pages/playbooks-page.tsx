import { Link, useNavigate } from "react-router";
import { AppHeaderUser } from "../components/app-header-user";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { NewPlaybookDialog } from "../components/new-playbook-dialog";
import { getPlaybooks, canEdit, isAdmin, type ApiPlaybook } from "../lib/api";
import { useAuthOptional } from "../contexts/AuthContext";
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
    getPlaybooks().then(setPlaybooks).catch(() => setPlaybooks([])).finally(() => setLoading(false));
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
              <Link to="/" className="text-sm font-medium text-slate-600 hover:text-slate-900">
                Vorgänge
              </Link>
              <Link to="/playbooks" className="text-sm font-medium text-blue-600">
                Playbooks
              </Link>
              <Link to="/profile" className="text-sm font-medium text-slate-600 hover:text-slate-900">
                Mein Profil
              </Link>
              {isAdmin(auth?.user ?? null) && (
                <Link to="/admin" className="text-sm font-medium text-slate-600 hover:text-slate-900">
                  Verwaltung
                </Link>
              )}
              <AppHeaderUser />
            </nav>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Page Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-xl font-semibold text-slate-900">Playbooks</h2>
            <p className="text-sm text-slate-600 mt-1">
              Versionierte Prüfvorlagen für verschiedene Fachbereiche und Case-Typen
            </p>
          </div>
          {canEdit(auth?.user ?? null) && (
            <Button className="gap-2" onClick={() => setNewPlaybookOpen(true)}>
              <Plus className="size-4" />
              Neues Playbook
            </Button>
          )}
        </div>

        {/* Filters */}
        <Card className="mb-6">
          <CardContent className="pt-6">
            <div className="flex gap-4">
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-slate-400" />
                <Input
                  placeholder="Suche nach Name oder Fachbereich..."
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
                  <SelectItem value="active">Aktiv</SelectItem>
                  <SelectItem value="archived">Archiviert</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </CardContent>
        </Card>

        {/* Playbooks Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredPlaybooks.map((playbook) => (
            <Card
              key={playbook.id}
              className="hover:shadow-md transition-shadow cursor-pointer"
              onClick={() => navigate(`/playbooks/${playbook.id}`)}
            >
              <CardHeader>
                <div className="flex items-start justify-between mb-2">
                  <BookOpen className="size-8 text-blue-600" />
                  {playbook.isActive ? (
                    <Badge className="bg-green-100 text-green-700">Aktiv</Badge>
                  ) : (
                    <Badge className="bg-slate-100 text-slate-700">
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
                    <span className="text-slate-600">Version</span>
                    <Badge variant="outline">{playbook.version}</Badge>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-slate-600">Checks</span>
                    <div className="flex items-center gap-1">
                      <CheckSquare className="size-4 text-blue-600" />
                      <span className="font-medium">{playbook.checks?.length ?? 0}</span>
                    </div>
                  </div>
                  <div className="text-xs text-slate-500 pt-2 border-t">
                    Erstellt: {new Date(playbook.createdAt).toLocaleDateString("de-DE")}
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        {loading && (
          <Card>
            <CardContent className="py-12 text-center">
              <p className="text-slate-600">Playbooks werden geladen…</p>
            </CardContent>
          </Card>
        )}
        {!loading && filteredPlaybooks.length === 0 && (
          <Card>
            <CardContent className="py-12 text-center">
              <BookOpen className="size-12 text-slate-300 mx-auto mb-4" />
              <p className="text-slate-600">Keine Playbooks gefunden</p>
              <p className="text-sm text-slate-500 mt-1">
                Versuchen Sie, Ihre Suchkriterien anzupassen
              </p>
            </CardContent>
          </Card>
        )}
      </main>
      <NewPlaybookDialog
        open={newPlaybookOpen}
        onOpenChange={setNewPlaybookOpen}
        onSuccess={(pb) => {
          loadPlaybooks();
          navigate(`/playbooks/${pb.id}`);
        }}
      />
    </div>
  );
}
