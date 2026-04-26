---
sprint_id: "SPRINT-17"
remote_id: "local:SPRINT-17"
source_tool: "cleargate-native"
status: "Closed"
start_date: "2026-04-26"
end_date: "2026-04-26"
activated_at: "2026-04-26T00:00:00Z"
human_approved_at: "2026-04-26T00:00:00Z"
completed_at: "2026-04-26T00:00:00Z"
shipping_commit: "de92873"
synced_at: null
created_at: "2026-04-26T00:00:00Z"
updated_at: "2026-04-26T00:00:00Z"
created_at_version: "cleargate-post-sprint-16"
updated_at_version: "cleargate-post-sprint-16"
draft_tokens: { input: null, output: null, cache_read: null, cache_creation: null, model: null, sessions: [] }
cached_gate_result: { pass: null, failing_criteria: [], last_gate_check: null }
---

# SPRINT-17 Plan

> Single-epic sprint: ship EPIC-012 (MCP Server Integration) end-to-end. Four 🟢 stories under EPIC-012, no CRs, no bugs. EPIC-012 ambiguity flipped 🟡 → 🟢 on 2026-04-26 — first 4 OQs resolved at epic-update pass, 7 additional sprint-planning OQs (Q5–Q11) resolved at sprint-planning pass on the same day. **Notable scope expansion**: V1 supports both `sse` AND `streamable_http` transports (Q11) since Microsoft is migrating Azure DevOps + other remote MCP servers to Streamable HTTP. Both Pydantic AI classes inherit from `_MCPServerHTTP` — additional cost ~5 LOC of dispatcher logic.

## Sprint Goal

**Allow workspace admins to connect MCP (Model Context Protocol) servers to their workspace via dashboard or Slack chat, so the agent automatically discovers and uses pre-built tools (e.g. GitHub, Linear, Azure DevOps) without manual `http_request` instructions.** Two transports supported: classic SSE and modern Streamable HTTP (HTTPS-only, IP blacklist enforced, auth headers encrypted at rest, stdio explicitly excluded). After this sprint, an admin can add/test/disable/remove MCP servers via the workspace card or by talking to the agent in Slack; on the next message the agent transparently gains the connected server's tools. **Manual smoke target**: connect the Azure DevOps Remote MCP Server (Streamable HTTP) end-to-end as the V1 acceptance demo.

## 0. Sprint Readiness Gate

- [x] All items reviewed — four 🟢 Low-ambiguity stories under one 🟢 epic (EPIC-012 ambiguity resolved 2026-04-26).
- [x] No 🔴 High-ambiguity items in scope.
- [x] Dependencies identified (see §3).
- [x] Risk flags reviewed (see §5).
- [x] All 4 story files drafted (2026-04-26); pre-sprint validation pass complete (V1 smoke target verified end-to-end against GitHub MCP — see STORY-012-04 §5.6).
- [x] Sprint infrastructure ready — `sprint/S-17` branch cut, `.active` sentinel flipped, `sprint-runs/SPRINT-17/plans/` created.
- [ ] **Awaiting Architect W01 blueprint + human Gate 1 approval to begin coding.** All 11 OQs resolved 2026-04-26 across three passes (epic-update, sprint-planning, validation).

## 1. Active Scope

| # | Priority | Item | Parent | Complexity | Ambiguity | Status | Blocker |
|---|---|---|---|---|---|---|---|
| 1 | P1 | [STORY-012-01: MCP Service Layer](./STORY-012-01-mcp-service-layer.md) | EPIC-012 | L1 | 🟢 | Draft (TBD) | — |
| 2 | P1 | [STORY-012-02: MCP REST Endpoints](./STORY-012-02-mcp-rest-endpoints.md) | EPIC-012 | L2 | 🟢 | Draft (TBD) | 012-01 (consumes service layer) |
| 3 | P1 | [STORY-012-03: Agent MCP Wiring](./STORY-012-03-agent-mcp-wiring.md) | EPIC-012 | L2 | 🟢 | Draft (TBD) | 012-01 (consumes service layer) |
| 4 | P1 | [STORY-012-04: MCP Dashboard UI](./STORY-012-04-mcp-dashboard-ui.md) | EPIC-012 | L2 | 🟢 | Draft (TBD) | 012-02 (consumes REST API) |

