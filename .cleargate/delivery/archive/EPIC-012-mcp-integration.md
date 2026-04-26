---
epic_id: "EPIC-012"
status: "Shipped"
ambiguity: "🟢"
context_source: "PROPOSAL-001-teemo-platform.md"
owner: "sandrinio"
target_date: "TBD"
created_at: "2026-04-12T00:00:00Z"
updated_at: "2026-04-26T00:00:00Z"
created_at_version: "vbounce-backlog"
updated_at_version: "cleargate-2026-04-26-resolve-questions"
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

> **Ported from V-Bounce.** Original: `product_plans.vbounce-archive/backlog/EPIC-012_mcp_integration/EPIC-012_mcp_integration.md`. Carried forward during ClearGate migration 2026-04-24.

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
- `teemo_mcp_servers` table + migration `014_teemo_mcp_servers.sql`
- `mcp_service.py` — CRUD service layer with validation (slug name with reserved-name deny-list, HTTPS-only, IP blacklist via shared `url_safety` module, header encryption)
- REST endpoints: `POST/GET/PATCH/DELETE /api/workspaces/:id/mcp-servers`, `POST /api/workspaces/:id/mcp-servers/:name/test`
- 3 agent tools: `add_mcp_server`, `remove_mcp_server`, `list_mcp_servers` — users manage MCP connections via Slack chat. `add_mcp_server`'s tool-result echo redacts the `auth_header` argument so the model context never re-emits the token (defence in depth on top of the always-warn message — see §6).
- Agent factory: load active MCP servers at build time, populate `AgentDeps.mcp_servers: list[MCPServer]`, construct `Agent(mcp_servers=deps.mcp_servers)`. Factory return shape stays 2-tuple (`(agent, deps)`) — DI-via-deps is the Pydantic AI documented best practice; avoids touching every test fixture that unpacks `build_agent`.
- Slack dispatch changes: `AsyncExitStack` reads `deps.mcp_servers` and wraps `agent.run()` so MCP `__aenter__`/`__aexit__` lifecycle runs once per Slack request, including on exception.
- System prompt: `## Connected Integrations` section listing active MCP server names (one line per server; tools enumerated by Pydantic AI itself, not the system prompt).
- Lift `_is_safe_url()` from `app/agents/agent.py` to a new `app/core/url_safety.py` module so MCP service and the existing `http_request` agent tool share a single source of truth.
- **Two transports supported**: classic SSE (`MCPServerSSE`) AND modern Streamable HTTP (`MCPServerStreamableHTTP`). DB `transport` column CHECK = `IN ('sse', 'streamable_http')`. Service-layer dispatch picks the right Pydantic AI class by transport value. Both share parent `_MCPServerHTTP` so URL safety, encryption, and AsyncExitStack lifecycle are identical.
- Frontend: MCP section in `WorkspaceCard` — list connected servers as cards, each showing name, URL, transport badge (SSE / Streamable HTTP), status badge, enable/disable toggle, test button, delete button.
- Frontend: "Add MCP Server" modal — name, URL, transport selector (radio: SSE / Streamable HTTP, default Streamable HTTP), and a **dynamic key-value headers editor** (matching Claude Desktop / Cursor / VS Code's general MCP-config shape). Default first header row is pre-populated with key `Authorization` for the 80% case; users add/remove/edit rows freely. Zero rows is allowed for servers that don't need auth.
- Frontend: optional **"Paste from another client" import affordance** in the modal — collapsible textarea + Import button. Accepts Claude Desktop's `mcpServers` wrapper, VS Code's `servers` wrapper (with `type:"http"` → `streamable_http` mapping), raw single-server JSON, or `{name → entry}` map. On Import the form fields are populated; the textarea is a one-shot helper, never the source of truth on submit. Rejects stdio configs (`command` / `args`) with a friendly error. Strips `${env:...}` / `${input:...}` placeholder values and prompts the user to fill them in.
- Frontend: pure-function JSON parser (`frontend/src/lib/mcpJsonImport.ts`) that the modal calls — fully unit-testable, no React imports.
- TanStack Query hooks for MCP CRUD + test connection.

### OUT-OF-SCOPE (Do NOT Build This)
- **stdio transport** — security risk (arbitrary process execution on host). HTTP-style transports only.
- **MCP server health monitoring / auto-reconnect** — server is connected fresh per agent run
- **Connection pooling / caching** — optimization deferred; acceptable latency for V1
- **MCP server discovery / marketplace** — user must know the server URL
- **Per-tool access control** — all tools from a connected MCP server are available to the agent
- **MCP server hosting** — Tee-Mo does not host MCP servers; users connect to externally hosted ones
- **Dedicated workspace settings page** — MCP section lives inline in `WorkspaceCard` (same as BYOK keys)
- **Configurable test-connection timeout** — Q2 chose 10s flat; only revisit if real-world reports surface false-fails on cold-start MCP servers

---

## 3. Context

### 3.1 User Personas
- **Workspace Admin (Dashboard)**: Configures MCP servers via the web UI. Wants to see status, test connections, and manage access.
- **Workspace Admin (Slack)**: Prefers to set up integrations directly in Slack chat.
- **Slack User**: Benefits from MCP tools without knowing they exist.

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
| **Security** | HTTP-style transports only (`sse`, `streamable_http`). HTTPS only. IP blacklist via shared `app.core.url_safety._is_safe_url()`. Headers encrypted at rest (AES-256-GCM, reuses `app.core.encryption`). Reserved-name deny-list rejects server names colliding with first-party agent tools (`search`, `skill`, `skills`, `knowledge`, `automation`, `automations`, `http_request`). |
| **Tech Stack** | Pydantic AI 1.79 — `MCPServerSSE` for `transport='sse'`, `MCPServerStreamableHTTP` for `transport='streamable_http'`. MCP extra confirmed satisfied transitively via `pydantic-ai==1.79.0` → `pydantic-ai-slim[mcp,fastmcp,...]`; verified `from pydantic_ai.mcp import MCPServerSSE, MCPServerStreamableHTTP` imports cleanly 2026-04-26. |
| **Performance** | MCP servers connected per request (no pooling). SSE/Streamable HTTP handshake adds latency — acceptable for V1. Test-connection timeout = 10s. |
| **UI Pattern** | Inline in `WorkspaceCard`, same patterns as `KeySection` (BYOK). Cards, badges, modals, inline errors. |

---

## 4. Technical Context

### 4.1 Affected Areas
| Area | Files/Modules | Change Type |
|------|---------------|-------------|
| Migration | `database/migrations/014_teemo_mcp_servers.sql` | **New** — `transport` CHECK = `IN ('sse','streamable_http')` |
| URL safety (shared) | `backend/app/core/url_safety.py` | **New** — lift `_is_safe_url()` from `agent.py`; export public `is_safe_url()` |
| Agent factory | `backend/app/agents/agent.py` | **Modify** — re-import `is_safe_url` from `core.url_safety`; add `mcp_servers` to `AgentDeps`; load active servers; pass to `Agent(mcp_servers=deps.mcp_servers)`; add 3 agent tools (`add_mcp_server`/`remove_mcp_server`/`list_mcp_servers`); append `## Connected Integrations` to system prompt. **Return signature stays 2-tuple.** |
| MCP service | `backend/app/services/mcp_service.py` | **New** — CRUD + validation; transport dispatcher (`sse` → `MCPServerSSE`, `streamable_http` → `MCPServerStreamableHTTP`); reserved-name deny-list; `test_connection()` runs handshake + `tools/list`, asserts ≥1 tool returned |
| MCP routes | `backend/app/api/routes/mcp_servers.py` | **New** — REST endpoints, `assert_team_member` auth, list never returns decrypted headers |
| Slack dispatch | `backend/app/services/slack_dispatch.py` | **Modify** — `AsyncExitStack` reads `deps.mcp_servers` and wraps `agent.run()`; covers exception path |
| Main app | `backend/app/main.py` | **Modify** — mount MCP router, update `TEEMO_TABLES` |
| Frontend hooks | `frontend/src/hooks/useMcpServers.ts` | **New** — TanStack Query hooks |
| Frontend UI | `frontend/src/components/dashboard/WorkspaceCard.tsx` | **Modify** — add MCP section beneath `KeySection` |
| Frontend modal | `frontend/src/components/dashboard/AddMcpServerModal.tsx` | **New** — name + URL + transport selector + auth header inputs |
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
| `teemo_mcp_servers` | **NEW** | `id` (UUID PK), `workspace_id` (FK → `teemo_workspaces`, `ON DELETE CASCADE`), `name` (text, slug regex `^[a-z0-9_-]{2,32}$`, unique per workspace, NOT IN reserved-deny-list at app layer), `transport` (text, CHECK `IN ('sse', 'streamable_http')`), `url` (text, HTTPS-only validated server-side), `headers_encrypted` (jsonb, AES-256-GCM-encrypted values via `app.core.encryption`), `is_active` (bool, default true), `created_at` (timestamptz, default now()). Migration file: `014_teemo_mcp_servers.sql`. |

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

#### STORY-012-01: MCP Service Layer (foundation)
- New file `backend/app/core/url_safety.py` — exports `is_safe_url(url: str) -> tuple[bool, str | None]`. Lifts logic from existing private `_is_safe_url()` in `agents/agent.py`; latter re-imports the public form. No behavioral change for the existing `http_request` agent tool.
- Migration `014_teemo_mcp_servers.sql` per §4.3, with `CHECK (transport IN ('sse', 'streamable_http'))`.
- `backend/app/services/mcp_service.py`: `list_mcp_servers`, `get_mcp_server`, `create_mcp_server`, `update_mcp_server`, `delete_mcp_server`, `test_connection`.
- Validation: slug regex `^[a-z0-9_-]{2,32}$`; reserved-name deny-list `{search, skill, skills, knowledge, automation, automations, http_request}`; HTTPS-only URL; `is_safe_url()` IP-blacklist check; header value encryption via `app.core.encryption`.
- `test_connection(workspace_id, name)`: 10s timeout. Constructs `MCPServerSSE` or `MCPServerStreamableHTTP` based on transport column, runs `__aenter__` (handshake), invokes `tools/list`, asserts ≥ 1 tool. Returns `{ok: bool, tool_count: int, error: str | None}`.
- Tests: 12+ unit tests covering CRUD, all validation paths (slug/reserved-name/HTTPS/IP-blacklist/header encryption round-trip), test-connection happy path, test-connection sad paths (timeout, 0 tools returned, handshake error).

#### STORY-012-02: MCP REST Endpoints
- `POST /api/workspaces/:id/mcp-servers` — create (requires `assert_team_member`); accepts `{name, transport, url, headers}` body where `transport` defaults to `streamable_http`.
- `GET /api/workspaces/:id/mcp-servers` — list (returns `{name, transport, url, is_active, created_at}` — never decrypted headers).
- `PATCH /api/workspaces/:id/mcp-servers/:name` — update (url, headers, is_active, transport).
- `DELETE /api/workspaces/:id/mcp-servers/:name` — delete.
- `POST /api/workspaces/:id/mcp-servers/:name/test` — test connection (delegates to `mcp_service.test_connection()`).
- Tests: 10+ endpoint tests — auth matrix (member/non-member/non-existent), list-never-leaks-headers, test happy + sad paths via `respx`/`httpx_mock` stub, plus ONE integration smoke that spins a minimal in-process SSE responder fixture.

#### STORY-012-03: Agent MCP Wiring (DI via AgentDeps, NOT a return-shape change)
- `AgentDeps` dataclass gains `mcp_servers: list[MCPServer] = field(default_factory=list)`.
- `build_agent()` fetches active MCP servers via `mcp_service.list_mcp_servers(workspace_id, active_only=True)`, instantiates `MCPServerSSE` or `MCPServerStreamableHTTP` per row, populates `deps.mcp_servers`. **Return signature unchanged: 2-tuple `(agent, deps)`.**
- `Agent(...)` constructed with `mcp_servers=deps.mcp_servers`.
- System prompt: append `## Connected Integrations` section with active server names (one line per server). No tool enumeration in the prompt — Pydantic AI registers tools itself.
- 3 agent tools: `add_mcp_server(ctx, name, transport, url, auth_header=None)` — creates server, returns success message + always-warn footer "⚠️ Your auth token is encrypted server-side, but the message you sent is still in this thread — consider deleting it." **Tool result echoes back name/url/transport but NEVER `auth_header`** (defence in depth — Q3+Q7). `remove_mcp_server(ctx, name)`, `list_mcp_servers(ctx)`.
- `slack_dispatch.py`: `async with AsyncExitStack() as stack:` enters each `deps.mcp_servers` server before calling `agent.run()`. Pattern matches Pydantic AI MCP example. Verified to honour `__aexit__` on exception.
- Tests: 8+ tests — `AgentDeps.mcp_servers` populated correctly from DB; agent constructed with right MCP-server instances per transport; system prompt contains `## Connected Integrations`; `add_mcp_server` tool result redacts `auth_header`; AsyncExitStack `__aexit__` runs on `agent.run()` raise; happy path with zero MCP servers configured (regression check for existing workspaces).

#### STORY-012-04: MCP Dashboard UI
- `WorkspaceCard.tsx`: new "Integrations" inline section below `KeySection`.
- Each connected MCP server rendered as a mini-card: name, URL, transport badge (SSE / Streamable HTTP), status badge (Active / Disabled / Untested), enable/disable toggle, Test button, Delete button.
- "Add Integration" button → `AddMcpServerModal`.
- Modal fields: Name (slug input with client-side regex hint), Transport (radio, default Streamable HTTP), URL (text input), **Headers (dynamic key-value editor)**. Default first row pre-populated with key `Authorization` for the 80% case; users add/remove/edit rows freely; zero rows allowed for servers that don't need auth.
- Modal also exposes a collapsible **"Paste from another client" textarea** (advanced affordance). Clicking Import parses pasted JSON via the new pure-function `mcpJsonImport.ts` lib and populates the form fields. Accepts Claude Desktop's `mcpServers` wrapper, VS Code's `servers`+`type` wrapper, raw single-server entries, and `{name → entry}` maps. Rejects stdio configs (presence of `command` / `args`) with a security-minded error. Strips `${env:...}` / `${input:...}` placeholder values and prompts the user to fill them in.
- New extracted reusable component `HeadersEditor.tsx` (dumb controlled component over `Array<{key, value}>`).
- New pure-function lib `frontend/src/lib/mcpJsonImport.ts` — parser logic, fully unit-testable, no React imports.
- `useMcpServers.ts`: TanStack Query hooks — `useMcpServersQuery`, `useCreateMcpServerMutation`, `useUpdateMcpServerMutation`, `useDeleteMcpServerMutation`, `useTestMcpServerMutation`.
- Tests (~17 across 5 files): 4 Modal (slug regex rejection + 3 submit body shapes for 1/multi/zero headers + JSON-import populate), 3 Section, 3 HeadersEditor, 6 Parser (Shapes A/B/C + stdio rejection + placeholder detection + invalid JSON), 2 Hook.

---

## 6. Risks & Edge Cases
| Risk | Likelihood | Mitigation |
|------|------------|------------|
| `pydantic-ai[mcp]` extra not available in 1.79 | Medium | Verify before sprint. If unavailable, implement raw SSE client as fallback. |
| MCP server SSE handshake slow (>5s) | Medium | Agent runs async after Slack 200 ack. V1 accepts latency; connection pooling is a future optimization. |
| MCP server returns too many tools (bloats system prompt) | **Confirmed Medium** (GitHub MCP probe 2026-04-26 = 41 tools ≈ 6–10k tokens of overhead) | Pydantic AI handles tool registration; token cost is real and noticeable. **V1 accepts full tool surface.** **V2 mitigation**: expose `X-MCP-Toolsets` / `X-MCP-Tools` filtering headers (Microsoft + GitHub gateways both support; verified in CORS-allow-headers from the GitHub probe) as an "Advanced" modal field. Flashcard required after first real-user connection. |
| DNS rebinding on MCP server URL | Low | `_is_safe_url()` resolves DNS then checks IPs — already mitigated. |
| User provides MCP server URL pointing to internal service | Medium | IP blacklist + HTTPS-only blocks most vectors. |
| MCP server auth token in Slack message history | Medium | Warn in agent response: "Your auth token has been encrypted and stored securely, but it's visible in this chat message. Consider deleting your message." |

---

## 7. Acceptance Criteria (Epic-Level)

```gherkin
Feature: MCP Server Integration

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

  Scenario: Add MCP server via Slack
    Given a Slack thread with the bot
    When user says "connect to GitHub MCP at https://mcp.example.com/sse with token ghp_abc"
    Then agent calls add_mcp_server tool
    And confirms "GitHub MCP connected. Tools available on your next message."

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
| Q1: Pydantic AI MCP extra availability in 1.79 | Verify `pip install pydantic-ai[mcp]` works | Blocks implementation | sandrinio | **Resolved 2026-04-26** — already satisfied. `pydantic-ai==1.79.0` transitively requires `pydantic-ai-slim[mcp,fastmcp,...]`; `from pydantic_ai.mcp import MCPServerSSE, MCPServerStreamableHTTP` imports cleanly in backend venv. No pyproject change needed. |
| Q2: MCP handshake timeout | A: 5s, B: 10s, C: 15s | Affects test-connection UX | sandrinio | **Resolved 2026-04-26** — B (10s). 5s false-fails on cold-start TLS + real MCP server warmup (3–7s typical); 15s too slow for a "Test" button. |
| Q3: Should agent warn about token visibility in chat? | A: Yes (always), B: Only on first use | UX polish vs. noise | sandrinio | **Resolved 2026-04-26** — A (always). One-liner appended to success response, not a modal. "First use only" loses the signal when admin adds a 2nd/3rd server later — same risk, no warning. |
| Q4: Test-connection success criterion | A: SSE handshake completes, B: handshake + ≥1 tool returned, C: HTTP HEAD only | Determines what "Connected ✓" actually proves | sandrinio | **Resolved 2026-04-26** — B (handshake + ≥1 tool). A passes against any SSE endpoint; C passes against any URL. Only B verifies the endpoint is genuinely MCP-shaped. Latency bounded by Q2's 10s. |
| Q5: Migration numbering ordering | A: skip dup → `014_*`; B: switch to timestamped; C: rename + fix | Schema hygiene; affects deployment doc | sandrinio | **Resolved 2026-04-26** — C. Existing `012_teemo_automations.sql` renamed to `012a_teemo_automations.sql` (preserves alphabetic sort, zero runtime risk since migrations are idempotent + manually pasted). New MCP migration = `014_teemo_mcp_servers.sql`. README inventory + numbering-fix note added. |
| Q6: `build_agent` signature change for MCP | A: 2→3-tuple; B: add to `AgentDeps` | Test-fixture blast radius | sandrinio | **Resolved 2026-04-26** — B (DI via `AgentDeps`). Web-research confirms Pydantic AI's documented best practice: "the wrong way is global variables or factory return values; the right way is dependency injection". Test fixtures untouched; signature stays 2-tuple. |
| Q7: Test-connection SSE fixturing | A: stubs only; B: real responder; C: both | Determines test fidelity vs. CI speed | sandrinio | **Resolved 2026-04-26** — C. `respx`/`httpx_mock` stubs for unit tests (fast, no I/O); ONE integration smoke spinning a minimal in-process SSE responder. Mirrors the existing Slack signing-test pattern. |
| Q8: `_is_safe_url()` location | A: keep private to `agent.py`; B: lift to `app/core/url_safety.py` | Code reuse + import shape | sandrinio | **Resolved 2026-04-26** — B. Lift to `app/core/url_safety.py`; re-import from `agent.py`; MCP service uses the public form. Single source of truth for URL safety. |
| Q9: Reserved server-name deny-list contents | List of forbidden slugs | Prevent collision with first-party agent tools | sandrinio | **Resolved 2026-04-26** — `{search, skill, skills, knowledge, automation, automations, http_request}`. Future first-party tool additions must update the deny-list (flashcard tag for this). |
| Q10: Agent tool echo redaction | A: redact `auth_header`; B: echo verbatim | Defence in depth on top of always-warn | sandrinio | **Resolved 2026-04-26** — A. `add_mcp_server`'s tool-result string returns name/url/transport but never `auth_header`. Cheap; reduces blast radius if Slack message-history is exfiltrated. |
| Q11: Transport set in V1 | A: SSE only; B: SSE + Streamable HTTP | Determines which remote MCP servers we can connect to | sandrinio | **Resolved 2026-04-26** — B. Microsoft is migrating Azure DevOps + their other servers to Streamable HTTP; SSE is becoming legacy. Both `MCPServerSSE` and `MCPServerStreamableHTTP` inherit from `_MCPServerHTTP` so the URL safety, encryption, AsyncExitStack, and test-connection logic are identical — service-layer dispatcher picks the class by `transport` column. ~5 LOC additional cost; locks in Azure DevOps Remote MCP as a viable smoke target. |

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
- Pydantic AI MCP docs: https://ai.pydantic.dev/mcp/

---

## Change Log
| Date | Change | By |
|------|--------|-----|
| 2026-04-12 | Initial draft. Covers full MCP lifecycle: DB, service, REST, agent tools, dispatch lifecycle, dashboard UI. 4 stories. SSE-only transport, HTTPS-only, IP blacklist, encrypted headers. | sandrinio + Claude |
| 2026-04-26 | Resolved all 4 open questions: pydantic-ai MCP extra confirmed satisfied transitively; SSE timeout = 10s; always-warn on token visibility in chat; test-connection = full SSE handshake. Ambiguity 🟡 → 🟢. | sandrinio + Claude |
| 2026-04-26 | Sprint-planning-pass: 7 additional decisions locked. Q5 (migration numbering = 014 + rename collider to 012a). Q6 (`build_agent` keeps 2-tuple; MCP servers via `AgentDeps` per Pydantic AI DI best practice). Q7 (test-connection fixture = stubs + one in-process integration smoke). Q8 (lift `_is_safe_url()` to `app/core/url_safety.py`). Q9 (reserved-name deny-list documented). Q10 (`add_mcp_server` redacts `auth_header` in echo). **Q11 (scope expansion): support both `sse` AND `streamable_http` transports** — Microsoft migrating Azure DevOps + others to Streamable HTTP; both inherit from `_MCPServerHTTP` so additional cost ~5 LOC. §2/§4.1/§4.3/§5 updated accordingly. | sandrinio + Claude |
| 2026-04-26 | UX-pass: confirmed Tee-Mo MCP integration stays **fully general** (matches Claude Desktop / Cursor / VS Code's "form-as-typed-JSON-builder" model — no pre-defined per-server integrations to maintain). STORY-012-04 modal redesigned: single `auth_header` field replaced with **dynamic key-value Headers editor** (add/remove/edit rows, zero rows allowed); added **optional "Paste from another client" JSON-import affordance** with parser supporting Claude Desktop / VS Code / raw / map shapes (rejects stdio, strips `${env:...}` placeholders); new pure-function lib `mcpJsonImport.ts` + `HeadersEditor.tsx` extracted. STORY-012-03 agent tool clarified: Slack-chat `add_mcp_server` exposes the 80% case (single `auth_header` → Authorization Bearer); complex multi-header cases route users to the dashboard via a hint in the success message. **OAuth-flow MCP servers (e.g. Azure DevOps Remote at `mcp.dev.azure.com`) explicitly out of V1 scope** — flagged for follow-up as EPIC-026 stub. | sandrinio + Claude |
| 2026-04-26 | Pre-sprint-validation pass: ran end-to-end probes against (a) Azure DevOps REST + Remote MCP via owner-supplied PAT, (b) GitHub MCP via owner-supplied PAT. **Findings**: AzDO REST works (PAT lists projects/teams/iterations/work items); AzDO Remote MCP rejects PAT auth at protocol layer (Entra-OAuth-only — confirms EPIC-026 plan). GitHub MCP fully validated end-to-end: `initialize` → `tools/list` (41 tools) → `tools/call get_me` all green. **V1 acceptance smoke target = GitHub MCP** (`https://api.githubcopilot.com/mcp/`, Streamable HTTP, Bearer PAT). Token-budget signal upgraded from Low → Medium in §6 risks (41 tools × ~150–250 tokens each ≈ 6–10k system-prompt tokens per connected server) — V1 accepts the cost, V2 should expose `X-MCP-Toolsets` filtering. Full runbooks captured in STORY-012-04 §5.2 (AzDO findings) and §5.6 (GitHub MCP runbook). | sandrinio + Claude |
