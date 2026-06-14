import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useParams } from "react-router";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getPlaybooks,
  getPlaybooksForSelection,
  getPlaybookCoveragePreview,
  runChecks,
  type ApiCase,
  type ApiPlaybook,
  type PlaybookCoverage,
  type CaseSimilarityResult,
  type CaseRiskScore,
  type RunChecksStrategy,
} from "../lib/api";
import { useRunningChecks } from "./RunningChecksContext";
import { caseDetailKeys, useCaseRiskScore, useSimilarCases } from "../lib/queries/caseDetailQueries";

interface CaseDetailContextValue {
  runChecksOpen: boolean;
  setRunChecksOpen: (open: boolean) => void;
  playbooks: ApiPlaybook[];
  selectedPlaybookId: string;
  setSelectedPlaybookId: (id: string) => void;
  runChecksStrategy: "full_text" | "rag" | "both";
  setRunChecksStrategy: (s: "full_text" | "rag" | "both") => void;
  runChecksLoading: boolean;
  runChecksStatus: "idle" | "running" | "completed" | "failed";
  runChecksError: string | null;
  setRunChecksError: (err: string | null) => void;
  runChecksProgress: { done: number; total: number };
  coveragePreview: PlaybookCoverage | null;
  similarCases: CaseSimilarityResult[];
  riskScore: CaseRiskScore | null;
  handleRunChecks: () => void;
}

const CaseDetailContext = createContext<CaseDetailContextValue | null>(null);

export function useCaseDetail(): CaseDetailContextValue {
  const ctx = useContext(CaseDetailContext);
  if (!ctx) throw new Error("useCaseDetail must be used inside CaseDetailProvider");
  return ctx;
}

interface CaseDetailProviderProps {
  caseData: ApiCase | null;
  children: ReactNode;
}

export function CaseDetailProvider({ caseData, children }: CaseDetailProviderProps) {
  const { caseId } = useParams<{ caseId: string }>();
  const { registerJob, getJob } = useRunningChecks();
  const queryClient = useQueryClient();

  const [runChecksOpen, setRunChecksOpen] = useState(false);
  const [playbooks, setPlaybooks] = useState<ApiPlaybook[]>([]);
  const [selectedPlaybookId, setSelectedPlaybookId] = useState("");
  const [runChecksStrategy, setRunChecksStrategy] = useState<"full_text" | "rag" | "both">("full_text");
  const [runChecksJobError, setRunChecksJobError] = useState<string | null>(null);

  const currentJob = caseId ? getJob(caseId) : undefined;
  const runChecksStatus: "idle" | "running" | "completed" | "failed" =
    currentJob?.status === "running"
      ? "running"
      : currentJob?.status === "failed"
        ? "failed"
        : "idle";
  const runChecksProgress = currentJob
    ? { done: currentJob.checksDone, total: currentJob.checksTotal }
    : { done: 0, total: 0 };

  const { data: riskScore = null } = useCaseRiskScore(caseId ?? "");
  const { data: similarCases = [] } = useSimilarCases(caseId ?? "");

  const { data: coveragePreview = null } = useQuery<PlaybookCoverage | null>({
    queryKey: ["playbook-coverage", selectedPlaybookId, caseId],
    queryFn: () => getPlaybookCoveragePreview(selectedPlaybookId, caseId!),
    enabled: !!selectedPlaybookId && !!caseId,
    staleTime: 30_000,
  });

  useEffect(() => {
    if (!runChecksOpen || !caseData) return;
    let cancelled = false;
    (async () => {
      try {
        const rows = await getPlaybooksForSelection({
          department: caseData.department,
          processing_context: caseData.processingContext?.trim() || undefined,
          case_type: caseData.caseType,
          strict_case_type: true,
        });
        const list = rows.map((r) => r.playbook);
        if (cancelled) return;
        if (list.length > 0) {
          setPlaybooks(list);
        } else {
          const all = await getPlaybooks();
          if (!cancelled) setPlaybooks(all);
        }
      } catch {
        if (!cancelled) {
          getPlaybooks().then(setPlaybooks).catch(() => setPlaybooks([]));
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [runChecksOpen, caseData]);

  const runChecksMutation = useMutation({
    mutationFn: ({
      caseId: id,
      playbookId,
      strategies,
    }: {
      caseId: string;
      playbookId: string;
      strategies: RunChecksStrategy[];
    }) => runChecks(id, playbookId, strategies),
    onSuccess: (result, variables) => {
      if ("accepted" in result && result.accepted) {
        const selectedPb = playbooks.find((p) => p.id === variables.playbookId);
        registerJob(variables.caseId, result.jobId, caseData?.title ?? "", selectedPb?.name);
      } else {
        void queryClient.invalidateQueries({ queryKey: caseDetailKeys.detail(variables.caseId) });
        void queryClient.invalidateQueries({ queryKey: caseDetailKeys.riskScore(variables.caseId) });
        void queryClient.invalidateQueries({ queryKey: caseDetailKeys.runChecksStatus(variables.caseId) });
        setRunChecksOpen(false);
        setSelectedPlaybookId("");
      }
    },
  });

  const prevJobStatusRef = useRef<string | undefined>(undefined);
  useEffect(() => {
    const currentStatus = currentJob?.status;
    const prevStatus = prevJobStatusRef.current;
    prevJobStatusRef.current = currentStatus;

    if (prevStatus === "running" && currentStatus === "completed") {
      if (caseId) {
        void queryClient.invalidateQueries({ queryKey: caseDetailKeys.detail(caseId) });
        void queryClient.invalidateQueries({ queryKey: caseDetailKeys.riskScore(caseId) });
        void queryClient.invalidateQueries({ queryKey: caseDetailKeys.runChecksStatus(caseId) });
      }
      setRunChecksOpen(false);
      setSelectedPlaybookId("");
    } else if (prevStatus === "running" && currentStatus === "failed") {
      setRunChecksJobError("Checks fehlgeschlagen.");
    }
  }, [currentJob?.status, caseId, queryClient]);

  const handleRunChecks = useCallback(() => {
    if (!caseId || !selectedPlaybookId) return;
    setRunChecksJobError(null);
    const strategies: RunChecksStrategy[] =
      runChecksStrategy === "both" ? ["full_text", "rag"] : [runChecksStrategy];
    runChecksMutation.mutate({ caseId, playbookId: selectedPlaybookId, strategies });
  }, [caseId, selectedPlaybookId, runChecksStrategy, runChecksMutation]);

  const runChecksError =
    runChecksJobError ??
    (runChecksMutation.isError
      ? runChecksMutation.error instanceof Error
        ? runChecksMutation.error.message
        : "Checks fehlgeschlagen."
      : null);

  const setRunChecksError = (err: string | null) => {
    setRunChecksJobError(err);
    if (!err) runChecksMutation.reset();
  };

  return (
    <CaseDetailContext.Provider
      value={{
        runChecksOpen,
        setRunChecksOpen,
        playbooks,
        selectedPlaybookId,
        setSelectedPlaybookId,
        runChecksStrategy,
        setRunChecksStrategy,
        runChecksLoading: runChecksMutation.isPending,
        runChecksStatus,
        runChecksError,
        setRunChecksError,
        runChecksProgress,
        coveragePreview: coveragePreview ?? null,
        similarCases,
        riskScore,
        handleRunChecks,
      }}
    >
      {children}
    </CaseDetailContext.Provider>
  );
}
