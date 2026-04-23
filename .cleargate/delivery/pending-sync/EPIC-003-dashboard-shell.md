---
epic_id: "EPIC-003"
status: "Active"
ambiguity: "🟢"
context_source: "PROPOSAL-001-teemo-platform.md"
owner: "Solo dev"
target_date: "2026-04-13"
created_at: "2026-04-11T00:00:00Z"
updated_at: "2026-04-24T00:00:00Z"
created_at_version: "vbounce-backlog"
updated_at_version: "cleargate-migration-2026-04-24"
server_pushed_at_version: null
draft_tokens:
  input: null
  output: null
  cache_read: null
  cache_creation: null
  model: null
  sessions: []
cached_gate_result:
  pass: null
  failing_criteria: []
  last_gate_check: null
---

> **Ported from V-Bounce.** Original: `product_plans.vbounce-archive/backlog/EPIC-003_dashboard_shell/EPIC-003_dashboard_shell.md`. Carried forward during ClearGate migration 2026-04-24.

> **⚠ Post-ADR-026 reshape (2026-04-12).** EPIC-003 is now split into two slices across two sprints, with EPIC-005 Phase A (Slack OAuth install) landing between them. The dev-only manual team-create path is ELIMINATED. Original open questions Q1 / Q2 / Q3 / Q4 / Q5 / Q6 / Q7 / Q8 / Q9 / Q10 are resolved (see §8). See §5 Decomposition for the new Slice A / Slice B story inventory.
>
> - **Slice A — Schema Foundation (S-03)**: Migrations 005/006/007 + TEEMO_TABLES extension + PyJWT BUG fix. Lands alongside ADR-026 deploy story in the same sprint. No routes, no frontend.
> - **Slice B — Workspace CRUD (S-05)**: Backend workspace routes + frontend `/app/teams/$teamId` workspace list + create/rename modals + make-default toggle. Attaches to real `teemo_slack_teams` rows created by EPIC-005 Phase A in S-04.

# EPIC-003: Dashboard Shell + SlackTeam / Workspace CRUD

## 1. Problem & Value

### 1.1 The Problem

After registering (EPIC-002), a user lands on a placeholder `/app` page that says "Welcome to Tee-Mo. Signed in as <email>." and offers no way to do anything else. Downstream epics — **EPIC-004** (BYOK), **EPIC-005** (Slack), **EPIC-006** (Drive), **EPIC-007** (AI Agent), **EPIC-008** (Wizard) — all require a **Workspace** entity (a knowledge silo under a SlackTeam) to attach their features to, and a **SlackTeam → Workspace → ChannelBinding** data shape per ADR-024. Without this shell, every subsequent feature has nothing to dock onto.

### 1.2 The Solution

Ship the **Dashboard Shell** and the **team/workspace CRUD foundation** (schema + API + UI) so the five downstream epics can plug in without rework:

1. **Schema foundation** — three new migrations that refactor the workspace model to ADR-024's `1 user : N SlackTeams : N Workspaces : N channel bindings` shape (create `teemo_slack_teams`, create `teemo_workspace_channels`, ALTER `teemo_workspaces` to drop slack bot fields and add `is_default_for_team` + partial unique index).
2. **Backend CRUD API** — authenticated REST endpoints for listing/creating/renaming/deleting SlackTeams and Workspaces, scoped to the current user via `get_current_user_id`.
3. **Frontend shell** — replace the `/app` placeholder body with a two-level navigation: **Team list** (landing after login) → **Team detail** showing Workspaces under that team, with "New Workspace" / "Rename" / "Make default" actions.
4. **No dev-only path — real Slack install from Day 2** — per ADR-026, deploy is pulled forward and EPIC-005 Phase A sandwiches between EPIC-003's two slices. The `/app` team list's "Install Slack" button is a real CTA from S-04, not a disabled placeholder. Workspace CRUD in Slice B attaches to real `teemo_slack_teams` rows. This eliminates the dev-only spoofing vector, the dead-code cleanup burden, and the "dev vs prod" mental model cost.
5. **Trailing tech-debt fix** — BUG-20260411-001 (PyJWT module-level options leak causing test-order flake) resolved in Slice A (S-03) because every new backend route in S-04 and S-05 lands more tests into the same suite, and the flake would only get worse.

