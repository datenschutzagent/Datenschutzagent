-- Add source_strategy to findings (full_text vs rag for run-checks variant).
-- Run once for existing databases; new installs get the column via create_all.
-- Example: psql $DATABASE_URL -f backend/migrations/002_add_finding_source_strategy.sql
ALTER TABLE findings ADD COLUMN IF NOT EXISTS source_strategy VARCHAR(20);
