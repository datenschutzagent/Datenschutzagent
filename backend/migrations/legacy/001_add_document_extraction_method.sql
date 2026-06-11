-- Add extraction_method to documents (OCR vs text extraction).
-- Run once for existing databases; new installs get the column via create_all.
-- Example: psql $DATABASE_URL -f backend/migrations/001_add_document_extraction_method.sql
ALTER TABLE documents ADD COLUMN IF NOT EXISTS extraction_method VARCHAR(20);
