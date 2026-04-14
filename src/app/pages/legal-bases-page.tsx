import { Link, useNavigate } from "react-router";
import { AppLayout } from "../components/app-layout";
import { PageHeader } from "../components/page-header";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "../components/ui/dialog";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "../components/ui/alert-dialog";
import {
  getLegalBases,
  createLegalBase,
  updateLegalBase,
  deleteLegalBase,
  canEdit,
  type ApiLegalBase,
} from "../lib/api";
import { useAuthOptional } from "../contexts/AuthContext";
import { toast } from "sonner";
import { logger } from "../lib/logger";
import { Skeleton } from "../components/ui/skeleton";
import { Plus, Scale, Edit, Trash2, Loader2 } from "lucide-react";
import { useState, useEffect } from "react";

export function LegalBasesPage() {
  const navigate = useNavigate();
  const auth = useAuthOptional();
  const [bases, setBases] = useState<ApiLegalBase[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<ApiLegalBase | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ApiLegalBase | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const [title, setTitle] = useState("");
  const [shortName, setShortName] = useState("");
  const [content, setContent] = useState("");
  const [applicability, setApplicability] = useState<"always" | "conditional">("always");
  const [departmentCodesStr, setDepartmentCodesStr] = useState("");
  const [caseTypesStr, setCaseTypesStr] = useState("");
  const [internalOnly, setInternalOnly] = useState(false);

  const loadBases = () => {
    setLoading(true);
    getLegalBases()
      .then(setBases)
      .catch((e) => {
        logger.error("Rechtsgrundlagen konnten nicht geladen werden", {}, e);
        toast.error("Rechtsgrundlagen konnten nicht geladen werden.");
        setBases([]);
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadBases();
  }, []);

  const openCreate = () => {
    setEditing(null);
    setTitle("");
    setShortName("");
    setContent("");
    setApplicability("always");
    setDepartmentCodesStr("");
    setCaseTypesStr("");
    setInternalOnly(false);
    setSubmitError(null);
    setDialogOpen(true);
  };

  const openEdit = (b: ApiLegalBase) => {
    setEditing(b);
    setTitle(b.title);
    setShortName(b.shortName ?? "");
    setContent(b.content ?? "");
    setApplicability(b.applicability);
    setDepartmentCodesStr((b.departmentCodes ?? []).join(", "));
    setCaseTypesStr((b.caseTypes ?? []).join(", "));
    setInternalOnly(b.internalOnly ?? false);
    setSubmitError(null);
    setDialogOpen(true);
  };

  const handleSubmit = async () => {
    setSubmitError(null);
    if (!title.trim()) {
      setSubmitError("Titel ist erforderlich.");
      return;
    }
    const departmentCodes = departmentCodesStr
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    const caseTypes = caseTypesStr
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    setActionLoading(true);
    try {
      if (editing) {
        await updateLegalBase(editing.id, {
          title: title.trim(),
          short_name: shortName.trim() || null,
          content: content.trim() || "",
          applicability,
          department_codes: applicability === "conditional" ? departmentCodes : null,
          case_types: applicability === "conditional" ? caseTypes : null,
          internal_only: internalOnly,
        });
      } else {
        await createLegalBase({
          title: title.trim(),
          short_name: shortName.trim() || null,
          content: content.trim() || "",
          applicability,
          department_codes: applicability === "conditional" ? departmentCodes : null,
          case_types: applicability === "conditional" ? caseTypes : null,
          internal_only: internalOnly,
        });
      }
      setDialogOpen(false);
      loadBases();
      toast.success(editing ? "Rechtsgrundlage gespeichert" : "Rechtsgrundlage angelegt");
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : String(e));
    } finally {
      setActionLoading(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setActionLoading(true);
    try {
      await deleteLegalBase(deleteTarget.id);
      setDeleteTarget(null);
      loadBases();
      toast.success("Rechtsgrundlage gelöscht");
    } finally {
      setActionLoading(false);
    }
  };

  const canEditBases = canEdit(auth?.user ?? null);

  return (
    <AppLayout>
        <PageHeader
          title="Rechtsgrundlagen"
          description="Gesetze und Vorgaben (DSGVO, BDSG, Klinik-Gesetz, Betriebsvereinbarungen) für die Prüfungen des Agenten"
          action={
            canEditBases ? (
              <Button className="gap-2" onClick={openCreate}>
                <Plus className="size-4" />
                Neue Rechtsgrundlage
              </Button>
            ) : undefined
          }
        />

        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[1, 2, 3].map((i) => (
              <Card key={i}>
                <CardHeader>
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <Skeleton className="h-5 w-48" />
                    <Skeleton className="h-5 w-16" />
                  </div>
                  <Skeleton className="h-4 w-24 mb-2" />
                  <Skeleton className="h-4 w-full" />
                  <Skeleton className="h-4 w-3/4" />
                </CardHeader>
                <CardContent>
                  <div className="flex gap-2 pt-2 border-t border-border">
                    <Skeleton className="h-8 w-20" />
                    <Skeleton className="h-8 w-20" />
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        ) : bases.length === 0 ? (
          <Card>
            <CardContent className="py-12 text-center">
              <Scale className="size-12 text-muted-foreground/30 mx-auto mb-4" />
              <p className="text-muted-foreground">Keine Rechtsgrundlagen angelegt</p>
              <p className="text-sm text-muted-foreground mt-1">
                Legen Sie DSGVO, BDSG oder andere Vorgaben an, um sie in Playbooks zu referenzieren.
              </p>
              {canEditBases && (
                <Button className="mt-4" onClick={openCreate}>
                  <Plus className="size-4 mr-2" />
                  Erste Rechtsgrundlage anlegen
                </Button>
              )}
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {bases.map((base) => (
              <Card key={base.id}>
                <CardHeader>
                  <div className="flex items-start justify-between gap-2">
                    <Scale className="size-6 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
                    <div className="flex gap-1 shrink-0">
                      {canEditBases && (
                        <>
                          <Button variant="ghost" size="icon" className="size-8" onClick={() => openEdit(base)} aria-label={`${base.title} bearbeiten`}>
                            <Edit className="size-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="size-8 text-red-600 hover:text-red-700"
                            onClick={() => setDeleteTarget(base)}
                            aria-label={`${base.title} löschen`}
                          >
                            <Trash2 className="size-4" />
                          </Button>
                        </>
                      )}
                    </div>
                  </div>
                  <CardTitle className="text-base">{base.title}</CardTitle>
                  <CardDescription>
                    {base.shortName ?? base.title} •{" "}
                    {base.applicability === "always" ? (
                      <Badge variant="outline" className="text-xs">Immer gültig</Badge>
                    ) : (
                      <Badge variant="secondary" className="text-xs">Bedingt</Badge>
                    )}
                  </CardDescription>
                </CardHeader>
                <CardContent className="text-sm text-muted-foreground">
                  {base.applicability === "conditional" && (
                    <div className="space-y-1">
                      {base.departmentCodes?.length > 0 && (
                        <p>Einheiten: {base.departmentCodes.join(", ")}</p>
                      )}
                      {base.caseTypes?.length > 0 && <p>Vorgangstypen: {base.caseTypes.join(", ")}</p>}
                      {base.internalOnly && <p className="text-amber-600 dark:text-amber-400">Nur Innenrecht</p>}
                    </div>
                  )}
                  <p className="mt-2 line-clamp-2">{base.content?.slice(0, 120) || "—"}…</p>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{editing ? "Rechtsgrundlage bearbeiten" : "Neue Rechtsgrundlage"}</DialogTitle>
            <DialogDescription>
              Titel und Inhalt werden für RAG-Abfragen bei Playbook-Checks verwendet. Bei „bedingt“ können
              Einheit und Vorgangstyp eingeschränkt werden.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="lb-title">Titel *</Label>
              <Input
                id="lb-title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="z. B. DSGVO, BDSG, Hessisches Klinikgesetz"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="lb-short">Kurzname (optional)</Label>
              <Input
                id="lb-short"
                value={shortName}
                onChange={(e) => setShortName(e.target.value)}
                placeholder="z. B. DSGVO"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="lb-content">Inhalt (Auszüge, Paragraphen, Anforderungen)</Label>
              <Textarea
                id="lb-content"
                value={content}
                onChange={(e) => setContent(e.target.value)}
                rows={8}
                className="font-mono text-sm"
                placeholder="Relevante Texte aus der Rechtsgrundlage für die Prüfung durch den Agenten…"
              />
            </div>
            <div className="grid gap-2">
              <Label>Gültigkeit</Label>
              <Select value={applicability} onValueChange={(v) => setApplicability(v as "always" | "conditional")}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="always">Immer gültig (z. B. DSGVO, BDSG)</SelectItem>
                  <SelectItem value="conditional">Nur unter Bedingungen (Einheit / Vorgangstyp)</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {applicability === "conditional" && (
              <>
                <div className="grid gap-2">
                  <Label htmlFor="lb-depts">Einheiten-Codes (kommagetrennt, z. B. IT, HR)</Label>
                  <Input
                    id="lb-depts"
                    value={departmentCodesStr}
                    onChange={(e) => setDepartmentCodesStr(e.target.value)}
                    placeholder="IT, HR, RECHT"
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="lb-ct">Vorgangstypen (kommagetrennt)</Label>
                  <Input
                    id="lb-ct"
                    value={caseTypesStr}
                    onChange={(e) => setCaseTypesStr(e.target.value)}
                    placeholder="Allgemein, IT-System, HR"
                  />
                </div>
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="lb-internal"
                    checked={internalOnly}
                    onChange={(e) => setInternalOnly(e.target.checked)}
                    className="rounded border-slate-300"
                  />
                  <Label htmlFor="lb-internal">Nur Innenrecht (z. B. Betriebsvereinbarung)</Label>
                </div>
              </>
            )}
            {submitError && (
              <p className="text-sm text-red-600 dark:text-red-400">{submitError}</p>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)} disabled={actionLoading}>
              Abbrechen
            </Button>
            <Button onClick={handleSubmit} disabled={actionLoading}>
              {actionLoading && <Loader2 className="size-4 animate-spin mr-2" />}
              {editing ? "Speichern" : "Anlegen"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={!!deleteTarget} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Rechtsgrundlage löschen?</AlertDialogTitle>
            <AlertDialogDescription>
              {deleteTarget && (
                <>„{deleteTarget.title}“ wird unwiderruflich gelöscht. Referenzen in Playbooks werden ungültig.</>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Abbrechen</AlertDialogCancel>
            <AlertDialogAction onClick={handleDelete} className="bg-red-600 hover:bg-red-700" disabled={actionLoading}>
              Löschen
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </AppLayout>
  );
}
