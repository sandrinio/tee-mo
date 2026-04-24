---
story_id: "STORY-018-08-agent-scheduler-tz"
parent_epic_ref: "EPIC-018"
status: "Draft"
ambiguity: "🟢"
context_source: "EPIC-018-scheduled-automations.md"
actor: "Slack user scheduling via chat"
complexity_label: "L2"
created_at: "2026-04-24T00:00:00Z"
updated_at: "2026-04-24T00:00:00Z"
created_at_version: "cleargate-post-sprint-13"
updated_at_version: "cleargate-post-sprint-13"
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

# STORY-018-08: Agent knows the scheduler's timezone (Slack chat path)
**Complexity:** L2 — thread `sender_tz` through `slack_dispatch → AgentDeps → system prompt + create_automation` and add one prompt rule. Known pattern, ~2-4hr.

## 1. The Spec (The Contract)

### 1.1 User Story
As a **Slack user who asks the bot to schedule something** (e.g. "remind me every weekday at 9am"), I want the automation to be saved in **my** timezone — the one Slack has on my profile — so that "9am" means 09:00 in my zone, not 09:00 UTC. When my timezone can't be determined, I want the bot to **say** which zone it used so I can correct it in one turn.

### 1.2 Detailed Requirements
- **R1.** `slack_dispatch._handle_chat_or_mention` reads `user.tz` from the existing `users_info(user=sender_user_id)` response and passes it to `build_agent` (and downstream into `AgentDeps`). No extra Slack API call.
- **R2.** `AgentDeps` gains a `sender_tz: str` field (default `"UTC"`). Existing test fixtures that construct `AgentDeps` directly keep working — `sender_tz` has a default, and any code path that reads `ctx.deps.sender_tz` uses `getattr(..., "sender_tz", "UTC")` to tolerate older fakes (precedent: `_add_citation` on `citations`).
- **R3.** `_build_system_prompt` accepts `sender_tz` and appends, immediately after the existing UTC `current_time_line`:
  > `User's timezone: <tz>. Current local time for the user: <HH:MM on YYYY-MM-DD>. When the user references "9am", "tomorrow", "this evening", etc., interpret in this zone by default.`
  When `sender_tz == "UTC"`, emit a softer variant: `User's timezone could not be determined; default to UTC and state this when confirming any scheduled time.`
- **R4.** Add a standing rule to the preamble (applies on every run, not just the automations section):
  > "Whenever you schedule, confirm, or reason about a specific time, state the timezone you used (e.g. 'Scheduled for 09:00 America/Los_Angeles'). Never leave the timezone implicit."
- **R5.** `create_automation` tool (`agent.py:619`): change the default `timezone="UTC"` argument to pull from `ctx.deps.sender_tz`. The agent may still override by passing an explicit value (e.g. user says "9am New York time"). When the tool records the tz, it returns the final tz in the tool result so the agent can cite it.
- **R6.** `update_automation` tool does **not** auto-rewrite tz on unrelated patches — only changes tz when the agent explicitly passes one (behavior unchanged).
- **R7.** If `users_info` fails or `user.tz` is missing/empty, `sender_tz` is `"UTC"` and R3's softer variant is rendered. No 500, no retry storm.

