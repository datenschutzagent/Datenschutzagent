import { useState } from "react";
import { Card } from "./ui/card";
import { Button } from "./ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { Progress } from "./ui/progress";
import { Upload, X, Check, CircleAlert, Loader2 } from "lucide-react";
import { documentTypeLabels, type DocumentType } from "../lib/mock-data";
import { randomUUID } from "../lib/uuid";
import { uploadDocument, uploadDocumentsBulk } from "../lib/api";

interface UploadedFile {
  id: string;
  file: File;
  type: DocumentType | null;
  progress: number;
  status: "uploading" | "success" | "error";
  errorMessage?: string;
}

interface DocumentUploadZoneProps {
  caseId?: string;
  uploadedBy?: string;
  onUploadComplete?: (files: UploadedFile[]) => void;
}

export function DocumentUploadZone({ caseId, uploadedBy = "", onUploadComplete }: DocumentUploadZoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const [completing, setCompleting] = useState(false);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    
    const files = Array.from(e.dataTransfer.files);
    processFiles(files);
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const files = Array.from(e.target.files);
      processFiles(files);
    }
  };

  const processFiles = (files: File[]) => {
    const allowedFormats = ['.docx', '.pdf', '.xlsx', '.doc', '.jpg', '.jpeg', '.png', '.tif', '.tiff'];
    const maxSize = 10 * 1024 * 1024; // 10MB

    const newFiles: UploadedFile[] = files.map((file) => {
      const extension = '.' + file.name.split('.').pop()?.toLowerCase();
      const isValidFormat = allowedFormats.includes(extension);
      const isValidSize = file.size <= maxSize;

      return {
        id: randomUUID(),
        file,
        type: null,
        progress: 0,
        status: isValidFormat && isValidSize ? "uploading" : "error",
        errorMessage: !isValidFormat 
          ? "Nicht unterstütztes Format" 
          : !isValidSize 
          ? "Datei zu groß (max. 10MB)" 
          : undefined,
      };
    });

    setUploadedFiles((prev) => [...prev, ...newFiles]);

    if (caseId) {
      setUploadedFiles((prev) =>
        prev.map((f) => (newFiles.some((n) => n.id === f.id) && f.status === "uploading" ? { ...f, status: "success", progress: 100 } : f))
      );
    } else {
      newFiles.forEach((uf) => {
        if (uf.status === "uploading") simulateUpload(uf.id);
      });
    }
  };

  const simulateUpload = (fileId: string) => {
    let progress = 0;
    const interval = setInterval(() => {
      progress += 10;
      setUploadedFiles((prev) => prev.map((f) => (f.id === fileId ? { ...f, progress } : f)));
      if (progress >= 100) {
        clearInterval(interval);
        setUploadedFiles((prev) =>
          prev.map((f) => (f.id === fileId ? { ...f, status: "success", progress: 100 } : f))
        );
      }
    }, 200);
  };

  const handleRemoveFile = (fileId: string) => {
    setUploadedFiles((prev) => prev.filter((f) => f.id !== fileId));
  };

  const handleTypeChange = (fileId: string, type: DocumentType) => {
    setUploadedFiles((prev) =>
      prev.map((f) =>
        f.id === fileId ? { ...f, type } : f
      )
    );
  };

  const handleComplete = async () => {
    if (caseId && uploadedFiles.some((f) => f.status === "success" && f.type)) {
      setCompleting(true);
      const toUpload = uploadedFiles.filter((f) => f.status === "success" && f.type !== null) as (UploadedFile & { type: DocumentType })[];
      try {
        const sameType = toUpload.length > 0 && toUpload.every((f) => f.type === toUpload[0].type);
        if (toUpload.length > 1 && sameType) {
          const created = await uploadDocumentsBulk(
            caseId,
            toUpload.map((u) => u.file),
            toUpload[0].type,
            uploadedBy
          );
          if (created.length < toUpload.length) {
            setUploadedFiles((prev) =>
              prev.map((f) =>
                f.status === "success" && f.type
                  ? { ...f, status: "error", errorMessage: `Nur ${created.length} von ${toUpload.length} hochgeladen.` }
                  : f
              )
            );
          } else {
            onUploadComplete?.(uploadedFiles);
          }
        } else {
          for (const uf of toUpload) {
            if (uf.type) await uploadDocument(caseId, uf.file, uf.type, uploadedBy);
          }
          onUploadComplete?.(uploadedFiles);
        }
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Upload fehlgeschlagen";
        setUploadedFiles((prev) =>
          prev.map((f) =>
            f.status === "success" && f.type ? { ...f, status: "error", errorMessage: msg } : f
          )
        );
      } finally {
        setCompleting(false);
      }
    } else {
      onUploadComplete?.(uploadedFiles);
    }
  };

  const canComplete =
    uploadedFiles.length > 0 &&
    uploadedFiles.every((f) => f.status === "success" && f.type !== null) &&
    !completing;

  return (
    <div className="space-y-4">
      {/* Drop Zone */}
      <div
        className={`border-2 border-dashed rounded-lg p-12 text-center transition-all duration-150 ${
          isDragging
            ? "border-primary bg-primary/5 scale-[1.01]"
            : "border-border hover:border-primary/50 hover:bg-muted/30"
        }`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <Upload className={`mx-auto mb-4 transition-transform duration-150 ${isDragging ? "size-14 text-primary" : "size-12 text-muted-foreground/50"}`} />
        {isDragging ? (
          <p className="text-primary font-medium mb-2">Dateien loslassen zum Hochladen</p>
        ) : (
          <p className="text-muted-foreground mb-2">
            Dateien hierher ziehen oder{" "}
            <label className="text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 cursor-pointer">
              klicken zum Auswählen
              <input
                type="file"
                multiple
                accept=".docx,.pdf,.xlsx,.doc,.jpg,.jpeg,.png,.tif,.tiff"
                className="hidden"
                onChange={handleFileSelect}
              />
            </label>
          </p>
        )}
        <p className="text-sm text-muted-foreground">
          Unterstützte Formate: DOCX, PDF, XLSX, DOC, JPG, PNG, TIFF (max. 10 MB)
        </p>
      </div>

      {/* Uploaded Files List */}
      {uploadedFiles.length > 0 && (
        <div className="space-y-3">
          <h4 className="font-medium text-foreground">Hochgeladene Dateien ({uploadedFiles.length})</h4>
          
          {uploadedFiles.map((uploadedFile) => (
            <Card key={uploadedFile.id} className="p-4">
              <div className="flex items-start gap-3">
                <div className="mt-1">
                  {uploadedFile.status === "uploading" && (
                    <div className="size-10 rounded-full bg-blue-100 dark:bg-blue-950/50 flex items-center justify-center">
                      <Upload className="size-5 text-blue-600 dark:text-blue-400 animate-pulse" />
                    </div>
                  )}
                  {uploadedFile.status === "success" && (
                    <div className="size-10 rounded-full bg-green-100 dark:bg-green-950/50 flex items-center justify-center">
                      <Check className="size-5 text-green-600 dark:text-green-400" />
                    </div>
                  )}
                  {uploadedFile.status === "error" && (
                    <div className="size-10 rounded-full bg-red-100 dark:bg-red-950/50 flex items-center justify-center">
                      <CircleAlert className="size-5 text-red-600 dark:text-red-400" />
                    </div>
                  )}
                </div>

                <div className="flex-1">
                  <div className="flex items-start justify-between mb-2">
                    <div>
                      <h5 className="font-medium text-foreground">{uploadedFile.file.name}</h5>
                      <p className="text-sm text-muted-foreground">
                        {(uploadedFile.file.size / 1024).toFixed(0)} KB
                      </p>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleRemoveFile(uploadedFile.id)}
                      aria-label={`${uploadedFile.file.name} entfernen`}
                    >
                      <X className="size-4" />
                    </Button>
                  </div>

                  {uploadedFile.status === "uploading" && (
                    <Progress value={uploadedFile.progress} className="h-1.5" />
                  )}

                  {uploadedFile.status === "error" && uploadedFile.errorMessage && (
                    <div className="flex items-center gap-2 text-red-600 dark:text-red-400 text-sm">
                      <CircleAlert className="size-4" />
                      <span>{uploadedFile.errorMessage}</span>
                    </div>
                  )}

                  {uploadedFile.status === "success" && (
                    <div className="mt-2">
                      <Select
                        value={uploadedFile.type || undefined}
                        onValueChange={(value) => handleTypeChange(uploadedFile.id, value as DocumentType)}
                      >
                        <SelectTrigger className="w-full">
                          <SelectValue placeholder="Dokumenttyp auswählen..." />
                        </SelectTrigger>
                        <SelectContent>
                          {Object.entries(documentTypeLabels).map(([type, label]) => (
                            <SelectItem key={type} value={type}>
                              {label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  )}
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Actions */}
      {uploadedFiles.length > 0 && (
        <div className="flex items-center justify-between pt-4 border-t border-border">
          <p className="text-sm text-muted-foreground">
            {uploadedFiles.filter(f => f.status === "success").length} von {uploadedFiles.length} erfolgreich
            {!canComplete && " • Bitte Dokumenttypen zuweisen"}
          </p>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setUploadedFiles([])}>
              Alle entfernen
            </Button>
            <Button onClick={handleComplete} disabled={!canComplete}>
              {completing ? <Loader2 className="size-4 animate-spin mr-2" /> : null}
              {caseId ? "Hochladen & abschließen" : "Upload abschließen"}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
