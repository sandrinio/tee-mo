---
sprint_id: "S-04"
created: "2026-04-12"
last_updated: "2026-04-12"
---

# Sprint Context: S-04

> Cross-cutting rules for ALL agents in this sprint. Read this before starting any work.
>
> **Sprint Goal:** Real Slack OAuth install end-to-end. Logged-in user clicks **Install Slack** on `/app`, completes consent, lands back with a `teemo_slack_teams` row owned by them and visible in the team list. Closes the S-03 events-stub TODO with real signing-secret verification.

## Design Tokens & UI Conventions

> Only STORY-005A-06 touches UI. Reuse existing conventions — do not introduce new design tokens.

- **Component library**: reuse existing TanStack Router + shadcn-style components already in `frontend/src/components/`. No new UI primitives this sprint.
- **Flash banners**: the 5 redirect-query-param banner variants (`slack_success`, `slack_error=user_denied|state_invalid|ok_false|http_error|unknown`) live in a single `BANNER_VARIANTS` lookup in `app.tsx`. Do NOT spread banner copy across files.
- **Install button**: render as a plain `<a href="/api/slack/install">`, NOT a button with `onClick`. The backend redirect needs a full-page navigation so the `Authorization` cookie rides along.

## Shared Patterns & Conventions

- **All Tee-Mo tables carry the `teemo_` prefix.** We share a self-hosted Supabase instance with other projects — do not create bare `slack_teams` or `installations` tables.
- **All Supabase access goes through `from app.core.db import get_supabase`** (service-role, cached). Do NOT instantiate fresh clients or use the anon key.
- **Explicit column selects only on read paths that touch `teemo_slack_teams`.** NEVER use `.select("*")` — the table contains `encrypted_slack_bot_token` which MUST NOT leak to API responses (ADR-010). Every read specifies columns by name.
- **JWT auth via `_JWT` module-local instance in `backend/app/core/security.py`.** `create_slack_state_token` / `verify_slack_state_token` reuse this instance — do NOT instantiate a second PyJWT object.
- **AES-256-GCM via `cryptography.hazmat.primitives.ciphers.aead.AESGCM`** (ADR-002). Nonce is 12 bytes of `os.urandom(12)`; ciphertext is stored as `nonce || ciphertext || tag` base64-encoded. Exactly one encrypt/decrypt helper pair in `backend/app/core/encryption.py`.
- **Settings validator must raise `ValueError` at import time** if `TEEMO_ENCRYPTION_KEY` is missing or not a valid 32-byte key. Fail fast at container start, not at first encryption call.
- **Outbound HTTP uses `httpx.AsyncClient`** (first use). The S-04 story §3 guides include a hand-rolled mock pattern for tests — reuse it verbatim across 005A-04 tests to keep one canonical shape.
- **Self-documenting code.** Every new export (function, class, Pydantic model) gets a docstring.
- **Health check is column-agnostic.** Do NOT regress the `ce7c0b1` fix — any new `teemo_*` table added this sprint must be queryable by the health probe without assuming an `id` column (fallback query already in place; just verify nothing re-hardcodes `.select("id")`).

## Locked Dependencies

| Package | Version | Reason |
|---------|---------|--------|
| `slack-bolt` | `1.28.x` (the version pinned in `backend/pyproject.toml`) | AsyncAssistant surface deferred to EPIC-005 Phase B. No upgrade this sprint. |
| `cryptography` | current pin | AES-256-GCM API locked; do not bump for an unrelated reason. |
| `httpx` | current pin | First-use in this sprint — stable API is assumed. |
| `slack-sdk` / any new Slack client | — | **Do not add.** slack-bolt already includes `WebClient`; use that. |

## Active Lessons (Broad Impact)

Copied from FLASHCARDS.md — directly affect S-04 stories:

- **[2026-04-11] Health check is column-agnostic.** New ADR-024 tables (`teemo_slack_teams` with `slack_team_id` PK, `teemo_workspace_channels` with `slack_channel_id` PK) have no `id` column. The fallback probe in `backend/app/main.py` handles this — do NOT revert the fix in `ce7c0b1`.
- **[2026-04-11] `get_supabase()` is the only Supabase factory.** Service-role, `@lru_cache`-wrapped. New Slack code imports from `app.core.db` — do not re-instantiate clients.
- **[2026-04-11] `samesite="lax"` on auth cookies is deliberate.** EPIC-005 (this sprint) redirects back to the frontend after Slack OAuth. Strict would drop the auth cookie on the return hop. Do not "harden" to strict.
- **[2026-04-12] `teemo_` table prefix is mandatory.** Shared Supabase instance. Any new table in this sprint is `teemo_slack_*` / `teemo_workspace_*`, never a bare name.

## Sprint-Specific Rules

- **No out-of-scope pulls.** The Slack AI Apps surface (`AsyncAssistant`) is **deferred to EPIC-005 Phase B / EPIC-011**. Even though `slack_bolt` will be imported by STORY-005A-01, do NOT reach for `AsyncAssistant`, assistant handlers, thread metadata, or any "while we're here" additions. OAuth install + events stub only.
- **No BYOK key handling in `encryption.py`.** The encryption helper built in STORY-005A-01 will later be reused for BYOK OpenAI/Anthropic keys (Release 2). This sprint it only handles Slack bot tokens. Do not add key-type parameters, multi-key support, or per-provider namespaces now.
- **Merge ordering is strict for `slack_oauth.py`:** 003 (creates file with `/install`) → 004 (adds `/oauth/callback`) → 005 (adds `/teams`). DevOps must honor this — do not re-order.
- **STORY-005A-04 is the only Full Bounce.** Dev → QA → Architect. It's security-sensitive (token encryption + cross-user check + 5 redirect branches). Architect must validate the encryption+DB composition.
- **Fast Track for the other 5 stories.** No QA/Arch gates — Dev report → DevOps merge. Trust the tests.
- **Escalation threshold:** if STORY-005A-04 hits 2 QA bounces, STOP and escalate to the user per SQ-2 in sprint plan §3. Do not push to a 3rd bounce without a human decision.
- **Key fingerprint verification:** STORY-005A-01 logs `TEEMO_ENCRYPTION_KEY` fingerprint (sha256[:8] = `aecf7b12`) at startup. DevOps verifies the same fingerprint in Coolify production logs after sprint merge. Mismatch = STOP the release.
- **Slack scope tuple is exactly 7:** `app_mentions:read, channels:history, channels:read, chat:write, groups:history, groups:read, im:history` (ADR-021 + ADR-025). No additions, no removals.
- **State token TTL is 10 minutes** and uses the module-local `_JWT` instance. Same `JWT_SECRET` env var as auth tokens.

## Change Log

| Date | Change | By |
|------|--------|-----|
| 2026-04-12 | Sprint context created at Sprint Setup step 0.7. Captures: ADR-002/010/021/024/025 compliance, strict merge ordering for `slack_oauth.py`, Full Bounce only on 005A-04, out-of-scope fences around AI Apps surface and BYOK, teemo_ prefix + Supabase factory + samesite=lax flashcards. | Team Lead |
