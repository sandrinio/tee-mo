---
story_id: "STORY-003-03-migrations"
parent_epic_ref: "EPIC-003 Slice A (Schema Foundation)"
status: "Ready to Bounce"
ambiguity: "🟢 Low"
context_source: "Roadmap §3 ADR-024 (workspace model), ADR-025 (channel binding); EPIC-003 Slice A story inventory; database/migrations/001-004 as pattern reference"
actor: "Backend Dev (writes SQL + tests) + Solo dev (runs SQL in Supabase editor)"
complexity_label: "L2"
---

# STORY-003-03: Migrations 005 + 006 + 007 + `TEEMO_TABLES` Extension

**Complexity: L2** — 3 SQL migration files, one edit to `backend/app/main.py` tuple, one edit to the health-DB test. ~45 minutes. User runs the SQL manually in the Supabase SQL editor.

---

## 1. The Spec (The Contract)

### 1.1 Problem Statement

ADR-024 refactors the workspace model to `1 user : N SlackTeams : N Workspaces : N channel bindings`. The `teemo_workspaces` table from S-01 migration 002 is pre-ADR-024 — it has `slack_bot_user_id` and `encrypted_slack_bot_token` columns that now belong on a new `teemo_slack_teams` table, and it's missing `is_default_for_team` + the `one_default_per_team` partial unique index. ADR-025 needs a new `teemo_workspace_channels` table for explicit channel-to-workspace bindings. All three migrations must land before any downstream epic (EPIC-003 Slice B, EPIC-005 Phase A) can write to the new tables.

### 1.2 Detailed Requirements

- **R1 — Migration 005: Create `teemo_slack_teams`**
  - File: `database/migrations/005_teemo_slack_teams.sql`
  - Table: `teemo_slack_teams` with columns:
    - `slack_team_id VARCHAR(32) PRIMARY KEY` — Slack's team ID (e.g. `T0123ABC456`)
    - `owner_user_id UUID NOT NULL REFERENCES teemo_users(id) ON DELETE CASCADE`
    - `slack_bot_user_id VARCHAR(32) NOT NULL` — the bot's own Slack user ID (for self-message filter per ADR-021)
    - `encrypted_slack_bot_token TEXT NOT NULL` — AES-256-GCM ciphertext (ADR-002/010)
    - `installed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
    - `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
  - Indexes:
    - `CREATE INDEX idx_teemo_slack_teams_owner_user_id ON teemo_slack_teams (owner_user_id)` — for the team list UI (user lookup)
  - `updated_at` trigger reusing the `teemo_set_updated_at()` function from S-01 migration 001.
  - RLS disabled (same pattern as `teemo_workspaces` — backend enforces isolation via `get_current_user_id`).
  - Trailing `DO` block prints `'✓ teemo_slack_teams migration complete. Current row count: {N}'`.

