-- =============================================================================
-- Migration: 004_teemo_skills
-- Purpose:   Chat-created skills — named instruction bundles the agent can
--            load and invoke. CRUD happens exclusively via agent chat tools
--            (ADR-023). No `related_tools`, no `is_system`, no seeded skills.
-- Depends on: 002_teemo_workspaces
-- =============================================================================

-- -----------------------------------------------------------------------------
-- teemo_skills
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS teemo_skills (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id    UUID NOT NULL REFERENCES teemo_workspaces(id) ON DELETE CASCADE,

    name            VARCHAR(60)  NOT NULL,              -- slug, e.g., "budget-comparison"
    summary         VARCHAR(160) NOT NULL,              -- "Use when..." format
    instructions    TEXT         NOT NULL,              -- full workflow (≤2000 chars enforced by check)

    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    -- One skill name per workspace.
    CONSTRAINT uq_teemo_skills_workspace_name
        UNIQUE (workspace_id, name),

    -- Name must be a lowercase slug: alphanumeric + hyphens, no leading/trailing hyphen.
    CONSTRAINT chk_teemo_skills_name_format
        CHECK (name ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),

    -- Length guards for the three text fields.
    CONSTRAINT chk_teemo_skills_summary_length
        CHECK (CHAR_LENGTH(summary) BETWEEN 1 AND 160),
    CONSTRAINT chk_teemo_skills_instructions_length
        CHECK (CHAR_LENGTH(instructions) BETWEEN 1 AND 2000)
);

-- Primary lookup: active skills for a workspace (for L1 catalog injection)
CREATE INDEX IF NOT EXISTS idx_teemo_skills_workspace_active
    ON teemo_skills (workspace_id)
    WHERE is_active = TRUE;

-- updated_at trigger (reuses function from 001)
DROP TRIGGER IF EXISTS trg_teemo_skills_updated_at ON teemo_skills;
CREATE TRIGGER trg_teemo_skills_updated_at
    BEFORE UPDATE ON teemo_skills
    FOR EACH ROW
    EXECUTE FUNCTION teemo_set_updated_at();

-- RLS disabled (backend enforces workspace isolation)
ALTER TABLE teemo_skills DISABLE ROW LEVEL SECURITY;

DO $$
DECLARE
    cnt BIGINT;
BEGIN
    SELECT COUNT(*) INTO cnt FROM teemo_skills;
    RAISE NOTICE '✓ teemo_skills migration complete. Current row count: %', cnt;
END $$;
