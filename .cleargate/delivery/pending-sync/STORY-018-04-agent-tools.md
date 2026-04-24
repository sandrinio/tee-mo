---
story_id: "STORY-018-04-agent-tools"
parent_epic_ref: "EPIC-018"
status: "Draft"
ambiguity: "🟢"
context_source: "PROPOSAL-001-teemo-platform.md"
owner: "TBD"
target_date: "TBD"
complexity_label: "L2"
parallel_eligible: false
expected_bounce_exposure: "low"
created_at: "2026-04-15T00:00:00Z"
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

> **Ported from V-Bounce.** Original: `product_plans.vbounce-archive/backlog/EPIC-018_scheduled_automations/STORY-018-04-agent-tools.md`. Carried forward during ClearGate migration 2026-04-24.

# STORY-018-04: Agent Tools + System Prompt Integration

**Complexity: L2** — 4 new tools wired into the existing agent factory, plus a keyword-gated system prompt section. Follows the exact same pattern as existing tools — no new infrastructure needed.

---

## 1. The Spec (The Contract)

### 1.1 User Story
> As a **Workspace Admin in Slack**, I want to **tell the bot to schedule an automation by describing it in natural language**, so that **I can set up recurring posts without ever opening the dashboard**.

### 1.2 Detailed Requirements

#### R1 — 4 agent tools in `backend/app/agents/agent.py`

All tools: async function with `ctx: RunContext[AgentDeps]` as first arg, typed parameters, docstring, returns `str`.

- **`create_automation`**: Calls `automation_service.create_automation`. Returns confirmation string with `next_run_at` and target channels. On `ValueError`, returns error string (does NOT raise).
- **`list_automations`**: Returns formatted Markdown list with name, schedule summary, active/inactive state, next_run_at, channels. Empty → `"No automations configured for this workspace."`.
- **`update_automation`**: Builds patch dict from non-None args. Returns confirmation or error string.
- **`delete_automation`**: Returns `"Automation deleted. Execution history has been removed."` if True, `"Automation not found."` if False.

#### R2 — `## Scheduled Automations` system prompt section (keyword-gated)

In `_build_system_prompt()`, add `automations: list[dict] | None = None` parameter. Inject the section **only when `automations` is a non-empty list**.

Section content describes the 4 tools, when to use them (keywords: "schedule", "every week", "automatically post", etc.), the channel rule (ALWAYS require explicit channel), and the schedule shape dict.

#### R3 — `build_agent()` query for automations

After existing skills/documents/wiki_pages queries, add a query for `teemo_automations` where `workspace_id=workspace_id` and `is_active=True`. Pass `automations=automations` into `_build_system_prompt(...)`.

#### R4 — Wire tools into the Agent constructor

Add the 4 new tools to the existing `tools=[...]` list.

### 1.3 Out of Scope
- Agent tool for dry-run (`test_automation`) — UI-only affordance.
- Fetching automation_id by name from the agent.
- Pagination of `list_automations` output.

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

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations

| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Unit tests | 9 | One per Gherkin scenario |

### 4.2 Definition of Done (The Gate)
- [ ] TDD enforced.
- [ ] All Gherkin scenarios covered.
- [ ] No ADR violations.
- [ ] Lazy import pattern used for `automation_service`.

---

## Token Usage

| Agent | Input | Output | Total |
|-------|-------|--------|-------|
