---
epic_id: "EPIC-018"
status: "Active"
children:
  - "STORY-018-01-service-layer"
  - "STORY-018-02-rest-endpoints"
  - "STORY-018-03-executor-cron"
  - "STORY-018-04-agent-tools"
  - "STORY-018-05-ui-list-history"
  - "STORY-018-06-ui-modals"
ambiguity: "🟢"
context_source: "PROPOSAL-001-teemo-platform.md"
owner: "sandrinio"
target_date: "TBD"
created_at: "2026-04-14T00:00:00Z"
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
> **Ported from V-Bounce.** Original: `product_plans.vbounce-archive/backlog/EPIC-018_scheduled_automations/EPIC-018_scheduled_automations.md`. Carried forward during ClearGate migration 2026-04-24.

> **Sprint note:** EPIC-018 was Active in SPRINT-12 at migration cutover. Stories 018-01 through 018-06 were in progress at time of porting.

# EPIC-018: Scheduled Automations

## 1. Problem & Value

### 1.1 The Problem

Tee-Mo's agent today is strictly reactive — a user has to @mention the bot (or DM it) for the agent to do anything. There's no way to say "every Monday at 09:00, summarize last week's releases into #general" or "tomorrow at 5pm, remind me to close the quarterly report." Users must open Slack and re-issue the same prompt every time they want a recurring task, and one-off scheduled work has no home at all.

### 1.2 The Solution

Add **scheduled automations**: a user (via the dashboard UI or via an agent tool call from Slack chat) defines a prompt plus a schedule (recurring or one-time), and a background scheduler spawns the agent at the scheduled time, runs the prompt with full access to the workspace's tools/knowledge, and delivers the result to the bound Slack channel.

Both surfaces (UI and agent tools) write through the **same service layer** and the **same REST API**, so behavior is identical regardless of who created the automation. A **dry-run** action executes the prompt exactly like a real run but returns the output to the user's screen instead of posting to Slack. Every run (scheduled or dry) is captured in an execution history so users can audit what the agent said and when.

Reference implementation: `chy_automations` in `Documents/Dev/new_app` (see §4 for the copy-then-strip plan).

### 1.3 Success Metrics (North Star)
- A workspace owner can create a recurring automation from the dashboard in < 60s.
- A workspace owner can create the same automation from a Slack chat message by describing it to the bot.
- Dashboard lists all automations per workspace with next-run time, last-run status, and toggles.
- Dashboard "Dry Run" button executes the prompt and renders the generated output on screen without posting to Slack and without writing delivered_content to history (run is still logged).
- Execution history shows ≥ last 50 runs per automation with status, timing, tokens used, and error (if any).
- No automation can leak across workspaces (workspace_id filter enforced in service + RLS).
- Scheduled runs fire within ±60s of `next_run_at` under normal load.

---

## 2. Scope Boundaries

### ✅ IN-SCOPE (Build This)
- [ ] `teemo_automations` table + `teemo_automation_executions` table (migrations)
- [ ] SQL helpers: `calculate_next_run_time(schedule JSONB, from_time)` + `get_due_automations()` RPC
- [ ] `automation_service.py` — CRUD + schedule validation + history pruning (cap 50 rows/automation)
- [ ] REST endpoints: `POST/GET/PATCH/DELETE /api/workspaces/:id/automations`, `GET /api/workspaces/:id/automations/:id/history`, `POST /api/workspaces/:id/automations/test-run`
- [ ] `automation_executor.py` — runs a single automation end-to-end: builds the agent, runs the prompt, writes execution row, delivers to Slack, advances `next_run_at`, deactivates one-time automations
- [ ] `automation_cron.py` — asyncio background loop (60s tick) following the existing `wiki_ingest_cron` / `drive_sync_cron` pattern, registered in `main.py` lifespan
- [ ] `skip_if_active` guard — if a prior execution is still `running`, skip this tick and advance `next_run_at`
- [ ] 4 agent tools (wired into the existing conversation-tier agent): `create_automation`, `list_automations`, `update_automation`, `delete_automation`
- [ ] System prompt: `## Scheduled Automations` section describing the tools and when to use them (keyword-triggered, same pattern as Skills catalog)
- [ ] Frontend: `AutomationsSection` inline in `WorkspaceCard` (below KeySection / MCP section) — list, badges, enable/disable toggle, delete, history drawer, dry-run button
- [ ] Frontend: `AddAutomationModal` — name, prompt (textarea), schedule builder (once/daily/weekdays/weekly/monthly + time + timezone), **multi-select target channel picker** (checkbox list of already-bound channels — user must select ≥ 1)
- [ ] Frontend: `AutomationHistoryDrawer` — execution list with status badge, timestamps, expandable generated output, error detail
- [ ] Frontend: `useAutomations.ts` — TanStack Query hooks for CRUD + history + dry-run
- [ ] Dry-run UX: modal opens showing loading → rendered output (markdown). No Slack post. No delivered_content write. Execution row is written with `was_dry_run=true` flag
- [ ] Timezone support: per-automation IANA tz name, persisted on the row; UI defaults to user browser tz
- [ ] One-time automations auto-deactivate (`is_active=false`) after the single run completes

