import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { AlertTriangle, CheckCircle2, FileText, Loader2, Lock, ShieldAlert } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "../ui/alert";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "../ui/alert-dialog";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../ui/card";
import { Input } from "../ui/input";
import { Label } from "../ui/label";

import {
  finalizeDsfa,
  generateDsfa,
  getDsfa,
  getDsfaJobStatus,
  type ApiCase,
  type DsfaPayload,
  type DsfaResponse,
} from "../../lib/api/cases";
import { useAuthOptional } from "../../contexts/AuthContext";
import { RiskMatrix2D, type DsfaRisk } from "../risk-matrix-2d";
import { ConfidenceBadge } from "../ui/confidence-badge";
import { DsfaScreeningCard } from "./DsfaScreeningCard";
import { RiskMitigationPanel } from "./risk-mitigation-panel";

const RISK_LEVEL_LABEL: Record<string, string> = {
  low: "Niedrig",
  medium: "Mittel",
  high: "Hoch",
  critical: "Kritisch",
};

const RISK_LEVEL_COLORS: Record<string, string> = {
  low: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300",
  medium: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300",
  high: "bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300",
  critical: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300",
};

interface Props {
  caseData: ApiCase;
  canEdit: boolean;
}

export function CaseDsfaTab({ caseData, canEdit }: Props) {
  const auth = useAuthOptional();
  const [dsfa, setDsfa] = useState<DsfaResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);

  const [finalizeOpen, setFinalizeOpen] = useState(false);
  const [finalizing, setFinalizing] = useState(false);
  const [finalizedBy, setFinalizedBy] = useState("");

  const pollHandle = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (pollHandle.current !== null) {
      clearInterval(pollHandle.current);
      pollHandle.current = null;
    }
  }, []);

  const loadDsfa = useCallback(async () => {
    try {
      const data = await getDsfa(caseData.id);
      setDsfa(data);
      setError(null);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      // 404 = noch keine DSFA — kein Fehlerstatus.
      if (/not found|404|Keine DSFA/i.test(msg)) {
        setDsfa(null);
      } else {
        setError(msg);
      }
    }
  }, [caseData.id]);

  // Auto-Load on mount + cleanup polling on unmount.
  useEffect(() => {
    setLoading(true);
    loadDsfa().finally(() => setLoading(false));
    return () => stopPolling();
  }, [loadDsfa, stopPolling]);

  // Pre-fill finalize-by with current user display name.
  useEffect(() => {
    if (auth?.user?.display_name) {
      setFinalizedBy(auth.user.display_name);
    }
  }, [auth?.user?.display_name]);

  async function handleGenerate() {
    if (generating) return;
    setGenerating(true);
    setError(null);
    try {
      await generateDsfa(caseData.id);
      toast.info("DSFA wird generiert. Das kann eine Minute dauern.");
      // Polling alle 2 Sekunden, max ~5 Minuten.
      let attempts = 0;
      pollHandle.current = setInterval(async () => {
        attempts += 1;
        try {
          const status = await getDsfaJobStatus(caseData.id);
          if (status.status === "completed") {
            stopPolling();
            await loadDsfa();
            setGenerating(false);
            toast.success("DSFA erfolgreich generiert.");
          } else if (status.status === "failed") {
            stopPolling();
            setGenerating(false);
            const msg = status.error ?? "Unbekannter Fehler";
            setError(`Generierung fehlgeschlagen: ${msg}`);
            toast.error(`DSFA-Generierung fehlgeschlagen: ${msg}`);
          } else if (attempts > 150) {
            // Safety cutoff after 5 min.
            stopPolling();
            setGenerating(false);
            setError("Generierung dauert zu lange. Bitte später erneut versuchen.");
          }
        } catch (err) {
          stopPolling();
          setGenerating(false);
          setError(err instanceof Error ? err.message : String(err));
        }
      }, 2000);
    } catch (err) {
      setGenerating(false);
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
      toast.error(`DSFA konnte nicht gestartet werden: ${msg}`);
    }
  }

  async function handleFinalize() {
    if (!finalizedBy.trim()) return;
    setFinalizing(true);
    try {
      const updated = await finalizeDsfa(caseData.id, finalizedBy.trim());
      setDsfa(updated);
      setFinalizeOpen(false);
      toast.success("DSFA finalisiert.");
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      toast.error(`Finalisierung fehlgeschlagen: ${msg}`);
    } finally {
      setFinalizing(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16 text-muted-foreground">
        <Loader2 className="size-5 animate-spin mr-2" /> Lade DSFA…
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {error && (
        <Alert variant="destructive">
          <AlertTriangle className="size-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Screening immer oben — Auslöser für ggf. eine Generierung. */}
      <DsfaScreeningCard caseId={caseData.id} />

      {/* Status-Header + Generate-Button */}
      <Card>
        <CardHeader className="flex flex-row items-start justify-between gap-4">
          <div>
            <CardTitle className="text-base flex items-center gap-2">
              <FileText className="size-4" /> DSFA-Bewertung (Art. 35 DSGVO)
            </CardTitle>
            <CardDescription>
              Vollständige Datenschutz-Folgenabschätzung mit LLM-Unterstützung. Bewertungen
              werden gegen die org-spezifische Risk-Matrix abgeglichen.
            </CardDescription>
          </div>
          {canEdit && (
            <Button
              onClick={() => void handleGenerate()}
              disabled={generating || (dsfa?.status === "finalized")}
              size="sm"
            >
              {generating ? <Loader2 className="size-4 animate-spin mr-1" /> : null}
              {generating ? "Generiere…" : dsfa ? "Neu generieren" : "DSFA generieren"}
            </Button>
          )}
        </CardHeader>
        <CardContent>
          {!dsfa && !generating && (
            <p className="text-sm text-muted-foreground">
              Es wurde noch keine DSFA für diesen Vorgang generiert.
              {canEdit
                ? " Klicken Sie auf „DSFA generieren“, um den LLM-gestützten Workflow zu starten."
                : " Bitte einen Editor/Admin um die Generierung."}
            </p>
          )}
          {generating && (
            <p className="text-sm text-muted-foreground">
              DSFA wird generiert. Die Karte aktualisiert sich automatisch, sobald der Job abgeschlossen ist.
            </p>
          )}
          {dsfa && <DsfaResult dsfa={dsfa} caseId={caseData.id} />}
        </CardContent>
      </Card>

      {dsfa && canEdit && dsfa.status === "draft" && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Lock className="size-4" /> DSFA finalisieren
            </CardTitle>
            <CardDescription>
              Nach der Finalisierung ist die DSFA nicht mehr bearbeitbar. Es wird ein Audit-Eintrag erzeugt.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button variant="default" onClick={() => setFinalizeOpen(true)}>
              <Lock className="size-4 mr-1" /> DSFA finalisieren…
            </Button>
          </CardContent>
        </Card>
      )}

      <AlertDialog open={finalizeOpen} onOpenChange={setFinalizeOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>DSFA wirklich finalisieren?</AlertDialogTitle>
            <AlertDialogDescription>
              Eine finalisierte DSFA kann nicht mehr bearbeitet werden. Bitte tragen Sie ein, wer die Finalisierung vornimmt.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <div className="space-y-2 my-3">
            <Label htmlFor="finalized-by">Finalisiert durch</Label>
            <Input
              id="finalized-by"
              value={finalizedBy}
              onChange={(e) => setFinalizedBy(e.target.value)}
              placeholder="Name oder E-Mail"
            />
          </div>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={finalizing}>Abbrechen</AlertDialogCancel>
            <AlertDialogAction
              onClick={(e) => {
                e.preventDefault();
                void handleFinalize();
              }}
              disabled={finalizing || !finalizedBy.trim()}
            >
              {finalizing ? <Loader2 className="size-4 animate-spin mr-1" /> : null}
              Finalisieren
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function DsfaResult({ dsfa, caseId }: { dsfa: DsfaResponse; caseId: string }) {
  const payload: DsfaPayload = dsfa.payload;
  const risks = payload.risks ?? [];
  const generatedAt = new Date(dsfa.generated_at).toLocaleString("de-DE");
  const finalizedAt = dsfa.finalized_at ? new Date(dsfa.finalized_at).toLocaleString("de-DE") : null;
  const confidencePct =
    typeof payload.confidence === "number" ? Math.round(payload.confidence * 100) : null;

  return (
    <div className="space-y-6">
      {/* Status-Header */}
      <div className="flex flex-wrap items-center gap-3">
        <Badge
          className={
            dsfa.status === "finalized"
              ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300"
              : "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300"
          }
        >
          {dsfa.status === "finalized" ? "Finalisiert" : "Entwurf"}
        </Badge>
        <span className="text-xs text-muted-foreground">Erstellt: {generatedAt}</span>
        {finalizedAt && (
          <span className="text-xs text-muted-foreground">
            Finalisiert: {finalizedAt} {dsfa.finalized_by ? `von ${dsfa.finalized_by}` : ""}
          </span>
        )}
        {payload.low_confidence === true && (
          <span
            className="text-xs px-2 py-1 rounded-full font-medium bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300 inline-flex items-center gap-1"
            title={
              "Selbsteinschätzung des LLM: " +
              (confidencePct !== null ? `${confidencePct}%` : "niedrig") +
              ". Bitte Bewertung manuell prüfen."
            }
          >
            <ShieldAlert className="size-3" /> Niedrige Konfidenz
          </span>
        )}
        <ConfidenceBadge source={payload.source} confidence={payload.confidence} />
      </div>

      {/* Rule-based / hybrid fallback banner */}
      {(payload.source === "rules" || payload.source === "hybrid") && (
        <Alert>
          <ShieldAlert className="size-4" />
          <AlertTitle>
            {payload.source === "rules"
              ? "Regelbasierter Fallback aktiv"
              : "Hybrid-Bewertung (LLM + Regeln)"}
          </AlertTitle>
          <AlertDescription>
            {payload.source === "rules"
              ? "Diese DSFA wurde regelbasiert erzeugt — vermutlich war das LLM nicht verfügbar oder die Konfidenz lag unter der konfigurierten Schwelle. Eine manuelle Validierung wird empfohlen; bei Verfügbarkeit des LLM kann die DSFA neu generiert werden."
              : "Die LLM-Konfidenz war unter der Schwelle, deshalb wurden die Risiken aus den Heuristiken übernommen. Bitte vor Finalisierung prüfen."}
          </AlertDescription>
        </Alert>
      )}

      {/* DPO-Konsultation */}
      {payload.dpo_consultation_required && (
        <Alert variant="destructive">
          <AlertTriangle className="size-4" />
          <AlertTitle>DSB-Konsultation erforderlich (Art. 36 DSGVO)</AlertTitle>
          <AlertDescription>
            Das Residualrisiko ist hoch genug, dass die zuständige Aufsichtsbehörde
            konsultiert werden muss, bevor mit der Verarbeitung begonnen wird.
          </AlertDescription>
        </Alert>
      )}

      {/* Notwendigkeit + Verhältnismäßigkeit */}
      <div className="grid md:grid-cols-2 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Notwendigkeit</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm whitespace-pre-line">{payload.necessity_assessment}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Verhältnismäßigkeit</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm whitespace-pre-line">{payload.proportionality_assessment}</p>
          </CardContent>
        </Card>
      </div>

      {/* Risiken-Liste */}
      {risks.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-sm font-medium">Identifizierte Risiken ({risks.length})</h4>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-muted-foreground text-left border-b">
                  <th className="py-2 pr-3 font-medium">Beschreibung</th>
                  <th className="py-2 pr-3 font-medium">Likelihood</th>
                  <th className="py-2 pr-3 font-medium">Severity</th>
                  <th className="py-2 pr-3 font-medium">Risk-Level</th>
                  <th className="py-2 pr-3 font-medium">Mitigation</th>
                </tr>
              </thead>
              <tbody>
                {risks.map((r, idx) => {
                  const lik = r.likelihood_score ?? null;
                  const sev = r.severity_score ?? null;
                  const level = r.risk_level ?? r.severity;
                  return (
                    <tr key={idx} className="border-b last:border-0 align-top">
                      <td className="py-2 pr-3 max-w-md">{r.description}</td>
                      <td className="py-2 pr-3 whitespace-nowrap">
                        {lik !== null ? `${lik} (${r.likelihood})` : r.likelihood}
                      </td>
                      <td className="py-2 pr-3 whitespace-nowrap">
                        {sev !== null ? `${sev} (${r.severity})` : r.severity}
                      </td>
                      <td className="py-2 pr-3">
                        <span
                          className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                            RISK_LEVEL_COLORS[level] ?? ""
                          }`}
                        >
                          {RISK_LEVEL_LABEL[level] ?? level}
                        </span>
                      </td>
                      <td className="py-2 pr-3 text-muted-foreground">{r.mitigation}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Risk-Matrix (Größe 3/5/7) — zeigt residual + (gestrichelt) inherent */}
      {risks.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-sm font-medium">Risk-Matrix (ISO 27005)</h4>
          <RiskMatrix2D
            risks={risks as DsfaRisk[]}
            inherentRisks={(payload.inherent_risks ?? []) as DsfaRisk[]}
            size={(payload.scale_size as 3 | 5 | 7 | undefined) ?? 5}
            matrix={payload.matrix ?? undefined}
            likelihoodLabels={
              payload.scale_labels?.likelihood
                ? Object.fromEntries(
                    Object.entries(payload.scale_labels.likelihood).map(([k, v]) => [Number(k), v]),
                  )
                : undefined
            }
            severityLabels={
              payload.scale_labels?.severity
                ? Object.fromEntries(
                    Object.entries(payload.scale_labels.severity).map(([k, v]) => [Number(k), v]),
                  )
                : undefined
            }
          />
        </div>
      )}

      {/* Residualrisiko + Inherent-Vergleich */}
      <div className="flex flex-wrap items-center gap-2 text-sm">
        {payload.inherent_residual_risk && payload.inherent_residual_risk !== payload.residual_risk && (
          <>
            <span className="font-medium">Inherent:</span>
            <span
              className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                RISK_LEVEL_COLORS[payload.inherent_residual_risk] ?? ""
              }`}
            >
              {RISK_LEVEL_LABEL[payload.inherent_residual_risk] ?? payload.inherent_residual_risk}
            </span>
            <span className="text-muted-foreground">→</span>
          </>
        )}
        <span className="font-medium">Residualrisiko:</span>
        <span
          className={`text-xs px-2 py-0.5 rounded-full font-medium ${
            RISK_LEVEL_COLORS[payload.residual_risk] ?? ""
          }`}
        >
          {RISK_LEVEL_LABEL[payload.residual_risk] ?? payload.residual_risk}
        </span>
      </div>

      {/* Mitigation-Panel: TOM-Verknüpfungen und Risk-Reduktion */}
      <RiskMitigationPanel target={{ kind: "case", id: caseId }} />

      {/* Maßnahmen */}
      {payload.measures.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <CheckCircle2 className="size-4" /> Geplante Maßnahmen ({payload.measures.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="text-sm space-y-1 list-disc list-inside">
              {payload.measures.map((m, i) => (
                <li key={i}>{m}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
