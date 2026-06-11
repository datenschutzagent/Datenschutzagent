-- Improvement fixes: findings timestamps, DB indexes, processing_context length, playbook FK
-- Run: psql $DATABASE_URL -f migrations/013_improvements.sql

-- 1. Add created_at and updated_at to findings
ALTER TABLE findings
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

-- 2. Indexes for findings (frequent filter/join columns)
CREATE INDEX IF NOT EXISTS ix_findings_case_id ON findings (case_id);
CREATE INDEX IF NOT EXISTS ix_findings_case_id_status ON findings (case_id, status);
CREATE INDEX IF NOT EXISTS ix_findings_case_id_severity ON findings (case_id, severity);

-- 3. Indexes for documents
CREATE INDEX IF NOT EXISTS ix_documents_case_id ON documents (case_id);
CREATE INDEX IF NOT EXISTS ix_documents_extraction_status ON documents (extraction_status);

-- 4. Indexes for cases
CREATE INDEX IF NOT EXISTS ix_cases_status ON cases (status);
CREATE INDEX IF NOT EXISTS ix_cases_department ON cases (department);
CREATE INDEX IF NOT EXISTS ix_cases_updated_at ON cases (updated_at);

-- 5. Extend processing_context from 80 to 500 characters
ALTER TABLE cases ALTER COLUMN processing_context TYPE VARCHAR(500);

-- 6. Make run_checks_jobs.playbook_id nullable (SET NULL instead of CASCADE)
--    so deleting a playbook does not destroy job history
ALTER TABLE run_checks_jobs
    DROP CONSTRAINT IF EXISTS run_checks_jobs_playbook_id_fkey;
ALTER TABLE run_checks_jobs
    ALTER COLUMN playbook_id DROP NOT NULL;
ALTER TABLE run_checks_jobs
    ADD CONSTRAINT run_checks_jobs_playbook_id_fkey
    FOREIGN KEY (playbook_id) REFERENCES playbooks(id) ON DELETE SET NULL;
