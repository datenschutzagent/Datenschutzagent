/**
 * Global context that tracks running playbook check jobs across the application.
 *
 * - Polls GET /cases/running-checks every 3 seconds while jobs are active.
 * - On initial mount, fetches once to discover jobs already running (e.g. after page refresh).
 * - Fires toast notifications when jobs complete or fail.
 * - Provides helpers so any component can query running state without extra API calls.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getRunningChecks, type RunningCheckJob } from "../lib/api";
import { toast } from "sonner";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface RunChecksContextValue {
  /** All currently tracked jobs (running + briefly retained completed/failed). */
  jobs: RunningCheckJob[];
  /** Register a newly started job (called after POST /run-checks returns 202). */
  registerJob(caseId: string, jobId: string, caseTitle: string, playbookName?: string): void;
  /** True if the given case currently has a running check job. */
  isRunning(caseId: string): boolean;
  /** Get the tracked job for a specific case (if any). */
  getJob(caseId: string): RunningCheckJob | undefined;
  /** Manually dismiss a completed/failed job from the banner. */
  dismissJob(caseId: string): void;
  /** Number of jobs with status "running". */
  runningCount: number;
}

const RunningChecksContext = createContext<RunChecksContextValue | null>(null);

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

const POLL_INTERVAL_MS = 3_000;

export function RunningChecksProvider({ children }: { children: React.ReactNode }) {
  const [jobs, setJobs] = useState<Map<string, RunningCheckJob>>(new Map());
  const prevStatusRef = useRef<Map<string, string>>(new Map());

  const runningCount = Array.from(jobs.values()).filter((j) => j.status === "running").length;

  // -- React Query polling ---------------------------------------------------

  const { data: serverJobs = [] } = useQuery({
    queryKey: ["running-checks"],
    queryFn: getRunningChecks,
    refetchInterval: runningCount > 0 ? POLL_INTERVAL_MS : false,
    staleTime: 0,
    refetchOnWindowFocus: false,
  });

  // Merge server jobs into the local jobs Map whenever a poll completes
  useEffect(() => {
    setJobs((prev) => {
      let changed = false;
      const next = new Map(prev);
      const seenCaseIds = new Set<string>();

      for (const job of serverJobs) {
        seenCaseIds.add(job.caseId);
        const existing = prev.get(job.caseId);
        if (!existing || existing.status !== job.status || existing.checksDone !== job.checksDone) {
          next.set(job.caseId, job);
          changed = true;
        }
      }

      // Jobs that were "running" locally but are no longer on the server have completed
      for (const [caseId, prevJob] of prev) {
        if (prevJob.status === "running" && !seenCaseIds.has(caseId)) {
          next.set(caseId, { ...prevJob, status: "completed" });
          changed = true;
        }
      }

      return changed ? next : prev;
    });
  }, [serverJobs]);

  // -- helpers ---------------------------------------------------------------

  const registerJob = useCallback(
    (caseId: string, jobId: string, caseTitle: string, playbookName?: string) => {
      setJobs((prev) => {
        const next = new Map(prev);
        next.set(caseId, {
          jobId,
          caseId,
          caseTitle,
          playbookName: playbookName ?? null,
          status: "running",
          checksDone: 0,
          checksTotal: 0,
          createdAt: new Date().toISOString(),
        });
        return next;
      });
    },
    [],
  );

  const isRunning = useCallback(
    (caseId: string) => {
      const job = jobs.get(caseId);
      return job?.status === "running";
    },
    [jobs],
  );

  const getJob = useCallback((caseId: string) => jobs.get(caseId), [jobs]);

  const dismissJob = useCallback(
    (caseId: string) => {
      setJobs((prev) => {
        const next = new Map(prev);
        next.delete(caseId);
        return next;
      });
    },
    [],
  );

  // -- toast notifications ---------------------------------------------------

  useEffect(() => {
    const prev = prevStatusRef.current;

    for (const [caseId, job] of jobs) {
      const prevStatus = prev.get(caseId);

      if (prevStatus === "running" && job.status === "completed") {
        toast.success(`Prüfungen abgeschlossen: ${job.caseTitle}`, {
          description:
            job.checksTotal > 0
              ? `${job.checksTotal} Checks erfolgreich ausgeführt.`
              : undefined,
          duration: 8000,
        });
        setTimeout(() => dismissJob(caseId), 8000);
      }

      if (prevStatus === "running" && job.status === "failed") {
        toast.error(`Prüfungen fehlgeschlagen: ${job.caseTitle}`, {
          description: "Ein Fehler ist aufgetreten.",
          duration: 12000,
        });
        setTimeout(() => dismissJob(caseId), 12000);
      }
    }

    const snapshot = new Map<string, string>();
    for (const [caseId, job] of jobs) {
      snapshot.set(caseId, job.status);
    }
    prevStatusRef.current = snapshot;
  }, [jobs, dismissJob]);

  // -- context value ---------------------------------------------------------

  const jobsArray = useMemo(() => Array.from(jobs.values()), [jobs]);

  const value: RunChecksContextValue = {
    jobs: jobsArray,
    registerJob,
    isRunning,
    getJob,
    dismissJob,
    runningCount,
  };

  return (
    <RunningChecksContext.Provider value={value}>
      {children}
    </RunningChecksContext.Provider>
  );
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useRunningChecks(): RunChecksContextValue {
  const ctx = useContext(RunningChecksContext);
  if (!ctx) {
    throw new Error("useRunningChecks must be used within a RunningChecksProvider");
  }
  return ctx;
}
