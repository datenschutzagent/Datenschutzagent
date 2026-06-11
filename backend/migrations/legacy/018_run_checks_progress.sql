-- Migration 018: Add checks_total and checks_done to run_checks_jobs for progress tracking
ALTER TABLE run_checks_jobs
  ADD COLUMN IF NOT EXISTS checks_total INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS checks_done  INTEGER NOT NULL DEFAULT 0;
