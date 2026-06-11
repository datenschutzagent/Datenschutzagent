-- Table for async run-checks job status (running/completed/failed).
-- Example: psql $DATABASE_URL -f backend/migrations/009_add_run_checks_jobs.sql
CREATE TABLE IF NOT EXISTS run_checks_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL,
    playbook_id UUID NOT NULL REFERENCES playbooks(id) ON DELETE CASCADE,
    playbook_name VARCHAR(200) NOT NULL,
    strategies TEXT[] NOT NULL DEFAULT '{}',
    celery_task_id VARCHAR(255) NULL,
    error TEXT NULL,
    findings_count INTEGER NOT NULL DEFAULT 0,
    result_payload JSONB NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_run_checks_jobs_case_id_created_at ON run_checks_jobs (case_id, created_at DESC);
