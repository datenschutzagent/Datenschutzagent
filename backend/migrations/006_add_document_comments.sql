-- Document comments: per-document discussion (author from current user).
-- Run once: psql $DATABASE_URL -f backend/migrations/006_add_document_comments.sql
CREATE TABLE IF NOT EXISTS document_comments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    case_id UUID NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    author VARCHAR(200) NOT NULL DEFAULT '',
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    text TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_document_comments_document_id ON document_comments(document_id);
CREATE INDEX IF NOT EXISTS ix_document_comments_created_at ON document_comments(created_at);
