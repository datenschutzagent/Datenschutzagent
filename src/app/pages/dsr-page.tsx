import { useState, useEffect, useCallback, useMemo } from "react";
import { AppLayout } from "../components/app-layout";
import { PageHeader } from "../components/page-header";
import { Card, CardContent } from "../components/ui/card";
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
  listDSRRequests,
  createDSRRequest,
  updateDSRRequest,
  deleteDSRRequest,
  generateDSRDraft,
  getDSRActivity,
  type ApiDSRRequest,
  type ApiDSRActivity,
  type DSRRequestCreate,
  type DSRRequestType,
  type DSRStatus,
} from "../lib/api";
import { toast } from "sonner";
import {
  AlertTriangle,
  Plus,
  Clock,
  CheckCircle,
  Loader2,
  FileText,
  Trash2,
  Eye,
  UserCheck,
} from "lucide-react";

const REQUEST_TYPE_LABELS: Record<string, string> = {
  access: "Auskunft (Art. 15)",
  rectification: "Berichtigung (Art. 16)",
  erasure: "Löschung (Art. 17)",
  restriction: "Einschränkung (Art. 18)",
  portability: "Datenübertragbarkeit (Art. 20)",
  objection: "Widerspruch (Art. 21)",
};

const STATUS_LABELS: Record<string, string> = {
  received: "Eingegangen",
  in_progress: "In Bearbeitung",
  response_sent: "Beantwortet",
  closed: "Abgeschlossen",
  denied: "Abgelehnt",
};

const STATUS_COLORS: Record<string, string> = {
  received: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300",
  in_progress: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300",
  response_sent: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
  closed: "bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-300",
  denied: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300",
};

function daysUntilDeadline(deadline: string): number {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const dl = new Date(deadline);
  dl.setHours(0, 0, 0, 0);
  return Math.ceil((dl.getTime() - today.getTime()) / 86_400_000);
}

function DeadlineIndicator({ deadline, status }: { deadline: string; status: string }) {
  const days = daysUntilDeadline(deadline);
  const done = ["response_sent", "closed", "denied"].includes(status);
  if (done) return <span className="text-xs text-green-600 dark:text-green-400 flex items-center gap-1"><CheckCircle className="size-3" /> Erledigt</span>;
  if (days < 0) return <span className="text-xs text-red-600 font-semibold flex items-center gap-1"><AlertTriangle className="size-3" /> {Math.abs(days)} Tage überfällig</span>;
  if (days <= 7) return <span className="text-xs text-red-500 font-semibold flex items-center gap-1"><Clock className="size-3" /> {days} Tage verbleibend</span>;
  if (days <= 14) return <span className="text-xs text-orange-500 flex items-center gap-1"><Clock className="size-3" /> {days} Tage verbleibend</span>;
  return <span className="text-xs text-slate-500 flex items-center gap-1"><Clock className="size-3" /> {days} Tage verbleibend</span>;
}

interface NewDSRForm {
  request_type: DSRRequestType;
  requestor_name: string;
  requestor_email: string;
  description: string;
  department: string;
  assignee: string;
  received_at: string;
  deadline_extension_days: string;
}

const defaultForm: NewDSRForm = {
  request_type: "access",
  requestor_name: "",
  requestor_email: "",
  description: "",
  department: "",
  assignee: "",
  received_at: new Date().toISOString().slice(0, 10),
  deadline_extension_days: "0",
};

