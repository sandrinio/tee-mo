-- Migration 011: Wiki knowledge tables
-- STORY-013-01: Creates teemo_wiki_pages and teemo_wiki_log tables for the wiki
-- knowledge pipeline (EPIC-013). These tables store AI-generated wiki pages
-- synthesized from workspace documents, enabling the agent to answer questions
-- using structured wiki content rather than raw Drive files.
--
-- teemo_wiki_pages: Stores individual wiki pages with slug, title, content,
--   TLDR, source document IDs, and confidence metadata. Uniqueness is enforced
--   per (workspace_id, slug) pair so ingest can upsert without collision.
--
-- teemo_wiki_log: Audit trail for wiki pipeline operations (ingest, query, lint,
--   update). Enables debugging and observability for the async wiki pipeline.


-- ---------------------------------------------------------------------------
-- teemo_wiki_pages
-- ---------------------------------------------------------------------------

CREATE TABLE teemo_wiki_pages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES teemo_workspaces(id) ON DELETE CASCADE,
    slug VARCHAR(200) NOT NULL,
    title VARCHAR(512) NOT NULL,
    page_type VARCHAR(32) NOT NULL,
    content TEXT NOT NULL,
    tldr VARCHAR(500),
    source_document_ids UUID[],
    related_slugs TEXT[],
    confidence VARCHAR(16) DEFAULT 'high',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_wiki_page_type CHECK (page_type IN ('source-summary', 'concept', 'entity', 'synthesis')),
    CONSTRAINT chk_wiki_confidence CHECK (confidence IN ('high', 'medium', 'low')),
    CONSTRAINT uq_wiki_slug_workspace UNIQUE (workspace_id, slug)
);

-- Index on workspace_id for fast per-workspace lookups (system prompt + tool queries)
CREATE INDEX idx_wiki_pages_workspace_id ON teemo_wiki_pages(workspace_id);

-- Index on slug for fast read_wiki_page(slug) lookups
CREATE INDEX idx_wiki_pages_slug ON teemo_wiki_pages(slug);

-- Auto-update updated_at on every row modification.
-- Required so the wiki pipeline can detect stale pages without a separate
-- version counter.
CREATE OR REPLACE FUNCTION update_wiki_pages_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_wiki_pages_updated_at
    BEFORE UPDATE ON teemo_wiki_pages
    FOR EACH ROW
    EXECUTE FUNCTION update_wiki_pages_updated_at();


-- ---------------------------------------------------------------------------
-- teemo_wiki_log
-- ---------------------------------------------------------------------------

CREATE TABLE teemo_wiki_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES teemo_workspaces(id) ON DELETE CASCADE,
    operation VARCHAR(32) NOT NULL,
    details JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_wiki_log_operation CHECK (operation IN ('ingest', 'query', 'lint', 'update'))
);

-- Index on workspace_id for per-workspace log queries
CREATE INDEX idx_wiki_log_workspace_id ON teemo_wiki_log(workspace_id);
