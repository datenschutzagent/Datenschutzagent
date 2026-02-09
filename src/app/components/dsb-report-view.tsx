import { useCallback, useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Separator } from "./ui/separator";
import { Alert, AlertDescription } from "./ui/alert";
import {
  FileText,
  Download,
  CircleAlert,
  CheckCircle2,
  Shield,
  TrendingUp,
  Clock,
  Users,
  Loader2,
} from "lucide-react";
import {
  getDSBReportIfExists,
  getDSBReportBlob,
  getDSBReportStatus,
  generateDSBReport,
  downloadBlob,
  type DSBReportViewData,
} from "../lib/api";

interface DSBReportViewProps {
  caseId: string;
}

const statusLabel: Record<string, string> = {
  intake: "Eingang",
  in_review: "In Vorprüfung",
  questions_pending: "Rückfragen",
  revision: "Revision",
  ready_for_decision: "Entscheidungsreife",
  completed: "Abgeschlossen",
};

const POLL_INTERVAL_MS = 2000;

export function DSBReportView({ caseId }: DSBReportViewProps) {
  const [data, setData] = useState<DSBReportViewData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [downloadLoading, setDownloadLoading] = useState(false);
  const [generating, setGenerating] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    getDSBReportIfExists(caseId)
      .then((report) => {
        setData(report ?? null);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Fehler beim Laden"))
      .finally(() => setLoading(false));
  }, [caseId]);

  useEffect(() => {
    load();
  }, [load]);

  const handleGenerateReport = useCallback(() => {
    setGenerating(true);
    setError(null);
    generateDSBReport(caseId)
      .then((result) => {
        if (result.status === "completed") {
          load();
          setGenerating(false);
          return;
        }
        const poll = () => {
          getDSBReportStatus(caseId).then((status) => {
            if (status.status === "running") {
              setTimeout(poll, POLL_INTERVAL_MS);
              return;
            }
            if (status.status === "failed") {
              setError(status.error ?? "Report-Erstellung fehlgeschlagen");
              setGenerating(false);
              return;
            }
            if (status.status === "completed") {
              load();
              setGenerating(false);
            }
          }).catch((e) => {
            setError(e instanceof Error ? e.message : "Fehler beim Prüfen des Status");
            setGenerating(false);
          });
        };
        poll();
      })
      .catch((e) => {
        setError(e instanceof Error ? e.message : "Report-Erstellung fehlgeschlagen");
        setGenerating(false);
      });
  }, [caseId, load]);

  const handleDownloadMarkdown = async () => {
    setDownloadLoading(true);
    try {
      const blob = await getDSBReportBlob(caseId, "markdown");
      const date = new Date().toISOString().slice(0, 10);
      const slug = (data?.caseTitle ?? caseId).replace(/[^\w\s-]/g, "").slice(0, 50).trim().replace(/\s+/g, "-") || "Report";
      downloadBlob(blob, `DSB-Report-${slug}-${date}.md`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Download fehlgeschlagen");
    } finally {
      setDownloadLoading(false);
    }
  };

  if (loading && !data && !generating) {
    return (
      <div className="flex items-center justify-center py-12 gap-2 text-slate-600 dark:text-slate-400 dark:text-slate-500 dark:text-slate-400">
        <Loader2 className="size-5 animate-spin" />
        <span>Report wird geladen…</span>
      </div>
    );
  }

  if (error && !data) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{error}</AlertDescription>
        <Button variant="outline" size="sm" className="mt-2" onClick={load}>
          Erneut versuchen
        </Button>
      </Alert>
    );
  }

  if (!data && !loading) {
    return (
      <div className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>DSB Summary Report</CardTitle>
            <CardDescription>Noch kein Report für diesen Vorgang vorhanden.</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-slate-600 dark:text-slate-400 mb-4">
              Der Report wird auf Basis der hochgeladenen Dokumente und der durchgeführten Playbook-Checks erstellt.
              Erstellen Sie den Report, um eine Übersicht zu erhalten.
            </p>
            <Button onClick={handleGenerateReport} disabled={generating}>
              {generating ? (
                <>
                  <Loader2 className="size-4 animate-spin mr-2" />
                  Report wird erstellt…
                </>
              ) : (
                "Report erstellen"
              )}
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const reportData = data!;

  return (
    <div className="space-y-6">
      {reportData.reportStale && (
        <Alert className="border-amber-200 bg-amber-50 dark:border-amber-800 dark:bg-amber-950/30">
          <CircleAlert className="size-4 text-amber-600 dark:text-amber-400" />
          <AlertDescription className="text-amber-800 dark:text-amber-200">
            Die Datenbasis hat sich geändert (neue Dokumente oder neue Analyse). Der Report basiert nicht mehr auf dem
            aktuellen Stand. Bitte erstellen Sie den Report neu.
          </AlertDescription>
          <div className="mt-3">
            <Button size="sm" onClick={handleGenerateReport} disabled={generating}>
              {generating ? <Loader2 className="size-4 animate-spin mr-2" /> : null}
              Report neu erstellen
            </Button>
          </div>
        </Alert>
      )}

      {/* Header */}
      <Card>
        <CardHeader>
          <div className="flex items-start justify-between">
            <div className="flex items-start gap-4">
              <div className="p-3 bg-blue-100 rounded-lg">
                <FileText className="size-8 text-blue-600 dark:text-blue-400" />
              </div>
              <div>
                <CardTitle>DSB Summary Report</CardTitle>
                <CardDescription className="mt-1">
                  Vorprüfung: {reportData.caseTitle}
                </CardDescription>
              </div>
            </div>
            <div className="flex gap-2">
              <Button
                variant="outline"
                className="gap-2"
                onClick={handleGenerateReport}
                disabled={generating}
              >
                {generating ? <Loader2 className="size-4 animate-spin" /> : null}
                Report neu erstellen
              </Button>
              <Button
                variant="outline"
                className="gap-2"
                onClick={handleDownloadMarkdown}
                disabled={downloadLoading}
              >
                {downloadLoading ? <Loader2 className="size-4 animate-spin" /> : <Download className="size-4" />}
                Bericht herunterladen (Markdown)
              </Button>
            </div>
          </div>
        </CardHeader>
      </Card>

      {/* Report Metadata */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Report-Metadaten</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <p className="text-slate-600 dark:text-slate-400 dark:text-slate-500 dark:text-slate-400 mb-1">Report-ID</p>
              <p className="font-medium">{reportData.caseId}-report</p>
            </div>
            <div>
              <p className="text-slate-600 dark:text-slate-400 dark:text-slate-500 dark:text-slate-400 mb-1">Generiert am</p>
              <p className="font-medium">
                {new Date(reportData.generatedAt).toLocaleString("de-DE")}
              </p>
            </div>
            <div>
              <p className="text-slate-600 dark:text-slate-400 dark:text-slate-500 dark:text-slate-400 mb-1">Playbook Version</p>
              <p className="font-medium">{reportData.playbookVersion || "–"}</p>
            </div>
            <div>
              <p className="text-slate-600 dark:text-slate-400 dark:text-slate-500 dark:text-slate-400 mb-1">Status</p>
              <Badge className="bg-blue-100 text-blue-700 dark:bg-blue-900/50 dark:text-blue-300">{statusLabel[reportData.status] ?? reportData.status}</Badge>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Executive Summary */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <TrendingUp className="size-5" />
            Executive Summary
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            <div className="p-4 border rounded-lg">
              <div className="flex items-center gap-2 mb-2">
                <FileText className="size-4 text-slate-400 dark:text-slate-500 dark:text-slate-400" />
                <span className="text-sm text-slate-600 dark:text-slate-400 dark:text-slate-500 dark:text-slate-400">Dokumente</span>
              </div>
              <p className="text-2xl font-semibold">{reportData.summary.totalDocuments}</p>
            </div>
            <div className="p-4 border rounded-lg">
              <div className="flex items-center gap-2 mb-2">
                <CircleAlert className="size-4 text-red-600 dark:text-red-400" />
                <span className="text-sm text-slate-600 dark:text-slate-400 dark:text-slate-500 dark:text-slate-400">Findings</span>
              </div>
              <p className="text-2xl font-semibold">{reportData.summary.totalFindings}</p>
              <p className="text-xs text-red-600 dark:text-red-400 mt-1">
                {reportData.summary.criticalFindings} kritisch, {reportData.summary.highFindings} hoch
              </p>
            </div>
            <div className="p-4 border rounded-lg">
              <div className="flex items-center gap-2 mb-2">
                <CheckCircle2 className="size-4 text-green-600 dark:text-green-400" />
                <span className="text-sm text-slate-600 dark:text-slate-400 dark:text-slate-500 dark:text-slate-400">VVT-Vollständigkeit</span>
              </div>
              <p className="text-2xl font-semibold">
                {reportData.summary.vvtAvailable ? `${reportData.summary.vvtCompleteness}%` : "–"}
              </p>
              {!reportData.summary.vvtAvailable && (
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">Kein VVT vorhanden</p>
              )}
            </div>
          </div>

          {reportData.summary.dsfaAssessment === "unclear" && (
            <Alert className="border-slate-200 bg-slate-50 dark:border-slate-700 dark:bg-slate-900/50">
              <Shield className="size-4 text-slate-600 dark:text-slate-400" />
              <AlertDescription className="text-slate-700 dark:text-slate-300">
                <strong>DSFA-Einschätzung:</strong> Unklar – noch keine Schwellenwertanalyse bzw. Check-Läufe durchgeführt.
                Bitte Playbook-Checks ausführen, um eine Einschätzung zu erhalten.
              </AlertDescription>
            </Alert>
          )}
          {reportData.summary.dsfaAssessment === "required" && (
            <Alert className="border-amber-200 bg-amber-50 dark:border-amber-900/50 dark:bg-amber-950/30">
              <Shield className="size-4 text-amber-600 dark:text-amber-400" />
              <AlertDescription className="text-amber-800 dark:text-amber-200">
                <strong>DSFA erforderlich:</strong> Basierend auf den aktuellen Findings (kritisch/hoch) deutet die
                Auswertung auf eine erforderliche Datenschutz-Folgenabschätzung hin.
              </AlertDescription>
            </Alert>
          )}
          {reportData.summary.dsfaAssessment === "not_required" && (
            <Alert className="border-green-200 bg-green-50 dark:border-green-900/50 dark:bg-green-950/30">
              <Shield className="size-4 text-green-600 dark:text-green-400" />
              <AlertDescription className="text-green-800 dark:text-green-200">
                <strong>DSFA nicht erforderlich:</strong> Basierend auf den aktuellen Findings wurde keine
                Notwendigkeit für eine DSFA festgestellt.
              </AlertDescription>
            </Alert>
          )}
        </CardContent>
      </Card>

      {/* Risk Overview */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <CircleAlert className="size-5 text-red-600 dark:text-red-400" />
            Identifizierte Risiken
          </CardTitle>
          <CardDescription>
            Top-Risiken, die vor Entscheidungsvorlage geklärt werden müssen
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {reportData.risks.length === 0 ? (
            <p className="text-sm text-slate-600 dark:text-slate-400 dark:text-slate-500 dark:text-slate-400">Keine Findings.</p>
          ) : (
          reportData.risks.map((risk, index) => (
            <div
              key={index}
              className={`p-4 border rounded-lg ${
                risk.severity === "critical"
                  ? "border-red-200 bg-red-50"
                  : risk.severity === "high"
                  ? "border-orange-200 bg-orange-50"
                  : "border-yellow-200 bg-yellow-50"
              }`}
            >
              <div className="flex items-start gap-3">
                <CircleAlert
                  className={`size-5 mt-0.5 ${
                    risk.severity === "critical"
                      ? "text-red-600 dark:text-red-400"
                      : risk.severity === "high"
                      ? "text-orange-600"
                      : "text-yellow-600"
                  }`}
                />
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <h4 className="font-medium text-slate-900 dark:text-slate-100">{risk.title}</h4>
                    <Badge
                      className={
                        risk.severity === "critical"
                          ? "bg-red-100 text-red-700 dark:bg-red-900/50 dark:text-red-300"
                          : risk.severity === "high"
                          ? "bg-orange-100 text-orange-700"
                          : "bg-yellow-100 text-yellow-700"
                      }
                    >
                      {risk.severity}
                    </Badge>
                  </div>
                  <p className="text-sm text-slate-700 dark:text-slate-300">{risk.description}</p>
                </div>
              </div>
            </div>
          )))}
        </CardContent>
      </Card>

      {/* Open Questions */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Users className="size-5" />
            Offene Rückfragen an Forschungsleitung
          </CardTitle>
          <CardDescription>
            Diese Fragen sollten an die Forschenden zurückgespielt werden
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ol className="space-y-3">
            {reportData.openQuestions.map((question, index) => (
              <li key={index} className="flex gap-3">
                <span className="font-semibold text-blue-600 dark:text-blue-400">{index + 1}.</span>
                <span className="text-sm text-slate-700 dark:text-slate-300">{question}</span>
              </li>
            ))}
          </ol>
        </CardContent>
      </Card>

      {/* Recommendations */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <CheckCircle2 className="size-5 text-green-600 dark:text-green-400" />
            Empfehlungen
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="space-y-2">
            {reportData.recommendations.length === 0 ? (
              <p className="text-sm text-slate-600 dark:text-slate-400 dark:text-slate-500 dark:text-slate-400">Keine.</p>
            ) : reportData.recommendations.map((rec, index) => (
              <li key={index} className="flex gap-3 text-sm">
                <CheckCircle2 className="size-4 text-green-600 dark:text-green-400 mt-0.5 flex-shrink-0" />
                <span className="text-slate-700 dark:text-slate-300">{rec}</span>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      {/* Next Steps */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="size-5" />
            {reportData.next_steps_is_suggested !== false ? "Nächste Schritte (Vorschläge)" : "Nächste Schritte"}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ol className="space-y-3">
            {reportData.nextSteps.map((step, index) => (
              <li key={index} className="flex gap-3">
                <div className="flex items-center justify-center size-6 rounded-full bg-blue-100 text-blue-700 dark:bg-blue-900/50 dark:text-blue-300 text-sm font-medium flex-shrink-0">
                  {index + 1}
                </div>
                <span className="text-sm text-slate-700 dark:text-slate-300 pt-0.5">{step}</span>
              </li>
            ))}
          </ol>
        </CardContent>
      </Card>

      <Separator />

      {/* Footer */}
      <div className="text-center text-sm text-slate-500 dark:text-slate-400 py-4">
        <p>
          Dieser Report wurde automatisch generiert und dient als Vorprüfung.
          Die finale Entscheidung obliegt dem Datenschutzbeauftragten.
        </p>
        <p className="mt-2">
          <strong>Hinweis:</strong> Alle Findings und Empfehlungen sind nachvollziehbar 
          und referenzieren konkrete Fundstellen in den eingereichten Dokumenten.
        </p>
      </div>
    </div>
  );
}