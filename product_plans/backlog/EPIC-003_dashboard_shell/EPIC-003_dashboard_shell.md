---
epic_id: "EPIC-003"
status: "Draft — pending human review of §6 Edge Cases + §8 Open Questions"
ambiguity: "🟡 Medium"
context_source: "Charter §1.1, §2.6, §5.3, §5.5, §10 Dashboard Epic Seed Map; Roadmap §2 EPIC-003 row + ADR-014/022/024/025; Design Guide §6, §9.2, §9.3; Codebase Context Pack 2026-04-11."
release: "D-01 Release 1: Foundation"
owner: "Solo dev"
priority: "P0"
tags: ["frontend", "backend", "schema", "dashboard", "crud"]
target_date: "2026-04-12"
---

# EPIC-003: Dashboard Shell + SlackTeam / Workspace CRUD

## 1. Problem & Value

### 1.1 The Problem

After registering (EPIC-002), a user lands on a placeholder `/app` page that says "Welcome to Tee-Mo. Signed in as <email>." and offers no way to do anything else. Downstream epics — **EPIC-004** (BYOK), **EPIC-005** (Slack), **EPIC-006** (Drive), **EPIC-007** (AI Agent), **EPIC-008** (Wizard) — all require a **Workspace** entity (a knowledge silo under a SlackTeam) to attach their features to, and a **SlackTeam → Workspace → ChannelBinding** data shape per ADR-024. Without this shell, every subsequent feature has nothing to dock onto.

### 1.2 The Solution

Ship the **Dashboard Shell** and the **team/workspace CRUD foundation** (schema + API + UI) so the five downstream epics can plug in without rework:

1. **Schema foundation** — three new migrations that refactor the workspace model to ADR-024's `1 user : N SlackTeams : N Workspaces : N channel bindings` shape (create `teemo_slack_teams`, create `teemo_workspace_channels`, ALTER `teemo_workspaces` to drop slack bot fields and add `is_default_for_team` + partial unique index).
2. **Backend CRUD API** — authenticated REST endpoints for listing/creating/renaming/deleting SlackTeams and Workspaces, scoped to the current user via `get_current_user_id`.
3. **Frontend shell** — replace the `/app` placeholder body with a two-level navigation: **Team list** (landing after login) → **Team detail** showing Workspaces under that team, with "New Workspace" / "Rename" / "Make default" actions.
4. **Empty-state pragmatic unlock** — because EPIC-005 (Slack OAuth) hasn't landed yet, the team list renders a disabled **"Install Slack"** CTA AND a **dev-only** "Create team manually" path so the Workspace CRUD loop is exercisable end-to-end before Slack integration arrives. EPIC-005 later replaces the dev path with the real OAuth callback; the dashboard UI stays put.
5. **Trailing tech-debt fix** — BUG-20260411-001 (PyJWT module-level options leak causing test-order flake) resolved in-sprint because every new backend route in EPIC-003 lands more tests into the same suite, and the flake will only get worse.

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

### Suggested Sequencing Hints (draft — to be finalized after §6 / §8 review)

