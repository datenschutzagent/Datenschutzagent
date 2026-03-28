import { useParams, Link, useNavigate } from "react-router";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { Alert, AlertDescription } from "../components/ui/alert";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "../components/ui/dialog";
import { statusLabels, statusColors, findingStatusLabels, severityColors, severityLabels } from "../lib/mock-data";
import {
  getCase,
  getPlaybooks,
  getPlaybooksForSelection,
  runChecks,
  getRunChecksStatus,
  updateFindingStatus,
  getDSBReportBlob,
  downloadBlob,
  canEdit,
  type ApiCase,
  type ApiFinding,
  type ApiPlaybook,
  type RunChecksStrategy,
} from "../lib/api";
import { useAuthOptional } from "../contexts/AuthContext";
import { VVTNormalizationView } from "../components/vvt-normalization-view";
import { DSBReportView } from "../components/dsb-report-view";
import { AnnotatedDocumentsView } from "../components/annotated-documents-view";
import { ActivityTimeline } from "../components/activity-timeline";
import { AppLayout } from "../components/app-layout";
import { CaseOverviewTab } from "../components/case-detail/CaseOverviewTab";
import { CaseDocumentsTab } from "../components/case-detail/CaseDocumentsTab";
import { CaseFindingsTab } from "../components/case-detail/CaseFindingsTab";
import { ArrowLeft, Download, MessageSquare, Loader2, CircleAlert, ChevronRight } from "lucide-react";
import { toast } from "sonner";
import { useState, useEffect, useMemo } from "react";
import { useAppConfig } from "../contexts/AppConfigContext";

