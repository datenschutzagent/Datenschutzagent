import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./ui/tabs";
import { Progress } from "./ui/progress";
import { Alert, AlertDescription } from "./ui/alert";
import { 
  FileSpreadsheet, 
  CheckCircle2, 
  AlertCircle, 
  ArrowRight,
  Download,
  RefreshCw
} from "lucide-react";

interface VVTField {
  fieldName: string;
  required: boolean;
  status: "filled" | "missing" | "inconsistent";
  sourceTemplate: string;
  canonicalValue?: string;
  evidence?: string;
  finding?: string;
}

const mockVVTData: VVTField[] = [
  {
    fieldName: "Zwecke der Verarbeitung",
    required: true,
    status: "filled",
    sourceTemplate: "Variante B (Psychologie)",
    canonicalValue: "Longitudinale Erhebung von Burnout-Symptomen zur Entwicklung präventiver Interventionen",
    evidence: "VVT_Burnout_Studie_v2.xlsx, Zeile 12, Spalte C",
  },
  {
    fieldName: "Rechtsgrundlage",
    required: true,
    status: "inconsistent",
    sourceTemplate: "Variante B (Psychologie)",
    canonicalValue: "Art. 6 Abs. 1 lit. e DSGVO (öffentliche Aufgabe)",
    evidence: "VVT_Burnout_Studie_v2.xlsx, Zeile 15, Spalte C",
    finding: "Widerspruch zum Informationsblatt (dort: Einwilligung)",
  },
  {
    fieldName: "Kategorien betroffener Personen",
    required: true,
    status: "filled",
    sourceTemplate: "Variante B (Psychologie)",
    canonicalValue: "Arbeitnehmer im Gesundheitswesen, Alter 25-60 Jahre",
    evidence: "VVT_Burnout_Studie_v2.xlsx, Zeile 18, Spalte C",
  },
  {
    fieldName: "Kategorien personenbezogener Daten",
    required: true,
    status: "filled",
    sourceTemplate: "Variante B (Psychologie)",
    canonicalValue: "Gesundheitsdaten (Art. 9 DSGVO): Burnout-Scores, psychische Belastungsindikatoren",
    evidence: "VVT_Burnout_Studie_v2.xlsx, Zeile 19, Spalte C",
  },
  {
    fieldName: "Empfänger / Empfängerkategorien",
    required: true,
    status: "filled",
    sourceTemplate: "Variante B (Psychologie)",
    canonicalValue: "Forschungsteam Universität, Cloud-Provider (USA) für Datenanalyse",
    evidence: "VVT_Burnout_Studie_v2.xlsx, Zeile 22, Spalte C",
  },
  {
    fieldName: "Drittlandtransfer",
    required: true,
    status: "inconsistent",
    sourceTemplate: "Variante B (Psychologie)",
    canonicalValue: "USA (CloudProvider Inc.)",
    evidence: "VVT_Burnout_Studie_v2.xlsx, Zeile 24, Spalte C",
    finding: "Kein AVV oder SCCs dokumentiert",
  },
  {
    fieldName: "Speicherdauer",
    required: true,
    status: "missing",
    sourceTemplate: "Variante B (Psychologie)",
    finding: "Feld leer oder unvollständig",
  },
  {
    fieldName: "Technische und organisatorische Maßnahmen (TOMs)",
    required: true,
    status: "filled",
    sourceTemplate: "Variante B (Psychologie)",
    canonicalValue: "Pseudonymisierung, Verschlüsselung, Zugriffskontrollen",
    evidence: "VVT_Burnout_Studie_v2.xlsx, Zeile 28, Spalte C",
  },
];

