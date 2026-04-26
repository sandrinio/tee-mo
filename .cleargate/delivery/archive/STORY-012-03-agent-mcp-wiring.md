---
story_id: "STORY-012-03-agent-mcp-wiring"
parent_epic_ref: "EPIC-012"
status: "Shipped"
ambiguity: "🟢 Low"
context_source: "PROPOSAL-001-teemo-platform.md"
actor: "Backend Engineer"
complexity_label: "L2"
created_at: "2026-04-26T00:00:00Z"
updated_at: "2026-04-26T00:00:00Z"
created_at_version: "cleargate-sprint-17-draft"
updated_at_version: "cleargate-sprint-17-draft"
server_pushed_at_version: null
draft_tokens: { input: null, output: null, cache_read: null, cache_creation: null, model: null, sessions: [] }
cached_gate_result: { pass: null, failing_criteria: [], last_gate_check: null }
---

# STORY-012-03: Agent MCP Wiring
**Complexity:** L2 — `AgentDeps` extension + MCP-server load + 3 agent tools + AsyncExitStack lifecycle in dispatch.

## 1. The Spec (The Contract)

### 1.1 User Story
As a Slack user, I want the agent to automatically gain MCP-server tools the moment my admin connects one, and to let me manage MCP connections via Slack chat ("@tee-mo connect to Azure DevOps MCP at https://… with token …"), so that I get GitHub/Linear/Azure-DevOps tooling without leaving Slack.

### 1.2 Detailed Requirements
1. **`AgentDeps` extension** (`backend/app/agents/agent.py`): add `mcp_servers: list[MCPServer] = field(default_factory=list)`. Pydantic AI's documented DI pattern. **`build_agent` return signature stays 2-tuple** (Q6).
2. **`build_agent` body**: between the existing key resolution and `Agent(...)` construction, fetch active MCP rows via `mcp_service.list_mcp_servers(workspace_id, active_only=True)`. For each row, instantiate the right Pydantic AI class via `mcp_service._build_mcp_client(record)` (the dispatcher from 012-01). Populate `deps.mcp_servers`. Pass `mcp_servers=deps.mcp_servers` to `Agent(...)` constructor.
3. **System prompt addition**: append `## Connected Integrations\n` followed by one bullet per active server: `- {name}` (one line each). Empty if none — the heading is omitted entirely so we don't pollute the prompt for the 99% of workspaces that have no MCP servers. No tool enumeration in the prompt; Pydantic AI registers tools itself.
4. **3 new agent tools** (`@agent.tool` declarations in the same region as the existing `add_skill` / `remove_skill` / `list_skills` tools). The Slack-chat surface intentionally exposes the **80% case only** (single Bearer-style auth header). Servers needing multiple custom headers (`X-API-Key`, `X-Workspace-ID`, etc.) are a dashboard-only path — the chat tool surfaces a hint pointing the user there.
   - `add_mcp_server(ctx, name: str, url: str, transport: str = "streamable_http", auth_header: str | None = None) -> str` — calls `mcp_service.create_mcp_server`. Headers dict passed to service: `{"Authorization": f"Bearer {auth_header}"}` if `auth_header` provided, else `{}`. On success returns `f"Connected '{name}' ({transport}) — tools available on your next message.\n\n⚠️ Your auth token is encrypted server-side, but the message you sent is still in this thread — consider deleting it.\n\nIf this server needs additional headers (e.g. X-API-Key), open the workspace dashboard → Integrations to edit."` **The returned string MUST NOT contain `auth_header`'s value** (Q10).
   - `remove_mcp_server(ctx, name: str) -> str` — calls `mcp_service.delete_mcp_server`. Returns `f"Disconnected '{name}'."` or `f"No MCP server '{name}' is connected."` if not found.
   - `list_mcp_servers(ctx) -> str` — returns `f"Connected: {', '.join(name + ' (' + transport + ', ' + ('active' if is_active else 'disabled') + ')' for ...)}"` or `"No MCP servers connected."` if none.
5. **Slack dispatch lifecycle** (`backend/app/services/slack_dispatch.py`): wrap the existing `agent.run(...)` call in:

   ```python
   async with AsyncExitStack() as stack:
       for server in deps.mcp_servers:
           await stack.enter_async_context(server)
       result = await agent.run(prompt, deps=deps, ...)
   ```

   `AsyncExitStack.__aexit__` runs every server's `__aexit__` even if `agent.run` raises — this is the load-bearing exception-safety guarantee (Q4 risk row).
6. **Zero-MCP regression safety**: when `deps.mcp_servers == []` (the case for every existing workspace today), the `AsyncExitStack` is empty and `agent.run` runs exactly as before. No latency cost, no behaviour change.

### 1.3 Out of Scope
- REST endpoints (012-02).
- Frontend (012-04).
- Service-layer logic (012-01).
- Health monitoring / auto-reconnect (epic §2 OUT-OF-SCOPE).
- Token redaction in already-stored Slack message history (the warn-message instructs the user to delete; we do not delete on their behalf).

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria (Gherkin)

