# SPRINT-17 Report: EPIC-012 MCP Server Integration

**Status:** Shipped
**Window:** 2026-04-26 → 2026-04-26 (single-day clock; sprint frontmatter `start_date` = `end_date` = `2026-04-26`)
**Stories:** 4 planned / 4 shipped / 0 carried over
**Branch:** `sprint/S-17` (cut from `main` at `2bcc295`, S-16 close-out)
**Shipping commit (sprint branch HEAD):** `de92873`
**Closed:** Sprint-branch all-green; squash-merge to `main` and live-smoke against GitHub MCP both pending Gate-3 human approval at report time.

---

## For Product Management

### Sprint goal — did we hit it?

Goal: *"Allow workspace admins to connect MCP servers to their workspace via dashboard or Slack chat, so the agent automatically discovers and uses pre-built tools (e.g. GitHub, Linear, Azure DevOps) without manual `http_request` instructions. Two transports supported: classic SSE and modern Streamable HTTP."*

**Yes, on the sprint branch.** All four EPIC-012 stories shipped on `sprint/S-17`; EPIC-012 progressed `Active` → `Shipped`; the V1 acceptance demo (GitHub MCP at `https://api.githubcopilot.com/mcp/`) was already validated end-to-end during the pre-sprint validation pass (41 tools registered through `initialize` → `tools/list` → `tools/call get_me`). Two open Gate-3 items remain at report time: the live Slack-side manual smoke against a real PAT (runbook in archived `STORY-012-04 §5.6`) and the squash-merge to `main` — both await explicit human approval per the standing S-13/14/15/16 pattern. Azure DevOps Remote MCP was *deliberately* not the smoke target — Microsoft's hosted endpoint is Entra-OAuth-only (verified pre-sprint, deferred to EPIC-026).

### Headline deliverables

- **MCP server registration end-to-end (dashboard + Slack chat).** Workspace admins can now add/list/test/toggle/delete MCP servers from the workspace card or by talking to the agent in Slack. Both transports supported (`sse` and `streamable_http`), HTTPS-only, IP-blacklisted at registration, header values AES-256-GCM encrypted at rest. The agent transparently gains the connected server's tools on the next message via `AgentDeps.mcp_servers` + `AsyncExitStack` lifecycle in `slack_dispatch`. Reserved-name deny-list (`{search, skill, skills, knowledge, automation, automations, http_request}`) prevents collisions with first-party agent tools. (EPIC-012; STORY-012-01..04.)
- **Form-as-typed-JSON-builder modal with paste-import affordance.** `AddMcpServerModal` matches Claude Desktop / Cursor / VS Code mental model: dynamic key-value Headers editor + "Paste from another client" textarea that ingests Claude-Desktop / VS Code / raw / map-shaped JSON, rejects stdio configs, and strips `${env:...}` placeholders. Pure-function `mcpJsonImport.ts` (no React imports) covers the parser logic. (STORY-012-04.)
- **Shared URL-safety module.** `_is_safe_url()` lifted from `agents/agent.py` to `core.url_safety.is_safe_url`; existing `http_request` tool re-imports the public form (zero behavioural change), MCP service uses the same module — single source of truth for URL safety across the agent loop and the registration layer. (STORY-012-01, Q8 resolution.)

### Risks that materialized

From SPRINT-17.md §5 + the pre-sprint OQ resolutions:

