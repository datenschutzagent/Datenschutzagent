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
import { Progress } from "../components/ui/progress";
import {
  listTOMs,
  getTOMStats,
  createTOM,
  updateTOM,
  deleteTOM,
  type ApiTOM,
  type ApiTOMStats,
  type TOMCreate,
  type TOMCategory,
  type TOMStatus,
} from "../lib/api";
import { toast } from "sonner";
import { Plus, Shield, Loader2, Trash2, CheckCircle, Clock, XCircle } from "lucide-react";

const CATEGORY_LABELS: Record<string, string> = {
  access_control: "Zugriffskontrolle",
  encryption: "Verschlüsselung",
  pseudonymization: "Pseudonymisierung",
  availability: "Verfügbarkeit",
  integrity: "Integrität",
  confidentiality: "Vertraulichkeit",
  resilience: "Belastbarkeit",
  testing: "Prüfverfahren",
  incident_response: "Vorfallreaktion",
  other: "Sonstiges",
};

const STATUS_LABELS: Record<string, string> = {
  planned: "Geplant",
  in_progress: "In Umsetzung",
  implemented: "Umgesetzt",
  not_applicable: "Nicht relevant",
};

const STATUS_COLORS: Record<string, string> = {
  planned: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300",
  in_progress: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300",
  implemented: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
  not_applicable: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400",
};

function StatusIcon({ status }: { status: string }) {
  switch (status) {
    case "implemented": return <CheckCircle className="size-4 text-green-500" />;
    case "in_progress": return <Clock className="size-4 text-blue-500" />;
    case "not_applicable": return <XCircle className="size-4 text-slate-400" />;
    default: return <Clock className="size-4 text-yellow-500" />;
  }
}

const ALL_CATEGORIES = Object.keys(CATEGORY_LABELS) as TOMCategory[];

interface NewTOMForm {
  title: string;
  description: string;
  category: TOMCategory;
  implementation_status: TOMStatus;
  responsible: string;
  review_date: string;
  evidence: string;
}

const defaultForm: NewTOMForm = {
  title: "",
  description: "",
  category: "access_control",
  implementation_status: "planned",
  responsible: "",
  review_date: "",
  evidence: "",
};

