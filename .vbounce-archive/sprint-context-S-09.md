---
sprint_id: "S-09"
created: "2026-04-13"
last_updated: "2026-04-13"
---

# Sprint Context: S-09

> Cross-cutting rules for ALL agents in this sprint. Read this before starting any work.

## Design Tokens & UI Conventions

- **Color palette**: Brand coral `brand-500` = `#F43F5E` (from Tailwind 4 `@theme`). Slate neutrals for text/bg. NO hardcoded hex — use Tailwind classes: `text-brand-500`, `bg-brand-50`, `text-slate-700`, etc.
- **Typography**: Inter (sans-serif), JetBrains Mono (monospace). Max font-weight: `font-semibold`. No `font-bold` or `font-black`.
- **Spacing rhythm**: Tailwind default 4px base (4/8/12/16/24/32px scale). Use `gap-*`, `px-*`, `py-*` classes.
- **Component patterns**: Use existing `Button` component from `frontend/src/components/ui/Button.tsx` for all buttons. Use existing `Card` and `Badge` from `frontend/src/components/ui/`. Do NOT use `<button>` with inline Tailwind for button-like elements.
- **Modals**: Use div-based overlay pattern (jsdom does not implement `<dialog>.showModal()`). See `CreateWorkspaceModal.tsx` for canonical pattern.
- **No shadcn, no MUI, no Framer Motion** (ADR-022 exclusions).
- **Design guide**: `product_plans/strategy/tee_mo_design_guide.md` — reference for mockups and component specs.

## Shared Patterns & Conventions

- All API calls go through `frontend/src/lib/api.ts` typed wrappers. NEVER call `fetch` directly from components.
- Data fetching uses TanStack Query (`useQuery` / `useMutation`). Never instantiate a second `QueryClient`.
- Backend routes use `from app.core.db import get_supabase` — never instantiate `create_client()` ad-hoc.
- All `teemo_*` tables added to `TEEMO_TABLES` tuple in `backend/app/main.py`.
- Auth cookies: `samesite="lax"` (deliberate for OAuth redirects). Do NOT change to `strict`.
- TanStack Router: layout routes MUST render `<Outlet />`. Adding a child route makes the parent a layout.
- After creating new files in `frontend/src/routes/`, run `vite build` first to regenerate `routeTree.gen.ts`, then run `tsc -b && vite build`.
- `httpx` imported at module level in route files (for monkeypatch in tests).
- Never use `from __future__ import annotations` in FastAPI route files (breaks runtime type resolution).

## Locked Dependencies

| Package | Version | Reason |
|---------|---------|--------|
| react | ^19.2.5 | Charter §3.2 |
| tailwindcss | ^4.2.0 | Charter §3.2 |
| vite | ^8.0.8 | Charter §3.2 |
| @tanstack/react-router | ^1.127.1 | Charter §3.2 |
| @tanstack/react-query | ^5.75.5 | Charter §3.2 |
| pydantic-ai | ^1.79 | Charter §3.2 |
| supabase | 2.28.3 | Charter §3.2 — v3 pre-release, stay on 2.x |
| slack-bolt | 1.28.0 | Charter §3.2 |

## Active Lessons (Broad Impact)

- **[S-01]** Sprint context locked deps must quote Charter §3.2 verbatim. Do NOT work from memory.
- **[S-01]** `@theme` declares custom tokens only. Tailwind 4 built-in palettes (slate, etc.) come free.
- **[S-04]** Vitest 2.x `vi.mock` hoisting TDZ — use `vi.hoisted(...)` for mock variables in test files.
- **[S-04]** `vitest@2.1.9 + vite@8` — keep Vitest config in separate `vitest.config.ts` to avoid `ProxyOptions` type conflict.
- **[S-04]** RTL auto-cleanup requires `globals: true` in vitest config.
- **[S-05]** jsdom does not implement `HTMLDialogElement.showModal()` — use div overlay modals.
- **[S-05]** Layout routes must render `<Outlet />`. Check before adding nested routes.
- **[S-05]** Worktree `.env` — copy `.env` to worktree root before running backend tests.
- **[S-08]** Frontend worktrees need `npm install` before `vite build`.
- **[S-08]** Hermetic mocks hide column-name mismatches — verify against live schema.

## Sprint-Specific Rules

- **sonner toast migration**: STORY-008-04 installs `sonner` and replaces `FlashBanner` in `app.index.tsx`. All 5 existing Slack OAuth notification variants (`ok`, `cancelled`, `expired`, `error`, `session_lost`) MUST be preserved as sonner toast equivalents. Zero notification regressions.
- **Merge order is strict**: 008-04 → 008-02 → 008-01 → 008-03 → 008-05. Each later story builds on patterns established by earlier ones.
- **WorkspaceCard.tsx shared surface**: 008-01 extracts KeySection (structural), 008-03 adds channel chips (content). Merge 008-01 before 008-03.
- **Use worktree-relative paths for ALL edits.** NEVER use absolute paths starting with `/Users/ssuladze/...`. Absolute paths skip the worktree and land on the main repo's branch.

## Change Log

| Date | Change | By |
|------|--------|-----|
| 2026-04-13 | Sprint context created | Team Lead |