export function CaseDetailPage() {
  const { caseId } = useParams();
  const navigate = useNavigate();
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
  const [runChecksOpen, setRunChecksOpen] = useState(false);
  const [playbooks, setPlaybooks] = useState<ApiPlaybook[]>([]);
  const [selectedPlaybookId, setSelectedPlaybookId] = useState<string>("");
  const [runChecksStrategy, setRunChecksStrategy] = useState<"full_text" | "rag" | "both">("full_text");
  const [runChecksLoading, setRunChecksLoading] = useState(false);
  const [runChecksStatus, setRunChecksStatus] = useState<"idle" | "running" | "completed" | "failed">("idle");
  const [runChecksError, setRunChecksError] = useState<string | null>(null);
  const [findingStatusLoading, setFindingStatusLoading] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState("overview");
  const [dsbReportDownloading, setDsbReportDownloading] = useState(false);

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
    if (!runChecksOpen || !caseData) return;
    let cancelled = false;
    (async () => {
      try {
        const rows = await getPlaybooksForSelection({
          department: caseData.department,
          processing_context: caseData.processingContext?.trim() || undefined,
          case_type: caseData.caseType,
          strict_case_type: true,
        });
        const list = rows.map((r) => r.playbook);
        if (cancelled) return;
        if (list.length > 0) {
          setPlaybooks(list);
        } else {
          const all = await getPlaybooks();
          if (!cancelled) setPlaybooks(all);
        }
      } catch {
        if (!cancelled) {
          getPlaybooks().then(setPlaybooks).catch(() => setPlaybooks([]));
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [runChecksOpen, caseData]);

  const handleRunChecks = async () => {
    if (!caseId || !selectedPlaybookId) return;
    setRunChecksLoading(true);
    setRunChecksError(null);
    try {
      const strategies: RunChecksStrategy[] =
        runChecksStrategy === "both" ? ["full_text", "rag"] : [runChecksStrategy];
      const result = await runChecks(caseId, selectedPlaybookId, strategies);
      if ("accepted" in result && result.accepted) {
        setRunChecksStatus("running");
      } else {
        setCaseData(result as ApiCase);
        setRunChecksOpen(false);
        setSelectedPlaybookId("");
      }
    } catch (e) {
      setRunChecksError(e instanceof Error ? e.message : "Checks fehlgeschlagen.");
    } finally {
      setRunChecksLoading(false);
    }
  };

  // Poll run-checks status when job was accepted (202) and dialog is open
  useEffect(() => {
    if (!caseId || runChecksStatus !== "running" || !runChecksOpen) return;
    const interval = setInterval(async () => {
      try {
        const statusRes = await getRunChecksStatus(caseId);
        if (statusRes.status === "completed") {
          setRunChecksStatus("idle");
          loadCase();
          setRunChecksOpen(false);
          setSelectedPlaybookId("");
        } else if (statusRes.status === "failed") {
          setRunChecksStatus("failed");
          setRunChecksError(statusRes.error ?? "Checks fehlgeschlagen.");
        }
      } catch {
        // keep polling
      }
    }, 2500);
    return () => clearInterval(interval);
  }, [caseId, runChecksStatus, runChecksOpen]);

  const handleFindingStatus = async (findingId: string, status: "accepted" | "overruled" | "fixed") => {
    setFindingStatusLoading(findingId);
    try {
      await updateFindingStatus(findingId, status);
      loadCase();
      setSelectedFinding(null);
      const statusLabel = status === "accepted" ? "akzeptiert" : status === "overruled" ? "überfahren" : "behoben";
      toast.success(`Finding als ${statusLabel} markiert`);
    } catch (e) {
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
      {/* Breadcrumb Navigation */}
      <nav aria-label="Breadcrumb" className="mb-4">
        <ol className="flex items-center gap-1.5 text-sm text-slate-600 dark:text-slate-400">
          <li>
            <Link to="/" className="hover:text-slate-900 dark:hover:text-slate-100">Vorgänge</Link>
          </li>
          <li><ChevronRight className="size-3.5" /></li>
          <li className="text-slate-900 dark:text-slate-100 font-medium truncate max-w-[300px]">
            {caseData.title}
          </li>
        </ol>
      </nav>

        {/* Viewer hint */}
        {auth?.user && auth.user.role === "viewer" && (
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
                disabled={dsbReportDownloading}
                onClick={async () => {
                  if (!caseId) return;
                  setDsbReportDownloading(true);
                  try {
                    const blob = await getDSBReportBlob(caseId, "markdown");
                    const slug = caseData.title.replace(/[^\w\s-]/g, "").slice(0, 50).trim().replace(/[-\s]+/g, "-") || "Report";
                    const date = new Date().toISOString().slice(0, 10);
                    downloadBlob(blob, `DSB-Report-${slug}-${date}.md`);
                  } catch (e) {
                    setError(e instanceof Error ? e.message : "DSB-Report konnte nicht geladen werden.");
                  } finally {
                    setDsbReportDownloading(false);
                  }
                }}
              >
                {dsbReportDownloading ? <Loader2 className="size-4 animate-spin" /> : <Download className="size-4" />}
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
            <TabsTrigger value="report">DSB-Report</TabsTrigger>
            <TabsTrigger value="annotated">Annotierte Dokumente</TabsTrigger>
          </TabsList>

          {/* Overview Tab */}
          <TabsContent value="overview" className="space-y-6">
            <CaseOverviewTab
              caseData={caseData}
              criticalFindings={criticalFindings}
              highFindings={highFindings}
              runChecksOpen={runChecksOpen}
              setRunChecksOpen={setRunChecksOpen}
              playbooks={playbooks}
              selectedPlaybookId={selectedPlaybookId}
              setSelectedPlaybookId={setSelectedPlaybookId}
              runChecksStrategy={runChecksStrategy}
              setRunChecksStrategy={setRunChecksStrategy}
              onRunChecks={handleRunChecks}
              runChecksLoading={runChecksLoading}
              runChecksStatus={runChecksStatus}
              runChecksError={runChecksError}
              setRunChecksError={setRunChecksError}
              onSelectFinding={setSelectedFinding}
              canEdit={userCanEdit}
            />
          </TabsContent>

          {/* Documents Tab */}
          <TabsContent value="documents" className="space-y-6">
            <CaseDocumentsTab
              caseData={caseData}
              isUploadDialogOpen={isUploadDialogOpen}
              setIsUploadDialogOpen={setIsUploadDialogOpen}
              onUploadComplete={loadCase}
              canEdit={userCanEdit}
            />
          </TabsContent>

          {/* Findings Tab */}
          <TabsContent value="findings" className="space-y-6">
            <CaseFindingsTab caseData={caseData} onSelectFinding={setSelectedFinding} onFindingsChanged={loadCase} />
          </TabsContent>

          {/* Audit Trail Tab */}
          <TabsContent value="audit" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Audit Trail</CardTitle>
                <CardDescription>Nachvollziehbare Historie aller Änderungen</CardDescription>
              </CardHeader>
              <CardContent>
                <ActivityTimeline caseId={caseData.id} />
              </CardContent>
            </Card>
          </TabsContent>

          {/* VVT Normalization Tab */}
          <TabsContent value="vvt">
            <VVTNormalizationView caseId={caseData.id} active={activeTab === "vvt"} />
          </TabsContent>

          {/* DSB Report Tab */}
          <TabsContent value="report">
            <DSBReportView caseId={caseData.id} />
          </TabsContent>

          {/* Annotated Documents Tab */}
          <TabsContent value="annotated">
            <AnnotatedDocumentsView caseId={caseData.id} />
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
              {userCanEdit && (
                <div className="flex gap-2 pt-4">
                  <Button
                    variant="outline"
                    className="flex-1"
                    disabled={findingStatusLoading === selectedFinding?.id}
                    onClick={() => selectedFinding && handleFindingStatus(selectedFinding.id, "accepted")}
                  >
                    Als akzeptiert markieren
                  </Button>
                  <Button
                    variant="outline"
                    className="flex-1"
                    disabled={findingStatusLoading === selectedFinding?.id}
                    onClick={() => selectedFinding && handleFindingStatus(selectedFinding.id, "overruled")}
                  >
                    Als überfahren markieren
                  </Button>
                  <Button
                    className="flex-1"
                    disabled={findingStatusLoading === selectedFinding?.id}
                    onClick={() => selectedFinding && handleFindingStatus(selectedFinding.id, "fixed")}
                  >
                    {findingStatusLoading === selectedFinding?.id ? <Loader2 className="size-4 animate-spin" /> : "Als behoben markieren"}
                  </Button>
                </div>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </AppLayout>
  );
}