---
sprint_id: "sprint-12"
sprint_goal: "Ship the full EPIC-018 backend — automations schema, REST CRUD, executor + asyncio cron, and agent tools — so scheduled automations fire autonomously to Slack and are manageable from both the API and Slack chat."
dates: "04/15 - 04/16"
status: "Active"
delivery: "D-07"
confirmed_by: "sandrinio"
confirmed_at: "2026-04-16"
---

# Sprint S-12 Plan

## 0. Sprint Readiness Gate
> This sprint CANNOT start until the human confirms this plan.

### Pre-Sprint Checklist
- [x] All stories below have been reviewed with the human
- [x] Open questions (§3) are resolved or non-blocking
- [x] No stories have 🔴 High ambiguity (spike first)
- [x] Dependencies identified and sequencing agreed
- [x] Risk flags reviewed from Risk Registry
- [x] **Human has confirmed this sprint plan**

---

## 1. Active Scope

| Priority | Story | Epic | Label | V-Bounce State | Blocker |
|----------|-------|------|-------|----------------|---------|
| 1 | [STORY-018-01: Schema + Service Layer](./STORY-018-01-service-layer.md) | EPIC-018 | L2 | Done | — |
| 2 | [STORY-018-02: REST Endpoints](./STORY-018-02-rest-endpoints.md) | EPIC-018 | L2 | Done | STORY-018-01 |
| 3 | [STORY-018-03: Executor + Cron Loop](./STORY-018-03-executor-cron.md) | EPIC-018 | L2 | Ready to Bounce | STORY-018-01 |
| 4 | [STORY-018-04: Agent Tools + System Prompt](./STORY-018-04-agent-tools.md) | EPIC-018 | L2 | Ready to Bounce | STORY-018-01 |

**Total: 4 stories** (4× L2)

### Context Pack Readiness

**STORY-018-01: Schema + Service Layer**
- [x] Story spec complete (§1)
- [x] Acceptance criteria defined (§2)
- [x] Implementation guide written (§3)
- [x] Ambiguity: 🟢 Low

**STORY-018-02: REST Endpoints**
- [x] Story spec complete (§1)
- [x] Acceptance criteria defined (§2)
- [x] Implementation guide written (§3)
- [x] Ambiguity: 🟢 Low

**STORY-018-03: Executor + Cron Loop**
- [x] Story spec complete (§1)
- [x] Acceptance criteria defined (§2)
- [x] Implementation guide written (§3)
- [x] Ambiguity: 🟢 Low

**STORY-018-04: Agent Tools + System Prompt**
- [x] Story spec complete (§1)
- [x] Acceptance criteria defined (§2)
- [x] Implementation guide written (§3)
- [x] Ambiguity: 🟢 Low

### Escalated / Parking Lot
- (none)

---

## 2. Execution Strategy

### Phase Plan

```
Phase 1 — Foundation (no dependencies)
└── STORY-018-01: Schema + Service Layer   ← migration + automation_service.py, unlocks everything

Phase 2 — Build out (parallel, all depend on 018-01)
├── STORY-018-02: REST Endpoints           ← 7 endpoints; mounts router in main.py
├── STORY-018-03: Executor + Cron Loop     ← executor + cron loop; registers cron in main.py lifespan
└── STORY-018-04: Agent Tools              ← 4 agent tools + system prompt; touches agent.py only
```

### Merge Ordering

| Order | Story | Reason |
|-------|-------|--------|
| 1 | STORY-018-01 | Foundation — no dependencies; service layer consumed by all others |
| 2 | STORY-018-02 | Mounts router in `main.py` — merge before 018-03 to serialise main.py edits |
| 3 | STORY-018-03 | Registers cron in `main.py` lifespan — after 018-02 to avoid merge conflict on same block |
| 4 | STORY-018-04 | Modifies `agent.py` only — no shared surface with 018-02/03; can merge last |

### Shared Surface Warnings

| File / Module | Stories Touching It | Risk |
|---------------|--------------------:|------|
| `backend/app/main.py` | 018-02 (router mount), 018-03 (lifespan cron) | **Medium** — sequential merge required (018-02 first, then 018-03). Each touches a different block but same file. |
| `backend/app/services/automation_service.py` | 018-01 (creates), 018-02/03/04 (imports) | **Low** — 018-01 creates the module; others import it read-only. No conflicts. |
| `backend/app/agents/agent.py` | 018-04 only | **Low** — single owner. |

