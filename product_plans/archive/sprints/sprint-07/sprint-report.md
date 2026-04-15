---
sprint_id: "S-07"
sprint_goal: "Ship EPIC-007 — Pydantic AI agent factory, skills CRUD, two-tier model strategy, Slack app_mention + message.im event handlers, thread history with speaker labels."
dates: "2026-04-12"
status: "Achieved"
total_tokens_used: "N/A (not instrumented)"
roadmap_ref: "product_plans/strategy/tee_mo_roadmap.md"
tag: "v0.7.0"
---

# Sprint Report: S-07

## 1. What Was Delivered

### User-Facing (Accessible Now)

- **Bot responds to @mentions in Slack** — `app_mention` event triggers agent, replies in-thread with answer
- **Bot responds to DMs** — `message.im` with self-message filter to prevent reply loops
- Unbound channel: bot posts one-line setup-nudge reply with dashboard link (ADR-025)
- No-key error: bot replies with clear "configure a BYOK key" message in-thread

### Internal / Backend (Not Directly Visible)

- `build_agent(tier, workspace_id)` factory — `conversation` tier (user-selectable) + `scan` tier (hardcoded fast model)
- `teemo_skills` table + `skill_service.py` CRUD — `load_skill`, `create_skill`, `update_skill`, `delete_skill` tools in agent
- Thread history service with speaker labels (`You:` / `Tee-Mo:`) via `conversations.replies`
- Channel binding REST CRUD: `GET/POST/DELETE /api/workspaces/:id/channels`, `POST /api/workspaces/:id/make-default`
- Slack dispatch: `app_mention` resolves via `workspace_channels` → `build_agent` → post reply; `message.im` resolves via team default workspace

### Not Completed

None. All 6 stories delivered. EPIC-007 complete.

### Product Docs Affected

N/A — vdoc not installed.

---

## 2. Story Results

| Story | Epic | Label | Final State | Bounces (QA) | Bounces (Arch) | Correction Tax | Tax Type |
|-------|------|-------|-------------|--------------|----------------|----------------|----------|
| STORY-007-01: Skill service | EPIC-007 | L2 | Done | 0 | 0 | 0% | — |
| STORY-007-03: Thread history service | EPIC-007 | L2 | Done | 0 | 0 | 0% | — |
| STORY-007-04: Channel binding REST | EPIC-007 | L2 | Done | 0 | 0 | 0% | — |
| STORY-007-02: Agent factory | EPIC-007 | L2 | Done | 0 | 0 | 0% | — |
| STORY-007-05: Slack dispatch | EPIC-007 | L3 | Done | 0 | 1 | 5% | Bug Fix |
| STORY-007-06: Manual E2E verification | EPIC-007 | L1 | Done | 0 | 0 | 0% | — |

### Story Highlights

- **STORY-007-05 (L3, 1 Arch bounce)**: Architect caught missing `thread_ts` propagation and missing error handling in the dispatch handler. Fixed before merge. All three providers (OpenAI, Anthropic, Google) verified working in STORY-007-06 E2E.
- **STORY-007-02 (Full Bounce)**: Agent factory passed QA + Arch on first attempt. Two-tier model strategy (`conversation` + `scan` tiers, same BYOK key) implemented cleanly.
- **STORY-007-04**: 107/107 full suite pass. Channel binding REST verified against `workspace_channels` table.

### 2.1 Change Requests

None.

---

## 3. Execution Metrics

### V-Bounce Quality

| Metric | Value |
|--------|-------|
| Stories Planned | 6 |
| Stories Delivered | 6 |
| Stories Escalated | 0 |
| Total QA Bounces | 0 |
| Total Architect Bounces | 1 |
| Bounce Ratio | 17% (1/6) |
| Average Correction Tax | ~0.8% |
| Bug Fix Tax | ~0.8% (thread_ts + error handling) |
| Enhancement Tax | 0% |
| First-Pass Success Rate | 83% |
| Total Tests Written | ~49 new (15+5+8+12+9+0); 148 total |

---

## 4. Lessons Learned

| Source | Lesson | Recorded? | When |
|--------|--------|-----------|------|
| (no new lessons flagged) | — | — | — |

---

## 5. Retrospective

### What Went Well

- Core demo pipeline complete: register → workspace → Slack install → BYOK → @mention → bot answers in-thread. End-to-end demoable.
- All three BYOK providers (OpenAI, Anthropic, Google) verified working in user-confirmed E2E.
- Architect catch on STORY-007-05 was legitimate — `thread_ts` missing would have caused replies to land outside threads in production.

### What Didn't Go Well

- 1 Arch bounce on the Slack dispatch story (007-05). Root cause: dispatch handler spec didn't explicitly state thread_ts propagation requirement. Story spec improved for future dispatch stories.

### Framework Self-Assessment

#### Templates

| Finding | Source Agent | Severity | Suggested Fix |
|---------|-------------|----------|---------------|
| Dispatch handler stories should explicitly list thread_ts + error handling requirements | Architect | Friction | Add "thread propagation" checklist item to Slack story template §3 |

---

## 6. Change Log

| Date | Change | By |
|------|--------|-----|
| 2026-04-15 | Sprint Report generated retroactively at S-11 close audit | Team Lead |
