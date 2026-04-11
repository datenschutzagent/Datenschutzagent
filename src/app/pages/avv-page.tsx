import { useState, useEffect, useCallback } from "react";
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
import {
  listAVVContracts,
  createAVVContract,
  updateAVVContract,
  deleteAVVContract,
  assessAvvRisk,
  type ApiAVVContract,
  type AVVCreate,
  type AVVUpdate,
  type AvvRiskAssessment,
} from "../lib/api";
import { toast } from "sonner";
import { Plus, FileText, Loader2, Trash2, AlertTriangle, Clock, ShieldAlert } from "lucide-react";

const STATUS_LABELS: Record<string, string> = {
  pending: "Ausstehend",
  under_review: "In Prüfung",
  signed: "Unterzeichnet",
  expired: "Abgelaufen",
  terminated: "Gekündigt",
};

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300",
  under_review: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300",
  signed: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
  expired: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300",
  terminated: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400",
};

const PARTNER_TYPE_LABELS: Record<string, string> = {
  processor: "Auftragsverarbeiter",
  sub_processor: "Unter-Auftragsverarbeiter",
};

function daysUntilExpiry(date: string): number {
  return Math.ceil((new Date(date).getTime() - Date.now()) / 86_400_000);
}

function ExpiryBadge({ expiryDate, status }: { expiryDate: string | null; status: string }) {
  if (!expiryDate || status !== "signed") return null;
  const days = daysUntilExpiry(expiryDate);
  if (days < 0)
    return <span className="text-xs text-red-600 flex items-center gap-1"><AlertTriangle className="size-3" /> Abgelaufen</span>;
  if (days <= 90)
    return <span className="text-xs text-orange-500 flex items-center gap-1"><Clock className="size-3" /> {days}T bis Ablauf</span>;
  return <span className="text-xs text-muted-foreground">{new Date(expiryDate).toLocaleDateString("de-DE")}</span>;
}

interface NewAVVForm {
  partner_name: string;
  partner_type: "processor" | "sub_processor";
  subject_matter: string;
  department: string;
  assignee: string;
  contract_date: string;
  expiry_date: string;
  notes: string;
}

const defaultForm: NewAVVForm = {
  partner_name: "",
  partner_type: "processor",
  subject_matter: "",
  department: "",
  assignee: "",
  contract_date: "",
  expiry_date: "",
  notes: "",
};

