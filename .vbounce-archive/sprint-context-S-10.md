---
sprint_id: "S-10"
created: "2026-04-13"
last_updated: "2026-04-13"
---

# Sprint Context: S-10

> Cross-cutting rules for ALL agents in this sprint. Read this before starting any work.

## Design Tokens & UI Conventions

- **Color palette**: Brand coral `#F43F5E`, slate neutrals, Asana-inspired warm minimalism (ADR-022)
- **Typography**: Inter 600 headings, Inter 400 body, JetBrains Mono code
- **Component patterns**: Use existing components from `frontend/src/components/`. Follow patterns in `tee_mo_design_guide.md`.
- **Modals**: Use div-based overlay pattern (no native `<dialog>` — jsdom doesn't support `showModal()`)

## Shared Patterns & Conventions

- All frontend API calls go through `frontend/src/lib/api.ts` — do not use `fetch` directly
- All frontend data fetching uses TanStack Query (`useQuery` / `useMutation`) — never raw fetch in components
- All backend Supabase access goes through `backend/app/core/db.get_supabase()` — no ad-hoc `create_client()`
- New tables added to `TEEMO_TABLES` tuple in `backend/app/main.py`
- Health probes use `select("*").limit(0)` — never `select("id")` (not all tables have `id` PK)
- `samesite="lax"` on auth cookies — do not change to `strict`
- `import httpx` at module level in route files (for test monkeypatch compatibility)
- `from __future__ import annotations` is FORBIDDEN in FastAPI route files
- TanStack Router: parent routes that have children MUST render `<Outlet />`
- After adding new `src/routes/*.tsx` files, run `vite build` first to regenerate `routeTree.gen.ts`
- Vitest mocks: use `vi.hoisted(...)` for variables referenced inside `vi.mock()` factories
- Vitest config: `globals: true` required for `@testing-library/react` auto-cleanup

## Locked Dependencies
> Copied verbatim from Charter §3.2. Do NOT change versions.

| Package | Version | Reason |
|---------|---------|--------|
| react | 19.1.0 | Charter §3.2 |
| tailwindcss | 4.1.3 | Charter §3.2 |
| vite | 8.0.8 | Charter §3.2 |
| @tanstack/react-router | 1.168.12 | Charter §3.2 |
| @tanstack/react-query | 5.97.0 | Charter §3.2 |
| zustand | 5.0.12 | Charter §3.2 |
| fastapi[standard] | 0.135.3 | Charter §3.2 |
| pydantic-ai[openai,anthropic,google] | 1.79.0 | Charter §3.2 |
| supabase | 2.28.3 | Charter §3.2 |
| cryptography | 46.0.7 | Charter §3.2 |
| PyJWT | 2.12.1 | Charter §3.2 |
| bcrypt | 5.0.0 | Charter §3.2 |
| slack-bolt | 1.28.0 | Charter §3.2 |
| google-api-python-client | 2.194.0 | Charter §3.2 |
| google-auth | 2.49.2 | Charter §3.2 |

## Active Lessons (Broad Impact)

- Supabase `.upsert()` — omit `DEFAULT NOW()` columns from payload (FLASHCARD)
- `base64.urlsafe_b64decode` needs padding for bare base64url from `.env` (FLASHCARD)
- Hermetic mocks hide column-name mismatches — verify column names against migration SQL (FLASHCARD)
- Frontend worktrees need `npm install` before `vite build` (FLASHCARD)
- Worktree `.env` resolves from `parents[3]` — copy `.env` to worktree root (FLASHCARD)
- Agent Edit/Write must use worktree-relative paths, NEVER absolute paths (FLASHCARD)
- Salvaged frontend API URLs must be verified against actual backend route paths (FLASHCARD)

## Sprint-Specific Rules

- **New dependency**: `pymupdf4llm` replaces `pypdf` for PDF extraction (STORY-006-07). Pre-built wheels available for amd64 Linux.
- **Shared surface `agent.py`**: STORY-006-08 merges before STORY-006-10. Both modify `read_drive_file` tool.
- **Shared surface `drive_service.py`**: STORY-006-07 merges before STORY-006-08.
- **Shared surface `knowledge.py`**: STORY-006-10 merges before STORY-006-11.
- **All stories are Fast Track** — Dev pass only, no QA/Architect gates.

## Change Log

| Date | Change | By |
|------|--------|-----|
| 2026-04-13 | Sprint context created | Team Lead |
