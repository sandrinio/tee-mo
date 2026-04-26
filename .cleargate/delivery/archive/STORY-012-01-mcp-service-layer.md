---
story_id: "STORY-012-01-mcp-service-layer"
parent_epic_ref: "EPIC-012"
status: "Shipped"
ambiguity: "🟢 Low"
context_source: "PROPOSAL-001-teemo-platform.md"
actor: "Backend Engineer"
complexity_label: "L1"
created_at: "2026-04-26T00:00:00Z"
updated_at: "2026-04-26T00:00:00Z"
created_at_version: "cleargate-sprint-17-draft"
updated_at_version: "cleargate-sprint-17-draft"
server_pushed_at_version: null
draft_tokens: { input: null, output: null, cache_read: null, cache_creation: null, model: null, sessions: [] }
cached_gate_result: { pass: null, failing_criteria: [], last_gate_check: null }
---

# STORY-012-01: MCP Service Layer
**Complexity:** L1 — single backend slice (migration + service module + shared URL-safety lift). Foundation for 012-02/03/04.

## 1. The Spec (The Contract)

### 1.1 User Story
As a backend engineer, I want a `mcp_service` CRUD layer plus the `teemo_mcp_servers` schema, so that the REST endpoints (012-02), the agent factory (012-03), and the dashboard (012-04) can all manage MCP server registrations without duplicating validation, encryption, or transport-dispatch logic.

### 1.2 Detailed Requirements
1. **Migration `014_teemo_mcp_servers.sql`**: idempotent (`CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`), ends with `RAISE NOTICE` row count. Schema per EPIC-012 §4.3:
   - `id` UUID PK default `gen_random_uuid()`.
   - `workspace_id` UUID NOT NULL, FK to `teemo_workspaces(id)` `ON DELETE CASCADE`.
   - `name` TEXT NOT NULL.
   - `transport` TEXT NOT NULL `CHECK (transport IN ('sse', 'streamable_http'))`.
   - `url` TEXT NOT NULL.
   - `headers_encrypted` JSONB NOT NULL default `'{}'::jsonb`.
   - `is_active` BOOLEAN NOT NULL default `true`.
   - `created_at` TIMESTAMPTZ NOT NULL default `now()`.
   - `UNIQUE (workspace_id, name)` constraint.
   - Index on `workspace_id` for the list query.
2. **New module `app/core/url_safety.py`** (Q8 resolution): exports `is_safe_url(url: str) -> tuple[bool, str | None]`. Lifts logic from existing private `_is_safe_url()` in `app/agents/agent.py`. Validates: scheme is `https`, host resolves to a non-private/non-loopback/non-link-local IPv4 or IPv6 address. Returns `(False, reason)` on failure.
3. **Refactor `app/agents/agent.py`**: `_is_safe_url()` deleted; existing `http_request` tool now calls `from app.core.url_safety import is_safe_url`. Zero behavioural change for that tool.
4. **New module `app/services/mcp_service.py`** with these public functions, all `async`:
   - `list_mcp_servers(workspace_id: UUID, *, active_only: bool = False) -> list[McpServerRecord]` — returns dataclasses with decrypted `headers` populated (used by 012-03 agent factory). REST endpoints in 012-02 use a separate accessor that omits headers.
   - `get_mcp_server(workspace_id: UUID, name: str) -> McpServerRecord | None`.
   - `create_mcp_server(workspace_id, *, name, transport, url, headers: dict[str, str] | None) -> McpServerRecord` — validates per §1.2.5; encrypts each header value; inserts row.
   - `update_mcp_server(workspace_id, name, *, transport=None, url=None, headers=None, is_active=None) -> McpServerRecord` — partial update with the same validation matrix as create. `headers=None` means "leave existing"; `headers={}` means "clear all".
   - `delete_mcp_server(workspace_id, name) -> bool`.
   - `test_connection(workspace_id, name, *, timeout_seconds: float = 10.0) -> McpTestResult` — instantiates the right Pydantic AI class per transport, runs `__aenter__` (handshake), invokes `tools/list`, asserts `len(tools) >= 1`, calls `__aexit__`. Returns `McpTestResult(ok: bool, tool_count: int, error: str | None)`.
