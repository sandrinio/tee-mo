---
sprint_id: "sprint-07"
sprint_goal: "Ship EPIC-007 — AI agent responds to Slack @mentions and DMs using BYOK key, with thread history context and speaker identification. Skills via chat."
dates: "2026-04-12 – 2026-04-13"
status: "Confirmed"
delivery: "D-03"
confirmed_by: "sandrinio"
confirmed_at: "2026-04-12"
---

# Sprint S-07 Plan

## 0. Sprint Readiness Gate
> This sprint CANNOT start until the human confirms this plan.

### Pre-Sprint Checklist
- [x] All stories below have been reviewed with the human
- [x] Open questions (§3) are resolved or non-blocking
- [x] No stories have 🔴 High ambiguity (spike first)
- [x] Dependencies identified and sequencing agreed
- [x] Risk flags reviewed from Risk Registry
- [x] **Human has confirmed this sprint plan** (2026-04-12)

---

## 1. Active Scope
> Stories pulled from the backlog for execution during this sprint window.

| Priority | Story | Epic | Label | V-Bounce State | Blocker |
|----------|-------|------|-------|----------------|---------|
| 1 | [STORY-007-01: Skill Service](./STORY-007-01-skill-service.md) | EPIC-007 | L1 | Ready to Bounce | — |
| 2 | [STORY-007-03: Thread History Service](./STORY-007-03-thread-history.md) | EPIC-007 | L2 | Ready to Bounce | — |
| 3 | [STORY-007-04: Channel Binding REST](./STORY-007-04-channel-binding-rest.md) | EPIC-007 | L2 | Ready to Bounce | — |
| 4 | [STORY-007-02: Agent Factory + Skill Tools](./STORY-007-02-agent-factory.md) | EPIC-007 | L3 | Ready to Bounce | 007-01 |
| 5 | [STORY-007-05: Slack Event Dispatch](./STORY-007-05-slack-dispatch.md) | EPIC-007 | L3 | Ready to Bounce | 007-02, 007-03 |
| 6 | [STORY-007-06: Manual E2E Verification](./STORY-007-06-manual-e2e.md) | EPIC-007 | L1 | Ready to Bounce | 007-05 |

### Context Pack Readiness

**STORY-007-01: Skill Service**
- [x] Story spec complete (§1)
- [x] Acceptance criteria defined (§2)
- [x] Implementation guide written (§3)
- [x] Ambiguity: 🟢 Low

**STORY-007-02: Agent Factory + Skill Tools**
- [x] Story spec complete (§1)
- [x] Acceptance criteria defined (§2)
- [x] Implementation guide written (§3)
- [x] Ambiguity: 🟢 Low

**STORY-007-03: Thread History Service**
- [x] Story spec complete (§1)
- [x] Acceptance criteria defined (§2)
- [x] Implementation guide written (§3)
- [x] Ambiguity: 🟢 Low

**STORY-007-04: Channel Binding REST**
- [x] Story spec complete (§1)
- [x] Acceptance criteria defined (§2)
- [x] Implementation guide written (§3)
- [x] Ambiguity: 🟢 Low

**STORY-007-05: Slack Event Dispatch**
- [x] Story spec complete (§1)
- [x] Acceptance criteria defined (§2)
- [x] Implementation guide written (§3)
- [x] Ambiguity: 🟢 Low

**STORY-007-06: Manual E2E Verification**
- [x] Story spec complete (§1)
- [x] Acceptance criteria defined (§2)
- [x] Implementation guide written (§3)
- [x] Ambiguity: 🟢 Low

### Escalated / Parking Lot
- (None)

---

## 2. Execution Strategy

### Phase Plan
- **Phase 1 (parallel)**: STORY-007-01 (skill service) + STORY-007-03 (thread history) + STORY-007-04 (channel binding REST) — zero shared files, parallel worktrees
- **Phase 2 (after 007-01 merges)**: STORY-007-02 (agent factory + skill tools — imports skill_service)
- **Phase 3 (after 007-02 + 007-03 merge)**: STORY-007-05 (slack dispatch — wires everything together)
- **Phase 4 (after 007-05 merges + deploy)**: STORY-007-06 (manual E2E in real Slack — requires user to configure Slack event subscriptions + bind a channel)

### Merge Ordering
| Order | Story | Reason |
|-------|-------|--------|
| 1a | STORY-007-01 | Foundation — skill_service.py consumed by agent factory |
| 1b | STORY-007-03 | Independent — thread history consumed by dispatch |
| 1c | STORY-007-04 | Independent — channel binding REST consumed by dispatch (workspace resolution) and by E2E (bind a channel before testing) |
| 2 | STORY-007-02 | Agent factory — imports skill_service from 007-01 |
| 3 | STORY-007-05 | Integration — imports agent factory (007-02) + thread history (007-03), queries workspace_channels (007-04 schema already exists) |
| 4 | STORY-007-06 | Manual E2E — no code, verifies full stack |

> 007-01, 007-03, and 007-04 can merge in any order — they touch completely disjoint file sets.

