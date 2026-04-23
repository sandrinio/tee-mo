---
sprint_id: "S-05"
created: "2026-04-12"
last_updated: "2026-04-12"
---

# Sprint Context: S-05

> Cross-cutting rules for ALL agents in this sprint. Read this before starting any work.

## Design Tokens & UI Conventions

- **Color palette**: Neutral slate backgrounds; single coral brand accent `--color-brand-coral: #E94560`; functional colors only (success/warning/danger/info). No decorative color.
- **Typography**: Inter (sans), JetBrains Mono (mono). Max weight: `font-semibold` (600). Never `font-bold` (700).
- **Spacing rhythm**: Tailwind 4 default scale (4px base).
- **Component patterns**: Use existing `Button`, `Input` components from `frontend/src/components/ui/`. Card pattern: `bg-white rounded-lg shadow-sm border border-slate-200 p-6`.

## Shared Patterns & Conventions

- **API calls**: All frontend fetches go through TanStack Query. Typed wrappers in `frontend/src/lib/api.ts`. Never call `fetch` directly from a component. (FLASHCARDS.md)
- **Backend DB access**: Always use `from app.core.db import get_supabase`. Never instantiate `create_client()` ad-hoc. (FLASHCARDS.md)
- **Health probe**: Use `select("*").limit(0)`, NOT `select("id")` — tables have heterogeneous PKs. (FLASHCARDS.md)
- **Route registration**: Endpoints hit by healthchecks/HEAD must use `@app.api_route(..., methods=["GET", "HEAD"])`. (FLASHCARDS.md)
- **Vitest mocks**: Use `vi.hoisted(...)` for mock variables in `vi.mock` factories. (FLASHCARDS.md)
- **New routes**: After creating new `frontend/src/routes/*.tsx` files, run `vite build` first to regenerate `routeTree.gen.ts`, then `npm run build`. (FLASHCARDS.md)
- **Worktree paths**: Use worktree-relative paths for ALL edits. NEVER use absolute paths starting with `/Users/ssuladze/...`. (FLASHCARDS.md)

## Locked Dependencies

| Package | Version | Reason |
|---------|---------|--------|
| `react` + `react-dom` | 19.2.5 | Charter §3.2 |
| `tailwindcss` | 4.2.x | Charter §3.2 |
| `vite` | 8.0.8 | Charter §3.2 |
| `@tanstack/react-router` | 1.168.12 | Charter §3.2 |
| `@tanstack/react-query` | 5.97.0 | Charter §3.2 |
| `zustand` | 5.0.12 | Charter §3.2 |
| `fastapi[standard]` | 0.135.3 | Charter §3.2 |
| `supabase` (Python) | 2.28.3 | Charter §3.2 |
| `PyJWT` | 2.12.1 | Charter §3.2 |
| `bcrypt` | 5.0.0 | Charter §3.2 — passwords > 72 bytes raise ValueError |
| `slack-bolt` | 1.28.0 | Charter §3.2 |

## Active Lessons (Broad Impact)

- Supabase `.upsert()` — omit `DEFAULT NOW()` columns from payload entirely (FLASHCARDS.md)
- `base64.urlsafe_b64decode` needs padding for bare base64url from `.env` (FLASHCARDS.md)
- Starlette `StaticFiles(html=True)` is NOT a SPA fallback — use explicit catch-all route (FLASHCARDS.md)
- Pydantic `EmailStr` rejects `.test` TLD — use `LaxEmailStr` from `app.models.user` in tests (FLASHCARDS.md)

## Sprint-Specific Rules

- **S-04 regression guard**: `frontend/src/lib/api.ts` changes MUST be additive only. Do NOT modify or remove existing S-04 exports (`SlackTeam`, `SlackTeamsResponse`, `listSlackTeams`). QA validates after B04 + B05 merges.
- **Salvage protocol**: B01 and B04 reuse code from orphan branch `sprint/S-05-fasttrack` (commit `e98d378`). Use `git show e98d378:<path>` to retrieve. For `api.ts`, do NOT apply the branch diff — only copy new workspace types and wrappers additively.
- **No new dependencies**: This sprint adds no new packages. All work uses existing stack.

## Change Log

| Date | Change | By |
|------|--------|-----|
| 2026-04-12 | Sprint context created | Team Lead |
