---
story_id: "STORY-012-04-mcp-dashboard-ui"
parent_epic_ref: "EPIC-012"
status: "Shipped"
ambiguity: "🟢 Low"
context_source: "PROPOSAL-001-teemo-platform.md"
actor: "Frontend Engineer"
complexity_label: "L2"
created_at: "2026-04-26T00:00:00Z"
updated_at: "2026-04-26T00:00:00Z"
created_at_version: "cleargate-sprint-17-draft"
updated_at_version: "cleargate-sprint-17-draft"
server_pushed_at_version: null
draft_tokens: { input: null, output: null, cache_read: null, cache_creation: null, model: null, sessions: [] }
cached_gate_result: { pass: null, failing_criteria: [], last_gate_check: null }
---

# STORY-012-04: MCP Dashboard UI
**Complexity:** L2 — inline section in `WorkspaceCard` + add-modal + 5 TanStack Query hooks + typed API wrappers.

## 1. The Spec (The Contract)

### 1.1 User Story
As a workspace admin, I want to see, add, test, toggle, and delete MCP servers from the workspace card without leaving the dashboard, so that I can manage integrations alongside BYOK keys and channels using the same UI patterns I already know.

### 1.2 Detailed Requirements
1. **`useMcpServers.ts` hook module** — exports 5 TanStack Query hooks:
   - `useMcpServersQuery(workspaceId)` — `GET /api/workspaces/{id}/mcp-servers`. Query key: `["mcp-servers", workspaceId]`.
   - `useCreateMcpServerMutation(workspaceId)` — `POST` create. On success: `queryClient.invalidateQueries({queryKey: ["mcp-servers", workspaceId]})`.
   - `useUpdateMcpServerMutation(workspaceId)` — `PATCH /:name`. Same invalidation.
   - `useDeleteMcpServerMutation(workspaceId)` — `DELETE /:name`. Same invalidation.
   - `useTestMcpServerMutation(workspaceId)` — `POST /:name/test`. Does NOT invalidate (test-connection is read-only side effect on the dashboard).
2. **Typed API wrappers in `frontend/src/lib/api.ts`** — 5 functions matching the REST contract from 012-02. New TypeScript types:

   ```ts
   export type McpTransport = 'sse' | 'streamable_http';
   export interface McpServer {
     name: string;
     transport: McpTransport;
     url: string;
     is_active: boolean;
     created_at: string;
   }
   export interface McpTestResult {
     ok: boolean;
     tool_count: number;
     error: string | null;
   }
   ```

3. **`WorkspaceCard.tsx` modification**: insert a new `IntegrationsSection` JSX block beneath the existing `KeySection`. Section header "Integrations" with the same chrome (heading + helper text + "Add Integration" button on the right). When the query has zero servers, show empty-state copy: "No integrations connected yet. Add one to give the agent extra tools.". When ≥1 server, render a `<ul>` of mini-cards.
4. **MCP mini-card** — one row per server with these elements left-to-right:
   - Server name (bold).
   - Transport badge — small pill, "SSE" or "Streamable HTTP" (matching Tailwind tokens used elsewhere; see KeySection for the badge pattern).
   - URL (monospace, truncated mid-string with `…` for long URLs).
   - Status badge — "Active" green / "Disabled" gray / "Untested" amber (computed from is_active + last test result if available; default to "Untested" until the user clicks Test).
   - "Test" button — calls `useTestMcpServerMutation`. While loading, shows spinner. On success, badge flips to "Active ({tool_count} tools)" green. On failure, badge flips to red with the error tooltip.
   - "Toggle" switch — calls `useUpdateMcpServerMutation` with `{is_active: !current}`.
   - "Delete" button — opens a confirm dialog ("Disconnect '{name}'?"). On confirm, calls `useDeleteMcpServerMutation`.
