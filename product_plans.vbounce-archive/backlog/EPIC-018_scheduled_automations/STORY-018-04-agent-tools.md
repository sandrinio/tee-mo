---
story_id: "STORY-018-04-agent-tools"
parent_epic_ref: "EPIC-018"
status: "Draft"
ambiguity: "🟢 Low"
context_source: "EPIC-018 §2, §3.3, §7; backend/app/agents/agent.py (tool registration + system prompt assembly pattern); backend/app/services/automation_service.py (STORY-018-01); new_app orchestrator.py (agent tool reference)"
actor: "Workspace Admin (Slack)"
complexity_label: "L2"
---

# STORY-018-04: Agent Tools + System Prompt Integration

**Complexity: L2** — 4 new tools wired into the existing agent factory, plus a keyword-gated system prompt section. Follows the exact same pattern as existing tools (read_document, search_wiki, etc.) — no new infrastructure needed.

---

## 1. The Spec (The Contract)

### 1.1 User Story
> As a **Workspace Admin in Slack**, I want to **tell the bot to schedule an automation by describing it in natural language**, so that **I can set up recurring posts without ever opening the dashboard**.

### 1.2 Detailed Requirements

#### R1 — 4 agent tools in `backend/app/agents/agent.py`

All tools follow the existing tool pattern: async function with `ctx: RunContext[AgentDeps]` as first arg, typed parameters, docstring, returns `str`.

---

**Tool 1: `create_automation`**

```python
async def create_automation(
    ctx: RunContext[AgentDeps],
    name: str,
    prompt: str,
    schedule: dict,
    slack_channel_ids: list[str],
    timezone: str = "UTC",
    description: str | None = None,
) -> str:
```

- Calls `automation_service.create_automation(workspace_id=..., owner_user_id=ctx.deps.user_id, payload={"name": name, "prompt": prompt, "schedule": schedule, "slack_channel_ids": slack_channel_ids, "timezone": timezone, "description": description}, supabase=ctx.deps.supabase)`.
- On success: return a confirmation string including `next_run_at` and target channels. Example: `"Automation 'Daily Standup' created. Next run: 2026-04-16 09:00 UTC. Posts to: #general, #updates."`.
- On `ValueError` (validation error from service): return the error message as a string (do not raise — let the agent surface it conversationally).
- On any other exception: return `"Failed to create automation: {error}"`.

Docstring must document the `schedule` dict shape with examples (daily, weekdays, weekly, monthly, once).

---

**Tool 2: `list_automations`**

```python
async def list_automations(ctx: RunContext[AgentDeps]) -> str:
```

- Calls `automation_service.list_automations(workspace_id=ctx.deps.workspace_id, supabase=ctx.deps.supabase)`.
- On empty list: return `"No automations configured for this workspace."`.
- On non-empty: return formatted Markdown list. Each item: name, schedule summary (use a Python port of `getScheduleSummary` — see §3.2), active/inactive state, next_run_at (or "—" if inactive/None), target channels.

Example output:
```
**Automations (2 total)**

1. **Daily Standup** (Active) — every weekday at 09:00 UTC
   Next run: 2026-04-16 09:00 UTC | Channels: #general
   
2. **Weekly Report** (Paused) — every Monday at 17:00 Europe/Tbilisi
   Next run: — | Channels: #general, #updates
```

---

**Tool 3: `update_automation`**

```python
async def update_automation(
    ctx: RunContext[AgentDeps],
    automation_id: str,
    name: str | None = None,
    prompt: str | None = None,
    schedule: dict | None = None,
    slack_channel_ids: list[str] | None = None,
    timezone: str | None = None,
    is_active: bool | None = None,
    description: str | None = None,
) -> str:
```

- Builds patch dict from non-None args.
- Calls `automation_service.update_automation(workspace_id=ctx.deps.workspace_id, automation_id=automation_id, patch=patch, supabase=ctx.deps.supabase)`.
- Returns confirmation with updated field names, or error string on failure / not-found.

---

**Tool 4: `delete_automation`**

```python
async def delete_automation(
    ctx: RunContext[AgentDeps],
    automation_id: str,
) -> str:
```

