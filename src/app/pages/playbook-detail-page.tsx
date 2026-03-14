import { useParams, Link, useNavigate } from "react-router";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "../components/ui/alert-dialog";
import { AppLayout } from "../components/app-layout";
import { NewPlaybookDialog } from "../components/new-playbook-dialog";
import {
  getPlaybook,
  createPlaybook,
  updatePlaybook,
  deletePlaybook,
  getLegalBases,
  canEdit as userCanEdit,
  type ApiPlaybook,
  type ApiLegalBase,
} from "../lib/api";
import { useAuthOptional } from "../contexts/AuthContext";
import {
  BookOpen,
  CheckSquare,
  FileText,
  CircleAlert,
  Edit,
  Copy,
  Archive,
  Loader2,
  Trash2,
  Scale,
  ChevronRight,
} from "lucide-react";
import { toast } from "sonner";
import { useState, useEffect } from "react";

/** Normalize API check item for display (backend may use name/instruction or check_name/requirement). */
function normalizeChecks(checks: unknown[]): { id: string; name: string; description: string; type: "document" | "cross_document"; category: string; mandatory: boolean; targetDocuments: string[] }[] {
  return checks.map((c, i) => {
    const o = (c && typeof c === "object" && c as Record<string, unknown>) || {};
    const name = (o.name as string) ?? (o.check_name as string) ?? `Check ${i + 1}`;
    const description = (o.description as string) ?? (o.instruction as string) ?? (o.requirement as string) ?? "";
    const type = ((o.type as string) === "cross_document" ? "cross_document" : "document") as "document" | "cross_document";
    const category = (o.category as string) ?? "";
    const mandatory = (o.mandatory as boolean) ?? false;
    const targetDocuments = Array.isArray(o.target_documents) ? (o.target_documents as string[]) : Array.isArray(o.targetDocuments) ? (o.targetDocuments as string[]) : [];
    return { id: (o.id as string) ?? `check-${i}`, name, description, type, category, mandatory, targetDocuments };
  });
}

