---
last_updated: "2026-04-12T18:30"
status: "In Execution — Release 1 ~85% delivered (S-01 + S-02 + S-03 shipped; live at https://teemo.soula.ge; EPIC-005 Phase A [S-04] and EPIC-003 Slice B [S-05] remaining)"
charter_ref: "product_plans/strategy/tee_mo_charter.md"
design_guide_ref: "product_plans/strategy/tee_mo_design_guide.md"
risk_registry_ref: "product_plans/strategy/RISK_REGISTRY.md"
---

# Product Roadmap: Tee-Mo

## 1. Strategic Context

| Key | Value |
|-----|-------|
| **Vision** | A context-aware AI agent embedded in Slack that answers questions using thread history and a curated Google Drive knowledge base, at zero host inference cost via BYOK. |
| **Primary Goal** | Ship a live, end-to-end demoable app for the hackathon on 2026-04-18. |
| **Tech Stack** | React 19 + Tailwind 4 + Vite 8 + TanStack Router/Query + Zustand (frontend); FastAPI 0.135 + Pydantic AI 1.79 + Supabase 2.28 + cryptography 46 + Slack Bolt 1.28 + google-api-python-client 2.194 (backend) |
| **Target Users** | Hackathon judges (primary). Slack workspace admins who want a BYOK AI assistant with Drive knowledge (secondary). |

### Project Window
| Key | Value |
|-----|-------|
| **Start Date** | 2026-04-11 |
| **End Date** | 2026-04-18 |
| **Total Sprints** | 16 |
| **Team** | Solo developer + Claude Code (V-Bounce agent team) |
| **Sprint Cadence** | 2 sprints/day × 8 days, ~4 hours per sprint |

### Success Metrics
> From Charter §1.3.

- Host operates at zero LLM inference cost (100% BYOK).
- Live demo: register → create workspace → install Slack → connect Drive → add files → @mention bot → correct in-thread answer referencing a file.
- All three providers (OpenAI, Anthropic, Google) selectable and functional.
- BYOK keys, Slack bot tokens, and Google refresh tokens all encrypted at rest (AES-256-GCM).
- 15-file cap enforced per workspace.
- Zero plaintext key exposure in logs, DB, or frontend responses.

---

## 2. Release Plan

> Three releases mapped to the 8-day hackathon window. Each release is a demoable checkpoint that reduces "does anything work?" risk early.

### Release 1: Foundation + Deploy + Slack Install (Days 1–3, Sprints 1–5)
**Target**: 2026-04-13 EOD *(slipped by 1 day from 2026-04-12 per ADR-026 to absorb deploy + Slack Phase A into Release 1)*
**Exit Criteria**:
- [x] Repo scaffolded with frontend + backend + Supabase connection *(S-01)*
- [x] User can register, log in, see empty dashboard *(S-02 — `/app` placeholder behind `ProtectedRoute`)*
- [ ] **Live at `https://teemo.soula.ge` via Coolify auto-deploy from GitHub main** *(EPIC-003 Slice A / ADR-026, S-03)*
- [ ] **Slack Phase A — real OAuth install writes a `teemo_slack_teams` row** *(EPIC-005 Phase A, S-04)*
- [ ] Workspace CRUD — user can create, list, rename, and make-default workspaces under a real Slack team *(EPIC-003 Slice B, S-05)*
- [x] Both servers run locally with one command *(S-01 + user-verified acceptance)*

