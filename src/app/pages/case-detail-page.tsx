import { useParams, Link, useNavigate } from "react-router";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { Alert, AlertDescription } from "../components/ui/alert";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "../components/ui/dialog";
import { mockCases, statusLabels, statusColors, documentTypeLabels, severityColors, findingStatusLabels, Finding } from "../lib/mock-data";
import { VVTNormalizationView } from "../components/vvt-normalization-view";
import { DSBReportView } from "../components/dsb-report-view";
import { AnnotatedDocumentsView } from "../components/annotated-documents-view";
import { DocumentUploadZone } from "../components/document-upload-zone";
import { 
  ArrowLeft, 
  Upload, 
  FileText, 
  Download, 
  AlertCircle, 
  CheckCircle2,
  Clock,
  XCircle,
  Shield,
  FileCheck,
  MessageSquare
} from "lucide-react";
import { useState } from "react";

export function CaseDetailPage() {
  const { caseId } = useParams();
  const navigate = useNavigate();
  const caseData = mockCases.find((c) => c.id === caseId);
  const [selectedFinding, setSelectedFinding] = useState<Finding | null>(null);
  const [isUploadDialogOpen, setIsUploadDialogOpen] = useState(false);

  if (!caseData) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <Card className="max-w-md">
          <CardContent className="pt-6 text-center">
            <AlertCircle className="size-12 text-slate-300 mx-auto mb-4" />
            <p className="text-slate-600">Vorgang nicht gefunden</p>
            <Button className="mt-4" onClick={() => navigate("/")}>
              Zurück zur Übersicht
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const criticalFindings = caseData.findings.filter(f => f.severity === "critical" && f.status === "open");
  const highFindings = caseData.findings.filter(f => f.severity === "high" && f.status === "open");
  const openFindings = caseData.findings.filter(f => f.status === "open");

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
        {/* Back Button */}
        <Button variant="ghost" className="mb-4 gap-2" onClick={() => navigate("/")}>
          <ArrowLeft className="size-4" />
          Zurück zur Übersicht
        </Button>

        {/* Case Header */}
        <div className="mb-6">
          <div className="flex items-start justify-between mb-4">
            <div>
              <div className="flex items-center gap-3 mb-2">
                <h2 className="text-2xl font-semibold text-slate-900">{caseData.title}</h2>
                <Badge className={statusColors[caseData.status]}>
                  {statusLabels[caseData.status]}
                </Badge>
              </div>
              <div className="flex items-center gap-4 text-sm text-slate-600">
                <span>{caseData.department}</span>
                <span>•</span>
                <span>{caseData.caseType}</span>
                <span>•</span>
                <span>Erstellt: {new Date(caseData.createdAt).toLocaleDateString("de-DE")}</span>
              </div>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" className="gap-2">
                <Download className="size-4" />
                DSB-Report
              </Button>
              <Button variant="outline" className="gap-2">
                <MessageSquare className="size-4" />
                Kommentierte Dokumente
              </Button>
            </div>
          </div>

          {/* Alert for Critical Issues */}
          {criticalFindings.length > 0 && (
            <Alert className="border-red-200 bg-red-50">
              <AlertCircle className="size-4 text-red-600" />
              <AlertDescription className="text-red-800">
                <strong>{criticalFindings.length} kritische</strong> und <strong>{highFindings.length} hohe</strong> Findings 
                müssen vor Entscheidungsvorlage bearbeitet werden.
              </AlertDescription>
            </Alert>
          )}
        </div>

        {/* Tabs */}
        <Tabs defaultValue="overview" className="space-y-6">
          <TabsList>
            <TabsTrigger value="overview">Überblick</TabsTrigger>
            <TabsTrigger value="documents">Dokumente ({caseData.documents.length})</TabsTrigger>
            <TabsTrigger value="findings">
              Findings ({caseData.findings.length})
              {openFindings.length > 0 && (
                <Badge className="ml-2 bg-red-600 text-white">{openFindings.length}</Badge>
              )}
            </TabsTrigger>
            <TabsTrigger value="audit">Audit Trail</TabsTrigger>
            <TabsTrigger value="vvt">VVT Normalisierung</TabsTrigger>
            <TabsTrigger value="report">DSB-Report</TabsTrigger>
            <TabsTrigger value="annotated">Annotierte Dokumente</TabsTrigger>
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
                    <span className="text-slate-600">Vorgang-ID:</span>
                    <p className="font-medium">{caseData.id}</p>
                  </div>
                  <div>
                    <span className="text-slate-600">Erstellt von:</span>
                    <p className="font-medium">{caseData.createdBy}</p>
                  </div>
                  <div>
                    <span className="text-slate-600">Zugewiesen an:</span>
                    <p className="font-medium">{caseData.assignee}</p>
                  </div>
                  <div>
                    <span className="text-slate-600">Sprache:</span>
                    <p className="font-medium">{caseData.language.toUpperCase()}</p>
                  </div>
                  <div>
                    <span className="text-slate-600">Playbook:</span>
                    <p className="font-medium">{caseData.playbookVersion}</p>
                  </div>
                  <div>
                    <span className="text-slate-600">Letzte Aktualisierung:</span>
                    <p className="font-medium">{new Date(caseData.updatedAt).toLocaleDateString("de-DE")}</p>
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
                    <span className="text-sm text-slate-600">Dokumente</span>
                    <Badge variant="outline">{caseData.documents.length}</Badge>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-slate-600">Findings gesamt</span>
                    <Badge variant="outline">{caseData.findings.length}</Badge>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-red-600">Kritisch (offen)</span>
                    <Badge className="bg-red-100 text-red-700">{criticalFindings.length}</Badge>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-orange-600">Hoch (offen)</span>
                    <Badge className="bg-orange-100 text-orange-700">{highFindings.length}</Badge>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-green-600">Behoben</span>
                    <Badge className="bg-green-100 text-green-700">
                      {caseData.findings.filter(f => f.status === "fixed").length}
                    </Badge>
                  </div>
                </CardContent>
              </Card>

              {/* Quick Actions Card */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Aktionen</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  <Button variant="outline" className="w-full justify-start gap-2">
                    <Shield className="size-4" />
                    Playbook neu ausführen
                  </Button>
                  <Button variant="outline" className="w-full justify-start gap-2">
                    <FileCheck className="size-4" />
                    VVT normalisieren
                  </Button>
                  <Button variant="outline" className="w-full justify-start gap-2">
                    <Download className="size-4" />
                    Alle Artefakte exportieren
                  </Button>
                </CardContent>
              </Card>
            </div>

            {/* Recent Findings */}
            <Card>
              <CardHeader>
                <CardTitle>Aktuelle Findings (Top 3)</CardTitle>
                <CardDescription>Die wichtigsten offenen Prüfpunkte</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {caseData.findings
                  .filter(f => f.status === "open")
                  .slice(0, 3)
                  .map((finding) => (
                    <div
                      key={finding.id}
                      className="p-4 border rounded-lg hover:bg-slate-50 cursor-pointer"
                      onClick={() => setSelectedFinding(finding)}
                    >
                      <div className="flex items-start gap-3">
                        <AlertCircle className="size-5 text-red-600 mt-0.5" />
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-1">
                            <h4 className="font-medium text-slate-900">{finding.checkName}</h4>
                            <Badge className={severityColors[finding.severity]}>
                              {finding.severity}
                            </Badge>
                          </div>
                          <p className="text-sm text-slate-600">{finding.description}</p>
                        </div>
                      </div>
                    </div>
                  ))}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Documents Tab */}
          <TabsContent value="documents" className="space-y-6">
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>Dokumente</CardTitle>
                    <CardDescription>Alle hochgeladenen Dokumente mit Versionierung</CardDescription>
                  </div>
                  <Dialog open={isUploadDialogOpen} onOpenChange={setIsUploadDialogOpen}>
                    <DialogTrigger asChild>
                      <Button className="gap-2">
                        <Upload className="size-4" />
                        Dokument hochladen
                      </Button>
                    </DialogTrigger>
                    <DialogContent className="max-w-3xl">
                      <DialogHeader>
                        <DialogTitle>Dokumente hochladen</DialogTitle>
                        <DialogDescription>
                          Laden Sie Dokumente für diesen Vorgang hoch
                        </DialogDescription>
                      </DialogHeader>
                      <DocumentUploadZone 
                        onUploadComplete={() => {
                          setIsUploadDialogOpen(false);
                          // In a real app, refresh documents
                        }}
                      />
                    </DialogContent>
                  </Dialog>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {caseData.documents.map((doc) => (
                    <div key={doc.id} className="p-4 border rounded-lg hover:bg-slate-50">
                      <div className="flex items-start justify-between">
                        <div className="flex items-start gap-3">
                          <FileText className="size-5 text-blue-600 mt-0.5" />
                          <div>
                            <div className="flex items-center gap-2 mb-1">
                              <h4 className="font-medium text-slate-900">{doc.name}</h4>
                              <Badge variant="outline">{documentTypeLabels[doc.type]}</Badge>
                              <Badge variant="outline">v{doc.version}</Badge>
                            </div>
                            <div className="flex items-center gap-3 text-sm text-slate-600">
                              <span>{doc.format.toUpperCase()}</span>
                              <span>•</span>
                              <span>{doc.size}</span>
                              <span>•</span>
                              <span>Hochgeladen: {new Date(doc.uploadedAt).toLocaleDateString("de-DE")}</span>
                              <span>•</span>
                              <span>von {doc.uploadedBy}</span>
                            </div>
                          </div>
                        </div>
                        <div className="flex gap-2">
                          <Button variant="ghost" size="sm">
                            <Download className="size-4" />
                          </Button>
                          <Button variant="ghost" size="sm">
                            <Clock className="size-4" />
                          </Button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Findings Tab */}
          <TabsContent value="findings" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Findings</CardTitle>
                <CardDescription>Alle Prüfergebnisse aus Playbook-Checks</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {caseData.findings.map((finding) => (
                    <div
                      key={finding.id}
                      className="p-4 border rounded-lg hover:bg-slate-50 cursor-pointer"
                      onClick={() => setSelectedFinding(finding)}
                    >
                      <div className="flex items-start gap-3">
                        {finding.status === "open" && <AlertCircle className="size-5 text-red-600 mt-0.5" />}
                        {finding.status === "fixed" && <CheckCircle2 className="size-5 text-green-600 mt-0.5" />}
                        {finding.status === "accepted" && <Shield className="size-5 text-blue-600 mt-0.5" />}
                        {finding.status === "overruled" && <XCircle className="size-5 text-slate-600 mt-0.5" />}
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-2">
                            <h4 className="font-medium text-slate-900">{finding.checkName}</h4>
                            <Badge className={severityColors[finding.severity]}>
                              {finding.severity}
                            </Badge>
                            <Badge variant="outline">{findingStatusLabels[finding.status]}</Badge>
                            <Badge variant="outline" className="text-xs">
                              {finding.category}
                            </Badge>
                          </div>
                          <p className="text-sm text-slate-600 mb-2">{finding.description}</p>
                          <p className="text-sm text-blue-600 font-medium mb-1">{finding.recommendation}</p>
                          <div className="text-xs text-slate-500">
                            <strong>Evidenzen:</strong>
                            <ul className="mt-1 ml-4 list-disc">
                              {finding.evidence.map((ev, i) => (
                                <li key={i}>{ev}</li>
                              ))}
                            </ul>
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Audit Trail Tab */}
          <TabsContent value="audit" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Audit Trail</CardTitle>
                <CardDescription>Nachvollziehbare Historie aller Änderungen</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="flex gap-4">
                    <div className="flex flex-col items-center">
                      <div className="size-2 rounded-full bg-blue-600" />
                      <div className="w-px h-full bg-slate-200" />
                    </div>
                    <div className="flex-1 pb-4">
                      <p className="text-sm font-medium text-slate-900">Playbook-Check durchgeführt</p>
                      <p className="text-xs text-slate-600 mt-1">
                        Version {caseData.playbookVersion} • {new Date(caseData.updatedAt).toLocaleString("de-DE")}
                      </p>
                      <p className="text-xs text-slate-500 mt-1">
                        System: 5 neue Findings generiert
                      </p>
                    </div>
                  </div>
                  <div className="flex gap-4">
                    <div className="flex flex-col items-center">
                      <div className="size-2 rounded-full bg-green-600" />
                      <div className="w-px h-full bg-slate-200" />
                    </div>
                    <div className="flex-1 pb-4">
                      <p className="text-sm font-medium text-slate-900">Dokument aktualisiert</p>
                      <p className="text-xs text-slate-600 mt-1">
                        VVT v2 hochgeladen • {new Date("2026-02-03").toLocaleString("de-DE")}
                      </p>
                      <p className="text-xs text-slate-500 mt-1">
                        {caseData.createdBy}: VVT_Burnout_Studie_v2.xlsx
                      </p>
                    </div>
                  </div>
                  <div className="flex gap-4">
                    <div className="flex flex-col items-center">
                      <div className="size-2 rounded-full bg-slate-400" />
                      <div className="w-px h-full bg-slate-200" />
                    </div>
                    <div className="flex-1 pb-4">
                      <p className="text-sm font-medium text-slate-900">Vorgang angelegt</p>
                      <p className="text-xs text-slate-600 mt-1">
                        {new Date(caseData.createdAt).toLocaleString("de-DE")}
                      </p>
                      <p className="text-xs text-slate-500 mt-1">
                        {caseData.createdBy}: Initiale Dokumentation hochgeladen
                      </p>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* VVT Normalization Tab */}
          <TabsContent value="vvt">
            <VVTNormalizationView />
          </TabsContent>

          {/* DSB Report Tab */}
          <TabsContent value="report">
            <DSBReportView />
          </TabsContent>

          {/* Annotated Documents Tab */}
          <TabsContent value="annotated">
            <AnnotatedDocumentsView />
          </TabsContent>
        </Tabs>
      </main>

      {/* Finding Detail Dialog */}
      <Dialog open={!!selectedFinding} onOpenChange={() => setSelectedFinding(null)}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              {selectedFinding?.checkName}
              <Badge className={selectedFinding ? severityColors[selectedFinding.severity] : ""}>
                {selectedFinding?.severity}
              </Badge>
            </DialogTitle>
            <DialogDescription>
              {selectedFinding?.category} • Status: {selectedFinding ? findingStatusLabels[selectedFinding.status] : ""}
            </DialogDescription>
          </DialogHeader>
          {selectedFinding && (
            <div className="space-y-4">
              <div>
                <h4 className="text-sm font-medium text-slate-900 mb-1">Beschreibung</h4>
                <p className="text-sm text-slate-600">{selectedFinding.description}</p>
              </div>
              <div>
                <h4 className="text-sm font-medium text-slate-900 mb-1">Empfehlung</h4>
                <p className="text-sm text-blue-600">{selectedFinding.recommendation}</p>
              </div>
              <div>
                <h4 className="text-sm font-medium text-slate-900 mb-1">Evidenzen</h4>
                <ul className="text-sm text-slate-600 space-y-1">
                  {selectedFinding.evidence.map((ev, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <span className="text-blue-600">•</span>
                      <span>{ev}</span>
                    </li>
                  ))}
                </ul>
              </div>
              <div className="flex gap-2 pt-4">
                <Button variant="outline" className="flex-1">Als akzeptiert markieren</Button>
                <Button variant="outline" className="flex-1">Als überfahren markieren</Button>
                <Button className="flex-1">Als behoben markieren</Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}