---
sprint_id: "S-07"
created: "2026-04-12"
last_updated: "2026-04-12"
---

# Sprint Context: S-07

> Cross-cutting rules for ALL agents in this sprint. Read this before starting any work.

## Design Tokens & UI Conventions
> No frontend UI work in this sprint — all backend.

## Shared Patterns & Conventions

- **Supabase access**: Always use `from app.core.db import get_supabase` — never instantiate a client directly.
- **Encryption**: Decrypt keys/tokens via `from app.core.encryption import decrypt`. Never call AESGCM directly.
- **Auth dependency**: Protected routes use `Depends(get_current_user_id)` from `app.api.deps`.
- **Table prefix**: All tables use `teemo_` prefix (shared Supabase instance).
- **httpx/Slack client imports at module level**: Per FLASHCARDS.md S-04 lesson, import `httpx` and `slack_sdk` at the module top so tests can monkeypatch.
- **Module separation**: `backend/app/agents/` must NOT import anything from `fastapi`. The agent system is isolated from the HTTP layer. `backend/app/services/slack_dispatch.py` bridges the two.
- **Error responses from Slack dispatch**: Post errors to Slack thread as user-friendly messages. Never expose stack traces, workspace IDs, or key material.

## Locked Dependencies

| Package | Version | Reason |
|---------|---------|--------|
| `pydantic-ai[openai,anthropic,google]` | `1.79.0` | Charter §3.2 pin |
| `slack-bolt` | `1.28.0` | Charter §3.2 pin |
| `cryptography` | `46.0.7` | Charter §3.2 pin — AES-256-GCM via AESGCM |
| `fastapi[standard]` | `0.135.3` | Charter §3.2 pin |
| `supabase` | `2.28.3` | Charter §3.2 pin — NOT 3.0 pre-release |

## Active Lessons (Broad Impact)

- **[S-04] `httpx.AsyncClient` first use**: Import at module level so tests can monkeypatch. See FLASHCARDS.md "Slack OAuth (S-04)".
- **[S-04] `slack_bolt.AsyncApp` uses `request_verification_enabled`, NOT `token_verification_enabled`**: Constructor param name matters.
- **[S-04] Supabase `.upsert()` — omit `DEFAULT NOW()` columns**: Don't pass `installed_at`, `bound_at`, `created_at` in upsert payloads.
- **[S-04] `base64.urlsafe_b64decode` needs padding**: Apply `raw + "=" * (-len(raw) % 4)` before decode.
- **[S-03] `select("*")` not `select("id")` in health checks**: Not all tables have an `id` column.

## Sprint-Specific Rules

- **First-use of Pydantic AI**: STORY-007-02 introduces `pydantic_ai.Agent` for the first time. Copy the exact `_build_pydantic_ai_model` and `_ensure_model_imports` patterns from `Documents/Dev/new_app/backend/app/agents/orchestrator.py`. Do not improvise the model instantiation.
- **First-use of `AsyncWebClient`**: STORY-007-03 uses `slack_sdk.web.async_client.AsyncWebClient` directly (not via Bolt). Test with a hand-rolled `FakeAsyncWebClient` class.
- **No `asyncio.create_task` in tests**: The dispatch background task pattern makes direct assertion hard. Test the dispatch function directly, test the endpoint separately for immediate 200 response.
- **Worktree `.env` copy**: Copy project root `.env` to each worktree root before running backend tests (FLASHCARDS.md S-05 lesson).

## Change Log

| Date | Change | By |
|------|--------|-----|
| 2026-04-12 | Sprint context created | Team Lead |
