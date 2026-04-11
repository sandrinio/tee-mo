-- =============================================================================
-- Migration: 006_teemo_workspace_channels
-- Purpose:   Create teemo_workspace_channels per ADR-024 + ADR-025. Explicit
--            channel-to-workspace bindings. PRIMARY KEY on slack_channel_id
--            enforces one-workspace-per-channel globally.
-- Depends on: 002_teemo_workspaces (for FK), 005_teemo_slack_teams (soft dep)
-- ADR:       ADR-024 (workspace model), ADR-025 (explicit channel binding)
-- =============================================================================

CREATE TABLE IF NOT EXISTS teemo_workspace_channels (
    slack_channel_id  VARCHAR(32) PRIMARY KEY,                         -- Slack channel ID (e.g. "C0123ABC456")
    workspace_id      UUID NOT NULL REFERENCES teemo_workspaces(id) ON DELETE CASCADE,
    slack_team_id     VARCHAR(32) NOT NULL,                            -- Denormalized for consistency checks
    bound_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- workspace → channels lookup (channel chip refresh in dashboard)
CREATE INDEX IF NOT EXISTS idx_teemo_workspace_channels_workspace_id
    ON teemo_workspace_channels (workspace_id);

-- team → channels lookup (dashboard channel picker, binding status refresh)
CREATE INDEX IF NOT EXISTS idx_teemo_workspace_channels_slack_team_id
    ON teemo_workspace_channels (slack_team_id);

ALTER TABLE teemo_workspace_channels DISABLE ROW LEVEL SECURITY;

DO $$
DECLARE
    cnt BIGINT;
BEGIN
    SELECT COUNT(*) INTO cnt FROM teemo_workspace_channels;
    RAISE NOTICE '✓ teemo_workspace_channels migration complete. Current row count: %', cnt;
END $$;