- **R2 — Migration 006: Create `teemo_workspace_channels`**
  - File: `database/migrations/006_teemo_workspace_channels.sql`
  - Table: `teemo_workspace_channels` with columns:
    - `slack_channel_id VARCHAR(32) PRIMARY KEY` — Slack's channel ID (e.g. `C0123ABC456`). PRIMARY KEY ensures a channel is bound to at most one workspace globally (per ADR-025).
    - `workspace_id UUID NOT NULL REFERENCES teemo_workspaces(id) ON DELETE CASCADE`
    - `slack_team_id VARCHAR(32) NOT NULL` — denormalized for consistency checks (no FK — could add one in a follow-up, but it would require migration 005 to be applied first, which it is)
    - `bound_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
  - Indexes:
    - `CREATE INDEX idx_teemo_workspace_channels_workspace_id ON teemo_workspace_channels (workspace_id)` — for workspace → channels lookup (channel chip refresh)
    - `CREATE INDEX idx_teemo_workspace_channels_slack_team_id ON teemo_workspace_channels (slack_team_id)` — for team → channels lookup (dashboard channel picker)
  - RLS disabled.
  - Trailing `DO` block as above.

- **R3 — Migration 007: ALTER `teemo_workspaces` for ADR-024**
  - File: `database/migrations/007_teemo_workspaces_alter.sql`
  - **Safety pre-check** (at the top of the file, wrapped in a `DO` block):
    ```sql
    DO $$
    DECLARE
        stale_count BIGINT;
    BEGIN
        SELECT COUNT(*) INTO stale_count
        FROM teemo_workspaces
        WHERE slack_bot_user_id IS NOT NULL
           OR encrypted_slack_bot_token IS NOT NULL;
        IF stale_count > 0 THEN
            RAISE EXCEPTION 'Migration 007 aborted: % teemo_workspaces row(s) contain data in columns being dropped. Back up and clear them first.', stale_count;
        END IF;
    END $$;
    ```
  - **Drop** the old unique constraint:
    ```sql
    ALTER TABLE teemo_workspaces DROP CONSTRAINT IF EXISTS uq_teemo_workspaces_user_slack_team;
    ```
  - **Drop** columns that move to `teemo_slack_teams`:
    ```sql
    ALTER TABLE teemo_workspaces DROP COLUMN IF EXISTS slack_bot_user_id;
    ALTER TABLE teemo_workspaces DROP COLUMN IF EXISTS encrypted_slack_bot_token;
    ```
  - **Convert** `slack_team_id` from plain VARCHAR to FK:
    ```sql
    ALTER TABLE teemo_workspaces
        ADD CONSTRAINT fk_teemo_workspaces_slack_team
        FOREIGN KEY (slack_team_id) REFERENCES teemo_slack_teams(slack_team_id) ON DELETE CASCADE;
    ```
  - **Add** the default flag:
    ```sql
    ALTER TABLE teemo_workspaces ADD COLUMN IF NOT EXISTS is_default_for_team BOOLEAN NOT NULL DEFAULT FALSE;
    ```
  - **Partial unique index**:
    ```sql
    CREATE UNIQUE INDEX IF NOT EXISTS one_default_per_team
        ON teemo_workspaces (slack_team_id)
        WHERE is_default_for_team = TRUE;
    ```
  - Trailing `DO` block printing `'✓ teemo_workspaces migration 007 complete.'`.

- **R4 — Update `backend/app/main.py` `TEEMO_TABLES` tuple**
  - Current: `("teemo_users", "teemo_workspaces", "teemo_knowledge_index", "teemo_skills")`
  - New: `("teemo_users", "teemo_workspaces", "teemo_knowledge_index", "teemo_skills", "teemo_slack_teams", "teemo_workspace_channels")`
  - This makes `/api/health` check all 6 tables; if any one fails, the aggregate `status` becomes `"degraded"`.

- **R5 — Update `backend/tests/test_health_db.py`** (or equivalent health test file)
  - If the file asserts 4 tables, update to assert 6 tables.
  - Add a test that explicitly checks all 6 keys are present in the `database` response.
  - If the file doesn't exist (rename happened during S-02), search for the existing health-related tests via `grep -rn 'teemo_' backend/tests/` and update them.

- **R6 — User runs the SQL manually**
  - The Dev agent does NOT run the SQL. DevOps agent does NOT run the SQL. The user pastes each of the 3 files, one at a time, into the `https://sulabase.soula.ge` SQL editor and runs them in order (005 → 006 → 007).
  - After running 005 + 006 + 007, the user runs a verification query: `SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name LIKE 'teemo_%' ORDER BY table_name;` — expected output: 6 rows.
  - The user then runs `curl https://teemo.soula.ge/api/health | jq '.database | keys'` and confirms 6 keys are present, all `"ok"`.

- **R7 — Migration file header documentation**
  - Each SQL file header comment must include: purpose, depends on which prior migrations, and which ADR drives it. Match the S-01 pattern.

### 1.3 Out of Scope

- Any Python code that WRITES to the new tables — EPIC-005 Phase A does that for `teemo_slack_teams`, EPIC-003 Slice B does it for workspaces, and `teemo_workspace_channels` writes come in EPIC-005 Phase B.
- RLS policies — disabled per project convention (backend enforces isolation).
- Data migration — the tables are empty; nothing to migrate.
- A migration runner script — user runs SQL manually per Q3 resolved.
- Foreign key on `teemo_workspace_channels.slack_team_id` — left as a plain column for now; can be tightened in a follow-up migration if needed.

### TDD Red Phase: No

Rationale: SQL migrations are declarative. The test we write (R5) is a trivial assertion that the health endpoint returns 6 table keys — it can be added alongside the migration, no Red phase needed.

---

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria

