import { useParams, Link, useNavigate, useSearchParams } from "react-router";
import { ErrorBoundary } from "../components/ErrorBoundary";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { Alert, AlertDescription } from "../components/ui/alert";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "../components/ui/dialog";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "../components/ui/alert-dialog";
import { statusLabels, statusColors, findingStatusLabels, severityColors, severityLabels } from "../lib/mock-data";
import {
  getCase,
  getRunChecksStatus,
  updateFindingStatus,
  getFindingComments,
  createFindingComment,
  archiveCase,
  unarchiveCase,
  canEdit,
  getAuditTrailExportBlob,
  downloadAuditPackage,
  downloadBlob,
  downloadAuditTrail,
  downloadRopaExport,
  type ApiCase,
  type ApiFinding,
  type ApiFindingComment,
} from "../lib/api";
import { CaseDsfaTab } from "../components/case-detail/CaseDsfaTab";
import { DsfaScreeningCard } from "../components/case-detail/DsfaScreeningCard";
import { useAuthOptional } from "../contexts/AuthContext";
import { VVTNormalizationView } from "../components/vvt-normalization-view";
import { DSBReportView } from "../components/dsb-report-view";
import { AnnotatedDocumentsView } from "../components/annotated-documents-view";
import { ActivityTimeline } from "../components/activity-timeline";
import { AppLayout } from "../components/app-layout";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "../components/ui/breadcrumb";
import { CaseOverviewTab } from "../components/case-detail/CaseOverviewTab";
import { CaseDocumentsTab } from "../components/case-detail/CaseDocumentsTab";
import { CaseFindingsTab } from "../components/case-detail/CaseFindingsTab";
import { CasePrivacyPolicyTab } from "../components/case-detail/CasePrivacyPolicyTab";
import { Download, MessageSquare, Loader2, CircleAlert } from "lucide-react";
import { toast } from "sonner";
import { useState, useEffect, useMemo } from "react";
import { useAppConfig } from "../contexts/AppConfigContext";
import { useRunningChecks } from "../contexts/RunningChecksContext";
import { CaseDetailProvider, useCaseDetail } from "../contexts/CaseDetailContext";