5. **`AddMcpServerModal.tsx`** — new file. Form-driven JSON builder; all inputs are first-class form fields, never freeform JSON edits at submit time. Inputs:
   - **Name** — text input, slug regex hint `^[a-z0-9_-]{2,32}$` shown as helper text. Client-side validation (rejected with inline error before submit).
   - **Transport** — radio group, default `streamable_http`. Labels: "Streamable HTTP (recommended)" and "SSE (legacy)".
   - **URL** — text input, must start `https://`.
   - **Headers** — **dynamic key-value editor** (replaces the single auth_header field). Renders a table of `[ key ] [ value ] [ × ]` rows below a "+ Add header" button. Default first row is pre-populated with key=`Authorization` and value placeholder `Bearer your-token` (covers the 80% case). User can:
     - Edit any key (text input) or value (`type="password"` masked input).
     - Click `×` on a row to remove it (zero rows is allowed — some MCP servers don't need auth).
     - Click `+ Add header` to append a blank row.
     - Header order does not matter to MCP servers; no reorder UI.
     - Helper text: "Stored encrypted server-side, one value at a time. Each MCP server's README lists the required headers."
   - **Submit** — disabled while name/URL invalid (Headers can be empty). On submit, builds a `{name, transport, url, headers: {key1: value1, ...}}` object from the form and calls `useCreateMcpServerMutation`. On success, closes modal + invalidates the list query. On 400 from server, surfaces `detail` inline.
6. **"Paste from another client" import affordance** (collapsible panel inside the modal, default collapsed):
   - Heading: `▼ Paste from another client (advanced)`. Body: `<textarea>` placeholder "Paste an entry from claude_desktop_config.json, .vscode/mcp.json, or any MCP-compatible JSON config." + `[ Import ]` button.
   - Clicking Import calls `parseMcpJson(textarea.value)` from the new lib (§3.2). On success, the form fields above are populated (Name from wrapper key if present, Transport, URL, and one Headers row per key in the parsed `headers` dict). On failure, inline error below the textarea.
   - **The textarea is a one-shot import helper, never the source of truth for submit.** After Import, users can freely edit/add/remove rows. Submit always reads the form, not the textarea.
   - Accepted JSON shapes (parser logic is in `mcpJsonImport.ts`):
     - **Shape A** — Claude Desktop / Cursor `mcpServers` wrapper (`{"mcpServers": {"<name>": {url, transport, headers}}}`). If multiple servers, import the first and surface a warning: "Imported '<name>'. Paste again to import the others."
     - **Shape B** — VS Code `.vscode/mcp.json` `servers` wrapper using `type` field instead of `transport`. Map `type: "http"` → `streamable_http`, `type: "sse"` → `sse`.
     - **Shape C** — Raw single-server entry without wrapper (`{url, transport, headers}`).
     - **Shape D** — `{<name>: {url, transport, headers}}` map without wrapper.
   - Normalization: `transport: "streamable-http"` (dash) → `streamable_http` (underscore). Missing transport defaults to `streamable_http`. Wrapper-key `<name>` pre-fills the Name input.
   - Header values containing `${env:...}` or `${input:...}` placeholders are imported with the value field cleared and inline hint "Replace placeholder with the actual token".
   - Rejected with friendly errors: invalid JSON ("Couldn't parse JSON: <parser error>"); stdio config (presence of `command` or `args` keys) → "Tee-Mo only supports HTTP-based MCP servers (SSE / Streamable HTTP). The config you pasted is for a local stdio server, which we don't support for security reasons."; missing `url` → "JSON is missing a `url` field".
7. **No new route, no new page** — purely inline in the existing workspace card.

### 1.3 Out of Scope
- Backend (012-01, 012-02, 012-03).
- Per-tool ACL UI.
- Marketplace/discovery of public MCP servers (epic §2 OUT-OF-SCOPE).
- Mobile redesign (the existing `WorkspaceCard` is desktop-first; mobile fit follows whatever EPIC-025 set up — no new responsive work here).
- Server-Sent-Events status polling (test-connection is on-demand only).
- **OAuth-flow MCP servers** (e.g. Azure DevOps Remote at `mcp.dev.azure.com`). Static-token / Bearer-header servers only in V1. OAuth is its own follow-up epic (EPIC-026 stub).
- **Per-row reorder of headers**. Header order doesn't affect MCP servers.
- **Bulk-import multiple servers in one paste**. If a `mcpServers` wrapper has multiple entries, we import the first and warn the user to paste again for the others.
- **Editing the JSON textarea after Import**. The textarea is a one-shot helper — once Import populates the form, the textarea can be cleared/ignored. Submit reads only the form.

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria (Gherkin)

```gherkin
Feature: MCP Dashboard UI

  Scenario: Empty state
    Given workspace W has no MCP servers
    When the user opens the workspace card
    Then the "Integrations" section shows the empty-state copy
    And an "Add Integration" button is visible

  Scenario: Add Streamable HTTP server happy path with Authorization header
    Given the Add Integration modal is open
    When the user enters name="github", URL="https://api.githubcopilot.com/mcp/", and a single Headers row {Authorization: "Bearer ghp_xxx"}, then submits
    Then a POST is fired to /api/workspaces/.../mcp-servers with body {name, transport: "streamable_http", url, headers: {Authorization: "Bearer ghp_xxx"}}
    And on 201, the modal closes
    And the list re-renders with the new server card

  Scenario: Add server with multiple headers
    Given the modal is open
    When the user adds a second Headers row {X-API-Key: "k_abc"} alongside the default Authorization row, fills name + URL + Auth, and submits
    Then the POST body's headers dict contains both keys

  Scenario: Add server with zero headers
    Given the modal is open
    When the user clicks × on the default Authorization row to remove it, fills name + URL, and submits
    Then the POST body's headers dict is {}

  Scenario: Add SSE server (transport selected)
    Given the modal is open
    When the user picks "SSE (legacy)" and submits with valid name + URL
    Then the POST body contains transport="sse"

  Scenario: Slug regex client-side rejection
    Given the modal is open
    When the user enters name="My GitHub!"
    Then the Submit button is disabled
    And inline helper text shows the regex hint

  Scenario: Import from claude_desktop_config.json wrapper
    Given the modal is open and the Paste-from-another-client panel is expanded
    When the user pastes {"mcpServers":{"github":{"url":"https://api.githubcopilot.com/mcp/","transport":"streamable-http","headers":{"Authorization":"Bearer ghp_xxx"}}}} and clicks Import
    Then the Name field becomes "github"
    And the Transport radio shows "Streamable HTTP"
    And the URL field becomes "https://api.githubcopilot.com/mcp/"
    And the Headers table shows one row {Authorization: "Bearer ghp_xxx"}

  Scenario: Import from VS Code mcp.json wrapper
    Given the modal is open and the panel is expanded
    When the user pastes {"servers":{"ado":{"url":"https://mcp.dev.azure.com/myorg","type":"http"}}} and clicks Import
    Then the Transport radio shows "Streamable HTTP" (type:"http" mapped to streamable_http)
    And the Name field becomes "ado"

  Scenario: Import rejects stdio config
    When the user pastes {"command":"npx","args":["-y","azure-devops-mcp"]} and clicks Import
    Then an inline error reads "Tee-Mo only supports HTTP-based MCP servers (SSE / Streamable HTTP). The config you pasted is for a local stdio server, which we don't support for security reasons."
    And the form fields are unchanged

  Scenario: Import strips placeholder header values
    When the user pastes a config whose headers contain {"Authorization": "Bearer ${env:GITHUB_TOKEN}"} and clicks Import
    Then the Headers table shows the row with key="Authorization" but value blank
    And inline helper hint reads "Replace placeholder with the actual token"

  Scenario: Edit imported headers before submit
    Given the user has imported a JSON config that populated 2 headers
    When the user adds a third row, removes the first, and edits the second's value
    And clicks Submit
    Then the POST body's headers dict reflects exactly the form's current state, ignoring whatever was originally imported

  Scenario: Test button success
    Given a connected MCP server card
    When the user clicks "Test"
    Then the badge flips to "Active (N tools)" green where N matches the response.tool_count

  Scenario: Test button failure
    Given a connected MCP server whose test endpoint returns ok=false
    When the user clicks "Test"
    Then the badge flips to red
    And hovering the badge shows the error string

  Scenario: Toggle disable
    Given an active MCP server card
    When the user toggles it off
    Then a PATCH fires with is_active=false
    And the card's status badge flips to "Disabled" gray

  Scenario: Delete confirm
    When the user clicks Delete on a card
    Then a confirm dialog appears
    When the user confirms
    Then a DELETE fires
    And the card disappears
```

### 2.2 Verification Steps (Manual)
- [ ] `npm test -- useMcpServers AddMcpServerModal IntegrationsSection` — all 5+ Vitest tests pass.
- [ ] `npm run typecheck` clean.
- [ ] In a real dev workspace, walk the entire happy path: add Azure DevOps Remote (Streamable HTTP) via the modal → Test → Toggle → Delete. All four mutate the right endpoint and the UI re-renders correctly.
- [ ] Mobile viewport (375px) — section is scrollable, no overflow horizontally.

## 3. The Implementation Guide

### 3.1 Context & Files

| Item | Value |
|---|---|
| Primary New Files | `frontend/src/hooks/useMcpServers.ts`, `frontend/src/components/dashboard/AddMcpServerModal.tsx`, `frontend/src/components/dashboard/IntegrationsSection.tsx`, `frontend/src/components/dashboard/HeadersEditor.tsx` (extracted dynamic key-value table), `frontend/src/lib/mcpJsonImport.ts` (pure JSON parser) |
| Modified Files | `frontend/src/components/dashboard/WorkspaceCard.tsx` (mount `IntegrationsSection`), `frontend/src/lib/api.ts` (5 typed wrappers + 2 types) |
| Test Files | `frontend/src/hooks/__tests__/useMcpServers.test.ts` (NEW), `frontend/src/components/dashboard/__tests__/AddMcpServerModal.test.tsx` (NEW), `frontend/src/components/dashboard/__tests__/IntegrationsSection.test.tsx` (NEW), `frontend/src/components/dashboard/__tests__/HeadersEditor.test.tsx` (NEW), `frontend/src/lib/__tests__/mcpJsonImport.test.ts` (NEW) |

### 3.2 Technical Logic

**Reference patterns (read these before coding):**
- `frontend/src/components/dashboard/KeySection.tsx` — same chrome, same hook pattern. Copy structure, swap MCP-specific bits.
- `frontend/src/hooks/useKeys.ts` — TanStack Query hook shape, error handling, `queryClient.invalidateQueries` shape.
- `frontend/src/components/dashboard/AddKeyModal.tsx` — modal shell, validation pattern, password-type input for the secret.

**Status badge state machine** (kept in `IntegrationsSection` local state, NOT in the server response — V1 only):

```ts
type CardStatus = 'untested' | 'active' | 'disabled' | 'failed';
// untested: server.is_active && no recent test result
// active: server.is_active && last test ok=true
// disabled: !server.is_active
// failed: server.is_active && last test ok=false
```

`useTestMcpServerMutation`'s `onSuccess` updates the local state map keyed by `server.name`.

**`HeadersEditor` component contract:**

```ts
interface HeadersEditorProps {
  rows: Array<{ key: string; value: string }>;          // controlled state
  onChange: (next: Array<{ key: string; value: string }>) => void;
  valueInputType?: 'password' | 'text';                  // default 'password'
}
```

Renders a table of `[ key ] [ value ] [ × ]` rows + a `+ Add header` button. Empty rows (key === '') are filtered before submit by the parent modal. Component is intentionally dumb — no validation, no persistence — so it's reusable for any future "list of headers" need (BYOK keys with custom Bearer formats, webhook signers, etc.).

**`mcpJsonImport.ts` contract** (pure function, fully unit-testable, no React imports):

```ts
export interface ParsedMcpServer {
  name: string | null;                        // populated only if wrapper key present
  transport: 'sse' | 'streamable_http';
  url: string;
  headers: Array<{ key: string; value: string; placeholder: boolean }>;
  warning: string | null;                     // e.g. "Imported 'github'. Paste again to import the others."
}

export type ParseResult =
  | { ok: true; server: ParsedMcpServer }
  | { ok: false; error: string };

export function parseMcpJson(input: string): ParseResult { /* ~50 LOC */ }
```

Parser logic (in order):
1. `JSON.parse(input)` — bail with friendly error on syntax error.
2. Detect shape: presence of `mcpServers` key → Shape A; `servers` key → Shape B (VS Code); `url` key at root → Shape C; otherwise treat as Shape D (`{name → entry}` map).
3. For wrapper shapes, pick the first entry by insertion order; emit a warning if there were multiple.
4. Reject if entry contains `command` or `args` keys (stdio).
5. Reject if entry is missing `url`.
6. Map `transport` / `type` per the table above. Default to `streamable_http` if missing.
7. Map `headers` (object) → array of `{key, value, placeholder}`. `placeholder=true` if value matches `/^\$\{(env|input):/`, in which case the value is cleared.
8. Return `{ok: true, server: {...}}`.

Modal calls `parseMcpJson` on Import click; on success, sets the form's controlled state from the result; on failure, sets an inline error string under the textarea.

### 3.3 API Contract (consumer side)

Mirrors 012-02's REST contract exactly. No new server-side surface.

## 4. Quality Gates

### 4.1 Minimum Test Expectations

| Test Type | Minimum Count | Notes |
|---|---|---|
| Hook tests (`useMcpServers.test.ts`) | 2 | Query happy path; create-mutation invalidates list. Use MSW or fetch-mock. |
| Modal tests (`AddMcpServerModal.test.tsx`) | 4 | Slug regex client-side rejection; submit posts the right body shape with single header; submit posts with multiple headers; submit posts with zero headers (empty `{}`). |
| Section tests (`IntegrationsSection.test.tsx`) | 3 | Empty state; renders cards; test button flips badge; delete confirms before mutating. |
| HeadersEditor tests (`HeadersEditor.test.tsx`) | 3 | Add row appends; remove row deletes; onChange fires with the updated array. |
| JSON parser tests (`mcpJsonImport.test.ts`) | 6 | Shape A (Claude Desktop wrapper, single + multi-server warning); Shape B (VS Code `type:"http"` → `streamable_http`); Shape C (raw); stdio rejection; placeholder header value detection (`${env:...}` → cleared + flagged); invalid JSON returns `ok:false` with parser error. |

### 4.2 Definition of Done (The Gate)
- [ ] All §4.1 tests pass locally.
- [ ] All Gherkin scenarios from §2.1 covered.
- [ ] `npm run typecheck` clean.
- [ ] Manual happy-path walkthrough on a real dev workspace.
- [ ] Mobile viewport (375px) sanity check.
- [ ] Architect/Developer self-review.

---

## ClearGate Ambiguity Gate (🟢 / 🟡 / 🔴)
**Current Status: 🟢 Low.** Component shapes, hook signatures, badge state machine, modal validation, dynamic-headers contract, JSON-import parser logic, and file paths all specified. References existing patterns (`KeySection`, `AddKeyModal`, `useKeys`) so there's a known anchor for every visual decision. JSON parser is a pure function, fully unit-testable in isolation.

---

## 5. Manual Smoke Testing Notes (Azure DevOps probe — captured 2026-04-26)

Owner provided a real Azure DevOps PAT in `.env` as `AZADO_PAT_FOR_TESTING_ONLY` (org=`dtstac`, project=`K1DE`, default team=`K1DE Team`) so we could validate the auth-model claims before sprint kickoff. Findings — both as ground truth for the V1 smoke target picker and as a reference runbook for the QA pass:

### 5.1 What the PAT can do (verified)

| Probe | Endpoint | Result |
|---|---|---|
| List projects | `GET https://dev.azure.com/dtstac/_apis/projects?api-version=7.1` with `Authorization: Basic <base64(":PAT")>` | **200** — returns 2 projects incl. `K1DE` |
| List teams | `GET .../{org}/_apis/projects/K1DE/teams?api-version=7.1` | **200** — 9 teams (incl. default `K1DE Team`) |
| List iterations | `GET .../{org}/{proj}/{team}/_apis/work/teamsettings/iterations?api-version=7.1` | **200** — 206 historical+current+future iterations |
| Find current iteration | same endpoint with `&$timeframe=current` | **200** — `Sprint 216` (2026-04-22 → 2026-05-05) |
| List work items in current iteration | `GET .../{org}/{proj}/{team}/_apis/work/teamsettings/iterations/{id}/workitems?api-version=7.1` | **200** — 156 work item references |
| Batch fetch work items | `GET .../{org}/{proj}/_apis/wit/workitems?ids={comma-sep}&fields=...&api-version=7.1` | **200** — full title/state/assignee per item |

**Conclusion:** the PAT is valid and scoped to read work items, projects, iterations. Sprint-summary use case via `wit_get_work_items_for_iteration` would absolutely work IF we had a PAT-accepting AzDO MCP server endpoint to point at.

### 5.2 What the PAT CANNOT do (verified)

| Probe | Endpoint | Result |
|---|---|---|
| Remote AzDO MCP — Bearer PAT | `POST https://mcp.dev.azure.com/dtstac` with `Authorization: Bearer ${PAT}` and an `initialize` JSON-RPC body | **401** |
| Remote AzDO MCP — Basic PAT | same endpoint, `Authorization: Basic <base64(":PAT")>` | **401** |

**Conclusion:** Microsoft's hosted Remote MCP at `mcp.dev.azure.com/{org}` is genuinely Entra-ID-OAuth-only — confirmed empirically. Validates Q11 / EPIC-026 plan: a static-token MCP integration cannot reach the Azure DevOps Remote MCP today. Adding OAuth is a separate epic.

### 5.3 What this means for the V1 smoke target

**Drop Azure DevOps Remote as the V1 smoke target.** Two viable paths for the manual smoke test in STORY-012-04 §2.2:

- **Option A (recommended): GitHub MCP.** `POST` to `https://api.githubcopilot.com/mcp/` with a GitHub PAT in `Authorization: Bearer …`. Streamable HTTP. Real public Microsoft-supported endpoint. Exercises identical Tee-Mo code path.
- **Option B: Self-hosted MCP server.** Run any open-source MCP server (e.g. `Tiberriver256/mcp-server-azure-devops`, or a community "MCP-as-HTTP-shim" wrapper around AzDO REST), expose it via ngrok over HTTPS, point Tee-Mo at the ngrok URL with the AzDO PAT in headers. Works today but adds setup overhead — pick A unless you specifically need AzDO data in the demo.

### 5.4 Sample paste-import payload (for §2.1 Import scenarios)

This is the canonical Claude-Desktop-shape JSON the import textarea should accept. Useful as a fixture in `mcpJsonImport.test.ts`:

```json
{
  "mcpServers": {
    "github": {
      "url": "https://api.githubcopilot.com/mcp/",
      "transport": "streamable-http",
      "headers": {
        "Authorization": "Bearer ghp_REPLACE_WITH_REAL_TOKEN"
      }
    }
  }
}
```

After Import, the form fields should populate as: Name=`github`, Transport=`Streamable HTTP`, URL=`https://api.githubcopilot.com/mcp/`, Headers=`[{key:"Authorization", value:"Bearer ghp_REPLACE..."}]`.

### 5.5 Credential handling reminder

- The PAT lives in `.env` only as `AZADO_PAT_FOR_TESTING_ONLY`. **Never commit, log, or echo the PAT value.** When testing manually, use `set -a && source .env && set +a` then reference `${AZADO_PAT_FOR_TESTING_ONLY}` in curl/script calls.
- This PAT is for pre-sprint validation only — it has no role inside Tee-Mo's runtime. Tee-Mo's `headers_encrypted` column is the one and only persistence path for any token a real user pastes through the dashboard.
- Org/project/team names captured here (`dtstac` / `K1DE` / `K1DE Team`, current iteration `Sprint 216`) are not credentials and are safe to commit.

### 5.6 GitHub MCP — verified V1 smoke target (probed 2026-04-26)

Owner provided a GitHub classic PAT in `.env` as `GITHUB_PAT_FOR_TESTING` so we could pre-sprint-validate the Streamable HTTP transport end-to-end against a real public MCP server.

**Endpoint:** `https://api.githubcopilot.com/mcp/`
**Transport:** Streamable HTTP (per Pydantic AI's `MCPServerStreamableHTTP` class).
**Server identity:** `github-mcp-server` (`remote-3242d9e12bd9ffa96a76388614e42ce90d05f764`).
**Required header:** `Authorization: Bearer ${GITHUB_PAT}`.
**Required scopes on the PAT:** `read:user` (for the gateway auth handshake) and `repo` (for the actual tools); a GitHub Copilot subscription on the PAT-owning account is also required.

**Probe results — full happy path validated:**

| # | Probe | Endpoint / Method | Result |
|---|---|---|---|
| 1 | Whoami sanity | `GET https://api.github.com/user` | **200** — `login=sandrinio` |
| 2 | MCP `initialize` | `POST .../mcp/` with `{jsonrpc:"2.0", method:"initialize", ...}` and `Accept: application/json, text/event-stream` | **200** — SSE response, `Mcp-Session-Id` header issued, server announces `tools / prompts / resources / completions` capabilities |
| 3 | MCP `notifications/initialized` | `POST .../mcp/` with `Mcp-Session-Id` | **202** (acknowledged) |
| 4 | MCP `tools/list` | `POST .../mcp/` same session | **200** — **41 tools** registered (`add_issue_comment`, `create_pull_request`, `get_me`, `list_issues`, `search_repositories`, `create_branch`, `get_file_contents`, etc.) |
| 5 | MCP `tools/call get_me` | `POST .../mcp/` with `params:{name:"get_me", arguments:{}}` | **200** — returns the PAT-owner's GitHub user object |

**Conclusion:** the `Streamable HTTP` transport path is fully verified end-to-end. Tee-Mo's `MCPServerStreamableHTTP` wiring will work against this exact endpoint with no protocol-level surprises. Pydantic AI handles the session-id management internally — Tee-Mo only needs to hand it `(url, headers)`.

**Token-budget note (flagged for flashcard):** 41 tools × ~150–250 tokens of schema each = **~6–10k tokens of system-prompt overhead** consumed the moment GitHub MCP is connected. That's substantial for BYOK-budget-conscious workspaces. **Mitigation belongs in V2** — expose Microsoft's standard `X-MCP-Toolsets` / `X-MCP-Tools` filtering headers (already supported by the GitHub MCP gateway too, per probe 2's CORS-allow-headers) as an "Advanced" field in the modal. In V1 we accept the full surface; flag in `STORY-012-04 §1.3 Out of Scope` and surface to user as a follow-up note.

**V1 manual smoke runbook (use this in §2.2 manual verification):**

1. Open the workspace card → Add Integration.
2. In the "Paste from another client" panel, paste:
   ```json
   {
     "mcpServers": {
       "github": {
         "url": "https://api.githubcopilot.com/mcp/",
         "transport": "streamable-http",
         "headers": { "Authorization": "Bearer YOUR_GITHUB_PAT_HERE" }
       }
     }
   }
   ```
3. Click Import → form populates with name=`github`, transport=`Streamable HTTP`, URL, single Authorization header row.
4. Replace the placeholder with the actual PAT (or paste-with-real-token directly to skip step 3).
5. Click Save → 201 expected.
6. Click Test on the new card → "Active (41 tools)" green badge expected.
7. In Slack, ask "@tee-mo who am I on GitHub?" → agent should call `get_me` and return the GitHub username.
8. Toggle the card off → next message in Slack should NOT see GitHub tools.
9. Delete the card → confirm dialog → row removed from the workspace.

If steps 5–7 all succeed, sprint DoD's V1 acceptance demo is satisfied.
