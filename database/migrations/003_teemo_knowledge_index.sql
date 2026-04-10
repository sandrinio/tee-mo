-- =============================================================================
-- Migration: 003_teemo_knowledge_index
-- Purpose:   Knowledge base — up to 15 Google Drive files per workspace.
--            AI-generated descriptions with content-hash based re-scan (ADR-006).
-- Depends on: 002_teemo_workspaces
-- =============================================================================

-- -----------------------------------------------------------------------------
-- teemo_knowledge_index
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS teemo_knowledge_index (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id      UUID NOT NULL REFERENCES teemo_workspaces(id) ON DELETE CASCADE,

    -- Google Drive identity
    drive_file_id     VARCHAR(128) NOT NULL,            -- Google's immutable file ID
    title             VARCHAR(512) NOT NULL,            -- file name at index time
    link              TEXT NOT NULL,                    -- webViewLink from Drive API
    mime_type         VARCHAR(128) NOT NULL,            -- e.g., 'application/vnd.google-apps.document'

    -- Self-describing metadata (Charter §5.2 + ADR-006)
    ai_description    TEXT NOT NULL,                    -- 2-3 sentence AI summary, required
    content_hash      VARCHAR(64) NOT NULL,             -- MD5 hex of last-read content
    last_scanned_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- A given Drive file can only be indexed once per workspace.
    CONSTRAINT uq_teemo_knowledge_index_workspace_file
        UNIQUE (workspace_id, drive_file_id),

    -- Supported MIME types (Charter §6 + ADR-016). Rejecting at insert time
    -- prevents the app from ever inserting an unreadable file.
    CONSTRAINT chk_teemo_knowledge_index_mime_type CHECK (
        mime_type IN (
            'application/vnd.google-apps.document',     -- Google Docs
            'application/vnd.google-apps.spreadsheet',  -- Google Sheets
            'application/vnd.google-apps.presentation', -- Google Slides
            'application/pdf',                          -- PDF
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',  -- .docx
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'         -- .xlsx
        )
    )
);

-- Primary lookup: all files for a workspace
CREATE INDEX IF NOT EXISTS idx_teemo_knowledge_index_workspace_id
    ON teemo_knowledge_index (workspace_id);

-- -----------------------------------------------------------------------------
-- 15-file hard cap per workspace (Charter §1.1, ADR-007)
-- Enforced by trigger at the DB level for defence in depth.
-- Backend also enforces this before INSERT — but the DB is the last line.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION teemo_enforce_knowledge_index_cap()
RETURNS TRIGGER AS $$
DECLARE
    current_count INT;
BEGIN
    SELECT COUNT(*) INTO current_count
    FROM teemo_knowledge_index
    WHERE workspace_id = NEW.workspace_id;

    IF current_count >= 15 THEN
        RAISE EXCEPTION 'knowledge_index_full: workspace % already has 15 files (max)', NEW.workspace_id
            USING HINT = 'Remove an existing file before adding a new one.';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_teemo_knowledge_index_cap ON teemo_knowledge_index;
CREATE TRIGGER trg_teemo_knowledge_index_cap
    BEFORE INSERT ON teemo_knowledge_index
    FOR EACH ROW
    EXECUTE FUNCTION teemo_enforce_knowledge_index_cap();

-- RLS disabled (backend enforces workspace isolation)
ALTER TABLE teemo_knowledge_index DISABLE ROW LEVEL SECURITY;

DO $$
DECLARE
    cnt BIGINT;
BEGIN
    SELECT COUNT(*) INTO cnt FROM teemo_knowledge_index;
    RAISE NOTICE '✓ teemo_knowledge_index migration complete. Current row count: %', cnt;
END $$;
