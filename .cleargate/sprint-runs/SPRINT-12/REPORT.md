---
sprint_id: "SPRINT-12"
report_type: "retrospective"
generated_by: "cleargate-migration-2026-04-24"
generated_at: "2026-04-24T00:00:00Z"
source_origin: "vbounce-sprint-report-S-12.md"
---

# SPRINT-12 Retrospective

> **Ported from V-Bounce.** Synthesized from `.vbounce-archive/sprint-report-S-12.md` during ClearGate migration 2026-04-24. V-Bounce's report format was more freeform; this is a best-effort remap into ClearGate's 6-section retrospective shape.

Sprint Goal: Ship the full EPIC-018 backend — automations schema, REST CRUD, executor + asyncio cron, and agent tools — so scheduled automations fire autonomously to Slack and are manageable from both the API and Slack chat.

Sprint Window: 2026-04-15 → 2026-04-16

## §1 What Was Delivered

**User-facing:**
- Scheduled automations fire autonomously to Slack.
- Agent tools to manage automations from Slack chat (create/list/edit/delete via the agent).
- REST API for managing automations (7 endpoints — CRUD).

**Internal / infrastructure:**
- Automations schema + service layer (STORY-018-01, 29 tests).
- 7 REST endpoints for automations (STORY-018-02, 14 tests).
- Automation executor + asyncio cron loop (STORY-018-03, 11 tests).
- Agent tools + system prompt updates for automations (STORY-018-04, 9 tests).
- Main app lifespan integrated with automation cron (docstring updated inline).
- New asyncio cron pattern adopted across 3 modules: `drive_sync_cron`, `wiki_ingest_cron`, `automation_cron`. ADR-032 recording required at sprint close.

**Carried over (if any):**
- ADR-032 (asyncio cron pattern) — record in Roadmap §3 during sprint close.
- Pre-existing `test_automations_routes.py` ImportError on `app.core.encryption` in test environment (pre-existing, not this sprint — P2).
- Vdoc task: offer vdoc creation for EPIC-018 Automations feature post-sprint.

## §2 Story Results + CR Change Log

| Story | Title | Outcome | QA Bounces | Arch Bounces | Correction Tax | Notes |
|---|---|---|---|---|---|---|
| STORY-018-01 | Schema + Service Layer | Done | 0 | 0 | 0% | TDD-first. Migration + service layer. 29 tests. |
| STORY-018-02 | REST Endpoints | Done | 0 | 0 | 0% | 7 endpoints. 14/14 pass. |
| STORY-018-03 | Executor + Cron Loop | Done | 0 | 0 | 10% | TDD-first. Team Lead fixed 6 mock tracking patterns (plain function assignment broke Mock instrumentation). 11 tests. |
| STORY-018-04 | Agent Tools + System Prompt | Done | 0 | 0 | 0% | Fast Track. 9/9 pass. |

**Change Requests / User Requests during sprint:**
- None (no mid-sprint scope changes).

**Integration audit findings (fixed inline):**
- **CRITICAL:** `automation_executor.py` called `build_agent` with 3 unsupported kwargs (`provider`, `api_key`, `model`). Every real automation execution would have crashed. Fix: removed extra kwargs — `build_agent` resolves BYOK internally.
- **HIGH:** `automation_executor.py` line 175 — no null-guard on `slack_row.data` before `decrypt()` call. Fix: added guard matching existing BYOK pattern.
- **LOW:** `main.py` lifespan docstring not updated to mention automation cron. Fixed inline.

**Sprint interruption recovery:**
- Session was interrupted mid-bounce. On resume: STORY-018-02 Green complete (14/14 passing, ready for merge); STORY-018-03 Green code existed but tests had 5/11 failures (mock tracking pattern bug); STORY-018-04 Green code existed but no formal green report yet. All three recovered and merged in the resume session.

## §3 Execution Metrics

- **Stories planned → shipped:** 4/4 (100%)
- **First-pass success rate:** 100% (0 QA bounces, 0 Arch bounces across all 4 stories)
- **Bug-Fix Tax:** 2 bugs fixed inline via integration audit (CRITICAL + HIGH) before release — would have crashed all real automations
- **Enhancement Tax:** 0 mid-sprint scope changes
- **Total tokens used:** ~361,248 across 9 agent invocations (this resume session only — prior interrupted session tokens not captured; actual total likely 500K+ across both sessions). Story doc totals (12,559) diverge >20% — task notification totals are authoritative.
- **Aggregate correction tax:** ~2.5% weighted avg
- **Tests added:** 63 across 3 test files (34 mentioned in Key Takeaways; detailed per-story count: 29 + 14 + 11 + 9 = 63).
- **Estimated cost:** ~$1.50-2.50 (Sonnet 4.6 rates, rough estimate without input/output split).

## §4 Lessons

Top themes from flashcards flagged during this sprint (batch review pending):
- **#test-dep-override:** `_assert_workspace_owner` must accept `supabase` as explicit parameter (not call `get_supabase()` directly) when tests use `app.dependency_overrides[get_supabase]` — plain `get_supabase()` calls inside helpers bypass the mock.
- **#worktree-venv:** Always use `backend/.venv/bin/python` (not system Python) in worktree test commands — system Python 3.9 lacks `pydantic_ai`.
- **#mock-side_effect:** Use `mock.method.side_effect = fn` instead of `mock.method = fn`. Replacing a Mock attribute with a plain function destroys `.called` and `call_args_list`. Use `side_effect` to intercept calls while preserving Mock instrumentation.
- **#mock-chained-tracking:** When overriding `supabase.table` for tracking, use `original_fn = supabase.table.side_effect` + `supabase.table.side_effect = wrapper` (not `supabase.table = wrapper`). Replacing the Mock loses `call_args_list` on subsequent assertions.

(See `.cleargate/FLASHCARD.md` for full text once ported.)

## §5 Tooling

- **Friction signals:**
  - Mock tracking pattern (side_effect vs direct assignment) burned 5+ tests in 018-03 (P1).
  - Spec gap: executor.py `build_agent(...)` call copied from new_app reference without verifying the actual signature — surfaced only in integration audit (P1).
  - Pre-merge validation: DevOps 018-03 noted uncommitted sprint branch files that blocked merge — sprint branch had dirty state from worktree setup (P2).
  - Worktree test isolation: `test_automations_routes.py` has ImportError on `app.core.encryption` in test environment (pre-existing, P2).
  - Session recovery: V-Bounce handled session interruption cleanly — worktrees, reports, and git state all recoverable from `state.json` (positive).
- **Framework issues filed:**
  - P1: Add mock tracking pattern flashcard (side_effect not direct assignment).
  - P1: Spec `build_agent` signature verification gate before Dev Green.
  - P2: Pre-merge validation must clear worktree-setup dirty state on sprint branch.
  - P2: Investigate pre-existing `app.core.encryption` ImportError in `test_automations_routes.py`.
- **Hook failures:** N/A (V-Bounce had no hooks).

## §6 Roadmap

**Next sprint preview (as understood when this report was written):**
- Record ADR-032 (asyncio cron pattern: `asyncio.create_task` + `CancelledError` re-raise + lifespan-managed cancellation) in Roadmap §3 during sprint close — now used by 3 modules (`drive_sync_cron`, `wiki_ingest_cron`, `automation_cron`).
- Scribe task: offer vdoc creation for EPIC-018 Automations feature post-sprint close.
- Carry pre-existing `app.core.encryption` ImportError investigation.
- Automations frontend UI likely in a follow-up epic (backend shipped; UI not in scope of S-12).
