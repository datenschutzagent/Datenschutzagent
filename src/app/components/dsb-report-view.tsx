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
  Users
} from "lucide-react";

interface DSBReportData {
  caseId: string;
  caseTitle: string;
  generatedAt: string;
  playbookVersion: string;
  status: string;
  summary: {
    totalDocuments: number;
    totalFindings: number;
    criticalFindings: number;
    highFindings: number;
    dsfaRequired: boolean;
    vvtCompleteness: number;
  };
  risks: Array<{
    title: string;
    severity: "critical" | "high" | "medium";
    description: string;
  }>;
  openQuestions: string[];
  recommendations: string[];
  nextSteps: string[];
}

const mockReportData: DSBReportData = {
  caseId: "case-001",
  caseTitle: "Longitudinalstudie zur Burnout-Prävention",
  generatedAt: "2026-02-06T10:30:00",
  playbookVersion: "v2.3.0",
  status: "in_review",
  summary: {
    totalDocuments: 4,
    totalFindings: 5,
    criticalFindings: 1,
    highFindings: 3,
    dsfaRequired: true,
    vvtCompleteness: 87,
  },
  risks: [
    {
      title: "Speicherdauer nicht dokumentiert",
      severity: "critical",
      description: "Die Speicherdauer fehlt im Informationsblatt (Art. 13 DSGVO) und ist im VVT nicht ausgefüllt. Dies ist eine kritische Informationspflicht.",
    },
    {
      title: "Inkonsistente Rechtsgrundlage",
      severity: "high",
      description: "Im VVT ist Art. 6 Abs. 1 lit. e DSGVO angegeben, im Informationsblatt wird jedoch von Einwilligung gesprochen. Dies muss rechtssicher geklärt werden.",
    },
    {
      title: "Fehlender AVV für US-Dienstleister",
      severity: "high",
      description: "Der Cloud-Provider in den USA ist als Empfänger genannt, jedoch fehlen AVV und TOMs sowie Drittlandtransfer-Garantien (z.B. SCCs).",
    },
  ],
  openQuestions: [
    "Welche konkrete Speicherdauer gilt für die Forschungsdaten? (z.B. 10 Jahre nach Projektende gemäß institutioneller Richtlinie)",
    "Ist die Verarbeitung tatsächlich auf Art. 6 Abs. 1 lit. e DSGVO gestützt oder wird eine Einwilligung eingeholt?",
    "Liegt ein unterzeichneter AVV mit CloudProvider Inc. vor? Falls ja, bitte nachreichen.",
    "Welche Standard-Vertragsklauseln (SCCs) werden für den Drittlandtransfer verwendet?",
  ],
  recommendations: [
    "Speicherdauer im VVT und Informationsblatt ergänzen",
    "Rechtsgrundlage zwischen VVT und Informationsblatt konsistent darstellen",
    "AVV, TOMs-Anlage und SCCs für US-Cloud-Provider nachreichen",
    "DSFA vollständig erstellen (Schwellenwertanalyse deutet auf Erfordernis hin)",
  ],
  nextSteps: [
    "Rückmeldung an Forschungsleitung mit offenen Fragen",
    "Nach Revision: Playbook neu durchlaufen",
    "DSFA-Erstellung begleiten",
    "Abschließende Entscheidungsvorlage für DSB",
  ],
};

export function DSBReportView() {
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
                  Vorprüfung: {mockReportData.caseTitle}
                </CardDescription>
              </div>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" className="gap-2">
                <Download className="size-4" />
                Als PDF exportieren
              </Button>
              <Button variant="outline" className="gap-2">
                <Download className="size-4" />
                Als Markdown
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
              <p className="font-medium">{mockReportData.caseId}-report-001</p>
            </div>
            <div>
              <p className="text-slate-600 mb-1">Generiert am</p>
              <p className="font-medium">
                {new Date(mockReportData.generatedAt).toLocaleString("de-DE")}
              </p>
            </div>
            <div>
              <p className="text-slate-600 mb-1">Playbook Version</p>
              <p className="font-medium">{mockReportData.playbookVersion}</p>
            </div>
            <div>
              <p className="text-slate-600 mb-1">Status</p>
              <Badge className="bg-blue-100 text-blue-700">In Vorprüfung</Badge>
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
              <p className="text-2xl font-semibold">{mockReportData.summary.totalDocuments}</p>
            </div>
            <div className="p-4 border rounded-lg">
              <div className="flex items-center gap-2 mb-2">
                <AlertCircle className="size-4 text-red-600" />
                <span className="text-sm text-slate-600">Findings</span>
              </div>
              <p className="text-2xl font-semibold">{mockReportData.summary.totalFindings}</p>
              <p className="text-xs text-red-600 mt-1">
                {mockReportData.summary.criticalFindings} kritisch, {mockReportData.summary.highFindings} hoch
              </p>
            </div>
            <div className="p-4 border rounded-lg">
              <div className="flex items-center gap-2 mb-2">
                <CheckCircle2 className="size-4 text-green-600" />
                <span className="text-sm text-slate-600">VVT-Vollständigkeit</span>
              </div>
              <p className="text-2xl font-semibold">{mockReportData.summary.vvtCompleteness}%</p>
            </div>
          </div>

          {mockReportData.summary.dsfaRequired && (
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
          {mockReportData.risks.map((risk, index) => (
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
          ))}
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
            {mockReportData.openQuestions.map((question, index) => (
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
            {mockReportData.recommendations.map((rec, index) => (
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
            {mockReportData.nextSteps.map((step, index) => (
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