---
story_id: "STORY-004-01"
parent_epic_ref: "EPIC-004"
status: "Shipped"
ambiguity: "🟢"
context_source: "PROPOSAL-001-teemo-platform.md"
complexity_label: "L2"
parallel_eligible: false
expected_bounce_exposure: "low"
approved: true
created_at: "2026-04-12T00:00:00Z"
updated_at: "2026-04-12T00:00:00Z"
created_at_version: "vbounce-backlog"
updated_at_version: "cleargate-migration-2026-04-24"
server_pushed_at_version: null
draft_tokens:
  input: null
  output: null
  cache_read: null
  cache_creation: null
  model: null
  sessions: []
cached_gate_result:
  pass: null
  failing_criteria: []
  last_gate_check: null
---

> **Ported from V-Bounce (shipped).** Original: `product_plans.vbounce-archive/archive/sprints/sprint-06/STORY-004-01-backend-key-routes.md`. Shipped in sprint S-06, carried forward during ClearGate migration 2026-04-24.

# STORY-004-01: Backend Key Routes + Models + Validator

## 1. The Spec

### 1.1 Goal
Ship 4 backend routes for workspace-scoped BYOK key management + the supporting Pydantic models + the live provider validation service. This gives the frontend a complete key CRUD surface and unlocks STORY-004-02 (resolvers).

### 1.2 Routes to implement

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/keys/validate` | Required | Probe provider API with a plaintext key — never stores it |
| `POST` | `/api/workspaces/{workspace_id}/keys` | Required | Encrypt + store key + provider + model on workspace row |
| `GET` | `/api/workspaces/{workspace_id}/keys` | Required | Return masked key, provider, has_key status |
| `DELETE` | `/api/workspaces/{workspace_id}/keys` | Required | NULL out encrypted_api_key, ai_provider, ai_model |

### 1.3 What is COPY, what is NEW

| Item | Action | Source |
|------|--------|--------|
| `backend/app/models/key.py` | **Copy + strip** | `new_app/backend/app/models/key.py` — keep `KeyCreate` (add optional `ai_model`), `KeyResponse`, `KeyValidateRequest`, `KeyValidateResponse`. **Remove**: `KeyRename`, `scope`, `editable` fields, instance-key logic |
| `backend/app/api/routes/keys.py` | **Copy + strip** | `new_app/backend/app/api/routes/keys.py` — keep `_make_key_mask`, validate route, create route (simplified), get route, delete route. **Remove**: `update_key`, `rename_key`, `activate_key`, `get_key_impact`, instance-key logic |
| `backend/app/services/key_validator.py` | **Copy + strip** | `new_app/backend/app/services/key_validator.py` — copy `validate_key(provider, key)` function wholesale |
| `backend/app/main.py` | **Modify** | Mount new `keys_router` — one `include_router()` call |

---

## 2. The Truth (Acceptance Criteria)

```gherkin
Feature: BYOK Key Routes

  Scenario: POST /api/keys/validate — valid OpenAI key
    Given the user is authenticated
    When POST /api/keys/validate {provider: "openai", key: "sk-...valid..."}
    Then response 200 {valid: true, message: "Valid"}
    And no row is written to teemo_workspaces

  Scenario: POST /api/keys/validate — invalid key
    Given the user is authenticated
    When POST /api/keys/validate {provider: "anthropic", key: "bogus-key"}
    Then response 200 {valid: false, message: "<error description>"}
    And rate-limit errors return {valid: false, message: "Rate limited — try again shortly"}

  Scenario: POST /api/workspaces/{id}/keys — saves key successfully
    Given the user is authenticated and owns workspace W1
    When POST /api/workspaces/W1/keys {provider: "openai", key: "sk-...valid...", ai_model: "gpt-4o"}
    Then response 201 {provider: "openai", key_mask: "sk-a...xyz9", has_key: true, ai_model: "gpt-4o"}
    And teemo_workspaces set: encrypted_api_key = AES(key), ai_provider = "openai", ai_model = "gpt-4o"
    And plaintext key NOT in response body or logs

  Scenario: POST /api/workspaces/{id}/keys — workspace not owned by caller
    Given the user is authenticated but does NOT own workspace W2
    When POST /api/workspaces/W2/keys {provider: "openai", key: "..."}
    Then response 404

  Scenario: GET /api/workspaces/{id}/keys — key exists
    Given workspace W1 has encrypted_api_key set, ai_provider = "openai"
    When GET /api/workspaces/W1/keys
    Then response 200 {provider: "openai", key_mask: "sk-a...xyz9", has_key: true}

  Scenario: GET /api/workspaces/{id}/keys — no key
    Given workspace W1 has encrypted_api_key = NULL
    When GET /api/workspaces/W1/keys
    Then response 200 {has_key: false, provider: null, key_mask: null}

  Scenario: DELETE /api/workspaces/{id}/keys
    Given workspace W1 has a key set
    When DELETE /api/workspaces/W1/keys
    Then response 200 {message: "Key deleted"}
    And teemo_workspaces: encrypted_api_key = NULL, ai_provider = NULL, ai_model = NULL
