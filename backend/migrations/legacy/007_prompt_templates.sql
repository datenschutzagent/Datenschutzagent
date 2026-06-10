-- Versioned prompt templates for LLM (check runner, VVT). One active version per key.
-- Run once: psql $DATABASE_URL -f backend/migrations/007_prompt_templates.sql
CREATE TABLE IF NOT EXISTS prompt_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key VARCHAR(100) NOT NULL,
    version VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(key, version)
);
CREATE INDEX IF NOT EXISTS ix_prompt_templates_key ON prompt_templates(key);
CREATE INDEX IF NOT EXISTS ix_prompt_templates_key_active ON prompt_templates(key, is_active) WHERE is_active = true;
