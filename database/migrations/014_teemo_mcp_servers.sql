-- Migration 014: teemo_mcp_servers
-- STORY-012-01 (MCP Service Layer) — SPRINT-17
--
-- Stores MCP (Model Context Protocol) server registrations for each workspace.
-- Supports two transports: 'sse' (Server-Sent Events) and 'streamable_http'
-- (Streamable HTTP — default, used by GitHub MCP, Azure DevOps Remote MCP, etc).
--
-- Security:
--   - workspace_id FK ON DELETE CASCADE — removing a workspace removes all its MCP servers.
--   - headers_encrypted: JSONB of {"Header-Name": "<base64-ciphertext>"} — each header
--     value is encrypted individually with AES-256-GCM via app.core.encryption.encrypt().
--     Plaintext header values are NEVER stored.
--   - URL validation (HTTPS-only + IP blacklist) is enforced at the application layer
--     (app.services.mcp_service.validate_mcp_server_input).
--   - Transport CHECK constraint prevents any unrecognised transport from being inserted.
--
-- Idempotent: safe to run multiple times (IF NOT EXISTS guards everywhere).
--
-- Rollback:
--   DROP TABLE IF EXISTS teemo_mcp_servers CASCADE;

CREATE TABLE IF NOT EXISTS teemo_mcp_servers (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id     UUID        NOT NULL REFERENCES teemo_workspaces(id) ON DELETE CASCADE,
    name             TEXT        NOT NULL,
    transport        TEXT        NOT NULL CHECK (transport IN ('sse', 'streamable_http')),
    url              TEXT        NOT NULL,
    headers_encrypted JSONB      NOT NULL DEFAULT '{}'::jsonb,
    is_active        BOOLEAN     NOT NULL DEFAULT true,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (workspace_id, name)
);

CREATE INDEX IF NOT EXISTS idx_teemo_mcp_servers_workspace_id
    ON teemo_mcp_servers (workspace_id);

DO $$ BEGIN
    RAISE NOTICE 'teemo_mcp_servers ready (% rows)', (SELECT count(*) FROM teemo_mcp_servers);
END $$;