**Total: 4 items — 4 stories under EPIC-012 (1× L1 · 3× L2).** Smaller scope than S-16 (7 items) by design — EPIC-012 is a coherent vertical slice with non-trivial security surface (encryption + URL safety + transport restriction), and a focused sprint reduces context-switching.

### Pre-sprint hygiene (no engineering — bookkeeping)
- [x] Migration `012_teemo_automations.sql` renamed to `012a_teemo_automations.sql` (Q5 resolution; 2026-04-26). `database/migrations/README.md` inventory + numbering-fix note updated.
- [x] All 4 STORY-012-0X files drafted into `pending-sync/` (2026-04-26).
- [x] **Pre-sprint validation pass** — Azure DevOps PAT + GitHub PAT probed end-to-end; V1 smoke target = GitHub MCP (`https://api.githubcopilot.com/mcp/`); AzDO Remote MCP confirmed Entra-OAuth-only (deferred to EPIC-026). Full runbooks in STORY-012-04 §5.
- [x] Sprint branch `sprint/S-17` cut from `main` (HEAD `2bcc295`, S-16 close-out).
- [x] `.cleargate/sprint-runs/SPRINT-17/plans/` directory created.
- [x] `.cleargate/sprint-runs/.active` flipped from `SPRINT-16` to `SPRINT-17`.
- [ ] **Mark EPIC-012 status `Active` at kickoff commit** (currently `Draft`).
- [ ] Backfill BUG-002 frontmatter status `Approved` → `Shipped` (fix is on `main` per `workspaces.py:79` + `channels.py:114`; status drift only). 1-line change, runs alongside kickoff commit.
- [ ] Architect agent writes `.cleargate/sprint-runs/SPRINT-17/plans/W01.md` blueprint (one milestone covering all 4 stories).
- [ ] Push EPIC-012 + 4 stories to remote PM tool to obtain remote IDs (or leave local-only per S-13/14/15/16 fallback if remote unavailable).
- [ ] Run wiki-ingest fallback at kickoff so the index reflects EPIC-012 Active + 4 new stories + SPRINT-17 + BUG-002 status correction.

## 2. Context Pack Readiness

**STORY-012-01 — MCP Service Layer**
- [x] Migration slot: `014_teemo_mcp_servers.sql` (Q5 resolution; collision at slot 012 cleaned up via rename of `012_teemo_automations.sql` → `012a_teemo_automations.sql`).
- [x] Schema (Q11-extended): `id` UUID PK, `workspace_id` FK to `teemo_workspaces` `ON DELETE CASCADE`, `name` TEXT (slug `^[a-z0-9_-]{2,32}$`, unique per workspace, NOT IN reserved-deny-list at app layer), `transport` TEXT `CHECK (transport IN ('sse', 'streamable_http'))`, `url` TEXT (HTTPS-only, validated server-side), `headers_encrypted` JSONB (AES-256-GCM-encrypted values via `core.encryption`), `is_active` BOOLEAN DEFAULT true, `created_at` TIMESTAMPTZ DEFAULT now(). Table name `teemo_mcp_servers`.
- [x] **Q8 resolution: lift `_is_safe_url()` to `app/core/url_safety.py`.** New module exports `is_safe_url(url) -> tuple[bool, str | None]`. `agent.py` re-imports the public form (zero behavioural change for `http_request` tool). MCP service uses the same module — single source of truth.
- [x] **Q9 resolution: reserved-name deny-list = `{search, skill, skills, knowledge, automation, automations, http_request}`** (Tee-Mo first-party agent tool names). Validated at create + update time. Future first-party tool additions must update the deny-list (flashcard tag).
- [x] Reuses `app/core/encryption.py` `encrypt`/`decrypt` (EPIC-004) — already used by BYOK keys; same AES-256-GCM scheme.