```

---

## 3. Implementation Guide

### 3.1 New files to create

**`backend/app/models/key.py`** — stripped from new_app:

```python
ProviderLiteral = Literal["google", "openai", "anthropic"]

class KeyCreate(BaseModel):
    provider: ProviderLiteral
    key: str
    ai_model: str | None = None

class KeyResponse(BaseModel):
    provider: str
    key_mask: str
    has_key: bool
    ai_model: str | None = None

class KeyValidateRequest(BaseModel):
    provider: ProviderLiteral
    key: str

class KeyValidateResponse(BaseModel):
    valid: bool
    message: str
```

**`backend/app/services/key_validator.py`** — copy from new_app:
- Function signature: `async def validate_key(provider: str, key: str) -> tuple[bool, str]`
- Probe strategy per provider:
  - `openai`: `GET https://api.openai.com/v1/models` with `Authorization: Bearer {key}` — expect 200
  - `anthropic`: `POST https://api.anthropic.com/v1/messages` minimal payload — look for non-401/403
  - `google`: `GET https://generativelanguage.googleapis.com/v1beta/models?key={key}` — expect 200
- Use `httpx.AsyncClient`
- Catch HTTP errors; map 429 to `(False, "Rate limited — try again shortly")`

### 3.2 Key mask storage decision

Add a `key_mask` column to `teemo_workspaces` via a new migration `008_workspaces_add_key_mask.sql`:
```sql
ALTER TABLE teemo_workspaces ADD COLUMN IF NOT EXISTS key_mask VARCHAR(20);
```
Store the computed mask alongside `encrypted_api_key` on every `POST /api/workspaces/{id}/keys` call. Clear it to NULL on delete.

### 3.3 Default model per provider (if `ai_model` not supplied)
| Provider | Default `ai_model` |
|----------|-------------------|
| `google` | `"gemini-2.5-flash"` |
| `openai` | `"gpt-4o"` |
| `anthropic` | `"claude-sonnet-4-6"` |

### 3.4 Ownership check pattern
```python
result = (
    supabase.table("teemo_workspaces")
    .select("id, ai_provider, key_mask")
    .eq("id", workspace_id)
    .eq("user_id", user_id)
    .maybe_single()
    .execute()
)
if not result or not result.data:
    raise HTTPException(status_code=404, detail="Workspace not found")
```

### 3.5 ADR compliance
- ADR-002: AES-256-GCM via `backend/app/core/encryption.py` already shipped in S-04.
- Never call `encrypt()` / `decrypt()` outside the route handler.
- Ownership filter `.eq("user_id", user_id)` on every DB write.

---

## 4. Test Requirements

Write tests in `backend/tests/test_key_routes.py`:

1. `test_validate_valid_openai_key` — mock `httpx.AsyncClient`, return 200, assert `{valid: true}`
2. `test_validate_invalid_key` — mock returns 401, assert `{valid: false}`
3. `test_save_key_success` — saves key, checks DB has encrypted blob + mask
4. `test_save_key_ownership_enforced` — different user_id → 404
5. `test_get_key_with_key` — returns mask + provider
6. `test_get_key_no_key` — returns `{has_key: false}`
7. `test_delete_key` — NULLs out encrypted_api_key + ai_provider + ai_model

---

## Change Log
| Date | Change | By |
|------|--------|-----|
| 2026-04-12 | Story created from EPIC-004 decomposition | Claude (doc-manager) |
