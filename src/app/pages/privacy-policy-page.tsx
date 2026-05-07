import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router";
import { AppLayout } from "../components/app-layout";
import { PageHeader } from "../components/page-header";
import { Card, CardContent } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Input } from "../components/ui/input";
import { Skeleton } from "../components/ui/skeleton";
import {
  listPrivacyPolicies,
  getCases,
  type ApiCase,
  type ApiPrivacyPolicy,
} from "../lib/api";
import { toast } from "sonner";
import { ArrowRight, Download, FileText, Search } from "lucide-react";

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

interface CaseGroup {
  caseId: string;
  caseTitle: string;
  caseDepartment: string;
  policies: ApiPrivacyPolicy[];
}

export function PrivacyPolicyPage() {
  const [policies, setPolicies] = useState<ApiPrivacyPolicy[]>([]);
  const [cases, setCases] = useState<Record<string, ApiCase>>({});
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const [pol, caseList] = await Promise.all([
          listPrivacyPolicies(),
          getCases(0, 500, undefined, true),
        ]);
        if (cancelled) return;
        setPolicies(pol);
        const map: Record<string, ApiCase> = {};
        for (const c of caseList) map[c.id] = c;
        setCases(map);
      } catch {
        if (!cancelled) toast.error("Datenschutzerklärungen konnten nicht geladen werden.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const groups: CaseGroup[] = useMemo(() => {
    const byCase = new Map<string, CaseGroup>();
    for (const p of policies) {
      const c = cases[p.case_id];
      const group = byCase.get(p.case_id) ?? {
        caseId: p.case_id,
        caseTitle: c?.title ?? "(Vorgang gelöscht)",
        caseDepartment: c?.department ?? "",
        policies: [],
      };
      group.policies.push(p);
      byCase.set(p.case_id, group);
    }
    const list = Array.from(byCase.values());
    list.forEach((g) => g.policies.sort((a, b) => b.version - a.version));
    list.sort((a, b) => {
      const aDate = a.policies[0]?.generated_at ?? "";
      const bDate = b.policies[0]?.generated_at ?? "";
      return bDate.localeCompare(aDate);
    });
    return list;
  }, [policies, cases]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return groups;
    return groups.filter((g) => {
      if (g.caseTitle.toLowerCase().includes(q)) return true;
      if (g.caseDepartment.toLowerCase().includes(q)) return true;
      return g.policies.some((p) => p.title.toLowerCase().includes(q));
    });
  }, [groups, search]);

  const totalVersions = policies.length;

  return (
    <AppLayout>
      <div className="container mx-auto max-w-6xl py-8 px-4">
        <PageHeader
          title="Datenschutzerklärungen"
          description="Übersicht aller vorgangsspezifischen Datenschutzerklärungen. Generierung und Bearbeitung erfolgen im jeweiligen Vorgang."
        />

        <div className="flex items-center gap-3 mt-6 mb-4">
          <div className="relative flex-1 max-w-md">
            <Search className="size-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Vorgang, Abteilung oder Titel suchen…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9"
            />
          </div>
          <span className="text-sm text-muted-foreground">
            {filtered.length} {filtered.length === 1 ? "Vorgang" : "Vorgänge"} •{" "}
            {totalVersions} {totalVersions === 1 ? "Version" : "Versionen"}
          </span>
        </div>

        {loading ? (
          <div className="space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-28 w-full rounded-lg" />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <Card className="border-dashed">
            <CardContent className="py-16 text-center">
              <FileText className="size-12 mx-auto mb-4 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">
                {policies.length === 0
                  ? "Noch keine Datenschutzerklärungen erstellt."
                  : "Keine Treffer für die aktuelle Suche."}
              </p>
              {policies.length === 0 && (
                <p className="text-xs text-muted-foreground mt-2">
                  Datenschutzerklärungen werden im Tab „Datenschutzerklärung" eines Vorgangs generiert.
                </p>
              )}
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-3">
            {filtered.map((group) => {
              const latest = group.policies[0];
              return (
                <Card key={group.caseId}>
                  <CardContent className="p-4">
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <h3 className="font-semibold truncate">{group.caseTitle}</h3>
                          {group.caseDepartment && (
                            <Badge variant="outline" className="text-xs">
                              {group.caseDepartment}
                            </Badge>
                          )}
                          <Badge variant="secondary" className="text-xs">
                            {group.policies.length}{" "}
                            {group.policies.length === 1 ? "Version" : "Versionen"}
                          </Badge>
                        </div>
                        {latest && (
                          <p className="text-xs text-muted-foreground">
                            Aktuell: v{latest.version} • {latest.title} •{" "}
                            {formatDateTime(latest.generated_at)}
                          </p>
                        )}
                      </div>
                      <div className="flex gap-2 shrink-0">
                        {latest && (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => downloadMarkdown(latest)}
                            aria-label="Aktuelle Version herunterladen"
                          >
                            <Download className="size-4 mr-1" />
                            Aktuelle Version
                          </Button>
                        )}
                        {cases[group.caseId] && (
                          <Button asChild size="sm">
                            <Link to={`/cases/${group.caseId}?tab=privacy-policy`}>
                              Im Vorgang öffnen
                              <ArrowRight className="size-4 ml-1" />
                            </Link>
                          </Button>
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}
      </div>
    </AppLayout>
  );
}
