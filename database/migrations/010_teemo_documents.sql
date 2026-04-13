-- Migration 010: Replace teemo_knowledge_index with teemo_documents
--
-- EPIC-015 STORY-015-01: Documents Table Migration + Document Service Layer
--
-- Replaces the Drive-specific teemo_knowledge_index table with a unified
-- teemo_documents table that supports google_drive, upload, and agent sources.
-- Adds sync_status state machine for EPIC-013 wiki pipeline handoff.
-- Content hash upgraded from MD5 to SHA-256.
-- 15-document cap enforced via BEFORE INSERT trigger.
-- No data migration required — teemo_knowledge_index has zero production rows.

-- ---------------------------------------------------------------------------
-- 1. Create teemo_documents
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS teemo_documents (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id        UUID NOT NULL REFERENCES teemo_workspaces(id) ON DELETE CASCADE,
    title               VARCHAR(512) NOT NULL,
    content             TEXT,
    ai_description      TEXT,
    doc_type            VARCHAR(32) NOT NULL,
    source              VARCHAR(20) NOT NULL,
    sync_status         VARCHAR(16) NOT NULL DEFAULT 'pending',
    external_id         VARCHAR(128),
    external_link       TEXT,
    original_filename   VARCHAR(512),
    content_hash        VARCHAR(64),
    file_size           INTEGER,
    metadata            JSONB DEFAULT '{}',
    last_synced_at      TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_teemo_documents_source
        CHECK (source IN ('google_drive', 'upload', 'agent')),

    CONSTRAINT chk_teemo_documents_sync_status
        CHECK (sync_status IN ('pending', 'processing', 'synced', 'error')),

    CONSTRAINT chk_teemo_documents_doc_type
        CHECK (doc_type IN (
            'pdf', 'docx', 'xlsx', 'text', 'markdown',
            'google_doc', 'google_sheet', 'google_slides'
        ))
);

-- ---------------------------------------------------------------------------
-- 2. Indexes
-- ---------------------------------------------------------------------------

-- Workspace fan-out — nearly every query filters on workspace_id.
CREATE INDEX IF NOT EXISTS idx_teemo_documents_workspace
    ON teemo_documents (workspace_id);

-- content_hash — change-detection lookups by Drive cron (EPIC-015 §4.4).
CREATE INDEX IF NOT EXISTS idx_teemo_documents_content_hash
    ON teemo_documents (content_hash);

-- external_id — Drive file ID lookups (upsert by external_id).
CREATE INDEX IF NOT EXISTS idx_teemo_documents_external_id
    ON teemo_documents (external_id) WHERE external_id IS NOT NULL;

-- sync_status — partial index used by EPIC-013 wiki pipeline to find pending docs.
-- Excludes 'synced' rows (the majority) to keep the index small.
CREATE INDEX IF NOT EXISTS idx_teemo_documents_sync_status
    ON teemo_documents (sync_status) WHERE sync_status != 'synced';

-- Drive uniqueness: one row per (workspace, external Drive file ID).
CREATE UNIQUE INDEX IF NOT EXISTS uq_teemo_documents_drive
    ON teemo_documents (workspace_id, external_id)
    WHERE external_id IS NOT NULL;

-- Upload uniqueness: one row per (workspace, original filename) per source=upload.
CREATE UNIQUE INDEX IF NOT EXISTS uq_teemo_documents_upload
    ON teemo_documents (workspace_id, original_filename)
    WHERE source = 'upload';

-- ---------------------------------------------------------------------------
-- 3. updated_at auto-update trigger
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION trg_teemo_documents_updated_at_fn()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_teemo_documents_updated_at
    BEFORE UPDATE ON teemo_documents
    FOR EACH ROW EXECUTE FUNCTION trg_teemo_documents_updated_at_fn();

-- ---------------------------------------------------------------------------
-- 4. 15-document cap trigger (ADR-007: all sources combined)
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION trg_teemo_documents_cap_fn()
RETURNS TRIGGER AS $$
BEGIN
    IF (
        SELECT COUNT(*)
        FROM teemo_documents
        WHERE workspace_id = NEW.workspace_id
    ) >= 15 THEN
        RAISE EXCEPTION 'Maximum 15 documents per workspace';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_teemo_documents_cap
    BEFORE INSERT ON teemo_documents
    FOR EACH ROW EXECUTE FUNCTION trg_teemo_documents_cap_fn();

-- ---------------------------------------------------------------------------
-- 5. Drop old table — no data to migrate (zero production rows)
-- ---------------------------------------------------------------------------

DROP TABLE IF EXISTS teemo_knowledge_index CASCADE;
