import { useState, useMemo } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../ui/card";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Checkbox } from "../ui/checkbox";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../ui/select";
import { CircleAlert, CheckCircle2, Shield, XCircle, ShieldAlert, AlertTriangle, AlertCircle, Info, Download, Loader2 } from "lucide-react";
import { findingStatusLabels, severityColors, severityLabels } from "../../lib/mock-data";
import type { FindingSeverity } from "../../lib/mock-data";
import {
  bulkUpdateFindingStatus,
  downloadFindingsExport,
  downloadBlob,
  type ApiCase,
  type ApiFinding,
  type FindingStatus,
} from "../../lib/api";
import { toast } from "sonner";

function SeverityIcon({ severity }: { severity: FindingSeverity }) {
  switch (severity) {
    case "critical": return <ShieldAlert className="size-3.5" />;
    case "high": return <AlertTriangle className="size-3.5" />;
    case "medium": return <AlertCircle className="size-3.5" />;
    case "low": return <Info className="size-3.5" />;
    case "info": return <Info className="size-3.5" />;
  }
}

export interface CaseFindingsTabProps {
  caseData: ApiCase;
  onSelectFinding: (finding: ApiFinding) => void;
  onFindingsChanged?: () => void;
}

export function CaseFindingsTab({ caseData, onSelectFinding, onFindingsChanged }: CaseFindingsTabProps) {
  const [severityFilter, setSeverityFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [bulkStatus, setBulkStatus] = useState<FindingStatus>("accepted");
  const [bulkLoading, setBulkLoading] = useState(false);
  const [exportLoading, setExportLoading] = useState(false);

  const filtered = useMemo(() => {
    return caseData.findings.filter((f) => {
      if (severityFilter !== "all" && f.severity !== severityFilter) return false;
      if (statusFilter !== "all" && f.status !== statusFilter) return false;
      return true;
    });
  }, [caseData.findings, severityFilter, statusFilter]);

  const allSelected = filtered.length > 0 && filtered.every((f) => selectedIds.has(f.id));
  const someSelected = selectedIds.size > 0;

  const toggleSelectAll = () => {
    if (allSelected) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(filtered.map((f) => f.id)));
    }
  };

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const handleBulkUpdate = async () => {
    if (selectedIds.size === 0) return;
    setBulkLoading(true);
    try {
      const result = await bulkUpdateFindingStatus(Array.from(selectedIds), bulkStatus);
      toast.success(`${result.updated} Findings aktualisiert`);
      setSelectedIds(new Set());
      onFindingsChanged?.();
    } catch {
      toast.error("Fehler beim Aktualisieren der Findings");
    } finally {
      setBulkLoading(false);
    }
  };

  const handleExport = async (format: "csv" | "docx" = "csv") => {
    setExportLoading(true);
    try {
      const blob = await downloadFindingsExport(caseData.id, {
        severity: severityFilter !== "all" ? severityFilter : undefined,
        status: statusFilter !== "all" ? statusFilter : undefined,
        format,
      });
      const date = new Date().toISOString().slice(0, 10);
      const slug = caseData.title.replace(/[^\w\s-]/g, "").slice(0, 40).trim().replace(/[-\s]+/g, "-") || "Befunde";
      downloadBlob(blob, `Befunde-${slug}-${date}.${format}`);
    } catch {
      toast.error("Export fehlgeschlagen");
    } finally {
      setExportLoading(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <CardTitle>Findings</CardTitle>
            <CardDescription>
              {filtered.length} von {caseData.findings.length} Prüfergebnissen
            </CardDescription>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            {/* Severity filter */}
            <Select value={severityFilter} onValueChange={(v) => { setSeverityFilter(v); setSelectedIds(new Set()); }}>
              <SelectTrigger className="w-36">
                <SelectValue placeholder="Schweregrad" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Alle Schweregrade</SelectItem>
                <SelectItem value="critical">Kritisch</SelectItem>
                <SelectItem value="high">Hoch</SelectItem>
                <SelectItem value="medium">Mittel</SelectItem>
                <SelectItem value="low">Niedrig</SelectItem>
                <SelectItem value="info">Info</SelectItem>
              </SelectContent>
            </Select>
            {/* Status filter */}
            <Select value={statusFilter} onValueChange={(v) => { setStatusFilter(v); setSelectedIds(new Set()); }}>
              <SelectTrigger className="w-36">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Alle Status</SelectItem>
                <SelectItem value="open">Offen</SelectItem>
                <SelectItem value="accepted">Akzeptiert</SelectItem>
                <SelectItem value="overruled">Überfahren</SelectItem>
                <SelectItem value="fixed">Behoben</SelectItem>
              </SelectContent>
            </Select>
            {/* Export buttons */}
            <Button variant="outline" size="sm" className="gap-1.5" onClick={() => handleExport("csv")} disabled={exportLoading || caseData.findings.length === 0}>
              {exportLoading ? <Loader2 className="size-4 animate-spin" /> : <Download className="size-4" />}
              CSV
            </Button>
            <Button variant="outline" size="sm" className="gap-1.5" onClick={() => handleExport("docx")} disabled={exportLoading || caseData.findings.length === 0}>
              <Download className="size-4" />
              DOCX
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {/* Bulk action bar */}
        {someSelected && (
          <div className="flex items-center gap-3 mb-4 p-3 bg-muted/60 rounded-lg border border-border">
            <span className="text-sm font-medium">{selectedIds.size} ausgewählt</span>
            <Select value={bulkStatus} onValueChange={(v) => setBulkStatus(v as FindingStatus)}>
              <SelectTrigger className="w-40">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="accepted">Akzeptieren</SelectItem>
                <SelectItem value="overruled">Überfahren</SelectItem>
                <SelectItem value="fixed">Als behoben markieren</SelectItem>
                <SelectItem value="open">Auf offen setzen</SelectItem>
              </SelectContent>
            </Select>
            <Button size="sm" onClick={handleBulkUpdate} disabled={bulkLoading}>
              {bulkLoading ? <Loader2 className="size-4 animate-spin mr-1" /> : null}
              Anwenden
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setSelectedIds(new Set())}>
              Abbrechen
            </Button>
          </div>
        )}

        <div className="space-y-3">
          {/* Select-all header row */}
          {filtered.length > 0 && (
            <div className="flex items-center gap-3 px-1 pb-1">
              <Checkbox
                checked={allSelected}
                onCheckedChange={toggleSelectAll}
                aria-label="Alle auswählen"
              />
              <span className="text-xs text-muted-foreground">Alle auswählen</span>
            </div>
          )}

          {filtered.length === 0 && (
            <p className="text-sm text-muted-foreground py-4 text-center">
              Keine Findings für die gewählten Filter.
            </p>
          )}

          {filtered.map((finding) => (
            <div
              key={finding.id}
              className={`p-4 border rounded-lg transition-colors ${
                selectedIds.has(finding.id)
                  ? "border-primary/50 bg-primary/5"
                  : "border-border hover:bg-muted/50"
              }`}
            >
              <div className="flex items-start gap-3">
                <div className="mt-0.5 shrink-0" onClick={(e) => e.stopPropagation()}>
                  <Checkbox
                    checked={selectedIds.has(finding.id)}
                    onCheckedChange={() => toggleSelect(finding.id)}
                    aria-label={`Finding auswählen: ${finding.checkName}`}
                  />
                </div>
                <div
                  className="flex items-start gap-3 flex-1 cursor-pointer"
                  onClick={() => onSelectFinding(finding)}
                >
                  {finding.status === "open" && <CircleAlert className="size-5 text-red-600 dark:text-red-400 mt-0.5 shrink-0" />}
                  {finding.status === "fixed" && <CheckCircle2 className="size-5 text-green-600 dark:text-green-400 mt-0.5 shrink-0" />}
                  {finding.status === "accepted" && <Shield className="size-5 text-blue-600 dark:text-blue-400 mt-0.5 shrink-0" />}
                  {finding.status === "overruled" && <XCircle className="size-5 text-slate-600 dark:text-slate-400 mt-0.5 shrink-0" />}
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2 flex-wrap">
                      <h4 className="font-medium text-foreground">{finding.checkName}</h4>
                      <Badge className={`${severityColors[finding.severity as FindingSeverity]} flex items-center gap-1`}>
                        <SeverityIcon severity={finding.severity as FindingSeverity} />
                        {severityLabels[finding.severity as FindingSeverity]}
                      </Badge>
                      <Badge variant="outline">{findingStatusLabels[finding.status]}</Badge>
                      <Badge variant="outline" className="text-xs">
                        {finding.category}
                      </Badge>
                      {!finding.documentId && (
                        <Badge variant="secondary" className="text-xs">Vorgangsbezogen</Badge>
                      )}
                      {finding.sourceStrategy === "rag" && (
                        <Badge variant="secondary" className="text-xs bg-purple-100 text-purple-800 dark:bg-purple-900/50 dark:text-purple-300">RAG</Badge>
                      )}
                      {finding.sourceStrategy === "full_text" && (
                        <Badge variant="outline" className="text-xs">Volltext</Badge>
                      )}
                    </div>
                    <p className="text-sm text-muted-foreground mb-2">{finding.description}</p>
                    <p className="text-sm text-blue-600 dark:text-blue-400 font-medium mb-1">{finding.recommendation}</p>
                    <div className="text-xs text-muted-foreground">
                      <strong>Evidenzen:</strong>
                      <ul className="mt-1 ml-4 list-disc">
                        {finding.evidence.map((ev, i) => (
                          <li key={i}>{ev}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
