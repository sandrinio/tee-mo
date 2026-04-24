---
sprint_id: "S-06"
created: "2026-04-12"
last_updated: "2026-04-12"
---

# Sprint Context: S-06

> Cross-cutting rules for ALL agents in this sprint. Read this before starting any work.

## Design Tokens & UI Conventions
> Applies to STORY-004-04 (Key Section UI).

- **Color palette**: Brand coral `#F43F5E` (`text-rose-500` / `bg-rose-500`), slate neutrals, per ADR-022
- **Typography**: Inter (body/headings), JetBrains Mono (code/key masks)
- **Component patterns**: Div overlay modals (NOT native `<dialog>` — jsdom doesn't implement `showModal()`)
- **Icons**: Lucide React (`CheckCircle2`, `AlertCircle`, `Key`, `Eye`, `EyeOff`)
- **Button styling**: Reuse existing button patterns from S-05 WorkspaceCard (rename/delete buttons)

## Shared Patterns & Conventions

- **All API calls** go through `frontend/src/lib/api.ts` typed wrappers — never raw `fetch` in components
- **All frontend data fetching** uses TanStack Query (`useQuery` / `useMutation`) — never raw fetch hooks
- **All backend DB access** uses `from app.core.db import get_supabase` — never ad-hoc `create_client()`
- **All encryption** uses `from app.core.encryption import encrypt, decrypt` — never direct `cryptography` calls
- **httpx imports** at module level (NOT inside functions) so tests can monkeypatch
- **Ownership filter** `.eq("user_id", user_id)` on every workspace query — never skip
- **Worktree-relative paths** for ALL Edit/Write tool calls — NEVER use absolute paths starting with `/Users/`

## Locked Dependencies
> From Charter §3.2. Copy verbatim — do NOT change versions.

| Package | Version | Reason |
|---------|---------|--------|
| `fastapi` | `0.135.0` | Charter §3.2 |
| `pydantic` | `2.11.3` | Charter §3.2 |
| `supabase` | `2.28.3` | Charter §3.2, ADR-015 (not 3.0 pre-release) |
| `cryptography` | `46.0.0` | Charter §3.2, ADR-002 |
| `httpx` | `0.28.1` | Charter §3.2 |
| `vite` | `^8.0.8` | Charter §3.2 |
| `@tanstack/react-query` | `^5.75.5` | Charter §3.2 |
| `vitest` | `^2.1.9` | Charter §3.2 |

## Active Lessons (Broad Impact)
> FLASHCARDS.md entries that affect multiple stories in this sprint.

- **[S-04] httpx module-level import**: `import httpx` at top of module for test monkeypatching. `monkeypatch.setattr(module.httpx, "AsyncClient", FakeAsyncClient)`.
- **[S-04] Supabase `.upsert()` — omit `DEFAULT NOW()` columns**: Don't pass `installed_at`, `created_at`, etc. in payload dicts.
- **[S-04] base64url padding**: Any base64url from `.env` needs `padded = raw + "=" * (-len(raw) % 4)` before decode.
- **[S-05] Worktree `.env` placement**: Copy `.env` to worktree root before running backend tests.
- **[S-05] jsdom doesn't implement `showModal()`**: Use div overlay modals, not native `<dialog>`.
- **[S-05] Vitest `vi.hoisted()`**: When `vi.mock` factory closes over a variable, wrap in `vi.hoisted(...)`.
- **[S-05] Frontend API URLs must match backend routes**: Cross-check every URL in frontend code against actual backend route definitions.

## Sprint-Specific Rules

- **Copy source available**: Stories 004-01 and 004-02 strip from `new_app/`. Dev agents should read `new_app/` source files listed in the story §3 before implementing.
- **Key mask is stored, not computed at read time**: `key_mask` column (migration 008) stores the computed mask alongside `encrypted_api_key`. `GET /api/workspaces/{id}/keys` reads from this column — no decryption needed at read time.
- **Plaintext key NEVER in responses or logs**: ADR-002 hard rule. Pydantic models strip the key field from `__repr__`. Routes return `KeyResponse` (has `key_mask`, not `key`).
- **Default model per provider**: `google` → `gemini-2.5-flash`, `openai` → `gpt-4o`, `anthropic` → `claude-sonnet-4-6` (Charter §3.4).
- **No Risk Registry file exists** — risk flags are tracked in the sprint plan §2 only.

## Change Log

| Date | Change | By |
|------|--------|-----|
| 2026-04-12 | Sprint context created | Team Lead |