### Execution Mode

| Story | Label | Mode | Reason |
|-------|-------|------|--------|
| STORY-018-01 | L2 | Full Bounce (QA/Arch skipped for velocity) | Foundation migration — must be correct. TDD-first. |
| STORY-018-02 | L2 | Full Bounce (QA/Arch skipped for velocity) | 7 endpoints with auth + ownership checks. |
| STORY-018-03 | L2 | Full Bounce (QA/Arch skipped for velocity) | Executor pipeline has partial/failure/skip logic. |
| STORY-018-04 | L2 | Fast Track | Agent tools are thin wrappers over service layer. Service already tested in 018-01. |

### ADR Compliance Notes
- **ADR-002** (AES-256-GCM encryption): 018-03 decrypts bot token + BYOK key — follows existing `decrypt()` call pattern from `wiki_ingest_cron._resolve_workspace_key`. ✅
- **ADR-027** (wiki primary knowledge path): 018-04 adds automation tools but does not modify wiki tools or system prompt wiki section. ✅
- **New ADR needed (post-sprint)**: Asyncio cron pattern chosen over APScheduler for automations. Record as ADR-032 in Roadmap §3 during S-12 close.

### Dependency Chain

| Story | Depends On | Reason |
|-------|-----------|--------|
| STORY-018-02 | STORY-018-01 | REST routes wrap service layer CRUD |
| STORY-018-03 | STORY-018-01 | Executor calls `automation_service.prune_execution_history`; cron calls `get_due_automations` RPC |
| STORY-018-04 | STORY-018-01 | Agent tools call `automation_service` CRUD |

### Risk Flags
- **Slack bot token resolution chain** (018-03): executor needs `workspace → slack_team_id → teemo_slack_teams.encrypted_slack_bot_token`. If workspace has no linked Slack team, delivery fails gracefully (per spec — write `status='failed'` with clear error). Low risk: existing production workspaces all have Slack teams from EPIC-005.
- **RPC `calculate_next_run_time` call** (018-03): SQL function defined in migration (018-01). If RPC returns `None` for a malformed schedule, next_run_at is set to NULL and automation goes dormant silently. Mitigation: `validate_schedule()` in the service layer catches malformed schedules at create/update time; cron should never see one in practice.
- **`agent.py` concurrent-edit** (018-04): STORY-018-04 modifies `agent.py`. If STORY-018-03 also modified `agent.py` it would conflict — but 018-03 doesn't touch `agent.py` (it imports `build_agent` but doesn't modify the file). ✅ No conflict.
- **Hackathon time**: 3 days remain (→ Apr 18). S-12 delivers the backend foundation; S-13 (frontend) must ship by Apr 17 to leave a day for demo rehearsal.

---

## 3. Sprint Open Questions

| Question | Options | Impact | Owner | Status |
|----------|---------|--------|-------|--------|
| Should dry-run (test-run endpoint, STORY-018-02 R6) write a `was_dry_run=true` execution row? | A: Write row (full audit trail). B: Ephemeral — no row written. | History drawer shows previews or not | sandrinio | **Decided in STORY-018-02: ephemeral for the `/test-run` endpoint; dry-run rows via executor path in 018-06** |
| Startup stale-run cleanup: reset only `running` rows older than 10 min, or ALL `running` rows? | A: 10-min threshold (safe — avoids false-positives on fast restarts). B: All running rows. | Risk of cancelling legitimately-running automations | sandrinio | **Decided: A (10-min threshold per STORY-018-03 R8)** |

---

<!-- EXECUTION_LOG_START -->
## 4. Execution Log

| Story | Final State | QA Bounces | Arch Bounces | Tests Written | Correction Tax | Notes |
|-------|-------------|------------|--------------|---------------|----------------|-------|
| STORY-018-01 | Done | 0 | 0 | — | 0% | TDD: 29 unit tests, clean merge, QA/Arch skipped for velocity |
| STORY-018-02 | Done | 0 | 0 | — | 0% | 14/14 tests pass. QA/Arch skipped for velocity per sprint plan. |
<!-- EXECUTION_LOG_END -->
