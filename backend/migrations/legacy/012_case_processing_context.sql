-- Optional case dimensions for sector-agnostic workflows (beyond university case_type).
ALTER TABLE cases
    ADD COLUMN IF NOT EXISTS processing_context VARCHAR(80) NULL,
    ADD COLUMN IF NOT EXISTS special_category_data BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS international_transfer BOOLEAN NOT NULL DEFAULT false;
