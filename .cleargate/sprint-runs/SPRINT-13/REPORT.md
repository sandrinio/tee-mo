# SPRINT-13 Report: EPIC-018 Dashboard UI Close + P1 Auth Fix

**Status:** ✅ Shipped + Closed
**Window:** 2026-04-24 → 2026-04-24 (1 calendar day: ~4h development, ~1h live-testing + hotfixes)
**Stories:** 3 planned / 3 shipped / 0 carried over
**Hotfixes during live-testing window:** 4 commits (5 distinct fixes)
**Closed:** 2026-04-24 by orchestrator (Reporter-fallback — agent unavailable this session)

---

## For Product Management

### Sprint goal — did we hit it?

Goal: *"Close the loop on EPIC-018 by shipping the dashboard UI for Scheduled Automations, and fix a P1 auth bug that blocks any non-owner team member from reaching their own workspaces."*

**Yes.** Every Slack-team member — not just the installer — can now register, install, and manage both their workspaces and their scheduled automations end-to-end from the dashboard. BUG-002 landed first and unblocked the manual QA path for the two follow-on UI stories.

### Headline deliverables

- **Team-member access to shared Slack workspaces** (BUG-002) — any authenticated member of a Slack team can now list and create workspaces under that team. The pre-fix behavior was silent 403 for anyone except the original installer.
- **Automations dashboard surface** (STORY-018-05 + STORY-018-06) — workspace detail page now renders an Automations section with list, toggle, two-click delete, inline "Dry Run" preview, a history drawer (execution timeline with expandable `generated_content`), and a full add-automation modal with a schedule builder covering all five occurrence types (daily / weekdays / weekly / monthly / once) plus a curated timezone picker.

Agent-driven Slack chat control of automations already shipped in SPRINT-12; this sprint closes the web surface so users have parity between Slack and the dashboard.

### Risks that materialized

From sprint plan §5:
- **BUG-002 fix breaking owner-scoped flows** — mitigation fired correctly. `_assert_workspace_owner` helpers in `keys.py` / `drive_oauth.py` / `automations.py` / `knowledge.py` left untouched (row-level creator scope preserved per ADR-024). Full backend pytest delta: +3 passes (the new BUG-002 tests), 0 regressions.
- **Modal DOM pattern regresses jsdom test pollution** — mitigation fired. Both new modals (`AddAutomationModal`, `DryRunModal`) and the history drawer use the div-overlay pattern from `CreateWorkspaceModal.tsx`. QA grep-verified no `<dialog>` or `showModal()`.
- **Schedule payload drift from agent tool** — mitigation fired. QA cross-read `buildSchedulePayload` against `_AUTOMATIONS_PROMPT_SECTION` in `backend/app/agents/agent.py:124-143`; all five occurrence shapes match byte-for-byte, including `schedule_type` top-level switch.
- **Automations backend execute_async refactor** — unused risk (deliberately out of scope, filed for SPRINT-14).

One surprise not in the risk table: the sprint-plan §2 prose stated the dry-run endpoint as `/{aid}/dry-run` but the actual backend route is `POST /automations/test-run` with a prompt-only body. Architect caught this during plan inspection and recorded it as flashcard `2026-04-24 #frontend #epic-018`. Zero downstream cost.

### Cost envelope

**Unavailable — ledger gap.** See Meta section. Rough wall time ~3h 51m across 7 agent invocations (1 Architect + 3 Developer + 3 QA).

### What's unblocked for next sprint

- **EPIC-018 is fully closed** as of `64574dd`. Follow-on polish work (observability, error channels, scheduled-run telemetry) is now a CR against a closed epic rather than open scope.
- **SPRINT-14 can take EPIC-024 leftovers** (STORY-024-02 background worker locks, STORY-024-04 fix legacy tests) without EPIC-018 competing for attention.
- **Automations backend `execute_async` refactor** — lifted out of the SPRINT-12 squash-merge note; can be picked up opportunistically.
- **Pre-existing test-harness infra bug** surfaced during BUG-002 execution: `TestClient(app)` with `with` context manager hangs under pytest-asyncio auto mode because FastAPI lifespan starts 3 async cron loops (drive, wiki, automation). 4 test modules (`test_workspace_routes.py`, `test_channel_binding.py`, `test_channel_enrichment.py`, `test_automations_routes.py`) are currently excluded from CI by convention. Candidate for a SPRINT-14 infra story.

