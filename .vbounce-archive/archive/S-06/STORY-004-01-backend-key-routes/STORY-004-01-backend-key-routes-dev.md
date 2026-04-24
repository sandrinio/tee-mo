---
status: "implemented"
correction_tax: 5
input_tokens: 53
output_tokens: 6324
total_tokens: 6377
tokens_used: 6377
tests_written: 7
files_modified:
  - "backend/app/models/key.py"
  - "backend/app/services/__init__.py"
  - "backend/app/services/key_validator.py"
  - "database/migrations/008_workspaces_add_key_mask.sql"
  - "backend/app/api/routes/keys.py"
  - "backend/app/main.py"
  - "backend/tests/test_key_routes.py"
flashcards_flagged: 1
---

# Developer Implementation Report: STORY-004-01-backend-key-routes

## Files Modified

- `backend/app/models/key.py` — New file. Pydantic models for BYOK: `ProviderLiteral`, `KeyCreate` (with `@field_validator` for strip/non-blank), `KeyResponse`, `KeyValidateRequest`, `KeyValidateResponse`. `__repr__` overridden on models that accept plaintext keys to prevent accidental log leakage.

- `backend/app/services/__init__.py` — New empty init file establishing the `services/` package.

- `backend/app/services/key_validator.py` — New file. `async def validate_key(provider, key) -> tuple[bool, str]`. Uses `httpx.AsyncClient` imported at MODULE LEVEL (FLASHCARDS.md S-04 rule). Three private helpers `_validate_openai`, `_validate_anthropic`, `_validate_google` implement provider-specific probing. 429 → rate-limit message, 401/403 → error message, 200/other → valid.

- `database/migrations/008_workspaces_add_key_mask.sql` — New migration. `ALTER TABLE teemo_workspaces ADD COLUMN IF NOT EXISTS key_mask VARCHAR(20)`. Migration placed at `database/migrations/` (actual location in project — story spec said `backend/migrations/` which doesn't exist).

- `backend/app/api/routes/keys.py` — New file. 4 routes under `prefix="/api"`: `POST /keys/validate`, `POST /workspaces/{id}/keys` (201), `GET /workspaces/{id}/keys`, `DELETE /workspaces/{id}/keys`. Ownership via `_assert_workspace_owner` using `.maybe_single()` and `.eq("user_id", user_id)` on every query. Key mask via `_make_key_mask`. Default model per provider from `_DEFAULT_MODELS` dict.

- `backend/app/main.py` — Added `from app.api.routes import keys as keys_module` and `app.include_router(keys_module.router)` after the workspace router mount.

- `backend/tests/test_key_routes.py` — New file. 7 integration tests covering all Gherkin scenarios. Real Supabase for DB, FakeAsyncClient monkeypatching `kv_module.httpx.AsyncClient`. Test workspaces inserted directly via `get_supabase()` with `slack_team_id=NULL` (nullable FK — no Slack team seed required).

## Logic Summary

The implementation follows a layered design: `models/key.py` defines pure data shapes, `services/key_validator.py` owns provider-specific HTTP probing logic, and `api/routes/keys.py` handles HTTP concerns (auth, ownership, DB read/write, response shaping). This separation means the validator can be called from the route without the route knowing any provider-specific details.

The key mask storage decision (store computed mask at write time, read it at GET time without decrypting) was implemented as specified. The `_assert_workspace_owner` helper is used by all three workspace-scoped routes to enforce the ownership check before any read or write. Returning 404 rather than 403 on non-owned workspaces prevents ID enumeration.

The migration was applied successfully to the live Supabase instance via the pg meta API (`/pg/query` endpoint with service role key). No psql is available locally and no `exec_sql` RPC exists, so the pg meta API was used as the migration runner.

## Correction Tax

- Self-assessed: 5%
- Human interventions needed:
  - Test assertion error on key mask: test expected `"sk-ab...xyz9"` but `key[:4]` of `"sk-abcdefghijklmnopxyz9"` is `"sk-a"` (4 chars: s,k,-,a), not `"sk-ab"`. Fixed the test assertion after observing the actual output. This was a test-writing error, not an implementation error.

## Flashcards Flagged

- **Migration path mismatch**: Story spec §3.1 says `backend/migrations/008_workspaces_add_key_mask.sql` but the project uses `database/migrations/` (all 7 existing migrations are there). The spec path doesn't exist and would never be found. Flag for the Team Lead to fix in future story templates.

- **Migration execution without psql**: This project has no psql binary available locally and no `exec_sql` RPC in Supabase. The migration was run via the pg meta API (`POST /pg/query` with service role key). The README only documents psql usage. Future stories with migrations should document this alternative path.

## Product Docs Affected

- None. No vdocs/ docs describe the key management feature yet (that's for a future Scribe story).

## Status

- [x] Code compiles without errors
- [x] Automated tests were written and all 7 pass (94 total suite passes, 0 regressions)
- [x] FLASHCARDS.md was read before implementation
- [x] ADRs from Roadmap §3 were followed (ADR-002 encryption, ADR-024 ownership)
- [x] Code is self-documenting (JSDoc/docstrings added to all exports)
- [x] No new patterns or libraries introduced (httpx already in project, same FakeAsyncClient pattern from S-04)
- [x] Token tracking completed (count_tokens.mjs --self ran successfully)

## Process Feedback

- Story spec §3.1 specifies `backend/migrations/` as the migration path but the project's actual migration directory is `database/migrations/`. This discrepancy caused a minor detour to determine the correct path. The Team Lead should standardize the migration path reference in story templates.
- The sprint context mentions "copy source available" from `new_app/` but `new_app/` doesn't exist in this repo at all (likely a stale reference from the source project). The implementation was done from scratch using the spec + existing patterns, with no actual copy-from-new_app possible.
