import { useState, useEffect } from "react";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "./ui/dialog";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { Textarea } from "./ui/textarea";
import { Badge } from "./ui/badge";
import { FileText, CheckCircle2, Upload, X } from "lucide-react";
import { toast } from "sonner";
import {
  getDepartments,
  getPlaybooks,
  getPlaybooksForSelection,
  createCase,
  uploadDocumentsBulk,
  type ApiCase,
  type ApiDepartment,
  type ApiPlaybook,
} from "../lib/api";
import { documentTypeLabels, type DocumentType } from "../lib/mock-data";

interface NewCaseDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess?: (newCase: ApiCase) => void;
}

const ALLOWED_EXTENSIONS = [".docx", ".pdf", ".xlsx", ".doc"];
const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB

const PROCESSING_CONTEXT_NONE = "none";

const PROCESSING_CONTEXT_OPTIONS: { value: string; label: string }[] = [
  { value: PROCESSING_CONTEXT_NONE, label: "Keiner / nicht festgelegt" },
  { value: "research", label: "Forschung" },
  { value: "hr", label: "Personal" },
  { value: "it_operations", label: "IT-Betrieb" },
  { value: "communications", label: "Öffentlichkeitsarbeit / Kommunikation" },
  { value: "procurement", label: "Beschaffung" },
  { value: "other", label: "Sonstiges" },
];

