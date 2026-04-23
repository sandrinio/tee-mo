---
sprint_id: "S-11"
created: "2026-04-13"
last_updated: "2026-04-13"
---

# Sprint Context: S-11

> Cross-cutting rules for ALL agents in this sprint. Read this before starting any work.

## Design Tokens & UI Conventions
> Only STORY-015-06 has UI work this sprint.

- **Color palette**: Brand coral `#F43F5E` (brand-500), Slate neutrals per Design Guide §2
- **Typography**: Inter for all text, JetBrains Mono for code
- **Component patterns**: Use existing components from `frontend/src/components/ui/`. Badge component already exists.
- **Design Guide**: `product_plans/strategy/tee_mo_design_guide.md` — required reading for frontend stories

## Shared Patterns & Conventions

- **API calls**: All frontend fetches go through TanStack Query (`useQuery`/`useMutation`). Typed wrappers in `frontend/src/lib/api.ts`. Never call `fetch` directly from components.
- **Supabase client**: Always use `from app.core.db import get_supabase`. Never instantiate `create_client()` ad-hoc.
- **Table naming**: All tables use `teemo_` prefix (shared self-hosted Supabase).
- **Health check probes**: Use `select("*").limit(0)`, never `select("id")` — not all tables have `id` PK.
- **Cookies**: `samesite="lax"` in auth cookies. Do not switch to `strict`.
- **httpx**: Import at module level for monkeypatch testability. Use `monkeypatch.setattr(module.httpx, "AsyncClient", ...)`.
- **Pydantic email**: Use `LaxEmailStr` from `app.models.user` for endpoints exercised by tests.
- **Upsert with DEFAULT NOW()**: Omit those columns from the payload dict entirely.
- **Base64url from .env**: Always pad before decoding: `raw + "=" * (-len(raw) % 4)`.
- **Starlette SPA fallback**: Use explicit catch-all route, NOT `StaticFiles(html=True)`.
- **Starlette HEAD**: Use `@app.api_route(..., methods=["GET", "HEAD"])` for health/catch-all endpoints.
- **New routes in TanStack Router**: Run `vite build` first to regenerate `routeTree.gen.ts` before `tsc -b && vite build`.
- **Vitest mocks**: Use `vi.hoisted(...)` for variables closed over by `vi.mock` factories.
- **Vitest config**: Keep separate `vitest.config.ts` (imports from `vitest/config`, not `vite`). Set `globals: true` for `@testing-library/react` cleanup.
- **Worktree paths**: Use worktree-RELATIVE paths for ALL edits. NEVER use absolute paths starting with `/Users/ssuladze/...`.
- **SHA-256 for content hashing**: STORY-015-01 replaces MD5 with SHA-256. All subsequent stories that hash content must use SHA-256.

## Locked Dependencies
> From Charter §9 — copy/pasted verbatim. Do NOT change these versions.

| Package | Version | Reason |
|---------|---------|--------|
| react | 19.2.5 | Charter §9 |
| tailwindcss | 4.2.x | Charter §9 |
| vite | 8.0.8 | Charter §9 |
| @tanstack/router | 1.168.12 | Charter §9 |
| @tanstack/query | 5.97.0 | Charter §9 |
| zustand | 5.0.12 | Charter §9 |
| fastapi | 0.135.3 | Charter §9 |
| pydantic-ai | 1.79.0 | Charter §9 |
| supabase (python) | 2.28.3 | Charter §9 |
| cryptography | 46.0.7 | Charter §9 |
| pyjwt | 2.12.1 | Charter §9 |
| bcrypt | 5.0.0 | Charter §9 — raises ValueError on passwords > 72 bytes |
| slack-bolt | 1.28.0 | Charter §9 |
| google-api-python-client | 2.194.0 | Charter §9 |
| google-auth | 2.49.2 | Charter §9 |

## Active Lessons (Broad Impact)

- [2026-04-12] Worktree `.env` resolves from `parents[3]` of config.py — copy `.env` to worktree root
- [2026-04-12] Agent Edit/Write with absolute paths bypass worktree isolation — use relative paths
- [2026-04-12] `supabase.table(t).select("id")` fails on tables without `id` column — use `select("*")`
- [2026-04-12] Starlette `StaticFiles(html=True)` is NOT a SPA fallback
- [2026-04-12] `slack_bolt.AsyncApp` uses `request_verification_enabled`, NOT `token_verification_enabled`
- [2026-04-11] All frontend fetches go through TanStack Query
- [2026-04-11] Vitest `vi.mock` hoisting TDZ — use `vi.hoisted(...)`

## Sprint-Specific Rules

- **STORY-015-01 is the foundation.** All other stories depend on the `teemo_documents` table and `document_service.py` it creates. Do not start Phase 2 stories until 015-01 is merged.
- **agent.py contention**: 3 stories touch `backend/app/agents/agent.py`. Merge order: 015-03 first, then 013-01, then 013-04. Each subsequent Dev must read agent.py from the sprint branch AFTER previous merges.
- **Wiki ingest uses AI judge**: STORY-013-02 has an AI-judged prompt tuning loop. Pass threshold: all 5 criteria >= 3.5 avg across 8 test files.
- **Tiny doc threshold**: Skip wiki ingest for docs < 100 chars. Set `sync_status='synced'` immediately.
- **Sequential wiki ingest**: One doc at a time per workspace. No advisory locks needed.
- **read_document fallback**: Renamed from `read_drive_file`. Wiki is primary knowledge path, raw doc is fallback for exact quotes/specific data/pending ingest.
- **No data migration**: SQL migration drops `teemo_knowledge_index`. Acceptable (no clients, no data).

## Change Log

| Date | Change | By |
|------|--------|-----|
| 2026-04-13 | Sprint context created | Team Lead |