5. **Validation rules** (raised as `ValidationError` subclass, not generic `ValueError`):
   - `name`: regex `^[a-z0-9_-]{2,32}$`. Reject names in deny-list `{"search", "skill", "skills", "knowledge", "automation", "automations", "http_request"}` (Q9).
   - `transport`: must be `"sse"` or `"streamable_http"`. Default in higher layers (REST/agent tool) is `"streamable_http"`.
   - `url`: must start `https://`; `is_safe_url(url)` must return `(True, None)`.
   - `headers`: keys are non-empty strings; values are non-empty strings. Encrypted via `app.core.encryption.encrypt(value)` before storage.
6. **Transport dispatcher** (helper inside `mcp_service`): `def _build_mcp_client(record: McpServerRecord) -> MCPServer` returns either `MCPServerSSE(record.url, headers=...)` or `MCPServerStreamableHTTP(record.url, headers=...)` based on `record.transport`. Used by both `list_mcp_servers` (when 012-03 agent factory wants live clients) and `test_connection`.

### 1.3 Out of Scope
- REST endpoints (012-02).
- Agent factory wiring (012-03).
- Frontend (012-04).
- Auto-discovery of public MCP servers / marketplace (epic §2 OUT-OF-SCOPE).
- Per-tool ACL on the registered server (epic §2 OUT-OF-SCOPE).
- Configurable timeout env var (Q2 chose 10s flat).

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria (Gherkin)

```gherkin
Feature: MCP Service Layer

  Scenario: Create with valid SSE config
    Given a workspace exists
    When create_mcp_server(name="github", transport="sse", url="https://mcp.example.com/sse", headers={"Authorization": "Bearer ghp_abc"})
    Then a row is inserted with transport="sse"
    And headers_encrypted contains an encrypted blob, not the plaintext token
    And get_mcp_server returns a record whose decrypted headers match the input

  Scenario: Create with valid Streamable HTTP config
    Given a workspace exists
    When create_mcp_server(name="azuredevops", transport="streamable_http", url="https://mcp.azure.com/", headers={"Authorization": "Bearer pat_xxx"})
    Then a row is inserted with transport="streamable_http"

  Scenario: Reject reserved name
    When create_mcp_server(name="search", ...)
    Then raises ValidationError with message containing "reserved"

  Scenario: Reject invalid slug
    When create_mcp_server(name="My GitHub!", ...)
    Then raises ValidationError with message containing "name"

  Scenario: Reject HTTP URL
    When create_mcp_server(url="http://insecure.example/sse", ...)
    Then raises ValidationError with message containing "https"

  Scenario: Reject private-IP URL
    When create_mcp_server(url="https://10.0.0.1/sse", ...)
    Then raises ValidationError with message containing "unsafe"

  Scenario: Test connection happy path
    Given a registered MCP server whose endpoint returns ≥1 tool on tools/list
    When test_connection(workspace_id, name)
    Then returns McpTestResult(ok=True, tool_count>=1, error=None)

  Scenario: Test connection — endpoint returns zero tools
    Given a registered MCP server whose tools/list returns []
    When test_connection(workspace_id, name)
    Then returns McpTestResult(ok=False, tool_count=0, error="no tools returned")

  Scenario: Test connection — handshake timeout
    Given a registered MCP server at an unreachable URL
    When test_connection(workspace_id, name, timeout_seconds=10)
    Then returns McpTestResult(ok=False, tool_count=0, error containing "timeout")

  Scenario: Lift _is_safe_url preserves http_request behaviour
    Given the existing http_request agent tool
    When called with a private-IP URL
    Then it rejects with the same error message as before the lift
```

