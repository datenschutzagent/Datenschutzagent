import { useCallback, useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Separator } from "./ui/separator";
import { Alert, AlertDescription } from "./ui/alert";
import {
  FileText,
  Download,
  AlertCircle,
  CheckCircle2,
  Shield,
  TrendingUp,
  Clock,
  Users,
  Loader2,
} from "lucide-react";
import { getDSBReport, getDSBReportBlob, downloadBlob, type DSBReportViewData } from "../lib/api";

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

export function DSBReportView({ caseId }: DSBReportViewProps) {
  const [data, setData] = useState<DSBReportViewData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [downloadLoading, setDownloadLoading] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    getDSBReport(caseId)
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : "Fehler beim Laden"))
      .finally(() => setLoading(false));
  }, [caseId]);

  useEffect(() => {
    load();
  }, [load]);

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

  if (loading && !data) {
    return (
      <div className="flex items-center justify-center py-12 gap-2 text-slate-600">
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

  const reportData = data!;

  return (
    <div className="space-y-6">
      {/* Header */}
      <Card>
        <CardHeader>
          <div className="flex items-start justify-between">
            <div className="flex items-start gap-4">
              <div className="p-3 bg-blue-100 rounded-lg">
                <FileText className="size-8 text-blue-600" />
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
              <p className="text-slate-600 mb-1">Report-ID</p>
              <p className="font-medium">{reportData.caseId}-report</p>
            </div>
            <div>
              <p className="text-slate-600 mb-1">Generiert am</p>
              <p className="font-medium">
                {new Date(reportData.generatedAt).toLocaleString("de-DE")}
              </p>
            </div>
            <div>
              <p className="text-slate-600 mb-1">Playbook Version</p>
              <p className="font-medium">{reportData.playbookVersion || "–"}</p>
            </div>
            <div>
              <p className="text-slate-600 mb-1">Status</p>
              <Badge className="bg-blue-100 text-blue-700">{statusLabel[reportData.status] ?? reportData.status}</Badge>
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
                <FileText className="size-4 text-slate-400" />
                <span className="text-sm text-slate-600">Dokumente</span>
              </div>
              <p className="text-2xl font-semibold">{reportData.summary.totalDocuments}</p>
            </div>
            <div className="p-4 border rounded-lg">
              <div className="flex items-center gap-2 mb-2">
                <AlertCircle className="size-4 text-red-600" />
                <span className="text-sm text-slate-600">Findings</span>
              </div>
              <p className="text-2xl font-semibold">{reportData.summary.totalFindings}</p>
              <p className="text-xs text-red-600 mt-1">
                {reportData.summary.criticalFindings} kritisch, {reportData.summary.highFindings} hoch
              </p>
            </div>
            <div className="p-4 border rounded-lg">
              <div className="flex items-center gap-2 mb-2">
                <CheckCircle2 className="size-4 text-green-600" />
                <span className="text-sm text-slate-600">VVT-Vollständigkeit</span>
              </div>
              <p className="text-2xl font-semibold">{reportData.summary.vvtCompleteness}%</p>
            </div>
          </div>

          {reportData.summary.dsfaRequired && (
            <Alert className="border-amber-200 bg-amber-50">
              <Shield className="size-4 text-amber-600" />
              <AlertDescription className="text-amber-800">
                <strong>DSFA erforderlich:</strong> Die Schwellenwertanalyse deutet auf eine 
                erforderliche Datenschutz-Folgenabschätzung hin.
              </AlertDescription>
            </Alert>
          )}
        </CardContent>
      </Card>

      {/* Risk Overview */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertCircle className="size-5 text-red-600" />
            Identifizierte Risiken
          </CardTitle>
          <CardDescription>
            Top-Risiken, die vor Entscheidungsvorlage geklärt werden müssen
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {reportData.risks.length === 0 ? (
            <p className="text-sm text-slate-600">Keine Findings.</p>
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
                <AlertCircle
                  className={`size-5 mt-0.5 ${
                    risk.severity === "critical"
                      ? "text-red-600"
                      : risk.severity === "high"
                      ? "text-orange-600"
                      : "text-yellow-600"
                  }`}
                />
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <h4 className="font-medium text-slate-900">{risk.title}</h4>
                    <Badge
                      className={
                        risk.severity === "critical"
                          ? "bg-red-100 text-red-700"
                          : risk.severity === "high"
                          ? "bg-orange-100 text-orange-700"
                          : "bg-yellow-100 text-yellow-700"
                      }
                    >
                      {risk.severity}
                    </Badge>
                  </div>
                  <p className="text-sm text-slate-700">{risk.description}</p>
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
                <span className="font-semibold text-blue-600">{index + 1}.</span>
                <span className="text-sm text-slate-700">{question}</span>
              </li>
            ))}
          </ol>
        </CardContent>
      </Card>

      {/* Recommendations */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <CheckCircle2 className="size-5 text-green-600" />
            Empfehlungen
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="space-y-2">
            {reportData.recommendations.length === 0 ? (
              <p className="text-sm text-slate-600">Keine.</p>
            ) : reportData.recommendations.map((rec, index) => (
              <li key={index} className="flex gap-3 text-sm">
                <CheckCircle2 className="size-4 text-green-600 mt-0.5 flex-shrink-0" />
                <span className="text-slate-700">{rec}</span>
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
            Nächste Schritte
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ol className="space-y-3">
            {reportData.nextSteps.map((step, index) => (
              <li key={index} className="flex gap-3">
                <div className="flex items-center justify-center size-6 rounded-full bg-blue-100 text-blue-700 text-sm font-medium flex-shrink-0">
                  {index + 1}
                </div>
                <span className="text-sm text-slate-700 pt-0.5">{step}</span>
              </li>
            ))}
          </ol>
        </CardContent>
      </Card>

      <Separator />

      {/* Footer */}
      <div className="text-center text-sm text-slate-500 py-4">
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