### 1.3 Success Metrics (North Star)

- A fresh-registered user can navigate `/login → /app (team list) → create dev-only team → team detail → create workspace → rename workspace → make it default` entirely in the browser with zero backend or DB intervention.
- All three `TEEMO_TABLES` expansion targets (`teemo_slack_teams`, `teemo_workspace_channels`, updated `teemo_workspaces`) show `"ok"` in `GET /api/health`.
- Backend test suite grows from 22 → ~40 tests, all passing deterministically (no order-sensitive flakes — BUG-20260411 fixed in-sprint).
- `npm run build` exits 0 with zero TypeScript errors after the three new routes land, and `routeTree.gen.ts` includes `/app`, `/app/teams/$teamId`, `/app/teams/$teamId/workspaces/$wsId` (or a flatter equivalent — see §8 Q5).
- No downstream epic (004 / 005 / 006 / 007 / 008) requires a schema change to proceed after EPIC-003 lands.

---

## 2. Scope Boundaries

### ✅ IN-SCOPE (Build This)

**Schema**
- [ ] Migration 005: `teemo_slack_teams` (PK `slack_team_id VARCHAR(32)`, `owner_user_id UUID FK`, `slack_bot_user_id VARCHAR(32)`, `encrypted_slack_bot_token TEXT`, `installed_at`, `updated_at` + `owner_user_id` index + updated_at trigger)
- [ ] Migration 006: `teemo_workspace_channels` (PK `slack_channel_id VARCHAR(32)`, `workspace_id UUID FK`, `slack_team_id VARCHAR(32)`, `bound_at` + `workspace_id` index + `slack_team_id` index)
- [ ] Migration 007: ALTER `teemo_workspaces` — drop `slack_bot_user_id` + `encrypted_slack_bot_token` columns, drop `uq_teemo_workspaces_user_slack_team` constraint, convert `slack_team_id` to FK → `teemo_slack_teams.slack_team_id` with ON DELETE CASCADE, add `is_default_for_team BOOLEAN NOT NULL DEFAULT FALSE`, create partial unique index `one_default_per_team ON (slack_team_id) WHERE is_default_for_team = TRUE`
- [ ] Update `backend/app/main.py` `TEEMO_TABLES` tuple to include `teemo_slack_teams` and `teemo_workspace_channels`
- [ ] Health endpoint returns 6 tables instead of 4 (tests updated)

**Backend API**
- [ ] `backend/app/models/slack_team.py`: `SlackTeam` response model, `SlackTeamCreateDevOnly` request model
- [ ] `backend/app/models/workspace.py`: `Workspace` response model (no secrets — omit `encrypted_api_key`, `encrypted_google_refresh_token`), `WorkspaceCreate` request (name + slack_team_id), `WorkspaceUpdate` request (name only)
- [ ] `backend/app/api/routes/slack_teams.py`:
  - `GET /api/slack-teams` — list current user's SlackTeams
  - `POST /api/slack-teams` — **dev-only** create (gated on `settings.debug == True`, returns 403 otherwise); accepts `{slack_team_id, slack_bot_user_id, team_name}`, writes a row with a placeholder encrypted token
- [ ] `backend/app/api/routes/workspaces.py`:
  - `GET /api/slack-teams/{team_id}/workspaces` — list workspaces under a team (scoped to current user as team owner)
  - `POST /api/slack-teams/{team_id}/workspaces` — create a new workspace (name); auto-sets `is_default_for_team = TRUE` if it's the first workspace under that team
  - `GET /api/workspaces/{ws_id}` — fetch a single workspace (authorization via team ownership)
  - `PATCH /api/workspaces/{ws_id}` — rename (accepts `{name}` only)
  - `POST /api/workspaces/{ws_id}/make-default` — atomic default swap (transaction: clear existing default under the team, set this one)
