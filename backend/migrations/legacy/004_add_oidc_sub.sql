-- Add OIDC subject for user lookup on first login (sync with IdP).
-- Run once: psql $DATABASE_URL -f backend/migrations/004_add_oidc_sub.sql
ALTER TABLE users ADD COLUMN IF NOT EXISTS oidc_sub VARCHAR(500) NULL UNIQUE;
CREATE UNIQUE INDEX IF NOT EXISTS ix_users_oidc_sub ON users (oidc_sub) WHERE oidc_sub IS NOT NULL;