| Epic | Priority | Status | Notes |
|------|----------|--------|-------|
| EPIC-001: Project Scaffold & Supabase Schema | P0 | **Done (S-01) — partial** | **Delivered in S-01**: FastAPI scaffold + `app/core/config.py` + `app/core/db.py` (cached Supabase singleton) + `GET /api/health` with per-table `teemo_*` aggregate, Vite 8 + React 19 + Tailwind 4 + TanStack Router scaffold, 4 migrations applied (`teemo_users`, `teemo_workspaces`, `teemo_knowledge_index`, `teemo_skills`). **Deferred to EPIC-003 Slice A**: the 2 ADR-024 tables (`teemo_slack_teams`, `teemo_workspace_channels`) + `teemo_workspaces` ALTERs. |
| EPIC-002: Auth (Email + Password + JWT) | P0 | **Done (S-02)** — tagged `v0.2.0-auth` | 22 backend + 10 frontend tests, integration audit SHIP. Carries BUG-20260411 (PyJWT test-order) to S-03 backlog. |
| EPIC-003: Dashboard Shell + Workspace CRUD | P0 | **Reshaped — split into Slice A (S-03) + Slice B (S-05) per ADR-026** | **Slice A (S-03 — schema foundation):** migrations 005/006/007 (per ADR-024: create `teemo_slack_teams`, create `teemo_workspace_channels`, ALTER `teemo_workspaces`), update `TEEMO_TABLES` in `/api/health`, PyJWT BUG-20260411 fix. No routes or frontend in this slice. **Slice B (S-05 — workspace CRUD):** backend routes (`GET/POST /api/slack-teams/:id/workspaces`, `GET/PATCH /api/workspaces/:id`, `POST /api/workspaces/:id/make-default`), frontend `/app/teams/$teamId` route, workspace cards, create/rename modals, make-default toggle, "Not connected" status chips for future BYOK/Drive/Channels. **Dev-only manual team-create path eliminated** — Slack OAuth Phase A (EPIC-005, S-04) sandwiches between the two slices and lands real Slack teams. |
| **NEW — ADR-026 Deploy Infrastructure** | P0 | **Pulled forward to S-03** | Dockerfile (multi-stage: Vite build → FastAPI serving static), Coolify project config, GitHub auto-deploy on push to main, `https://teemo.soula.ge` via Coolify Traefik HTTPS, production env vars injected via Coolify UI. Previously scoped in EPIC-010 (Release 3); now S-03 scope per ADR-026. EPIC-010 scope reduces to seed data + README + demo script. |
| EPIC-005: Slack Integration — **Phase A (OAuth install)** | P0 | **Pulled into Release 1 — S-04** | Phase A only: `backend/app/core/encryption.py` (AES-256-GCM per ADR-002/010), `backend/app/core/slack.py` (Slack Bolt AsyncApp scaffold), `/api/slack/install` (OAuth URL builder), `/api/slack/oauth/callback` (exchange code → `oauth.v2.access` → extract `team`, `bot_user_id` via `auth.test` → encrypt bot token → write `teemo_slack_teams` row → redirect to `/app`), minimal `/api/slack/events` endpoint that handles only `url_verification` challenge for Slack's app-setup verification (real event handlers come in Phase B), frontend landing `/app` team list with real "Install Slack" button + header chrome. Tested in production shape from Day 2 because deploy is live from S-03. |
| EPIC-005: Slack Integration — **Phase B (events + channel binding)** | P0 | **Deferred to after EPIC-007** | Phase B: `app_mention` + `message.im` handlers (self-message filter using `slack_bot_user_id` from Phase A), unbound-channel setup-nudge, `/api/workspaces/:id/channels` CRUD, channel picker modal, `conversations.list` integration, `is_member` status refresh. Depends on EPIC-007 agent being callable from the event handler. Schedule TBD — do not over-plan. |

### Release 2: Core Pipeline (Days 3–6, Sprints 5–12)
**Target**: 2026-04-16 EOD
**Exit Criteria** (this is the demoable milestone — if nothing else works, this must):
- User can configure BYOK key and validate it
- User can install Slack bot via OAuth into a real Slack workspace
- User can connect Google Drive via OAuth
- User can add a file from Drive Picker; AI scan generates `ai_description`; 15-file cap enforced
- User @mentions bot in Slack → bot posts answer in thread, having read the relevant Drive file
- Two-tier model strategy works (conversation tier + scan tier with same BYOK key)

| Epic | Priority | Status | Notes |
|------|----------|--------|-------|
| EPIC-004: BYOK Key Management | P0 | Draft | Copy + strip from new_app. One key per provider. Hard gate for file indexing. |
| EPIC-005: Slack Integration (OAuth + Events + Bindings) | P0 | Draft | Slack Bolt AsyncApp. OAuth install writes `slack_teams`. Event handlers: `app_mention` resolves via `workspace_channels` (unbound → setup-nudge reply, no fallback), `message.im` resolves via `is_default_for_team`. Channel binding REST (`GET /api/slack/teams/:id/channels`, `POST/DELETE /api/workspaces/:id/channels`, `POST /api/workspaces/:id/make-default`). Scopes: `app_mentions:read`, `channels:history`, `groups:history`, `im:history`, `chat:write`, **`channels:read`**, **`groups:read`**. See ADR-024 + ADR-025. |
| EPIC-006: Google Drive Integration | P0 | Draft | Offline refresh token OAuth, Google Picker, knowledge_index CRUD, `read_drive_file` tool with MIME routing (Docs/Sheets/Slides/PDF/Word/Excel). |
| EPIC-007: AI Agent + Two-Tier Models + Skills | P0 | Draft | Copy + strip orchestrator. `build_agent(tier)` factory. `scan_file_metadata` service. Self-updating `ai_description` via content hash check. Skills: `skills` table + `skill_service.py` (copy + strip from new_app) + 4 orchestrator tools (`load_skill`, `create_skill`, `update_skill`, `delete_skill`) — no `related_tools`, no seeded skills. Chat-only CRUD. |