```gherkin
Feature: Agent MCP Wiring

  Scenario: build_agent populates AgentDeps.mcp_servers from active rows
    Given workspace W has 2 active MCP servers (1 SSE, 1 streamable_http) and 1 inactive
    When build_agent(workspace_id=W, ...) returns (agent, deps)
    Then deps.mcp_servers has 2 entries
    And the SSE row produced an MCPServerSSE instance
    And the streamable_http row produced an MCPServerStreamableHTTP instance
    And the inactive row is absent

  Scenario: System prompt lists active integration names
    Given workspace W has active MCP servers ["github", "azuredevops"]
    When build_agent(...) is called
    Then the constructed Agent's system prompt contains "## Connected Integrations" then "- github" then "- azuredevops"

  Scenario: System prompt omits the heading when no MCP servers
    Given workspace W has zero active MCP servers
    When build_agent(...) is called
    Then the constructed Agent's system prompt does not contain "## Connected Integrations"

  Scenario: add_mcp_server tool result redacts auth_header
    Given an active workspace and the agent built
    When the agent invokes add_mcp_server(name="x", url="https://mcp.example/", transport="sse", auth_header="ghp_TOPSECRET")
    Then the returned tool-result string does NOT contain "ghp_TOPSECRET"
    And it DOES contain the always-warn footer "consider deleting"

  Scenario: AsyncExitStack runs __aexit__ on agent.run() success
    Given a Slack dispatch with 1 active MCP server (a mock that records __aenter__ and __aexit__ calls)
    When the dispatch completes successfully
    Then __aenter__ was called exactly once
    And __aexit__ was called exactly once

  Scenario: AsyncExitStack runs __aexit__ on agent.run() exception
    Given a Slack dispatch where agent.run() raises RuntimeError mid-execution
    When the dispatch is invoked
    Then __aexit__ was still called exactly once on the MCP server
    And the original RuntimeError propagates

  Scenario: Zero-MCP workspace runs unchanged
    Given workspace W with no MCP servers
    When the existing slack-dispatch happy-path test runs
    Then it passes with no behavioural change vs. before this story

  Scenario: list_mcp_servers shows transport and active flag
    Given workspace W has [{name="github", transport="sse", is_active=true}, {name="x", transport="streamable_http", is_active=false}]
    When the agent invokes list_mcp_servers
    Then the returned string contains "github (sse, active)" and "x (streamable_http, disabled)"
```

### 2.2 Verification Steps (Manual)
- [ ] `pytest backend/tests/agents/test_agent_mcp.py backend/tests/services/test_slack_dispatch_*.py -v` — all 8+ new tests + existing dispatch tests pass.
- [ ] In a dev workspace with no MCP servers, send a Slack message — agent responds normally with no `## Connected Integrations` in its system prompt.
- [ ] Connect **GitHub MCP** (`https://api.githubcopilot.com/mcp/`, Streamable HTTP, Bearer PAT — verified V1 smoke target per STORY-012-04 §5.6) via the Slack `add_mcp_server` tool — verify the warn footer appears, the multi-header dashboard hint appears, AND `ghp_*` is NOT in the agent's reply.
- [ ] After the connect message, send a follow-up like "what GitHub username am I?" — agent should call `get_me` (one of the 41 tools registered) and return the answer in Slack.

## 3. The Implementation Guide

### 3.1 Context & Files

| Item | Value |
|---|---|
| Primary Modified Files | `backend/app/agents/agent.py` (AgentDeps extension, build_agent body, 3 new tools, system-prompt section), `backend/app/services/slack_dispatch.py` (AsyncExitStack wrapper) |
| Test File | `backend/tests/agents/test_agent_mcp.py` (NEW), `backend/tests/services/test_slack_dispatch_mcp_lifecycle.py` (NEW) |

### 3.2 Technical Logic

**`AgentDeps` field placement:** add at the end of the existing dataclass declaration (preserve field order for any positional-init paths in tests).

**Tool ordering in `build_agent`:** keep the existing 4 skill tools first, then add the 3 MCP tools in the order `add_mcp_server`, `remove_mcp_server`, `list_mcp_servers`. Match Pydantic AI's auto-generated tool docstrings: each tool's docstring should be a single sentence the model can read to decide when to call it.

**Pre-flight grep** (Developer must run before editing): `grep -rn "build_agent" backend/tests/` — every test fixture that calls `build_agent` should still unpack 2-tuple. Q6 chose this approach precisely so this grep returns "no changes needed in tests."

### 3.3 API Contract (agent tool surface)

| Tool | Args | Returns | Side effects |
|---|---|---|---|
| `add_mcp_server` | `name, url, transport='streamable_http', auth_header=None` | success/error string (NEVER echoes `auth_header`) | INSERT into `teemo_mcp_servers` via service |
| `remove_mcp_server` | `name` | success/not-found string | DELETE row |
| `list_mcp_servers` | — | enumerated names + transport + active flag | None |

## 4. Quality Gates

### 4.1 Minimum Test Expectations

| Test Type | Minimum Count | Notes |
|---|---|---|
| Agent tests (`test_agent_mcp.py`) | 5 | AgentDeps populated; system-prompt section presence/absence; tool redaction; transport dispatch (SSE vs Streamable HTTP); zero-MCP regression. |
| Dispatch lifecycle tests (`test_slack_dispatch_mcp_lifecycle.py`) | 3 | __aexit__ on success; __aexit__ on exception; zero-server pass-through. |

### 4.2 Definition of Done (The Gate)
- [ ] All §4.1 tests pass locally.
- [ ] All Gherkin scenarios from §2.1 covered.
- [ ] `grep -rn "build_agent" backend/tests/` shows no test was updated (Q6 pre-flight check confirms zero-blast-radius).
- [ ] `_is_safe_url` import path in `agent.py` updated to `from app.core.url_safety import is_safe_url` (012-01 hand-off).
- [ ] Manual smoke: connect Azure DevOps Remote MCP via Slack tool, verify warn footer + token redaction.
- [ ] Architect/Developer self-review.

---

## ClearGate Ambiguity Gate (🟢 / 🟡 / 🔴)
**Current Status: 🟢 Low.** AgentDeps shape, tool signatures, system-prompt section format, AsyncExitStack pattern, redaction rules all specified. No TBDs.
