-- Migration 017: Playbook revision history
-- Stores a content snapshot before each PATCH; enables version history and rollback.

CREATE TABLE IF NOT EXISTS playbook_revisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    playbook_id UUID NOT NULL REFERENCES playbooks(id) ON DELETE CASCADE,
    version VARCHAR(50) NOT NULL,
    content JSONB NOT NULL,
    changed_by VARCHAR(200) NOT NULL DEFAULT '',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_playbook_revisions_playbook_id_created_at
    ON playbook_revisions (playbook_id, created_at);
