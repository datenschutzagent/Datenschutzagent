import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../ui/card";
import { Badge } from "../ui/badge";
import { CircleAlert, CheckCircle2, Shield, XCircle } from "lucide-react";
import { findingStatusLabels, severityColors } from "../../lib/mock-data";
import type { ApiCase, ApiFinding } from "../../lib/api";

export interface CaseFindingsTabProps {
  caseData: ApiCase;
  onSelectFinding: (finding: ApiFinding) => void;
}

export function CaseFindingsTab({ caseData, onSelectFinding }: CaseFindingsTabProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Findings</CardTitle>
        <CardDescription>Alle Prüfergebnisse aus Playbook-Checks</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {caseData.findings.map((finding) => (
            <div
              key={finding.id}
              className="p-4 border border-border rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800/50 cursor-pointer transition-colors"
              onClick={() => onSelectFinding(finding)}
            >
              <div className="flex items-start gap-3">
                {finding.status === "open" && <CircleAlert className="size-5 text-red-600 dark:text-red-400 mt-0.5" />}
                {finding.status === "fixed" && <CheckCircle2 className="size-5 text-green-600 dark:text-green-400 mt-0.5" />}
                {finding.status === "accepted" && <Shield className="size-5 text-blue-600 dark:text-blue-400 mt-0.5" />}
                {finding.status === "overruled" && <XCircle className="size-5 text-slate-600 dark:text-slate-400 mt-0.5" />}
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-2">
                    <h4 className="font-medium text-slate-900 dark:text-slate-100">{finding.checkName}</h4>
                    <Badge className={severityColors[finding.severity]}>
                      {finding.severity}
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
                  <p className="text-sm text-slate-600 dark:text-slate-400 mb-2">{finding.description}</p>
                  <p className="text-sm text-blue-600 dark:text-blue-400 font-medium mb-1">{finding.recommendation}</p>
                  <div className="text-xs text-slate-500 dark:text-slate-400">
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
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
