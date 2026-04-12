---
epic_id: "EPIC-012"
status: "Draft"
ambiguity: "🟡 Medium"
context_source: "EPIC-007 agent factory / Pydantic AI MCP docs / workspace settings UI patterns"
release: "Release 2: Core Pipeline"
owner: "sandrinio"
priority: "P1 - High"
tags: ["backend", "frontend", "agent", "mcp", "pydantic-ai", "integrations"]
target_date: "TBD"
---

# EPIC-012: MCP Server Integration

## 1. Problem & Value

### 1.1 The Problem

Tee-Mo's agent currently has a fixed set of built-in tools (skill CRUD, web search, page crawl, HTTP requests). When users want the agent to interact with external services like GitHub, Linear, Jira, or databases, they must either craft raw HTTP requests via the `http_request` tool or write skill instructions that describe API calls step-by-step. This is fragile, requires users to know API details, and doesn't scale.

### 1.2 The Solution

Allow workspace admins to connect **MCP (Model Context Protocol) servers** to their workspace. MCP servers expose pre-built, well-typed tools that the agent discovers automatically at runtime. A user connects a GitHub MCP server once, and the agent immediately gains tools like `create_issue`, `list_pull_requests`, `search_code` — no manual API instructions needed.

Management is available through both **REST API** (for dashboard UI) and **agent conversation** (for Slack-native setup).

### 1.3 Success Metrics
- Admin can connect an MCP server via the dashboard or Slack conversation.
- Agent automatically discovers and uses MCP tools on the next message.
- Dashboard shows all connected MCP servers per workspace with live connection status.
- Admin can test, enable/disable, and remove MCP connections from the dashboard.
- No MCP server auth tokens are stored in plaintext or exposed in API responses.
- Private/internal network URLs are blocked at registration time.

---

## 2. Scope Boundaries

### IN-SCOPE (Build This)
- `teemo_mcp_servers` table + migration
- `mcp_service.py` — CRUD service layer with validation (slug name, HTTPS-only, IP blacklist, header encryption)
- REST endpoints: `POST/GET/PATCH/DELETE /api/workspaces/:id/mcp-servers`, `POST /api/workspaces/:id/mcp-servers/:name/test`
- 3 agent tools: `add_mcp_server`, `remove_mcp_server`, `list_mcp_servers` — so users can manage MCP connections via Slack chat
- Agent factory changes: resolve MCP servers at build time, pass to `Agent(mcp_servers=[...])`
- Slack dispatch changes: `AsyncExitStack` lifecycle management for MCP servers around `agent.run()`
- System prompt: `## Connected Integrations` section listing active MCP server names
- Frontend: MCP section in `WorkspaceCard` — list connected servers as cards, each showing name, URL, status badge, enable/disable toggle, test button, delete button
- Frontend: "Add MCP Server" modal — name, URL, optional auth header inputs
- TanStack Query hooks for MCP CRUD + test connection

### OUT-OF-SCOPE (Do NOT Build This)
- **stdio transport** — security risk (arbitrary process execution on host). SSE only.
- **MCP server health monitoring / auto-reconnect** — server is connected fresh per agent run
- **Connection pooling / caching** — optimization deferred; acceptable latency for V1
- **MCP server discovery / marketplace** — user must know the server URL
- **Per-tool access control** — all tools from a connected MCP server are available to the agent
- **MCP server hosting** — Tee-Mo does not host MCP servers; users connect to externally hosted ones
- **Dedicated workspace settings page** — MCP section lives inline in `WorkspaceCard` (same as BYOK keys)

---

## 3. Context

### 3.1 User Personas
- **Workspace Admin (Dashboard)**: Configures MCP servers via the web UI. Wants to see status, test connections, and manage access.
- **Workspace Admin (Slack)**: Prefers to set up integrations directly in Slack chat: "Connect my GitHub MCP server at https://..."
- **Slack User**: Benefits from MCP tools without knowing they exist. Asks the agent "create an issue for this bug" and it just works.

### 3.2 User Journey — Dashboard Flow
```
Admin opens workspace card
  → Sees "Integrations" section (empty or with existing MCP cards)
  → Clicks "Add Integration"
  → Modal: enters name, SSE URL, optional auth header
  → Clicks "Test Connection" → green/red status
  → Clicks "Save" → card appears with status badge
  → Can toggle enable/disable, re-test, or delete
```