```gherkin
Feature: ADR-024 schema migrations

  Scenario: Migration 005 creates teemo_slack_teams
    Given Supabase SQL editor is open at sulabase.soula.ge
    When I paste and run 005_teemo_slack_teams.sql
    Then the statement completes without error
    And the table teemo_slack_teams exists with columns: slack_team_id, owner_user_id, slack_bot_user_id, encrypted_slack_bot_token, installed_at, updated_at
    And the primary key is slack_team_id
    And the foreign key to teemo_users exists with ON DELETE CASCADE
    And the index idx_teemo_slack_teams_owner_user_id exists
    And the trigger trg_teemo_slack_teams_updated_at exists
    And the DO block prints "✓ teemo_slack_teams migration complete"

  Scenario: Migration 006 creates teemo_workspace_channels
    Given migration 005 succeeded
    When I paste and run 006_teemo_workspace_channels.sql
    Then the table teemo_workspace_channels exists with columns: slack_channel_id, workspace_id, slack_team_id, bound_at
    And the primary key is slack_channel_id
    And the foreign key to teemo_workspaces exists with ON DELETE CASCADE
    And both indexes (workspace_id, slack_team_id) exist

  Scenario: Migration 007 ALTERs teemo_workspaces safely
    Given teemo_workspaces has zero rows with data in slack_bot_user_id or encrypted_slack_bot_token
    When I paste and run 007_teemo_workspaces_alter.sql
    Then the statement completes without error
    And the columns slack_bot_user_id and encrypted_slack_bot_token no longer exist on teemo_workspaces
    And the column is_default_for_team exists with default FALSE
    And the foreign key fk_teemo_workspaces_slack_team exists referencing teemo_slack_teams
    And the partial unique index one_default_per_team exists with WHERE is_default_for_team = TRUE
    And the old uq_teemo_workspaces_user_slack_team constraint no longer exists

  Scenario: Migration 007 aborts if there is stale data
    Given a test row exists in teemo_workspaces with slack_bot_user_id NOT NULL
    When I run 007_teemo_workspaces_alter.sql
    Then the statement raises an exception with message containing "Migration 007 aborted"
    And no columns are dropped

  Scenario: /api/health reports 6 teemo_* tables after migrations
    Given all 3 migrations have been applied to sulabase.soula.ge
    And the backend is restarted (or TEEMO_TABLES update is deployed)
    When I curl https://teemo.soula.ge/api/health
    Then the response status is 200
    And the response JSON database has exactly 6 keys
    And the keys are: teemo_users, teemo_workspaces, teemo_knowledge_index, teemo_skills, teemo_slack_teams, teemo_workspace_channels
    And every value is "ok"
    And the top-level status is "ok"

  Scenario: The partial unique index enforces one default per team
    Given teemo_slack_teams has a row "T-TEST-001"
    And teemo_workspaces has 2 rows under that team
    When I set is_default_for_team = TRUE on both rows
    Then the second UPDATE fails with a unique constraint violation on one_default_per_team
```

### 2.2 Verification Steps (Manual)

**User (Supabase SQL editor):**
- [ ] Open SQL editor at `https://sulabase.soula.ge`
- [ ] Run `database/migrations/005_teemo_slack_teams.sql` — expect success + `✓` notice
- [ ] Run `database/migrations/006_teemo_workspace_channels.sql` — expect success + `✓` notice
- [ ] Run `database/migrations/007_teemo_workspaces_alter.sql` — expect success + `✓` notice
- [ ] Run verification query:
  ```sql
  SELECT table_name FROM information_schema.tables
  WHERE table_schema='public' AND table_name LIKE 'teemo_%'
  ORDER BY table_name;
  ```
  Expect 6 rows: `teemo_knowledge_index`, `teemo_skills`, `teemo_slack_teams`, `teemo_users`, `teemo_workspace_channels`, `teemo_workspaces`
- [ ] Spot-check column list:
  ```sql
  SELECT column_name, data_type, is_nullable FROM information_schema.columns
  WHERE table_name = 'teemo_workspaces' AND table_schema = 'public'
  ORDER BY ordinal_position;
  ```
  Expect `is_default_for_team` present, `slack_bot_user_id` NOT present, `encrypted_slack_bot_token` NOT present.
- [ ] Spot-check partial unique index:
  ```sql
  SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'teemo_workspaces';
  ```
  Expect `one_default_per_team` index with a `WHERE` clause.

**DevOps agent (from command line, after user + Coolify redeploy):**
- [ ] `curl -s https://teemo.soula.ge/api/health | jq '.database | keys | length'` returns `6`
- [ ] `curl -s https://teemo.soula.ge/api/health | jq '.database'` lists all 6 keys with `"ok"` values
- [ ] `curl -s https://teemo.soula.ge/api/health | jq '.status'` returns `"ok"`
- [ ] Backend test suite passes locally: `cd backend && /Users/ssuladze/Documents/Dev/SlaXadeL/backend/.venv/bin/python -m pytest tests/ -v` — existing 22 tests still green + the updated health-DB test now asserts 6 keys

