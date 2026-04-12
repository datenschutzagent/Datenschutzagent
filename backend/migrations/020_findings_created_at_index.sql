-- Add index on findings.created_at to support the 6-month trend query in /findings/stats.
-- Without this index the query scans the entire findings table for every stats request.
-- Run: psql $DATABASE_URL -f migrations/020_findings_created_at_index.sql

CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_findings_created_at ON findings (created_at);
