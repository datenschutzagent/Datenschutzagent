-- Migration 016: Case archiving (Retention/Archivierung)
-- Adds archived_at timestamp and retention_months to cases table.
-- archived_at: set when a case is archived; NULL = not archived
-- retention_months: optional retention period in months (NULL = no automatic archiving)

ALTER TABLE cases
    ADD COLUMN IF NOT EXISTS archived_at TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS retention_months INTEGER DEFAULT NULL;

-- Index for fast filtering of non-archived cases (the common query)
CREATE INDEX IF NOT EXISTS idx_cases_archived_at ON cases (archived_at);