- Calls `automation_service.delete_automation(workspace_id=ctx.deps.workspace_id, automation_id=automation_id, supabase=ctx.deps.supabase)`.
- Returns `"Automation deleted. Execution history has been removed."` if `True`, `"Automation not found."` if `False`.

---

#### R2 — `## Scheduled Automations` system prompt section (keyword-gated)

In `_build_system_prompt()`, add an `automations: list[dict] | None = None` parameter.

Inject the section **only when `automations` is a non-empty list** (workspace has ≥1 automation):

```python
if automations:
    prompt += "\n\n## Scheduled Automations\n" + _AUTOMATIONS_PROMPT_SECTION
```

Where `_AUTOMATIONS_PROMPT_SECTION` is a module-level constant string:

```
Use these tools to manage scheduled automations for this workspace:
- `create_automation(name, prompt, schedule, slack_channel_ids, timezone?)`: Schedule a prompt to run automatically and post results to one or more bound Slack channels.
- `list_automations()`: List all automations — name, schedule, next run, active state.
- `update_automation(automation_id, **patch)`: Update any field of an existing automation (name, prompt, schedule, channels, is_active).
- `delete_automation(automation_id)`: Permanently delete an automation and its execution history.

**When to use**: when the user says "schedule", "every week", "automatically post", "set up a recurring task", "remind me", "automate", or asks about existing automations.

**Channel rule**: ALWAYS require the user to name at least one bound channel. Do NOT assume a default. If the user hasn't specified a channel, ask which of the workspace's bound channels to post to before calling create_automation.

**Schedule shape** (pass as a dict):
- Daily:    {"occurrence": "daily",    "when": "09:00"}
- Weekdays: {"occurrence": "weekdays", "when": "09:00"}
- Weekly:   {"occurrence": "weekly",   "when": "09:00", "days": [1, 3]}   # 0=Sun … 6=Sat
- Monthly:  {"occurrence": "monthly",  "when": "09:00", "day_of_month": 1}
- Once:     {"occurrence": "once",     "at": "2026-04-20T17:00:00"}       # ISO 8601, must be future
```

#### R3 — `build_agent()` query for automations

Inside `build_agent()`, after the existing skills/documents/wiki_pages queries, add:

```python
# Query automations for system prompt gating
automations_result = (
    supabase.table("teemo_automations")
    .select("id, name, schedule, timezone, is_active, next_run_at, slack_channel_ids")
    .eq("workspace_id", workspace_id)
    .eq("is_active", True)
    .execute()
)
automations: list[dict] = automations_result.data or []
```

Pass `automations=automations` into `_build_system_prompt(...)`.

#### R4 — Wire tools into the Agent constructor

Add the 4 new tools to the existing `tools=[...]` list at the `Agent(...)` call:

```python
tools=[
    ..., search_wiki, read_wiki_page, lint_wiki,
    create_automation, list_automations, update_automation, delete_automation,
]
```

### 1.3 Out of Scope
- Agent tool for dry-run (`test_automation`) — UI-only affordance (STORY-018-02).
- Fetching automation_id by name from the agent — agent must ask the user for the ID or use `list_automations` first.
- Pagination of `list_automations` output — 50-row cap enforced by service; output is the full list.

### TDD Red Phase: Yes

---

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria

