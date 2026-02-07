import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../ui/card";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "../ui/dialog";
import { documentTypeLabels } from "../../lib/mock-data";
import { getDocumentDownloadBlob, downloadBlob, type ApiCase, type ApiDocument } from "../../lib/api";
import { DocumentUploadZone } from "../document-upload-zone";
import { DocumentViewDialog } from "./DocumentViewDialog";
import { Download, FileText, Loader2, Upload } from "lucide-react";

export interface CaseDocumentsTabProps {
  caseData: ApiCase;
  isUploadDialogOpen: boolean;
  setIsUploadDialogOpen: (open: boolean) => void;
  onUploadComplete: () => void;
  /** When false (e.g. viewer role), hide upload button. */
  canEdit?: boolean;
}

export function CaseDocumentsTab({
  caseData,
  isUploadDialogOpen,
  setIsUploadDialogOpen,
  onUploadComplete,
  canEdit = true,
}: CaseDocumentsTabProps) {
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [viewDocument, setViewDocument] = useState<ApiDocument | null>(null);

  async function handleDownload(doc: { id: string; name: string }) {
    setDownloadingId(doc.id);
    try {
      const blob = await getDocumentDownloadBlob(doc.id);
      downloadBlob(blob, doc.name);
    } finally {
      setDownloadingId(null);
    }
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Dokumente</CardTitle>
            <CardDescription>Alle hochgeladenen Dokumente mit Versionierung</CardDescription>
          </div>
          {canEdit && (
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
                  Laden Sie Dokumente für diesen Vorgang hoch. Wenn Sie einen Dokumenttyp wählen, der bereits existiert, wird automatisch eine neue Version (v2, v3, …) angelegt.
                </DialogDescription>
              </DialogHeader>
              <DocumentUploadZone
                caseId={caseData.id}
                uploadedBy={caseData.assignee || "DSB Team"}
                onUploadComplete={() => {
                  setIsUploadDialogOpen(false);
                  onUploadComplete();
                }}
              />
            </DialogContent>
          </Dialog>
          )}
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
                      <Badge variant="outline">{documentTypeLabels[doc.type as keyof typeof documentTypeLabels] ?? doc.type}</Badge>
                      <Badge variant="outline">v{doc.version}</Badge>
                      {doc.extractionMethod === "ocr" && (
                        <Badge variant="secondary" className="text-xs">Text per OCR extrahiert</Badge>
                      )}
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
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setViewDocument(doc)}
                  >
                    Anzeigen
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleDownload(doc)}
                    disabled={downloadingId !== null}
                  >
                    {downloadingId === doc.id ? (
                      <Loader2 className="size-4 animate-spin" />
                    ) : (
                      <Download className="size-4" />
                    )}
                  </Button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
      <DocumentViewDialog
        open={viewDocument !== null}
        onOpenChange={(open) => !open && setViewDocument(null)}
        document={viewDocument}
        canEdit={canEdit}
      />
    </Card>
  );
}