**STORY-012-02 — MCP REST Endpoints**
- [x] Endpoint mount path: `/api/workspaces/{workspace_id}/mcp-servers` and `/api/workspaces/{workspace_id}/mcp-servers/{name}/test`. Auth via existing `assert_team_member` (consistent with workspace-scoped routes).
- [x] List response shape: `{name, transport, url, is_active, created_at}` — **never** return decrypted headers. Headers are write-only over the API.
- [x] `POST /test` runs handshake + `tools/list` and asserts ≥ 1 tool returned (Q4 = B); 10s timeout (Q2 = B). Returns `{ok, tool_count, error}`.
- [x] Router file: `backend/app/api/routes/mcp_servers.py` (NEW). Mounted in `backend/app/main.py`. `TEEMO_TABLES` updated to include `teemo_mcp_servers`.
- [x] **Q7 resolution: test fixturing = httpx_mock/respx for unit tests + ONE in-process integration smoke** with a minimal SSE responder (mirrors Slack signing test pattern).

**STORY-012-03 — Agent MCP Wiring**
- [x] **Q6 resolution: NO signature change.** `build_agent()` keeps 2-tuple `(agent, deps)` (`backend/app/agents/agent.py:1684`). MCP servers ride on `AgentDeps.mcp_servers: list[MCPServer]` per Pydantic AI's documented DI best practice. Test fixtures untouched — zero migration cost.
- [x] Inside `build_agent`: load active MCP rows via `mcp_service.list_mcp_servers(workspace_id, active_only=True)`; instantiate `MCPServerSSE` for `transport='sse'` rows and `MCPServerStreamableHTTP` for `transport='streamable_http'` rows (Q11); populate `deps.mcp_servers`.
- [x] Agent constructed with `mcp_servers=deps.mcp_servers` (Pydantic AI 1.79 `Agent(..., mcp_servers=...)` kwarg).
- [x] System prompt addition: `## Connected Integrations` section listing active MCP server names — appended to the existing system-prompt builder, not a separate template. No tool enumeration in the prompt (Pydantic AI registers tools itself).
- [x] 3 new agent tools registered: `add_mcp_server(ctx, name, transport, url, auth_header=None)`, `remove_mcp_server`, `list_mcp_servers`. Tool placement: same pattern as existing `add_skill` / `remove_skill` / `list_skills`. **Q10: `add_mcp_server` tool result echoes name/url/transport but NEVER `auth_header`** (defence in depth).
- [x] Slack dispatch lifecycle: `async with AsyncExitStack() as stack:` enters every `deps.mcp_servers` server before calling `agent.run()`. Pattern: `for s in deps.mcp_servers: await stack.enter_async_context(s)`. Verified to honour `__aexit__` on exception (DoD test).
- [x] Pydantic AI MCP availability verified (2026-04-26): `pydantic-ai==1.79.0` transitively requires `pydantic-ai-slim[mcp,fastmcp,...]`; `from pydantic_ai.mcp import MCPServerSSE, MCPServerStreamableHTTP` imports cleanly in `backend/.venv`. No `pyproject.toml` change needed.

**STORY-012-04 — MCP Dashboard UI**
- [x] Inline section in `WorkspaceCard.tsx` — **same pattern as `KeySection`** (BYOK). NOT a separate settings page.
- [x] New file: `frontend/src/components/dashboard/AddMcpServerModal.tsx` — name + URL + **transport selector (radio: SSE / Streamable HTTP, default Streamable HTTP)** + optional auth-header inputs. Submit calls `useCreateMcpServerMutation`.
- [x] New file: `frontend/src/hooks/useMcpServers.ts` — TanStack Query hooks (`useMcpServersQuery`, `useCreateMcpServerMutation`, `useUpdateMcpServerMutation`, `useDeleteMcpServerMutation`, `useTestMcpServerMutation`).
- [x] Mini-cards: name, URL, **transport badge (SSE / Streamable HTTP)**, status badge (Active / Disabled / Untested), Enable toggle, Test button (calls `useTestMcpServerMutation` → green/red with tool count), Delete button.
- [x] `frontend/src/lib/api.ts` adds typed wrappers for the 5 MCP endpoints. `Transport` type union: `'sse' | 'streamable_http'`.

