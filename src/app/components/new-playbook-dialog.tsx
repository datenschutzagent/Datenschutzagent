import { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "./ui/dialog";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { Textarea } from "./ui/textarea";
import { getDepartments, createPlaybook, updatePlaybook, type ApiDepartment, type ApiPlaybook } from "../lib/api";
import { Plus, Trash2 } from "lucide-react";

interface CheckRow {
  name: string;
  instruction: string;
}

interface NewPlaybookDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initialPlaybook?: ApiPlaybook | null;
  onSuccess?: (playbook: ApiPlaybook) => void;
}

export function NewPlaybookDialog({
  open,
  onOpenChange,
  initialPlaybook,
  onSuccess,
}: NewPlaybookDialogProps) {
  const isEdit = Boolean(initialPlaybook?.id);
  const [departments, setDepartments] = useState<ApiDepartment[]>([]);
  const [loading, setLoading] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [version, setVersion] = useState("1.0");
  const [department, setDepartment] = useState<string>("");
  const [caseType, setCaseType] = useState("");
  const [checks, setChecks] = useState<CheckRow[]>([{ name: "", instruction: "" }]);

  useEffect(() => {
    if (open) getDepartments().then(setDepartments).catch(() => setDepartments([]));
  }, [open]);

  useEffect(() => {
    if (open && initialPlaybook) {
      setName(initialPlaybook.name);
      setVersion(initialPlaybook.version ?? "1.0");
      setDepartment(initialPlaybook.department ?? "");
      setCaseType(initialPlaybook.caseType ?? "");
      const raw = initialPlaybook.checks ?? [];
      const rows: CheckRow[] = Array.isArray(raw)
        ? (raw as Record<string, unknown>[]).map((c) => ({
            name: (c.name as string) ?? (c.check_name as string) ?? "",
            instruction:
              (c.instruction as string) ?? (c.requirement as string) ?? (c.description as string) ?? "",
          }))
        : [{ name: "", instruction: "" }];
      setChecks(rows.length ? rows : [{ name: "", instruction: "" }]);
    } else if (open && !initialPlaybook) {
      setName("");
      setVersion("1.0");
      setDepartment("");
      setCaseType("");
      setChecks([{ name: "", instruction: "" }]);
    }
  }, [open, initialPlaybook]);

  const addCheck = () => setChecks((prev) => [...prev, { name: "", instruction: "" }]);
  const removeCheck = (index: number) =>
    setChecks((prev) => (prev.length <= 1 ? [{ name: "", instruction: "" }] : prev.filter((_, i) => i !== index)));
  const updateCheck = (index: number, field: "name" | "instruction", value: string) =>
    setChecks((prev) => prev.map((c, i) => (i === index ? { ...c, [field]: value } : c)));

  const handleSubmit = async () => {
    setSubmitError(null);
    if (!name.trim() || !version.trim()) {
      setSubmitError("Name und Version sind erforderlich.");
      return;
    }
    const contentChecks = checks
      .filter((c) => c.name.trim() || c.instruction.trim())
      .map((c) => ({ name: c.name.trim() || "Check", instruction: c.instruction.trim() || "" }));
    if (!contentChecks.length) {
      setSubmitError("Mindestens ein Check mit Name und Anweisung ist erforderlich.");
      return;
    }
    const content = { checks: contentChecks };
    setLoading(true);
    try {
      if (isEdit && initialPlaybook?.id) {
        const updated = await updatePlaybook(initialPlaybook.id, {
          name: name.trim(),
          version: version.trim(),
          content,
          case_type: caseType.trim() || null,
          department: department || null,
        });
        onOpenChange(false);
        onSuccess?.(updated);
      } else {
        const created = await createPlaybook({
          name: name.trim(),
          version: version.trim(),
          content,
          case_type: caseType.trim() || null,
          department: department || null,
        });
        onOpenChange(false);
        onSuccess?.(created);
      }
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : "Fehler beim Speichern");
    } finally {
      setLoading(false);
    }
  };

  const departmentValues = departments.map((d) => d.value);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isEdit ? "Playbook bearbeiten" : "Neues Playbook"}</DialogTitle>
          <DialogDescription>
            {isEdit
              ? "Metadaten und Checks anpassen."
              : "Neues Playbook anlegen. Mindestens ein Check mit Name und Prüfanweisung ist erforderlich."}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="pb-name">Name *</Label>
              <Input
                id="pb-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="z.B. Datenschutz-Vorprüfung FB 01"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="pb-version">Version *</Label>
              <Input
                id="pb-version"
                value={version}
                onChange={(e) => setVersion(e.target.value)}
                placeholder="1.0"
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Fachbereich</Label>
              <Select value={department} onValueChange={setDepartment}>
                <SelectTrigger>
                  <SelectValue placeholder="Fachbereich wählen" />
                </SelectTrigger>
                <SelectContent>
                  {departmentValues.map((v) => (
                    <SelectItem key={v} value={v}>
                      {v}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="pb-case-type">Case-Typ</Label>
              <Input
                id="pb-case-type"
                value={caseType}
                onChange={(e) => setCaseType(e.target.value)}
                placeholder="z.B. Forschungsvorhaben"
              />
            </div>
          </div>
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label>Checks *</Label>
              <Button type="button" variant="outline" size="sm" onClick={addCheck} className="gap-1">
                <Plus className="size-4" />
                Check hinzufügen
              </Button>
            </div>
            <div className="space-y-3 border rounded-lg p-3 bg-slate-50 dark:bg-slate-800/50 max-h-[280px] overflow-y-auto">
              {checks.map((check, index) => (
                <div key={index} className="flex gap-2 items-start">
                  <div className="flex-1 space-y-2">
                    <Input
                      placeholder="Check-Name"
                      value={check.name}
                      onChange={(e) => updateCheck(index, "name", e.target.value)}
                    />
                    <Textarea
                      placeholder="Prüfanweisung (instruction)"
                      value={check.instruction}
                      onChange={(e) => updateCheck(index, "instruction", e.target.value)}
                      rows={2}
                      className="resize-none"
                    />
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    onClick={() => removeCheck(index)}
                    className="text-slate-500 dark:text-slate-400 hover:text-red-600 dark:hover:text-red-400"
                  >
                    <Trash2 className="size-4" />
                  </Button>
                </div>
              ))}
            </div>
          </div>
        </div>
        {submitError && <p className="text-sm text-red-600 dark:text-red-400">{submitError}</p>}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Abbrechen
          </Button>
          <Button onClick={handleSubmit} disabled={loading}>
            {loading ? "Wird gespeichert…" : isEdit ? "Speichern" : "Anlegen"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