### ❌ OUT-OF-SCOPE (Do NOT Build This)
- **Data source binding** — unlike new_app, the user does NOT attach documents/saved-queries/github filters to an automation. The agent already has workspace knowledge tools (`read_drive_file`, wiki retrieval) and the prompt itself must mention what it needs.
- **Non-Slack delivery adapters** (email, telegram, document-output) — Tee-Mo delivers to Slack only. Within Slack, an automation MAY target one-or-more of the workspace's already-bound channels (multi-fanout), but no other delivery medium.
- **`delivery_method` discriminator** — only Slack-channel delivery is supported; no mode enum needed.
- **Default-channel fallback** — there is no implicit default. The user (or agent on the user's behalf) must always explicitly pick at least one bound channel from `teemo_workspace_channels` for the workspace.
- **Mention resolution in prompts** (`@[Doc]`, `::blueprint`) — new_app's prompt-enrichment step is not copied. Plain prompts only.
- **ARQ / Redis worker** — reuse Tee-Mo's existing in-process asyncio cron pattern; do not introduce a new dependency.
- **Multi-tenant distributed scheduler / leader election** — single-process cron is acceptable for the hackathon scale (one backend instance).
- **Cron expression syntax** (`0 9 * * MON`) — structured JSONB schedule only (daily / weekdays / weekly / monthly / once).
- **Retries on failure** — a failed run is recorded as `status='failed'` with an error; the schedule keeps advancing. No auto-retry.
- **Usage/cost dashboards for automation tokens** — `tokens_used` is recorded on the row but no aggregate UI is built here.
- **Agent tool for `test_run` (dry-run)** — dry-run is a UI-only affordance. The agent does not expose a "preview" tool (keeps the agent surface small; users who want to dry-run use the dashboard).
- **Per-workspace concurrency limits / quotas** — a future concern.

---

## 3. Context

### 3.1 User Personas
- **Workspace Admin (Dashboard)**: Wants precise control — schedule builder, timezone picker, dry-run preview, history browsing.
- **Workspace Admin (Slack)**: Wants to say "@tee-mo every weekday at 9am post a summary of new drive files into #standup" and have it just work.
- **Slack User (Recipient)**: Doesn't create automations — just sees the agent's scheduled posts land in the bound channel as regular bot messages.

### 3.2 Constraints
| Type | Constraint |
|------|------------|
| **Security** | Workspace isolation: all CRUD and cron queries filtered by `workspace_id`. Only workspace owners may mutate; members+ may read. RLS matches the pattern used for `teemo_workspaces` and MCP. |
| **Tech Stack** | Reuse existing Pydantic AI agent factory (EPIC-007). Reuse Slack Bolt AsyncApp for `chat.postMessage`. Reuse asyncio-cron pattern (`wiki_ingest_cron`). No new runtime dependencies (no ARQ, no Redis). |
| **Performance** | Cron tick fires every 60s. Per-run execution budget bounded by agent BYOK model latency. `skip_if_active` prevents overlapping runs of the same automation. History pruning caps at 50 rows per automation. |
| **BYOK Hard Gate** | Workspace has exactly one BYOK key (the user-provided one) — scheduled runs use that key. If missing/invalid at run time, write `status='failed'` history row with a human-readable error; do not crash the cron. No personal-key fallback. |

---

## 9. Artifact Links

**Stories (Status Tracking):**
- [x] STORY-018-01 — Automations Schema + Service Layer → **Spec complete** (`STORY-018-01-service-layer.md`)
- [x] STORY-018-02 — Automations REST Endpoints → **Spec complete** (`STORY-018-02-rest-endpoints.md`)
- [x] STORY-018-03 — Automation Executor + Cron Loop → **Spec complete** (`STORY-018-03-executor-cron.md`)
- [x] STORY-018-04 — Agent Tools + System Prompt Integration → **Spec complete** (`STORY-018-04-agent-tools.md`)
- [x] STORY-018-05 — Dashboard UI: Automations Section + History → **Spec complete** (`STORY-018-05-ui-list-history.md`)
- [x] STORY-018-06 — Dashboard UI: Add Modal + Schedule Builder + Dry Run → **Spec complete** (`STORY-018-06-ui-modals.md`)

## Change Log
| Date | Change | By |
|------|--------|-----|
| 2026-04-14 | Initial draft. Reference implementation: new_app `chy_automations`. Port reshaped to: (a) drop data-source binding, (b) drop multi-adapter delivery (Slack-only), (c) drop ARQ/Redis (reuse existing asyncio cron pattern), (d) dry-run is UI-only. 6 stories proposed. | sandrinio + Claude |
| 2026-04-14 | Blocking questions resolved. Multi-channel fanout: `slack_channel_ids TEXT[]` with per-channel `delivery_results` JSONB on executions; status adds `'partial'`. Workspace BYOK only. System prompt keyword-gated. | sandrinio + Claude |
| 2026-04-24 | Ported to ClearGate v0.2.1. | ClearGate migration |
