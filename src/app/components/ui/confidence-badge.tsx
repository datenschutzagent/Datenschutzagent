/**
 * ConfidenceBadge — visualises the LLM self-reported confidence on risk
 * assessments, plus the provenance of the underlying numbers (LLM,
 * rule-based fallback, or hybrid).
 *
 * Used on the DSFA tab and AVV detail view. Backend supplies:
 *   - source: 'llm' | 'rules' | 'hybrid'
 *   - confidence: 0..1
 */
import { Badge } from "./badge";

type Source = "llm" | "rules" | "hybrid" | null | undefined;

type Props = {
  source: Source;
  /** LLM self-reported confidence on [0, 1]. */
  confidence: number | null | undefined;
  /** Pull threshold so the badge highlights itself when the LLM confidence
   * dropped below the configured low_threshold. Defaults to 0.6 to match
   * the YAML default. */
  lowThreshold?: number;
};

const SOURCE_LABEL: Record<NonNullable<Source>, string> = {
  llm: "LLM-Bewertung",
  rules: "Regelbasiert",
  hybrid: "Hybrid (LLM + Regeln)",
};

export function ConfidenceBadge({ source, confidence, lowThreshold = 0.6 }: Props) {
  if (!source && (confidence === null || confidence === undefined)) return null;

  const pct = typeof confidence === "number" ? Math.round(confidence * 100) : null;
  const isLowConfidence = typeof confidence === "number" && confidence < lowThreshold;

  const variant: "secondary" | "default" | "destructive" | "outline" =
    source === "rules"
      ? "destructive"
      : source === "hybrid"
        ? "default"
        : isLowConfidence
          ? "default"
          : "secondary";

  const tone =
    source === "rules"
      ? "border-destructive/40"
      : source === "hybrid"
        ? "border-primary/40"
        : "";

  return (
    <Badge
      variant={variant}
      className={tone}
      title={
        source === "rules"
          ? "LLM nicht verfügbar oder unter Schwelle — regelbasierter Heuristik-Fallback."
          : source === "hybrid"
            ? "LLM-Ergebnis war unter der Konfidenz-Schwelle; Heuristik wurde herangezogen."
            : isLowConfidence
              ? "LLM-Selbsteinschätzung niedrig — Ergebnis bitte manuell prüfen."
              : "Klassische LLM-Bewertung."
      }
    >
      <span>{source ? SOURCE_LABEL[source] : "Konfidenz"}</span>
      {pct !== null && <span className="ml-1 opacity-80">· {pct}%</span>}
    </Badge>
  );
}
