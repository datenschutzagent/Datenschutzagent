import { useState, useEffect, useCallback } from "react";
import { AppLayout } from "../components/app-layout";
import { PageHeader } from "../components/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../components/ui/dialog";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "../components/ui/alert-dialog";
import { Skeleton } from "../components/ui/skeleton";
import { Separator } from "../components/ui/separator";
import {
  listDataBreaches,
  createDataBreach,
  updateDataBreach,
  deleteDataBreach,
  generateBreachNotification,
  getDataBreachActivity,
  type ApiDataBreach,
  type ApiDataBreachActivity,
  type DataBreachCreate,
} from "../lib/api";
import { toast } from "sonner";
import {
  AlertTriangle,
  Plus,
  Clock,
  CheckCircle,
  ShieldAlert,
  Loader2,
  FileText,
  Trash2,
  Eye,
} from "lucide-react";

const BREACH_TYPE_LABELS: Record<string, string> = {
  confidentiality: "Vertraulichkeit",
  integrity: "Integrität",
  availability: "Verfügbarkeit",
};

const STATUS_LABELS: Record<string, string> = {
  discovered: "Entdeckt",
  assessed: "Bewertet",
  reported_to_authority: "Behörde gemeldet",
  reported_to_subjects: "Betroffene informiert",
  closed: "Abgeschlossen",
  no_notification_required: "Keine Meldung nötig",
};

const RISK_COLORS: Record<string, string> = {
  low: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300",
  medium: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300",
  high: "bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300",
  critical: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300",
};

const RISK_LABELS: Record<string, string> = {
  low: "Niedrig",
  medium: "Mittel",
  high: "Hoch",
  critical: "Kritisch",
};

function hoursUntilDeadline(deadline: string): number {
  return (new Date(deadline).getTime() - Date.now()) / 3_600_000;
}

function DeadlineIndicator({ deadline, status }: { deadline: string; status: string }) {
  const hours = hoursUntilDeadline(deadline);
  const notified = ["reported_to_authority", "closed", "no_notification_required"].includes(status);
  if (notified) return <span className="text-xs text-green-600 dark:text-green-400 flex items-center gap-1"><CheckCircle className="size-3" /> Erledigt</span>;
  if (hours < 0) return <span className="text-xs text-red-600 font-semibold flex items-center gap-1"><AlertTriangle className="size-3" /> Frist überschritten</span>;
  if (hours < 12) return <span className="text-xs text-red-500 font-semibold flex items-center gap-1"><Clock className="size-3" /> {Math.round(hours)}h verbleibend</span>;
  if (hours < 48) return <span className="text-xs text-orange-500 flex items-center gap-1"><Clock className="size-3" /> {Math.round(hours)}h verbleibend</span>;
  return <span className="text-xs text-slate-500 flex items-center gap-1"><Clock className="size-3" /> {Math.round(hours)}h verbleibend</span>;
}

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

