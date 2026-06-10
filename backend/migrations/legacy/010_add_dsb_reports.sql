-- Persisted DSB report per case (latest overwrites) and jobs for async generation.
-- Example: psql $DATABASE_URL -f backend/migrations/010_add_dsb_reports.sql
CREATE TABLE IF NOT EXISTS dsb_reports (
    case_id UUID PRIMARY KEY REFERENCES cases(id) ON DELETE CASCADE,
    generated_at TIMESTAMPTZ NOT NULL,
    payload JSONB NOT NULL,
    basis_document_count INTEGER NOT NULL DEFAULT 0,
    basis_last_run_checks_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS dsb_report_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL,
    celery_task_id VARCHAR(255) NULL,
    error TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_dsb_report_jobs_case_id_created_at ON dsb_report_jobs (case_id, created_at DESC);
