/**
 * Global context that tracks running playbook check jobs across the application.
 *
 * - Polls GET /cases/running-checks every 3 seconds while jobs are active.
 * - On initial mount, fetches once to discover jobs already running (e.g. after page refresh).
 * - Fires toast notifications when jobs complete or fail.
 * - Provides helpers so any component can query running state without extra API calls.
 */
import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
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
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const mountedRef = useRef(true);

  // -- helpers ---------------------------------------------------------------

  const runningCount = Array.from(jobs.values()).filter((j) => j.status === "running").length;

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

  const getJob = useCallback(
    (caseId: string) => jobs.get(caseId),
    [jobs],
  );

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

  // -- polling ---------------------------------------------------------------

  const poll = useCallback(async () => {
    try {
      const running = await getRunningChecks();
      if (!mountedRef.current) return;

      setJobs((prev) => {
        const next = new Map(prev);
        const seenCaseIds = new Set<string>();

        // Update/add jobs from backend
        for (const job of running) {
          seenCaseIds.add(job.caseId);
          next.set(job.caseId, job);
        }

        // Check for jobs that were "running" in prev but are no longer in the response
        // -> they completed or failed between polls
        for (const [caseId, prevJob] of prev) {
          if (prevJob.status === "running" && !seenCaseIds.has(caseId)) {
            // Job is no longer running on the server — mark as completed
            next.set(caseId, { ...prevJob, status: "completed" });
          }
        }

        return next;
      });
    } catch {
      // Transient network error — keep polling, don't clear state
    }
  }, []);

  // -- toast notifications ---------------------------------------------------

  useEffect(() => {
    const prev = prevStatusRef.current;

    for (const [caseId, job] of jobs) {
      const prevStatus = prev.get(caseId);

      if (prevStatus === "running" && job.status === "completed") {
        toast.success(`Prüfungen abgeschlossen: ${job.caseTitle}`, {
          description: job.checksTotal > 0
            ? `${job.checksTotal} Checks erfolgreich ausgeführt.`
            : undefined,
          duration: 8000,
        });
        // Auto-dismiss after 8 seconds
        setTimeout(() => dismissJob(caseId), 8000);
      }

      if (prevStatus === "running" && job.status === "failed") {
        toast.error(`Prüfungen fehlgeschlagen: ${job.caseTitle}`, {
          description: "Ein Fehler ist aufgetreten.",
          duration: 12000,
        });
        // Auto-dismiss after 12 seconds
        setTimeout(() => dismissJob(caseId), 12000);
      }
    }

    // Snapshot current statuses for next comparison
    const snapshot = new Map<string, string>();
    for (const [caseId, job] of jobs) {
      snapshot.set(caseId, job.status);
    }
    prevStatusRef.current = snapshot;
  }, [jobs, dismissJob]);

  // -- interval management ---------------------------------------------------

  useEffect(() => {
    // Initial fetch on mount to discover already-running jobs
    poll();

    return () => {
      mountedRef.current = false;
    };
  }, [poll]);

  useEffect(() => {
    if (runningCount > 0) {
      if (!intervalRef.current) {
        intervalRef.current = setInterval(poll, POLL_INTERVAL_MS);
      }
    } else {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [runningCount, poll]);

  // -- context value ---------------------------------------------------------

  const jobsArray = Array.from(jobs.values());

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
