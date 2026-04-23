---
proposal_id: "PROPOSAL-001"
status: "Approved"
author: "@sandrinio"
approved: true
created_at: "2026-04-10T00:00:00Z"
updated_at: "2026-04-24T00:00:00Z"
created_at_version: "vbounce-strategy-phase"
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

# PROPOSAL-001: Tee-Mo — Context-Aware Slack AI Agent (BYOK)

> **Historical note.** This proposal is the ClearGate umbrella parent for all EPIC-002 through EPIC-024 drafted under V-Bounce Engine. The original 545-line authoritative Charter lives at `product_plans.vbounce-archive/strategy/tee_mo_charter.md`; this proposal is its compact ClearGate-shaped surface. Approved in V-Bounce on 2026-04-11 (Charter frontmatter: `ambiguity: 🟢 Low, readiness: Ready for Roadmap`) and carried forward verbatim during the 2026-04-24 ClearGate migration.

## 1. Initiative & Context

### 1.1 Objective
Tee-Mo is a context-aware AI agent embedded in Slack that answers team queries using thread history and up to 15 user-curated Google Drive documents. The **BYOK (Bring Your Own Key)** model makes the host bear zero inference cost — each workspace supplies its own OpenAI, Anthropic, or Google key. Users can also teach the agent custom **skills** through natural Slack chat.

### 1.2 The "Why"
- Teams need context-aware AI in-Slack without per-seat subscriptions or vendor lock-in.
- Existing chat-AI products either index everything (vector DB overhead, privacy concerns) or gate behind vendor apps.
- BYOK + real-time targeted Drive read = zero host inference cost + small, auditable knowledge surface that the user fully controls.

### 1.3 Success Definition
- Host operates at **zero LLM inference cost** — 100% of API charges go to the end-user's own key.
- Users query workspace knowledge without leaving Slack.
- Any of the three supported providers (OpenAI, Anthropic, Google) is interchangeable without code changes.
- A workspace adds/updates/removes Drive knowledge files with no developer involvement.
- API keys, Slack bot tokens, and Google refresh tokens are all AES-256-GCM encrypted at rest; never exposed to frontend or logs.

## 2. Technical Architecture & Constraints

### 2.1 Dependencies
Full pinned-version table in Charter §3.2. Core stack:
- **Frontend:** React 19.2.5, Tailwind CSS 4.2, Vite 8.0.8, TanStack Router 1.168.12, TanStack Query 5.97, Zustand 5.0.12
- **Backend:** FastAPI 0.135.3, Pydantic AI 1.79.0 (`[openai,anthropic,google]`), slack-bolt 1.28.0, cryptography 46.0.7, PyJWT 2.12.1, bcrypt 5.0.0
- **Data:** Self-hosted Supabase (PostgreSQL). Prefix: `teemo_*`
- **External:** Slack Events/Web/OAuth API, Google Drive API v3, Google Picker API, Google OAuth (offline refresh token), user's chosen LLM provider

### 2.2 System Constraints

| Type | Constraint |
|---|---|
| Architectural | BYOK mandatory — host never calls provider with own key. No vector DB. No RAG. Real-time targeted Drive reads via `read_drive_file` / `search_wiki`. |
| Security | AES-256-GCM for all user-supplied secrets (BYOK keys, Slack bot tokens, Google refresh tokens). Plaintext never logged or returned to frontend. |
| Event scope | `app_mention` (channels) + `message.im` (DMs). NO `message.channels`. Self-message filter required on DM path. Replies always threaded via `thread_ts`. |
| Hard caps | 15 Drive files per workspace; 72-char password max (bcrypt 5.0 compliance). |
| Identity | Email + password only. No email verification. No Google SSO. JWT (15min access + 7d refresh, httpOnly). |
| Relationship shape | `1 User : N SlackTeams : N Workspaces : N channel bindings`. `is_default_for_team` enforced via partial unique index. |
| Deploy | VPS + Coolify (self-hosted PaaS). Live at `https://teemo.soula.ge`. GitHub auto-deploy from `sandrinio/tee-mo` main. |

## 3. Scope Impact (Touched Files & Data)

### 3.1 Architectural Domain
This umbrella proposal spans the full initial build and subsequent iteration. Scope is carved into epic families — see the Epic Seed Map in Charter §10:

- **Auth** — EPIC-002
- **BYOK Key Management** — EPIC-004
- **AI Agent & Orchestrator (incl. skills, two-tier models)** — EPIC-007, EPIC-015
- **Slack Integration (Phase A install, Phase B events/bindings)** — EPIC-005, EPIC-011
- **Google Drive Integration & Knowledge Index** — EPIC-006
- **Dashboard / Workspace Setup UI** — EPIC-003, EPIC-008
- **Wiki / Knowledge Pipeline** — EPIC-013, EPIC-017
- **Structured Logging & Observability** — EPIC-016
- **Automations (scheduled)** — EPIC-018
- **Production Hardening (UX polish, concurrency, token mgmt)** — EPIC-022, EPIC-023, EPIC-024
- **MCP Integration** — EPIC-012
- **Local Upload** — EPIC-014

### 3.2 Known Files
All shipped modules live under `backend/` and `frontend/` per standard FastAPI + Vite scaffolding. Per-epic file maps in each child epic's §4 Technical Grounding.

### 3.3 Historical Artifacts
- **Charter (authoritative detail):** `product_plans.vbounce-archive/strategy/tee_mo_charter.md`
- **Roadmap (ADRs 001-027, delivery log):** `product_plans.vbounce-archive/strategy/tee_mo_roadmap.md`
- **Design Guide:** `.cleargate/knowledge/design-guide.md`
- **V-Bounce sprint archive:** `product_plans.vbounce-archive/archive/sprints/sprint-01/` through `sprint-11/`
- **Migration record:** `MIGRATION_CLEARGATE.md`, `MIGRATION_PORT_MAP.md`

## 🔒 Approval Gate

**Pre-approved.** This proposal was ratified under V-Bounce on 2026-04-11 (Charter frontmatter: `ambiguity: 🟢 Low`). All EPIC-\* work items in `.cleargate/delivery/` reference this proposal via `context_source`. The gate stays `approved: true` — future scope expansions either amend this proposal (Change Log below) or file new proposals.

## Change Log

| Date | Change | By |
|------|--------|----|
| 2026-04-10 | Charter initial draft | Claude (doc-manager, V-Bounce) |
| 2026-04-10 to 2026-04-11 | 14 Charter revisions — final state: 🟢 Low ambiguity, 7 design principles, 27 ADRs, workspace model restructure (ADR-024), skills feature, DM support, two-tier model strategy, Google Drive offline refresh flow, full MIME support | Claude (doc-manager, V-Bounce) |
| 2026-04-24 | Ported to ClearGate as PROPOSAL-001. Compact umbrella form; full detail preserved in `product_plans.vbounce-archive/strategy/tee_mo_charter.md`. `approved: true` carried forward. | Claude Opus 4.7 (migration/cleargate) |
