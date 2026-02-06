import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { FileText, Download, MessageSquare, Loader2 } from "lucide-react";
import { getAnnotatedDocuments, getAnnotatedDocumentBlob, downloadBlob, type ApiAnnotatedDocumentItem } from "../lib/api";
import { useEffect, useState } from "react";

interface AnnotatedDocumentsViewProps {
  caseId: string;
}

export function AnnotatedDocumentsView({ caseId }: AnnotatedDocumentsViewProps) {
  const [items, setItems] = useState<ApiAnnotatedDocumentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [downloadingAll, setDownloadingAll] = useState(false);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getAnnotatedDocuments(caseId)
      .then(setItems)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, [caseId]);

  async function handleDownload(documentId: string, documentName: string) {
    setDownloadingId(documentId);
    try {
      const blob = await getAnnotatedDocumentBlob(caseId, documentId);
      const base = documentName.replace(/\.[^.]+$/, "") || "document";
      downloadBlob(blob, `Annotiert-${base}.docx`);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setDownloadingId(null);
    }
  }

  async function handleDownloadAll() {
    if (items.length === 0) return;
    setDownloadingAll(true);
    setError(null);
    for (const item of items) {
      try {
        const blob = await getAnnotatedDocumentBlob(caseId, item.document_id);
        const base = item.document_name.replace(/\.[^.]+$/, "") || "document";
        downloadBlob(blob, `Annotiert-${base}.docx`);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
        break;
      }
    }
    setDownloadingAll(false);
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="size-8 animate-spin text-slate-400" />
      </div>
    );
  }

  if (error) {
    return (
      <Card>
        <CardContent className="py-6">
          <p className="text-sm text-red-600">{error}</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div className="flex items-start justify-between">
            <div className="flex items-start gap-4">
              <div className="p-3 bg-purple-100 rounded-lg">
                <MessageSquare className="size-8 text-purple-600" />
              </div>
              <div>
                <CardTitle>Kommentierte Dokumente</CardTitle>
                <CardDescription className="mt-1">
                  Dokumente mit Findings als DOCX herunterladen (extrahierter Inhalt + Prüfergebnisse)
                </CardDescription>
              </div>
            </div>
            {items.length > 0 && (
              <Button
                className="gap-2"
                onClick={handleDownloadAll}
                disabled={downloadingAll}
              >
                {downloadingAll ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : (
                  <Download className="size-4" />
                )}
                Alle herunterladen
              </Button>
          </div>
        </CardHeader>
      </Card>

      {items.length === 0 ? (
        <Card>
          <CardContent className="py-8 text-center text-slate-600">
            <FileText className="size-12 mx-auto mb-3 text-slate-300" />
            <p>Keine Dokumente mit Findings.</p>
            <p className="text-sm mt-1">Führen Sie zuerst „Checks starten“ aus, um Findings zu erzeugen.</p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-6">
          {items.map((item) => (
            <Card key={item.document_id}>
              <CardHeader>
                <div className="flex items-start justify-between">
                  <div className="flex items-start gap-3">
                    <FileText className="size-6 text-blue-600 mt-1" />
                    <div>
                      <CardTitle className="text-lg">{item.document_name}</CardTitle>
                      <CardDescription className="flex items-center gap-3 mt-1">
                        <Badge variant="outline">{item.finding_count} Findings</Badge>
                      </CardDescription>
                    </div>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    className="gap-2"
                    onClick={() => handleDownload(item.document_id, item.document_name)}
                    disabled={downloadingId !== null}
                  >
                    {downloadingId === item.document_id ? (
                      <Loader2 className="size-4 animate-spin" />
                    ) : (
                      <Download className="size-4" />
                    )}
                    DOCX herunterladen
                  </Button>
                </div>
              </CardHeader>
            </Card>
          ))}
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Hinweis</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-slate-600">
          <p>Die heruntergeladene DOCX enthält den extrahierten Dokumentinhalt sowie einen Abschnitt mit allen Findings (Check-Name, Schwere, Beschreibung, Empfehlung).</p>
        </CardContent>
      </Card>
    </div>
  );
}