### 3.3 User Journey — Slack Flow
```
Admin: "@tee-mo connect to GitHub MCP at https://mcp.example.com/sse with token ghp_abc123"
Agent: calls add_mcp_server() → "GitHub MCP connected. I'll have access to its tools on your next message."
Admin: "@tee-mo list my integrations"
Agent: calls list_mcp_servers() → "Connected: github (active), linear (active)"
Admin: "@tee-mo remove the linear integration"
Agent: calls remove_mcp_server() → "Linear MCP disconnected."
```

### 3.4 Constraints
| Type | Constraint |
|------|------------|
| **Security** | SSE transport only. HTTPS only. IP blacklist via `_is_safe_url()`. Headers encrypted at rest (AES-256-GCM). |
| **Tech Stack** | Pydantic AI 1.79 MCP support (`MCPServerHTTP`). Verify `pydantic-ai[mcp]` extra availability. |
| **Performance** | MCP servers connected per request (no pooling). SSE handshake adds latency — acceptable for V1. Agent already runs async after Slack 200 ack. |
| **UI Pattern** | Inline in `WorkspaceCard`, same patterns as `KeySection` (BYOK). Cards, badges, modals, inline errors. |

---

## 4. Technical Context

### 4.1 Affected Areas
| Area | Files/Modules | Change Type |
|------|---------------|-------------|
| Migration | `database/migrations/0XX_teemo_mcp_servers.sql` | **New** |
| MCP service | `backend/app/services/mcp_service.py` | **New** — CRUD + validation |
| MCP routes | `backend/app/api/routes/mcp_servers.py` | **New** — REST endpoints |
| Agent factory | `backend/app/agents/agent.py` | **Modify** — MCP resolution, tools, system prompt, return signature |
| Slack dispatch | `backend/app/services/slack_dispatch.py` | **Modify** — AsyncExitStack lifecycle |
| Main app | `backend/app/main.py` | **Modify** — mount MCP router, update TEEMO_TABLES |
| Frontend hooks | `frontend/src/hooks/useMcpServers.ts` | **New** — TanStack Query hooks |
| Frontend UI | `frontend/src/components/dashboard/WorkspaceCard.tsx` | **Modify** — add MCP section |
| Frontend modal | `frontend/src/components/dashboard/AddMcpServerModal.tsx` | **New** |
| API client | `frontend/src/lib/api.ts` | **Modify** — add MCP API wrappers |

### 4.2 Dependencies
| Type | Dependency | Status |
|------|------------|--------|
| **Requires** | EPIC-007: Agent factory + `_is_safe_url()` + `http_request` tool | Done (S-07) |
| **Requires** | EPIC-004: `core.encryption` (encrypt/decrypt) | Done (S-06) |
| **Requires** | EPIC-003 Slice B: WorkspaceCard UI patterns | Done (S-05) |
| **Requires** | Pydantic AI MCP extra (`pydantic-ai[mcp]`) | **Verify** |

### 4.3 Data Changes
| Entity | Change | Fields |
|--------|--------|--------|
| `teemo_mcp_servers` | **NEW** | `id` (UUID PK), `workspace_id` (FK), `name` (slug, unique per workspace), `transport` (text, CHECK = 'sse'), `url` (text, HTTPS only), `headers_encrypted` (jsonb, encrypted values), `is_active` (bool), `created_at` (timestamptz). |

---

## 5. Story Decomposition

### Story Map

| # | Story | Complexity | Dependencies | Scope |
|---|-------|-----------|--------------|-------|
| 1 | **STORY-012-01: MCP Service Layer** | L1 | — | Migration + `mcp_service.py` CRUD with validation |
| 2 | **STORY-012-02: MCP REST Endpoints** | L2 | 012-01 | REST API + test-connection endpoint |
| 3 | **STORY-012-03: Agent MCP Wiring** | L2 | 012-01 | Agent factory + dispatch lifecycle + agent tools |
| 4 | **STORY-012-04: MCP Dashboard UI** | L2 | 012-02 | Frontend cards, modal, hooks, status badges |