1. **Schema foundation** must exist first. No backend routes or frontend hooks work without migrations 005-007 applied and TEEMO_TABLES updated.
2. **PyJWT BUG fix** should land in the same sprint as schema foundation (S-03) — before EPIC-003 adds more backend tests that would exacerbate the flake. L1 size, ~30 min.
3. **Backend routes** can run in parallel AFTER schema: `slack_teams` routes and `workspaces` routes are independent at the route level (they only share the `get_current_user_id` dep and the `assert_team_owner` helper).
4. **Backend integration tests** ship in the same stories as the routes they test (S-02 pattern — one story per resource for spec + tests).
5. **Frontend API wrappers** + **TanStack Query hooks** can land together in one story (they're both thin typed interfaces to the backend routes).
6. **Frontend /app team list** depends on: wrappers + hooks + backend `GET /api/slack-teams`.
7. **Frontend /app/teams/$teamId workspace list** depends on: wrappers + hooks + backend `GET /api/slack-teams/:id/workspaces` + backend `POST /api/slack-teams/:id/workspaces`.
8. **Polish** (rename, make-default, empty-state copy) ships last in a single story once the CRUD loop is green.

### Draft Story Inventory (10 stories, ~2 sprints)

| # | Story (draft) | Label | Parent sprint |
|---|---|---|---|
| 1 | Migrations 005 + 006 + 007 + update TEEMO_TABLES + extend `/api/health` coverage | L2 | S-03 |
| 2 | BUG-20260411 fix: migrate `decode_token` to `jwt.PyJWT()` instance + regression-lock test | L1 | S-03 |
| 3 | Backend: `models/slack_team.py` + `/api/slack-teams` routes (list + dev-only create) + integration tests | L2 | S-03 |
| 4 | Backend: `models/workspace.py` + `/api/slack-teams/{team_id}/workspaces` + `/api/workspaces/{id}` routes (list, create, get, rename, make-default) + integration tests (including partial-unique constraint) | L2 | S-03 |
| 5 | Frontend: `lib/api.ts` wrappers (7 functions + types) + `hooks/useWorkspaces.ts` TanStack Query hooks | L2 | S-04 |
| 6 | Frontend: replace `/app` body with team list (empty state + dev-only create modal + team cards) | L2 | S-04 |
| 7 | Frontend: new `/app/teams/$teamId` route — workspace list + CreateWorkspaceModal | L2 | S-04 |
| 8 | Frontend: RenameWorkspaceModal + make-default action + optimistic UI + inline error rollback | L2 | S-04 |
| 9 | Frontend: dashboard header bar (shell chrome — logo + user email + sign-out) + empty/loading/error polish | L1 | S-04 |
| 10 | Manual verification checklist + documentation of dev-only path for future removal (when EPIC-005 ships) | L1 | S-04 |

Story IDs are placeholder. Final IDs (`STORY-003-01-migrations`, etc.) assigned during decomposition Phase 3.

---

## 6. Risks & Edge Cases

| # | Risk | Likelihood | Severity | Mitigation |
|---|---|---|---|---|
| R1 | **Migration 007 drops columns with live data** — if any workspaces have been created between the S-01 schema bake and EPIC-003, `slack_bot_user_id` / `encrypted_slack_bot_token` data is lost. | Low | High | Migration 007 includes a DO-block pre-check: `SELECT COUNT(*) FROM teemo_workspaces WHERE slack_bot_user_id IS NOT NULL OR encrypted_slack_bot_token IS NOT NULL` — if non-zero, RAISE EXCEPTION and abort. Current state: verified zero rows. |
| R2 | **FK conversion (`slack_team_id` VARCHAR → FK) fails** if any existing `teemo_workspaces.slack_team_id` doesn't match a `teemo_slack_teams.slack_team_id`. | Low | High | Same pre-check: verify zero rows. If rows exist with a slack_team_id, pre-create the matching slack_teams row before the FK constraint lands. In practice: no rows exist; we're safe. |
| R3 | **`one_default_per_team` partial unique constraint** — creating a new default for a team while an existing default exists must not leave a transient state with two defaults. | Medium | Medium | `POST /api/workspaces/{id}/make-default` runs as a single transaction: `UPDATE ... SET is_default_for_team = FALSE WHERE slack_team_id = $1 AND is_default_for_team = TRUE; UPDATE ... SET is_default_for_team = TRUE WHERE id = $2`. Supabase client supports transactions via RPC or explicit `begin/commit` pattern — verify the approach during Story §3 drafting. |
| R4 | **First-workspace auto-default race** — two simultaneous `POST /api/slack-teams/{id}/workspaces` calls could both think they're the first workspace and both end up with `is_default_for_team = TRUE`, violating the partial unique constraint. | Low | Medium | The partial unique index catches it at the DB level — the second insert returns a unique violation error. Handler catches the error, retries with `is_default_for_team = FALSE`, returns 201. Integration test covers this. |
| R5 | **Dev-only team create is a spoofing vector** — a logged-in attacker could create a team with an arbitrary `slack_team_id` they don't own, then later when real OAuth lands, EPIC-005 would refuse to install to that team_id because it's already taken. | Medium | Low (pre-demo only) | Gate on `settings.debug == True`. Production `.env` sets `DEBUG=false` — the endpoint returns 403. Plus: document in the dev-only endpoint's docstring that this is a temporary path and will be removed in EPIC-005. File a tracking TODO. |
| R6 | **Cascade on team delete is dangerous** — deleting a `teemo_slack_teams` row cascades to all workspaces → all channel bindings → all knowledge_index rows → all skills. Before EPIC-003 has any delete UI, this is a moot risk; but once added, irreversible data loss is one click away. | Low | High | **Do not ship team delete in EPIC-003.** No UI surface, no API route. Defer to a dedicated "danger zone" story post-EPIC-007. |
| R7 | **Workspace delete has the same cascade shape** — same concern at smaller scale. | Low | Medium | **Same decision: defer workspace delete to later.** EPIC-003 ships rename only. §2 Out-of-Scope is explicit. |
| R8 | **TanStack Router regenerate flake** — adding `app.teams.$teamId.tsx` will hit the known `tsc -b && vite build` ordering bug (FLASHCARDS.md 2026-04-11). | High | Low | Story task files for frontend stories document the vite-first workaround. Acceptable accepted debt (recorded in FLASHCARDS.md, candidate for `/improve`). |
| R9 | **Authorization leak between users** — if `GET /api/workspaces/{id}` doesn't verify team ownership, user A can read user B's workspaces. | Medium | High | Every handler calls `assert_team_owner(workspace.slack_team_id, current_user_id)` before returning data. Integration tests must include a cross-user 403 scenario. |
| R10 | **Response model leaks secrets** — if `Workspace` response model includes `encrypted_api_key` or `encrypted_google_refresh_token`, those ciphertexts end up in the frontend. | Medium | High | Pydantic `WorkspaceResponse` model explicitly does NOT include those fields. Separate `WorkspaceInternal` model (if needed) used only inside the backend. Integration test asserts the response JSON does not contain `encrypted_api_key` / `encrypted_google_refresh_token`. |
| R11 | **Workspace name collision within a team** — two workspaces with identical names under one team. | High | Low (cosmetic) | **Accept.** No uniqueness constraint. UI differentiates by UUID in the URL. User can rename if confused. |
| R12 | **`/api/health` smoke check breaks on new tables** — if migrations land but `TEEMO_TABLES` tuple isn't updated, health returns `"degraded"` because the new tables are "unknown". | Low | Low (trivial fix) | Migration story includes the `TEEMO_TABLES` update as part of the same story; test asserts health returns `"ok"` post-migration. |
| R13 | **Vitest TDZ recurrence in new hooks tests** — if Story 5 (frontend hooks) writes Vitest tests that mock `queryClient` or the API wrappers, the Vitest hoisting TDZ from S-02 (FLASHCARDS.md 2026-04-11) will hit again. | Medium | Low | Story task files for frontend test stories must call out `vi.hoisted()` wrapper explicitly. Red-phase reviewer (Team Lead Step 2c) must verify. |
| R14 | **Dashboard header (R6) has no sticky behavior** — on scroll, the header disappears and user loses sign-out access. | Low | Low | Use `sticky top-0 z-10 bg-slate-50` classes on the header. Design Guide §9.2 implies this but doesn't mandate. |
| R15 | **First-time user lands on empty team list with no clear CTA** — could bounce. | Medium | Medium | Empty state is a full-bleed card with a friendly headline ("Install Slack to create your first workspace"), a sub-copy explaining what happens next, and the disabled button. In dev, the secondary "Create team manually" button is clearly labeled as dev-only. |

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

## 8. Open Questions

**These are the decisions the human needs to make before Story decomposition can proceed.**

| # | Question | Options | Impact | Recommendation | Owner | Status |
|---|---|---|---|---|---|---|
| Q1 | **Ship the dev-only manual team-create path, or wait for EPIC-005 Slack OAuth?** | **(A)** Ship the dev-only path gated on `DEBUG=true`. EPIC-005 later replaces the dev path with real OAuth. Workspace CRUD is testable end-to-end in S-04. **(B)** Skip the dev path. EPIC-003 only ships the team-list empty state + disabled "Install Slack" button. The Workspace CRUD API is built but not reachable via the UI until EPIC-005 lands. | (A) unlocks immediate frontend CRUD demoability; (B) is cleaner but leaves the CRUD dead code until EPIC-005 merges. | **(A) Ship it.** The dev path is ~30 min of work, ~30 min of cleanup when EPIC-005 removes it. (B) trades that for unverifiable UI. | Solo dev | **Open** |
| Q2 | **Ship Rename and Make-Default actions in EPIC-003 or defer to EPIC-008?** | **(A)** Ship both in EPIC-003. **(B)** Ship Rename only; defer Make-Default to EPIC-008 wizard (it's part of the "polish" story). **(C)** Defer both; EPIC-003 is create-only. | Rename is low-risk, high-value (users will want it). Make-Default is the only UX hook for the "which workspace gets DMs" Charter §5.5 rule — deferring it means the charter behavior is unobservable until much later. | **(A) Ship both.** Make-Default is the only surface that makes `is_default_for_team` observable. Small cost, big clarity. | Solo dev | **Open** |
| Q3 | **Workspace detail view: disabled placeholder chips for future BYOK / Drive / Channels, or hide entirely?** | **(A)** Show as disabled "Not connected" chips so the user (and future judges) see the shape of what's coming. **(B)** Hide them entirely until EPIC-004/005/006 land. | (A) sets expectations and looks intentional. (B) is cleaner but gives no indication of the coming flow. | **(A) Show as disabled chips.** Matches Design Guide §9.2's "setup status" pattern. | Solo dev | **Open** |
| Q4 | **BYOK (EPIC-004) column placement — include now or add later?** | The existing `teemo_workspaces` table already has `ai_provider`, `ai_model`, `encrypted_api_key` columns (from S-01 migration 002). Do we **(A)** leave them as-is and let EPIC-004 populate them, or **(B)** drop them in migration 007 and have EPIC-004 add them back when it ships? | (A) is simpler — the columns already exist, unused. (B) keeps EPIC-003's schema clean. | **(A) Leave them.** They're unused but not harmful, and EPIC-004 will thank you for not re-adding them. | Solo dev | **Open** |
| Q5 | **Frontend route structure: flat or nested?** | **(A)** `/app` → team list; `/app/teams/$teamId` → workspace list (2 route files, nested). **(B)** `/app` → team list + inline drawer for workspaces (1 route file, modal-based). **(C)** `/app` → combined single-page hierarchy that renders everything in one component (1 route file, no modal). | (A) gives bookmarkable URLs and matches Design Guide §9.2 two-screen model. (B) is cheaper to build. (C) is cheapest but fights browser back-button and deep linking. | **(A) Nested routes.** Matches the Design Guide, enables EPIC-008 wizard to reuse `/app/teams/$teamId` as its target, bookmarkable URLs help the demo flow. | Solo dev | **Open** |
| Q6 | **Sprint split for EPIC-003: 2 sprints or 3?** | **(A) 2 sprints**: S-03 = schema + PyJWT fix + all 4 backend stories; S-04 = all 5 frontend stories + polish. **(B) 3 sprints**: S-03 = schema + PyJWT fix only; S-04 = backend routes + tests; S-05 = frontend. | (A) is tight but feasible because stories 1-4 are mostly copy-style backend work. (B) is safer but pushes Release 1 completion to S-05, eating Release 2 capacity on the 2026-04-18 deadline. | **(A) 2 sprints** unless S-03 obviously overruns — in which case split at that point. | Solo dev | **Open** |
| Q7 | **BUG-20260411 (PyJWT fix): ship in S-03 or as a separate maintenance sprint?** | **(A)** Ship in S-03 as an L1 trailing story (~30 min) — avoids a separate sprint. **(B)** Spin up S-02.5 as a hotfix-only sprint before S-03 plans anything. **(C)** Defer until after EPIC-003 because the workaround (`-p no:randomly` + explicit order) works. | (A) keeps sprints meaningful; (B) is ceremony overhead; (C) means EPIC-003's ~18 new backend tests inherit the flake. | **(A) Ship in S-03.** Blocks nothing and removes a growing pain point. | Solo dev | **Open** |
| Q8 | **Browser walkthrough of S-02 before EPIC-003 starts?** | **(A)** Run the 11 manual steps from STORY-002-04 §2.2 now (~3 min Incognito) before committing to EPIC-003. **(B)** Skip — EPIC-003 replaces `/app` body anyway, so any visual bugs there get caught in S-04's manual verification. | (A) catches any login/register regression before we build on top; (B) saves 3 minutes. | **(A) Run it.** 3 minutes of insurance. If the register flow is subtly broken, EPIC-003 inherits the breakage silently. | Solo dev | **Open** |
| Q9 | **Dashboard header chrome — sticky and minimal, or full toolbar?** | **(A) Minimal sticky**: logo on left, user email + sign-out on right, `h-14`. **(B) Full toolbar**: logo + breadcrumbs + user menu + help + notifications bell. | (A) matches Tee-Mo minimalism (Charter §2.6); (B) is premature scope. | **(A) Minimal sticky.** ADR-022 explicitly says "no shadcn, no MUI" — keep the chrome boring. | Solo dev | **Open** |
| Q10 | **Create modal UX: native `<form>` or a reusable `<Modal>` component?** | **(A)** Inline native `<form>` in each route file, same pattern as `/login` and `/register`. **(B)** Build a reusable `<Modal>` component (new primitive) and use it for all three create/rename modals. | (A) matches S-02 pattern exactly; (B) is cleaner but adds a new primitive and a new story. | **(A) Native forms.** Stay consistent with S-02. A reusable modal is EPIC-008 wizard territory. | Solo dev | **Open** |

---

## 9. Artifact Links

**Stories (to be created after §8 questions are resolved):**
- [ ] STORY-003-01-migrations → Backlog (pending)
- [ ] STORY-003-02-pyjwt-fix → Backlog (pending)
- [ ] STORY-003-03-slack-teams-routes → Backlog (pending)
- [ ] STORY-003-04-workspaces-routes → Backlog (pending)
- [ ] STORY-003-05-frontend-api-hooks → Backlog (pending)
- [ ] STORY-003-06-team-list-view → Backlog (pending)
- [ ] STORY-003-07-team-detail-workspace-list → Backlog (pending)
- [ ] STORY-003-08-rename-and-make-default → Backlog (pending)
- [ ] STORY-003-09-dashboard-shell-chrome → Backlog (pending)
- [ ] STORY-003-10-manual-verification → Backlog (pending)

**References:**
- Charter: `product_plans/strategy/tee_mo_charter.md` §1.1, §2.6, §5.3, §5.5, §6 (constraints), §10 Dashboard Epic Seed Map
- Roadmap: `product_plans/strategy/tee_mo_roadmap.md` §2 Release 1 + §3 ADR-014/022/024/025 + §4 cross-epic deps
- Design Guide: `product_plans/strategy/tee_mo_design_guide.md` §2, §3, §4, §6 (primitives), §9.2 (Workspace List layout)
- Flashcards: `FLASHCARDS.md` — TanStack Query rule, Tailwind 4 `@theme` rule, samesite=lax, Vitest `vi.mock` TDZ, TanStack Router / Vite ordering
- S-02 patterns: `backend/app/api/routes/auth.py` (routes), `backend/tests/test_auth_routes.py` (tests), `frontend/src/routes/login.tsx` (forms)
- Prior migrations: `database/migrations/001..004_*.sql`
- BUG report: `product_plans/backlog/EPIC-002_auth/BUG-20260411-pyjwt-test-ordering.md`

---

## Change Log

| Date | Change | By |
|------|--------|-----|
| 2026-04-11 | Epic drafted from Context Pack. Ambiguity 🟡 Medium — pending human review of §6 Risks + §8 Open Questions before decomposition. | Team Lead (post-S-02 planning) |
