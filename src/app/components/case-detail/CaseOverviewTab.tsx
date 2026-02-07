import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../ui/card";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "../ui/dialog";
import { severityColors, priorityLabels, priorityColors } from "../../lib/mock-data";
import type { ApiCase, ApiFinding, ApiPlaybook, RunChecksStrategy } from "../../lib/api";
import { AlertCircle, Download, FileCheck, Loader2, Shield } from "lucide-react";

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
  onSelectFinding: (finding: ApiFinding) => void;
  /** When false (e.g. viewer role), hide/disable write actions like Run Checks. */
  canEdit?: boolean;
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
  onSelectFinding,
  canEdit = true,
}: CaseOverviewTabProps) {
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
            {caseData.deadline && (
              <div>
                <span className="text-slate-600 dark:text-slate-400">Frist:</span>
                <p className="font-medium">{new Date(caseData.deadline).toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" })}</p>
                {(() => {
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
            )}
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
                <div className="flex justify-end gap-2">
                  <Button variant="outline" onClick={() => setRunChecksOpen(false)}>Abbrechen</Button>
                  <Button onClick={onRunChecks} disabled={!selectedPlaybookId || runChecksLoading}>
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
                  <AlertCircle className="size-5 text-red-600 dark:text-red-400 mt-0.5" />
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
    </div>
  );
}