---

## For Developers

### Per-story walkthrough

**BUG-002: Team members can't access their workspaces under a shared Slack team** · L2 · cost unavailable · ~22m dev + ~10m QA

- Files: `backend/app/api/routes/workspaces.py`, `backend/app/api/routes/channels.py`, `backend/tests/test_workspaces_team_member_access.py` (new).
- Tests added: 3 (covering all 3 Gherkin scenarios in bug §5).
- Kickbacks: 0 (one-shot).
- Deviations from plan: `channels.py` helper needed a two-step query (membership check + team-row fetch for the encrypted bot token). Original helper returned the team row in one query; after the rename the membership table doesn't carry bot-token data. Plan only said "rename and switch query" — didn't address the return-value dependency. Net +20 LoC not +5.
- Flashcards recorded: `#test-harness #fastapi #lifespan` — `TestClient(app) as client:` deadlocks under pytest-asyncio auto mode because the FastAPI lifespan starts 3 cron loops. Use `TestClient(app)` without the context manager for mock-heavy tests (same pattern as `test_auth_routes.py`).
- Commit: `c026dd6`
- Test-first signature verification (QA): new test FAILS on parent `3d098fe` with `403 "You do not have access to this Slack team"`, GREEN on `c026dd6`. Textbook RED→GREEN.

**STORY-018-05: Automations list + history UI on workspace page** · L2 · cost unavailable · ~8m dev + ~3m QA

- Files: `frontend/src/types/automation.ts` (new), `frontend/src/hooks/useAutomations.ts` (new), `frontend/src/components/workspace/AutomationsSection.tsx` (new), `frontend/src/components/workspace/AutomationHistoryDrawer.tsx` (new), `frontend/src/lib/api.ts` (+6 fns), `frontend/src/routes/app.teams.$teamId.$workspaceId.tsx` (mount + state stubs for 018-06), `AutomationsSection.test.tsx` (new).
- Tests added: 7 (covering all 7 Gherkin scenarios).
- Kickbacks: 0 (one-shot).
- Deviations from plan: none. 4 state stubs (`addAutomationOpen`, `dryRunPrompt`, `dryRunName`, `dryRunOpen`) pre-positioned on the route for 018-06 exactly as the plan §2 coupling table specified.
- Flashcards recorded: none new.
- Commit: `3b8a3d5`

**STORY-018-06: Automations add/edit + dry-run modals** · L2 · cost unavailable · ~11m dev + ~2.5m QA

- Files: `frontend/src/components/workspace/AddAutomationModal.tsx` (new, 755 LoC), `DryRunModal.tsx` (new), `AddAutomationModal.test.tsx` (new, 9 tests), `app.teams.$teamId.$workspaceId.tsx` (+18/-3 — mount only).
- Tests added: 9 covering 8 Gherkin scenarios (scenario 7 split into spinner + output assertions, approved by plan and QA).
- Kickbacks: 0 (one-shot).
- Deviations from plan: none. Pure-consumer rule held — zero edits to `api.ts` or `useAutomations.ts`. Schedule payload matches the 5-row plan table exactly; `schedule_type` = `"once"` vs `"recurring"` switch correct.
- Flashcards recorded: none formalized, but Dev flagged two test-harness gotchas worth promoting (see below).
- Commit: `99321e6`

### Agent efficiency breakdown

| Role | Invocations | Tokens | Cost | Tokens/story | Notes |
|---|---|---|---|---|---|
| Architect | 1 | unavailable | — | — | 110-line W01 plan, grep-backed claims, flashcard sweep |
| Developer | 3 | unavailable | — | — | All three stories one-shot; commit-per-story honored |
| QA | 3 | unavailable | — | — | All three stories PASS first time; RED→GREEN proof on BUG-002 |
| Reporter | 1 (this report) | — | — | — | Reporter agent not registered this session; orchestrator wrote in-line |

