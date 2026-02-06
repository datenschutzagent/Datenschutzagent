import { useParams, Link, useNavigate } from "react-router";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { getPlaybook, type ApiPlaybook } from "../lib/api";
import {
  ArrowLeft,
  BookOpen,
  CheckSquare,
  FileText,
  AlertCircle,
  Edit,
  Copy,
  Archive,
  Loader2,
} from "lucide-react";
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
  const [playbook, setPlaybook] = useState<ApiPlaybook | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!playbookId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    getPlaybook(playbookId)
      .then(setPlaybook)
      .catch((e) => {
        setError(e instanceof Error ? e.message : String(e));
        setPlaybook(null);
      })
      .finally(() => setLoading(false));
  }, [playbookId]);

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="size-10 animate-spin text-blue-600" />
          <p className="text-slate-600">Playbook wird geladen…</p>
        </div>
      </div>
    );
  }

  if (error || !playbook) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <Card className="max-w-md">
          <CardContent className="pt-6 text-center">
            <AlertCircle className="size-12 text-slate-300 mx-auto mb-4" />
            <p className="text-slate-600">Playbook nicht gefunden</p>
            {error && <p className="text-sm text-red-600 mt-2">{error}</p>}
            <Button className="mt-4" onClick={() => navigate("/playbooks")}>
              Zurück zur Übersicht
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const checks = normalizeChecks(playbook.checks ?? []);
  const documentChecks = checks.filter((c) => c.type === "document");
  const crossDocChecks = checks.filter((c) => c.type === "cross_document");
  const mandatoryChecks = checks.filter((c) => c.mandatory);

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
        {/* Back Button */}
        <Button variant="ghost" className="mb-4 gap-2" onClick={() => navigate("/playbooks")}>
          <ArrowLeft className="size-4" />
          Zurück zur Übersicht
        </Button>

        {/* Playbook Header */}
        <div className="mb-6">
          <div className="flex items-start justify-between mb-4">
            <div className="flex items-start gap-4">
              <div className="p-3 bg-blue-100 rounded-lg">
                <BookOpen className="size-8 text-blue-600" />
              </div>
              <div>
                <div className="flex items-center gap-3 mb-2">
                  <h2 className="text-2xl font-semibold text-slate-900">{playbook.name}</h2>
                  {playbook.status === "active" && (
                    <Badge className="bg-green-100 text-green-700">Aktiv</Badge>
                  )}
                  {playbook.status === "draft" && (
                    <Badge className="bg-amber-100 text-amber-700">Entwurf</Badge>
                  )}
                  {playbook.status === "archived" && (
                    <Badge className="bg-slate-100 text-slate-700">Archiviert</Badge>
                  )}
                </div>
                <div className="flex items-center gap-4 text-sm text-slate-600">
                  <span>{playbook.department ?? "—"}</span>
                  <span>•</span>
                  <span>{playbook.caseType ?? "—"}</span>
                  <span>•</span>
                  <span>Version {playbook.version ?? "—"}</span>
                </div>
              </div>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" className="gap-2">
                <Edit className="size-4" />
                Bearbeiten
              </Button>
              <Button variant="outline" className="gap-2">
                <Copy className="size-4" />
                Duplizieren
              </Button>
              {playbook.status === "active" && (
                <Button variant="outline" className="gap-2">
                  <Archive className="size-4" />
                  Archivieren
                </Button>
              )}
            </div>
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
                    <span className="text-slate-600">Playbook-ID:</span>
                    <p className="font-medium">{playbook.id}</p>
                  </div>
                  <div>
                    <span className="text-slate-600">Version:</span>
                    <p className="font-medium">{playbook.version}</p>
                  </div>
                  <div>
                    <span className="text-slate-600">Fachbereich:</span>
                    <p className="font-medium">{playbook.department}</p>
                  </div>
                  <div>
                    <span className="text-slate-600">Case-Typ:</span>
                    <p className="font-medium">{playbook.caseType}</p>
                  </div>
                  <div>
                    <span className="text-slate-600">Erstellt:</span>
                    <p className="font-medium">{playbook.createdAt ? new Date(playbook.createdAt as string).toLocaleDateString("de-DE") : "—"}</p>
                  </div>
                  <div>
                    <span className="text-slate-600">Letzte Aktualisierung:</span>
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
                    <span className="text-sm text-slate-600">Checks gesamt</span>
                    <Badge variant="outline">{checks.length}</Badge>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-slate-600">Pflichtchecks</span>
                    <Badge className="bg-blue-100 text-blue-700">{mandatoryChecks.length}</Badge>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-slate-600">Dokumenten-Checks</span>
                    <Badge variant="outline">{documentChecks.length}</Badge>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-slate-600">Cross-Document-Checks</span>
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
                    <span className="text-sm text-slate-600">Aktive Vorgänge</span>
                    <Badge variant="outline">2</Badge>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-slate-600">Abgeschlossene Vorgänge</span>
                    <Badge variant="outline">15</Badge>
                  </div>
                  <div className="text-xs text-slate-500 pt-2 border-t">
                    Dieses Playbook wird aktiv für laufende Forschungsvorhaben verwendet.
                  </div>
                </CardContent>
              </Card>
            </div>

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
                      <div key={category} className="p-4 border rounded-lg">
                        <h4 className="font-medium text-slate-900 mb-2">{category}</h4>
                        <p className="text-sm text-slate-600">
                          {checksInCategory.length} Check{checksInCategory.length !== 1 ? "s" : ""}
                          {checksInCategory.filter((c) => c.mandatory).length > 0 && (
                            <span className="text-blue-600 ml-2">
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
                    <div key={check.id} className="p-4 border rounded-lg hover:bg-slate-50">
                      <div className="flex items-start gap-3">
                        <CheckSquare className="size-5 text-blue-600 mt-0.5" />
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-1">
                            <h4 className="font-medium text-slate-900">{check.name}</h4>
                            {check.mandatory && (
                              <Badge className="bg-blue-100 text-blue-700">Pflicht</Badge>
                            )}
                            <Badge variant="outline" className="text-xs">{check.category}</Badge>
                          </div>
                          <p className="text-sm text-slate-600 mb-2">{check.description}</p>
                          <div className="flex items-center gap-2">
                            <FileText className="size-4 text-slate-400" />
                            <span className="text-xs text-slate-500">
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
                    <div key={check.id} className="p-4 border rounded-lg hover:bg-slate-50">
                      <div className="flex items-start gap-3">
                        <div className="p-1.5 bg-purple-100 rounded">
                          <CheckSquare className="size-5 text-purple-600" />
                        </div>
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-1">
                            <h4 className="font-medium text-slate-900">{check.name}</h4>
                            {check.mandatory && (
                              <Badge className="bg-blue-100 text-blue-700">Pflicht</Badge>
                            )}
                            <Badge variant="outline" className="text-xs">{check.category}</Badge>
                          </div>
                          <p className="text-sm text-slate-600 mb-2">{check.description}</p>
                          <div className="flex items-center gap-2">
                            <FileText className="size-4 text-slate-400" />
                            <span className="text-xs text-slate-500">
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
                      <div className="size-3 rounded-full bg-green-600" />
                      <div className="w-px h-full bg-slate-200" />
                    </div>
                    <div className="flex-1 pb-6">
                      <div className="flex items-center gap-2 mb-1">
                        <Badge className="bg-green-100 text-green-700">{playbook.version}</Badge>
                        <Badge className="bg-blue-100 text-blue-700">Aktuell</Badge>
                      </div>
                      <p className="text-sm font-medium text-slate-900 mb-1">
                        Aktualisierung: AVV-Checks erweitert
                      </p>
                      <p className="text-xs text-slate-600 mb-2">
                        {playbook.updatedAt ? new Date(playbook.updatedAt as string).toLocaleString("de-DE") : "—"}
                      </p>
                      <ul className="text-xs text-slate-500 space-y-1 ml-4 list-disc">
                        <li>Neue Checks für Drittlandtransfer hinzugefügt</li>
                        <li>TOMs-Anlage-Prüfung erweitert</li>
                      </ul>
                    </div>
                  </div>
                  <div className="flex gap-4">
                    <div className="flex flex-col items-center">
                      <div className="size-3 rounded-full bg-slate-400" />
                      <div className="w-px h-full bg-slate-200" />
                    </div>
                    <div className="flex-1 pb-6">
                      <div className="flex items-center gap-2 mb-1">
                        <Badge variant="outline">v2.2.0</Badge>
                      </div>
                      <p className="text-sm font-medium text-slate-900 mb-1">
                        DSFA-Screening-Logik verbessert
                      </p>
                      <p className="text-xs text-slate-600 mb-2">
                        {new Date("2025-12-10").toLocaleString("de-DE")}
                      </p>
                      <ul className="text-xs text-slate-500 space-y-1 ml-4 list-disc">
                        <li>Schwellenwert-Kriterien aktualisiert</li>
                      </ul>
                    </div>
                  </div>
                  <div className="flex gap-4">
                    <div className="flex flex-col items-center">
                      <div className="size-3 rounded-full bg-slate-400" />
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <Badge variant="outline">v2.0.0</Badge>
                      </div>
                      <p className="text-sm font-medium text-slate-900 mb-1">
                        Initiale Version für {playbook.department}
                      </p>
                      <p className="text-xs text-slate-600">
                        {playbook.createdAt ? new Date(playbook.createdAt as string).toLocaleString("de-DE") : "—"}
                      </p>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
}