### Release 3: Demo Polish (Days 7–8, Sprints 13–16)
**Target**: 2026-04-18 (hackathon deadline)
**Exit Criteria**:
- 4-step workspace setup wizard polished end-to-end
- Error handling: rate limits, invalid keys, revoked Drive tokens, context overflow with trim notice, unsupported MIME types
- Visual polish on dashboard (minimalistic modern design per Charter §2.6)
- Deployed to a public URL with HTTPS (ngrok or equivalent for Slack webhook)
- Seed demo workspace with 3-5 Drive files for reliable judge walkthrough
- README with setup + demo instructions

| Epic | Priority | Status | Notes |
|------|----------|--------|-------|
| EPIC-008: Workspace Setup Wizard Polish | P0 | Draft | Two-phase flow per ADR-024: **Phase A** (team install, one-time per team) = Slack OAuth. **Phase B** (per knowledge silo, repeatable) = name → Drive OAuth → BYOK → Drive files → bind Slack channels. Workspace card renders channel chips with Active / Pending /invite status, **Make default** toggle, **📨 DMs route here** badge on the default. Minimalistic modern Tailwind design per `tee_mo_design_guide.md`. |
| EPIC-009: Error Handling & UX Polish | P0 | Draft | All Charter §6 edge cases wired to user-facing errors with clear messages. |
| EPIC-010: Demo Hardening & Deploy | P0 | Draft | Seed data, public HTTPS endpoint, README, demo script. |

---

## 3. Technical Architecture Decisions

> ADRs are immutable once Decided. Create a new row to override.

