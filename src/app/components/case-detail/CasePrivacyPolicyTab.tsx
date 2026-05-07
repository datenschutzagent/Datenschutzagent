import { useCallback, useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../ui/card";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Label } from "../ui/label";
import { Textarea } from "../ui/textarea";
import { Badge } from "../ui/badge";
import { Skeleton } from "../ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "../ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "../ui/alert-dialog";
import { Alert, AlertDescription } from "../ui/alert";
import {
  deletePrivacyPolicy,
  generatePrivacyPolicyForCase,
  listPrivacyPoliciesForCase,
  updatePrivacyPolicy,
  type ApiCase,
  type ApiPrivacyPolicy,
} from "../../lib/api";
import { Download, FileText, Loader2, Pencil, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";

function formatDateTime(iso: string) {
  try {
    return new Date(iso).toLocaleString("de-DE", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function downloadMarkdown(policy: ApiPrivacyPolicy) {
  const blob = new Blob([policy.content_markdown], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `datenschutzerklaerung_v${policy.version}_${policy.id.slice(0, 8)}.md`;
  a.click();
  URL.revokeObjectURL(url);
}

interface Props {
  caseData: ApiCase;
  canEdit: boolean;
}

export function CasePrivacyPolicyTab({ caseData, canEdit }: Props) {
  const [policies, setPolicies] = useState<ApiPrivacyPolicy[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<ApiPrivacyPolicy | null>(null);
  const [editMode, setEditMode] = useState(false);
  const [editContent, setEditContent] = useState("");
  const [editTitle, setEditTitle] = useState("");
  const [saving, setSaving] = useState(false);
  const [showGenerate, setShowGenerate] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [genForm, setGenForm] = useState({ contact: "", notes: "" });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listPrivacyPoliciesForCase(caseData.id);
      setPolicies(data);
      setSelected((prev) => {
        if (!prev) return data[0] ?? null;
        return data.find((p) => p.id === prev.id) ?? data[0] ?? null;
      });
    } catch {
      toast.error("Datenschutzerklärungen konnten nicht geladen werden.");
    } finally {
      setLoading(false);
    }
  }, [caseData.id]);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleGenerate() {
    setGenerating(true);
    try {
      const policy = await generatePrivacyPolicyForCase(caseData.id, {
        contact: genForm.contact || undefined,
        notes: genForm.notes || undefined,
      });
      toast.success(`Version ${policy.version} erfolgreich generiert.`);
      setShowGenerate(false);
      setGenForm({ contact: "", notes: "" });
      setPolicies((prev) => [policy, ...prev]);
      setSelected(policy);
    } catch (err) {
      toast.error(`Generierung fehlgeschlagen: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setGenerating(false);
    }
  }

  function openEdit(policy: ApiPrivacyPolicy) {
    setEditContent(policy.content_markdown);
    setEditTitle(policy.title);
    setEditMode(true);
  }

  async function handleSaveEdit() {
    if (!selected) return;
    setSaving(true);
    try {
      const updated = await updatePrivacyPolicy(selected.id, {
        title: editTitle,
        content_markdown: editContent,
      });
      setPolicies((prev) => prev.map((p) => (p.id === updated.id ? updated : p)));
      setSelected(updated);
      setEditMode(false);
      toast.success("Gespeichert.");
    } catch {
      toast.error("Speichern fehlgeschlagen.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: string) {
    try {
      await deletePrivacyPolicy(id);
      setPolicies((prev) => prev.filter((p) => p.id !== id));
      if (selected?.id === id) setSelected(null);
      toast.success("Gelöscht.");
    } catch {
      toast.error("Löschen fehlgeschlagen.");
    }
  }

  const hasContext = Boolean(caseData.processingContext);
  const hasRetention = Boolean(caseData.retentionMonths);
  const showCompletenessHint = !hasContext || !hasRetention;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="flex flex-row items-start justify-between gap-4 pb-3">
          <div>
            <CardTitle>Datenschutzerklärung</CardTitle>
            <CardDescription>
              Vorgangsspezifische Erklärung gemäß Art. 13/14 DSGVO. Mehrere Versionen sind möglich.
            </CardDescription>
          </div>
          {canEdit && !caseData.archivedAt && (
            <Button onClick={() => setShowGenerate(true)} size="sm">
              <Plus className="size-4 mr-2" />
              Neue Version generieren
            </Button>
          )}
        </CardHeader>
        <CardContent>
          {showCompletenessHint && (
            <Alert className="mb-4 border-amber-200 bg-amber-50 dark:border-amber-800 dark:bg-amber-900/30">
              <AlertDescription className="text-amber-800 dark:text-amber-200 text-sm">
                Hinweis: Für ein vollständiges Ergebnis sollten Verarbeitungs-Kontext und Speicherdauer (Retention) im Vorgang gepflegt sein.
              </AlertDescription>
            </Alert>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div className="space-y-2">
              <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
                Versionen ({policies.length})
              </h3>
              {loading ? (
                Array.from({ length: 2 }).map((_, i) => (
                  <Skeleton key={i} className="h-16 w-full rounded-md" />
                ))
              ) : policies.length === 0 ? (
                <Card className="border-dashed">
                  <CardContent className="py-8 text-center">
                    <FileText className="size-8 mx-auto mb-2 text-muted-foreground" />
                    <p className="text-sm text-muted-foreground">
                      Noch keine Datenschutzerklärung für diesen Vorgang.
                    </p>
                    {canEdit && !caseData.archivedAt && (
                      <Button
                        variant="outline"
                        size="sm"
                        className="mt-3"
                        onClick={() => setShowGenerate(true)}
                      >
                        Jetzt generieren
                      </Button>
                    )}
                  </CardContent>
                </Card>
              ) : (
                policies.map((p) => (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => {
                      setSelected(p);
                      setEditMode(false);
                    }}
                    className={`w-full text-left rounded-md border p-3 transition-colors hover:border-primary/50 ${
                      selected?.id === p.id ? "border-primary bg-muted/30" : ""
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <Badge variant="outline" className="text-xs">
                        v{p.version}
                      </Badge>
                      <span className="text-xs text-muted-foreground">
                        {formatDateTime(p.generated_at)}
                      </span>
                    </div>
                    <p className="text-sm font-medium truncate">{p.title}</p>
                    {p.version_note && (
                      <p className="text-xs text-muted-foreground truncate mt-0.5">
                        {p.version_note}
                      </p>
                    )}
                  </button>
                ))
              )}
            </div>

            <div className="lg:col-span-2">
              {!selected ? (
                <Card className="h-full flex items-center justify-center border-dashed">
                  <CardContent className="text-center py-12">
                    <FileText className="size-10 mx-auto mb-3 text-muted-foreground" />
                    <p className="text-sm text-muted-foreground">
                      Wähle eine Version aus oder generiere eine neue.
                    </p>
                  </CardContent>
                </Card>
              ) : editMode ? (
                <Card>
                  <CardHeader className="flex flex-row items-center justify-between pb-3 gap-3">
                    <div className="flex-1">
                      <Input
                        value={editTitle}
                        onChange={(e) => setEditTitle(e.target.value)}
                        placeholder="Titel"
                        className="font-semibold"
                      />
                    </div>
                    <div className="flex gap-2">
                      <Button variant="outline" size="sm" onClick={() => setEditMode(false)}>
                        Abbrechen
                      </Button>
                      <Button size="sm" onClick={handleSaveEdit} disabled={saving}>
                        {saving ? <Loader2 className="size-4 animate-spin mr-1" /> : null}
                        Speichern
                      </Button>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <Textarea
                      value={editContent}
                      onChange={(e) => setEditContent(e.target.value)}
                      className="font-mono text-sm min-h-[480px] resize-y"
                    />
                  </CardContent>
                </Card>
              ) : (
                <Card>
                  <CardHeader className="flex flex-row items-start justify-between gap-3 pb-3">
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <Badge variant="outline" className="text-xs">
                          v{selected.version}
                        </Badge>
                        <CardTitle className="text-base">{selected.title}</CardTitle>
                      </div>
                      <CardDescription className="text-xs">
                        Erstellt: {formatDateTime(selected.generated_at)}
                        {selected.created_by ? ` • ${selected.created_by}` : ""}
                      </CardDescription>
                      {selected.version_note && (
                        <p className="text-xs text-muted-foreground mt-1">
                          {selected.version_note}
                        </p>
                      )}
                    </div>
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => downloadMarkdown(selected)}
                      >
                        <Download className="size-4 mr-1" />
                        Download
                      </Button>
                      {canEdit && !caseData.archivedAt && (
                        <Button variant="outline" size="sm" onClick={() => openEdit(selected)}>
                          <Pencil className="size-4 mr-1" />
                          Bearbeiten
                        </Button>
                      )}
                      {canEdit && !caseData.archivedAt && (
                        <AlertDialog>
                          <AlertDialogTrigger asChild>
                            <Button
                              variant="outline"
                              size="sm"
                              className="text-destructive hover:text-destructive"
                              aria-label="Version löschen"
                            >
                              <Trash2 className="size-4" />
                            </Button>
                          </AlertDialogTrigger>
                          <AlertDialogContent>
                            <AlertDialogHeader>
                              <AlertDialogTitle>Version löschen?</AlertDialogTitle>
                              <AlertDialogDescription>
                                Diese Version der Datenschutzerklärung wird unwiderruflich entfernt.
                              </AlertDialogDescription>
                            </AlertDialogHeader>
                            <AlertDialogFooter>
                              <AlertDialogCancel>Abbrechen</AlertDialogCancel>
                              <AlertDialogAction onClick={() => handleDelete(selected.id)}>
                                Löschen
                              </AlertDialogAction>
                            </AlertDialogFooter>
                          </AlertDialogContent>
                        </AlertDialog>
                      )}
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="prose prose-sm dark:prose-invert max-w-none max-h-[560px] overflow-y-auto">
                      <pre className="whitespace-pre-wrap text-sm font-sans leading-relaxed">
                        {selected.content_markdown}
                      </pre>
                    </div>
                  </CardContent>
                </Card>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      <Dialog open={showGenerate} onOpenChange={setShowGenerate}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Datenschutzerklärung generieren</DialogTitle>
            <DialogDescription>
              Eine neue Version wird auf Basis der Daten dieses Vorgangs erzeugt.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label htmlFor="contact">Kontakt Verantwortlicher (optional)</Label>
              <Input
                id="contact"
                placeholder="Name, Adresse, E-Mail des Verantwortlichen"
                value={genForm.contact}
                onChange={(e) => setGenForm((f) => ({ ...f, contact: e.target.value }))}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="notes">Besondere Hinweise (optional)</Label>
              <Textarea
                id="notes"
                placeholder="z.B. Cookie-Banner, spezifische Empfänger, …"
                value={genForm.notes}
                onChange={(e) => setGenForm((f) => ({ ...f, notes: e.target.value }))}
                className="min-h-[80px]"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowGenerate(false)} disabled={generating}>
              Abbrechen
            </Button>
            <Button onClick={handleGenerate} disabled={generating}>
              {generating ? (
                <>
                  <Loader2 className="size-4 animate-spin mr-2" />
                  Generiere…
                </>
              ) : (
                "Generieren"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
