-- =============================================================================
-- Migration: 002_teemo_workspaces
-- Purpose:   Create teemo_workspaces — one row per Slack team installation.
--            Multi-workspace per user supported (Roadmap ADR-011).
-- Depends on: 001_teemo_users
-- =============================================================================

-- -----------------------------------------------------------------------------
-- teemo_workspaces
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS teemo_workspaces (
    id                                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                           UUID NOT NULL REFERENCES teemo_users(id) ON DELETE CASCADE,
    name                              VARCHAR(120) NOT NULL,

    -- Slack installation
    slack_team_id                     VARCHAR(32),             -- e.g., "T0123ABC456"
    slack_bot_user_id                 VARCHAR(32),             -- needed for self-message filter (Charter §5.1)
    encrypted_slack_bot_token         TEXT,                    -- AES-256-GCM ciphertext (ADR-010)

    -- BYOK AI provider configuration
    ai_provider                       VARCHAR(16),             -- 'google' | 'anthropic' | 'openai'
    ai_model                          VARCHAR(64),             -- user-selected conversation-tier model id
    encrypted_api_key                 TEXT,                    -- AES-256-GCM ciphertext

    -- Google Drive OAuth (offline refresh token, ADR-009)
    encrypted_google_refresh_token    TEXT,                    -- AES-256-GCM ciphertext

    created_at                        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                        TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- One Slack team can only be installed once per user account.
    -- (A user can have many workspaces; a single Slack team is unique per user.)
    CONSTRAINT uq_teemo_workspaces_user_slack_team
        UNIQUE (user_id, slack_team_id),

    -- Provider must be one of the supported 3 (if set).
    CONSTRAINT chk_teemo_workspaces_provider
        CHECK (ai_provider IS NULL OR ai_provider IN ('google', 'anthropic', 'openai'))
);

-- Lookup indexes
CREATE INDEX IF NOT EXISTS idx_teemo_workspaces_user_id
    ON teemo_workspaces (user_id);

CREATE INDEX IF NOT EXISTS idx_teemo_workspaces_slack_team_id
    ON teemo_workspaces (slack_team_id)
    WHERE slack_team_id IS NOT NULL;

-- updated_at trigger (reuses function from 001)
DROP TRIGGER IF EXISTS trg_teemo_workspaces_updated_at ON teemo_workspaces;
CREATE TRIGGER trg_teemo_workspaces_updated_at
    BEFORE UPDATE ON teemo_workspaces
    FOR EACH ROW
    EXECUTE FUNCTION teemo_set_updated_at();

-- RLS disabled (same rationale as 001 — backend enforces isolation)
ALTER TABLE teemo_workspaces DISABLE ROW LEVEL SECURITY;

DO $$
DECLARE
    cnt BIGINT;
BEGIN
    SELECT COUNT(*) INTO cnt FROM teemo_workspaces;
    RAISE NOTICE '✓ teemo_workspaces migration complete. Current row count: %', cnt;
END $$;