| ID | Decision | Choice | Rationale | Status | Date |
|----|----------|--------|-----------|--------|------|
| ADR-001 | Authentication | Custom email/password JWT (copy from new_app `security.py` + `auth.py`) | Supabase Auth ruled out — charter §1.2. No email verification. JWT: 15min access + 7d refresh in httpOnly cookies. | Decided | 2026-04-10 |
| ADR-002 | Encryption | AES-256-GCM via Python `cryptography.AESGCM` (copy new_app `encryption.py`) | Authenticated encryption. Same primitive for BYOK keys, Slack bot tokens, Google refresh tokens. NOT Fernet. | Decided | 2026-04-10 |
| ADR-003 | AI Framework | Pydantic AI 1.79 with `[openai,anthropic,google]` extras | Provider-agnostic model string format (`provider:model-id`). Copy `build_orchestrator` pattern from new_app. | Decided | 2026-04-10 |
| ADR-004 | Two-Tier Model Strategy | Conversation tier (user-selectable) + Scan tier (hardcoded small/fast model per provider) | Summarization is cheap and high-volume; doesn't need frontier reasoning. Same BYOK key, different `model_id`. See Charter §3.4. | Decided | 2026-04-11 |
| ADR-005 | Knowledge Retrieval | Real-time targeted Drive read via `read_drive_file` tool | NO vector DB, NO RAG, NO embeddings. Agent uses AI-generated title+description to pick files. Charter §1.2, §2.3. | Decided | 2026-04-10 |
| ADR-006 | Self-Describing Knowledge Base | AI generates `ai_description` at index time and re-generates on content hash change during `read_drive_file` | Users write nothing. Descriptions stay fresh automatically. Content hash avoids redundant LLM calls. | Decided | 2026-04-11 |
| ADR-007 | Knowledge Base Cap | 15 files per workspace, enforced server-side | Bounded context window predictability. Product decision from Charter §1.1. | Decided | 2026-04-10 |
| ADR-008 | Slack Event Scope | `app_mention` only — NO `message.channels` | Avoid running AI on every message. All replies posted in originating thread via `thread_ts`. | **Superseded by ADR-021** | 2026-04-10 |
| ADR-009 | Google Drive Backend Auth | Offline refresh token (one-time OAuth during workspace setup) | Simpler UX than Service Account file-sharing. Backend exchanges refresh → short-lived access token per call. | Decided | 2026-04-10 |
| ADR-010 | Slack Bot Token Storage | Encrypted at rest with AES-256-GCM (field: `encrypted_slack_bot_token`) | Token has full bot permissions. Cannot be plaintext. Same primitive as BYOK and Drive tokens. | Decided | 2026-04-10 |
| ADR-011 | Multi-Workspace per User | Supported from day 1, both schema and UI | Low marginal cost. Avoids painful later migration. Each workspace has independent Slack/BYOK/Drive config. | **Superseded by ADR-024** | 2026-04-10 |
| ADR-012 | Copy-Then-Optimize from `new_app` | Auth, BYOK, Orchestrator directly copied and stripped | Saves estimated 4+ sprints vs writing from scratch. Strip scopes documented in Charter §3.3 + §10 Epic Seed Map. | Decided | 2026-04-10 |
| ADR-013 | Slack Response Mode | Post full reply via `chat.postMessage` (no streaming) | Simpler than `chat.update` polling. Streaming is v2 concern. | Decided | 2026-04-10 |
| ADR-014 | Frontend Stack | React 19 + Tailwind 4 + Vite 8 + TanStack Router + TanStack Query + Zustand | Matches new_app; enables maximum copy-reuse of auth components. | Decided | 2026-04-11 |
| ADR-015 | Database | Supabase (PostgreSQL) | Matches new_app. Includes RLS-ready tables. Supabase Python client 2.28.3 (not 3.0 pre-release). | Decided | 2026-04-11 |
| ADR-016 | MIME Type Support | Google Docs/Sheets/Slides (export API) + PDF (pypdf) + Word (python-docx) + Excel (openpyxl) | Unsupported types rejected at index time with clear error. | Decided | 2026-04-10 |
| ADR-017 | bcrypt Length Validation | Enforce `len(password) ≤ 72 bytes` at register endpoint; return 422 if exceeded | bcrypt 5.0 raises ValueError instead of silent truncation. | Decided | 2026-04-10 |
| ADR-018 | Context Overflow Handling | Prune oldest thread messages first until payload fits; append trim notice to reply | No hard failure on long threads. | Decided | 2026-04-10 |
| ADR-019 | Deploy Target | VPS + Coolify (self-hosted PaaS on a VPS). Coolify handles Traefik TLS, builds, and env vars. | Stable public HTTPS URL for Slack webhooks. No ngrok churn. Already owned by solo dev. | Decided | 2026-04-11 |
| ADR-020 | Database Hosting | Self-hosted Supabase instance (user-managed). Credentials injected via env at deploy time. | Zero additional infra to provision. Avoids Supabase hosted free-tier limits during demo. | Decided | 2026-04-11 |
| ADR-021 | Slack Event Scope (supersedes ADR-008) | `app_mention` (channels) + `message.im` (DMs). NO `message.channels`. Self-message filter required on `message.im`. Replies always threaded via `thread_ts`. | Supports both public channel Q&A and private 1:1 assistant use. DMs require self-message filter to prevent bot reply loops. Requires `slack_bot_user_id` stored at install time. | Decided | 2026-04-11 |
| ADR-022 | Design System | Asana-inspired warm minimalism. Coral brand (`#F43F5E`), slate neutrals, Inter + JetBrains Mono, Tailwind 4 CSS-first, Radix primitives + Lucide icons. No shadcn, no MUI, no Framer Motion. Full spec in `tee_mo_design_guide.md`. | Matches Charter §2.6 minimalistic modern UI principle. Zero dependency on heavy UI frameworks. Implementable in ~1 sprint. | Decided | 2026-04-11 |
| ADR-023 | Skills Architecture | Copy new_app `skill_service.py` + 4 orchestrator tools, stripped. Simplified schema: `id, workspace_id, name, summary, instructions, is_active, created_at, updated_at`. NO `related_tools` (Tee-Mo has one tool). NO `is_system` (no seeded skills). NO REST endpoints or dashboard UI — chat-only CRUD. L1 catalog auto-injected into conversation-tier system prompt every turn. | Enables live "teach the bot" demo — a killer hackathon moment. Chat-only avoids 1+ sprint of dashboard work. Stripping `related_tools` keeps tools simple. No seed skills avoids tuning work. | Decided | 2026-04-11 |
| ADR-024 | Workspace Model (supersedes ADR-011) | Shape is `1 user : N SlackTeams : N Workspaces : N channel bindings`. New `slack_teams` table holds one row per Slack install (team_id, bot user, encrypted bot token). `workspaces` table is now a **knowledge silo** (Drive + BYOK + skills + Drive auth) with a `slack_team_id` FK and `is_default_for_team` flag. New `workspace_channels` table binds Slack channels to Workspaces (PK `slack_channel_id` — a channel is owned by at most one Workspace globally). Partial unique index `one_default_per_team` enforces exactly one default Workspace per SlackTeam. | Lets one user run many isolated knowledge silos under the same Slack install (e.g., Marketing brain for `#marketing`, Engineering brain for `#eng`) without re-installing the bot and without leaking data across channels. Separating team install from silo creation also removes duplication of the encrypted bot token. Charter §4 + §5.3 + §5.5 + §10 Slack Epic + §10 Dashboard Epic updated. | Decided | 2026-04-11 |
| ADR-025 | Explicit Channel Binding (no silent fallback) | A channel must have an explicit `workspace_channels` row to get AI replies. `app_mention` in an unbound channel → bot posts a one-line in-thread reply with a setup link to the dashboard (channel+team pre-filled) and stops. No listener on `member_joined_channel`, no proactive messages, no auto-join. Only `message.im` (DMs) consults the team's default Workspace. Binding UI is the dashboard channel picker (`conversations.list`). Channel status is shown as **Active** (bound + `is_member=true`) or **Pending /invite** (bound + `is_member=false`). Scopes added: `channels:read`, `groups:read`. | Avoids two footguns: (a) silently using the wrong knowledge base for a channel just because a default exists, (b) the bot posting unsolicited welcome messages when invited. Makes the "which channel uses which brain" answer explicit in the DB rather than implicit in fallback logic. Charter §5.5 + §6 + §10 Slack Epic. | Decided | 2026-04-11 |
| ADR-026 | **Deploy Infrastructure Pulled Forward** (complements ADR-019/020) | Ship a minimal production deploy to Coolify on `https://teemo.soula.ge` during Sprint S-03 as the first story of the sprint — NOT in Release 3 as originally scoped. Single Dockerfile (multi-stage: Vite build → FastAPI serving frontend static files + `/api/*` routes), GitHub auto-deploy on push to `main` (repo `sandrinio/tee-mo` public), Coolify Traefik HTTPS, production secrets injected via Coolify env var UI (never committed). Backend `CORS_ORIGINS` includes `https://teemo.soula.ge`; frontend `VITE_API_URL=/api` (same-origin). Reshapes EPIC-003 into **Slice A** (S-03 schema + deploy + PyJWT fix) and **Slice B** (S-05 workspace CRUD), with **EPIC-005 Phase A** (Slack OAuth install) landing in S-04 between them. Eliminates EPIC-003's dev-only manual team-create path entirely. | Slack webhooks, Google OAuth production redirect_uri, cross-subdomain cookies, CORS credentials, and `secure=true` cookie flag all require public HTTPS — none of which are validatable on `http://localhost`. Deferring deploy to Release 3 means all of those concerns surface on Day 7 when there's no time to fix them. Pulling deploy forward costs ~3h in S-03 and saves us from a Day-7 cascade of surprises. User confirmed `teemo.soula.ge` DNS already points at Coolify, GitHub auto-deploy is the chosen method, and Coolify env vars are the secret-injection path. Release 1 target date slips by 1 day (2026-04-12 → 2026-04-13) to absorb the added scope. EPIC-010 (Demo Hardening) scope reduces correspondingly — it no longer owns initial deploy setup, only seed data + README polish + demo script. | Decided | 2026-04-12 |

