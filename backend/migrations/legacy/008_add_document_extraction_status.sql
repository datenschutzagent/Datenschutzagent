-- Add extraction_status and extraction_error to documents (async extraction state).
-- Run once for existing databases; new installs get the columns via create_all.
-- Example: psql $DATABASE_URL -f backend/migrations/008_add_document_extraction_status.sql
ALTER TABLE documents ADD COLUMN IF NOT EXISTS extraction_status VARCHAR(20) DEFAULT 'pending';
ALTER TABLE documents ADD COLUMN IF NOT EXISTS extraction_error TEXT;

-- Backfill: documents with content are done, others stay pending
UPDATE documents SET extraction_status = 'done' WHERE content IS NOT NULL AND (extraction_status IS NULL OR extraction_status = 'pending');
UPDATE documents SET extraction_status = 'pending' WHERE content IS NULL AND (extraction_status IS NULL OR extraction_status = '');
