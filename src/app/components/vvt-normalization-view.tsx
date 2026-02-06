import { useCallback, useEffect, useState } from "react";
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
  RefreshCw,
  Loader2
} from "lucide-react";
import { getVVTNormalization, getVVTExportBlob, downloadBlob, type ApiVVTField } from "../lib/api";

interface VVTNormalizationViewProps {
  caseId: string;
  documentId?: string;
}

export function VVTNormalizationView({ caseId, documentId }: VVTNormalizationViewProps) {
  const [data, setData] = useState<{ fields: ApiVVTField[]; documentName: string; sourceTemplate: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [exportLoading, setExportLoading] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    getVVTNormalization(caseId, documentId)
      .then((res) => {
        setData({
          fields: res.fields,
          documentName: res.documentName,
          sourceTemplate: res.sourceTemplate,
        });
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Fehler beim Laden"))
      .finally(() => setLoading(false));
  }, [caseId, documentId]);

  useEffect(() => {
    load();
  }, [load]);

  const handleExport = async () => {
    setExportLoading(true);
    try {
      const blob = await getVVTExportBlob(caseId, documentId, "csv");
      const date = new Date().toISOString().slice(0, 10);
      downloadBlob(blob, `VVT-Export-${caseId}-${date}.csv`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export fehlgeschlagen");
    } finally {
      setExportLoading(false);
    }
  };

  const fields = data?.fields ?? [];
  const totalFields = fields.length;
  const filledFields = fields.filter(f => f.status === "filled").length;
  const missingFields = fields.filter(f => f.status === "missing").length;
  const inconsistentFields = fields.filter(f => f.status === "inconsistent").length;
  const completionRate = totalFields > 0 ? Math.round((filledFields / totalFields) * 100) : 0;

  if (loading && !data) {
    return (
      <div className="flex items-center justify-center py-12 gap-2 text-slate-600">
        <Loader2 className="size-5 animate-spin" />
        <span>VVT wird analysiert…</span>
      </div>
    );
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{error}</AlertDescription>
        <Button variant="outline" size="sm" className="mt-2" onClick={load}>
          Erneut versuchen
        </Button>
      </Alert>
    );
  }

  if (totalFields === 0) {
    return (
      <Alert>
        <AlertDescription>
          Kein VVT-Dokument in diesem Vorgang. Bitte zuerst ein Dokument vom Typ „VVT / ROPA“ hochladen.
        </AlertDescription>
      </Alert>
    );
  }

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
              <Button variant="outline" className="gap-2" onClick={load} disabled={loading}>
                {loading ? <Loader2 className="size-4 animate-spin" /> : <RefreshCw className="size-4" />}
                Neu analysieren
              </Button>
              <Button className="gap-2" onClick={handleExport} disabled={exportLoading}>
                {exportLoading ? <Loader2 className="size-4 animate-spin" /> : <Download className="size-4" />}
                Als CSV exportieren
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
              <p className="font-medium text-slate-900">{data?.sourceTemplate || "—"}</p>
              {data?.documentName && (
                <p className="text-xs text-slate-500 mt-1">Dokument: {data.documentName}</p>
              )}
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
              {fields.map((field, index) => (
                <VVTFieldCard key={index} field={field} />
              ))}
            </TabsContent>

            <TabsContent value="filled" className="space-y-3">
              {fields
                .filter(f => f.status === "filled")
                .map((field, index) => (
                  <VVTFieldCard key={index} field={field} />
                ))}
            </TabsContent>

            <TabsContent value="issues" className="space-y-3">
              {fields
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

function VVTFieldCard({ field }: { field: ApiVVTField }) {
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