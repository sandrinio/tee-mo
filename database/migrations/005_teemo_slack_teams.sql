-- =============================================================================
-- Migration: 005_teemo_slack_teams
-- Purpose:   Create teemo_slack_teams per ADR-024. One row per Slack workspace
--            installation. Holds the encrypted bot token and the bot's user ID
--            for self-message filter (ADR-021).
-- Depends on: 001_teemo_users (for FK to teemo_users)
-- ADR:       ADR-024 (Workspace Model — 1 user : N SlackTeams : N Workspaces)
-- =============================================================================

CREATE TABLE IF NOT EXISTS teemo_slack_teams (
    slack_team_id              VARCHAR(32) PRIMARY KEY,        -- Slack team ID (e.g. "T0123ABC456")
    owner_user_id              UUID NOT NULL REFERENCES teemo_users(id) ON DELETE CASCADE,
    slack_bot_user_id          VARCHAR(32) NOT NULL,           -- Bot's Slack user ID (self-message filter per ADR-021)
    encrypted_slack_bot_token  TEXT NOT NULL,                  -- AES-256-GCM ciphertext (ADR-002/010)
    installed_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Owner lookup for the team list UI
CREATE INDEX IF NOT EXISTS idx_teemo_slack_teams_owner_user_id
    ON teemo_slack_teams (owner_user_id);

-- updated_at trigger (reuses function from 001_teemo_users)
DROP TRIGGER IF EXISTS trg_teemo_slack_teams_updated_at ON teemo_slack_teams;
CREATE TRIGGER trg_teemo_slack_teams_updated_at
    BEFORE UPDATE ON teemo_slack_teams
    FOR EACH ROW
    EXECUTE FUNCTION teemo_set_updated_at();

-- RLS disabled — backend enforces isolation via get_current_user_id + assert_team_owner
ALTER TABLE teemo_slack_teams DISABLE ROW LEVEL SECURITY;

DO $$
DECLARE
    cnt BIGINT;
BEGIN
    SELECT COUNT(*) INTO cnt FROM teemo_slack_teams;
    RAISE NOTICE '✓ teemo_slack_teams migration complete. Current row count: %', cnt;
END $$;
