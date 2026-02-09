-- Legal bases (Rechtsgrundlagen) for agent context: DSGVO, BDSG, sector-specific laws, etc.
-- Example: psql $DATABASE_URL -f backend/migrations/011_legal_bases.sql
CREATE TABLE IF NOT EXISTS legal_bases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(500) NOT NULL,
    short_name VARCHAR(100) NULL,
    content TEXT NOT NULL DEFAULT '',
    applicability VARCHAR(20) NOT NULL DEFAULT 'always',
    department_codes TEXT[] NULL,
    case_types TEXT[] NULL,
    internal_only BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