export function DataBreachesPage() {
  const [breaches, setBreaches] = useState<ApiDataBreach[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("all");
  const [overdueOnly, setOverdueOnly] = useState(false);

  const [showNew, setShowNew] = useState(false);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState<NewBreachForm>(defaultForm);

  const [selected, setSelected] = useState<ApiDataBreach | null>(null);
  const [activity, setActivity] = useState<ApiDataBreachActivity[]>([]);
  const [loadingActivity, setLoadingActivity] = useState(false);
  const [generatingDraft, setGeneratingDraft] = useState(false);
  const [updatingStatus, setUpdatingStatus] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await listDataBreaches({
        status: statusFilter !== "all" ? statusFilter : undefined,
        overdueOnly,
      });
      setBreaches(r.items);
      setTotal(r.total);
    } catch {
      toast.error("Datenpannen konnten nicht geladen werden.");
    } finally {
      setLoading(false);
    }
  }, [statusFilter, overdueOnly]);

  useEffect(() => { void load(); }, [load]);

  async function openDetail(b: ApiDataBreach) {
    setSelected(b);
    setLoadingActivity(true);
    try {
      const acts = await getDataBreachActivity(b.id);
      setActivity(acts);
    } finally {
      setLoadingActivity(false);
    }
  }

  async function handleCreate() {
    if (!form.title.trim()) { toast.error("Titel ist erforderlich."); return; }
    setCreating(true);
    try {
      const body: DataBreachCreate = {
        title: form.title.trim(),
        description: form.description.trim() || undefined,
        discovered_at: new Date(form.discovered_at).toISOString(),
        breach_type: form.breach_type,
        affected_data_categories: form.affected_data_categories
          ? form.affected_data_categories.split(",").map((s) => s.trim()).filter(Boolean)
          : undefined,
        affected_persons_count: form.affected_persons_count ? Number(form.affected_persons_count) : undefined,
        department: form.department.trim() || undefined,
        assignee: form.assignee.trim(),
        risk_level: (form.risk_level || undefined) as DataBreachCreate["risk_level"],
        measures_taken: form.measures_taken.trim() || undefined,
      };
      await createDataBreach(body);
      toast.success("Datenpanne erfasst.");
      setShowNew(false);
      setForm(defaultForm);
      void load();
    } catch {
      toast.error("Fehler beim Erfassen der Datenpanne.");
    } finally {
      setCreating(false);
    }
  }

  async function handleGenerateDraft() {
    if (!selected) return;
    setGeneratingDraft(true);
    try {
      const updated = await generateBreachNotification(selected.id);
      setSelected(updated);
      toast.success("Meldungsentwurf generiert.");
    } catch {
      toast.error("Fehler beim Generieren des Entwurfs.");
    } finally {
      setGeneratingDraft(false);
    }
  }

  async function handleStatusChange(newStatus: string) {
    if (!selected) return;
    setUpdatingStatus(true);
    try {
      const updated = await updateDataBreach(selected.id, { status: newStatus });
      setSelected(updated);
      setBreaches((prev) => prev.map((b) => b.id === updated.id ? updated : b));
      toast.success("Status aktualisiert.");
    } catch {
      toast.error("Fehler beim Aktualisieren.");
    } finally {
      setUpdatingStatus(false);
    }
  }

  async function handleDelete(id: string) {
    try {
      await deleteDataBreach(id);
      setBreaches((prev) => prev.filter((b) => b.id !== id));
      setTotal((t) => t - 1);
      if (selected?.id === id) setSelected(null);
      toast.success("Datenpanne gelöscht.");
    } catch {
      toast.error("Fehler beim Löschen.");
    }
  }

  const overdue = breaches.filter(
    (b) => !["reported_to_authority", "closed", "no_notification_required"].includes(b.status)
      && hoursUntilDeadline(b.notificationDeadline) < 0
  ).length;

  return (
    <AppLayout>
      <PageHeader
        title="Datenpannen"
        description="Art. 33/34 DSGVO – 72-Stunden-Meldepflicht bei Datenschutzverletzungen"
      />

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
        <Card>
          <CardContent className="pt-4 pb-3">
            <div className="text-2xl font-bold">{total}</div>
            <div className="text-xs text-muted-foreground mt-0.5">Gesamt</div>
          </CardContent>
        </Card>
        <Card className={overdue > 0 ? "border-red-300 dark:border-red-700" : ""}>
          <CardContent className="pt-4 pb-3">
            <div className={`text-2xl font-bold ${overdue > 0 ? "text-red-600" : ""}`}>{overdue}</div>
            <div className="text-xs text-muted-foreground mt-0.5">Frist überschritten</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 pb-3">
            <div className="text-2xl font-bold">
              {breaches.filter((b) => b.status === "discovered" || b.status === "assessed").length}
            </div>
            <div className="text-xs text-muted-foreground mt-0.5">Offen</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 pb-3">
            <div className="text-2xl font-bold">
              {breaches.filter((b) => b.status === "closed").length}
            </div>
            <div className="text-xs text-muted-foreground mt-0.5">Abgeschlossen</div>
          </CardContent>
        </Card>
      </div>

      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-48">
            <SelectValue placeholder="Status filtern" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Alle Status</SelectItem>
            {Object.entries(STATUS_LABELS).map(([v, l]) => (
              <SelectItem key={v} value={v}>{l}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <input
            type="checkbox"
            checked={overdueOnly}
            onChange={(e) => setOverdueOnly(e.target.checked)}
            className="rounded"
          />
          Nur überfällige
        </label>
        <div className="ml-auto">
          <Button onClick={() => setShowNew(true)}>
            <Plus className="size-4 mr-1" /> Datenpanne erfassen
          </Button>
        </div>
      </div>

      {/* List */}
      {loading ? (
        <div className="space-y-3">
          {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-20 w-full" />)}
        </div>
      ) : breaches.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            <ShieldAlert className="size-10 mx-auto mb-3 opacity-40" />
            <p>Keine Datenpannen gefunden.</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {breaches.map((b) => (
            <Card
              key={b.id}
              className="hover:shadow-md transition-shadow cursor-pointer"
              onClick={() => void openDetail(b)}
            >
              <CardContent className="py-4 px-5">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-medium text-sm truncate">{b.title}</span>
                      {b.riskLevel && (
                        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${RISK_COLORS[b.riskLevel] ?? ""}`}>
                          {RISK_LABELS[b.riskLevel]}
                        </span>
                      )}
                      <Badge variant="outline" className="text-xs">
                        {STATUS_LABELS[b.status] ?? b.status}
                      </Badge>
                    </div>
                    <div className="text-xs text-muted-foreground mt-1 flex flex-wrap gap-3">
                      <span>Art: {BREACH_TYPE_LABELS[b.breachType] ?? b.breachType}</span>
                      {b.department && <span>Abteilung: {b.department}</span>}
                      {b.affectedPersonsCount != null && <span>Betroffene: {b.affectedPersonsCount}</span>}
                      <span>Entdeckt: {new Date(b.discoveredAt).toLocaleDateString("de-DE")}</span>
                    </div>
                  </div>
                  <div className="shrink-0 text-right">
                    <DeadlineIndicator deadline={b.notificationDeadline} status={b.status} />
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* New breach dialog */}
      <Dialog open={showNew} onOpenChange={setShowNew}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Datenpanne erfassen</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div>
              <Label>Titel *</Label>
              <Input value={form.title} onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))} placeholder="Kurze Beschreibung der Verletzung" />
            </div>
            <div>
              <Label>Beschreibung</Label>
              <Textarea value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} rows={3} />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Entdeckt am *</Label>
                <Input type="datetime-local" value={form.discovered_at} onChange={(e) => setForm((f) => ({ ...f, discovered_at: e.target.value }))} />
              </div>
              <div>
                <Label>Art der Verletzung *</Label>
                <Select value={form.breach_type} onValueChange={(v) => setForm((f) => ({ ...f, breach_type: v as NewBreachForm["breach_type"] }))}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
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
                <Input value={form.affected_data_categories} onChange={(e) => setForm((f) => ({ ...f, affected_data_categories: e.target.value }))} placeholder="z.B. Name, E-Mail, Adresse" />
              </div>
              <div>
                <Label>Betroffene Personen (ca.)</Label>
                <Input type="number" value={form.affected_persons_count} onChange={(e) => setForm((f) => ({ ...f, affected_persons_count: e.target.value }))} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Abteilung</Label>
                <Input value={form.department} onChange={(e) => setForm((f) => ({ ...f, department: e.target.value }))} />
              </div>
              <div>
                <Label>Zuständig</Label>
                <Input value={form.assignee} onChange={(e) => setForm((f) => ({ ...f, assignee: e.target.value }))} />
              </div>
            </div>
            <div>
              <Label>Risikostufe</Label>
              <Select value={form.risk_level || "none"} onValueChange={(v) => setForm((f) => ({ ...f, risk_level: v === "none" ? "" : v }))}>
                <SelectTrigger><SelectValue placeholder="Risiko bewerten" /></SelectTrigger>
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
              <Textarea value={form.measures_taken} onChange={(e) => setForm((f) => ({ ...f, measures_taken: e.target.value }))} rows={2} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowNew(false)}>Abbrechen</Button>
            <Button onClick={() => void handleCreate()} disabled={creating}>
              {creating && <Loader2 className="size-4 mr-1 animate-spin" />}
              Erfassen
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Detail dialog */}
      {selected && (
        <Dialog open onOpenChange={() => setSelected(null)}>
          <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <ShieldAlert className="size-5 text-orange-500" />
                {selected.title}
              </DialogTitle>
            </DialogHeader>

            <div className="space-y-5">
              {/* Status + deadline */}
              <div className="flex flex-wrap gap-3 items-center">
                <Badge variant="outline">{STATUS_LABELS[selected.status] ?? selected.status}</Badge>
                {selected.riskLevel && (
                  <span className={`text-xs px-2 py-1 rounded-full font-medium ${RISK_COLORS[selected.riskLevel] ?? ""}`}>
                    Risiko: {RISK_LABELS[selected.riskLevel]}
                  </span>
                )}
                <DeadlineIndicator deadline={selected.notificationDeadline} status={selected.status} />
              </div>

              <div className="grid grid-cols-2 gap-4 text-sm">
                <div><span className="text-muted-foreground">Art:</span> {BREACH_TYPE_LABELS[selected.breachType]}</div>
                <div><span className="text-muted-foreground">Entdeckt:</span> {new Date(selected.discoveredAt).toLocaleString("de-DE")}</div>
                <div><span className="text-muted-foreground">Meldepflicht bis:</span> <span className="font-medium">{new Date(selected.notificationDeadline).toLocaleString("de-DE")}</span></div>
                {selected.department && <div><span className="text-muted-foreground">Abteilung:</span> {selected.department}</div>}
                {selected.affectedPersonsCount != null && <div><span className="text-muted-foreground">Betroffene:</span> {selected.affectedPersonsCount}</div>}
                {selected.affectedDataCategories.length > 0 && (
                  <div className="col-span-2"><span className="text-muted-foreground">Datenkategorien:</span> {selected.affectedDataCategories.join(", ")}</div>
                )}
              </div>

              {selected.description && (
                <div>
                  <p className="text-sm font-medium mb-1">Beschreibung</p>
                  <p className="text-sm text-muted-foreground whitespace-pre-wrap">{selected.description}</p>
                </div>
              )}

              {selected.measuresTaken && (
                <div>
                  <p className="text-sm font-medium mb-1">Ergriffene Maßnahmen</p>
                  <p className="text-sm text-muted-foreground whitespace-pre-wrap">{selected.measuresTaken}</p>
                </div>
              )}

              {/* Status actions */}
              <div>
                <p className="text-sm font-medium mb-2">Status ändern</p>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(STATUS_LABELS)
                    .filter(([v]) => v !== selected.status)
                    .map(([v, l]) => (
                      <Button
                        key={v}
                        size="sm"
                        variant="outline"
                        disabled={updatingStatus}
                        onClick={() => void handleStatusChange(v)}
                      >
                        {updatingStatus && <Loader2 className="size-3 mr-1 animate-spin" />}
                        {l}
                      </Button>
                    ))}
                </div>
              </div>

              <Separator />

              {/* Notification draft */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <p className="text-sm font-medium flex items-center gap-1">
                    <FileText className="size-4" /> Behörden-Meldungsentwurf
                  </p>
                  <Button size="sm" variant="outline" onClick={() => void handleGenerateDraft()} disabled={generatingDraft}>
                    {generatingDraft ? <Loader2 className="size-3 mr-1 animate-spin" /> : <Eye className="size-3 mr-1" />}
                    {selected.draftNotification ? "Neu generieren" : "Generieren"}
                  </Button>
                </div>
                {selected.draftNotification ? (
                  <pre className="text-xs bg-slate-50 dark:bg-slate-900 border rounded-md p-3 whitespace-pre-wrap max-h-64 overflow-y-auto">
                    {selected.draftNotification}
                  </pre>
                ) : (
                  <p className="text-xs text-muted-foreground italic">Noch kein Entwurf generiert.</p>
                )}
              </div>

              {/* Activity */}
              <Separator />
              <div>
                <p className="text-sm font-medium mb-2">Aktivitätsprotokoll</p>
                {loadingActivity ? (
                  <div className="space-y-1">{[...Array(3)].map((_, i) => <Skeleton key={i} className="h-6 w-full" />)}</div>
                ) : activity.length === 0 ? (
                  <p className="text-xs text-muted-foreground">Keine Aktivitäten.</p>
                ) : (
                  <div className="space-y-1 max-h-40 overflow-y-auto">
                    {activity.map((a) => (
                      <div key={a.id} className="flex items-center gap-3 text-xs">
                        <span className="text-muted-foreground shrink-0">{new Date(a.createdAt).toLocaleString("de-DE")}</span>
                        <span className="font-medium">{a.eventType}</span>
                        {Object.keys(a.payload).length > 0 && (
                          <span className="text-muted-foreground truncate">
                            {Object.entries(a.payload).map(([k, v]) => `${k}: ${v}`).join(", ")}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            <DialogFooter>
              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button variant="destructive" size="sm">
                    <Trash2 className="size-4 mr-1" /> Löschen
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>Datenpanne löschen?</AlertDialogTitle>
                    <AlertDialogDescription>
                      Diese Aktion kann nicht rückgängig gemacht werden.
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>Abbrechen</AlertDialogCancel>
                    <AlertDialogAction onClick={() => void handleDelete(selected.id)}>
                      Löschen
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
              <Button variant="outline" onClick={() => setSelected(null)}>Schließen</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </AppLayout>
  );
}