### 1.3 Out of Scope
- Dashboard modal tz detection — see STORY-018-07.
- Workspace-level default tz setting for automations created by the web UI (owner_user_id's stored tz). Can revisit if needed.
- Auto-migrating existing automations (rows created with `timezone="UTC"` stay as-is).
- Adding `users:read` scope — already present (name resolution uses it).
- Surfacing tz in the Slack formatted confirmation card — the prompt rule makes it part of the agent's text reply; Block Kit tweaks can wait.

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria (Gherkin)

```gherkin
Feature: Scheduler-aware timezone in Slack chat automation flow

  Scenario: Slack user with a known tz schedules a daily automation
    Given a Slack user whose profile tz is "America/Los_Angeles"
    And the user messages the bot "remind me every day at 9am to stand up"
    When the agent calls create_automation without an explicit timezone
    Then the new automation row has timezone = "America/Los_Angeles"
    And the agent's reply text contains "America/Los_Angeles"

  Scenario: Slack user explicitly overrides timezone in the prompt
    Given a Slack user whose profile tz is "America/Los_Angeles"
    And the user says "schedule a 5pm New York standup summary every weekday"
    When the agent calls create_automation with timezone="America/New_York"
    Then the new automation row has timezone = "America/New_York"
    And the agent's reply text contains "America/New_York"

  Scenario: users.info fails for the sender
    Given users_info(user=<sender>) raises
    When the user asks the bot to schedule something
    Then the agent treats sender_tz as "UTC"
    And the system prompt tells the agent its tz is unknown
    And the agent's reply contains "UTC" and explicitly notes the timezone assumption

  Scenario: users.info returns a user object with no tz field
    Given users_info(user=<sender>) returns a user object without "tz"
    When the user asks the bot to schedule something
    Then sender_tz is "UTC"
    And the agent's reply states the timezone assumption

  Scenario: System prompt always declares time context
    Given any chat message routed to the agent (scheduling or not)
    When _build_system_prompt runs with a non-UTC sender_tz
    Then the prompt contains both the UTC anchor line and a "User's timezone: <tz>" line
    And the prompt contains the standing rule about stating timezone in replies
```

### 2.2 Verification Steps (Manual)
- [ ] In a local Slack workspace, send the bot "remind me every day at 9am to standup" — verify the created automation row (via dashboard or DB) has your Slack profile's tz.
- [ ] Temporarily have `users_info` raise (patch in a test build) — bot replies and explicitly says UTC.
- [ ] Ask the bot "schedule a 5pm New York daily digest" — row timezone is `America/New_York` regardless of your profile zone.

## 3. The Implementation Guide

### 3.1 Context & Files

| Item | Value |
|---|---|
| Primary File | `backend/app/agents/agent.py` (AgentDeps, _build_system_prompt, create_automation tool) |
| Related Files | `backend/app/services/slack_dispatch.py:~338` (pluck tz from users_info, pass to build_agent), `backend/tests/test_automation_tools.py`, `backend/tests/test_slack_dispatch.py` (or equivalent), `backend/app/services/automation_service.py` (no change expected — just consume tz as-is) |
| New Files Needed | No |

### 3.2 Technical Logic
- **slack_dispatch.py**: extend the existing `users_info` block (~line 338):
  ```python
  sender_tz = (user_data.get("tz") or "").strip() or "UTC"
  ```
  Pass `sender_tz` through to `build_agent(...)` (add kwarg) which stores it on `AgentDeps`.
- **agent.py `AgentDeps`**: add `sender_tz: str = "UTC"` (with default so existing construct-sites keep compiling).
- **agent.py `_build_system_prompt(sender_tz: str = "UTC", ...)`**:
  - Keep the existing UTC `current_time_line`.
  - Compute `now_local = datetime.now(ZoneInfo(sender_tz))` when `sender_tz != "UTC"`. Append the user-tz line (R3).
  - When tz is UTC, append the "timezone unknown, default UTC, state it" variant.
  - Append the standing rule (R4) into the Rules block (next to "Be concise and helpful").
- **agent.py `create_automation` tool**: replace `timezone: str = "UTC"` with reading `ctx.deps.sender_tz` when the caller omits it. Keep the param in the signature so explicit overrides still work.
- **Tests**: extend `test_automation_tools.py` with a fixture that sets `AgentDeps.sender_tz` and asserts the row tz matches (happy path + override path). Extend slack_dispatch tests for the users_info → sender_tz extraction and the failure path.

### 3.3 API Contract
No REST contract change. Tool signatures are agent-internal — pydantic-ai schema of `create_automation` still exposes `timezone?: str` to the model; only the default source changes.

## 4. Quality Gates

### 4.1 Minimum Test Expectations

| Test Type | Minimum Count | Notes |
|---|---|---|
| Unit tests | 4 | (a) `AgentDeps.sender_tz` default, (b) prompt includes user-tz line when set, (c) `create_automation` uses `sender_tz` when caller omits tz, (d) `create_automation` honors explicit override |
| Integration tests | 2 | (a) `slack_dispatch` extracts tz from users_info and wires to AgentDeps, (b) `users_info` failure → `sender_tz = "UTC"` + prompt softer variant |

### 4.2 Definition of Done (The Gate)
- [ ] Minimum test expectations (§4.1) met.
- [ ] All Gherkin scenarios from §2.1 covered.
- [ ] No regression in existing `test_automation_tools.py` / `test_slack_dispatch.py`.
- [ ] Lint + typecheck + test suite pass.
- [ ] Peer / Architect review passed.

---

## ClearGate Ambiguity Gate
**Current Status: 🟢 Low Ambiguity** — surface of change is concrete; Slack already returns `user.tz`; `AgentDeps` extension pattern has a precedent (`citations` field).