export function NewCaseDialog({ open, onOpenChange, onSuccess }: NewCaseDialogProps) {
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [departmentsFromApi, setDepartmentsFromApi] = useState<ApiDepartment[]>([]);
  const [playbooks, setPlaybooks] = useState<ApiPlaybook[]>([]);
  const [playbooksForStep2, setPlaybooksForStep2] = useState<ApiPlaybook[]>([]);
  const [loading, setLoading] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [pendingFiles, setPendingFiles] = useState<File[]>([]);
  const [pendingDocumentType, setPendingDocumentType] = useState<DocumentType>("other");
  const [formData, setFormData] = useState({
    title: "",
    department: "",
    caseType: "",
    language: "de" as "de" | "en" | "de_en",
    description: "",
    assignee: "DSB Team",
    processingContext: PROCESSING_CONTEXT_NONE,
    specialCategoryData: false,
    internationalTransfer: false,
  });

  useEffect(() => {
    if (!open) return;
    getDepartments()
      .then(setDepartmentsFromApi)
      .catch(() => setDepartmentsFromApi([]));
    getPlaybooks().then(setPlaybooks).catch(() => setPlaybooks([]));
  }, [open]);

  useEffect(() => {
    if (!open || step !== 2 || !formData.department) {
      setPlaybooksForStep2([]);
      return;
    }
    let cancelled = false;
    getPlaybooksForSelection({
      department: formData.department,
      processing_context:
        formData.processingContext === PROCESSING_CONTEXT_NONE
          ? undefined
          : formData.processingContext.trim() || undefined,
      strict_case_type: false,
    })
      .then((rows) => {
        if (cancelled) return;
        const fromApi = rows.map((r) => r.playbook).filter((pb) => pb.isActive);
        if (fromApi.length > 0) {
          setPlaybooksForStep2(fromApi);
          return;
        }
        setPlaybooksForStep2(
          playbooks.filter((pb) => pb.department === formData.department && pb.isActive),
        );
      })
      .catch(() => {
        if (cancelled) return;
        setPlaybooksForStep2(
          playbooks.filter((pb) => pb.department === formData.department && pb.isActive),
        );
      });
    return () => {
      cancelled = true;
    };
  }, [open, step, formData.department, formData.processingContext, playbooks]);

  const departments: string[] =
    departmentsFromApi.length > 0
      ? departmentsFromApi.map((d) => d.value)
      : Array.from(new Set(playbooks.map((pb) => pb.department).filter(Boolean))) as string[];
  const selectedPlaybooks = step === 2 ? playbooksForStep2 : [];

  const handleSubmit = async () => {
    setSubmitError(null);
    setLoading(true);
    try {
      const newCase = await createCase({
        title: formData.title,
        department: formData.department,
        case_type: formData.caseType,
        language: formData.language,
        created_by: "",
        assignee: formData.assignee,
        processing_context:
          formData.processingContext === PROCESSING_CONTEXT_NONE
            ? null
            : formData.processingContext.trim() || null,
        special_category_data: formData.specialCategoryData,
        international_transfer: formData.internationalTransfer,
      });
      if (pendingFiles.length > 0) {
        await uploadDocumentsBulk(newCase.id, pendingFiles, pendingDocumentType, formData.assignee || "");
      }
      onOpenChange(false);
      setStep(1);
      setPendingFiles([]);
      setPendingDocumentType("other");
      setFormData({
        title: "",
        department: "",
        caseType: "",
        language: "de",
        description: "",
        assignee: "DSB Team",
        processingContext: PROCESSING_CONTEXT_NONE,
        specialCategoryData: false,
        internationalTransfer: false,
      });
      toast.success("Vorgang erfolgreich angelegt");
      onSuccess?.(newCase);
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : "Fehler beim Anlegen");
    } finally {
      setLoading(false);
    }
  };

  const addPendingFiles = (files: FileList | null) => {
    if (!files?.length) return;
    const valid: File[] = [];
    for (let i = 0; i < files.length; i++) {
      const f = files[i];
      const ext = "." + (f.name.split(".").pop()?.toLowerCase() ?? "");
      if (ALLOWED_EXTENSIONS.includes(ext) && f.size <= MAX_FILE_SIZE) valid.push(f);
    }
    setPendingFiles((prev) => [...prev, ...valid]);
  };

  const removePendingFile = (index: number) => {
    setPendingFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const canProceedToStep2 = formData.title && formData.department;
  const canSubmit = formData.title && formData.department && formData.caseType;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Neuen Vorgang anlegen</DialogTitle>
          <DialogDescription>
            {step === 1 && "Geben Sie die Grundinformationen zum Forschungsvorhaben ein."}
            {step === 2 && "Wählen Sie das passende Playbook für die Vorprüfung."}
            {step === 3 && "Optional: Dokumente hinzufügen. Sie können auch später auf der Vorgangsseite hochladen."}
          </DialogDescription>
        </DialogHeader>

        {/* Step Indicator */}
        <div className="flex items-center gap-2 mb-4">
          <div className="flex items-center gap-2">
            <div className={`size-8 rounded-full flex items-center justify-center text-sm font-medium ${step >= 1 ? "bg-blue-600 text-white" : "bg-muted text-muted-foreground"}`}>
              {step > 1 ? <CheckCircle2 className="size-5" /> : "1"}
            </div>
            <span className="hidden sm:block text-sm font-medium">Grunddaten</span>
          </div>
          <div className="flex-1 h-px bg-border" />
          <div className="flex items-center gap-2">
            <div className={`size-8 rounded-full flex items-center justify-center text-sm font-medium ${step >= 2 ? "bg-blue-600 text-white" : "bg-muted text-muted-foreground"}`}>
              {step > 2 ? <CheckCircle2 className="size-5" /> : "2"}
            </div>
            <span className="hidden sm:block text-sm font-medium">Playbook</span>
          </div>
          <div className="flex-1 h-px bg-border" />
          <div className="flex items-center gap-2">
            <div className={`size-8 rounded-full flex items-center justify-center text-sm font-medium ${step >= 3 ? "bg-blue-600 text-white" : "bg-muted text-muted-foreground"}`}>
              3
            </div>
            <span className="hidden sm:block text-sm font-medium">Dokumente (optional)</span>
          </div>
        </div>

        {step === 1 && (
          <div className="space-y-4">
            {/* Title */}
            <div className="space-y-2">
              <Label htmlFor="title">
                Titel des Forschungsvorhabens <span className="text-red-600 dark:text-red-400">*</span>
              </Label>
              <Input
                id="title"
                placeholder="z.B. Longitudinalstudie zur Burnout-Prävention"
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
              />
            </div>

            {/* Department */}
            <div className="space-y-2">
              <Label htmlFor="department">
                Fachbereich <span className="text-red-600 dark:text-red-400">*</span>
              </Label>
              <Select
                value={formData.department}
                onValueChange={(value) =>
                  setFormData({ ...formData, department: value, caseType: "" })
                }
              >
                <SelectTrigger id="department">
                  <SelectValue placeholder="Fachbereich auswählen" />
                </SelectTrigger>
                <SelectContent>
                  {departments.map((value) => (
                    <SelectItem key={value} value={value}>
                      {value}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="processingContext">Verarbeitungskontext (optional)</Label>
              <Select
                value={formData.processingContext}
                onValueChange={(value) =>
                  setFormData({ ...formData, processingContext: value, caseType: "" })
                }
              >
                <SelectTrigger id="processingContext">
                  <SelectValue placeholder="Kontext wählen" />
                </SelectTrigger>
                <SelectContent>
                  {PROCESSING_CONTEXT_OPTIONS.map((o) => (
                    <SelectItem key={o.value} value={o.value}>
                      {o.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="flex flex-col gap-3 rounded-md border border-border p-3">
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input
                  type="checkbox"
                  checked={formData.specialCategoryData}
                  onChange={(e) =>
                    setFormData({ ...formData, specialCategoryData: e.target.checked })
                  }
                  className="rounded border-input"
                />
                Besondere Kategorien personenbezogener Daten (Art. 9 DSGVO)
              </label>
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input
                  type="checkbox"
                  checked={formData.internationalTransfer}
                  onChange={(e) =>
                    setFormData({ ...formData, internationalTransfer: e.target.checked })
                  }
                  className="rounded border-input"
                />
                Grenzüberschreitende Datenübermittlung relevant
              </label>
            </div>

            {/* Language */}
            <div className="space-y-2">
              <Label htmlFor="language">Sprache</Label>
              <Select value={formData.language} onValueChange={(value) => setFormData({ ...formData, language: value })}>
                <SelectTrigger id="language">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="de">Deutsch</SelectItem>
                  <SelectItem value="en">Englisch</SelectItem>
                  <SelectItem value="de_en">Deutsch + Englisch</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Description */}
            <div className="space-y-2">
              <Label htmlFor="description">Beschreibung (optional)</Label>
              <Textarea
                id="description"
                placeholder="Kurze Beschreibung des Vorhabens..."
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                rows={3}
              />
            </div>

            {/* Assignee */}
            <div className="space-y-2">
              <Label htmlFor="assignee">Zugewiesen an</Label>
              <Select value={formData.assignee} onValueChange={(value) => setFormData({ ...formData, assignee: value })}>
                <SelectTrigger id="assignee">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="DSB Team">DSB Team</SelectItem>
                  <SelectItem value="Dr. Müller">Dr. Müller (DSB)</SelectItem>
                  <SelectItem value="Lisa Schmidt">Lisa Schmidt (Reviewer)</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-4">
            <div className="p-4 bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 rounded-lg">
              <h4 className="font-medium text-blue-900 dark:text-blue-100 mb-1">Fachbereich: {formData.department}</h4>
              <p className="text-sm text-blue-700 dark:text-blue-300">
                {selectedPlaybooks.length} {selectedPlaybooks.length === 1 ? "aktives Playbook" : "aktive Playbooks"} verfügbar
              </p>
            </div>

            <div className="space-y-2">
              <Label>
                Case-Typ / Playbook auswählen <span className="text-red-600 dark:text-red-400">*</span>
              </Label>
              <div className="space-y-3">
                {selectedPlaybooks.length === 0 && (
                  <div className="text-center py-8 text-muted-foreground">
                    <FileText className="size-12 mx-auto mb-2 text-muted-foreground/40" />
                    <p>Keine aktiven Playbooks für diesen Fachbereich verfügbar.</p>
                    <p className="text-sm mt-1">Bitte wählen Sie einen anderen Fachbereich.</p>
                  </div>
                )}
                {selectedPlaybooks.map((playbook) => (
                  <div
                    key={playbook.id}
                    className={`p-4 border rounded-lg cursor-pointer transition-all ${
                      formData.caseType === (playbook.caseType ?? "")
                        ? "border-blue-600 bg-blue-50 dark:bg-blue-950/30"
                        : "border-border hover:border-blue-300 dark:hover:border-blue-700"
                    }`}
                    onClick={() => setFormData({ ...formData, caseType: playbook.caseType ?? playbook.name })}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <h4 className="font-medium text-foreground">{playbook.name}</h4>
                          <Badge variant="outline">{playbook.version}</Badge>
                        </div>
                        <p className="text-sm text-muted-foreground mb-2">{playbook.caseType ?? playbook.name}</p>
                        <div className="flex items-center gap-4 text-xs text-muted-foreground">
                          <span>{playbook.checks?.length ?? 0} Checks</span>
                        </div>
                      </div>
                      {formData.caseType === (playbook.caseType ?? playbook.name) && (
                        <CheckCircle2 className="size-5 text-blue-600 flex-shrink-0" />
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Sie können jetzt Dokumente hinzufügen oder den Vorgang ohne Dokumente anlegen und später hochladen.
            </p>
            <div className="space-y-2">
              <Label>Dokumenttyp (für alle ausgewählten Dateien)</Label>
              <Select value={pendingDocumentType} onValueChange={(v) => setPendingDocumentType(v as DocumentType)}>
                <SelectTrigger>
                  <SelectValue />
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
            <div className="border-2 border-dashed border-border rounded-lg p-6 text-center hover:border-primary/50 transition-colors">
              <Upload className="size-10 mx-auto mb-2 text-muted-foreground/50" />
              <Label className="text-blue-600 hover:text-blue-700 cursor-pointer">
                Dateien auswählen
                <input
                  type="file"
                  multiple
                  accept=".docx,.pdf,.xlsx,.doc"
                  className="hidden"
                  onChange={(e) => addPendingFiles(e.target.files)}
                />
              </Label>
              <p className="text-sm text-muted-foreground mt-1">DOCX, PDF, XLSX, DOC (max. 10 MB)</p>
            </div>
            {pendingFiles.length > 0 && (
              <ul className="space-y-2">
                {pendingFiles.map((f, i) => (
                  <li key={i} className="flex items-center justify-between rounded border px-3 py-2 text-sm">
                    <span className="truncate">{f.name}</span>
                    <Button type="button" variant="ghost" size="sm" onClick={() => removePendingFile(i)} aria-label={`${f.name} entfernen`}>
                      <X className="size-4" />
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {submitError && (
          <p className="text-sm text-red-600 dark:text-red-400">{submitError}</p>
        )}
        <DialogFooter className="flex-col-reverse gap-2 sm:flex-row sm:gap-0">
          {step >= 2 && (
            <Button variant="outline" onClick={() => setStep((s) => (s - 1) as 1 | 2 | 3)}>
              Zurück
            </Button>
          )}
          {step === 1 && (
            <Button onClick={() => setStep(2)} disabled={!canProceedToStep2}>
              Weiter
            </Button>
          )}
          {step === 2 && (
            <>
              <Button variant="outline" onClick={handleSubmit} disabled={!canSubmit || loading}>
                {loading ? "Wird angelegt…" : "Ohne Dokumente anlegen"}
              </Button>
              <Button onClick={() => setStep(3)} disabled={!canSubmit}>
                Weiter
              </Button>
            </>
          )}
          {step === 3 && (
            <Button onClick={handleSubmit} disabled={loading}>
              {loading ? "Wird angelegt…" : pendingFiles.length > 0 ? "Vorgang anlegen & Dokumente hochladen" : "Vorgang anlegen"}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
