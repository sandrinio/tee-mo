# Tee-Mo Database Migrations

All Tee-Mo tables are prefixed with `teemo_` to coexist with other apps on the shared self-hosted Supabase instance.

## Running Migrations

Migrations are plain SQL. Run them in numeric order via the Supabase Studio SQL Editor, `psql`, or any other Postgres client. Each file is **idempotent** (safe to run multiple times).

```bash
# Example via psql (assuming DATABASE_URL is set)
psql "$DATABASE_URL" -f database/migrations/001_teemo_users.sql
psql "$DATABASE_URL" -f database/migrations/002_teemo_workspaces.sql
psql "$DATABASE_URL" -f database/migrations/003_teemo_knowledge_index.sql
psql "$DATABASE_URL" -f database/migrations/004_teemo_skills.sql
```

Or paste each file's contents into Supabase Studio's SQL Editor and click **Run**.

Every migration ends with a `RAISE NOTICE` showing the row count after completion — a quick sanity check that the table exists and is readable.

## Migration Inventory

| # | File | Creates | Depends On |
|---|------|---------|------------|
| 001 | `001_teemo_users.sql` | `teemo_users`, `teemo_set_updated_at()` function | — |
| 002 | `002_teemo_workspaces.sql` | `teemo_workspaces` | 001 |
| 003 | `003_teemo_knowledge_index.sql` | `teemo_knowledge_index`, `teemo_enforce_knowledge_index_cap()` trigger | 002 |
| 004 | `004_teemo_skills.sql` | `teemo_skills` | 002 |
| 005 | `005_teemo_slack_teams.sql` | `teemo_slack_teams`, `teemo_slack_team_members` | 002 |
| 006 | `006_teemo_workspace_channels.sql` | `teemo_workspace_channels` | 002, 005 |
| 007 | `007_teemo_workspaces_alter.sql` | adds columns to `teemo_workspaces` | 002 |
| 008 | `008_workspaces_add_key_mask.sql` | adds `byok_key_mask` column | 002 |
| 009 | `009_knowledge_add_cached_content.sql` | adds `cached_content` column | 003 |
| 010 | `010_teemo_documents.sql` | `teemo_documents` | 002 |
| 011 | `011_teemo_wiki_pages.sql` | `teemo_wiki_pages` | 002 |
| 012 | `012_increase_document_cap.sql` | raises document cap trigger to 100 | 010 |
| 012a | `012a_teemo_automations.sql` | `teemo_automations` (orig. ordering collided at 012; renumbered 2026-04-26 — see *Numbering Fix Note* below) | 002 |
| 013 | `013_add_bot_persona.sql` | adds `bot_persona` column | 002 |
| 20260421174500 | `20260421174500_create_claim_pending_docs_rpc.sql` | `claim_pending_docs` RPC | 010 |
| 014 | `014_teemo_mcp_servers.sql` *(planned, SPRINT-17)* | `teemo_mcp_servers` (SSE + Streamable HTTP MCP servers) | 002 |

### Numbering Fix Note (2026-04-26)

Two migrations were originally numbered `012_*` (`012_increase_document_cap.sql` and the now-renamed `012_teemo_automations.sql`). They shipped in different sprints (S-12 and earlier) and were both applied to production. Because migrations here are idempotent + manually pasted (no DB-side `_migrations` filename tracker), renaming the second collider to `012a_teemo_automations.sql` is purely cosmetic — production state unaffected. New numbered migrations (`014` onward) continue the sequential scheme.

## Tables

| Table | Purpose | Charter Ref |
|-------|---------|------------|
| `teemo_users` | Account holders for the dashboard | §4 |
| `teemo_workspaces` | Slack team installations, one user → many workspaces | §4 + ADR-011 |
| `teemo_knowledge_index` | Up to 15 Google Drive files per workspace | §4 + ADR-007 |
| `teemo_skills` | Chat-created instruction bundles for the agent | §4 + ADR-023 |

## Security Model

- **RLS is disabled on all teemo_ tables.** Tee-Mo uses custom JWT auth (Charter §5.3), not Supabase Auth, so RLS policies would need custom JWT claim mapping that isn't worth the complexity for a hackathon.
- **The backend enforces all isolation** via explicit `WHERE user_id = ?` and `WHERE workspace_id = ?` clauses in every query. This is the Charter §2.4 "Security First" rule: workspace isolation is enforced in application code against authenticated requests.
- **Only the service_role key is used** from the backend. The anon key is never used by Tee-Mo's backend.
- **Defence in depth**: the 15-file cap is enforced by a DB-level trigger (`teemo_enforce_knowledge_index_cap`) AS WELL AS backend-level count check, so even a bug in the API can't exceed the limit.

## Shared Instance Notes

This Supabase instance (`sulabase.soula.ge`) hosts multiple apps. As of sprint 1 planning, there are **49 existing tables**, none prefixed with `teemo_`. Always prefix new Tee-Mo tables, functions, triggers, and RPC calls with `teemo_` to prevent collision.

## Re-running / Resetting

All migrations use `CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`, `DROP TRIGGER IF EXISTS`, and `CREATE OR REPLACE FUNCTION` — you can re-run the whole set safely without data loss.

To fully reset Tee-Mo's tables (destructive):

```sql
DROP TABLE IF EXISTS teemo_skills CASCADE;
DROP TABLE IF EXISTS teemo_knowledge_index CASCADE;
DROP TABLE IF EXISTS teemo_workspaces CASCADE;
DROP TABLE IF EXISTS teemo_users CASCADE;
DROP FUNCTION IF EXISTS teemo_enforce_knowledge_index_cap() CASCADE;
DROP FUNCTION IF EXISTS teemo_set_updated_at() CASCADE;
```