export function AVVPage() {
  const [contracts, setContracts] = useState<ApiAVVContract[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("all");
  const [expiringSoon, setExpiringSoon] = useState(false);

  const [showNew, setShowNew] = useState(false);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState<NewAVVForm>(defaultForm);

  const [selected, setSelected] = useState<ApiAVVContract | null>(null);
  const [updatingStatus, setUpdatingStatus] = useState(false);
  const [riskAssessment, setRiskAssessment] = useState<AvvRiskAssessment | null>(null);
  const [assessingRisk, setAssessingRisk] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await listAVVContracts({
        status: statusFilter !== "all" ? statusFilter : undefined,
        expiringSoon,
      });
      setContracts(r.items);
      setTotal(r.total);
    } catch {
      toast.error("AVV konnten nicht geladen werden.");
    } finally {
      setLoading(false);
    }
  }, [statusFilter, expiringSoon]);

  useEffect(() => { void load(); }, [load]);

  async function handleCreate() {
    if (!form.partner_name.trim()) { toast.error("Partnername ist erforderlich."); return; }
    setCreating(true);
    try {
      const body: AVVCreate = {
        partner_name: form.partner_name.trim(),
        partner_type: form.partner_type,
        subject_matter: form.subject_matter.trim() || undefined,
        department: form.department.trim() || undefined,
        assignee: form.assignee.trim(),
        contract_date: form.contract_date || undefined,
        expiry_date: form.expiry_date || undefined,
        notes: form.notes.trim() || undefined,
      };
      await createAVVContract(body);
      toast.success("AVV angelegt.");
      setShowNew(false);
      setForm(defaultForm);
      void load();
    } catch {
      toast.error("Fehler beim Anlegen.");
    } finally {
      setCreating(false);
    }
  }

  async function handleStatusChange(newStatus: string) {
    if (!selected) return;
    setUpdatingStatus(true);
    try {
      const body: AVVUpdate = { status: newStatus };
      const updated = await updateAVVContract(selected.id, body);
      setSelected(updated);
      setContracts((prev) => prev.map((c) => c.id === updated.id ? updated : c));
      toast.success("Status aktualisiert.");
    } catch {
      toast.error("Fehler beim Aktualisieren.");
    } finally {
      setUpdatingStatus(false);
    }
  }

  async function handleRiskAssessment() {
    if (!selected) return;
    setAssessingRisk(true);
    setRiskAssessment(null);
    try {
      const result = await assessAvvRisk(selected.id);
      setRiskAssessment(result);
      toast.success("Risikobewertung abgeschlossen.");
    } catch (err) {
      toast.error(`Risikobewertung fehlgeschlagen: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setAssessingRisk(false);
    }
  }

  async function handleDelete(id: string) {
    try {
      await deleteAVVContract(id);
      setContracts((prev) => prev.filter((c) => c.id !== id));
      setTotal((t) => t - 1);
      if (selected?.id === id) setSelected(null);
      toast.success("AVV gelöscht.");
    } catch {
      toast.error("Fehler beim Löschen.");
    }
  }

  const expiredCount = contracts.filter((c) => c.status === "expired").length;
  const pendingCount = contracts.filter((c) => c.status === "pending" || c.status === "under_review").length;

  return (
    <AppLayout>
      <PageHeader
        title="AVV-Verwaltung"
        description="Art. 28 DSGVO – Auftragsverarbeitungsverträge verwalten"
      />

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
        <Card><CardContent className="pt-4 pb-3">
          <div className="text-2xl font-bold">{total}</div>
          <div className="text-xs text-muted-foreground mt-0.5">Gesamt</div>
        </CardContent></Card>
        <Card><CardContent className="pt-4 pb-3">
          <div className="text-2xl font-bold text-green-600">{contracts.filter((c) => c.status === "signed").length}</div>
          <div className="text-xs text-muted-foreground mt-0.5">Unterzeichnet</div>
        </CardContent></Card>
        <Card className={pendingCount > 0 ? "border-yellow-300" : ""}><CardContent className="pt-4 pb-3">
          <div className={`text-2xl font-bold ${pendingCount > 0 ? "text-yellow-600" : ""}`}>{pendingCount}</div>
          <div className="text-xs text-muted-foreground mt-0.5">In Bearbeitung</div>
        </CardContent></Card>
        <Card className={expiredCount > 0 ? "border-red-300" : ""}><CardContent className="pt-4 pb-3">
          <div className={`text-2xl font-bold ${expiredCount > 0 ? "text-red-600" : ""}`}>{expiredCount}</div>
          <div className="text-xs text-muted-foreground mt-0.5">Abgelaufen</div>
        </CardContent></Card>
      </div>

      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-44">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Alle Status</SelectItem>
            {Object.entries(STATUS_LABELS).map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}
          </SelectContent>
        </Select>
        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <input type="checkbox" checked={expiringSoon} onChange={(e) => setExpiringSoon(e.target.checked)} className="rounded" />
          Bald ablaufend (90 Tage)
        </label>
        <div className="ml-auto">
          <Button onClick={() => setShowNew(true)}><Plus className="size-4 mr-1" /> AVV anlegen</Button>
        </div>
      </div>

      {loading ? (
        <div className="space-y-3">{[...Array(5)].map((_, i) => <Skeleton key={i} className="h-16 w-full" />)}</div>
      ) : contracts.length === 0 ? (
        <Card><CardContent className="py-12 text-center text-muted-foreground">
          <FileText className="size-10 mx-auto mb-3 opacity-40" />
          <p>Keine AVV gefunden.</p>
        </CardContent></Card>
      ) : (
        <div className="space-y-2">
          {contracts.map((c) => (
            <Card key={c.id} className="hover:shadow-md transition-shadow cursor-pointer" onClick={() => setSelected(c)}>
              <CardContent className="py-3 px-5">
                <div className="flex items-center justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-medium text-sm">{c.partnerName}</span>
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_COLORS[c.status] ?? ""}`}>
                        {STATUS_LABELS[c.status] ?? c.status}
                      </span>
                      <span className="text-xs text-muted-foreground">{PARTNER_TYPE_LABELS[c.partnerType]}</span>
                    </div>
                    {c.department && <div className="text-xs text-muted-foreground mt-0.5">Abteilung: {c.department}</div>}
                  </div>
                  <ExpiryBadge expiryDate={c.expiryDate} status={c.status} />
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* New dialog */}
      <Dialog open={showNew} onOpenChange={setShowNew}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
          <DialogHeader><DialogTitle>AVV anlegen</DialogTitle></DialogHeader>
          <div className="space-y-4 py-2">
            <div>
              <Label>Partnername *</Label>
              <Input value={form.partner_name} onChange={(e) => setForm((f) => ({ ...f, partner_name: e.target.value }))} placeholder="Unternehmen / Dienstleister" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>Typ</Label>
                <Select value={form.partner_type} onValueChange={(v) => setForm((f) => ({ ...f, partner_type: v as NewAVVForm["partner_type"] }))}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="processor">Auftragsverarbeiter</SelectItem>
                    <SelectItem value="sub_processor">Unter-Auftragsverarbeiter</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>Abteilung</Label>
                <Input value={form.department} onChange={(e) => setForm((f) => ({ ...f, department: e.target.value }))} />
              </div>
            </div>
            <div>
              <Label>Vertragsgegenstand</Label>
              <Textarea value={form.subject_matter} onChange={(e) => setForm((f) => ({ ...f, subject_matter: e.target.value }))} rows={2} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>Vertragsdatum</Label>
                <Input type="date" value={form.contract_date} onChange={(e) => setForm((f) => ({ ...f, contract_date: e.target.value }))} />
              </div>
              <div>
                <Label>Ablaufdatum</Label>
                <Input type="date" value={form.expiry_date} onChange={(e) => setForm((f) => ({ ...f, expiry_date: e.target.value }))} />
              </div>
            </div>
            <div>
              <Label>Zuständig</Label>
              <Input value={form.assignee} onChange={(e) => setForm((f) => ({ ...f, assignee: e.target.value }))} />
            </div>
            <div>
              <Label>Notizen</Label>
              <Textarea value={form.notes} onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))} rows={2} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowNew(false)}>Abbrechen</Button>
            <Button onClick={() => void handleCreate()} disabled={creating}>
              {creating && <Loader2 className="size-4 mr-1 animate-spin" />}
              Anlegen
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Detail dialog */}
      {selected && (
        <Dialog open onOpenChange={() => setSelected(null)}>
          <DialogContent className="max-w-lg">
            <DialogHeader><DialogTitle>{selected.partnerName}</DialogTitle></DialogHeader>
            <div className="space-y-4">
              <div className="flex gap-2 flex-wrap">
                <span className={`text-xs px-2 py-1 rounded-full font-medium ${STATUS_COLORS[selected.status] ?? ""}`}>
                  {STATUS_LABELS[selected.status]}
                </span>
                <span className="text-xs px-2 py-1 rounded-full bg-slate-100 dark:bg-slate-800">
                  {PARTNER_TYPE_LABELS[selected.partnerType]}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-3 text-sm">
                {selected.department && <div><span className="text-muted-foreground">Abteilung:</span> {selected.department}</div>}
                {selected.contractDate && <div><span className="text-muted-foreground">Vertrag:</span> {new Date(selected.contractDate).toLocaleDateString("de-DE")}</div>}
                {selected.expiryDate && <div><span className="text-muted-foreground">Ablauf:</span> {new Date(selected.expiryDate).toLocaleDateString("de-DE")}</div>}
                {selected.assignee && <div><span className="text-muted-foreground">Zuständig:</span> {selected.assignee}</div>}
              </div>
              {selected.subjectMatter && <div>
                <p className="text-sm font-medium mb-1">Vertragsgegenstand</p>
                <p className="text-sm text-muted-foreground">{selected.subjectMatter}</p>
              </div>}
              {selected.notes && <div>
                <p className="text-sm font-medium mb-1">Notizen</p>
                <p className="text-sm text-muted-foreground">{selected.notes}</p>
              </div>}
              <div>
                <p className="text-sm font-medium mb-2">Status ändern</p>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(STATUS_LABELS).filter(([v]) => v !== selected.status).map(([v, l]) => (
                    <Button key={v} size="sm" variant="outline" disabled={updatingStatus} onClick={() => void handleStatusChange(v)}>
                      {updatingStatus && <Loader2 className="size-3 mr-1 animate-spin" />}
                      {l}
                    </Button>
                  ))}
                </div>
              </div>
            </div>
            <DialogFooter>
              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button variant="destructive" size="sm"><Trash2 className="size-4 mr-1" /> Löschen</Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>AVV löschen?</AlertDialogTitle>
                    <AlertDialogDescription>Diese Aktion kann nicht rückgängig gemacht werden.</AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>Abbrechen</AlertDialogCancel>
                    <AlertDialogAction onClick={() => void handleDelete(selected.id)}>Löschen</AlertDialogAction>
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