---

## 3. The Implementation Guide (AI-to-AI)

### 3.0 Environment Prerequisites

| Prerequisite | Value | Verified? |
|-------------|-------|-----------|
| **STORY-003-02** | `https://teemo.soula.ge` is live and serving 4-table health | [ ] |
| **Supabase** | User has access to `https://sulabase.soula.ge` SQL editor | [x] |
| **`teemo_workspaces` empty** | Zero rows (no workspace create path shipped yet) — verified via the DO-block pre-check in 007 | [ ] (verified at runtime) |
| **S-01 migrations** | `teemo_set_updated_at()` function exists from migration 001 | [x] |

### 3.1 Migration 005 — Full SQL

```sql
-- =============================================================================
-- Migration: 005_teemo_slack_teams
-- Purpose:   Create teemo_slack_teams per ADR-024. One row per Slack workspace
--            installation. Holds the encrypted bot token and the bot's user ID
--            for self-message filter (ADR-021).
-- Depends on: 001_teemo_users (for FK to teemo_users)
-- ADR:       ADR-024 (Workspace Model — 1 user : N SlackTeams : N Workspaces)
-- =============================================================================

CREATE TABLE IF NOT EXISTS teemo_slack_teams (
    slack_team_id              VARCHAR(32) PRIMARY KEY,        -- Slack team ID (e.g. "T0123ABC456")
    owner_user_id              UUID NOT NULL REFERENCES teemo_users(id) ON DELETE CASCADE,
    slack_bot_user_id          VARCHAR(32) NOT NULL,           -- Bot's Slack user ID (self-message filter per ADR-021)
    encrypted_slack_bot_token  TEXT NOT NULL,                  -- AES-256-GCM ciphertext (ADR-002/010)
    installed_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Owner lookup for the team list UI
CREATE INDEX IF NOT EXISTS idx_teemo_slack_teams_owner_user_id
    ON teemo_slack_teams (owner_user_id);

-- updated_at trigger (reuses function from 001_teemo_users)
DROP TRIGGER IF EXISTS trg_teemo_slack_teams_updated_at ON teemo_slack_teams;
CREATE TRIGGER trg_teemo_slack_teams_updated_at
    BEFORE UPDATE ON teemo_slack_teams
    FOR EACH ROW
    EXECUTE FUNCTION teemo_set_updated_at();

-- RLS disabled — backend enforces isolation via get_current_user_id + assert_team_owner
ALTER TABLE teemo_slack_teams DISABLE ROW LEVEL SECURITY;

DO $$
DECLARE
    cnt BIGINT;
BEGIN
    SELECT COUNT(*) INTO cnt FROM teemo_slack_teams;
    RAISE NOTICE '✓ teemo_slack_teams migration complete. Current row count: %', cnt;
END $$;
```

### 3.2 Migration 006 — Full SQL

```sql
-- =============================================================================
-- Migration: 006_teemo_workspace_channels
-- Purpose:   Create teemo_workspace_channels per ADR-024 + ADR-025. Explicit
--            channel-to-workspace bindings. PRIMARY KEY on slack_channel_id
--            enforces one-workspace-per-channel globally.
-- Depends on: 002_teemo_workspaces (for FK), 005_teemo_slack_teams (soft dep)
-- ADR:       ADR-024 (workspace model), ADR-025 (explicit channel binding)
-- =============================================================================

CREATE TABLE IF NOT EXISTS teemo_workspace_channels (
    slack_channel_id  VARCHAR(32) PRIMARY KEY,                         -- Slack channel ID (e.g. "C0123ABC456")
    workspace_id      UUID NOT NULL REFERENCES teemo_workspaces(id) ON DELETE CASCADE,
    slack_team_id     VARCHAR(32) NOT NULL,                            -- Denormalized for consistency checks
    bound_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- workspace → channels lookup (channel chip refresh in dashboard)
CREATE INDEX IF NOT EXISTS idx_teemo_workspace_channels_workspace_id
    ON teemo_workspace_channels (workspace_id);

-- team → channels lookup (dashboard channel picker, binding status refresh)
CREATE INDEX IF NOT EXISTS idx_teemo_workspace_channels_slack_team_id
    ON teemo_workspace_channels (slack_team_id);

ALTER TABLE teemo_workspace_channels DISABLE ROW LEVEL SECURITY;

DO $$
DECLARE
    cnt BIGINT;
BEGIN
    SELECT COUNT(*) INTO cnt FROM teemo_workspace_channels;
    RAISE NOTICE '✓ teemo_workspace_channels migration complete. Current row count: %', cnt;
END $$;
```