---

## 4. Dependencies & Integration Map

### External Dependencies
| Service | Purpose | Status | Risk if Unavailable |
|---------|---------|--------|---------------------|
| Slack API (OAuth + Events + Web API) | Bot install, `app_mention` events, thread replies | Available | **P0 — blocks Release 2**. No mitigation; this IS the product. |
| Google OAuth 2.0 | Offline refresh token flow for Drive access | Available | **P0 — blocks Release 2**. No mitigation. |
| Google Drive API v3 | File metadata, content reads, exports | Available | **P0**. Must have working credentials by Day 3. |
| Google Picker API | File selection UI | Available | P1 — could fall back to manual drive_file_id entry if blocked. |
| OpenAI / Anthropic / Google LLM APIs | User-provided BYOK inference | Available | P1 per user — bot errors gracefully if user's key is invalid. Not a host-side dependency. |
| Supabase | PostgreSQL DB + client | Available (local or hosted) | **P0 — blocks all data persistence**. Use local Docker Supabase for dev safety. |
| VPS + Coolify | Production deploy target (backend + frontend). Public HTTPS via Coolify's Traefik. | Available | **P0 — hosts the live Slack webhook endpoint**. Stable URL removes the ngrok subdomain problem entirely. |
| Self-hosted Supabase | PostgreSQL + Auth-free backend DB. Credentials provided via env at implementation time. | Available (user-managed) | **P0 — all persistence**. No local Docker Supabase needed. Env vars: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET` (≥32 bytes). |
| GitHub (sandrinio/tee-mo) | Source control + demo deploy origin | Available | P2 — local backup exists. |

### Cross-Epic Dependencies
| Epic | Depends On | Relationship | Status |
|------|------------|--------------|--------|
| EPIC-002 (Auth) | EPIC-001 (Scaffold) | Needs Supabase `users` table + FastAPI app | Sequential |
| EPIC-003 Slice A (Schema) | EPIC-002 (Auth) | Needs only the Supabase client already proven in S-01 | **S-03 — in planning** |
| EPIC-003 Slice B (Workspace CRUD) | EPIC-005 Phase A (real Slack team rows exist) | Replaced the dev-only manual team path per ADR-026 | **S-05 — deferred until after S-04** |
| EPIC-004 (BYOK) | EPIC-002 + EPIC-003 Slice B | Needs authenticated user + workspace CRUD | Sequential |
| EPIC-005 Phase A (Slack OAuth install) | EPIC-003 Slice A (schema) + ADR-026 (deploy — needs public HTTPS for OAuth redirect_uri) | `teemo_slack_teams` table must exist; `https://teemo.soula.ge` must be reachable | **S-04 — pulled into Release 1 per ADR-026** |
| EPIC-005 Phase B (Slack events) | EPIC-007 (AI Agent — event handler calls `build_agent`) | Schedule TBD — don't over-plan | **Deferred** |
| EPIC-006 (Google Drive) | EPIC-003 Slice B (Workspace entity) | Needs Workspace for `encrypted_google_refresh_token` — per-workspace Drive auth | Sequential |
| EPIC-007 (AI Agent) | EPIC-004 + EPIC-006 | Needs BYOK key (hard gate) + `read_drive_file` tool target | **Critical path** — the last convergence point. |
| EPIC-005 (Slack) | EPIC-007 (AI Agent) | Slack event handler calls `build_agent` and posts result | Slack + Agent must converge by Sprint 12. |
| EPIC-008 (Wizard) | EPIC-004 + EPIC-005 + EPIC-006 | Composes all setup steps into one flow | Release 3 entry condition. |
| EPIC-009 (Error Handling) | All EPICs 004–007 | Wires error paths into user-facing messages | Parallel with EPIC-008. |
| EPIC-010 (Demo Hardening) | All prior | Final deploy and seed | Sprints 15–16 only. |

