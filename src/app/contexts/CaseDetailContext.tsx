import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useParams } from "react-router";
import {
  getPlaybooks,
  getPlaybooksForSelection,
  getPlaybookCoveragePreview,
  getSimilarCases,
  getCaseRiskScore,
  runChecks,
  type ApiCase,
  type ApiPlaybook,
  type PlaybookCoverage,
  type CaseSimilarityResult,
  type CaseRiskScore,
  type RunChecksStrategy,
} from "../lib/api";
import { useRunningChecks } from "./RunningChecksContext";

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
  handleRunChecks: () => Promise<void>;
}

const CaseDetailContext = createContext<CaseDetailContextValue | null>(null);

export function useCaseDetail(): CaseDetailContextValue {
  const ctx = useContext(CaseDetailContext);
  if (!ctx) throw new Error("useCaseDetail must be used inside CaseDetailProvider");
  return ctx;
}

interface CaseDetailProviderProps {
  caseData: ApiCase | null;
  onReloadCase: () => void;
  children: ReactNode;
}

export function CaseDetailProvider({ caseData, onReloadCase, children }: CaseDetailProviderProps) {
  const { caseId } = useParams<{ caseId: string }>();
  const { registerJob, getJob } = useRunningChecks();

  const [runChecksOpen, setRunChecksOpen] = useState(false);
  const [playbooks, setPlaybooks] = useState<ApiPlaybook[]>([]);
  const [selectedPlaybookId, setSelectedPlaybookId] = useState("");
  const [runChecksStrategy, setRunChecksStrategy] = useState<"full_text" | "rag" | "both">("full_text");
  const [runChecksLoading, setRunChecksLoading] = useState(false);
  const [runChecksError, setRunChecksError] = useState<string | null>(null);
  const [coveragePreview, setCoveragePreview] = useState<PlaybookCoverage | null>(null);
  const [similarCases, setSimilarCases] = useState<CaseSimilarityResult[]>([]);
  const [riskScore, setRiskScore] = useState<CaseRiskScore | null>(null);

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

  const loadRiskScore = useCallback(() => {
    if (!caseId) return;
    getCaseRiskScore(caseId).then(setRiskScore).catch(() => {});
  }, [caseId]);

  useEffect(() => {
    loadRiskScore();
  }, [loadRiskScore]);

  useEffect(() => {
    if (!caseId) return;
    getSimilarCases(caseId).then(setSimilarCases).catch(() => {});
  }, [caseId]);

  useEffect(() => {
    if (!selectedPlaybookId || !caseId) {
      setCoveragePreview(null);
      return;
    }
    getPlaybookCoveragePreview(selectedPlaybookId, caseId)
      .then(setCoveragePreview)
      .catch(() => setCoveragePreview(null));
  }, [selectedPlaybookId, caseId]);

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

  const prevJobStatusRef = useRef<string | undefined>(undefined);
  useEffect(() => {
    const currentStatus = currentJob?.status;
    const prevStatus = prevJobStatusRef.current;
    prevJobStatusRef.current = currentStatus;

    if (prevStatus === "running" && currentStatus === "completed") {
      onReloadCase();
      loadRiskScore();
      setRunChecksOpen(false);
      setSelectedPlaybookId("");
    } else if (prevStatus === "running" && currentStatus === "failed") {
      setRunChecksError("Checks fehlgeschlagen.");
    }
  }, [currentJob?.status, loadRiskScore, onReloadCase]);

  const handleRunChecks = useCallback(async () => {
    if (!caseId || !selectedPlaybookId) return;
    setRunChecksLoading(true);
    setRunChecksError(null);
    try {
      const strategies: RunChecksStrategy[] =
        runChecksStrategy === "both" ? ["full_text", "rag"] : [runChecksStrategy];
      const result = await runChecks(caseId, selectedPlaybookId, strategies);
      if ("accepted" in result && result.accepted) {
        const selectedPb = playbooks.find((p) => p.id === selectedPlaybookId);
        registerJob(caseId, result.jobId, caseData?.title ?? "", selectedPb?.name);
      } else {
        onReloadCase();
        loadRiskScore();
        setRunChecksOpen(false);
        setSelectedPlaybookId("");
      }
    } catch (e) {
      setRunChecksError(e instanceof Error ? e.message : "Checks fehlgeschlagen.");
    } finally {
      setRunChecksLoading(false);
    }
  }, [caseId, selectedPlaybookId, runChecksStrategy, playbooks, caseData, registerJob, onReloadCase, loadRiskScore]);

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
        runChecksLoading,
        runChecksStatus,
        runChecksError,
        setRunChecksError,
        runChecksProgress,
        coveragePreview,
        similarCases,
        riskScore,
        handleRunChecks,
      }}
    >
      {children}
    </CaseDetailContext.Provider>
  );
}
