import { useState, useEffect, useCallback } from "react";
import { AppLayout } from "../components/app-layout";
import { PageHeader } from "../components/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../components/ui/dialog";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "../components/ui/alert-dialog";
import { Skeleton } from "../components/ui/skeleton";
import { Badge } from "../components/ui/badge";
import {
  listPrivacyPolicies,
  generatePrivacyPolicy,
  updatePrivacyPolicy,
  deletePrivacyPolicy,
  type ApiPrivacyPolicy,
} from "../lib/api";
import { toast } from "sonner";
import { Plus, FileText, Loader2, Trash2, Pencil, Download } from "lucide-react";

function formatDate(iso: string) {
  try {
    return new Date(iso).toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" });
  } catch {
    return iso;
  }
}

function downloadMarkdown(policy: ApiPrivacyPolicy) {
  const blob = new Blob([policy.content_markdown], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `datenschutzerklaerung_${policy.id.slice(0, 8)}.md`;
  a.click();
  URL.revokeObjectURL(url);
}

export function PrivacyPolicyPage() {
  const [policies, setPolicies] = useState<ApiPrivacyPolicy[]>([]);
  const [loading, setLoading] = useState(true);
  const [showGenerate, setShowGenerate] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [selected, setSelected] = useState<ApiPrivacyPolicy | null>(null);
  const [editMode, setEditMode] = useState(false);
  const [editContent, setEditContent] = useState("");
  const [editTitle, setEditTitle] = useState("");
  const [saving, setSaving] = useState(false);

  const [genForm, setGenForm] = useState({
    org_name: "",
    department: "",
    contact: "",
    notes: "",
  });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listPrivacyPolicies();
      setPolicies(data);
    } catch {
      toast.error("Datenschutzerklärungen konnten nicht geladen werden.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  async function handleGenerate() {
    setGenerating(true);
    try {
      const policy = await generatePrivacyPolicy({
        org_name: genForm.org_name || undefined,
        department: genForm.department || undefined,
        contact: genForm.contact || undefined,
        notes: genForm.notes || undefined,
      });
      toast.success("Datenschutzerklärung erfolgreich generiert.");
      setShowGenerate(false);
      setGenForm({ org_name: "", department: "", contact: "", notes: "" });
      setPolicies((prev) => [policy, ...prev]);
      setSelected(policy);
    } catch (err) {
      toast.error(`Generierung fehlgeschlagen: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setGenerating(false);
    }
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

  function openEdit(policy: ApiPrivacyPolicy) {
    setEditContent(policy.content_markdown);
    setEditTitle(policy.title);
    setEditMode(true);
  }

  return (
    <AppLayout>
      <div className="container mx-auto max-w-6xl py-8 px-4">
        <PageHeader
          title="Datenschutzerklärung"
          description="KI-gestützte Generierung von Datenschutzerklärungen gemäß Art. 13/14 DSGVO auf Basis Ihrer VVT-Daten."
          action={
            <Button onClick={() => setShowGenerate(true)}>
              <Plus className="size-4 mr-2" />
              Neue generieren
            </Button>
          }
        />

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mt-6">
          {/* Linke Spalte: Liste */}
          <div className="lg:col-span-1 space-y-3">
            <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
              Gespeicherte Erklärungen ({policies.length})
            </h2>

            {loading ? (
              Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-20 w-full rounded-lg" />
              ))
            ) : policies.length === 0 ? (
              <Card className="border-dashed">
                <CardContent className="py-10 text-center">
                  <FileText className="size-8 mx-auto mb-3 text-muted-foreground" />
                  <p className="text-sm text-muted-foreground">Noch keine Datenschutzerklärung generiert.</p>
                  <Button
                    variant="outline"
                    size="sm"
                    className="mt-3"
                    onClick={() => setShowGenerate(true)}
                  >
                    Jetzt generieren
                  </Button>
                </CardContent>
              </Card>
            ) : (
              policies.map((policy) => (
                <Card
                  key={policy.id}
                  className={`cursor-pointer transition-colors hover:border-primary/50 ${selected?.id === policy.id ? "border-primary" : ""}`}
                  onClick={() => { setSelected(policy); setEditMode(false); }}
                >
                  <CardContent className="p-4">
                    <p className="font-medium text-sm truncate">{policy.title}</p>
                    {policy.department && (
                      <Badge variant="outline" className="mt-1 text-xs">{policy.department}</Badge>
                    )}
                    <p className="text-xs text-muted-foreground mt-1">
                      Erstellt: {formatDate(policy.generated_at)}
                    </p>
                    {policy.version_note && (
                      <p className="text-xs text-muted-foreground truncate">{policy.version_note}</p>
                    )}
                  </CardContent>
                </Card>
              ))
            )}
          </div>

          {/* Rechte Spalte: Anzeige / Editor */}
          <div className="lg:col-span-2">
            {!selected ? (
              <Card className="h-full flex items-center justify-center border-dashed">
                <CardContent className="text-center py-16">
                  <FileText className="size-12 mx-auto mb-4 text-muted-foreground" />
                  <p className="text-muted-foreground">Wählen Sie eine Datenschutzerklärung aus oder generieren Sie eine neue.</p>
                </CardContent>
              </Card>
            ) : editMode ? (
              <Card>
                <CardHeader className="flex flex-row items-center justify-between pb-3">
                  <div className="flex-1">
                    <Input
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      className="font-semibold text-base"
                      placeholder="Titel"
                    />
                  </div>
                  <div className="flex gap-2 ml-3">
                    <Button variant="outline" size="sm" onClick={() => setEditMode(false)}>Abbrechen</Button>
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
                    className="font-mono text-sm min-h-[500px] resize-y"
                    placeholder="Markdown-Inhalt…"
                  />
                </CardContent>
              </Card>
            ) : (
              <Card>
                <CardHeader className="flex flex-row items-center justify-between pb-3">
                  <div>
                    <CardTitle className="text-base">{selected.title}</CardTitle>
                    {selected.version_note && (
                      <p className="text-xs text-muted-foreground mt-0.5">{selected.version_note}</p>
                    )}
                  </div>
                  <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={() => downloadMarkdown(selected)}>
                      <Download className="size-4 mr-1" />
                      Download
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => openEdit(selected)}>
                      <Pencil className="size-4 mr-1" />
                      Bearbeiten
                    </Button>
                    <AlertDialog>
                      <AlertDialogTrigger asChild>
                        <Button variant="outline" size="sm" className="text-destructive hover:text-destructive">
                          <Trash2 className="size-4" />
                        </Button>
                      </AlertDialogTrigger>
                      <AlertDialogContent>
                        <AlertDialogHeader>
                          <AlertDialogTitle>Datenschutzerklärung löschen?</AlertDialogTitle>
                          <AlertDialogDescription>
                            Diese Aktion kann nicht rückgängig gemacht werden.
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
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="prose prose-sm dark:prose-invert max-w-none max-h-[600px] overflow-y-auto">
                    <pre className="whitespace-pre-wrap text-sm font-sans leading-relaxed">
                      {selected.content_markdown}
                    </pre>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        </div>

        {/* Generierungs-Dialog */}
        <Dialog open={showGenerate} onOpenChange={setShowGenerate}>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle>Datenschutzerklärung generieren</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-2">
              <p className="text-sm text-muted-foreground">
                Das LLM erstellt eine Datenschutzerklärung auf Basis Ihrer VVT-Daten und AVV-Verträge.
                Die Eingaben unten sind optional und verbessern das Ergebnis.
              </p>
              <div className="space-y-2">
                <Label>Organisationsname</Label>
                <Input
                  placeholder="Wird aus dem Org-Profil übernommen wenn leer"
                  value={genForm.org_name}
                  onChange={(e) => setGenForm((f) => ({ ...f, org_name: e.target.value }))}
                />
              </div>
              <div className="space-y-2">
                <Label>Abteilung / Bereich (optional)</Label>
                <Input
                  placeholder="z.B. IT, HR, Marketing"
                  value={genForm.department}
                  onChange={(e) => setGenForm((f) => ({ ...f, department: e.target.value }))}
                />
              </div>
              <div className="space-y-2">
                <Label>Kontakt Verantwortlicher (optional)</Label>
                <Input
                  placeholder="Name, Adresse, E-Mail des Verantwortlichen"
                  value={genForm.contact}
                  onChange={(e) => setGenForm((f) => ({ ...f, contact: e.target.value }))}
                />
              </div>
              <div className="space-y-2">
                <Label>Besondere Hinweise (optional)</Label>
                <Textarea
                  placeholder="z.B. Cookie-Banner, spezifische Verarbeitungszwecke…"
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
    </AppLayout>
  );
}