---

## 5. Strategic Constraints

| Constraint | Type | Impact | Mitigation |
|------------|------|--------|------------|
| **Hackathon deadline 2026-04-18** | Deadline | Hard stop — nothing ships after this | Release 2 must be complete by Day 6 EOD. Days 7-8 reserved for polish and buffer. |
| **Solo developer, 4h per sprint** | Capacity | ~64 total build hours across 16 sprints | Copy-then-optimize from new_app (ADR-012) saves ~4 sprints. No epic gets more than 3 sprints. |
| **Zero host LLM cost** | Budget | Cannot use host-owned API keys anywhere | BYOK hard gate enforced in UI + backend (ADR-006). |
| **Must demo end-to-end** | Scope | Every epic is P0; no graceful degradation | Release 2 exit criteria require full pipeline working. |
| **Slack requires public HTTPS** | Infrastructure | Local-only dev won't receive events | Deploy to VPS via Coolify by Sprint 5. Stable domain means Slack event URL set once. |
| **Google OAuth requires verified domain for production** | Compliance | May show "unverified app" warning during demo | Use Google Cloud test mode — add judges as test users if needed. |
| **bcrypt 5.0 breaking change** | Dependency | Passwords > 72 bytes raise ValueError | ADR-017: hard validation at register endpoint. |
| **Supabase JS 3.0 is pre-release** | Dependency | Must not accidentally install 3.0 | Pin `supabase==2.28.3` in requirements. |

---

## 6. Open Questions

> All charter-level questions have been resolved. Remaining questions are tactical and will be resolved during epic decomposition.

| Question | Options | Impact | Owner | Status |
|----------|---------|--------|-------|--------|
| Deploy target for public HTTPS endpoint | VPS + Coolify | ADR-019 | Solo dev | **Decided** 2026-04-11 |
| Supabase: local Docker vs hosted | Self-hosted Supabase (user-provided creds at impl time) | ADR-020 | Solo dev | **Decided** 2026-04-11 |
| Demo Slack workspace | Solo dev already has an account — revisit at Sprint 13 | Affects demo reliability | Solo dev | **Parked** — revisit Sprint 13 |
| Google Cloud project verification status | Solo dev will provide Google Cloud project at impl time | Affects judge walkthrough | Solo dev | **Parked** — revisit Sprint 8 |
| DM support in addition to channel @mentions | Both — `app_mention` + `message.im` | ADR-021 | Solo dev | **Decided** 2026-04-11 |

---

## 7. Delivery Log

> Appended by Team Lead when each release is archived.

