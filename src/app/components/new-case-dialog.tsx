import { useState, useEffect } from "react";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "./ui/dialog";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { Textarea } from "./ui/textarea";
import { Badge } from "./ui/badge";
import { FileText, CheckCircle2 } from "lucide-react";
import { getDepartments, getPlaybooks, createCase, type ApiCase, type ApiDepartment, type ApiPlaybook } from "../lib/api";

interface NewCaseDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess?: (newCase: ApiCase) => void;
}

export function NewCaseDialog({ open, onOpenChange, onSuccess }: NewCaseDialogProps) {
  const [step, setStep] = useState<1 | 2>(1);
  const [departmentsFromApi, setDepartmentsFromApi] = useState<ApiDepartment[]>([]);
  const [playbooks, setPlaybooks] = useState<ApiPlaybook[]>([]);
  const [loading, setLoading] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [formData, setFormData] = useState({
    title: "",
    department: "",
    caseType: "",
    language: "de" as "de" | "en" | "de_en",
    description: "",
    assignee: "DSB Team",
  });

  useEffect(() => {
    if (!open) return;
    getDepartments()
      .then(setDepartmentsFromApi)
      .catch(() => setDepartmentsFromApi([]));
    getPlaybooks().then(setPlaybooks).catch(() => setPlaybooks([]));
  }, [open]);

  const departments: string[] =
    departmentsFromApi.length > 0
      ? departmentsFromApi.map((d) => d.value)
      : Array.from(new Set(playbooks.map((pb) => pb.department).filter(Boolean))) as string[];
  const selectedPlaybooks = playbooks.filter(
    pb => pb.department === formData.department && pb.isActive
  );

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
      });
      onOpenChange(false);
      setStep(1);
      setFormData({
        title: "",
        department: "",
        caseType: "",
        language: "de",
        description: "",
        assignee: "DSB Team",
      });
      onSuccess?.(newCase);
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : "Fehler beim Anlegen");
    } finally {
      setLoading(false);
    }
  };

  const canProceedToStep2 = formData.title && formData.department;
  const canSubmit = formData.title && formData.department && formData.caseType;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Neuen Vorgang anlegen</DialogTitle>
          <DialogDescription>
            {step === 1 ? "Geben Sie die Grundinformationen zum Forschungsvorhaben ein." : "Wählen Sie das passende Playbook für die Vorprüfung."}
          </DialogDescription>
        </DialogHeader>

        {/* Step Indicator */}
        <div className="flex items-center gap-4 mb-4">
          <div className="flex items-center gap-2">
            <div className={`size-8 rounded-full flex items-center justify-center ${step >= 1 ? 'bg-blue-600 text-white' : 'bg-slate-200 text-slate-600'}`}>
              {step > 1 ? <CheckCircle2 className="size-5" /> : "1"}
            </div>
            <span className="text-sm font-medium">Grunddaten</span>
          </div>
          <div className="flex-1 h-px bg-slate-200" />
          <div className="flex items-center gap-2">
            <div className={`size-8 rounded-full flex items-center justify-center ${step >= 2 ? 'bg-blue-600 text-white' : 'bg-slate-200 text-slate-600'}`}>
              2
            </div>
            <span className="text-sm font-medium">Playbook</span>
          </div>
        </div>

        {step === 1 && (
          <div className="space-y-4">
            {/* Title */}
            <div className="space-y-2">
              <Label htmlFor="title">
                Titel des Forschungsvorhabens <span className="text-red-600">*</span>
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
                Fachbereich <span className="text-red-600">*</span>
              </Label>
              <Select value={formData.department} onValueChange={(value) => setFormData({ ...formData, department: value, caseType: "" })}>
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
            <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
              <h4 className="font-medium text-blue-900 mb-1">Fachbereich: {formData.department}</h4>
              <p className="text-sm text-blue-700">
                {selectedPlaybooks.length} {selectedPlaybooks.length === 1 ? "aktives Playbook" : "aktive Playbooks"} verfügbar
              </p>
            </div>

            <div className="space-y-2">
              <Label>
                Case-Typ / Playbook auswählen <span className="text-red-600">*</span>
              </Label>
              <div className="space-y-3">
                {selectedPlaybooks.length === 0 && (
                  <div className="text-center py-8 text-slate-500">
                    <FileText className="size-12 mx-auto mb-2 text-slate-300" />
                    <p>Keine aktiven Playbooks für diesen Fachbereich verfügbar.</p>
                    <p className="text-sm mt-1">Bitte wählen Sie einen anderen Fachbereich.</p>
                  </div>
                )}
                {selectedPlaybooks.map((playbook) => (
                  <div
                    key={playbook.id}
                    className={`p-4 border rounded-lg cursor-pointer transition-all ${
                      formData.caseType === (playbook.caseType ?? "")
                        ? "border-blue-600 bg-blue-50"
                        : "border-slate-200 hover:border-blue-300"
                    }`}
                    onClick={() => setFormData({ ...formData, caseType: playbook.caseType ?? playbook.name })}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <h4 className="font-medium text-slate-900">{playbook.name}</h4>
                          <Badge variant="outline">{playbook.version}</Badge>
                        </div>
                        <p className="text-sm text-slate-600 mb-2">{playbook.caseType ?? playbook.name}</p>
                        <div className="flex items-center gap-4 text-xs text-slate-500">
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

        {submitError && (
          <p className="text-sm text-red-600">{submitError}</p>
        )}
        <DialogFooter>
          {step === 2 && (
            <Button variant="outline" onClick={() => setStep(1)}>
              Zurück
            </Button>
          )}
          {step === 1 && (
            <Button onClick={() => setStep(2)} disabled={!canProceedToStep2}>
              Weiter
            </Button>
          )}
          {step === 2 && (
            <Button onClick={handleSubmit} disabled={!canSubmit || loading}>
              {loading ? "Wird angelegt…" : "Vorgang anlegen"}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