### Shared Surface Warnings
| File / Module | Stories Touching It | Risk |
|---------------|--------------------:|------|
| `backend/app/main.py` | 007-04 (mount `channels_router`) | Low — one `include_router()` call |
| `backend/app/api/routes/slack_events.py` | 007-05 (replace 202 passthrough with dispatch) | **Medium** — modifies S-04-shipped endpoint. Must preserve signature verification and url_verification. |
| `backend/app/services/__init__.py` | 007-01, 007-03, 007-05 (new files in services/) | Low — additive only |

### Execution Mode
| Story | Label | Mode | Architect Override? | Reason |
|-------|-------|------|---------------------|--------|
| STORY-007-01 | L1 | Fast Track | — | Pure CRUD service, well-defined copy source |
| STORY-007-02 | L3 | Full Bounce | — | Core agent factory, first Pydantic AI usage, copy+strip from new_app |
| STORY-007-03 | L2 | Fast Track | — | Single service file, straightforward Slack API |
| STORY-007-04 | L2 | Fast Track | — | Standard REST CRUD, follows established patterns |
| STORY-007-05 | L3 | Full Bounce | — | Cross-cutting integration, modifies live Slack endpoint, asyncio.create_task pattern |
| STORY-007-06 | L1 | Fast Track | — | Manual verification, no code |

### ADR Compliance Notes
- 007-02: Pydantic AI 1.79 with lazy provider imports (ADR-003). Model string format verified against new_app.
- 007-02: Conversation tier only (ADR-004). Scan tier deferred to EPIC-006.
- 007-02: Skills are chat-only CRUD (ADR-023). No REST endpoints, no dashboard UI for skills.
- 007-04: Explicit channel binding (ADR-025). No fallback to default for channel mentions.
- 007-05: Both `app_mention` + `message.im` (ADR-021). Self-message filter on DMs.
- 007-05: All replies in-thread via `thread_ts` (ADR-008/021). No top-level posts.
- 007-05: No streaming — `chat.postMessage` only (ADR-013).
- All: BYOK keys decrypted in-memory only via `core.encryption.decrypt()` (ADR-002). Never logged.

### Copy Source Reference
| Target | Copy Source | Strip |
|--------|-----------|-------|
| `backend/app/services/skill_service.py` | `new_app/backend/app/services/skill_service.py` | `SYSTEM_SKILLS`, `seed_system_skills()`, `related_tools`, `is_system`, `TOOL_CATALOG` validation |
| `backend/app/agents/agent.py` | `new_app/backend/app/agents/orchestrator.py` | All tools except 4 skill tools, `chy_agent_definitions` lookup, `chy_workspace_agent_config` lookup, persona injection, team roster, response formatting, blueprint catalog, `internet_search` param |

### Dependency Chain
| Story | Depends On | Reason |
|-------|-----------|--------|
| STORY-007-02 | STORY-007-01 | Agent factory imports skill_service for tool implementations |
| STORY-007-05 | STORY-007-02 | Dispatch calls build_agent() |
| STORY-007-05 | STORY-007-03 | Dispatch calls fetch_thread_history() |
| STORY-007-06 | STORY-007-05 | E2E requires full stack deployed |

### Risk Flags
- **Pydantic AI first-use (Medium):** First use of `pydantic_ai.Agent` in Tee-Mo. Copy source from new_app is proven, but version differences (if any) could surface. Mitigation: pin exact version, copy exact model instantiation pattern.
- **Slack 3-second timeout (High):** `slack_events.py` must return 200 before agent runs. `asyncio.create_task` is the mitigation. If the event loop is blocked by something else, Slack will retry. Accepted risk.
- **S-04 regression on slack_events.py (Medium):** STORY-007-05 modifies the live events endpoint. Must preserve signature verification and url_verification. Full backend suite run post-merge.
- **Provider API availability (Low):** All provider calls use user's BYOK key. If key is invalid, error is surfaced gracefully. No Tee-Mo-side API dependency.
- **Module separation discipline (Low):** `agents/` package must not import FastAPI. Enforced by code review in Architect audit for 007-02.

---

## 3. Sprint Open Questions
| Question | Options | Impact | Owner | Status |
|----------|---------|--------|-------|--------|
| Thread history format for Pydantic AI | A: Plain text, B: ModelMessage objects | Affects agent quality. §3.3 of STORY-007-05 proposes Option B (ModelMessage). | sandrinio | **Decided — B** (ModelMessage objects for proper role separation) |
| Slack event subscriptions configured? | User must add `app_mention` + `message.im` at Slack API dashboard | Blocks STORY-007-06 E2E | sandrinio | Open — user does this before 007-06 |

---

<!-- EXECUTION_LOG_START -->
## 4. Execution Log
> Updated by the Lead after each story completes.

| Story | Final State | QA Bounces | Arch Bounces | Tests Written | Correction Tax | Notes |
|-------|-------------|------------|--------------|---------------|----------------|-------|
<!-- EXECUTION_LOG_END -->
