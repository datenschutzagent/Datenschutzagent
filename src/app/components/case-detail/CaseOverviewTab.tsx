import { useMemo, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../ui/card";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "../ui/dialog";
import { LineChart, Line, Tooltip, ResponsiveContainer } from "recharts";
import { severityColors, priorityLabels, priorityColors } from "../../lib/mock-data";
import type { ApiCase, ApiFinding, ApiPlaybook, CaseSimilarityResult, CaseRiskScore, PlaybookCoverage, RunChecksStrategy } from "../../lib/api";
import { updateCase } from "../../lib/api";
import { useAppConfig } from "../../contexts/AppConfigContext";
import { CircleAlert, Download, FileCheck, Loader2, Shield } from "lucide-react";
import { toast } from "sonner";

export interface CaseOverviewTabProps {
  caseData: ApiCase;
  criticalFindings: ApiFinding[];
  highFindings: ApiFinding[];
  runChecksOpen: boolean;
  setRunChecksOpen: (open: boolean) => void;
  playbooks: ApiPlaybook[];
  selectedPlaybookId: string;
  setSelectedPlaybookId: (id: string) => void;
  runChecksStrategy: "full_text" | "rag" | "both";
  setRunChecksStrategy: (s: "full_text" | "rag" | "both") => void;
  onRunChecks: () => void;
  runChecksLoading: boolean;
  runChecksStatus: "idle" | "running" | "completed" | "failed";
  runChecksError: string | null;
  setRunChecksError: (err: string | null) => void;
  onSelectFinding: (finding: ApiFinding) => void;
  /** When false (e.g. viewer role), hide/disable write actions like Run Checks. */
  canEdit?: boolean;
  coveragePreview?: PlaybookCoverage | null;
  similarCases?: CaseSimilarityResult[];
  riskScore?: CaseRiskScore | null;
  onCaseUpdated?: (caseData: ApiCase) => void;
}

export function CaseOverviewTab({
  caseData,
  criticalFindings,
  highFindings,
  runChecksOpen,
  setRunChecksOpen,
  playbooks,
  selectedPlaybookId,
  setSelectedPlaybookId,
  runChecksStrategy,
  setRunChecksStrategy,
  onRunChecks,
  runChecksLoading,
  runChecksStatus,
  runChecksError,
  setRunChecksError,
  onSelectFinding,
  canEdit = true,
  coveragePreview,
  similarCases = [],
  riskScore,
  onCaseUpdated,
}: CaseOverviewTabProps) {
  const appConfig = useAppConfig();
  const processingContextLabels = useMemo<Record<string, string>>(
    () => Object.fromEntries(appConfig.processing_context_options.map((o) => [o.value, o.label])),
    [appConfig.processing_context_options],
  );
  const [deadlineValue, setDeadlineValue] = useState(caseData.deadline ?? "");
  const [deadlineSaving, setDeadlineSaving] = useState(false);

  const handleDeadlineSave = async () => {
    setDeadlineSaving(true);
    try {
      const updated = await updateCase(caseData.id, { deadline: deadlineValue || null });
      onCaseUpdated?.(updated);
      toast.success("Frist gespeichert");
    } catch {
      toast.error("Frist konnte nicht gespeichert werden");
    } finally {
      setDeadlineSaving(false);
    }
  };
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-3 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Metadaten</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div>
              <span className="text-slate-600 dark:text-slate-400">Vorgang-ID:</span>
              <p className="font-medium">{caseData.id}</p>
            </div>
            <div>
              <span className="text-slate-600 dark:text-slate-400">Erstellt von:</span>
              <p className="font-medium">{caseData.createdBy}</p>
            </div>
            <div>
              <span className="text-slate-600 dark:text-slate-400">Zugewiesen an:</span>
              <p className="font-medium">{caseData.assignee}</p>
            </div>
            <div>
              <span className="text-slate-600 dark:text-slate-400">Sprache:</span>
              <p className="font-medium">{caseData.language.toUpperCase()}</p>
            </div>
            {caseData.processingContext ? (
              <div>
                <span className="text-slate-600 dark:text-slate-400">Verarbeitungskontext:</span>
                <p className="font-medium">
                  {processingContextLabels[caseData.processingContext] ??
                    caseData.processingContext}
                </p>
              </div>
            ) : null}
            {(caseData.specialCategoryData || caseData.internationalTransfer) && (
              <div>
                <span className="text-slate-600 dark:text-slate-400">Hinweise:</span>
                <p className="font-medium">
                  {[
                    caseData.specialCategoryData ? "Besondere Kategorien (Art. 9 DSGVO)" : null,
                    caseData.internationalTransfer ? "Grenzüberschreitende Übermittlung" : null,
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
              </div>
            )}
            {caseData.priority && (
              <div>
                <span className="text-slate-600 dark:text-slate-400">Priorität:</span>
                <div className="mt-1">
                  <Badge className={priorityColors[caseData.priority]}>
                    {priorityLabels[caseData.priority]}
                  </Badge>
                </div>
              </div>
            )}
            <div>
              <span className="text-slate-600 dark:text-slate-400">Frist:</span>
              {canEdit ? (
                <div className="flex items-center gap-2 mt-1">
                  <input
                    type="date"
                    className="text-sm border border-input rounded-md px-2 py-1 bg-background"
                    value={deadlineValue}
                    onChange={(e) => setDeadlineValue(e.target.value)}
                  />
                  <Button size="sm" variant="outline" onClick={handleDeadlineSave} disabled={deadlineSaving}>
                    {deadlineSaving ? <Loader2 className="size-3 animate-spin" /> : "Speichern"}
                  </Button>
                </div>
              ) : caseData.deadline ? (
                <p className="font-medium">{new Date(caseData.deadline).toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" })}</p>
              ) : (
                <p className="text-slate-400 dark:text-slate-500 text-sm">Keine Frist</p>
              )}
              {caseData.deadline && (() => {
                const today = new Date();
                const deadline = new Date(caseData.deadline);
                const daysUntil = Math.ceil((deadline.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
                if (daysUntil < 0) {
                  return (
                    <Badge className="mt-1 bg-red-600 dark:bg-red-700 text-white">
                      {Math.abs(daysUntil)} Tage überfällig
                    </Badge>
                  );
                } else if (daysUntil <= 3) {
                  return (
                    <Badge className="mt-1 bg-orange-600 dark:bg-orange-700 text-white">
                      Noch {daysUntil} {daysUntil === 1 ? "Tag" : "Tage"}
                    </Badge>
                  );
                }
                return null;
              })()}
            </div>
            <div>
              <span className="text-slate-600 dark:text-slate-400">Playbook:</span>
              <p className="font-medium">{caseData.playbookVersion}</p>
            </div>
            <div>
              <span className="text-slate-600 dark:text-slate-400">Letzte Aktualisierung:</span>
              <p className="font-medium">{new Date(caseData.updatedAt).toLocaleDateString("de-DE")}</p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Statistik</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm text-slate-600 dark:text-slate-400">Dokumente</span>
              <Badge variant="outline">{caseData.documents.length}</Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-slate-600 dark:text-slate-400">Findings gesamt</span>
              <Badge variant="outline">{caseData.findings.length}</Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-red-600 dark:text-red-400">Kritisch (offen)</span>
              <Badge className="bg-red-100 text-red-700 dark:bg-red-900/50 dark:text-red-300">{criticalFindings.length}</Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-orange-600 dark:text-orange-400">Hoch (offen)</span>
              <Badge className="bg-orange-100 text-orange-700 dark:bg-orange-900/50 dark:text-orange-300">{highFindings.length}</Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-green-600 dark:text-green-400">Behoben</span>
              <Badge className="bg-green-100 text-green-700 dark:bg-green-900/50 dark:text-green-300">
                {caseData.findings.filter(f => f.status === "fixed").length}
              </Badge>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Aktionen</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {canEdit && (
            <Dialog open={runChecksOpen} onOpenChange={setRunChecksOpen}>
              <DialogTrigger asChild>
                <Button variant="outline" className="w-full justify-start gap-2">
                  <Shield className="size-4" />
                  Playbook-Checks ausführen
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Playbook-Checks ausführen</DialogTitle>
                  <DialogDescription>
                    Wählen Sie ein Playbook. Die Checks werden gegen alle Dokumente des Vorgangs ausgeführt.
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Playbook</label>
                  <select
                    className="w-full border border-input rounded-md px-3 py-2 bg-input-background"
                    value={selectedPlaybookId}
                    onChange={(e) => setSelectedPlaybookId(e.target.value)}
                  >
                    <option value="">— Auswählen —</option>
                    {playbooks.map((pb) => (
                      <option key={pb.id} value={pb.id}>{pb.name} (v{pb.version})</option>
                    ))}
                  </select>
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Prüfvariante</label>
                  <select
                    className="w-full border border-input rounded-md px-3 py-2 bg-input-background"
                    value={runChecksStrategy}
                    onChange={(e) => setRunChecksStrategy(e.target.value as "full_text" | "rag" | "both")}
                  >
                    <option value="full_text">Volltext (gesamtes Dokument)</option>
                    <option value="rag">RAG (relevante Chunks aus Weaviate)</option>
                    <option value="both">Beide (Vergleich Volltext + RAG)</option>
                  </select>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    RAG nutzt die Vektordatenbank; „Beide“ führt Volltext- und RAG-Checks parallel aus.
                  </p>
                </div>
                {/* Coverage preview */}
                {coveragePreview && coveragePreview.total_checks > 0 && (
                  <div className="rounded-md border p-3 text-sm space-y-1">
                    <p className="font-medium text-slate-700 dark:text-slate-300">
                      Coverage: {coveragePreview.applicable_count} / {coveragePreview.total_checks} Checks anwendbar
                    </p>
                    {coveragePreview.missing_document_types.length > 0 && (
                      <p className="text-amber-700 dark:text-amber-400 text-xs">
                        Fehlende Dokumenttypen: {coveragePreview.missing_document_types.join(", ")}
                      </p>
                    )}
                    <div className="max-h-32 overflow-y-auto space-y-0.5 mt-1">
                      {coveragePreview.checks.map((c, i) => (
                        <div key={i} className="flex items-center gap-1.5 text-xs">
                          <span className={c.applicable ? "text-green-600 dark:text-green-400" : "text-slate-400 dark:text-slate-500"}>
                            {c.applicable ? "✓" : "–"}
                          </span>
                          <span className={c.applicable ? "" : "text-slate-400 dark:text-slate-500"}>{c.name}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {(runChecksStatus === "running" || runChecksError) && (
                  <div className="rounded-md border p-3 text-sm">
                    {runChecksStatus === "running" && (
                      <div className="flex items-center gap-2 text-slate-600 dark:text-slate-400">
                        <Loader2 className="size-4 animate-spin" />
                        Playbook-Checks werden ausgeführt… Bitte kurz warten.
                      </div>
                    )}
                    {runChecksError && (
                      <div className="text-amber-700 dark:text-amber-400">
                        <p className="font-medium">Playbook-Checks fehlgeschlagen</p>
                        <p className="mt-1">{runChecksError}</p>
                        <Button variant="outline" size="sm" className="mt-2" onClick={() => setRunChecksError(null)}>
                          Schließen
                        </Button>
                      </div>
                    )}
                  </div>
                )}
                <div className="flex justify-end gap-2">
                  <Button variant="outline" onClick={() => { setRunChecksOpen(false); setRunChecksError(null); }}>Abbrechen</Button>
                  <Button onClick={onRunChecks} disabled={!selectedPlaybookId || runChecksLoading || runChecksStatus === "running"}>
                    {runChecksLoading ? <Loader2 className="size-4 animate-spin" /> : null}
                    Checks starten
                  </Button>
                </div>
              </DialogContent>
            </Dialog>
            )}
            <Button variant="outline" className="w-full justify-start gap-2">
              <FileCheck className="size-4" />
              VVT normalisieren
            </Button>
            <Button variant="outline" className="w-full justify-start gap-2">
              <Download className="size-4" />
              Alle Artefakte exportieren
            </Button>
          </CardContent>
        </Card>
      </div>

      {riskScore && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              Risiko-Score
              {riskScore.history.length > 0 && (
                <span className="text-xs font-normal text-muted-foreground">({riskScore.history.length} Prüfläufe)</span>
              )}
            </CardTitle>
            <CardDescription>Aktueller Risikowert des Vorgangs (0 = kein Risiko, 100 = maximales Risiko)</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-6">
              <div className="shrink-0 text-center">
                <span
                  className={`text-4xl font-bold ${
                    riskScore.score === 0
                      ? "text-green-600 dark:text-green-400"
                      : riskScore.score < 30
                      ? "text-yellow-600 dark:text-yellow-400"
                      : riskScore.score < 60
                      ? "text-orange-600 dark:text-orange-400"
                      : "text-red-600 dark:text-red-400"
                  }`}
                >
                  {riskScore.score}
                </span>
                <p className="text-xs text-muted-foreground mt-1">/ 100</p>
              </div>
              <div className="flex-1 min-w-0">
                <div className="w-full bg-slate-200 dark:bg-slate-700 rounded-full h-3 mb-3">
                  <div
                    className={`h-3 rounded-full transition-all ${
                      riskScore.score === 0
                        ? "bg-green-500"
                        : riskScore.score < 30
                        ? "bg-yellow-500"
                        : riskScore.score < 60
                        ? "bg-orange-500"
                        : "bg-red-500"
                    }`}
                    style={{ width: `${riskScore.score}%` }}
                  />
                </div>
                {riskScore.history.length >= 2 && (
                  <ResponsiveContainer width="100%" height={48}>
                    <LineChart data={riskScore.history.map((h) => ({ score: h.score, at: new Date(h.created_at).toLocaleDateString("de-DE") }))}>
                      <Line type="monotone" dataKey="score" stroke="#3b82f6" strokeWidth={2} dot={false} />
                      <Tooltip
                        formatter={(v: number) => [`Score: ${v}`, ""]}
                        labelFormatter={(l) => l}
                        contentStyle={{ fontSize: "11px" }}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                )}
              </div>
              {riskScore.history.length > 0 && (() => {
                const last = riskScore.history[riskScore.history.length - 1];
                return (
                  <div className="shrink-0 text-xs text-muted-foreground space-y-1 text-right">
                    <div>Kritisch: <span className="font-medium text-red-600 dark:text-red-400">{last.critical}</span></div>
                    <div>Hoch: <span className="font-medium text-orange-600 dark:text-orange-400">{last.high}</span></div>
                    <div>Mittel: <span className="font-medium text-yellow-600 dark:text-yellow-400">{last.medium}</span></div>
                  </div>
                );
              })()}
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Aktuelle Findings (Top 3)</CardTitle>
          <CardDescription>Die wichtigsten offenen Prüfpunkte</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {caseData.findings
            .filter(f => f.status === "open")
            .slice(0, 3)
            .map((finding) => (
              <div
                key={finding.id}
                className="p-4 border border-border rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800/50 cursor-pointer transition-colors"
                onClick={() => onSelectFinding(finding)}
              >
                <div className="flex items-start gap-3">
                  <CircleAlert className="size-5 text-red-600 dark:text-red-400 mt-0.5" />
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <h4 className="font-medium text-slate-900 dark:text-slate-100">{finding.checkName}</h4>
                      <Badge className={severityColors[finding.severity]}>
                        {finding.severity}
                      </Badge>
                      {finding.sourceStrategy === "rag" && (
                        <Badge variant="secondary" className="text-xs bg-purple-100 text-purple-800 dark:bg-purple-900/50 dark:text-purple-300">RAG</Badge>
                      )}
                      {finding.sourceStrategy === "full_text" && (
                        <Badge variant="outline" className="text-xs">Volltext</Badge>
                      )}
                    </div>
                    <p className="text-sm text-slate-600 dark:text-slate-400">{finding.description}</p>
                  </div>
                </div>
              </div>
            ))}
        </CardContent>
      </Card>

      {similarCases.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Ähnliche Vorgänge</CardTitle>
            <CardDescription>Vorgänge aus derselben Abteilung und demselben Vorgangstyp mit überlappenden Findings</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {similarCases.map((s) => (
              <div key={String(s.case_id)} className="p-3 border border-border rounded-lg flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-sm text-foreground truncate">{s.title}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {s.department} · {s.case_type}
                  </p>
                  {s.shared_check_names.length > 0 && (
                    <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 truncate">
                      Gemeinsam: {s.shared_check_names.slice(0, 3).join(", ")}{s.shared_check_names.length > 3 ? ` +${s.shared_check_names.length - 3}` : ""}
                    </p>
                  )}
                </div>
                <div className="shrink-0 flex flex-col items-end gap-1">
                  <Badge variant="outline" className="text-xs">
                    {Math.round(s.overlap_score * 100)}% Überschneidung
                  </Badge>
                  <Badge variant="secondary" className="text-xs">{s.status}</Badge>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
