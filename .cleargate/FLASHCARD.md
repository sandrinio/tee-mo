# ClearGate Flashcards

One-liner gotcha log. Newest first. Grep by tag (e.g. `grep '#schema'`).
Active cards have no marker; `[S]` = stale, `[R]` = resolved (see `.claude/skills/flashcard/SKILL.md` Rules 7–8).
Format: `YYYY-MM-DD · #tags · [marker]? lesson`

> **Initial batch seeded from V-Bounce `FLASHCARDS.vbounce-archive.md` during 2026-04-24 migration.** Original long-form lessons (with "Seen in" / "What happened" / "How to apply" details) remain in the archive file for any card where the one-liner loses important context.

---

2026-04-27 · #agent #http · http_request tool dies on quoted header keys (`"Authorization"`) → httpx LocalProtocolError. Strip at agent.py:1379.
2026-04-26 · #mcp #pydantic-ai · pydantic-ai==1.79.0 ships pydantic-ai-slim[mcp,fastmcp,...] transitively; from pydantic_ai.mcp import MCPServerSSE, MCPServerStreamableHTTP imports cleanly with no extras pin needed.
2026-04-26 · #agent #lifespan · slack_dispatch wraps agent.run_stream (not agent.run) at slack_dispatch.py:104 — wrap MCP-server AsyncExitStack OUTSIDE the run_stream context manager so __aexit__ runs on stream-mid-flight exceptions too.
2026-04-26 · #agent #test-harness · build_agent return signature is 17+ unpack sites across backend/tests/ (test_agent_factory, test_token_efficiency, test_production_scenarios, test_wiki_*, slack_dispatch.py:357). Adding new agent state — extend AgentDeps, never the return tuple.
2026-04-26 · #schema #migrations · Migration slot 012 was double-booked (012_increase_document_cap.sql + 012a_teemo_automations.sql post-rename); next free slot for new tables is 014. README inventory and 012a rename live on main as of S-17 kickoff.
2026-04-26 · #correction #mcp · MCP server names must be rejected against deny-list {search, skill, skills, knowledge, automation, automations, http_request} — collisions with first-party Tee-Mo agent tool names are silent footguns. Update the deny-list whenever first-party tools are added.
2026-04-25 · #process #ambiguity · Ported V-Bounce stories carry baseline assumptions (exact error class, exact failing test names) from their port date; verify at current `sprint/S-N` tip before relying on them. STORY-024-04 cited a `TypeError: MagicMock` failure that had already been reshaped into an `AssertionError` by the time of execution — QA caught it, scope reclassified as "defensive hardening" rather than "pass-flipping fix."
2026-04-25 · #test-harness #fastapi #lifespan · TestClient(app) as client: deadlocks under pytest-asyncio auto mode — lifespan spawns drive/wiki/automation cron loops that never return. Use TestClient(app, raise_server_exceptions=False) without the context manager for mock-heavy tests (pattern proven in test_workspaces_team_member_access.py and test_auth_routes.py). Formalized in STORY-024-05.
2026-04-24 · #llm #pydantic-ai · BYOK keys must flow through provider constructors (`GoogleProvider(api_key=...)`, `AnthropicProvider(api_key=...)`, `OpenAIProvider(api_key=...)`), not via `Agent.run(model_settings={"api_key": ...})` — `model_settings` is silently ignored, pydantic-ai reads the key at model construction. Always call `_build_pydantic_ai_model(model_id, provider, api_key)` to instantiate.
2026-04-24 · #llm #slack · Thread-history anchoring beats a freshly-fixed system prompt. When debugging "agent keeps saying X after I fixed the prompt", test in a fresh thread first — the old thread's assistant messages are in-context and the model follows its own established pattern before reading new rules.
2026-04-24 · #slack #agent · "Bound channel" ≠ "bot invited to channel". Binding is a row in `teemo_workspace_channels` written by the dashboard's channel picker; inviting the bot via `/invite @bot` has no effect on binding. Tell users this explicitly when surfacing a `channel not bound` error.
2026-04-24 · #llm #prompt · When a tool param is an opaque ID the user can't type (channel ID, document UUID, skill ID), inject the real catalog into the system prompt. Otherwise the LLM fabricates plausible-looking IDs and blames `validate_*` failures on unrelated causes.
2026-04-24 · #llm #prompt · Never gate a tool's prompt section on "entity exists" — the LLM can never create the first entity because the keyword hints are hidden. Register the tool, always inject the section.
2026-04-24 · #schema #auth · When a fix broadens who can write to a table (e.g. BUG-002: owner-only → any member), re-check every uniqueness / default / scoping invariant downstream; a per-user existence check becomes wrong the moment multiple users share the scope.
2026-04-24 · #reporting #hook · Orchestrator must write `.cleargate/sprint-runs/.active` with sprint ID at kickoff; otherwise SubagentStop hook drops every row and REPORT.md has no ledger.
2026-04-24 · #test-harness #fastapi · `with TestClient(app) as client:` deadlocks under pytest-asyncio auto mode — lifespan spawns drive/wiki/automation cron loops; use bare `TestClient(app)` for mock-heavy tests (pattern from `test_auth_routes.py`).
2026-04-24 · #vitest #test-harness · Button whose label flips on `isPending` — render with `isPending: false`, click, then `rerender` with `isPending: true` to assert spinner; setting it true before first render disables the button.
2026-04-24 · #vitest #test-harness · Prefer `getByLabelText` over `getByDisplayValue('')`; empty-value queries are ambiguous whenever a form has multiple empty inputs.
2026-04-24 · #frontend #epic-018 · EPIC-018 dry-run endpoint is POST /automations/test-run (prompt-only body), NOT /{aid}/dry-run — declared before /{automation_id}.
2026-04-15 · #qa #process · [S] V-Bounce: 2 consecutive Dev-agent timeouts on a story = Team Lead implements directly, do not spawn a 3rd.
2026-04-15 · #qa · Sprint plans with 3+ stories touching agent.py mark it red-zone in §2 Shared Surface Warnings; merges need review.
2026-04-15 · #qa #recipe #ambiguity · L3 stories tuning LLM prompts need an AI judge harness in §3 (≥5 fixtures, 3-7 criteria, ≥3.5 pass) as QA gate.
2026-04-13 · #drive · Google `drive.file` scope can't refresh-token-read Picker-selected files; use `drive.readonly` for backend refresh flows.
2026-04-13 · #fastapi · Never `from __future__ import annotations` in FastAPI routes — stringified annotations break DI/body resolution; use `Optional[str]`.
2026-04-13 · #drive #auth · Google refresh tokens are NOT Bearer credentials; POST `/token` `grant_type=refresh_token` first, use resulting access_token.
2026-04-13 · #schema #test-harness · Hermetic Supabase mocks don't validate column names; verify new `.select()`/`.eq()` cols against live migration SQL pre-commit.
2026-04-13 · #process #frontend · [S] Frontend worktree checkout is clean (no node_modules); run `npm install` in worktree/frontend before build/test.
2026-04-12 · #fastapi #frontend · Starlette `StaticFiles(html=True)` is NOT an SPA fallback — add explicit catch-all GET/HEAD `{path:path}` returning index.html.
2026-04-12 · #fastapi · Starlette `@app.get` doesn't auto-handle HEAD; healthcheck endpoints need `@app.api_route(methods=['GET','HEAD'])`.
2026-04-12 · #schema #fastapi · Supabase `.select("id")` fails on tables without `id` PK (ADR-024); use `.select("*").limit(0)` for column-agnostic probes.
2026-04-12 · #process · [S] V-Bounce worktrees: use relative paths only — absolute `/Users/...` edits land on main repo's branch, breaking isolation.
2026-04-12 · #fastapi #test-harness · `import httpx` at module level in FastAPI routes so tests can `monkeypatch module.httpx.AsyncClient`; never inside handlers.
2026-04-12 · #schema · Supabase `.upsert()` writes every payload key; omit columns with DB `DEFAULT NOW()` entirely to preserve values on update.
2026-04-12 · #auth · `base64.urlsafe_b64decode` needs padding: `raw + "=" * (-len(raw) % 4)`; `secrets.token_urlsafe(32)` emits 43 unpadded chars.
2026-04-12 · #slack · `slack_bolt.AsyncApp` param is `request_verification_enabled` (NOT `token_verification_enabled`) in 1.28.x.
2026-04-12 · #slack · Hardened `/api/slack/events` returns bare 400 `Response` (no JSON detail) on malformed JSON; don't assert body shape.
2026-04-12 · #vitest #test-harness · vitest@2.1.9 + vite@8 type clash (ProxyOptions): keep vitest.config.ts separate from vite.config.ts, import from 'vitest/config'.
2026-04-12 · #vitest #frontend · @testing-library/react auto-cleanup needs `test.globals: true` in vitest.config — else DOM leaks across tests.
2026-04-12 · #process #test-harness · [S] Before backend tests in V-Bounce worktree: `cp .env .worktrees/STORY-{ID}/.env` — pydantic-settings uses parents[3].
2026-04-12 · #vitest #frontend · jsdom lacks `HTMLDialogElement.showModal()`; use div-overlay modal pattern for Vitest-tested components.
2026-04-12 · #frontend · TanStack file-based layout routes MUST render `<Outlet />`; move page content to `foo.index.tsx` when adding `foo.bar.tsx`.
2026-04-12 · #frontend #process · Salvaging frontend from stale branches: re-verify every URL against current backend routes — hermetic tests miss mismatches.
2026-04-11 · #process #ambiguity · Quote Charter §3.2 verbatim in sprint-context Locked Dependencies; never paraphrase version pins from memory.
2026-04-11 · #ui · Tailwind 4 `@theme` declares custom tokens only — slate/zinc/red/blue ship by default; redefining warns + no-ops.
2026-04-11 · #frontend #recipe · All frontend fetches via useQuery/useMutation calling typed functions in `frontend/src/lib/api.ts`; never raw fetch().
2026-04-11 · #schema #fastapi · Backend `/api/health` shape: `{status, service, database:{per-table}}`; add new tables to `TEEMO_TABLES` when migrating.
2026-04-11 · #auth · bcrypt 5.0 raises `ValueError` on passwords >72 bytes (not silent truncation); validate at `/api/auth/register` → 422.
2026-04-11 · #auth · Tee-Mo auth cookies `samesite=lax` (not strict) — OAuth redirects drop Strict; JSON-body rule provides CSRF cover.
2026-04-11 · #test-harness #auth · Pydantic `EmailStr` rejects .test TLD; use `LaxEmailStr` for request models exercised by integration tests (or `@example.com`).
2026-04-11 · #vitest #test-harness · Vitest 2.x AST-hoists `vi.mock` above local consts; wrap spies in `vi.hoisted(() => ({ spy: vi.fn() }))` to avoid TDZ.
2026-04-11 · #frontend #ci · After adding `routes/*.tsx`, run `vite build` first (regenerates routeTree.gen.ts) before `npm run build`; never hand-edit the gen file.