### 2.2 Verification Steps (Manual)
- [ ] Apply `014_teemo_mcp_servers.sql` to local Supabase via SQL editor; `RAISE NOTICE` shows `0 rows`.
- [ ] Run `pytest backend/tests/services/test_mcp_service.py -v` — all 12+ tests pass.
- [ ] Run full backend test suite — no regressions in `http_request` tool tests after the URL-safety lift.

## 3. The Implementation Guide

### 3.1 Context & Files

| Item | Value |
|---|---|
| Primary New Files | `database/migrations/014_teemo_mcp_servers.sql`, `backend/app/services/mcp_service.py`, `backend/app/core/url_safety.py` |
| Modified Files | `backend/app/agents/agent.py` (delete `_is_safe_url`, re-import), `backend/app/main.py` (`TEEMO_TABLES` add `teemo_mcp_servers`), `database/migrations/README.md` (add row 014) |
| Test File | `backend/tests/services/test_mcp_service.py` (NEW), `backend/tests/core/test_url_safety.py` (NEW) |

### 3.2 Technical Logic

**Encryption:** reuse `app.core.encryption.encrypt()` / `decrypt()` exactly as `byok_keys` does. Store one encrypted blob per header value (not the whole dict serialized) so individual values can be rotated later without re-encrypting all. JSONB shape: `{"Authorization": "<base64-ciphertext>", "X-API-Key": "<base64-ciphertext>"}`.

**Transport dispatcher:**

```python
def _build_mcp_client(record: McpServerRecord) -> MCPServer:
    headers = {k: decrypt(v) for k, v in record.headers_encrypted.items()}
    if record.transport == "sse":
        return MCPServerSSE(url=record.url, headers=headers)
    elif record.transport == "streamable_http":
        return MCPServerStreamableHTTP(url=record.url, headers=headers)
    raise ValueError(f"Unknown transport: {record.transport}")
```

**Test-connection:** uses `asyncio.wait_for(..., timeout=timeout_seconds)` around `async with client:` block, then calls `await client.list_tools()` (or whichever Pydantic AI 1.79 method enumerates tools — verify via `dir(MCPServerSSE())` during implementation; one flashcard's worth of risk).

### 3.3 API Contract

Internal Python module — no HTTP surface. Public exports:

```python
@dataclass
class McpServerRecord:
    id: UUID
    workspace_id: UUID
    name: str
    transport: Literal["sse", "streamable_http"]
    url: str
    headers_encrypted: dict[str, str]   # raw ciphertext blobs
    is_active: bool
    created_at: datetime

@dataclass
class McpTestResult:
    ok: bool
    tool_count: int
    error: str | None

class McpValidationError(ValueError): ...
```

## 4. Quality Gates

### 4.1 Minimum Test Expectations

| Test Type | Minimum Count | Notes |
|---|---|---|
| Unit tests (`test_mcp_service.py`) | 12 | CRUD happy paths (3) × both transports (×2) = 6, plus 6 validation paths (slug regex, reserved name, http://, private-IP, header encryption round-trip, test-connection happy/sad/timeout). |
| Unit tests (`test_url_safety.py`) | 4 | https/http/private-IP/loopback. |
| Regression check | 1 | Existing `http_request` tool tests still pass after `_is_safe_url` lift. |

### 4.2 Definition of Done (The Gate)
- [ ] All §4.1 tests pass locally with `pytest backend/tests/services/test_mcp_service.py backend/tests/core/test_url_safety.py`.
- [ ] All Gherkin scenarios from §2.1 covered by a named test.
- [ ] `_is_safe_url` is no longer defined in `app/agents/agent.py` (grep confirms zero references); replaced by `from app.core.url_safety import is_safe_url`.
- [ ] Migration `014_*.sql` applied cleanly; rerun is idempotent.
- [ ] `app/main.py` `TEEMO_TABLES` includes `teemo_mcp_servers`.
- [ ] Architect/Developer self-review.

---

## ClearGate Ambiguity Gate (🟢 / 🟡 / 🔴)
**Current Status: 🟢 Low.** All field shapes, validation rules, transport-dispatcher logic, and test counts specified. No TBDs.
