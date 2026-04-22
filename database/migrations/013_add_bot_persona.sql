-- =============================================================================
-- Migration: 013_add_bot_persona
-- Purpose:   Add bot_persona TEXT column to teemo_workspaces.
--            The persona replaces the default "You are Tee-Mo" identity line
--            at the top of the agent system prompt with a role defined by the
--            workspace owner (edited from the dashboard via PATCH /api/workspaces/{id}).
-- Depends on: 002_teemo_workspaces, 007_teemo_workspaces_alter
-- =============================================================================

ALTER TABLE teemo_workspaces
    ADD COLUMN IF NOT EXISTS bot_persona TEXT;

-- Enforce a reasonable upper bound in the DB itself.
-- 2000 chars ≈ ~500 tokens — big enough for a rich persona, small enough
-- to avoid runaway prompt bloat. DROP-then-ADD keeps the migration idempotent.
ALTER TABLE teemo_workspaces
    DROP CONSTRAINT IF EXISTS chk_teemo_workspaces_bot_persona_length;
ALTER TABLE teemo_workspaces
    ADD CONSTRAINT chk_teemo_workspaces_bot_persona_length
    CHECK (bot_persona IS NULL OR char_length(bot_persona) <= 2000);

DO $$
BEGIN
    RAISE NOTICE '✓ teemo_workspaces migration 013 complete (bot_persona column added).';
END $$;