```gherkin
Feature: Automation Agent Tools

  Scenario: Create automation via agent tool — success
    Given workspace W with a bound channel C1 (slack_channel_id="C123")
    When the agent calls create_automation(name="Daily Standup", prompt="Post standup", schedule={"occurrence": "daily", "when": "09:00"}, slack_channel_ids=["C123"])
    Then automation_service.create_automation is called with correct payload
    And the tool returns a string containing "Daily Standup" and the next_run_at time

  Scenario: Create automation — unbound channel rejected
    Given channel "C999" is NOT bound to workspace W
    When the agent calls create_automation(..., slack_channel_ids=["C999"])
    Then automation_service.create_automation raises ValueError
    And the tool returns an error string (does NOT raise)

  Scenario: List automations — non-empty workspace
    Given workspace W has 2 automations (one active, one inactive)
    When the agent calls list_automations()
    Then automation_service.list_automations is called
    And the tool returns a Markdown string listing both automations with schedule summaries

  Scenario: List automations — empty workspace
    Given workspace W has no automations
    When the agent calls list_automations()
    Then the tool returns "No automations configured for this workspace."

  Scenario: Update automation — toggle is_active
    Given automation A exists in workspace W
    When the agent calls update_automation(automation_id=A.id, is_active=False)
    Then automation_service.update_automation is called with patch={"is_active": False}
    And the tool returns a confirmation string

  Scenario: Delete automation — found
    Given automation A exists in workspace W
    When the agent calls delete_automation(automation_id=A.id)
    Then automation_service.delete_automation returns True
    And the tool returns a string containing "deleted"

  Scenario: Delete automation — not found
    Given no automation with that ID in workspace W
    When the agent calls delete_automation(automation_id="nonexistent")
    Then the tool returns "Automation not found."

  Scenario: System prompt includes automations section when automations exist
    Given workspace W has 1 active automation
    When build_agent(workspace_id=W.id, ...) is called
    Then the system prompt contains "## Scheduled Automations"
    And contains "create_automation"

  Scenario: System prompt omits automations section when no automations
    Given workspace W has 0 automations
    When build_agent(workspace_id=W.id, ...) is called
    Then the system prompt does NOT contain "## Scheduled Automations"
```

### 2.2 Test File
`backend/tests/test_automation_tools.py`

Mock `automation_service` at module level via `unittest.mock.patch`. Test each tool function directly (instantiate `AgentDeps`, call the function with a mock `RunContext`). Do not spin up a real agent.

---

## 3. Implementation Guide

### 3.1 File Map

| File | Action | Notes |
|------|--------|-------|
| `backend/app/agents/agent.py` | **Modify** | Add 4 tools + `_AUTOMATIONS_PROMPT_SECTION` constant + `automations` param to `_build_system_prompt` + query in `build_agent` |
| `backend/tests/test_automation_tools.py` | **Create** | Unit tests for all 4 tools + system prompt injection |

### 3.2 Python schedule summary helper

Implement `_schedule_summary(schedule: dict, timezone: str) -> str` as a module-level private function (or inside the tool module). Keeps formatting consistent between list_automations and UI.

```python
def _schedule_summary(schedule: dict, timezone: str) -> str:
    occ = schedule.get("occurrence", "")
    when = schedule.get("when", "")
    tz_label = timezone if timezone != "UTC" else "UTC"
    
    match occ:
        case "daily":    return f"every day at {when} {tz_label}"
        case "weekdays": return f"every weekday at {when} {tz_label}"
        case "weekly":
            day_names = ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"]
            days = ", ".join(day_names[d] for d in schedule.get("days", []))
            return f"every {days} at {when} {tz_label}"
        case "monthly":  return f"monthly on day {schedule.get('day_of_month')} at {when} {tz_label}"
        case "once":     return f"once at {schedule.get('at')} {tz_label}"
        case _:          return occ
```

### 3.3 Tool placement in agent.py

Insert the 4 automation tool functions after the existing `lint_wiki` tool block (around line 960+), before the final `build_agent()` function. Follow the existing numbered comment convention:

```python
# --- 11.70. Automation tools (EPIC-018 Phase C) ---
async def create_automation(...):
    ...
async def list_automations(...):
    ...
async def update_automation(...):
    ...
async def delete_automation(...):
    ...
```

### 3.4 Lazy import of automation_service

Import `automation_service` lazily inside each tool function (same pattern as `wiki_service` imports inside tool functions) to avoid circular import risk:

```python
async def list_automations(ctx: RunContext[AgentDeps]) -> str:
    from app.services import automation_service as _auto_service
    ...
```

---

## Change Log

| Date | Author | Change |
|------|--------|--------|
| 2026-04-15 | Claude (doc-manager) | Initial draft. 4 tools (create/list/update/delete), system prompt keyword-gated by automation existence, lazy service import pattern. Dry-run intentionally excluded (UI-only per EPIC-018 §8). |

---

## Token Usage

| Agent | Input | Output | Total |
|-------|-------|--------|-------|
| Developer | 77 | 1,212 | 1,289 |
