-- =============================================================================
-- Migration: 007_teemo_workspaces_alter
-- Purpose:   Apply ADR-024 refactor to teemo_workspaces:
--              - Drop slack_bot_user_id + encrypted_slack_bot_token (moved to teemo_slack_teams)
--              - Convert slack_team_id from plain VARCHAR to FK → teemo_slack_teams
--              - Add is_default_for_team BOOLEAN + partial unique index one_default_per_team
--              - Drop obsolete uq_teemo_workspaces_user_slack_team constraint
-- Depends on: 002_teemo_workspaces, 005_teemo_slack_teams
-- ADR:       ADR-024 (workspace model)
-- Safety:    DO-block pre-check aborts if ANY existing row has data in the columns
--            being dropped — prevents data loss.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Safety pre-check — fail loudly if there's data to preserve
-- -----------------------------------------------------------------------------
DO $$
DECLARE
    stale_count BIGINT;
BEGIN
    SELECT COUNT(*) INTO stale_count
    FROM teemo_workspaces
    WHERE slack_bot_user_id IS NOT NULL
       OR encrypted_slack_bot_token IS NOT NULL;
    IF stale_count > 0 THEN
        RAISE EXCEPTION 'Migration 007 aborted: % teemo_workspaces row(s) contain data in columns being dropped (slack_bot_user_id or encrypted_slack_bot_token). Back up and clear them before running this migration.', stale_count;
    END IF;
END $$;

-- -----------------------------------------------------------------------------
-- Drop the obsolete unique constraint (user + slack_team_id was the old shape)
-- -----------------------------------------------------------------------------
ALTER TABLE teemo_workspaces
    DROP CONSTRAINT IF EXISTS uq_teemo_workspaces_user_slack_team;

-- -----------------------------------------------------------------------------
-- Drop columns that move to teemo_slack_teams
-- -----------------------------------------------------------------------------
ALTER TABLE teemo_workspaces DROP COLUMN IF EXISTS slack_bot_user_id;
ALTER TABLE teemo_workspaces DROP COLUMN IF EXISTS encrypted_slack_bot_token;

-- -----------------------------------------------------------------------------
-- Convert slack_team_id from plain VARCHAR to FK → teemo_slack_teams
-- (Column already exists from migration 002; we just add the FK constraint.)
-- -----------------------------------------------------------------------------
ALTER TABLE teemo_workspaces
    ADD CONSTRAINT fk_teemo_workspaces_slack_team
    FOREIGN KEY (slack_team_id)
    REFERENCES teemo_slack_teams(slack_team_id)
    ON DELETE CASCADE;

-- -----------------------------------------------------------------------------
-- Add is_default_for_team flag + partial unique index
-- -----------------------------------------------------------------------------
ALTER TABLE teemo_workspaces
    ADD COLUMN IF NOT EXISTS is_default_for_team BOOLEAN NOT NULL DEFAULT FALSE;

-- Partial unique index: exactly one default workspace per team
CREATE UNIQUE INDEX IF NOT EXISTS one_default_per_team
    ON teemo_workspaces (slack_team_id)
    WHERE is_default_for_team = TRUE;

DO $$
BEGIN
    RAISE NOTICE '✓ teemo_workspaces migration 007 complete (ADR-024 refactor applied).';
END $$;
