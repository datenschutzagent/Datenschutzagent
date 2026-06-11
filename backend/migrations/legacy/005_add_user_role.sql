-- RBAC: one role per user (viewer, editor, admin). New users get default from config; existing users become editor.
-- Run once: psql $DATABASE_URL -f backend/migrations/005_add_user_role.sql
ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(20) NOT NULL DEFAULT 'viewer';
UPDATE users SET role = 'editor' WHERE role = 'viewer' OR role IS NULL;