### 3.3 Migration 007 — Full SQL

```sql
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
```

### 3.4 `backend/app/main.py` edit

Find the `TEEMO_TABLES` tuple (should be a module-level constant near the top of the file or near the health endpoint) and update:

```diff
- TEEMO_TABLES = ("teemo_users", "teemo_workspaces", "teemo_knowledge_index", "teemo_skills")
+ TEEMO_TABLES = (
+     "teemo_users",
+     "teemo_workspaces",
+     "teemo_knowledge_index",
+     "teemo_skills",
+     "teemo_slack_teams",
+     "teemo_workspace_channels",
+ )
```

### 3.5 Test update

Find the health-DB test file (likely `backend/tests/test_health_db.py` or `backend/tests/test_health.py`). Update any assertion that expects 4 tables to expect 6. Add:

```python
def test_health_reports_all_six_teemo_tables():
    """After ADR-024 migrations, /api/health must list all 6 teemo_* tables."""
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert set(body["database"].keys()) == {
        "teemo_users",
        "teemo_workspaces",
        "teemo_knowledge_index",
        "teemo_skills",
        "teemo_slack_teams",
        "teemo_workspace_channels",
    }
    for table_name, status in body["database"].items():
        assert status == "ok", f"{table_name} is {status}"
```

### 3.6 Files to Modify

| File | Change |
|------|--------|
| `database/migrations/005_teemo_slack_teams.sql` | **NEW** |
| `database/migrations/006_teemo_workspace_channels.sql` | **NEW** |
| `database/migrations/007_teemo_workspaces_alter.sql` | **NEW** |
| `backend/app/main.py` | **EDIT** — `TEEMO_TABLES` tuple +2 entries |
| `backend/tests/test_health_db.py` (or equivalent) | **EDIT** — expand 4 → 6 assertion |

### 3.7 Execution order

1. Dev agent writes all 5 files above + commits.
2. Dev agent runs the local pytest suite. It will **fail** on the 6-table assertion because the migrations haven't been applied to the Supabase instance yet. Dev agent notes this in the report — this is expected until the user runs SQL + Coolify redeploys.
3. Dev agent hands off SQL files to the user via the Dev report: "Run these 3 SQL files in the Supabase SQL editor in order: 005, 006, 007. Then paste back the output of the verification query from §2.2."
4. User runs the SQL. Reports back success + verification query output.
5. Dev agent re-runs pytest — should now pass. (Or, if the test hits live Supabase, it will pass as soon as the user runs the SQL without needing a redeploy.)
6. Dev agent hands off to DevOps agent for merge. Post-merge, Coolify auto-deploys; `curl https://teemo.soula.ge/api/health` should now report 6 tables.

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations

| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Unit tests | 0 — N/A | |
| Component tests | 0 — N/A | |
| E2E / acceptance tests | 0 — N/A | |
| Integration tests | 1 (updated existing test) | `/api/health` returns 6-table database map |

### 4.2 Definition of Done

- [ ] 3 SQL files exist in `database/migrations/` with ADR-024 refactor implementation.
- [ ] `backend/app/main.py` `TEEMO_TABLES` tuple has 6 entries.
- [ ] Health-DB test asserts 6 tables present in response.
- [ ] User has run all 3 migrations against `sulabase.soula.ge` via SQL editor.
- [ ] User verification query returns 6 rows for `teemo_*` tables.
- [ ] Column spot-check confirms `is_default_for_team` present, `slack_bot_user_id` and `encrypted_slack_bot_token` absent.
- [ ] Partial unique index `one_default_per_team` exists with `WHERE` clause.
- [ ] `curl https://teemo.soula.ge/api/health` returns 6 keys all `"ok"` AFTER the DevOps post-merge Coolify redeploy.
- [ ] Backend test suite passes locally (post-migration).
- [ ] DO-block pre-check in migration 007 aborted in a dry run with fake stale data — verified safe. (Optional — skip if time-bound.)

---

## Token Usage

| Agent | Input | Output | Total |
|-------|-------|--------|-------|
| Developer | 17 | 980 | 997 |