export function PlaybookDetailPage() {
  const { playbookId } = useParams();
  const navigate = useNavigate();
  const auth = useAuthOptional();
  const canEdit = userCanEdit(auth?.user ?? null);
  const [playbook, setPlaybook] = useState<ApiPlaybook | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [legalBases, setLegalBases] = useState<ApiLegalBase[]>([]);
  const [selectedLegalIds, setSelectedLegalIds] = useState<string[]>([]);
  const [legalBasesSaveLoading, setLegalBasesSaveLoading] = useState(false);

  const loadPlaybook = () => {
    if (!playbookId) return;
    setLoading(true);
    setError(null);
    getPlaybook(playbookId)
      .then(setPlaybook)
      .catch((e) => {
        setError(e instanceof Error ? e.message : String(e));
        setPlaybook(null);
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    if (!playbookId) {
      setLoading(false);
      return;
    }
    loadPlaybook();
  }, [playbookId]);

  useEffect(() => {
    getLegalBases().then(setLegalBases).catch(() => setLegalBases([]));
  }, []);

  useEffect(() => {
    if (playbook?.content && typeof playbook.content === "object" && playbook.content !== null) {
      const ids = (playbook.content as Record<string, unknown>).legal_basis_ids;
      setSelectedLegalIds(Array.isArray(ids) ? ids.map(String) : []);
    } else {
      setSelectedLegalIds([]);
    }
  }, [playbook?.id, playbook?.content]);

  const handleArchive = async () => {
    if (!playbook?.id) return;
    setActionLoading(true);
    try {
      const updated = await updatePlaybook(playbook.id, { is_active: false });
      setPlaybook(updated);
      toast.success("Playbook archiviert");
    } finally {
      setActionLoading(false);
    }
  };

  const handleDelete = async () => {
    if (!playbook?.id) return;
    setActionLoading(true);
    try {
      await deletePlaybook(playbook.id);
      setDeleteDialogOpen(false);
      navigate("/playbooks");
    } finally {
      setActionLoading(false);
    }
  };

  const handleCopy = async () => {
    if (!playbook) return;
    setActionLoading(true);
    try {
      const content = playbook.content as Record<string, unknown> | undefined;
      const legalBasisIds = content && Array.isArray(content.legal_basis_ids) ? content.legal_basis_ids : [];
      const created = await createPlaybook({
        name: `Kopie von ${playbook.name}`,
        version: "1.0",
        content: { checks: playbook.checks ?? [], legal_basis_ids: legalBasisIds },
        case_type: playbook.caseType ?? null,
        department: playbook.department ?? null,
      });
      navigate(`/playbooks/${created.id}`);
    } finally {
      setActionLoading(false);
    }
  };

  const toggleLegalBase = (id: string) => {
    setSelectedLegalIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const saveLegalBases = async () => {
    if (!playbook) return;
    setLegalBasesSaveLoading(true);
    try {
      const content = (playbook.content as Record<string, unknown>) ?? {};
      const updated = await updatePlaybook(playbook.id, {
        content: { ...content, legal_basis_ids: selectedLegalIds },
      });
      setPlaybook(updated);
    } finally {
      setLegalBasesSaveLoading(false);
    }
  };

  if (loading) {
    return (
      <AppLayout>
        <div className="flex items-center justify-center py-24">
          <div className="flex flex-col items-center gap-4">
            <Loader2 className="size-10 animate-spin text-blue-600 dark:text-blue-400" />
            <p className="text-slate-600 dark:text-slate-400">Playbook wird geladen…</p>
          </div>
        </div>
      </AppLayout>
    );
  }

  if (error || !playbook) {
    return (
      <AppLayout>
        <div className="flex items-center justify-center py-24">
          <Card className="max-w-md">
            <CardContent className="pt-6 text-center">
              <CircleAlert className="size-12 text-slate-300 dark:text-slate-500 mx-auto mb-4" />
              <p className="text-slate-600 dark:text-slate-400">Playbook nicht gefunden</p>
              {error && <p className="text-sm text-red-600 dark:text-red-400 mt-2">{error}</p>}
              <Button className="mt-4" onClick={() => navigate("/playbooks")}>
                Zurück zur Übersicht
              </Button>
            </CardContent>
          </Card>
        </div>
      </AppLayout>
    );
  }

  const checks = normalizeChecks(playbook.checks ?? []);
  const documentChecks = checks.filter((c) => c.type === "document");
  const crossDocChecks = checks.filter((c) => c.type === "cross_document");
  const mandatoryChecks = checks.filter((c) => c.mandatory);

  return (
    <AppLayout>
      {/* Breadcrumb Navigation */}
      <nav aria-label="Breadcrumb" className="mb-4">
        <ol className="flex items-center gap-1.5 text-sm text-slate-600 dark:text-slate-400">
          <li>
            <Link to="/playbooks" className="hover:text-slate-900 dark:hover:text-slate-100">Playbooks</Link>
          </li>
          <li><ChevronRight className="size-3.5" /></li>
          <li className="text-slate-900 dark:text-slate-100 font-medium truncate max-w-[300px]">
            {playbook.name}
          </li>
        </ol>
      </nav>

        {/* Playbook Header */}
        <div className="mb-6">
          <div className="flex items-start justify-between mb-4">
            <div className="flex items-start gap-4">
              <div className="p-3 bg-blue-100 dark:bg-blue-900/50 rounded-lg">
                <BookOpen className="size-8 text-blue-600 dark:text-blue-400" />
              </div>
              <div>
                <div className="flex items-center gap-3 mb-2">
                  <h2 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">{playbook.name}</h2>
                  {playbook.status === "active" && (
                    <Badge className="bg-green-100 text-green-700 dark:bg-green-900/50 dark:text-green-300">Aktiv</Badge>
                  )}
                  {playbook.status === "draft" && (
                    <Badge className="bg-amber-100 text-amber-700 dark:bg-amber-900/50 dark:text-amber-300">Entwurf</Badge>
                  )}
                  {playbook.status === "archived" && (
                    <Badge className="bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300">Archiviert</Badge>
                  )}
                </div>
                <div className="flex items-center gap-4 text-sm text-slate-600 dark:text-slate-400">
                  <span>{playbook.department ?? "—"}</span>
                  <span>•</span>
                  <span>{playbook.caseType ?? "—"}</span>
                  <span>•</span>
                  <span>Version {playbook.version ?? "—"}</span>
                </div>
              </div>
            </div>
            {canEdit && (
            <div className="flex gap-2">
              <Button
                variant="outline"
                className="gap-2"
                onClick={() => setEditDialogOpen(true)}
                disabled={actionLoading}
              >
                <Edit className="size-4" />
                Bearbeiten
              </Button>
              <Button
                variant="outline"
                className="gap-2"
                onClick={handleCopy}
                disabled={actionLoading}
              >
                <Copy className="size-4" />
                Duplizieren
              </Button>
              {playbook.isActive && (
                <Button
                  variant="outline"
                  className="gap-2"
                  onClick={handleArchive}
                  disabled={actionLoading}
                >
                  <Archive className="size-4" />
                  Archivieren
                </Button>
              )}
              <Button
                variant="outline"
                className="gap-2 text-red-600 dark:text-red-400 hover:text-red-700 dark:hover:text-red-300 hover:bg-red-50 dark:hover:bg-red-900/30"
                onClick={() => setDeleteDialogOpen(true)}
                disabled={actionLoading}
              >
                <Trash2 className="size-4" />
                Löschen
              </Button>
            </div>
            )}
          </div>
        </div>

        {/* Tabs */}
        <Tabs defaultValue="overview" className="space-y-6">
          <TabsList>
            <TabsTrigger value="overview">Überblick</TabsTrigger>
            <TabsTrigger value="checks">Checks ({checks.length})</TabsTrigger>
            <TabsTrigger value="history">Versions-Historie</TabsTrigger>
          </TabsList>

          {/* Overview Tab */}
          <TabsContent value="overview" className="space-y-6">
            <div className="grid grid-cols-3 gap-6">
              {/* Metadata Card */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Metadaten</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3 text-sm">
                  <div>
                    <span className="text-slate-600 dark:text-slate-400">Playbook-ID:</span>
                    <p className="font-medium">{playbook.id}</p>
                  </div>
                  <div>
                    <span className="text-slate-600 dark:text-slate-400">Version:</span>
                    <p className="font-medium">{playbook.version}</p>
                  </div>
                  <div>
                    <span className="text-slate-600 dark:text-slate-400">Fachbereich:</span>
                    <p className="font-medium">{playbook.department}</p>
                  </div>
                  <div>
                    <span className="text-slate-600 dark:text-slate-400">Case-Typ:</span>
                    <p className="font-medium">{playbook.caseType}</p>
                  </div>
                  <div>
                    <span className="text-slate-600 dark:text-slate-400">Erstellt:</span>
                    <p className="font-medium">{playbook.createdAt ? new Date(playbook.createdAt as string).toLocaleDateString("de-DE") : "—"}</p>
                  </div>
                  <div>
                    <span className="text-slate-600 dark:text-slate-400">Letzte Aktualisierung:</span>
                    <p className="font-medium">{playbook.updatedAt ? new Date(playbook.updatedAt as string).toLocaleDateString("de-DE") : "—"}</p>
                  </div>
                </CardContent>
              </Card>

              {/* Statistics Card */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Statistik</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-slate-600 dark:text-slate-400">Checks gesamt</span>
                    <Badge variant="outline">{checks.length}</Badge>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-slate-600 dark:text-slate-400">Pflichtchecks</span>
                    <Badge className="bg-blue-100 text-blue-700 dark:bg-blue-900/50 dark:text-blue-300">{mandatoryChecks.length}</Badge>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-slate-600 dark:text-slate-400">Dokumenten-Checks</span>
                    <Badge variant="outline">{documentChecks.length}</Badge>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-slate-600 dark:text-slate-400">Cross-Document-Checks</span>
                    <Badge variant="outline">{crossDocChecks.length}</Badge>
                  </div>
                </CardContent>
              </Card>

              {/* Usage Card */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Verwendung</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-slate-600 dark:text-slate-400">Aktive Vorgänge</span>
                    <Badge variant="outline">2</Badge>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-slate-600 dark:text-slate-400">Abgeschlossene Vorgänge</span>
                    <Badge variant="outline">15</Badge>
                  </div>
                  <div className="text-xs text-slate-500 dark:text-slate-400 pt-2 border-t border-border">
                    Dieses Playbook wird aktiv für laufende Forschungsvorhaben verwendet.
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Rechtsgrundlagen */}
            {canEdit && (
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="text-base flex items-center gap-2">
                        <Scale className="size-4 text-amber-600 dark:text-amber-400" />
                        Rechtsgrundlagen
                      </CardTitle>
                      <CardDescription>
                        Nur referenzierte Rechtsgrundlagen stehen dem Agenten bei Playbook-Checks zur Verfügung (RAG).
                      </CardDescription>
                    </div>
                    <Button
                      size="sm"
                      onClick={saveLegalBases}
                      disabled={legalBasesSaveLoading}
                    >
                      {legalBasesSaveLoading && <Loader2 className="size-4 animate-spin mr-2" />}
                      Speichern
                    </Button>
                  </div>
                </CardHeader>
                <CardContent>
                  {legalBases.length === 0 ? (
                    <p className="text-sm text-slate-600 dark:text-slate-400">
                      Keine Rechtsgrundlagen angelegt. Legen Sie unter Rechtsgrundlagen DSGVO, BDSG o. Ä. an.
                    </p>
                  ) : (
                    <div className="space-y-2 max-h-48 overflow-y-auto">
                      {legalBases.map((lb) => (
                        <label
                          key={lb.id}
                          className="flex items-center gap-2 p-2 rounded hover:bg-slate-50 dark:hover:bg-slate-800/50 cursor-pointer"
                        >
                          <input
                            type="checkbox"
                            checked={selectedLegalIds.includes(lb.id)}
                            onChange={() => toggleLegalBase(lb.id)}
                            className="rounded border-slate-300"
                          />
                          <span className="text-sm font-medium">{lb.title}</span>
                          {lb.shortName && (
                            <Badge variant="outline" className="text-xs">{lb.shortName}</Badge>
                          )}
                          {lb.applicability === "conditional" && (
                            <Badge variant="secondary" className="text-xs">bedingt</Badge>
                          )}
                        </label>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            )}

            {/* Check Categories */}
            <Card>
              <CardHeader>
                <CardTitle>Check-Kategorien</CardTitle>
                <CardDescription>Übersicht der Prüfbereiche in diesem Playbook</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 gap-4">
                  {Array.from(new Set(checks.map((c) => c.category).filter(Boolean))).map((category) => {
                    const checksInCategory = checks.filter((c) => c.category === category);
                    return (
                      <div key={category} className="p-4 border border-border rounded-lg">
                        <h4 className="font-medium text-slate-900 dark:text-slate-100 mb-2">{category}</h4>
                        <p className="text-sm text-slate-600 dark:text-slate-400">
                          {checksInCategory.length} Check{checksInCategory.length !== 1 ? "s" : ""}
                          {checksInCategory.filter((c) => c.mandatory).length > 0 && (
                            <span className="text-blue-600 dark:text-blue-400 ml-2">
                              ({checksInCategory.filter((c) => c.mandatory).length} Pflicht)
                            </span>
                          )}
                        </p>
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Checks Tab */}
          <TabsContent value="checks" className="space-y-6">
            {/* Document Checks */}
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>Dokumenten-Checks</CardTitle>
                    <CardDescription>Prüfungen einzelner Dokumente auf Vollständigkeit</CardDescription>
                  </div>
                  <Badge variant="outline">{documentChecks.length} Checks</Badge>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {documentChecks.map((check) => (
                    <div key={check.id} className="p-4 border border-border rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
                      <div className="flex items-start gap-3">
                        <CheckSquare className="size-5 text-blue-600 dark:text-blue-400 mt-0.5" />
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-1">
                            <h4 className="font-medium text-slate-900 dark:text-slate-100">{check.name}</h4>
                            {check.mandatory && (
                              <Badge className="bg-blue-100 text-blue-700 dark:bg-blue-900/50 dark:text-blue-300">Pflicht</Badge>
                            )}
                            <Badge variant="outline" className="text-xs">{check.category}</Badge>
                          </div>
                          <p className="text-sm text-slate-600 dark:text-slate-400 mb-2">{check.description}</p>
                          <div className="flex items-center gap-2">
                            <FileText className="size-4 text-slate-400 dark:text-slate-500" />
                            <span className="text-xs text-slate-500 dark:text-slate-400">
                              Ziel-Dokumente: {check.targetDocuments.join(", ")}
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Cross-Document Checks */}
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>Cross-Document-Checks</CardTitle>
                    <CardDescription>Konsistenzprüfungen über mehrere Dokumente hinweg</CardDescription>
                  </div>
                  <Badge variant="outline">{crossDocChecks.length} Checks</Badge>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {crossDocChecks.map((check) => (
                    <div key={check.id} className="p-4 border border-border rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
                      <div className="flex items-start gap-3">
                        <div className="p-1.5 bg-purple-100 dark:bg-purple-900/50 rounded">
                          <CheckSquare className="size-5 text-purple-600 dark:text-purple-400" />
                        </div>
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-1">
                            <h4 className="font-medium text-slate-900 dark:text-slate-100">{check.name}</h4>
                            {check.mandatory && (
                              <Badge className="bg-blue-100 text-blue-700 dark:bg-blue-900/50 dark:text-blue-300">Pflicht</Badge>
                            )}
                            <Badge variant="outline" className="text-xs">{check.category}</Badge>
                          </div>
                          <p className="text-sm text-slate-600 dark:text-slate-400 mb-2">{check.description}</p>
                          <div className="flex items-center gap-2">
                            <FileText className="size-4 text-slate-400 dark:text-slate-500" />
                            <span className="text-xs text-slate-500 dark:text-slate-400">
                              Beteiligt: {check.targetDocuments.join(", ")}
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* History Tab */}
          <TabsContent value="history" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Versions-Historie</CardTitle>
                <CardDescription>Alle Änderungen an diesem Playbook</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="flex gap-4">
                    <div className="flex flex-col items-center">
                      <div className="size-3 rounded-full bg-green-600 dark:bg-green-500" />
                      <div className="w-px h-full bg-slate-200 dark:bg-slate-700" />
                    </div>
                    <div className="flex-1 pb-6">
                      <div className="flex items-center gap-2 mb-1">
                        <Badge className="bg-green-100 text-green-700 dark:bg-green-900/50 dark:text-green-300">{playbook.version}</Badge>
                        <Badge className="bg-blue-100 text-blue-700 dark:bg-blue-900/50 dark:text-blue-300">Aktuell</Badge>
                      </div>
                      <p className="text-sm font-medium text-slate-900 dark:text-slate-100 mb-1">
                        Aktualisierung: AVV-Checks erweitert
                      </p>
                      <p className="text-xs text-slate-600 dark:text-slate-400 mb-2">
                        {playbook.updatedAt ? new Date(playbook.updatedAt as string).toLocaleString("de-DE") : "—"}
                      </p>
                      <ul className="text-xs text-slate-500 dark:text-slate-400 space-y-1 ml-4 list-disc">
                        <li>Neue Checks für Drittlandtransfer hinzugefügt</li>
                        <li>TOMs-Anlage-Prüfung erweitert</li>
                      </ul>
                    </div>
                  </div>
                  <div className="flex gap-4">
                    <div className="flex flex-col items-center">
                      <div className="size-3 rounded-full bg-slate-400 dark:bg-slate-500" />
                      <div className="w-px h-full bg-slate-200 dark:bg-slate-700" />
                    </div>
                    <div className="flex-1 pb-6">
                      <div className="flex items-center gap-2 mb-1">
                        <Badge variant="outline">v2.2.0</Badge>
                      </div>
                      <p className="text-sm font-medium text-slate-900 dark:text-slate-100 mb-1">
                        DSFA-Screening-Logik verbessert
                      </p>
                      <p className="text-xs text-slate-600 dark:text-slate-400 mb-2">
                        {new Date("2025-12-10").toLocaleString("de-DE")}
                      </p>
                      <ul className="text-xs text-slate-500 dark:text-slate-400 space-y-1 ml-4 list-disc">
                        <li>Schwellenwert-Kriterien aktualisiert</li>
                      </ul>
                    </div>
                  </div>
                  <div className="flex gap-4">
                    <div className="flex flex-col items-center">
                      <div className="size-3 rounded-full bg-slate-400 dark:bg-slate-500" />
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <Badge variant="outline">v2.0.0</Badge>
                      </div>
                      <p className="text-sm font-medium text-slate-900 dark:text-slate-100 mb-1">
                        Initiale Version für {playbook.department}
                      </p>
                      <p className="text-xs text-slate-600 dark:text-slate-400">
                        {playbook.createdAt ? new Date(playbook.createdAt as string).toLocaleString("de-DE") : "—"}
                      </p>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      <NewPlaybookDialog
        open={editDialogOpen}
        onOpenChange={setEditDialogOpen}
        initialPlaybook={playbook}
        onSuccess={(updated) => {
          setPlaybook(updated);
          setEditDialogOpen(false);
        }}
      />
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Playbook löschen?</AlertDialogTitle>
            <AlertDialogDescription>
              Dieses Playbook wird unwiderruflich gelöscht. Vorgänge, die bereits mit diesem Playbook
              gearbeitet haben, sind davon nicht betroffen.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Abbrechen</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              className="bg-red-600 dark:bg-red-700 hover:bg-red-700 dark:hover:bg-red-800"
              disabled={actionLoading}
            >
              {actionLoading ? "Wird gelöscht…" : "Löschen"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </AppLayout>
  );
}