| Sprint | Delivery | Date | Summary | Tag |
|--------|----------|------|---------|-----|
| S-01 | D-01 Release 1: Foundation | 2026-04-11 | **Scaffold delivered.** 4/4 stories Done (Fast Track), ~1.75% aggregate correction tax, 1 Dev bounce on STORY-001-03 (version-pin fix from Team Lead sprint-context error — lesson recorded). Ships: FastAPI 0.135.3 scaffold with `/api/health` (per-table `teemo_*` aggregate, cached Supabase singleton, 6 hermetic tests), Vite 8.0.8 + React 19.2.5 + Tailwind 4.2 CSS-first `@theme`, Inter/JetBrains Mono via `@fontsource`, 3 design-system primitives (Button/Card/Badge), TanStack Router file-based routes, landing page with live backend health smoke test via TanStack Query. 3 flashcards recorded (sprint-context must quote Charter verbatim; don't redefine Tailwind 4 built-in slate tokens; bcrypt 5.0 72-byte boundary). | (untagged — release tagging introduced in S-02) |
| S-02 | D-01 Release 1: Foundation | 2026-04-11 | **Auth delivered end-to-end.** 4/4 stories Done (Fast Track), ~2.5% aggregate correction tax, 0 bounces, 0 escalations. Ships: backend `app/core/security.py` (bcrypt + JWT + `validate_password_length` 72-byte guard per ADR-017), 5 auth routes (`/register`, `/login`, `/refresh`, `/logout`, `/me`) with httpOnly cookies (`samesite="lax"` — deliberate deviation for EPIC-005/006 OAuth redirects), `get_current_user_id` dependency, frontend Zustand `useAuth` store + 5 typed `lib/api.ts` wrappers + `AuthInitializer`, and full UI: `/login`, `/register`, `/app` placeholder (gated by `ProtectedRoute`), `SignOutButton`, enabled landing CTA. 22 backend pytest (9 unit + 13 live Supabase integration) + 10 frontend Vitest (first Vitest setup in Tee-Mo, `vitest@^2.1.9`). Architect integration audit verdict: **SHIP** (zero findings). 4 flashcards recorded (samesite=lax, LaxEmailStr for email-validator 2.x `.test` TLD, Vitest `vi.mock` TDZ, TanStack Router `tsc -b && vite build` ordering). 1 BUG filed for S-03 backlog: PyJWT module-level options leak causing test-order flake (production unaffected). Browser walkthrough (11 steps §2.2) deferred by user — not human-verified. | v0.2.0-auth |
| S-03 | D-01 Release 1: Foundation + Deploy + Slack Install | 2026-04-12 | **Deploy + ADR-024 schema + PyJWT fix + Slack stub delivered. Live at `https://teemo.soula.ge`.** 6 stories planned; 5 bounced + 1 (STORY-003-06 production verification) collapsed into sprint close. Fast Track throughout, 0 bounces, 0 escalations, ~0.83% aggregate correction tax. Ships: multi-stage Dockerfile (Node 22 Alpine → Python 3.11 slim, 962 MB) + `.dockerignore` + FastAPI same-origin static serving via `StaticFiles("/assets")` + explicit SPA catch-all route + HEAD-compatible healthcheck at `/api/health`; 318-line Coolify setup runbook; 3 ADR-024 schema migrations (`teemo_slack_teams`, `teemo_workspace_channels`, `teemo_workspaces` ALTER with FK + `is_default_for_team` + `one_default_per_team` partial unique index); `TEEMO_TABLES` extended 4→6; **BUG-20260411 FIXED** via scoped `jwt.PyJWT()` instance in `decode_token` + regression-lock test (backend test suite now passes in any order); `POST /api/slack/events` verification stub handling `url_verification` challenge. Backend test suite 22 → 36 (+14). Frontend 10 unchanged. User ran SQL migrations + created Slack app + added Google Cloud scopes in parallel. **2 post-release incidents caught and resolved during sprint close**: (1) Coolify Traefik routed to port 3000 instead of 8000 — config fix in Coolify UI; (2) health check used `select("id")` on schemaless-id tables, hotfix commit `ce7c0b1` swapped to `select("*")`. Both documented as flashcards. Live verification green: 6-table `/api/health` = `"ok"`, `/` SPA served, `/login` SPA fallback, `/api/slack/events` url_verification round-trip. Release tag: v0.3.0-deploy. **Release 1 still incomplete**: EPIC-005 Phase A (S-04 real Slack OAuth install) + EPIC-003 Slice B (S-05 workspace CRUD) remaining. | v0.3.0-deploy |

---

## 8. Change Log

| Date | Change | By |
|------|--------|-----|
| 2026-04-11 | Initial Roadmap created from Charter. 3 releases, 10 epics, 18 ADRs, 8 external dependencies, 5 open questions. | Claude (doc-manager) |
| 2026-04-11 | Closed 2 open questions: ADR-019 deploy to VPS + Coolify; ADR-020 self-hosted Supabase. §4 External Dependencies updated. §5 Constraints updated. Demo workspace and Google Cloud verification parked until sprints 13 and 8 respectively. | Claude (doc-manager) |
| 2026-04-11 | DM support decided (ADR-021 supersedes ADR-008). Design Guide decided (ADR-022) — Asana-inspired, full spec in `tee_mo_design_guide.md`. Added `design_guide_ref` to frontmatter. | Claude (doc-manager) |
| 2026-04-11 | Skills feature decided (ADR-023). Chat-only CRUD, `related_tools` stripped, no seeded skills. Folded into EPIC-007 (AI Agent) — no new epic needed. Adds ~2.5 hours of work to the existing critical path. | Claude (doc-manager) |
| 2026-04-11 | **Workspace model restructured (ADR-024 supersedes ADR-011, ADR-025 new).** New shape: `1 user : N SlackTeams : N Workspaces : N channel bindings`. Slack install is now team-level (new `slack_teams` table); Workspaces are knowledge silos (Drive + BYOK + skills + Drive auth) hanging off a team; channels bind explicitly to Workspaces via new `workspace_channels` table. Channels never fall back to a default — only DMs do. Binding is dashboard-led only (no `member_joined_channel` listener). Impacts: EPIC-001 (3 new/changed tables + partial unique index), EPIC-003 (two-level team→workspace navigation), EPIC-005 (new resolvers, binding REST, `channels:read`+`groups:read` scopes), EPIC-008 (two-phase wizard, channel chips, make-default toggle). Cost estimate: ~30% on top of EPIC-003 + EPIC-005, absorbed into existing sprint budget. S-02 (auth) unaffected. | Claude (doc-manager) |
| 2026-04-11 | §7 Delivery Log backfilled with S-01 and S-02 entries. Both delivered into D-01 Release 1: Foundation. S-02 tagged v0.2.0-auth. | Team Lead (S-02 close) |
| 2026-04-11 | **Post-S-02 status sync.** §2 Release 1 exit-criteria checkmarks updated (3/4 complete). EPIC-001 marked `Done (S-01) — partial` with the 2 ADR-024 migrations (`teemo_slack_teams`, `teemo_workspace_channels`) + `teemo_workspaces` ALTERs explicitly reassigned to EPIC-003 (they were added to scope after EPIC-001 was planned and logically belong with team/workspace CRUD). EPIC-002 marked `Done (S-02)` with the `v0.2.0-auth` tag. EPIC-003 marked `Next up` and flagged the empty-state shape required before EPIC-005 lands (manual/dev-only SlackTeam creation as the pragmatic unlock). Frontmatter status: `Planning` → `In Execution — Release 1 75% delivered`. Cross-epic dependency table updated to note EPIC-002 ✅ delivered. | Team Lead (post-S-02 sync) |
| 2026-04-12 | **ADR-026 Decided — Deploy infrastructure pulled forward to S-03.** User confirmed `teemo.soula.ge` DNS already resolves to Coolify, GitHub auto-deploy via `sandrinio/tee-mo` public repo is the chosen method, Coolify env vars will hold production secrets. **EPIC-003 reshaped into two slices**: Slice A (S-03 schema + deploy + PyJWT fix) and Slice B (S-05 workspace CRUD). **EPIC-005 split**: Phase A (OAuth install, locally + prod-testable once deploy is live) pulled into Release 1 at S-04; Phase B (events + channel binding) deferred to after EPIC-007 because it depends on the agent. **Dev-only manual team-create path eliminated** — EPIC-003 Slice B attaches to real Slack teams from Phase A instead. Release 1 target slipped by 1 day (2026-04-12 → 2026-04-13) to absorb the added scope. EPIC-010 (Demo Hardening) scope reduces — no longer owns initial deploy setup. §2 Release 1, §3 ADR-026, §4 dependency table, §8 Change Log all updated in one pass. | Team Lead (ADR-026 planning) |
| 2026-04-12 | **Sprint S-03 closed, live at `https://teemo.soula.ge` as `v0.3.0-deploy`.** §7 Delivery Log row appended. Frontmatter status updated to "Release 1 ~85% delivered". 4 new flashcards recorded in `FLASHCARDS.md` (Starlette `StaticFiles(html=True)` is not a SPA fallback, Starlette `@app.get` doesn't auto-handle HEAD, `supabase.table().select("id")` fails on non-id-PK tables, V-Bounce agent absolute-path worktree isolation break). BUG-20260411 closed by STORY-003-04. 2 post-release incidents caught during verification (Coolify port 3000→8000, health-check `select("id")` hotfix in commit `ce7c0b1`) — both documented as flashcards, no blocking debt carried forward. | Team Lead (S-03 close) |