export function TOMPage() {
  const [toms, setToms] = useState<ApiTOM[]>([]);
  const [stats, setStats] = useState<ApiTOMStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");

  const [showNew, setShowNew] = useState(false);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState<NewTOMForm>(defaultForm);

  const [selected, setSelected] = useState<ApiTOM | null>(null);
  const [updatingStatus, setUpdatingStatus] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [r, s] = await Promise.all([
        listTOMs({
          category: categoryFilter !== "all" ? categoryFilter : undefined,
          implementationStatus: statusFilter !== "all" ? statusFilter : undefined,
        }),
        getTOMStats(),
      ]);
      setToms(r.items);
      setStats(s);
    } catch {
      toast.error("TOMs konnten nicht geladen werden.");
    } finally {
      setLoading(false);
    }
  }, [categoryFilter, statusFilter]);

  useEffect(() => { void load(); }, [load]);

  async function handleCreate() {
    if (!form.title.trim()) { toast.error("Titel erforderlich."); return; }
    setCreating(true);
    try {
      const body: TOMCreate = {
        title: form.title.trim(),
        description: form.description.trim() || undefined,
        category: form.category,
        implementation_status: form.implementation_status,
        responsible: form.responsible.trim(),
        review_date: form.review_date || undefined,
        evidence: form.evidence.trim() || undefined,
      };
      await createTOM(body);
      toast.success("TOM angelegt.");
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
      const updated = await updateTOM(selected.id, { implementation_status: newStatus as TOMStatus });
      setSelected(updated);
      setToms((prev) => prev.map((t) => t.id === updated.id ? updated : t));
      toast.success("Status aktualisiert.");
    } catch {
      toast.error("Fehler beim Aktualisieren.");
    } finally {
      setUpdatingStatus(false);
    }
  }

  async function handleDelete(id: string) {
    try {
      await deleteTOM(id);
      setToms((prev) => prev.filter((t) => t.id !== id));
      if (selected?.id === id) setSelected(null);
      toast.success("TOM gelöscht.");
      void load();
    } catch {
      toast.error("Fehler beim Löschen.");
    }
  }

  // Group TOMs by category
  const grouped = ALL_CATEGORIES.reduce((acc, cat) => {
    const items = toms.filter((t) => t.category === cat);
    if (items.length > 0 || categoryFilter === cat) acc[cat] = items;
    return acc;
  }, {} as Record<string, ApiTOM[]>);

  return (
    <AppLayout>
      <PageHeader
        title="TOM-Katalog"
        description="Art. 32 DSGVO – Technisch-Organisatorische Maßnahmen"
      />

      {/* Implementation progress */}
      {stats && (
        <Card className="mb-6">
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Implementierungsstand</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-4 mb-3">
              <Progress value={stats.implementationRate} className="flex-1 h-3" />
              <span className="text-sm font-semibold shrink-0">{stats.implementationRate}%</span>
            </div>
            <div className="flex flex-wrap gap-4 text-sm">
              {Object.entries(STATUS_LABELS).map(([v, l]) => (
                <span key={v} className="flex items-center gap-1.5">
                  <StatusIcon status={v} />
                  <span className="text-muted-foreground">{l}:</span>
                  <span className="font-medium">{stats.byStatus[v] ?? 0}</span>
                </span>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <Select value={categoryFilter} onValueChange={setCategoryFilter}>
          <SelectTrigger className="w-48">
            <SelectValue placeholder="Kategorie" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Alle Kategorien</SelectItem>
            {Object.entries(CATEGORY_LABELS).map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-44">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Alle Status</SelectItem>
            {Object.entries(STATUS_LABELS).map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}
          </SelectContent>
        </Select>
        <div className="ml-auto">
          <Button onClick={() => setShowNew(true)}><Plus className="size-4 mr-1" /> TOM anlegen</Button>
        </div>
      </div>

      {loading ? (
        <div className="space-y-3">{[...Array(6)].map((_, i) => <Skeleton key={i} className="h-16 w-full" />)}</div>
      ) : toms.length === 0 ? (
        <Card><CardContent className="py-12 text-center text-muted-foreground">
          <Shield className="size-10 mx-auto mb-3 opacity-40" />
          <p>Keine TOMs gefunden.</p>
        </CardContent></Card>
      ) : (
        <div className="space-y-6">
          {Object.entries(grouped).map(([cat, items]) => (
            <div key={cat}>
              <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-2">
                {CATEGORY_LABELS[cat]} ({items.length})
              </h3>
              <div className="space-y-2">
                {items.map((tom) => (
                  <Card key={tom.id} className="hover:shadow-md transition-shadow cursor-pointer" onClick={() => setSelected(tom)}>
                    <CardContent className="py-3 px-5">
                      <div className="flex items-center justify-between gap-4">
                        <div className="flex items-center gap-3 min-w-0">
                          <StatusIcon status={tom.implementationStatus} />
                          <div className="min-w-0">
                            <span className="font-medium text-sm truncate block">{tom.title}</span>
                            {tom.responsible && <span className="text-xs text-muted-foreground">Zuständig: {tom.responsible}</span>}
                          </div>
                        </div>
                        <span className={`text-xs px-2 py-0.5 rounded-full font-medium shrink-0 ${STATUS_COLORS[tom.implementationStatus] ?? ""}`}>
                          {STATUS_LABELS[tom.implementationStatus]}
                        </span>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* New TOM dialog */}
      <Dialog open={showNew} onOpenChange={setShowNew}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
          <DialogHeader><DialogTitle>TOM anlegen</DialogTitle></DialogHeader>
          <div className="space-y-4 py-2">
            <div>
              <Label>Titel *</Label>
              <Input value={form.title} onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))} placeholder="Bezeichnung der Maßnahme" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>Kategorie *</Label>
                <Select value={form.category} onValueChange={(v) => setForm((f) => ({ ...f, category: v as TOMCategory }))}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {Object.entries(CATEGORY_LABELS).map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>Status</Label>
                <Select value={form.implementation_status} onValueChange={(v) => setForm((f) => ({ ...f, implementation_status: v as TOMStatus }))}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {Object.entries(STATUS_LABELS).map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div>
              <Label>Beschreibung</Label>
              <Textarea value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} rows={3} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>Zuständig</Label>
                <Input value={form.responsible} onChange={(e) => setForm((f) => ({ ...f, responsible: e.target.value }))} />
              </div>
              <div>
                <Label>Überprüfungsdatum</Label>
                <Input type="date" value={form.review_date} onChange={(e) => setForm((f) => ({ ...f, review_date: e.target.value }))} />
              </div>
            </div>
            <div>
              <Label>Nachweise / Belege</Label>
              <Textarea value={form.evidence} onChange={(e) => setForm((f) => ({ ...f, evidence: e.target.value }))} rows={2} placeholder="Dokumentation, Zertifikate, etc." />
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
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <StatusIcon status={selected.implementationStatus} />
                {selected.title}
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div className="flex gap-2">
                <span className={`text-xs px-2 py-1 rounded-full font-medium ${STATUS_COLORS[selected.implementationStatus] ?? ""}`}>
                  {STATUS_LABELS[selected.implementationStatus]}
                </span>
                <Badge variant="outline">{CATEGORY_LABELS[selected.category]}</Badge>
              </div>
              {selected.description && (
                <div>
                  <p className="text-sm font-medium mb-1">Beschreibung</p>
                  <p className="text-sm text-muted-foreground">{selected.description}</p>
                </div>
              )}
              <div className="grid grid-cols-2 gap-3 text-sm">
                {selected.responsible && <div><span className="text-muted-foreground">Zuständig:</span> {selected.responsible}</div>}
                {selected.reviewDate && <div><span className="text-muted-foreground">Überprüfung:</span> {new Date(selected.reviewDate).toLocaleDateString("de-DE")}</div>}
              </div>
              {selected.evidence && (
                <div>
                  <p className="text-sm font-medium mb-1">Nachweise</p>
                  <p className="text-sm text-muted-foreground">{selected.evidence}</p>
                </div>
              )}
              <div>
                <p className="text-sm font-medium mb-2">Status ändern</p>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(STATUS_LABELS).filter(([v]) => v !== selected.implementationStatus).map(([v, l]) => (
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
                    <AlertDialogTitle>TOM löschen?</AlertDialogTitle>
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
