import { useState } from "react";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Label } from "../ui/label";
import { Textarea } from "../ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../ui/dialog";
import { createDataBreach, type ApiDataBreach, type DataBreachCreate } from "../../lib/api";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";

interface NewBreachForm {
  title: string;
  description: string;
  discovered_at: string;
  breach_type: "confidentiality" | "integrity" | "availability";
  affected_data_categories: string;
  affected_persons_count: string;
  department: string;
  assignee: string;
  risk_level: string;
  measures_taken: string;
}

const defaultForm: NewBreachForm = {
  title: "",
  description: "",
  discovered_at: new Date().toISOString().slice(0, 16),
  breach_type: "confidentiality",
  affected_data_categories: "",
  affected_persons_count: "",
  department: "",
  assignee: "",
  risk_level: "",
  measures_taken: "",
};

interface DataBreachCreateDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: (breach: ApiDataBreach) => void;
}

export function DataBreachCreateDialog({
  open,
  onOpenChange,
  onCreated,
}: DataBreachCreateDialogProps) {
  const [form, setForm] = useState<NewBreachForm>(defaultForm);
  const [creating, setCreating] = useState(false);

  const handleCreate = async () => {
    if (!form.title.trim()) {
      toast.error("Titel ist erforderlich.");
      return;
    }
    setCreating(true);
    try {
      const body: DataBreachCreate = {
        title: form.title.trim(),
        description: form.description.trim() || undefined,
        discovered_at: new Date(form.discovered_at).toISOString(),
        breach_type: form.breach_type,
        affected_data_categories: form.affected_data_categories
          ? form.affected_data_categories
              .split(",")
              .map((s) => s.trim())
              .filter(Boolean)
          : undefined,
        affected_persons_count: form.affected_persons_count
          ? Number(form.affected_persons_count)
          : undefined,
        department: form.department.trim() || undefined,
        assignee: form.assignee.trim(),
        risk_level: (form.risk_level || undefined) as DataBreachCreate["risk_level"],
        measures_taken: form.measures_taken.trim() || undefined,
      };
      const created = await createDataBreach(body);
      toast.success("Datenpanne erfasst.");
      setForm(defaultForm);
      onOpenChange(false);
      onCreated(created);
    } catch {
      toast.error("Fehler beim Erfassen der Datenpanne.");
    } finally {
      setCreating(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Datenpanne erfassen</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <div>
            <Label>Titel *</Label>
            <Input
              value={form.title}
              onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
              placeholder="Kurze Beschreibung der Verletzung"
            />
          </div>
          <div>
            <Label>Beschreibung</Label>
            <Textarea
              value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              rows={3}
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label>Entdeckt am *</Label>
              <Input
                type="datetime-local"
                value={form.discovered_at}
                onChange={(e) => setForm((f) => ({ ...f, discovered_at: e.target.value }))}
              />
            </div>
            <div>
              <Label>Art der Verletzung *</Label>
              <Select
                value={form.breach_type}
                onValueChange={(v) =>
                  setForm((f) => ({ ...f, breach_type: v as NewBreachForm["breach_type"] }))
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="confidentiality">Vertraulichkeit</SelectItem>
                  <SelectItem value="integrity">Integrität</SelectItem>
                  <SelectItem value="availability">Verfügbarkeit</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label>Datenkategorien (kommasepariert)</Label>
              <Input
                value={form.affected_data_categories}
                onChange={(e) =>
                  setForm((f) => ({ ...f, affected_data_categories: e.target.value }))
                }
                placeholder="z.B. Name, E-Mail, Adresse"
              />
            </div>
            <div>
              <Label>Betroffene Personen (ca.)</Label>
              <Input
                type="number"
                value={form.affected_persons_count}
                onChange={(e) =>
                  setForm((f) => ({ ...f, affected_persons_count: e.target.value }))
                }
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label>Abteilung</Label>
              <Input
                value={form.department}
                onChange={(e) => setForm((f) => ({ ...f, department: e.target.value }))}
              />
            </div>
            <div>
              <Label>Zuständig</Label>
              <Input
                value={form.assignee}
                onChange={(e) => setForm((f) => ({ ...f, assignee: e.target.value }))}
              />
            </div>
          </div>
          <div>
            <Label>Risikostufe</Label>
            <Select
              value={form.risk_level || "none"}
              onValueChange={(v) =>
                setForm((f) => ({ ...f, risk_level: v === "none" ? "" : v }))
              }
            >
              <SelectTrigger>
                <SelectValue placeholder="Risiko bewerten" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">Nicht bewertet</SelectItem>
                <SelectItem value="low">Niedrig</SelectItem>
                <SelectItem value="medium">Mittel</SelectItem>
                <SelectItem value="high">Hoch</SelectItem>
                <SelectItem value="critical">Kritisch</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label>Ergriffene Maßnahmen</Label>
            <Textarea
              value={form.measures_taken}
              onChange={(e) => setForm((f) => ({ ...f, measures_taken: e.target.value }))}
              rows={2}
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Abbrechen
          </Button>
          <Button onClick={() => void handleCreate()} disabled={creating}>
            {creating && <Loader2 className="size-4 mr-1 animate-spin" />}
            Erfassen
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
