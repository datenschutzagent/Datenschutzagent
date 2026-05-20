import { useState } from "react";
import { Loader2 } from "lucide-react";
import { Alert, AlertDescription } from "../ui/alert";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../ui/card";
import { getDsfaScreening, type DsfaScreeningResult } from "../../lib/api/cases";

const RISK_LEVEL_COLORS: Record<string, string> = {
  low: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
  medium: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300",
  high: "bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300",
  critical: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300",
};

interface Props {
  caseId: string;
  /** When provided, container wraps with mt-6 (used in DSB-Report tab). */
  className?: string;
}

/**
 * EDSA 9-Faktoren-Test ohne LLM-Kosten. Aufrufer entscheidet, wo die Karte
 * gerendert wird (DSB-Report-Tab oder DSFA-Tab).
 */
export function DsfaScreeningCard({ caseId, className }: Props) {
  const [result, setResult] = useState<DsfaScreeningResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function runScreening() {
    setLoading(true);
    setError(null);
    try {
      const data = await getDsfaScreening(caseId);
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card className={className}>
      <CardHeader className="flex flex-row items-start justify-between gap-4 pb-3">
        <div>
          <CardTitle className="text-base">DSFA-Screening (Art. 35 DSGVO)</CardTitle>
          <CardDescription>
            Automatische Prüfung ob eine Datenschutz-Folgenabschätzung erforderlich ist (EDSA 9-Faktoren-Test)
          </CardDescription>
        </div>
        <Button size="sm" variant="outline" onClick={runScreening} disabled={loading}>
          {loading ? <Loader2 className="size-4 animate-spin mr-1" /> : null}
          {loading ? "Prüfe…" : result ? "Neu prüfen" : "Screening starten"}
        </Button>
      </CardHeader>
      <CardContent>
        {error && (
          <Alert variant="destructive" className="mb-4">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        {!result && !loading && (
          <p className="text-sm text-muted-foreground">
            Das Screening analysiert 9 Risikofaktoren und gibt eine Empfehlung ohne LLM-Kosten.
          </p>
        )}
        {result && (
          <div className="space-y-4">
            <div className="flex items-center gap-3">
              <Badge className={result.required ? RISK_LEVEL_COLORS.high : RISK_LEVEL_COLORS.low}>
                {result.required ? "DSFA erforderlich" : "DSFA nicht verpflichtend"}
              </Badge>
              <span className="text-sm text-muted-foreground">
                Score: {result.score}/{result.factors.length} Faktoren zutreffend
                (Schwelle: {result.threshold})
              </span>
            </div>
            <p className="text-sm">{result.recommendation}</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {result.factors.map((f) => (
                <div
                  key={f.id}
                  className={`flex items-start gap-2 p-2 rounded text-xs border ${
                    f.met
                      ? "border-orange-200 bg-orange-50 dark:border-orange-800 dark:bg-orange-900/20"
                      : "border-slate-200 bg-slate-50 dark:border-slate-700 dark:bg-slate-800/30"
                  }`}
                >
                  <span className={`mt-0.5 shrink-0 ${f.met ? "text-orange-600" : "text-slate-400"}`}>
                    {f.met ? "●" : "○"}
                  </span>
                  <div>
                    <p className={`font-medium ${f.met ? "text-orange-800 dark:text-orange-300" : "text-slate-600 dark:text-slate-400"}`}>
                      {f.label}
                    </p>
                    <p className="text-slate-500 dark:text-slate-500">{f.description}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