export function VVTNormalizationView() {
  const totalFields = mockVVTData.length;
  const filledFields = mockVVTData.filter(f => f.status === "filled").length;
  const missingFields = mockVVTData.filter(f => f.status === "missing").length;
  const inconsistentFields = mockVVTData.filter(f => f.status === "inconsistent").length;
  const completionRate = Math.round((filledFields / totalFields) * 100);

  return (
    <div className="space-y-6">
      {/* Header Card */}
      <Card>
        <CardHeader>
          <div className="flex items-start justify-between">
            <div className="flex items-start gap-4">
              <div className="p-3 bg-blue-100 rounded-lg">
                <FileSpreadsheet className="size-8 text-blue-600" />
              </div>
              <div>
                <CardTitle>VVT-Normalisierung</CardTitle>
                <CardDescription className="mt-1">
                  Automatische Erkennung und Mapping auf kanonisches Datenmodell
                </CardDescription>
              </div>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" className="gap-2">
                <RefreshCw className="size-4" />
                Neu analysieren
              </Button>
              <Button className="gap-2">
                <Download className="size-4" />
                Gold Standard exportieren
              </Button>
            </div>
          </div>
        </CardHeader>
      </Card>

      {/* Progress Overview */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Vollständigkeit</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-slate-600">Gesamt-Completion</span>
              <span className="text-sm font-medium">{completionRate}%</span>
            </div>
            <Progress value={completionRate} className="h-2" />
          </div>
          <div className="grid grid-cols-4 gap-4 pt-2 border-t">
            <div className="text-center">
              <p className="text-2xl font-semibold text-slate-900">{totalFields}</p>
              <p className="text-xs text-slate-600">Pflichtfelder</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-semibold text-green-600">{filledFields}</p>
              <p className="text-xs text-slate-600">Ausgefüllt</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-semibold text-orange-600">{inconsistentFields}</p>
              <p className="text-xs text-slate-600">Inkonsistent</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-semibold text-red-600">{missingFields}</p>
              <p className="text-xs text-slate-600">Fehlend</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Template Detection */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Template-Erkennung</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4">
            <div className="flex-1 p-4 border rounded-lg bg-slate-50">
              <p className="text-sm text-slate-600 mb-1">Erkanntes Template</p>
              <p className="font-medium text-slate-900">Variante B (Psychologie)</p>
              <p className="text-xs text-slate-500 mt-1">Confidence: 94%</p>
            </div>
            <ArrowRight className="size-6 text-slate-400" />
            <div className="flex-1 p-4 border rounded-lg bg-blue-50 border-blue-200">
              <p className="text-sm text-blue-600 mb-1">Ziel-Template</p>
              <p className="font-medium text-blue-900">Kanonisches VVT-Modell v3.1</p>
              <p className="text-xs text-blue-600 mt-1">Gold Standard</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Field Mapping */}
      <Card>
        <CardHeader>
          <CardTitle>Feld-Mapping & Status</CardTitle>
          <CardDescription>Detaillierte Übersicht aller VVT-Pflichtfelder</CardDescription>
        </CardHeader>
        <CardContent>
          <Tabs defaultValue="all">
            <TabsList className="mb-4">
              <TabsTrigger value="all">Alle ({totalFields})</TabsTrigger>
              <TabsTrigger value="filled">Ausgefüllt ({filledFields})</TabsTrigger>
              <TabsTrigger value="issues">
                Issues ({missingFields + inconsistentFields})
              </TabsTrigger>
            </TabsList>

            <TabsContent value="all" className="space-y-3">
              {mockVVTData.map((field, index) => (
                <VVTFieldCard key={index} field={field} />
              ))}
            </TabsContent>

            <TabsContent value="filled" className="space-y-3">
              {mockVVTData
                .filter(f => f.status === "filled")
                .map((field, index) => (
                  <VVTFieldCard key={index} field={field} />
                ))}
            </TabsContent>

            <TabsContent value="issues" className="space-y-3">
              {mockVVTData
                .filter(f => f.status === "missing" || f.status === "inconsistent")
                .map((field, index) => (
                  <VVTFieldCard key={index} field={field} />
                ))}
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </div>
  );
}

function VVTFieldCard({ field }: { field: VVTField }) {
  return (
    <div className="p-4 border rounded-lg hover:bg-slate-50">
      <div className="flex items-start gap-3">
        {field.status === "filled" && <CheckCircle2 className="size-5 text-green-600 mt-0.5" />}
        {field.status === "missing" && <AlertCircle className="size-5 text-red-600 mt-0.5" />}
        {field.status === "inconsistent" && <AlertCircle className="size-5 text-orange-600 mt-0.5" />}
        
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-2">
            <h4 className="font-medium text-slate-900">{field.fieldName}</h4>
            {field.required && (
              <Badge variant="outline" className="text-xs">Pflichtfeld</Badge>
            )}
            {field.status === "filled" && (
              <Badge className="bg-green-100 text-green-700">Ausgefüllt</Badge>
            )}
            {field.status === "missing" && (
              <Badge className="bg-red-100 text-red-700">Fehlend</Badge>
            )}
            {field.status === "inconsistent" && (
              <Badge className="bg-orange-100 text-orange-700">Inkonsistent</Badge>
            )}
          </div>

          {field.canonicalValue && (
            <div className="mb-2">
              <p className="text-sm text-slate-600 mb-1">Kanonischer Wert:</p>
              <p className="text-sm text-slate-900 bg-slate-50 p-2 rounded border">
                {field.canonicalValue}
              </p>
            </div>
          )}

          {field.evidence && (
            <div className="mb-2">
              <p className="text-xs text-slate-500">
                <strong>Evidenz:</strong> {field.evidence}
              </p>
            </div>
          )}

          {field.finding && (
            <Alert className="mt-2 border-orange-200 bg-orange-50">
              <AlertCircle className="size-4 text-orange-600" />
              <AlertDescription className="text-orange-800 text-sm">
                {field.finding}
              </AlertDescription>
            </Alert>
          )}

          <p className="text-xs text-slate-400 mt-2">Quelle: {field.sourceTemplate}</p>
        </div>
      </div>
    </div>
  );
}