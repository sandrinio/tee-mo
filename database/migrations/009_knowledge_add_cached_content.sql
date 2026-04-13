-- STORY-006-10: Add cached_content column to teemo_knowledge_index.
--
-- Stores the plain text content extracted from Google Drive at index time.
-- Enables cache-first reads in the agent tool (read_drive_file) so Drive API
-- calls are skipped when content is already cached.
--
-- NULL means not yet cached (files indexed before this migration).
-- The agent self-heals by backfilling cached_content on the next read.

ALTER TABLE teemo_knowledge_index
    ADD COLUMN IF NOT EXISTS cached_content TEXT;
