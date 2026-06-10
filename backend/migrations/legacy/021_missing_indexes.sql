-- Add missing indexes for common query patterns.
-- All created with CONCURRENTLY to avoid locking in production.
-- Run: psql $DATABASE_URL -f migrations/021_missing_indexes.sql

-- finding_comments and document_comments: support pagination and count queries by parent ID
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_finding_comments_finding_id ON finding_comments (finding_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_document_comments_document_id ON document_comments (document_id);

-- users.email: support login/lookup by email (e.g. OIDC first-login dedup check)
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_users_email ON users (email) WHERE email IS NOT NULL;

-- cases.status: support status-based filtering in list queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_cases_status ON cases (status);