export function CaseDetailPage() {
  const { caseId } = useParams();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const auth = useAuthOptional();
  const userCanEdit = canEdit(auth?.user ?? null);
  const appConfig = useAppConfig();
  const processingContextLabels = useMemo<Record<string, string>>(
    () => Object.fromEntries(appConfig.processing_context_options.map((o) => [o.value, o.label])),
    [appConfig.processing_context_options],
  );

  const [caseData, setCaseData] = useState<ApiCase | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedFinding, setSelectedFinding] = useState<ApiFinding | null>(null);
  const [isUploadDialogOpen, setIsUploadDialogOpen] = useState(false);
  const [findingStatusLoading, setFindingStatusLoading] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState(() => searchParams.get("tab") || "overview");
  const [documentsChangedSinceLastRun, setDocumentsChangedSinceLastRun] = useState(false);
  const [findingComments, setFindingComments] = useState<ApiFindingComment[]>([]);
  const [commentText, setCommentText] = useState("");
  const [commentLoading, setCommentLoading] = useState(false);

  const { registerJob } = useRunningChecks();

  const loadCase = () => {
    if (!caseId) return;
    setLoading(true);
    setError(null);
    getCase(caseId)
      .then(setCaseData)
      .catch((e) => setError(e instanceof Error ? e.message : "Fehler"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadCase();
  }, [caseId]);

  useEffect(() => {
    if (!caseId) return;
    getRunChecksStatus(caseId)
      .then((s) => {
        setDocumentsChangedSinceLastRun(s.documents_changed_since_last_run ?? false);
        if (s.status === "running" && s.job_id && caseData) {
          registerJob(caseId, s.job_id, caseData.title, s.playbook_name ?? undefined);
        }
      })
      .catch(() => {});
  }, [caseId, caseData?.title]);

  const handleSelectFinding = (finding: ApiFinding) => {
    setSelectedFinding(finding);
    setFindingComments([]);
    setCommentText("");
    getFindingComments(finding.id).then(setFindingComments).catch(() => {});
  };

  const handleAddComment = async () => {
    if (!selectedFinding || !commentText.trim()) return;
    setCommentLoading(true);
    try {
      const c = await createFindingComment(selectedFinding.id, commentText.trim());
      setFindingComments((prev) => [...prev, c]);
      setCommentText("");
    } catch {
      toast.error("Kommentar konnte nicht gespeichert werden");
    } finally {
      setCommentLoading(false);
    }
  };

  const handleFindingStatus = async (findingId: string, status: "accepted" | "overruled" | "fixed") => {
    setFindingStatusLoading(findingId);
    try {
      await updateFindingStatus(findingId, status);
      loadCase();
      setSelectedFinding(null);
      const statusLabel = status === "accepted" ? "akzeptiert" : status === "overruled" ? "überfahren" : "behoben";
      toast.success(`Finding als ${statusLabel} markiert`);
    } catch {
      toast.error("Fehler beim Aktualisieren des Finding-Status");
    } finally {
      setFindingStatusLoading(null);
    }
  };

  if (loading && !caseData) {
    return (
      <AppLayout>
        <div className="flex items-center justify-center py-24">
          <Card className="max-w-md">
            <CardContent className="pt-6 text-center">
              <Loader2 className="size-12 text-slate-400 dark:text-slate-500 mx-auto mb-4 animate-spin" />
              <p className="text-slate-600 dark:text-slate-400">Vorgang wird geladen…</p>
            </CardContent>
          </Card>
        </div>
      </AppLayout>
    );
  }
  if (error || !caseData) {
    return (
      <AppLayout>
        <div className="flex items-center justify-center py-24">
          <Card className="max-w-md">
            <CardContent className="pt-6 text-center">
              <CircleAlert className="size-12 text-slate-300 dark:text-slate-500 mx-auto mb-4" />
              <p className="text-slate-600 dark:text-slate-400">{error || "Vorgang nicht gefunden"}</p>
              <Button className="mt-4" onClick={() => navigate("/")}>
                Zurück zur Übersicht
              </Button>
            </CardContent>
          </Card>
        </div>
      </AppLayout>
    );
  }

  const criticalFindings = caseData.findings.filter(f => f.severity === "critical" && f.status === "open");
  const highFindings = caseData.findings.filter(f => f.severity === "high" && f.status === "open");
  const openFindings = caseData.findings.filter(f => f.status === "open");

  return (
    <AppLayout>
      <CaseDetailProvider caseData={caseData} onReloadCase={loadCase}>
        <CaseDetailPageContent
          caseData={caseData}
          setCaseData={setCaseData}
          activeTab={activeTab}
          setActiveTab={setActiveTab}
          isUploadDialogOpen={isUploadDialogOpen}
          setIsUploadDialogOpen={setIsUploadDialogOpen}
          documentsChangedSinceLastRun={documentsChangedSinceLastRun}
          criticalFindings={criticalFindings}
          highFindings={highFindings}
          openFindings={openFindings}
          selectedFinding={selectedFinding}
          setSelectedFinding={setSelectedFinding}
          findingComments={findingComments}
          commentText={commentText}
          setCommentText={setCommentText}
          commentLoading={commentLoading}
          findingStatusLoading={findingStatusLoading}
          userCanEdit={userCanEdit}
          isViewer={auth?.user?.role === "viewer"}
          processingContextLabels={processingContextLabels}
          caseId={caseId ?? ""}
          onLoadCase={loadCase}
          onSelectFinding={handleSelectFinding}
          onAddComment={handleAddComment}
          onFindingStatus={handleFindingStatus}
        />
      </CaseDetailProvider>
    </AppLayout>
  );
}