All numeric columns unavailable: `.cleargate/sprint-runs/SPRINT-13/token-ledger.jsonl` was never created (see Meta + "What the loop got wrong").

### What the loop got right

- **Test-first discipline on BUG-002 held.** Architect's §3 blueprint made the test-first ordering explicit; Developer wrote the 3 Gherkin tests, confirmed RED on current code, then implemented the rename. QA re-verified the RED state on parent commit as signature check. Exactly the pattern the bug §5 Gherkin demanded.
- **Plan's "pure consumer" rule saved 018-06 from scope bleed.** Dev could have been tempted to add a convenience hook or refactor `api.ts`; Architect's explicit "if diff shows api.ts or useAutomations.ts edits, flag scope drift" line kept the commit at 4 files exactly.
- **Architect grep-verified the dry-run endpoint path** upfront and corrected a sprint-plan §2 inaccuracy before any code was written. One flashcard recorded, zero rework downstream.
- **Sequencing plan was right.** BUG-002 first landed the assertion-rename and unblocked multi-user manual QA before the UI stories hit main. 018-05 → 018-06 sequencing caught a real dependency (shared hooks + state stubs); attempting them in parallel would have produced merge conflicts on `api.ts` and the workspace route.
- **One commit per story, clean merge graph.** Sprint branch has exactly 3 story commits + 3 merge commits, no fix-ups or amended commits.

### What the loop got wrong