### Suggested Sequencing
- **Phase 1**: STORY-012-01 (service layer) — foundation, no dependencies
- **Phase 2 (parallel)**: STORY-012-02 (REST) + STORY-012-03 (agent wiring) — both depend on 012-01, but touch disjoint files
- **Phase 3**: STORY-012-04 (frontend) — depends on 012-02 for API

### Story Summaries

#### STORY-012-01: MCP Service Layer
- `teemo_mcp_servers` migration with `CHECK (transport = 'sse')` constraint
- `mcp_service.py`: `list_mcp_servers`, `get_mcp_server`, `create_mcp_server`, `update_mcp_server`, `delete_mcp_server`
- Validation: slug name regex, HTTPS-only URL, `_is_safe_url()` IP check, header value encryption
- `test_connection(workspace_id, name, supabase)` — attempts SSE handshake, returns success/error
- Tests: 10+ unit tests covering CRUD + all validation paths

#### STORY-012-02: MCP REST Endpoints
- `POST /api/workspaces/:id/mcp-servers` — create (requires workspace ownership)
- `GET /api/workspaces/:id/mcp-servers` — list (returns name, url, is_active, created_at — no decrypted headers)
- `PATCH /api/workspaces/:id/mcp-servers/:name` — update (url, headers, is_active)
- `DELETE /api/workspaces/:id/mcp-servers/:name` — delete
- `POST /api/workspaces/:id/mcp-servers/:name/test` — test connection, returns `{status: "ok"}` or `{status: "error", detail: "..."}`
- Auth: workspace owner only (same pattern as channel binding endpoints)
- Tests: 8+ endpoint tests

#### STORY-012-03: Agent MCP Wiring
- `build_agent()` fetches active MCP servers, creates `MCPServerHTTP` instances, returns 3-tuple `(agent, deps, mcp_servers)`
- Agent constructed with `mcp_servers=[...]`
- System prompt: `## Connected Integrations` section with MCP server names
- 3 agent tools: `add_mcp_server(ctx, name, url, auth_header)`, `remove_mcp_server(ctx, name)`, `list_mcp_servers(ctx)`
- `slack_dispatch.py`: `AsyncExitStack` wrapping `agent.run()` for MCP lifecycle
- Tests: 6+ tests (factory with/without MCP, dispatch lifecycle mock, agent tools)

#### STORY-012-04: MCP Dashboard UI
- `WorkspaceCard.tsx`: new "Integrations" collapsible section below KeySection
- Each connected MCP server rendered as a mini-card:
  - Name + URL (truncated)
  - Status badge: "Connected" (green) / "Disconnected" (red) / "Disabled" (gray)
  - Enable/disable toggle
  - "Test" button → calls test endpoint, shows result inline
  - "Delete" button → confirm then delete
- "Add Integration" button → `AddMcpServerModal`
- Modal fields: Name (slug input), URL (text input), Auth Header (password input, optional)
- `useMcpServers.ts`: TanStack Query hooks — `useMcpServersQuery`, `useCreateMcpServerMutation`, `useUpdateMcpServerMutation`, `useDeleteMcpServerMutation`, `useTestMcpServerMutation`
- Query key: `['mcp-servers', workspaceId]`

---

## 6. Risks & Edge Cases
| Risk | Likelihood | Mitigation |
|------|------------|------------|
| `pydantic-ai[mcp]` extra not available in 1.79 | Medium | Verify before sprint. If unavailable, implement raw SSE client as fallback. |
| MCP server SSE handshake slow (>5s) | Medium | Agent runs async after Slack 200 ack, so Slack timeout is not an issue. But slow handshake degrades UX. V1 accepts this; connection pooling is a future optimization. |
| MCP server returns too many tools (bloats system prompt) | Low | Pydantic AI handles tool registration; token cost increases. Monitor in practice. Per-tool filtering is out of scope for V1. |
| DNS rebinding on MCP server URL | Low | `_is_safe_url()` resolves DNS then checks IPs — already mitigated. |
| User provides MCP server URL pointing to internal service | Medium | IP blacklist + HTTPS-only blocks most vectors. SSRF via DNS rebinding covered by resolve-then-check. |
| MCP server auth token in Slack message history | Medium | Token is visible in chat when user types it. Warn in agent response: "Your auth token has been encrypted and stored securely, but it's visible in this chat message. Consider deleting your message." |
| Agent adds MCP server via tool, token in skill instructions | Low | Agent tools encrypt headers at storage time. The `add_mcp_server` tool accepts auth_header param, encrypts immediately — plaintext never stored. |

