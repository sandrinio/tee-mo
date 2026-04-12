-- STORY-004-01: Add key_mask column to teemo_workspaces
--
-- The key_mask stores a short visual hint (e.g. "sk-ab...xyz9") computed
-- at key-save time and stored alongside encrypted_api_key. This avoids
-- decrypting the key at GET /api/workspaces/{id}/keys time, keeping
-- read operations fast and the plaintext key in memory only during writes.
--
-- VARCHAR(20) is sufficient for masks of the form:
--   short keys (<=8 chars): first 2 + "..." + last 2 = 7 chars max
--   long keys (>8 chars):   first 4 + "..." + last 4 = 11 chars max
--
-- ADR-002: The plaintext key NEVER enters this column — only the mask.

ALTER TABLE teemo_workspaces ADD COLUMN IF NOT EXISTS key_mask VARCHAR(20);
