-- Deadline tracking for cases and findings
-- Run: psql $DATABASE_URL -f migrations/014_deadline_tracking.sql

-- 1. Add case-level deadline
ALTER TABLE cases
    ADD COLUMN IF NOT EXISTS deadline DATE NULL;

-- 2. Add per-finding due date
ALTER TABLE findings
    ADD COLUMN IF NOT EXISTS due_date DATE NULL;

-- 3. Index for overdue case filter
CREATE INDEX IF NOT EXISTS ix_cases_deadline ON cases (deadline)
    WHERE deadline IS NOT NULL;