- [ ] Mount both routers in `backend/app/main.py` `include_router` calls
- [ ] Authorization helper: `async def assert_team_owner(team_id, user_id)` — raises 403 if `teemo_slack_teams.owner_user_id != user_id`
- [ ] Backend integration tests (new file `backend/tests/test_slack_teams_routes.py` + `test_workspaces_routes.py`) covering happy path, 403 cross-user access, 404 missing, partial-unique-constraint violation on default swap, cascade on team delete, rename

**Frontend — store and API wrappers**
- [ ] `frontend/src/lib/api.ts` — add 7 typed wrappers: `listSlackTeams`, `createSlackTeamDevOnly`, `listWorkspaces(teamId)`, `createWorkspace(teamId, name)`, `getWorkspace(id)`, `renameWorkspace(id, name)`, `makeWorkspaceDefault(id)`
- [ ] TanStack Query hooks (preferred over a new Zustand store for server state — Zustand already owns auth, this is cached server state): `useSlackTeamsQuery`, `useWorkspacesQuery(teamId)`, `useWorkspaceQuery(id)`, `useCreateWorkspaceMutation`, `useRenameWorkspaceMutation`, `useMakeDefaultMutation` (placed in `frontend/src/hooks/useWorkspaces.ts` or similar)

**Frontend — routes and UI**
- [ ] Replace `frontend/src/routes/app.tsx` body with the team-list view: wrapped in `<ProtectedRoute>`, header bar with "Tee-Mo" logo + user email + `<SignOutButton>`, main content is the team list
- [ ] Team list UI:
  - Empty state (zero teams): show a large empty-state card with a **disabled** "Install Slack" primary button ("Coming in Sprint 5"), a helper text, and **if `DEBUG=true` is exposed to the frontend** a secondary **"Create team manually (dev)"** button that opens a modal
  - Non-empty: grid of team cards (per Design Guide §9.2), each showing team name + workspace count + "Open →" link
- [ ] Dev-only create-team modal: native `<form>` with 3 fields (`slack_team_id` placeholder "T0123ABC456", `team_name`, `slack_bot_user_id` placeholder "U0123ABC456"), submit calls `createSlackTeamDevOnly`, shows backend error inline
- [ ] New route `frontend/src/routes/app.teams.$teamId.tsx` (or flatter naming — see §8 Q5):
  - Header with team name + breadcrumb "← Teams"
  - Workspace list (grid of cards per Design Guide §9.2)
  - "+ New Workspace" primary button opens create modal
  - Each workspace card shows: name, "Default for DMs" badge if `is_default_for_team == true`, setup status chips (for S-03: all chips show "Not connected" — EPIC-004/005/006 fill them in later), "Rename" + "Make default" actions
- [ ] Create workspace modal: native `<form>` with 1 field (`name`), submit calls `createWorkspace(teamId, name)`
- [ ] Rename workspace modal: same shape, pre-filled
- [ ] "Make default" action: optimistic UI update + mutation + error toast rollback (NO toast library — use inline error card like login/register do)

**BUG fix**
- [ ] Migrate `backend/app/core/security.py::decode_token` to use a scoped `jwt.PyJWT()` instance per BUG-20260411-001's proposed fix. Add a regression-lock test in `test_security.py` that verifies module-level `jwt.decode(options={...})` mutation does NOT leak into `decode_token`. Run `pytest tests/` 10× with `pytest-randomly` enabled to confirm stability.

### ❌ OUT-OF-SCOPE (Do NOT Build This)

