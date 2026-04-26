---
story_id: "STORY-012-02-mcp-rest-endpoints"
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

# STORY-012-02: MCP REST Endpoints
**Complexity:** L2 — REST routes + auth + test-connection wiring on top of 012-01's service.

## 1. The Spec (The Contract)

### 1.1 User Story
As a workspace admin, I want REST endpoints to register, list, update, test, and remove MCP servers, so that the dashboard UI (012-04) can drive MCP management end-to-end and CLI/curl tooling has a stable surface.

### 1.2 Detailed Requirements
1. **New file `backend/app/api/routes/mcp_servers.py`** mounted in `app/main.py` under prefix `/api/workspaces/{workspace_id}/mcp-servers`. All endpoints require `assert_team_member(team_id_of_workspace, user_id)` — same auth model as workspace-scoped routes (per BUG-002 fix).
2. **Endpoints**:
   - `POST /api/workspaces/{workspace_id}/mcp-servers` — body `{name: str, transport: 'sse' | 'streamable_http' = 'streamable_http', url: str, headers: dict[str, str] | None = None}`. Calls `mcp_service.create_mcp_server`. Returns 201 with the public response shape (no decrypted headers ever).
   - `GET /api/workspaces/{workspace_id}/mcp-servers` — returns `list[McpServerPublic]`. Public shape: `{name, transport, url, is_active, created_at}`. **Decrypted headers MUST NOT appear in any response.**
   - `PATCH /api/workspaces/{workspace_id}/mcp-servers/{name}` — body fields all optional: `{transport?, url?, headers?, is_active?}`. Calls `mcp_service.update_mcp_server`. Returns 200 with public shape. `headers={}` clears all; absent `headers` leaves existing.
   - `DELETE /api/workspaces/{workspace_id}/mcp-servers/{name}` — 204 on success.
   - `POST /api/workspaces/{workspace_id}/mcp-servers/{name}/test` — runs `mcp_service.test_connection`. Returns 200 with body `{ok: bool, tool_count: int, error: str | None}`. **Status code is always 200** even on `ok=False`; the body's `ok` flag is what the UI reads. Reason: a test-connection call succeeded at the HTTP layer; only the upstream MCP handshake failed.
3. **Error mapping**: `McpValidationError` → 400 with `{"detail": <message>}`; not-found on update/delete/test → 404; auth failure → 403 (existing pattern); workspace not in team → 404 from `assert_team_member`.
4. **`main.py`**: include the new router; add `"teemo_mcp_servers"` to `TEEMO_TABLES`.

### 1.3 Out of Scope
- Service-layer logic (lives in 012-01).
- Agent factory wiring (012-03).
- Frontend (012-04).
- Per-tool ACL UI / API.

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria (Gherkin)

```gherkin
Feature: MCP REST Endpoints

  Scenario: Member creates Streamable HTTP server
    Given a team member authenticated for workspace W
    When POST /api/workspaces/W/mcp-servers with {name="azuredevops", transport="streamable_http", url="https://mcp.azure.com/", headers={"Authorization":"Bearer pat"}}
    Then 201
    And response body has {name, transport, url, is_active=true, created_at} but NO headers field

  Scenario: Member creates SSE server (default-transport variant)
    Given a team member authenticated for workspace W
    When POST /api/workspaces/W/mcp-servers with body omitting transport
    Then 201 with transport="streamable_http" (default)

  Scenario: Non-member cannot create
    Given user U is not a member of workspace W's team
    When POST /api/workspaces/W/mcp-servers
    Then 404 (assert_team_member behaviour)

  Scenario: List never leaks decrypted headers
    Given workspace W has 2 MCP servers with auth headers stored
    When GET /api/workspaces/W/mcp-servers
    Then 200
    And no element of the response array contains a "headers" or "headers_encrypted" field

  Scenario: Patch toggles is_active
    Given an active MCP server "github"
    When PATCH /api/workspaces/W/mcp-servers/github with {is_active: false}
    Then 200 with is_active=false

  Scenario: Patch with headers={} clears headers
    Given an MCP server with stored auth header
    When PATCH .../github with {headers: {}}
    Then 200
    And subsequent GET shows the server with no auth header reachable (verify via service-layer query in test, since REST never returns headers)

  Scenario: Delete returns 204
    When DELETE /api/workspaces/W/mcp-servers/github
    Then 204
    And subsequent GET list omits "github"

  Scenario: Test connection — handshake + tools success
    Given an MCP server "x" whose endpoint returns 3 tools (stubbed via httpx_mock)
    When POST /api/workspaces/W/mcp-servers/x/test
    Then 200 with body {ok: true, tool_count: 3, error: null}

  Scenario: Test connection — zero tools returned
    Given an MCP server "x" whose endpoint returns 0 tools
    When POST .../test
    Then 200 with body {ok: false, tool_count: 0, error: "no tools returned"}

  Scenario: Test connection — integration smoke with in-process SSE responder
    Given a minimal in-process SSE responder fixture announcing 1 tool
    When POST .../test
    Then 200 with body {ok: true, tool_count: 1, error: null}

  Scenario: Reserved name returns 400
    When POST .../mcp-servers with {name: "search", ...}
    Then 400 with detail containing "reserved"

  Scenario: HTTP URL returns 400
    When POST .../mcp-servers with {url: "http://insecure.example/"}
    Then 400 with detail containing "https"
```