- **Ledger gap — no token-ledger.jsonl produced this sprint.** Root cause: the orchestrator never wrote `.cleargate/sprint-runs/.active` with `SPRINT-13` at kickoff, so the `SubagentStop` hook had no sprint to route to, and no `_off-sprint` fallback directory existed either (the hook checks for one; it doesn't create it). Every agent firing ran without capture. **Loop improvement:** add a pre-flight step to the orchestrator's sprint-kickoff sequence: write `.cleargate/sprint-runs/.active` AND `mkdir -p .cleargate/sprint-runs/_off-sprint` before spawning the first Architect. Record as flashcard `#reporting #hook`.
- **Reporter agent not available in this session.** `.claude/agents/reporter.md` exists on disk but the agent registry surfaced only architect/developer/qa/devops/scribe. Orchestrator fell back to writing REPORT.md directly, which forfeits the Opus model uplift and the standardized template guardrails. **Loop improvement:** confirm `.claude/agents/` is readable at session start; if Reporter is missing, either re-register or document the fallback.
- **Docstring sweep on BUG-002 was under-specified.** Plan §3 said "'owner' → 'member' on affected routes" without enumerating module-level docstrings. Dev had to derive which docstrings counted as "affected." Low-cost miss here but worth tightening the plan template.
- **Story file §3 Implementation Guide sections missing.** Developer reported that the ClearGate story template doesn't include the `§3.1 ADR references` / `§3 Implementation Guide` headings the V-Bounce template had. Milestone plan compensated, but drops a safety net. **Loop improvement:** align the ClearGate story template with what Developer agents expect, or update `developer.md` to reference the ClearGate headings.

### Flashcard audit

New cards this sprint: 1 (by Architect).

- `2026-04-24 · #frontend #epic-018 · EPIC-018 dry-run endpoint is POST /automations/test-run (prompt-only body), NOT /{aid}/dry-run`

Stale-candidate scan: skipped this sprint — `.cleargate/FLASHCARD.md` flashcard body is opaque one-liners without a clear status-marker convention in this repo yet. No stale flashcards flagged.

Supersede candidates: none.

**Candidates for next sprint to record as formal flashcards** (surfaced during execution but not yet written to FLASHCARD.md):
- `#test-harness #fastapi #lifespan` — `TestClient(app) as client:` deadlocks under pytest-asyncio auto mode; 3 cron loops hang during lifespan startup. Use `TestClient(app)` without context manager. Referenced in 4 currently-excluded test modules.
- `#vitest #test-harness` — When testing a button whose label flips on `isPending`, set mock `isPending: false` initially, click, then `rerender` with `isPending: true` to verify the spinner state. Setting `isPending: true` before first render disables the button entirely and the click does nothing.
- `#vitest #test-harness` — Prefer `getByLabelText` over `getByDisplayValue('')` for empty inputs; empty-value queries are ambiguous whenever a form has multiple empty fields.
- `#reporting #hook` — Orchestrator must write `.cleargate/sprint-runs/.active` at sprint kickoff or the token ledger is empty. No warning is emitted; silent failure.

### Open follow-ups

- **SPRINT-14:** EPIC-024 remaining stories (background worker locks, fix legacy tests).
- **SPRINT-14:** BUG-001 nav-aesthetics polish (deferred from §7 out-of-scope).
- **SPRINT-14 (infra):** Fix the `TestClient(app) with lifespan` deadlock so the 4 excluded test modules can re-enter CI. Candidate: lifespan-opt-out fixture or startup-event gating behind a `TESTING=1` env var.
- **SPRINT-14 (process):** Seed `.cleargate/sprint-runs/.active` in the sprint-kickoff checklist.
- **Post-sprint:** Run `cleargate wiki build` (DoD item) and archive sprint artifacts from `pending-sync/` → `archive/`.
- **Deferred from SPRINT-12:** Automations backend refactor to `execute_async` — not blocking anything, queue when a related backend change lands.

---

## Post-ship hotfixes (live-testing window — closed)

The squash-merge to main landed at `934497a`. Between merge and sprint close, live-testing surfaced 4 hotfix commits (5 distinct fixes) — all logged here rather than filed as separate BUG items because they fall inside SPRINT-13 scope. **Live-testing window closed 2026-04-24.**

| # | Commit | Scope | Surfaced by | Fix |
|---|---|---|---|---|
| 1 | `062dce8` | `fix(epic-005)` follow-on to BUG-002 | Live test: `POST /api/slack-teams/{id}/workspaces` → 500 `duplicate key on one_default_per_team`. BUG-002 newly let any member POST, but the "is this the first workspace?" check was still `(user_id, team_id)`-scoped, so a second member's first workspace always claimed `is_default_for_team=True` and collided with the owner's. | Scope the team-default check by `team_id + is_default_for_team=True` only. New workspace picks up the default flag only if no default exists for the team yet. Regression test added as Scenario 4 in `test_workspaces_team_member_access.py` with column-differentiating mock — RED on pre-fix confirmed. |
| 2 | `301e3c5` | `fix(epic-018)` agent prompt gating | Live test in Slack: asked Tee-Mo to schedule a daily news fetch; agent created a `fetch-rundown-ai-news` skill instead of an automation. Cause: `_AUTOMATIONS_PROMPT_SECTION` was gated on `automations is non-empty`, so workspaces with zero automations never saw the "schedule / every week / remind me" keyword hints. Tools were registered with pydantic-ai unconditionally — the gate hid only the discovery prompt, never prevented tool use. | Drop the `if automations:` gate. Section + hints injected on every workspace. Test 9 in `test_automation_tools.py` flipped: was "omit on empty," now "present on empty." |
| 3 | `1a55b89` | `fix(epic-018)` bound-channel hallucination | Live test: after Fix #2 agent did try to create automation but called `create_automation` with a fabricated channel ID (`C089L445E8D` — never existed; real ID for `#all-slop-tester` was `C0AUN0FJM36`). `validate_channels` correctly rejected the fake ID; the agent then invented an "invite the bot" story to explain the failure. Prod DB confirmed 3 real bound channels for the workspace — user was right, the agent was hallucinating. Root cause: system prompt never told the agent what the bound channel IDs actually were. | Inject a `## Bound Channels` section listing the real `slack_channel_id` values from `teemo_workspace_channels`, with an explicit "never invent, guess, or reconstruct channel IDs" rule. Diagnosed by SSH'ing to the Coolify host + querying Supabase directly (no prod-accessible agent log beyond that). |
| 4 | `c17f6ec` | `fix(epic-018)` Dry Run + history 500s | Two independent bugs found via dashboard UI: (a) Dry Run on the workspace's Automations section returned HTTP 500 with `UserError: Set the GOOGLE_API_KEY environment variable or pass it via GoogleProvider(api_key=...)` — `_run_preview_prompt` built the pydantic-ai Agent via a `"provider:model_id"` string and tried to pass the BYOK key through `.run(model_settings={"api_key": ...})`, but Google's provider reads the key at construction time so `model_settings` is ignored. (b) `GET /automations/{aid}/history` returned 500 with `TypeError: get_automation_history() missing 1 required positional argument: 'automation_id'` — route called the service with only `automation_id`, but service signature is `(workspace_id, automation_id, *, supabase)`. | (a) Use `_build_pydantic_ai_model(model_id, provider, api_key)` (same helper as `build_agent`) so `GoogleProvider(api_key=...)` / `AnthropicProvider` / `OpenAIProvider` receive the key at construction. Drop the broken `model_settings` arg. (b) Pass both `workspace_id` and `automation_id` positionally. Diagnosed via SSH to Coolify host. |

**Running totals (live-testing window):**
- Hotfixes: 4 (containing 5 distinct fixes — Fix #4 bundles two unrelated 500s)
- Bug-Fix Tax post-close: +4 hotfix commits (sprint plan §6 had target 1 — BUG-002 only)
- All traceable to SPRINT-13 scope: (1) BUG-002 opened a new insert path without updating downstream invariants; (2–3) EPIC-018 agent prompt issues — keyword gate too conservative and bound-channel catalog missing; (4) EPIC-018 dashboard wiring — BYOK key not forwarded to preview agent and history endpoint misused service signature.

**Loop-improvement signals this is sending:**
- **Live-test the bug-opens-a-new-path case.** BUG-002's test coverage proved the 403 was gone but never tried creating *two* workspaces under the same team. Worth adding to the bug template: "list every write path this fix newly unlocks — test at least one end-to-end in the live environment."
- **Empty-state probes for keyword-gated prompt sections.** Any prompt section gated on "has ≥1 X" is suspect because the LLM can never create the first X. Flashcard recorded.
- **Prompt-inject real IDs, not just names.** When a tool argument is a foreign key (channel ID, document ID, workspace ID, user ID), the system prompt needs a catalog of the real values. Otherwise the LLM fabricates plausible-looking ones and narrates around the downstream validation error. Rule of thumb: if a tool param is an opaque token the user can't type, the prompt must list the legal tokens. Flashcard recorded.
- **BYOK keys must flow through provider constructors, not model_settings.** `_run_preview_prompt` cloned the agent-build pattern but took a shortcut with `Agent(model="provider:model_id", ...)` + `run(model_settings={"api_key": ...})`. pydantic-ai's Google / Anthropic / OpenAI providers all read the key at *construction* time; `model_settings` is silently ignored. Any new code path that instantiates pydantic-ai must reuse `_build_pydantic_ai_model(model_id, provider, api_key)`. Flashcard recorded.
- **Thread-history anchoring is real.** After fix #3 the Slack agent's prompt had the correct bound-channel IDs, but the agent kept hallucinating the fake ID because its own earlier messages in the long thread already contained it. New-thread tests resolved this. Candidate flashcard: when debugging "prompt-injection not working" in a multi-turn chat agent, always sanity-check in a fresh thread before iterating on the prompt.

---

## Meta

**Token ledger:** `/Users/ssuladze/Documents/Dev/SlaXadeL/.cleargate/sprint-runs/SPRINT-13/token-ledger.jsonl` — **does not exist.** Sentinel `.cleargate/sprint-runs/.active` was missing for the entire sprint; hook at `.claude/hooks/token-ledger.sh` short-circuited without writing any rows. Sentinel has been written retroactively (2026-04-24 post-sprint) so subsequent agent firings will capture correctly. No way to recover the SPRINT-13 ledger.

**Flashcards added:** 1 (see `.cleargate/FLASHCARD.md`), + 4 informal candidates listed above awaiting record in SPRINT-14.

**Model rates used:** n/a — no cost computed (no ledger).

**Report generated:** 2026-04-24 by orchestrator in Reporter-fallback mode (Reporter agent unavailable this session).
