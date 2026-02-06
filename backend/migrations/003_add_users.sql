-- Create users table for profile and preferences (current user via CURRENT_USER_ID or default).
-- Run once for existing databases; new installs get the table via create_all.
-- Example: psql $DATABASE_URL -f backend/migrations/003_add_users.sql
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    display_name VARCHAR(200) NOT NULL DEFAULT 'Standardnutzer',
    email VARCHAR(320),
    preferences JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