### 2.2 Verification Steps (Manual)
- [ ] `pytest backend/tests/api/test_mcp_servers_routes.py -v` — all 10+ tests pass.
- [ ] `curl -X POST http://localhost:8000/api/workspaces/<id>/mcp-servers/<name>/test -H "Authorization: Bearer <jwt>"` against a real running MCP server returns the expected JSON. **Recommended target**: GitHub MCP (verified V1 smoke target — see STORY-012-04 §5.6). Expected body: `{"ok": true, "tool_count": 41, "error": null}`.

## 3. The Implementation Guide

### 3.1 Context & Files

| Item | Value |
|---|---|
| Primary New Files | `backend/app/api/routes/mcp_servers.py`, `backend/app/api/schemas/mcp_server.py` (Pydantic request/response models) |
| Modified Files | `backend/app/main.py` (router include + `TEEMO_TABLES` entry) |
| Test File | `backend/tests/api/test_mcp_servers_routes.py` (NEW) |

### 3.2 Technical Logic

**Auth pattern:** import `assert_team_member` from `app.api.routes.workspaces`. Resolve the team_id from the workspace_id at the top of each handler (existing helper in `workspaces.py`).

**Test fixture strategy (Q7 = C):**
- Unit tests use `respx` or `httpx_mock` to intercept the SSE/Streamable HTTP requests Pydantic AI's MCP clients make. Stubbed responses return canned `tools/list` payloads. Fast, no I/O, runs in CI.
- ONE integration smoke test spins a minimal `FastAPI` sub-app responding with the SSE handshake protocol, mounted on a random local port via `httpx.ASGITransport` or `uvicorn`'s programmatic server. This catches real-protocol regressions that a stub would miss. Pattern reference: existing Slack signing-test fixture in `tests/api/test_slack_events.py`.

**Public response shape:** define `McpServerPublic` in `schemas/mcp_server.py`:

```python
class McpServerPublic(BaseModel):
    name: str
    transport: Literal["sse", "streamable_http"]
    url: str
    is_active: bool
    created_at: datetime
    # NOTE: headers intentionally absent.
```

### 3.3 API Contract

| Endpoint | Method | Auth | Request Shape | Response Shape |
|---|---|---|---|---|
| `/api/workspaces/{wid}/mcp-servers` | POST | Bearer JWT + team-member | `{name, transport='streamable_http', url, headers?}` | 201 `McpServerPublic` |
| `/api/workspaces/{wid}/mcp-servers` | GET | Bearer JWT + team-member | — | 200 `list[McpServerPublic]` |
| `/api/workspaces/{wid}/mcp-servers/{name}` | PATCH | Bearer JWT + team-member | `{transport?, url?, headers?, is_active?}` | 200 `McpServerPublic` |
| `/api/workspaces/{wid}/mcp-servers/{name}` | DELETE | Bearer JWT + team-member | — | 204 (empty) |
| `/api/workspaces/{wid}/mcp-servers/{name}/test` | POST | Bearer JWT + team-member | — | 200 `{ok, tool_count, error}` |

## 4. Quality Gates

### 4.1 Minimum Test Expectations

| Test Type | Minimum Count | Notes |
|---|---|---|
| Endpoint tests (`test_mcp_servers_routes.py`) | 10 | Auth matrix (member/non-member), CRUD happy paths × both transports, validation rejection, list-never-leaks-headers, patch-clears-headers, delete-removes, test-success, test-zero-tools, test-timeout. |
| Integration smoke | 1 | In-process SSE responder fixture; full handshake + tools/list round trip. |

### 4.2 Definition of Done (The Gate)
- [ ] All §4.1 tests pass locally.
- [ ] All Gherkin scenarios from §2.1 covered.
- [ ] Manual `curl` against a real MCP server returns the expected JSON.
- [ ] OpenAPI / `docs` page lists all 5 endpoints.
- [ ] Architect/Developer self-review.

---

## ClearGate Ambiguity Gate (🟢 / 🟡 / 🔴)
**Current Status: 🟢 Low.** Endpoint shapes, error codes, auth model, response shapes, test fixture strategy all specified. No TBDs.
