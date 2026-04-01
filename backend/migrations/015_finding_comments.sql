-- Finding comment threads (mirrors document_comments pattern)
-- Run: psql $DATABASE_URL -f migrations/015_finding_comments.sql

CREATE TABLE IF NOT EXISTS finding_comments (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    finding_id  UUID NOT NULL REFERENCES findings(id) ON DELETE CASCADE,
    case_id     UUID NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    author      VARCHAR(200) NOT NULL DEFAULT '',
    user_id     UUID REFERENCES users(id) ON DELETE SET NULL,
    text        TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_finding_comments_finding_id ON finding_comments (finding_id);
CREATE INDEX IF NOT EXISTS ix_finding_comments_case_id ON finding_comments (case_id);