| Risk | Outcome |
|---|---|
| Test-connection SSE handshake requires a fixture MCP server | **Fired (012-02 first pass).** The unit-test stub patched `mcp_service.test_connection` directly instead of running the real handshake; the "integration smoke" was vacuous. Fix used `httpx.ASGITransport` over a `FastMCP`-based in-process server — confirmed real handshake + `tools/list`. |
| `AsyncExitStack` not awaited on `agent.run` exception path → connection leak | Did not fire — explicit pytest scenario covers exception propagation; `__aexit__` runs once even when the agent raises mid-stream. |
| `build_agent` return-shape change breaks 17+ test unpacks | Resolved pre-flight (Q6). DI-via-`AgentDeps.mcp_servers` chosen over a 3-tuple change; signature stayed 2-tuple; 17 unpack sites untouched. |
| Adding `streamable_http` doubles transport test matrix | Did not fire — both classes inherit from `_MCPServerHTTP`, parametrized fixtures kept the matrix to ~5 extra tests. |
| User pastes auth token in Slack `add_mcp_server` call → token visible in chat history | Mitigated. Always-warn footer ("⚠️ Your auth token is encrypted server-side, but the message you sent is still in this thread — consider deleting it.") + `add_mcp_server` tool result NEVER echoes `auth_header` (Q10). Both locked by tests. |
| MCP server tools bloat system prompt past model limits | **Confirmed (~6–10k tokens for GitHub MCP's 41 tools).** V1 accepts the cost; V2 mitigation (`X-MCP-Toolsets` filter as "Advanced" modal field) flagged for follow-up. |
| Test-pollution regression on `test_header_encrypt_round_trip` | **Fired (012-03 first pass).** `mcp_service` imported `decrypt` at top-level under monkeypatched `encryption.decrypt` — the bound symbol stayed pinned to the mock for the rest of the session, breaking any later test that used real decrypt. Fix: switch `mcp_service` to attribute-lookup `_encryption.decrypt(...)` + hoist test imports. |
| Pydantic AI MCP API differs from docs / changes mid-sprint | Resolved pre-flight (Q1). `pydantic-ai==1.79.0` ships `pydantic-ai-slim[mcp,fastmcp,...]` transitively; `MCPServerSSE` + `MCPServerStreamableHTTP` import cleanly from `pydantic_ai.mcp`. No version bump mid-sprint. |
| Slug name regex collides with reserved tool names | Did not fire — deny-list enforced at create/update time; tests enumerate every entry. Maintenance-burden flashcard recorded for future first-party tool additions. |

### Cost envelope

**Unavailable — ledger gap (5th consecutive sprint).** `.cleargate/sprint-runs/SPRINT-17/token-ledger.jsonl` does not exist. ClearGate's token-ledger hook is **intentionally disabled** for this sprint per the standing convention — five consecutive sprints (S-13, S-14, S-15, S-16, S-17) without cost capture. The hook port was an open follow-up from the S-15 and S-16 reports; deliberately not pulled into S-17 to keep the single-epic sprint focused. Flagged again in §Meta.

### What's unblocked for next sprint

- **EPIC-026 MCP-OAuth.** Pre-sprint validation already confirmed Azure DevOps Remote MCP is Entra-OAuth-only. With EPIC-012 shipping the static-token path, the OAuth follow-up has a clean shape to slot into.
- **V2 system-prompt filtering (`X-MCP-Toolsets`).** Modal "Advanced" panel, server-side header-passthrough — well-scoped follow-up for any sprint.
- **Connection pooling / health monitoring.** V1 connects per-request; the AsyncExitStack lifecycle is the seam to optimize against without redesigning the integration path.
- **Token-ledger hook port.** Now overdue (5 sprints). Pulling it into S-18 as a planned story remains the right next move.
- **Pre-existing test-baseline cleanup.** Backend has 42 pre-existing failures (down from 44 — 012-03 net-reduced by 2); frontend has ~61 pre-existing Vitest failures from a long-standing JSX-transform misconfiguration nobody owns. Neither was introduced by S-17.

---

## For Developers

### Per-story walkthrough

---

**STORY-012-01: MCP Service Layer** · L1 · backend · commit `a3954ec`

- **Files (created):** `database/migrations/014_teemo_mcp_servers.sql`, `backend/app/core/url_safety.py` (lift of `_is_safe_url`, public `is_safe_url(url) -> tuple[bool, str | None]`), `backend/app/services/mcp_service.py` (CRUD + `_build_mcp_client` dispatcher + `test_connection`), `backend/tests/services/test_mcp_service.py`, `backend/tests/core/test_url_safety.py`.
- **Files (modified):** `backend/app/agents/agent.py` (`_is_safe_url` deleted, single callsite `agent.py:1306` rewritten to consume `(ok, reason)` tuple while preserving the exact existing `http_request` rejection string for regression), `backend/app/main.py` (`TEEMO_TABLES` += `teemo_mcp_servers`), `database/migrations/README.md` (slot 014 inventory row).
- **Tests added:** ~16 backend (12+ in `test_mcp_service.py`: CRUD × both transports, slug regex, reserved-name deny-list per entry, `http://` rejection, private-IP rejection, header encryption round-trip, `test_connection` happy/zero-tools/timeout, `_is_safe_url` lift regression; 4+ in `test_url_safety.py`: https / http / private IPv4 / loopback).
- **Kickbacks:** 0 (one-shot first-pass).
- **Deviations from plan:** None on the implementation surface.

---

**STORY-012-03: Agent MCP Wiring** · L2 · backend · commits `6023f2b` (feat) + `151fe1f` (fix)

- **Files (modified):** `backend/app/agents/agent.py` — `AgentDeps.mcp_servers: list[Any] = field(default_factory=list)` appended to the dataclass (preserves positional-init order); `build_agent` body fetches active MCP rows + populates `deps.mcp_servers` + passes `mcp_servers=deps.mcp_servers` to `Agent(...)` constructor; `## Connected Integrations` section appended to `_build_system_prompt` (omitted entirely when zero MCP servers); 3 new `@agent.tool` declarations (`add_mcp_server`, `remove_mcp_server`, `list_mcp_servers`) in the same region as the existing `add_skill` block, with the `auth_header` value redacted from `add_mcp_server`'s return string per Q10. `backend/app/services/slack_dispatch.py` — `AsyncExitStack` wraps the existing `agent.run_stream(...)` call (NOT `agent.run` — the story spec drifted there; W01 caught it via flashcard).
- **Files (created):** `backend/tests/agents/test_agent_mcp.py`, `backend/tests/services/test_slack_dispatch_mcp_lifecycle.py`.
- **Tests added:** 13 backend across `test_agent_mcp.py` + `test_slack_dispatch_mcp_lifecycle.py` (8 Gherkin scenarios + 5 supporting unit tests). Covers transport dispatch, system-prompt presence/absence, `auth_header` redaction substring assertion, AsyncExitStack `__aexit__` on success AND on `RuntimeError` raise, zero-MCP regression.
- **Kickbacks:** 1 (test-pollution regression).
  - **First pass `6023f2b`** introduced `from app.core.encryption import decrypt` at module top of `mcp_service.py`. QA caught a regression on `test_header_encrypt_round_trip` — when an earlier test in the session monkeypatched `app.core.encryption.decrypt`, `mcp_service.decrypt` (a separate bound name in `mcp_service`'s module namespace) stayed pinned to the mock for the rest of the session, breaking any later test that exercised real decrypt against a stored ciphertext.
  - **Fix pass `151fe1f`** switched `mcp_service` to attribute-lookup (`from app.core import encryption as _encryption; _encryption.decrypt(...)`) + hoisted test imports so the monkeypatch target matches the lookup path. QA flagged the same shape lurks in 8 other modules that use `from app.core.encryption import decrypt` — backlog cleanup, not in scope here.
- **Deviations from plan:** Story §1.2.5 said "wrap the existing `agent.run(...)` call"; production code uses `agent.run_stream(...)`. Architect's W01 caught this and locked in the streaming wrap; flashcard recorded at sprint kickoff (now line 12 of `FLASHCARD.md`).

---

**STORY-012-02: MCP REST Endpoints** · L2 · backend · commits `3094143` (feat) + `58a51b6` (fix)

- **Files (created):** `backend/app/api/routes/mcp_servers.py` (5 endpoints under `/api/workspaces/{workspace_id}/mcp-servers`), `backend/app/api/schemas/mcp_server.py` (`McpServerCreate`, `McpServerPatch`, `McpServerPublic`, `McpTestResultPublic` — `McpServerPublic` deliberately omits `headers`), `backend/tests/api/test_mcp_servers_routes.py`.
- **Files (modified):** `backend/app/main.py` — `app.include_router(mcp_servers_router)`; `TEEMO_TABLES` was already populated by 012-01.
- **Tests added:** 17 endpoint tests covering the 12 Gherkin scenarios + 5 supporting (auth matrix 200/403/404, list-never-leaks-headers verified at the schema declaration level, PATCH `is_active`, PATCH `headers={}` clears, DELETE 204, test-connection HTTP-200-on-`ok=false`, reserved-name 400, `http://` 400, integration smoke via FastMCP-served in-process ASGI app).
- **Kickbacks:** 1 (real test-fidelity gap).
  - **First pass `3094143`** had two QA-flagged issues: (a) the 404 fixture for "MCP server name not found on test endpoint" was defined but never asserted — the route returned 200 on missing names; (b) the "integration smoke" was a stub — patched `mcp_service.test_connection` directly instead of exercising the real Pydantic AI handshake.
  - **Fix pass `58a51b6`** added the explicit 404 assertion, replaced the stub with a real in-process integration smoke using `httpx.ASGITransport` over a minimal `FastMCP`-based MCP server (avoids the pydantic-ai 1.x SSE-server hang that would have surfaced with a true network responder), and relocated the test file to its final path.
- **Deviations from plan:** The integration-smoke fixture strategy in W01 named `respx`/`httpx_mock` for unit tests + a generic in-process responder for integration. Final shape used `FastMCP` + `httpx.ASGITransport` because the simpler in-process responder hit a known pydantic-ai 1.x SSE deadlock; flashcard candidate (see §Flashcard audit).

---

**STORY-012-04: MCP Dashboard UI** · L2 · frontend · commit `de92873`

- **Files (created):** `frontend/src/hooks/useMcpServers.ts` (5 TanStack Query hooks; `useTestMcpServerMutation` deliberately does NOT invalidate the list query), `frontend/src/components/dashboard/AddMcpServerModal.tsx`, `frontend/src/components/dashboard/IntegrationsSection.tsx`, `frontend/src/components/dashboard/HeadersEditor.tsx` (dumb controlled component), `frontend/src/lib/mcpJsonImport.ts` (~50 LOC pure parser, no React imports), 5 Vitest specs.
- **Files (modified):** `frontend/src/components/dashboard/WorkspaceCard.tsx` (mounts `<IntegrationsSection />` immediately after `<KeySection />`, matching chrome verbatim per W01 §3.2), `frontend/src/lib/api.ts` (5 typed wrappers + `McpTransport` / `McpServer` / `McpTestResult` types).
- **Tests added:** 48 frontend Vitest across the 5 spec files (full Gherkin coverage: empty state; modal happy path with single header; multi-header; zero headers; SSE radio; slug regex client-side rejection; Claude Desktop wrapper import; VS Code `type:"http"` import; stdio rejection with the exact §1.2.6 error string; `${env:...}` placeholder strip + hint; edit-imported-headers-before-submit; Test button success badge with tool count; Test button failure red + tooltip; toggle disable PATCH; Delete confirm dialog; `useCreateMcpServerMutation` invalidates `["mcp-servers", workspaceId]`; HeadersEditor add/remove/onChange; multi-server JSON import warning).
- **Kickbacks:** 0 (one-shot first-pass).
- **Deviations from plan:** None. Status badge state machine kept in `IntegrationsSection` local state per W01 contract (server returns only `is_active`; client computes the visible badge). Headers editor's value input rendered `type="password"` masked.

---

### Agent efficiency breakdown

| Role | Invocations | Tokens | Cost | Notes |
|---|---|---|---|---|
| Architect | 1 | unavailable | — | W01 blueprint covered all 4 stories in one milestone. Pre-sprint surfaced 5 flashcard-worthy items (pydantic-ai 1.79 MCP imports, `slack_dispatch.run_stream` not `.run`, `build_agent` 17+ unpack sites, slot 014 free / `012a` rename, deny-list maintenance) — all recorded at kickoff before any developer agent spawned. Granularity Rubric: no splits/merges. |
| Developer | 4 stories + 2 fix-passes (6 commits feat/fix; 7 with kickoff) | unavailable | — | One feat commit per story; two fix-pass commits (012-02 `58a51b6`, 012-03 `151fe1f`) for QA-flagged real issues. First-pass success rate: 2/4 (50%). |
| QA | 4 + 2 re-runs | unavailable | — | Caught 2 real first-pass issues with high signal: 012-03 test-pollution regression on a previously-green test, 012-02 missing 404 + vacuous integration smoke. Both required real handshake / real symbol-binding behaviour to surface — neither would have shown up under naive mock-the-service-layer testing. |
| Reporter | 1 (this report) | unavailable | — | Token ledger intentionally disabled this sprint — see Meta. |

Token ledger unavailable — see Meta.

### What the loop got right

- **Parallel decomposition with truly disjoint file spaces.** STORY-012-02 and STORY-012-03 touched zero shared files (012-02 = `routes/mcp_servers.py` + `schemas/mcp_server.py` + `main.py`; 012-03 = `agents/agent.py` + `services/slack_dispatch.py`). Sequential merge held without conflicts; W01 §Parallelization note paid off.
- **DI-via-`AgentDeps` (Q6) avoided a 17-site signature change.** Pre-sprint Q-resolution chose `mcp_servers: list[MCPServer]` field on `AgentDeps` instead of expanding `build_agent`'s return tuple to 3-tuple. 17+ test unpack sites were untouched; the `grep build_agent backend/tests/` post-flight confirmed zero test-fixture changes. Highest single ROI of the sprint.
- **`httpx.ASGITransport` over `FastMCP` is the right answer for in-process MCP integration smokes.** The 012-02 first-pass attempt at a hand-rolled SSE responder hit a known pydantic-ai 1.x deadlock; the second-pass shape (real ASGI app served via in-process transport) gives genuine handshake + `tools/list` coverage with zero network I/O. Future-MCP-related sprints should default to this pattern.
- **Architect pre-sprint flashcard sweep prevented 2 spec-vs-reality landmines.** W01 caught (a) `slack_dispatch` wraps `agent.run_stream` not `agent.run` — story spec drifted; (b) `build_agent` had 17+ unpack sites that a 3-tuple change would have touched. Both surfaced before any developer agent spawned. Flashcards recorded at kickoff (lines 11–15 of `FLASHCARD.md`).

### What the loop got wrong

- **First-pass QA success rate fell to 50% (2/4) — below the 75% target.** Sprint plan §6 explicitly flagged 012-03 AsyncExitStack and 012-02 SSE fixturing as expected friction; both fired. Loop improvement: the friction-flag → first-pass-likely-to-fail mapping is now a strong signal — when sprint metrics §6 names a story as expected-to-friction, route a tighter QA pre-pass (or add an explicit pre-flight self-review checklist mirroring the friction prediction).
- **Top-level `from app.core.encryption import decrypt` is a session-wide foot-gun.** When *any* test in the session monkeypatches `encryption.decrypt`, the bound name in any module that did `from ... import decrypt` stays pinned to the mock. QA grep flagged **8 modules** with the same pattern — all are latent test-pollution hazards. **Loop improvement:** new flashcard `#test-harness #monkeypatch #python-imports`: any module that may be exercised before/after a test that monkeypatches `encryption.decrypt` should attribute-lookup (`_encryption.decrypt`), not import-bind. 8-module cleanup is a backlog hygiene story.
- **Story-spec drift on `agent.run` vs `agent.run_stream`.** STORY-012-03 §1.2.5 said wrap "`agent.run(...)`"; production code uses `run_stream`. W01 caught it; flashcard recorded. Loop improvement: when a story spec quotes a callsite to wrap, the architect's pre-flight grep against the named symbol is the right gate — confirmed value here.
- **Frontend pre-existing failure backlog (~61 Vitest failures from a JSX-transform misconfiguration) has no owner.** Survived another sprint without action; nobody flagged it during 012-04 development because the new tests pass. Recurring debt; carry-over to S-18.
- **Token ledger hook still off.** **Fifth sprint without cost capture (S-13, S-14, S-15, S-16, S-17).** Open follow-up since S-15; deliberately deferred again to keep S-17 focused. Now loud — pull the port into S-18 explicitly.

### Flashcard audit

**New cards this sprint: 5 confirmed (architect kickoff, lines 11–15 of `.cleargate/FLASHCARD.md`); 1 candidate from execution.**

The 5 architect-kickoff cards are already on disk:

1. `2026-04-26 · #mcp #pydantic-ai · pydantic-ai==1.79.0 ships pydantic-ai-slim[mcp,fastmcp,...] transitively; from pydantic_ai.mcp import MCPServerSSE, MCPServerStreamableHTTP imports cleanly with no extras pin needed.`
2. `2026-04-26 · #agent #lifespan · slack_dispatch wraps agent.run_stream (not agent.run) at slack_dispatch.py:104 — wrap MCP-server AsyncExitStack OUTSIDE the run_stream context manager so __aexit__ runs on stream-mid-flight exceptions too.`
3. `2026-04-26 · #agent #test-harness · build_agent return signature is 17+ unpack sites across backend/tests/ — adding new agent state, extend AgentDeps, never the return tuple.`
4. `2026-04-26 · #schema #migrations · Migration slot 012 was double-booked; next free slot for new tables is 014. README inventory and 012a rename live on main as of S-17 kickoff.`
5. `2026-04-26 · #correction #mcp · MCP server names must be rejected against deny-list {search, skill, skills, knowledge, automation, automations, http_request} — collisions with first-party Tee-Mo agent tool names are silent footguns. Update the deny-list whenever first-party tools are added.`

**Candidate from execution (not yet on disk):**

- `2026-04-26 · #test-harness #monkeypatch #python-imports` — when a module does `from app.core.encryption import decrypt` at top level and any earlier test in the session monkeypatches `encryption.decrypt`, the bound name in the importing module stays pinned to the mock for the rest of the session, silently breaking any later test that exercised real decrypt. Use attribute lookup (`from app.core import encryption as _encryption; _encryption.decrypt(...)`). 8 modules currently flagged; cleanup backlog. (Surfaced from STORY-012-03 fix pass `151fe1f`.)

**Stale-candidate scan:** none new this sprint.
**Supersede candidates:** none new.

### Open follow-ups

- **Gate-3 manual smoke (P1, this session or next):** connect GitHub MCP at `https://api.githubcopilot.com/mcp/` from a real workspace via the dashboard; full runbook in archived `STORY-012-04 §5.6` (steps 1–9). Pre-sprint validation already proved the protocol path; this exercises the production UI.
- **Gate-3 squash-merge to `main` (P1, awaiting human approval):** sprint branch `sprint/S-17` HEAD is `de92873`; expected commit prefix `feat: squash-merge sprint/S-17 onto main — EPIC-012 MCP server integration` per S-15/16 pattern.
- **S-18 (P3, hygiene):** 8 modules using `from app.core.encryption import decrypt` (or `encrypt`) at top level — switch to attribute lookup to remove the test-pollution foot-gun.
- **S-18 (P1, planned story):** port the V-Bounce SubagentStop token-ledger hook into ClearGate. Fifth consecutive sprint without cost capture; now overdue.
- **S-18 (P2, hygiene):** ~61 frontend pre-existing Vitest failures from the JSX-transform misconfiguration. No owner today. Pre-dates S-17.
- **S-18 (P2, hygiene):** ~42 backend pre-existing pytest failures (down from 44 — 012-03 net-reduced by 2). All in files S-17 never touched.
- **EPIC-026 stub (P2, future epic):** MCP-OAuth flow for Azure DevOps Remote MCP and any other Entra-only endpoints. Pre-sprint validation already documented the rejection-of-static-PAT shape; epic stub exists.
- **V2 enhancement (P3, future):** `X-MCP-Toolsets` / `X-MCP-Tools` filtering header passthrough exposed as an "Advanced" modal field — mitigates the ~6–10k system-prompt token bloat from 41-tool servers like GitHub MCP. Deferred from V1 by design.

---

## Meta

**Token ledger:** `.cleargate/sprint-runs/SPRINT-17/token-ledger.jsonl` — **does not exist (intentionally).** ClearGate's token-ledger hook is intentionally disabled for this sprint per the standing convention. **Fifth consecutive sprint without cost capture (S-13, S-14, S-15, S-16, S-17).** Open follow-up since S-15; pulling the V-Bounce SubagentStop port into S-18 as a planned story is the right next move. Reporter must NOT invoke `.claude/hooks/token-ledger.sh` for S-17 backfill — the hook stays off until the formal port lands.

**Wiki ingest:** ran throughout via PostToolUse hook + manual fallback at sprint-close.

**Architect upfront economics this sprint:** 5 flashcards recorded at kickoff (covering pydantic-ai imports, run_stream wrap, build_agent unpack-site economics, slot 014 free / 012a rename, deny-list maintenance) — every one of them prevented a real downstream landmine in implementation. Ratio remains favourable.

**QA-side economics this sprint:** 2/4 first-pass = 50% (below the §6 target of 75%). Both kickbacks were *real* fidelity issues (not numeric drift, not cosmetic) — the QA gate did its job; the loop's pre-pass missed them.

**Flashcards added:** 5 confirmed (architect-kickoff, lines 11–15 of `FLASHCARD.md`); 1 candidate flagged (`#test-harness #monkeypatch #python-imports`) for next maintenance pass.

**Prompt-injection flags:** none observed during this sprint's agent sessions.

**Report generated:** 2026-04-26 by Reporter agent.

---

## Definition of Done tick-through

- [x] **All 4 stories pass QA on their own branches.** 4/4 PASS post-fix.
- [ ] **Sprint branch `sprint/S-17` merges cleanly to `main`.** Pending Gate-3 human approval.
- [x] **`pytest backend/tests/` — full suite runs without hangs; 24+ new pytest scenarios; zero new failures.** ~45 new backend tests; pre-existing failures: 44 → 42.
- [x] **`npm test` (Vitest) — 5+ new tests in 012-04 pass; no existing failures introduced.** 48 new tests; ~61 pre-existing unchanged.
- [x] **`npm run typecheck` clean.**
- [x] **EPIC-012 progresses from `Active` to `Shipped` — 4/4 stories shipped.**
- [x] **Migration `014_teemo_mcp_servers.sql` applied cleanly + verified rollback.**
- [x] **No regression on EPIC-007 / EPIC-008 / EPIC-018 / EPIC-024.**
- [ ] **Manual smoke (V1 acceptance demo): connect GitHub MCP end-to-end via the dashboard.** Pending Gate-3.
- [ ] **Manual smoke: also connect ONE `transport='sse'` server.** Pending Gate-3.
- [ ] **Manual smoke: validate rejection paths.** Pending Gate-3.
- [ ] **Manual smoke: paste a Claude-Desktop-shape JSON config.** Pending Gate-3.
- [x] **Wiki ingest fallback processes all SPRINT-17 work items at close.**
- [x] **Reporter writes `.cleargate/sprint-runs/SPRINT-17/REPORT.md`.** This document.
- [x] **Flashcards recorded for any surprises.** 5 confirmed; 1 candidate flagged.

---

## Post-ship hotfixes (live-testing window — not yet open)

**N/A.** Squash-merge to `main` is pending Gate-3 human approval at report time. Section in place for appending if any hotfixes surface after the squash lands.
