# Architectural Decision Records (ADRs)

> ADRs are **immutable once Decided**. Override by adding a new ADR that supersedes.
> Ported verbatim from V-Bounce `tee_mo_roadmap.md` §3 on 2026-04-24. Full historical context lives at `product_plans.vbounce-archive/strategy/tee_mo_roadmap.md`.

---

| ID | Decision | Choice | Rationale | Status | Date |
|----|----------|--------|-----------|--------|------|
| ADR-001 | Authentication | Custom email/password JWT (copy from new_app `security.py` + `auth.py`) | Supabase Auth ruled out — Charter §1.2. No email verification. JWT: 15min access + 7d refresh in httpOnly cookies. | Decided | 2026-04-10 |
| ADR-002 | Encryption | AES-256-GCM via Python `cryptography.AESGCM` (copy new_app `encryption.py`) | Authenticated encryption. Same primitive for BYOK keys, Slack bot tokens, Google refresh tokens. NOT Fernet. | Decided | 2026-04-10 |
| ADR-003 | AI Framework | Pydantic AI 1.79 with `[openai,anthropic,google]` extras | Provider-agnostic model string format (`provider:model-id`). Copy `build_orchestrator` pattern from new_app. | Decided | 2026-04-10 |
| ADR-004 | Two-Tier Model Strategy | Conversation tier (user-selectable) + Scan tier (hardcoded small/fast model per provider) | Summarization is cheap and high-volume; doesn't need frontier reasoning. Same BYOK key, different `model_id`. See Charter §3.4. | Decided | 2026-04-11 |
| ADR-005 | Knowledge Retrieval | Real-time targeted Drive read via `read_drive_file` tool | NO vector DB, NO RAG, NO embeddings. Agent uses AI-generated title+description to pick files. Charter §1.2, §2.3. | Decided | 2026-04-10 |
| ADR-006 | Self-Describing Knowledge Base | AI generates `ai_description` at index time; re-generates on content hash change during `read_drive_file` | Users write nothing. Descriptions stay fresh automatically. Content hash avoids redundant LLM calls. | Decided | 2026-04-11 |
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
| ADR-022 | Design System | Asana-inspired warm minimalism. Coral brand (`#F43F5E`), slate neutrals, Inter + JetBrains Mono, Tailwind 4 CSS-first, Radix primitives + Lucide icons. No shadcn, no MUI, no Framer Motion. Full spec in `.cleargate/knowledge/design-guide.md`. | Matches Charter §2.6 minimalistic modern UI principle. Zero dependency on heavy UI frameworks. Implementable in ~1 sprint. | Decided | 2026-04-11 |
| ADR-023 | Skills Architecture | Copy new_app `skill_service.py` + 4 orchestrator tools, stripped. Simplified schema: `id, workspace_id, name, summary, instructions, is_active, created_at, updated_at`. NO `related_tools`. NO `is_system`. NO REST/dashboard UI — chat-only CRUD. L1 catalog auto-injected into conversation-tier system prompt every turn. | Enables live "teach the bot" demo — a killer hackathon moment. Chat-only avoids 1+ sprint of dashboard work. Stripping `related_tools` keeps tools simple. No seed skills avoids tuning work. | Decided | 2026-04-11 |
| ADR-024 | Workspace Model (supersedes ADR-011) | `1 user : N SlackTeams : N Workspaces : N channel bindings`. New `slack_teams` table holds one row per Slack install. `workspaces` is now a **knowledge silo** with `slack_team_id` FK + `is_default_for_team` flag. New `workspace_channels` table (PK `slack_channel_id` — a channel is globally unique). Partial unique index `one_default_per_team`. | Lets one user run many isolated knowledge silos under the same Slack install without re-installing the bot and without leaking data across channels. Separates team install from silo creation, removing bot token duplication. | Decided | 2026-04-11 |
| ADR-025 | Explicit Channel Binding (no silent fallback) | A channel must have an explicit `workspace_channels` row to get AI replies. `app_mention` in an unbound channel → bot posts a one-line setup-nudge in-thread with dashboard link and stops. No `member_joined_channel` listener, no proactive messages, no auto-join. Only `message.im` (DMs) consults the team's default Workspace. Scopes added: `channels:read`, `groups:read`. | Avoids silently using the wrong knowledge base, and avoids unsolicited bot messages. Makes "which channel uses which brain" explicit in the DB, not implicit in fallback logic. | Decided | 2026-04-11 |
| ADR-026 | Deploy Infrastructure Pulled Forward (complements ADR-019/020) | Ship minimal production deploy to Coolify on `https://teemo.soula.ge` during S-03 as first story of the sprint. Single Dockerfile (multi-stage Vite → FastAPI static + `/api/*`). GitHub auto-deploy on push to `main`. Coolify Traefik HTTPS + env-var secrets UI. Reshapes EPIC-003 into Slice A (S-03 schema + deploy + PyJWT fix) and Slice B (S-05 workspace CRUD), with EPIC-005 Phase A (Slack OAuth install) landing in S-04 between them. Eliminates EPIC-003's dev-only manual team-create path. | Slack webhooks, Google OAuth prod redirect_uri, cross-subdomain cookies, and `secure=true` cookie flag all require public HTTPS — unverifiable on localhost. Deferring deploy to Release 3 would surface those Day 7 with no time to fix. Pulling forward costs ~3h, saves Day-7 cascade. Release 1 slipped by 1 day to absorb. EPIC-010 scope reduces accordingly. | Decided | 2026-04-12 |
| ADR-027 | Wiki as Primary Knowledge Path | Agent uses `search_wiki` (BM25 full-text over `teemo_wiki_pages`) as primary retrieval. `read_document` (fetches raw `teemo_documents.cached_content` by UUID) is secondary fallback for: (a) exact quotes / verbatim data, (b) documents not yet `sync_status = synced`, (c) user references a specific file by name/ID. Conversation-tier system prompt describes both paths + routing rules. | Wiki pages are pre-chunked concept/entity units — much better retrieval signal than raw document text. `read_document` fallback prevents coverage gaps during ingest window and preserves precision lookups. Removing `read_drive_file` in STORY-015-03 was gated on `read_document` as a drop-in replacement. | Decided | 2026-04-13 |

---

## Superseded ADRs Summary

| Original | Superseded By | Why |
|---|---|---|
| ADR-008 Slack Event Scope (`app_mention` only) | **ADR-021** | DM support added; second trigger `message.im`. |
| ADR-011 Multi-Workspace per User (`1 user : N workspaces`) | **ADR-024** | Restructured to `1 user : N SlackTeams : N Workspaces : N channel bindings`. |

## Change Log

| Date | Change | By |
|------|--------|----|
| 2026-04-24 | Initial port from V-Bounce `tee_mo_roadmap.md` §3. All 27 ADRs carried forward verbatim. | Claude Opus 4.7 (migration/cleargate) |