interface CaseDetailPageContentProps {
  caseData: ApiCase;
  setCaseData: (data: ApiCase) => void;
  activeTab: string;
  setActiveTab: (tab: string) => void;
  isUploadDialogOpen: boolean;
  setIsUploadDialogOpen: (open: boolean) => void;
  documentsChangedSinceLastRun: boolean;
  criticalFindings: ApiFinding[];
  highFindings: ApiFinding[];
  openFindings: ApiFinding[];
  selectedFinding: ApiFinding | null;
  setSelectedFinding: (f: ApiFinding | null) => void;
  findingComments: ApiFindingComment[];
  commentText: string;
  setCommentText: (t: string) => void;
  commentLoading: boolean;
  findingStatusLoading: string | null;
  userCanEdit: boolean;
  isViewer: boolean;
  processingContextLabels: Record<string, string>;
  caseId: string;
  onLoadCase: () => void;
  onSelectFinding: (finding: ApiFinding) => void;
  onAddComment: () => Promise<void>;
  onFindingStatus: (findingId: string, status: "accepted" | "overruled" | "fixed") => Promise<void>;
}

function CaseDetailPageContent({
  caseData,
  setCaseData,
  activeTab,
  setActiveTab,
  isUploadDialogOpen,
  setIsUploadDialogOpen,
  documentsChangedSinceLastRun,
  criticalFindings,
  highFindings,
  openFindings,
  selectedFinding,
  setSelectedFinding,
  findingComments,
  commentText,
  setCommentText,
  commentLoading,
  findingStatusLoading,
  userCanEdit,
  isViewer,
  processingContextLabels,
  caseId,
  onLoadCase,
  onSelectFinding,
  onAddComment,
  onFindingStatus,
}: CaseDetailPageContentProps) {
  const { setRunChecksOpen } = useCaseDetail();

  return (
    <>
      <Breadcrumb className="mb-4">
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbLink asChild>
              <Link to="/">Vorgänge</Link>
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage className="truncate max-w-[300px]">{caseData.title}</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      {/* Archived banner */}
      {caseData.archivedAt && (
        <Alert className="mb-4 border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-900/30">
          <AlertDescription className="text-amber-800 dark:text-amber-200">
            Dieser Vorgang ist archiviert (seit {new Date(caseData.archivedAt).toLocaleDateString("de-DE")}) und schreibgeschützt.
          </AlertDescription>
        </Alert>
      )}

      {/* Viewer hint */}
      {isViewer && (
        <Alert className="mb-4 border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-900/30">
          <AlertDescription className="text-amber-800 dark:text-amber-200">
            Sie haben nur Leserechte. Bearbeiten, Löschen und das Ausführen von Checks sind nicht möglich.
          </AlertDescription>
        </Alert>
      )}

      {/* Case Header */}
      <div className="mb-6">
        <div className="flex items-start justify-between mb-4">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <h2 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">{caseData.title}</h2>
              <Badge className={statusColors[caseData.status]}>
                {statusLabels[caseData.status]}
              </Badge>
            </div>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-slate-600 dark:text-slate-400">
              <span>{caseData.department}</span>
              <span>•</span>
              <span>{caseData.caseType}</span>
              {caseData.processingContext ? (
                <>
                  <span>•</span>
                  <span>
                    Kontext:{" "}
                    {processingContextLabels[caseData.processingContext] ??
                      caseData.processingContext}
                  </span>
                </>
              ) : null}
              {(caseData.specialCategoryData || caseData.internationalTransfer) && (
                <>
                  <span>•</span>
                  <span>
                    {[
                      caseData.specialCategoryData ? "Art. 9" : null,
                      caseData.internationalTransfer ? "Drittland" : null,
                    ]
                      .filter(Boolean)
                      .join(", ")}
                  </span>
                </>
              )}
              <span>•</span>
              <span>Erstellt: {new Date(caseData.createdAt).toLocaleDateString("de-DE")}</span>
            </div>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              className="gap-2"
              onClick={() => setActiveTab("report")}
            >
              <Download className="size-4" />
              DSB-Report
            </Button>
            <Button
              variant="outline"
              className="gap-2"
              onClick={() => setActiveTab("annotated")}
            >
              <MessageSquare className="size-4" />
              Kommentierte Dokumente
            </Button>
            {userCanEdit && !caseData.archivedAt && (
              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button
                    variant="outline"
                    className="gap-2 text-amber-700 border-amber-300 hover:bg-amber-50 dark:text-amber-400 dark:border-amber-700 dark:hover:bg-amber-900/30"
                  >
                    Archivieren
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>Vorgang archivieren?</AlertDialogTitle>
                    <AlertDialogDescription>
                      Archivierte Vorgänge sind schreibgeschützt. Die Archivierung kann später rückgängig gemacht werden.
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>Abbrechen</AlertDialogCancel>
                    <AlertDialogAction
                      onClick={async () => {
                        if (!caseId) return;
                        try {
                          const updated = await archiveCase(caseId);
                          setCaseData(updated);
                          toast.success("Vorgang archiviert");
                        } catch (e) {
                          toast.error(e instanceof Error ? e.message : "Fehler beim Archivieren");
                        }
                      }}
                    >
                      Archivieren
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            )}
            {userCanEdit && caseData.archivedAt && (
              <Button
                variant="outline"
                className="gap-2"
                onClick={async () => {
                  if (!caseId) return;
                  try {
                    const updated = await unarchiveCase(caseId);
                    setCaseData(updated);
                    toast.success("Vorgang wiederhergestellt");
                  } catch (e) {
                    toast.error(e instanceof Error ? e.message : "Fehler beim Wiederherstellen");
                  }
                }}
              >
                Wiederherstellen
              </Button>
            )}
          </div>
        </div>

        {/* Alert for Critical Issues */}
        {criticalFindings.length > 0 && (
          <Alert className="border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/30">
            <CircleAlert className="size-4 text-red-600 dark:text-red-400" />
            <AlertDescription className="text-red-800 dark:text-red-200">
              <strong>{criticalFindings.length} kritische</strong> und <strong>{highFindings.length} hohe</strong> Findings
              müssen vor Entscheidungsvorlage bearbeitet werden.
            </AlertDescription>
          </Alert>
        )}
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
        <TabsList>
          <TabsTrigger value="overview">Überblick</TabsTrigger>
          <TabsTrigger value="documents">Dokumente ({caseData.documents.length})</TabsTrigger>
          <TabsTrigger value="findings">
            Findings ({caseData.findings.length})
            {openFindings.length > 0 && (
              <Badge className="ml-2 bg-red-600 dark:bg-red-700 text-white">{openFindings.length}</Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="audit">Audit Trail</TabsTrigger>
          <TabsTrigger value="vvt">VVT Normalisierung</TabsTrigger>
          <TabsTrigger value="dsfa">DSFA</TabsTrigger>
          <TabsTrigger value="report">DSB-Report</TabsTrigger>
          <TabsTrigger value="privacy-policy">Datenschutzerklärung</TabsTrigger>
          <TabsTrigger value="annotated">Annotierte Dokumente</TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-6">
          <ErrorBoundary>
            <CaseOverviewTab
              caseData={caseData}
              criticalFindings={criticalFindings}
              highFindings={highFindings}
              onSelectFinding={onSelectFinding}
              canEdit={userCanEdit}
              onCaseUpdated={setCaseData}
            />
          </ErrorBoundary>
        </TabsContent>

        {/* Documents Tab */}
        <TabsContent value="documents" className="space-y-6">
          <ErrorBoundary>
            <CaseDocumentsTab
              caseData={caseData}
              isUploadDialogOpen={isUploadDialogOpen}
              setIsUploadDialogOpen={setIsUploadDialogOpen}
              onUploadComplete={onLoadCase}
              canEdit={userCanEdit}
            />
          </ErrorBoundary>
        </TabsContent>

        {/* Findings Tab */}
        <TabsContent value="findings" className="space-y-6">
          <ErrorBoundary>
            {documentsChangedSinceLastRun && (
              <Alert className="border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-900/30">
                <AlertDescription className="text-amber-800 dark:text-amber-200 flex items-center justify-between gap-4">
                  <span>Dokumente wurden seit der letzten Prüfung aktualisiert. Die Findings könnten veraltet sein.</span>
                  {userCanEdit && (
                    <Button size="sm" variant="outline" onClick={() => setRunChecksOpen(true)}>
                      Jetzt prüfen
                    </Button>
                  )}
                </AlertDescription>
              </Alert>
            )}
            <CaseFindingsTab caseData={caseData} onSelectFinding={onSelectFinding} onFindingsChanged={onLoadCase} />
          </ErrorBoundary>
        </TabsContent>

        {/* Audit Trail Tab */}
        <TabsContent value="audit" className="space-y-6">
          <ErrorBoundary>
            <Card>
              <CardHeader className="flex flex-row items-start justify-between gap-4">
                <div>
                  <CardTitle>Audit Trail</CardTitle>
                  <CardDescription>Nachvollziehbare Historie aller Änderungen</CardDescription>
                </div>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={async () => {
                      try {
                        const blob = await getAuditTrailExportBlob(caseData.id);
                        downloadBlob(blob, `audit-trail-${caseData.id}.csv`);
                        toast.success("Audit Trail exportiert.");
                      } catch {
                        toast.error("Export fehlgeschlagen.");
                      }
                    }}
                  >
                    <Download className="size-4 mr-1" /> CSV exportieren
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    title="Vollständiges Audit-Paket als ZIP (Befunde, Dokumente, Activity-Log, SHA-256-Manifest)"
                    onClick={async () => {
                      try {
                        const blob = await downloadAuditPackage(caseData.id);
                        downloadBlob(blob, `audit-paket-${caseData.id.slice(0, 8)}.zip`);
                        toast.success("Audit-Paket exportiert.");
                      } catch {
                        toast.error("Audit-Export fehlgeschlagen.");
                      }
                    }}
                  >
                    <Download className="size-4 mr-1" /> Audit-Paket (ZIP)
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    title="Signierter Audit-Trail (HMAC-SHA256)."
                    onClick={async () => {
                      try {
                        const { filename, signature } = await downloadAuditTrail(caseData.id, "csv");
                        if (signature) {
                          toast.success(
                            `${filename} exportiert. Signatur: ${signature.slice(0, 16)}…${signature.slice(-8)}`,
                            { duration: 10000 },
                          );
                        } else {
                          toast.success(`${filename} exportiert.`);
                        }
                      } catch {
                        toast.error("Signierter Audit-Export fehlgeschlagen.");
                      }
                    }}
                  >
                    <Download className="size-4 mr-1" /> Signiert (CSV)
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    title="ROPA gemäß Art. 30 DSGVO als DOCX"
                    onClick={async () => {
                      try {
                        await downloadRopaExport(caseData.id, "docx");
                        toast.success("ROPA exportiert.");
                      } catch (err) {
                        const msg = err instanceof Error ? err.message : String(err);
                        toast.error(`ROPA-Export fehlgeschlagen: ${msg}`);
                      }
                    }}
                  >
                    <Download className="size-4 mr-1" /> ROPA (DOCX)
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <ActivityTimeline caseId={caseData.id} />
              </CardContent>
            </Card>
          </ErrorBoundary>
        </TabsContent>

        {/* VVT Normalization Tab */}
        <TabsContent value="vvt">
          <ErrorBoundary>
            <VVTNormalizationView caseId={caseData.id} active={activeTab === "vvt"} />
          </ErrorBoundary>
        </TabsContent>

        {/* DSFA Tab */}
        <TabsContent value="dsfa">
          <ErrorBoundary>
            <CaseDsfaTab caseData={caseData} canEdit={userCanEdit} />
          </ErrorBoundary>
        </TabsContent>

        {/* DSB Report Tab */}
        <TabsContent value="report">
          <ErrorBoundary>
            <DSBReportView caseId={caseData.id} />
          </ErrorBoundary>
          <ErrorBoundary>
            <DsfaScreeningCard caseId={caseData.id} className="mt-6" />
          </ErrorBoundary>
        </TabsContent>

        {/* Privacy Policy Tab */}
        <TabsContent value="privacy-policy">
          <ErrorBoundary>
            <CasePrivacyPolicyTab caseData={caseData} canEdit={userCanEdit} />
          </ErrorBoundary>
        </TabsContent>

        {/* Annotated Documents Tab */}
        <TabsContent value="annotated">
          <ErrorBoundary>
            <AnnotatedDocumentsView caseId={caseData.id} />
          </ErrorBoundary>
        </TabsContent>
      </Tabs>

      {/* Finding Detail Dialog */}
      <Dialog open={!!selectedFinding} onOpenChange={() => setSelectedFinding(null)}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              {selectedFinding?.checkName}
              {selectedFinding && (
                <Badge className={severityColors[selectedFinding.severity]}>
                  {severityLabels[selectedFinding.severity]}
                </Badge>
              )}
            </DialogTitle>
            <DialogDescription>
              {selectedFinding?.category}
              {!selectedFinding?.documentId && " • Vorgangsbezogen (Cross-Document)"}
              {selectedFinding?.sourceStrategy && ` • ${selectedFinding.sourceStrategy === "rag" ? "RAG" : "Volltext"}`}
              {" • Status: "}{selectedFinding ? findingStatusLabels[selectedFinding.status] : ""}
            </DialogDescription>
          </DialogHeader>
          {selectedFinding && (
            <div className="space-y-4">
              <div>
                <h4 className="text-sm font-medium text-slate-900 dark:text-slate-100 mb-1">Beschreibung</h4>
                <p className="text-sm text-slate-600 dark:text-slate-400">{selectedFinding.description}</p>
              </div>
              <div>
                <h4 className="text-sm font-medium text-slate-900 dark:text-slate-100 mb-1">Empfehlung</h4>
                <p className="text-sm text-blue-600 dark:text-blue-400">{selectedFinding.recommendation}</p>
              </div>
              <div>
                <h4 className="text-sm font-medium text-slate-900 dark:text-slate-100 mb-1">Evidenzen</h4>
                <ul className="text-sm text-slate-600 dark:text-slate-400 space-y-1">
                  {selectedFinding.evidence.map((ev, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <span className="text-blue-600 dark:text-blue-400">•</span>
                      <span>{ev}</span>
                    </li>
                  ))}
                </ul>
              </div>
              {/* Finding comments */}
              <div className="border-t pt-4">
                <h4 className="text-sm font-medium text-slate-900 dark:text-slate-100 mb-2">Kommentare</h4>
                {findingComments.length === 0 && (
                  <p className="text-xs text-slate-400 dark:text-slate-500 mb-2">Noch keine Kommentare.</p>
                )}
                <div className="space-y-2 mb-3 max-h-48 overflow-y-auto">
                  {findingComments.map((c) => (
                    <div key={c.id} className="text-sm bg-muted/50 rounded-md p-2">
                      <span className="font-medium text-slate-700 dark:text-slate-300">{c.author}</span>
                      <span className="text-xs text-slate-400 dark:text-slate-500 ml-2">
                        {new Date(c.created_at).toLocaleString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" })}
                      </span>
                      <p className="text-slate-600 dark:text-slate-400 mt-1">{c.text}</p>
                    </div>
                  ))}
                </div>
                {userCanEdit && (
                  <div className="flex gap-2">
                    <input
                      className="flex-1 text-sm border border-input rounded-md px-3 py-1.5 bg-background"
                      placeholder="Kommentar hinzufügen…"
                      value={commentText}
                      onChange={(e) => setCommentText(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && !e.shiftKey) {
                          e.preventDefault();
                          void onAddComment();
                        }
                      }}
                    />
                    <Button size="sm" onClick={() => void onAddComment()} disabled={commentLoading || !commentText.trim()}>
                      {commentLoading ? <Loader2 className="size-3 animate-spin" /> : "Senden"}
                    </Button>
                  </div>
                )}
              </div>

              {userCanEdit && (
                <div className="flex gap-2 pt-2">
                  <Button
                    variant="outline"
                    className="flex-1"
                    disabled={findingStatusLoading === selectedFinding?.id}
                    onClick={() => selectedFinding && void onFindingStatus(selectedFinding.id, "accepted")}
                  >
                    Als akzeptiert markieren
                  </Button>
                  <Button
                    variant="outline"
                    className="flex-1"
                    disabled={findingStatusLoading === selectedFinding?.id}
                    onClick={() => selectedFinding && void onFindingStatus(selectedFinding.id, "overruled")}
                  >
                    Als überfahren markieren
                  </Button>
                  <Button
                    className="flex-1"
                    disabled={findingStatusLoading === selectedFinding?.id}
                    onClick={() => selectedFinding && void onFindingStatus(selectedFinding.id, "fixed")}
                  >
                    {findingStatusLoading === selectedFinding?.id ? <Loader2 className="size-4 animate-spin" /> : "Als behoben markieren"}
                  </Button>
                </div>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
