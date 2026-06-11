-- Migration 019: Add auto_run_checks flag to cases
ALTER TABLE cases
  ADD COLUMN IF NOT EXISTS auto_run_checks BOOLEAN NOT NULL DEFAULT FALSE;