export function DSRPage() {
  const [requests, setRequests] = useState<ApiDSRRequest[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");
  const [overdueOnly, setOverdueOnly] = useState(false);

  const [showNew, setShowNew] = useState(false);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState<NewDSRForm>(defaultForm);

  const [selected, setSelected] = useState<ApiDSRRequest | null>(null);
  const [activity, setActivity] = useState<ApiDSRActivity[]>([]);
  const [loadingActivity, setLoadingActivity] = useState(false);
  const [generatingDraft, setGeneratingDraft] = useState(false);
  const [updatingStatus, setUpdatingStatus] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await listDSRRequests({
        status: statusFilter !== "all" ? statusFilter : undefined,
        requestType: typeFilter !== "all" ? typeFilter : undefined,
        overdueOnly,
      });
      setRequests(r.items);
      setTotal(r.total);
    } catch {
      toast.error("Anfragen konnten nicht geladen werden.");
    } finally {
      setLoading(false);
    }
  }, [statusFilter, typeFilter, overdueOnly]);

  useEffect(() => { void load(); }, [load]);

  async function openDetail(r: ApiDSRRequest) {
    setSelected(r);
    setLoadingActivity(true);
    try {
      const acts = await getDSRActivity(r.id);
      setActivity(acts);
    } finally {
      setLoadingActivity(false);
    }
  }

  async function handleCreate() {
    setCreating(true);
    try {
      const body: DSRRequestCreate = {
        request_type: form.request_type,
        requestor_name: form.requestor_name.trim() || undefined,
        requestor_email: form.requestor_email.trim() || undefined,
        description: form.description.trim() || undefined,
        department: form.department.trim() || undefined,
        assignee: form.assignee.trim() || undefined,
        received_at: form.received_at,
        deadline_extension_days: Number(form.deadline_extension_days) || 0,
      };
      await createDSRRequest(body);
      toast.success("Anfrage erfasst.");
      setShowNew(false);
      setForm(defaultForm);
      void load();
    } catch {
      toast.error("Fehler beim Erfassen der Anfrage.");
    } finally {
      setCreating(false);
    }
  }

  async function handleGenerateDraft() {
    if (!selected) return;
    setGeneratingDraft(true);
    try {
      const updated = await generateDSRDraft(selected.id);
      setSelected(updated);
      toast.success("Antwortentwurf generiert.");
    } catch {
      toast.error("Fehler beim Generieren des Entwurfs.");
    } finally {
      setGeneratingDraft(false);
    }
  }

  async function handleStatusChange(newStatus: DSRStatus) {
    if (!selected) return;
    setUpdatingStatus(true);
    try {
      const updated = await updateDSRRequest(selected.id, { status: newStatus });
      setSelected(updated);
      setRequests((prev) => prev.map((r) => r.id === updated.id ? updated : r));
      toast.success("Status aktualisiert.");
    } catch {
      toast.error("Fehler beim Aktualisieren.");
    } finally {
      setUpdatingStatus(false);
    }
  }

  async function handleDelete(id: string) {
    try {
      await deleteDSRRequest(id);
      setRequests((prev) => prev.filter((r) => r.id !== id));
      setTotal((t) => t - 1);
      if (selected?.id === id) setSelected(null);
      toast.success("Anfrage gelöscht.");
    } catch {
      toast.error("Fehler beim Löschen.");
    }
  }

  const overdue = requests.filter(
    (r) => !["response_sent", "closed", "denied"].includes(r.status)
      && daysUntilDeadline(r.responseDeadline) < 0
  ).length;

  const dsrAnalytics = useMemo(() => {
    const responded = requests.filter((r) => r.respondedAt != null);
    const responseTimes = responded.map((r) =>
      (new Date(r.respondedAt!).getTime() - new Date(r.receivedAt).getTime()) / 86_400_000
    );
    const avgDays = responseTimes.length > 0
      ? Math.round(responseTimes.reduce((a, b) => a + b, 0) / responseTimes.length)
      : null;

    const onTime = responded.filter(
      (r) => new Date(r.respondedAt!).getTime() <= new Date(r.responseDeadline).getTime()
    ).length;
    const onTimeRate = responded.length > 0 ? Math.round((onTime / responded.length) * 100) : null;

    const byType: Record<string, number> = {};
    for (const r of requests) {
      byType[r.requestType] = (byType[r.requestType] ?? 0) + 1;
    }

    return { avgDays, onTimeRate, byType, respondedCount: responded.length };
  }, [requests]);

  return (
    <AppLayout>
      <PageHeader
        title="Betroffenenrechte"
        description="Art. 15–22 DSGVO – Anfragen betroffener Personen verwalten"
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
              {requests.filter((r) => r.status === "received" || r.status === "in_progress").length}
            </div>
            <div className="text-xs text-muted-foreground mt-0.5">Offen</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 pb-3">
            <div className="text-2xl font-bold">
              {requests.filter((r) => r.status === "closed" || r.status === "response_sent").length}
            </div>
            <div className="text-xs text-muted-foreground mt-0.5">Abgeschlossen</div>
          </CardContent>
        </Card>
      </div>

      {/* Analytics row */}
      {requests.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
          <Card>
            <CardContent className="pt-4 pb-3 px-4">
              <div className="text-xs text-muted-foreground mb-1">On-Time-Rate (Art. 12 Abs. 3)</div>
              {dsrAnalytics.onTimeRate == null ? (
                <div className="text-sm text-muted-foreground">Noch keine Antworten</div>
              ) : (
                <>
                  <div className={`text-2xl font-bold ${dsrAnalytics.onTimeRate >= 90 ? "text-green-600" : dsrAnalytics.onTimeRate >= 70 ? "text-yellow-600" : "text-red-600"}`}>
                    {dsrAnalytics.onTimeRate}%
                  </div>
                  <div className="text-xs text-muted-foreground mt-0.5">
                    {dsrAnalytics.respondedCount} Anfragen beantwortet
                  </div>
                </>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-4 pb-3 px-4">
              <div className="text-xs text-muted-foreground mb-1">Ø Antwortzeit</div>
              {dsrAnalytics.avgDays == null ? (
                <div className="text-sm text-muted-foreground">Keine Daten</div>
              ) : (
                <>
                  <div className={`text-2xl font-bold ${dsrAnalytics.avgDays <= 30 ? "text-green-600" : "text-red-600"}`}>
                    {dsrAnalytics.avgDays}d
                  </div>
                  <div className="text-xs text-muted-foreground mt-0.5">Frist: 30 Tage</div>
                </>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-4 pb-3 px-4">
              <div className="text-xs text-muted-foreground mb-1">Anfragetypen</div>
              <div className="space-y-1.5 mt-1">
                {Object.entries(REQUEST_TYPE_LABELS).map(([key, label]) => {
                  const count = dsrAnalytics.byType[key] ?? 0;
                  if (count === 0) return null;
                  const pct = total > 0 ? Math.round((count / total) * 100) : 0;
                  return (
                    <div key={key} className="flex items-center gap-2 text-xs">
                      <span className="w-20 text-muted-foreground truncate" title={label}>{label.split(" ")[0]}</span>
                      <div className="flex-1 bg-muted rounded-full h-1.5">
                        <div className="bg-primary h-1.5 rounded-full" style={{ width: `${pct}%` }} />
                      </div>
                      <span className="w-4 text-right font-medium">{count}</span>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </div>
      )}

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
        <Select value={typeFilter} onValueChange={setTypeFilter}>
          <SelectTrigger className="w-56">
            <SelectValue placeholder="Typ filtern" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Alle Typen</SelectItem>
            {Object.entries(REQUEST_TYPE_LABELS).map(([v, l]) => (
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
            <Plus className="size-4 mr-1" /> Anfrage erfassen
          </Button>
        </div>
      </div>

      {/* List */}
      {loading ? (
        <div className="space-y-3">
          {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-20 w-full" />)}
        </div>
      ) : requests.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            <UserCheck className="size-10 mx-auto mb-3 opacity-40" />
            <p>Keine Betroffenenrechts-Anfragen gefunden.</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {requests.map((r) => (
            <Card
              key={r.id}
              className="hover:shadow-md transition-shadow cursor-pointer"
              onClick={() => void openDetail(r)}
            >
              <CardContent className="py-4 px-5">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-medium text-sm truncate">
                        {r.requestorName || "Anonyme Anfrage"}
                      </span>
                      <Badge variant="outline" className="text-xs">
                        {REQUEST_TYPE_LABELS[r.requestType] ?? r.requestType}
                      </Badge>
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_COLORS[r.status] ?? ""}`}>
                        {STATUS_LABELS[r.status] ?? r.status}
                      </span>
                    </div>
                    <div className="text-xs text-muted-foreground mt-1 flex flex-wrap gap-3">
                      {r.department && <span>Abteilung: {r.department}</span>}
                      {r.assignee && <span>Zuständig: {r.assignee}</span>}
                      <span>Eingegangen: {new Date(r.receivedAt).toLocaleDateString("de-DE")}</span>
                      <span>Frist: {new Date(r.responseDeadline).toLocaleDateString("de-DE")}</span>
                    </div>
                  </div>
                  <div className="shrink-0 text-right">
                    <DeadlineIndicator deadline={r.responseDeadline} status={r.status} />
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* New request dialog */}
      <Dialog open={showNew} onOpenChange={setShowNew}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Betroffenenrechts-Anfrage erfassen</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div>
              <Label>Art der Anfrage *</Label>
              <Select value={form.request_type} onValueChange={(v) => setForm((f) => ({ ...f, request_type: v as DSRRequestType }))}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {Object.entries(REQUEST_TYPE_LABELS).map(([v, l]) => (
                    <SelectItem key={v} value={v}>{l}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Name der betroffenen Person</Label>
                <Input value={form.requestor_name} onChange={(e) => setForm((f) => ({ ...f, requestor_name: e.target.value }))} placeholder="Max Mustermann" />
              </div>
              <div>
                <Label>E-Mail</Label>
                <Input type="email" value={form.requestor_email} onChange={(e) => setForm((f) => ({ ...f, requestor_email: e.target.value }))} placeholder="max@beispiel.de" />
              </div>
            </div>
            <div>
              <Label>Beschreibung</Label>
              <Textarea value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} rows={3} placeholder="Details zur Anfrage..." />
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
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Eingegangen am *</Label>
                <Input type="date" value={form.received_at} onChange={(e) => setForm((f) => ({ ...f, received_at: e.target.value }))} />
              </div>
              <div>
                <Label>Fristverlängerung (Tage)</Label>
                <Input
                  type="number"
                  min={0}
                  max={60}
                  value={form.deadline_extension_days}
                  onChange={(e) => setForm((f) => ({ ...f, deadline_extension_days: e.target.value }))}
                />
                <p className="text-xs text-muted-foreground mt-1">Art. 12 Abs. 3: Verlängerung um bis zu 2 Monate</p>
              </div>
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
                <UserCheck className="size-5 text-blue-500" />
                {REQUEST_TYPE_LABELS[selected.requestType]} – {selected.requestorName || "Anonyme Anfrage"}
              </DialogTitle>
            </DialogHeader>

            <div className="space-y-5">
              {/* Status + deadline */}
              <div className="flex flex-wrap gap-3 items-center">
                <span className={`text-xs px-2 py-1 rounded-full font-medium ${STATUS_COLORS[selected.status] ?? ""}`}>
                  {STATUS_LABELS[selected.status] ?? selected.status}
                </span>
                <DeadlineIndicator deadline={selected.responseDeadline} status={selected.status} />
              </div>

              <div className="grid grid-cols-2 gap-4 text-sm">
                <div><span className="text-muted-foreground">Art:</span> {REQUEST_TYPE_LABELS[selected.requestType]}</div>
                <div><span className="text-muted-foreground">Eingegangen:</span> {new Date(selected.receivedAt).toLocaleDateString("de-DE")}</div>
                <div><span className="text-muted-foreground">Antwortfrist:</span> <span className="font-medium">{new Date(selected.responseDeadline).toLocaleDateString("de-DE")}</span></div>
                {selected.department && <div><span className="text-muted-foreground">Abteilung:</span> {selected.department}</div>}
                {selected.assignee && <div><span className="text-muted-foreground">Zuständig:</span> {selected.assignee}</div>}
                {selected.requestorEmail && <div><span className="text-muted-foreground">E-Mail:</span> {selected.requestorEmail}</div>}
                {selected.respondedAt && <div><span className="text-muted-foreground">Beantwortet am:</span> {new Date(selected.respondedAt).toLocaleDateString("de-DE")}</div>}
              </div>

              {selected.description && (
                <div>
                  <p className="text-sm font-medium mb-1">Beschreibung</p>
                  <p className="text-sm text-muted-foreground whitespace-pre-wrap">{selected.description}</p>
                </div>
              )}

              {selected.responseSummary && (
                <div>
                  <p className="text-sm font-medium mb-1">Antwort-Zusammenfassung</p>
                  <p className="text-sm text-muted-foreground whitespace-pre-wrap">{selected.responseSummary}</p>
                </div>
              )}

              {/* Status actions */}
              <div>
                <p className="text-sm font-medium mb-2">Status ändern</p>
                <div className="flex flex-wrap gap-2">
                  {(Object.entries(STATUS_LABELS) as [DSRStatus, string][])
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

              {/* Response draft */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <p className="text-sm font-medium flex items-center gap-1">
                    <FileText className="size-4" /> Antwortentwurf
                  </p>
                  <Button size="sm" variant="outline" onClick={() => void handleGenerateDraft()} disabled={generatingDraft}>
                    {generatingDraft ? <Loader2 className="size-3 mr-1 animate-spin" /> : <Eye className="size-3 mr-1" />}
                    {selected.draftResponse ? "Neu generieren" : "Generieren"}
                  </Button>
                </div>
                {selected.draftResponse ? (
                  <pre className="text-xs bg-slate-50 dark:bg-slate-900 border rounded-md p-3 whitespace-pre-wrap max-h-64 overflow-y-auto">
                    {selected.draftResponse}
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
                    <AlertDialogTitle>Anfrage löschen?</AlertDialogTitle>
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