---

## 7. Acceptance Criteria (Epic-Level)

```gherkin
Feature: MCP Server Integration

  # --- Dashboard Management ---

  Scenario: Add MCP server via dashboard
    Given admin opens workspace card
    When they click "Add Integration" and enter name="github", url="https://mcp.example.com/sse", auth header
    And click "Save"
    Then a new MCP server card appears with status badge
    And the auth header is encrypted in the database

  Scenario: Test MCP connection
    Given workspace has a connected MCP server "github"
    When admin clicks "Test" on the github card
    Then the system attempts an SSE handshake
    And shows "Connected" (green) or error message (red)

  Scenario: Disable MCP server
    Given workspace has active MCP server "github"
    When admin toggles it to disabled
    Then the agent no longer loads github tools on the next message
    And the card shows "Disabled" (gray) badge

  Scenario: Delete MCP server
    Given workspace has MCP server "github"
    When admin clicks delete and confirms
    Then the server is removed from the database
    And the card disappears

  # --- Slack Management ---

  Scenario: Add MCP server via Slack
    Given a Slack thread with the bot
    When user says "connect to GitHub MCP at https://mcp.example.com/sse with token ghp_abc"
    Then agent calls add_mcp_server tool
    And confirms "GitHub MCP connected. Tools available on your next message."

  Scenario: List integrations via Slack
    Given workspace has 2 MCP servers
    When user asks "what integrations do I have?"
    Then agent calls list_mcp_servers and lists them with status

  Scenario: Remove MCP server via Slack
    When user says "disconnect the github integration"
    Then agent calls remove_mcp_server and confirms removal

  # --- Agent Tool Discovery ---

  Scenario: Agent uses MCP tools
    Given workspace has active GitHub MCP server
    When user says "@tee-mo list my open pull requests"
    Then the agent calls the MCP-provided list_pull_requests tool
    And returns the results in the thread

  # --- Security ---

  Scenario: Block private IP URL
    When admin tries to add MCP server with url="https://10.0.0.1/sse"
    Then the request is rejected with "unsafe URL" error

  Scenario: Block HTTP URL
    When admin tries to add MCP server with url="http://insecure.com/sse"
    Then the request is rejected with "HTTPS required" error

  Scenario: Block stdio transport
    Then only "sse" transport is accepted at the database level
```

---

## 8. Open Questions
| Question | Options | Impact | Owner | Status |
|----------|---------|--------|-------|--------|
| Pydantic AI MCP extra availability in 1.79 | Verify `pip install pydantic-ai[mcp]` works | Blocks implementation | — | **Open — verify before sprint** |
| MCP SSE handshake timeout | A: 5s, B: 10s, C: 15s | Affects test-connection UX and agent startup time | sandrinio | Proposed: 10s |
| Should agent warn about token visibility in chat? | A: Yes (always), B: Only on first use | UX polish vs. noise | sandrinio | Proposed: A |
| Test-connection implementation | A: Full SSE handshake + tool list, B: Just HTTP HEAD to URL | A is more accurate but slower; B is fast but doesn't verify MCP protocol | sandrinio | Proposed: A |

---

## 9. Artifact Links

**Stories:**
- [ ] STORY-012-01: MCP Service Layer — Draft
- [ ] STORY-012-02: MCP REST Endpoints — Draft
- [ ] STORY-012-03: Agent MCP Wiring — Draft
- [ ] STORY-012-04: MCP Dashboard UI — Draft

**References:**
- Agent factory: `backend/app/agents/agent.py` (STORY-007-02)
- Encryption: `backend/app/core/encryption.py` (EPIC-004)
- IP safety: `_is_safe_url()` in `agent.py`
- UI patterns: `WorkspaceCard.tsx`, `KeySection` inline pattern
- Pydantic AI MCP docs: https://ai.pydantic.dev/mcp/

---

## Change Log
| Date | Change | By |
|------|--------|-----|
| 2026-04-12 | Initial draft. Covers full MCP lifecycle: DB, service, REST, agent tools, dispatch lifecycle, dashboard UI. 4 stories. SSE-only transport, HTTPS-only, IP blacklist, encrypted headers. | sandrinio + Claude |