## 3. Sequencing + Dependencies

1. **STORY-012-01 first.** Foundation. Migration + service layer + validation. Unblocks every downstream story. Ships behind the sprint branch — no UI change yet, no agent change yet.
2. **STORY-012-02 + STORY-012-03 in parallel after 012-01.** Different file spaces:
   - 012-02 touches `backend/app/api/routes/mcp_servers.py` (NEW) + `main.py` (router mount line) + tests.
   - 012-03 touches `backend/app/agents/agent.py` (signature + tools + system prompt) + `services/slack_dispatch.py` (AsyncExitStack) + tests.
   - Only shared file is `main.py` (012-02 mounts router, 012-03 doesn't touch `main.py`) — zero conflict.
3. **STORY-012-04 last.** Depends on 012-02 for the REST API surface it consumes. Frontend-only. Cannot ship before 012-02 merges.

**Parallel-eligibility:** 012-02 and 012-03 can run concurrently after 012-01. Recommended order by complexity for early-bug-detection: 012-01 → 012-03 (highest-leverage; agent factory signature change ripples to tests) → 012-02 → 012-04.

## 4. Execution Strategy

### Branching
- Sprint branch: `sprint/S-17` cut from `main` after S-16 squash-merge (currently `2bcc295` — verify head before cutting).
- Per-item branches:
  - `story/STORY-012-01-mcp-service-layer`
  - `story/STORY-012-02-mcp-rest-endpoints`
  - `story/STORY-012-03-agent-mcp-wiring`
  - `story/STORY-012-04-mcp-dashboard-ui`
- One commit per item. Commit prefixes:
  - `feat(epic-012): STORY-012-01 mcp service layer`
  - `feat(epic-012): STORY-012-02 mcp rest endpoints`
  - `feat(epic-012): STORY-012-03 agent mcp wiring`
  - `feat(epic-012): STORY-012-04 mcp dashboard ui`
- DevOps merges sprint branch to `main` at sprint close under explicit human approval (S-13/14/15/16 squash-merge pattern).

### Four-agent loop
- **Architect** — write W01 blueprint to `.cleargate/sprint-runs/SPRINT-17/plans/W01.md` at kickoff. Surface any open questions found while reading the 4 stories + relevant code (agent factory return shape, current `_is_safe_url` location, Slack dispatch error paths). Run Granularity Rubric over each story; recommended baseline is 4 stories as decomposed in EPIC-012 §5 — splits or merges only if rubric trips.
- **Developer** — one story per commit. Must grep `.cleargate/FLASHCARD.md` for relevant tags before implementing:
  - 012-01: `#schema`, `#supabase`, `#fastapi`, `#auth`, `#pytest`, `#encryption`
  - 012-02: `#fastapi`, `#auth`, `#pytest`, `#test-harness`
  - 012-03: `#fastapi`, `#pytest`, `#test-harness`, `#lifespan`, `#agent`
  - 012-04: `#frontend`, `#tailwind`, `#vitest`, `#test-harness`, `#tanstack`
- **QA** — independent verification gate per story.
  - 012-01: 10+ unit tests covering CRUD + all validation paths (slug name regex, HTTPS-only, IP blacklist, header value encryption); migration applies cleanly + rolls back cleanly; encrypted column round-trips.
  - 012-02: 8+ endpoint tests — owner enforcement (200/403/404 matrix), list never leaks decrypted headers, test-connection happy/sad path with fixture SSE server (or stub), idempotent PATCH, DELETE removes row.
  - 012-03: 6+ tests — `build_agent` 3-tuple shape, MCP servers passed to Agent constructor, system prompt contains active MCP names, 3 agent tools registered + happy-path tool invocations, AsyncExitStack runs `__aexit__` on success AND on exception during `agent.run()`.
  - 012-04: 5+ Vitest tests — Add modal validates inputs, list renders cards with status badges, test button mutates and surfaces green/red, delete confirms before mutating, hooks invalidate the right query keys; manual smoke at 1440px.
  - **Sprint-wide regression**: Slack agent flow still works end-to-end with zero MCP servers configured (most existing workspaces); tests in `backend/tests/services/test_slack_dispatch_*` still pass with the new AsyncExitStack wrapper.
- **Reporter** — at sprint close, writes `.cleargate/sprint-runs/SPRINT-17/REPORT.md` with the 6-section retrospective. Token-ledger hook still backlogged — fifth sprint without rows; flag in REPORT Meta.

### Red-zone surfaces (3+ items touch these)
None. All four stories touch disjoint file spaces (012-01 = migration + service file; 012-02 = REST routes; 012-03 = agent factory + dispatch; 012-04 = frontend). Lower coordination overhead than S-16.

### Shared surface warnings
- `backend/app/agents/agent.py` — only 012-03 touches. **Return-signature change is the load-bearing decision**: 2-tuple → 3-tuple. Single production caller (`slack_dispatch.py`); test files unpack `build_agent` widely (grep before refactoring).
- `backend/app/services/slack_dispatch.py` — only 012-03 touches (AsyncExitStack wrapper around `agent.run()`).
- `backend/app/main.py` — only 012-02 touches (router mount + `TEEMO_TABLES` entry).
- `frontend/src/components/dashboard/WorkspaceCard.tsx` — only 012-04 touches (new "Integrations" inline section beneath KeySection).
- `frontend/src/lib/api.ts` — only 012-04 touches (typed wrappers for 5 MCP endpoints).

## 5. Risk & Definition of Done

### Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Test-connection SSE handshake requires a fixture MCP server in tests | High | Medium | 012-02 test plan: stub the handshake via `respx` / `httpx_mock` for unit tests; add ONE integration test that spins a minimal in-process SSE responder. Avoid network calls in CI. |
| `AsyncExitStack` not awaited on agent.run() exception path → connection leak | Medium | Medium | 012-03 DoD includes one explicit pytest scenario raising mid-`agent.run()` and asserting MCP `__aexit__` was called. Pattern matches Pydantic AI's own MCP example in `pydantic_ai/CLAUDE.md`. |
| `build_agent` return-shape change breaks tests that unpack 2-tuple | Resolved (Q6) | — | DI-via-`AgentDeps` chosen instead of return-shape change; signature unchanged. Test fixtures untouched. Pydantic AI documented best practice. |
| Adding `streamable_http` transport doubles the test matrix (validation, dispatch, lifecycle) | Medium | Low | Both transports inherit from `_MCPServerHTTP` — URL safety, encryption, AsyncExitStack code paths are identical. Test matrix doubles only at the transport-dispatcher seam (~5 tests parametrized over both transports). |
| User adds an `streamable_http` server expecting full MCP feature set, but Streamable HTTP is newer and some servers may behave differently than SSE | Low | Low | V1 acceptance demo uses Azure DevOps Remote MCP (Streamable HTTP, public preview). Any quirks surface in manual smoke. Failures fall back to a clear error from the Test button (Q4 = handshake + ≥1 tool). |
| MCP server tools bloat system prompt past model limits | Medium (real signal from probe) | Medium | Pre-sprint probe of GitHub MCP shows **41 tools = ~6–10k tokens** of system-prompt overhead per connected server. Pydantic AI handles registration; the `## Connected Integrations` section lists server NAMES only. **Mitigation deferred to V2** — expose `X-MCP-Toolsets` / `X-MCP-Tools` filtering headers (already supported by GitHub + Azure DevOps gateways) as an "Advanced" modal field. In V1 we accept the full surface; surface as a follow-up to the user. Flashcard required at sprint close. |
| User pastes auth token in Slack `add_mcp_server` call → token visible in chat history | Resolved (Q3 = A) | Medium | Always-warn one-liner appended to the agent's success response: "⚠️ Your auth token is encrypted server-side, but the message you sent is still in this thread — consider deleting it." 012-03 includes a Vitest-style assertion the warning string is present in the tool reply. |
| `_is_safe_url()` only validates against initial DNS lookup → DNS rebinding | Low | Medium | `_is_safe_url` already mitigates per EPIC-012 §6 (resolves DNS then checks IPs at registration time). MCP runtime SSE connection re-uses the same URL; no re-resolution attack vector beyond what's already documented. |
| 10s SSE timeout causes false-fail Test button on slow MCP servers (cold-start) | Low | Low | Q2 resolution chose 10s as the balance point. If real-world reports surface slow servers, surface timeout as a configurable `MCP_TEST_TIMEOUT_SECONDS` env var in S-18 — out of scope here. |
| Pydantic AI MCP API surface differs from docs / changes between 1.79 and any in-flight upgrade | Resolved (Q1) | — | 2026-04-26 verification: `MCPServerHTTP` and `MCPServerStdio` import cleanly from `pydantic_ai.mcp` at 1.79.0. Pin stays at 1.79.0 for this sprint; do not bump mid-sprint. |
| Slug name regex collides with reserved tool names in agent (e.g. user adds MCP server named "search") | Medium | Low | 012-01 validation: reject server names matching reserved set `{"search", "skill", "skills", "knowledge", "automation", "automations"}` (Tee-Mo's first-party tool names). Test enumerates the deny-list. Future first-party tool additions must update the deny-list — flashcard. |
| Wiki ingest still manual (no `cleargate` CLI in M3) | Resolved | — | Fallback wiki-ingest agent works (verified during EPIC-012 question resolution today). Reporter at sprint close runs the same fallback. |

### Definition of Done
- [ ] All 4 stories pass QA on their own branches.
- [ ] Sprint branch `sprint/S-17` merges cleanly to `main` (squash-merge under explicit human approval, pushed to `origin/main`).
- [ ] `pytest backend/tests/` — full suite runs without hangs; **24+ new pytest** scenarios across stories (10+ from 012-01, 8+ from 012-02, 6+ from 012-03) and zero new failures elsewhere.
- [ ] `npm test` (Vitest) — 5+ new tests in 012-04 pass; no existing failures introduced.
- [ ] `npm run typecheck` clean.
- [ ] EPIC-012 progresses from `Active` to `Shipped` — 4/4 stories shipped.
- [ ] Migration `014_teemo_mcp_servers.sql` applied cleanly on local + verified rollback.
- [ ] No regression on EPIC-007 agent loop, EPIC-008 setup wizard, EPIC-018 automations, EPIC-024 background worker — slack dispatch path covered by full test suite.
- [ ] **Manual smoke (V1 acceptance demo) — VERIFIED 2026-04-26**: connect **GitHub MCP** at `https://api.githubcopilot.com/mcp/` with a GitHub PAT (`transport='streamable_http'`) end-to-end. Pre-sprint probe sequence (`initialize` → `tools/list` → `tools/call get_me`) all green; **41 GitHub tools register**; full runbook in **STORY-012-04 §5.6**. *(Azure DevOps Remote MCP was originally proposed but ruled out 2026-04-26: Microsoft's hosted endpoint is Entra-OAuth-only, rejects static PATs. Verified empirically — see STORY-012-04 §5.2. AzDO is unblocked once EPIC-026 ships MCP-OAuth.)*
- [ ] Manual smoke: also connect ONE `transport='sse'` server (any public hosted MCP-SSE endpoint, or local via ngrok) to exercise the SSE class path.
- [ ] Manual smoke: try to add `http://insecure.example` → rejected with "HTTPS required". Try `https://10.0.0.1/sse` → rejected with "unsafe URL". Try `name='search'` → rejected with "reserved name" (Q9 deny-list).
- [ ] Manual smoke: paste a Claude-Desktop-shape JSON config into the modal's "Paste from another client" textarea → Import populates form fields correctly. Sample fixture in STORY-012-04 §5.4.
- [ ] Wiki ingest fallback processes all SPRINT-17 work items at close.
- [ ] Reporter writes `.cleargate/sprint-runs/SPRINT-17/REPORT.md` — 6-section retrospective.
- [ ] Flashcards recorded for any surprises (especially around AsyncExitStack lifecycle, Pydantic AI MCP API ergonomics, and SSE test fixturing).

## 6. Sprint Metrics & Goals

- **Items planned:** 4 stories under EPIC-012 = 4 items. (No CRs, no bugs in scope.)
- **Target first-pass success rate:** ≥ 75% (3/4 pass QA on first attempt). Expected friction points: 012-03 AsyncExitStack lifecycle on exception path, 012-02 SSE handshake test fixturing.
- **Target Bug-Fix Tax:** 0 (no bugs in scope).
- **Target Enhancement Tax:** 0 (single-epic sprint; resist scope creep).
- **Token budget:** no formal cap; Reporter aggregates post-hoc. Token-ledger hook still backlogged — fifth sprint without cost capture; Reporter flags in REPORT Meta.

## 7. Out-of-Scope (deliberate)

- **stdio MCP transport** — security risk (arbitrary process execution). HTTP-style transports (SSE + Streamable HTTP) only. (Epic §2.)
- **MCP server health monitoring / auto-reconnect** — server is connected fresh per agent run.
- **Connection pooling / caching** — V1 accepts per-request connection latency; optimization deferred.
- **MCP server discovery / marketplace** — user must know the SSE URL.
- **Per-tool access control** — all tools from a connected MCP server are available to the agent. Future epic if customer asks.
- **MCP server hosting** — Tee-Mo connects to externally hosted servers; does not host.
- **Dedicated workspace settings page for integrations** — inline in `WorkspaceCard`, same as BYOK keys.
- **EPIC-011 Slack AI Apps surface** — deferred per project memory (slack-bolt 1.28 plan-tier gating undocumented; revisit in EPIC-005 Phase B, not now).
- **EPIC-017 wiki-karpathy-parity / EPIC-018 scheduled-automations follow-ups** — both Active but separate concerns; do not bundle.
- **Configurable MCP test-connection timeout env var** — Q2 chose 10s flat. Make configurable only if real-world reports surface false-fails.
- **Token-ledger hook** — fifth sprint without cost capture; backlogged.

---

## ClearGate Readiness Gate

**Current Status: 🟢 Ready — awaiting human Gate 1 approval. All 4 story files drafted, V1 smoke target validated, sprint infrastructure provisioned.**

- [x] Scope = 4 items (4 EPIC-012 stories), all 🟢 ambiguity at entry. Story files drafted 2026-04-26.
- [x] Each item has a reachable parent (EPIC-012 🟢, ambiguity flipped 2026-04-26).
- [x] Red-zone surfaces identified: none (all 4 stories touch disjoint files).
- [x] Shared surfaces warned (§4): `agent.py` (012-03 only), `slack_dispatch.py` (012-03 only), `main.py` (012-02 only), `WorkspaceCard.tsx` (012-04 only), `lib/api.ts` (012-04 only).
- [x] Dependencies documented with explicit blocker columns.
- [x] Pre-sprint hygiene executed (§1) — sprint branch cut, sentinel flipped, plans/ created, migration rename committable, all stories drafted.
- [x] All 11 EPIC-012 OQs resolved 2026-04-26 across three passes. Pass 1 (epic-update): Q1 satisfied transitively, Q2=10s, Q3=always-warn, Q4=handshake+≥1 tool. Pass 2 (sprint-planning): Q5 migration rename, Q6 DI-via-AgentDeps, Q7 stub+integration fixturing, Q8 lift `_is_safe_url()`, Q9 reserved-name deny-list, Q10 redact `auth_header` in echo, **Q11 transport set = `{sse, streamable_http}`**. Pass 3 (pre-sprint validation): GitHub MCP verified end-to-end (41 tools, full handshake → tools/list → tools/call); AzDO Remote MCP rejection of static tokens confirmed (deferred to EPIC-026).
- [ ] **Human Gate 1 approval — pending.**
- [ ] Architect W01 blueprint — pending (next step after approval).