- **Real Slack OAuth** — deferred to EPIC-005. EPIC-003's "Install Slack" button is disabled.
- **Slack Bot Token Storage** — EPIC-005 owns the real token; EPIC-003's dev-only endpoint writes a placeholder string.
- **Channel binding CRUD** — deferred to EPIC-005 (needs Slack API access). Workspace card shows "Not connected" chip where channels would go.
- **BYOK key input** — deferred to EPIC-004. Workspace card shows "Not connected" chip.
- **Google Drive picker + refresh token** — deferred to EPIC-006.
- **4-step wizard** — deferred to EPIC-008. EPIC-003 ships raw CRUD only.
- **Workspace delete** — destructive + cascades to knowledge_index + skills. Defer until after EPIC-007 ships (by then there's real data to worry about). Rename only in EPIC-003.
- **SlackTeam rename / delete** — dev-only create is enough. Deleting a SlackTeam cascades to ALL workspaces, ALL channel bindings — too risky to ship before EPIC-005 real OAuth lands.
- **Moving a workspace between teams** — not supported. Schema enforces one-team-per-workspace via FK.
- **Workspace name uniqueness** — no constraint. Users can have two "Marketing" workspaces under one team if they want; we'll differentiate by UUID in the URL.
- **Toasts, animations, polish** — Tee-Mo design system `Card` + `Button` + inline `role="alert"` error blocks only (matches S-02 pattern). Framer Motion, Radix toasts, etc. are ADR-022 OUT.
- **Skills tab on workspace card** — Charter §1.2 explicitly excludes skills UI. Skills are chat-only per ADR-023.
- **E2E Playwright tests** — same as S-02: manual verification + unit/integration tests are the gate.

---

## 3. Context

### 3.1 User Personas

- **Solo developer (primary — you)**: Needs to demo "register → workspace exists → downstream epics plug in" without waiting for EPIC-005. The dev-only team-create path exists for your benefit.
- **Hackathon judge (secondary — downstream)**: Will see this UI during EPIC-008 polish. The dev path is gone by then; they see Slack install → real team → create workspace → ...

### 3.2 User Journey (Happy Path — Dev / Pre-EPIC-005)

```mermaid
flowchart LR
    A[/login] --> B[/register]
    B --> C[/app team list - empty state]
    C -->|dev Create team manually| D[/app team list - 1 team]
    D -->|click team card| E[/app/teams/$tid workspace list - empty]
    E -->|+ New Workspace| F[/app/teams/$tid workspace list - 1 default ws]
    F -->|Rename| F
    F -->|+ New Workspace| G[/app/teams/$tid - 2 ws, first is default]
    G -->|Make default on second| H[/app/teams/$tid - 2 ws, second is default]
```

### 3.3 Constraints

| Type | Constraint |
|------|------------|
| **Performance** | Dashboard initial load target < 500ms on dev (one TanStack Query to `/api/slack-teams`, renders immediately with cached auth cookie). |
| **Security** | All routes require `get_current_user_id` dep. Cross-user access returns 403 (not 404 — avoid info leak). Dev-only team-create endpoint gated on `settings.debug == True` (fails closed in prod). `encrypted_slack_bot_token` never returned to the frontend in any response. |
| **Tech Stack** | Must reuse TanStack Query (no Zustand store for server state), `lib/api.ts` typed wrappers (no raw `fetch` per FLASHCARDS.md), Tailwind 4 built-in tokens only (no new `@theme` tokens), Design Guide §6 primitives (`Button`, `Card`, `Badge`). |
| **Schema** | Migrations are forward-only. Migrations 005/006/007 are new files; migrations 001-004 are immutable (already shipped in S-01). ALTER of `teemo_workspaces` assumes zero existing rows (verified — no workspaces have been created yet). |
| **Routing** | TanStack Router file-based. New route files require vite-build-first workaround per FLASHCARDS.md `tsc -b && vite build` chicken-and-egg. Do NOT hand-edit `routeTree.gen.ts`. |
| **Auth** | All new backend routes mount under `/api` and rely on the httpOnly cookie set by EPIC-002. `samesite=lax` is already in place (FLASHCARDS.md). |

---

## 4. Technical Context

### 4.1 Affected Areas

| Area | Files / Modules | Change Type |
|------|-----------------|-------------|
| Database migrations | `database/migrations/005_teemo_slack_teams.sql` | **New** |
| Database migrations | `database/migrations/006_teemo_workspace_channels.sql` | **New** |
| Database migrations | `database/migrations/007_teemo_workspaces_alter.sql` | **New** |
| Backend health | `backend/app/main.py` (`TEEMO_TABLES` tuple + router mounts) | Modify |
| Backend models | `backend/app/models/slack_team.py` | **New** |
| Backend models | `backend/app/models/workspace.py` | **New** |
| Backend models | `backend/app/models/__init__.py` | Modify (export new models) |
| Backend routes | `backend/app/api/routes/slack_teams.py` | **New** |
| Backend routes | `backend/app/api/routes/workspaces.py` | **New** |
| Backend routes | `backend/app/api/routes/__init__.py` | Modify (register new routers) |
| Backend deps | `backend/app/api/deps.py` — may add `assert_team_owner` helper OR put it in each route file | Modify (additive) |
| Backend security | `backend/app/core/security.py::decode_token` — BUG-20260411 fix | Modify (refactor to `jwt.PyJWT()` instance) |
| Backend tests | `backend/tests/test_slack_teams_routes.py` | **New** |
| Backend tests | `backend/tests/test_workspaces_routes.py` | **New** |
| Backend tests | `backend/tests/test_security.py` — regression-lock for PyJWT | Modify (add 1 test) |
| Frontend API wrappers | `frontend/src/lib/api.ts` — add 7 wrappers + `SlackTeam` + `Workspace` types | Modify |
| Frontend hooks | `frontend/src/hooks/useWorkspaces.ts` (or similar) — TanStack Query hooks | **New** |
| Frontend routes | `frontend/src/routes/app.tsx` — replace body | Modify |
| Frontend routes | `frontend/src/routes/app.teams.$teamId.tsx` | **New** |
| Frontend routes | `frontend/src/routeTree.gen.ts` | **Auto-regenerated** — do NOT hand-edit |
| Frontend components | `frontend/src/components/dashboard/TeamCard.tsx` | **New** (or inline) |
| Frontend components | `frontend/src/components/dashboard/WorkspaceCard.tsx` | **New** (or inline) |
| Frontend components | `frontend/src/components/dashboard/CreateTeamDevModal.tsx` | **New** (dev-only) |
| Frontend components | `frontend/src/components/dashboard/CreateWorkspaceModal.tsx` | **New** |
| Frontend components | `frontend/src/components/dashboard/RenameWorkspaceModal.tsx` | **New** |
| Frontend components | `frontend/src/components/dashboard/EmptyTeamsState.tsx` | **New** |

**File count:** 3 new SQL + 7 new backend Python + 1 new frontend hooks file + 1-2 route edits + 1-2 route adds + 6-8 new React components. Roughly 20 new/modified files across ~10 stories.

### 4.2 Dependencies

| Type | Dependency | Status |
|------|------------|--------|
| **Requires** | EPIC-002: Auth (Email + Password + JWT) | ✅ Done (S-02, v0.2.0-auth) |
| **Requires** | EPIC-001 scaffold (FastAPI, Vite, Tailwind 4, design primitives, migrations 001-004) | ✅ Done (S-01, partial — absorbs remaining migrations into this epic) |
| **Unlocks** | EPIC-004: BYOK Key Management (needs workspace entity with `encrypted_api_key` column + workspace CRUD UI to attach BYOK form to) | Blocked on EPIC-003 |
| **Unlocks** | EPIC-005: Slack Integration (needs `teemo_slack_teams` + `teemo_workspace_channels` schema + team-scoped workspace CRUD + dashboard dock point for channel picker) | Blocked on EPIC-003 |
| **Unlocks** | EPIC-006: Google Drive Integration (needs Workspace entity with `encrypted_google_refresh_token` + per-workspace settings panel) | Blocked on EPIC-003 |
| **Unlocks** | EPIC-007: AI Agent (transitively blocked via EPIC-004 + EPIC-006) | Blocked |
| **Unlocks** | EPIC-008: Workspace Setup Wizard (composes setup flows across EPIC-004/005/006 — needs all UI docks present) | Blocked on EPIC-003 |

### 4.3 Integration Points

| System | Purpose | Docs |
|--------|---------|------|
| Self-hosted Supabase (PostgreSQL 15+) | New tables + ALTER migration | Roadmap §3 ADR-015 / ADR-020 |
| FastAPI TestClient + live Supabase | Integration tests (no mocking, matches S-02 pattern) | `backend/tests/test_auth_routes.py` (S-02 reference) |
| TanStack Query | Server state caching + mutations | `frontend/src/routes/index.tsx` (S-01 reference for `useQuery`) |
| TanStack Router file-based routes | `/app/teams/$teamId` dynamic route | `frontend/src/routes/login.tsx` / `register.tsx` (S-02 reference) |

### 4.4 Data Changes

| Entity | Change | Fields |
|--------|--------|--------|
| `teemo_slack_teams` | **NEW** | `slack_team_id VARCHAR(32) PK`, `owner_user_id UUID FK → teemo_users ON DELETE CASCADE`, `slack_bot_user_id VARCHAR(32) NOT NULL`, `encrypted_slack_bot_token TEXT NOT NULL` (placeholder string from dev-only create), `installed_at TIMESTAMPTZ DEFAULT NOW()`, `updated_at TIMESTAMPTZ DEFAULT NOW()` |
| `teemo_workspace_channels` | **NEW** | `slack_channel_id VARCHAR(32) PK`, `workspace_id UUID FK → teemo_workspaces ON DELETE CASCADE`, `slack_team_id VARCHAR(32) NOT NULL`, `bound_at TIMESTAMPTZ DEFAULT NOW()` |
| `teemo_workspaces` | **MODIFY** | **Drop:** `slack_bot_user_id`, `encrypted_slack_bot_token`, constraint `uq_teemo_workspaces_user_slack_team`. **Add:** `slack_team_id` converted to `FK → teemo_slack_teams(slack_team_id) ON DELETE CASCADE`; `is_default_for_team BOOLEAN NOT NULL DEFAULT FALSE`. **New partial unique index:** `one_default_per_team ON (slack_team_id) WHERE is_default_for_team = TRUE`. |
| `teemo_users` | No change | (referenced by new FK) |
| `teemo_knowledge_index` | No change | (downstream EPIC-006 adds content to this) |
| `teemo_skills` | No change | (downstream EPIC-007 adds content to this) |

---

## 5. Decomposition Guidance

### Affected Areas (for codebase research during Story drafting)

- [ ] `database/migrations/` — existing 001-004 structure (triggers, RLS disable, DO-block NOTICE pattern)
- [ ] `backend/app/api/routes/auth.py` — pattern reference for FastAPI router + `get_current_user_id` dep usage
- [ ] `backend/app/models/user.py` — pattern reference for Pydantic models with `Field(...)` constraints
- [ ] `backend/tests/test_auth_routes.py` — pattern reference for live-Supabase integration tests + teardown fixtures
- [ ] `frontend/src/routes/index.tsx` — pattern reference for `useQuery` + empty/loading/error states
- [ ] `frontend/src/routes/login.tsx` / `register.tsx` — pattern reference for native `<form>` submit + inline error block + Tailwind class strings
- [ ] `frontend/src/stores/authStore.ts` — for understanding the auth store interaction (when logout happens, queryClient.clear must fire; when make-default succeeds, invalidate team/workspace queries)
- [ ] `frontend/src/components/ui/{Button,Card,Badge}.tsx` — primitive prop types and variant names
- [ ] `frontend/src/app.css` — Tailwind `@theme` tokens available (brand-50/500/600/700 + semantic success/warning/danger/info)
- [ ] `frontend/src/main.tsx` — to understand how `queryClient` is exported and how new routes register
- [ ] `product_plans/strategy/tee_mo_design_guide.md` §9.2 (Workspace List layout) and §9.3 (Setup Wizard — only the visual chrome, not the flow)

### Key Constraints for Story Sizing

- Each story should touch **1–3 files** and have **one clear goal**
- Prefer **vertical slices**: "migration + its /api/health verification" is one story, not a "migrations-only" story
- Backend routes are split by resource: `slack_teams` routes are one story, `workspaces` routes are another
- Frontend stories prefer one route per story (team list, team detail)
- Modals are NOT their own stories — they're part of the route that uses them
- Stories must be independently verifiable (backend routes → curl or pytest; frontend → `npm run build` + manual nav)

### Slice A Story Inventory — S-03 (Schema Foundation)

EPIC-003 Slice A contributes **2 stories** to S-03.

| # | Story (draft) | Label |
|---|---|---|
| S-03 / EPIC-003 / 1 | Migrations 005 + 006 + 007 + TEEMO_TABLES update + `/api/health` regression tests | L2 |
| S-03 / EPIC-003 / 2 | BUG-20260411 fix: migrate `decode_token` to scoped `jwt.PyJWT()` instance + regression-lock test | L1 |

### Slice B Story Inventory — S-05 (Workspace CRUD)

EPIC-003 Slice B is the full S-05 sprint. All 7 stories live here.

| # | Story (draft) | Label |
|---|---|---|
| S-05 / EPIC-003 / 3 | Backend: `models/workspace.py` + exports | L1 |
| S-05 / EPIC-003 / 4 | Backend: `app/api/routes/workspaces.py` — full CRUD endpoints | L2 |
| S-05 / EPIC-003 / 5 | Backend integration tests: `test_workspaces_routes.py` against live Supabase | L2 |
| S-05 / EPIC-003 / 6 | Frontend: `lib/api.ts` wrappers + `hooks/useWorkspaces.ts` TanStack Query hooks | L2 |
| S-05 / EPIC-003 / 7 | Frontend: new `/app/teams/$teamId` file-based route — workspace list + CreateWorkspaceModal | L2 |
| S-05 / EPIC-003 / 8 | Frontend: workspace card — RenameWorkspaceModal + Make default + badges + status chips | L2 |
| S-05 / EPIC-003 / 9 | Manual verification walkthrough + `npm run build` regression | L1 (manual) |

---

## 6. Risks & Edge Cases

| # | Risk | Likelihood | Severity | Mitigation |
|---|---|---|---|---|
| R1 | **Migration 007 drops columns with live data** | Low | High | Migration 007 includes a DO-block pre-check; current state: verified zero rows. |
| R2 | **FK conversion fails** | Low | High | Same pre-check: verify zero rows. |
| R3 | **`one_default_per_team` partial unique constraint** | Medium | Medium | `POST /api/workspaces/{id}/make-default` runs as a single transaction. |
| R4 | **First-workspace auto-default race** | Low | Medium | The partial unique index catches it at the DB level; handler retries with `is_default_for_team = FALSE`. |
| R5 | **Dev-only team create is a spoofing vector** | Medium | Low (pre-demo only) | Gate on `settings.debug == True`. |
| R6 | **Cascade on team delete is dangerous** | Low | High | **Do not ship team delete in EPIC-003.** |
| R7 | **Workspace delete has the same cascade shape** | Low | Medium | **Same decision: defer workspace delete to later.** |
| R8 | **TanStack Router regenerate flake** | High | Low | Story task files for frontend stories document the vite-first workaround. |
| R9 | **Authorization leak between users** | Medium | High | Every handler calls `assert_team_owner`. Integration tests include a cross-user 403 scenario. |
| R10 | **Response model leaks secrets** | Medium | High | Pydantic `WorkspaceResponse` model explicitly does NOT include `encrypted_api_key` or `encrypted_google_refresh_token`. |

---

## 7. Acceptance Criteria (Epic-Level)

```gherkin
Feature: Dashboard Shell + SlackTeam / Workspace CRUD

  Background:
    Given the teemo_users table has a user "alice@example.com" with a valid password hash
    And the teemo_slack_teams table is empty
    And the teemo_workspaces table is empty
    And the teemo_workspace_channels table is empty
    And DEBUG=true is set in the backend environment

  Scenario: End-to-end dev flow — register → team → workspace → default swap
    Given a fresh incognito browser session
    When I register as "alice+$(date)@teemo.test" with password "correcthorse"
    Then I land on "/app" and see the team list empty state
    And I see a disabled "Install Slack" button
    And I see a "Create team manually (dev)" secondary button
    When I click "Create team manually (dev)"
    Then a modal opens with 3 fields
    When I enter slack_team_id="T0TEEMO001", team_name="Demo Team", slack_bot_user_id="U0BOT001"
    And I submit the form
    Then the modal closes
    And I see a "Demo Team" card in the team list
    When I click the "Demo Team" card
    Then I am on "/app/teams/T0TEEMO001" and see an empty workspace list
    When I click "+ New Workspace" and enter name "Marketing"
    Then I see a "Marketing" workspace card
    And the "Marketing" card shows a "Default for DMs" badge
    When I click "+ New Workspace" again and enter name "Engineering"
    Then I see both "Marketing" and "Engineering" cards
    And only "Marketing" shows the "Default for DMs" badge
    When I click "Make default" on the "Engineering" card
    Then the "Default for DMs" badge moves to "Engineering"
    And the "Marketing" card no longer shows the badge
    When I click "Rename" on the "Engineering" card and enter "Platform"
    Then the card shows "Platform"
    And a hard refresh preserves all the above state

  Scenario: Unauthorized access to another user's team
    Given user "bob@example.com" has a team T0BOB001 and a workspace under it
    And I am logged in as "alice@example.com"
    When I GET /api/slack-teams/T0BOB001/workspaces
    Then the response status is 403
    And the detail is "Forbidden"

  Scenario: Dev-only team creation fails in production
    Given DEBUG=false in the backend environment
    And I am logged in as "alice@example.com"
    When I POST /api/slack-teams with a valid dev-only payload
    Then the response status is 403
    And the detail is "Dev-only endpoint disabled in production"

  Scenario: Health endpoint reports all 6 tables after EPIC-003 migrations
    When I GET /api/health
    Then the response status is 200
    And database contains keys "teemo_users", "teemo_workspaces", "teemo_knowledge_index", "teemo_skills", "teemo_slack_teams", "teemo_workspace_channels"
    And every value is "ok"
    And top-level status is "ok"

  Scenario: Make-default is atomic (partial unique constraint holds)
    Given a team T0TEEMO001 with workspaces W1 (default) and W2 (not default)
    When I POST /api/workspaces/{W2.id}/make-default
    Then the response is 200
    And querying the DB shows W2.is_default_for_team = true AND W1.is_default_for_team = false
    And no race condition leaves both with true
```

---

## 8. Open Questions — RESOLVED by ADR-026 reshape (2026-04-12)

All 10 original open questions were resolved. No open questions remain. Ambiguity 🟢 Low.

---

## 9. Artifact Links

**Stories (Slice A - S-03 Completed):**
- [x] STORY-003-03-migrations → Archive (S-03)
- [x] STORY-003-04-pyjwt-fix → Archive (S-03)

**Stories (Slice B - Safe for Parallel Run):**
- [ ] STORY-003-B01-workspace-models → Backlog (Ready for Parallel)
- [ ] STORY-003-B04-frontend-api-hooks → Backlog (Ready for Parallel)

**Stories (Slice B - Blocked by S-04 Slack Install):**
- [ ] STORY-003-B02-workspace-routes → Backlog (Pending S-04)
- [ ] STORY-003-B03-workspace-tests → Backlog (Pending S-04)
- [ ] STORY-003-B05-team-workspace-list → Backlog (Pending S-04)
- [ ] STORY-003-B06-rename-make-default → Backlog (Pending S-04)
- [ ] STORY-003-B07-manual-verification → Backlog (Pending S-04)

---

## Change Log

| Date | Change | By |
|------|--------|-----|
| 2026-04-11 | Epic drafted from Context Pack. Ambiguity 🟡 Medium. | Team Lead (post-S-02 planning) |
| 2026-04-12 | **ADR-026 reshape.** Split into Slice A (S-03) and Slice B (S-05). All 10 open questions resolved. Ambiguity 🟡 → 🟢. | Team Lead (ADR-026 planning) |
