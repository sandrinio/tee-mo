---
epic_id: "EPIC-004"
status: "Shipped"
children:
  - "STORY-004-01-backend-key-routes"
  - "STORY-004-02-provider-resolvers"
  - "STORY-004-03-frontend-hooks"
  - "STORY-004-04-key-section-ui"
ambiguity: "🟢"
context_source: "PROPOSAL-001-teemo-platform.md"
owner: "Solo dev"
target_date: "2026-04-14"
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
> **Ported from V-Bounce (shipped).** Original: `product_plans.vbounce-archive/archive/epics/EPIC-004_byok_key_management/EPIC-004_byok_key_management.md`. Shipped in sprint S-06, carried forward during ClearGate migration 2026-04-24.

# EPIC-004: BYOK Key Management

## 1. Problem & Value

### 1.1 The Problem
Tee-Mo's core product promise is **zero host LLM inference cost** — every API call must be charged to the user's own key. Without a way to store, validate, and retrieve the user's provider key, the AI agent cannot be called at all, and file indexing is blocked (Charter §5.2 — BYOK is the hard gate).

### 1.2 The Solution
Implement a per-workspace BYOK flow: the user selects a provider (Google / OpenAI / Anthropic), inputs their API key, and the backend validates it against the live provider API, encrypts it with AES-256-GCM, and stores it on the workspace row. A resolver module decrypts the key at inference time and returns it to the agent factory. The frontend exposes a minimal, secure key-input UI on the Workspace card.

### 1.3 Success Metrics (North Star)
- Zero plaintext key exposure in logs, DB columns, or frontend responses (Charter §2.4 + ADR-002).
- User can add/update/delete their key for any of the three providers (Google, OpenAI, Anthropic).
- Key validation rejects invalid keys before storage with a clear error.
- `resolve_provider_key(workspace_id, supabase)` returns a decrypted plaintext key from `teemo_workspaces.encrypted_api_key` — used by the agent factory in EPIC-007.
- Frontend shows a masked key (`sk-a...xyz9`) to confirm storage without revealing the plaintext.

---

## 2. Scope Boundaries

### ✅ IN-SCOPE (Build This)
- [ ] `POST /api/workspaces/{id}/keys` — encrypt and store provider key on workspace row
- [ ] `GET /api/workspaces/{id}/keys` — return key mask + provider (no plaintext, ever)
- [ ] `DELETE /api/workspaces/{id}/keys` — clear `encrypted_api_key`, `ai_provider`, `ai_model` from workspace
- [ ] `POST /api/keys/validate` — test a plaintext key against provider API without storing it
- [ ] `backend/app/core/keys.py` — `get_workspace_key(supabase, workspace_id)` resolver for non-inference paths
- [ ] `backend/app/services/provider_resolver.py` — `resolve_provider_key(workspace_id, supabase)` for inference path (called by EPIC-007 agent factory)
- [ ] Frontend: Provider selector + masked key input + Validate button + Save key flow (per workspace card)
- [ ] Frontend: `useKeyQuery` / `useSaveKeyMutation` / `useDeleteKeyMutation` hooks
- [ ] Frontend API wrappers in `lib/api.ts` for all 4 endpoints

### ❌ OUT-OF-SCOPE (Do NOT Build This)
- Instance-level fallback keys (`chy_instance_provider_keys` from new_app) — Tee-Mo is single-tenant BYOK, no org-shared keys
- Multi-key naming / `KeyRename` endpoint — one active key per workspace
- Key impact-check endpoint (`GET /api/keys/{id}/impact`) — Tee-Mo has no workspace agent config table yet (that's EPIC-007)
- `scope` / `editable` fields on `KeyResponse` — no instance keys means no scope distinction needed
- AI model selector UI (provider + model dropdowns) — the workspace already stores `ai_provider` / `ai_model`; updating those is part of this epic **only for the provider field** chosen at key save time. Full model picker is EPIC-008 (Setup Wizard).
- `last_used_at` tracking — deferred to post-hackathon

---

## 3. Context

### 3.1 User Personas
- **Workspace Owner**: A Slack workspace admin who has registered a Tee-Mo account and created at least one Workspace (EPIC-003 done). Wants to plug in their OpenAI key and start chatting.

### 3.2 User Journey (Happy Path)
```mermaid
flowchart LR
    A["User opens Workspace card"] --> B["Sees 'No API key' status"]
    B --> C["Clicks 'Add key'"]
    C --> D["Selects provider, types key, clicks Validate"]
    D --> E["Backend validates key against provider"]
    E --> F["User clicks Save → encrypted to DB"]
    F --> G["Card shows masked key + provider badge"]
    G --> H["Add File button unlocks (EPIC-006)"]
```

### 3.3 Constraints
| Type | Constraint |
|------|------------|
| **Security** | Plaintext key NEVER stored, NEVER returned to frontend, NEVER logged (ADR-002) |
| **Security** | AES-256-GCM encryption only via `backend/app/core/encryption.py` (already implemented in S-04) |
| **Security** | Key mask format: `key[:4] + "..." + key[-4:]` (or `key[:2] + "..." + key[-2:]` if ≤8 chars) |
| **Tech Stack** | Provider literal: `Literal["google", "openai", "anthropic"]` — must match DB CHECK on `ai_provider` |
| **Architecture** | Storage is on the `teemo_workspaces` row — `encrypted_api_key` + `ai_provider` + `ai_model` columns (migration 002 already has them) |
| **Dependency** | EPIC-006 (file indexing) and EPIC-007 (agent) cannot start without `resolve_provider_key` — this is the critical path gate |

---

## 4. Technical Context

### 4.1 Affected Areas
| Area | Files/Modules | Change Type |
|------|---------------|-------------|
| Backend routes | `backend/app/api/routes/keys.py` | **NEW** — 4 routes (validate, save, get, delete) |
| Backend models | `backend/app/models/key.py` | **NEW** — `KeyCreate`, `KeyResponse`, `KeyValidateRequest`, `KeyValidateResponse` (stripped from new_app) |
| Backend service | `backend/app/core/keys.py` | **NEW** — `get_workspace_key()` resolver |
| Backend service | `backend/app/services/provider_resolver.py` | **NEW** — `resolve_provider_key()` inference resolver |
| Backend services dir | `backend/app/services/` | **NEW dir** — create this directory |
| Backend key validator | `backend/app/services/key_validator.py` | **NEW** — live provider probe (`validate_key()`) |
| Backend routes mount | `backend/app/main.py` | **MODIFY** — mount `keys_router` |
| Encryption | `backend/app/core/encryption.py` | **READ ONLY** — already shipped in S-04, no changes needed |
| Frontend hooks | `frontend/src/hooks/useKey.ts` | **NEW** — 3 TanStack Query hooks |
| Frontend API | `frontend/src/lib/api.ts` | **MODIFY** — add 4 key wrappers + `ProviderKey` interface |
| Frontend UI | `frontend/src/routes/app.teams.$teamId.tsx` | **MODIFY** — add key section to WorkspaceCard |

### 4.2 Dependencies
| Type | Dependency | Status |
|------|------------|--------|
| **Requires** | EPIC-003 Slice B (Workspace CRUD + WorkspaceCard UI) | Done (S-05 in progress) |
| **Requires** | `backend/app/core/encryption.py` (AES-256-GCM) | Done (S-04) |
| **Unlocks** | EPIC-006: Google Drive (file indexing requires BYOK hard gate) | Waiting |
| **Unlocks** | EPIC-007: AI Agent (agent factory calls `resolve_provider_key`) | Waiting |

### 4.3 Integration Points
| System | Purpose | Notes |
|--------|---------|-------|
| OpenAI API | Validate key via `GET https://api.openai.com/v1/models` | Bearer token probe |
| Anthropic API | Validate key via `POST https://api.anthropic.com/v1/messages` (minimal payload) | `x-api-key` header |
| Google AI (Gemini) | Validate key via `GET https://generativelanguage.googleapis.com/v1beta/models` | `?key=` query param |

### 4.4 Data Changes
| Entity | Change | Fields |
|--------|--------|--------|
| `teemo_workspaces` | **MODIFY** — columns already exist from migration 002; no new migration needed | `encrypted_api_key TEXT`, `ai_provider VARCHAR(16)`, `ai_model VARCHAR(64)` |

> **No new migration required.** `teemo_workspaces` already has `encrypted_api_key`, `ai_provider`, and `ai_model` columns from `002_teemo_workspaces.sql`. This epic writes to those columns via `PATCH`.

---

## 5. Decomposition Guidance

### Affected Areas (for codebase research)
- [x] `backend/app/core/encryption.py` — already ships `encrypt()` / `decrypt()` / `key_fingerprint()`
- [x] `backend/app/core/config.py` — `teemo_encryption_key` field already present
- [x] `backend/app/models/workspace.py` — existing `WorkspaceResponse` intentionally omits `encrypted_api_key`
- [x] `backend/app/main.py` — existing router mount pattern for reference
- [x] `frontend/src/lib/api.ts` — `apiGet`, `apiPost`, `apiPatch` helpers + existing `Workspace` interface
- [x] `frontend/src/hooks/useWorkspaces.ts` — TanStack Query hook pattern to copy for useKey.ts
- [x] `frontend/src/routes/app.teams.$teamId.tsx` — WorkspaceCard component to add key section to
- [x] `new_app/backend/app/api/routes/keys.py` — copy source (strip instance keys, multi-key, impact check)
- [x] `new_app/backend/app/models/key.py` — copy source (strip `scope`, `editable`, `KeyRename`)
- [x] `new_app/backend/app/core/keys.py` — copy source (strip instance-key fallback)

### Key Constraints for Story Sizing
- Each story touches 1–3 files and has one clear goal
- **Critical**: the `resolve_provider_key` service is gated by backend CRUD being in place

### Suggested Sequencing
1. **STORY-004-01**: Backend models + key validator service + 4 routes + router mount (backend foundation)
2. **STORY-004-02**: `core/keys.py` resolver + `services/provider_resolver.py` resolver (inference gate — unlocks EPIC-007)
3. **STORY-004-03**: Frontend API wrappers + TanStack Query hooks
4. **STORY-004-04**: Frontend KeySection UI on WorkspaceCard + E2E manual verification

---

## 6. Risks & Edge Cases
| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Provider validation call fails due to rate limit | Low | Catch HTTP 429 — return `valid=False, message="Rate limited — try again shortly"` |
| User stores a key, provider revokes it later | Medium | Backend surfaces decryption+inference errors to Slack thread (EPIC-007 responsibility) |
| Google LLM validation probe uses different auth than Drive | Low | Validate against Gemini (`generativelanguage.googleapis.com`), not Drive API |
| Workspace `encrypted_api_key` already set from old data | N/A | No prod data exists yet — clean slate |
| `ai_model` is not set at key-save time | Medium | Allow `ai_model` to be nullable at save; EPIC-008 setup wizard sets it. Backend omits model from agent call if null — EPIC-007 can default to a sensible model per provider. |
| Key exposed in exception traceback | Low | Pydantic strips the key field from model `__repr__` — do not log raw `KeyCreate.key` at any log level |

---

## 7. Acceptance Criteria (Epic-Level)

```gherkin
Feature: BYOK Key Management

  Scenario: Happy path — user saves a valid key
    Given the user is logged in and has a Workspace created under a Slack team
    When the user posts a valid OpenAI key to POST /api/workspaces/{id}/keys
    Then the backend validates the key against the OpenAI API
    And the key is AES-256-GCM encrypted and stored in teemo_workspaces.encrypted_api_key
    And GET /api/workspaces/{id}/keys returns {provider: "openai", key_mask: "sk-a...xyz9"}
    And the plaintext key is never present in the response body or logs

  Scenario: Validate endpoint rejects an invalid key before storage
    Given the user submits {provider: "anthropic", key: "invalid-key"}
    When POST /api/keys/validate is called
    Then the response is {valid: false, message: "<provider error>"}
    And no row is written to teemo_workspaces

  Scenario: Delete clears the key
    Given the workspace has an encrypted_api_key set
    When DELETE /api/workspaces/{id}/keys is called
    Then encrypted_api_key, ai_provider, and ai_model are set to NULL on the workspace row
    And GET /api/workspaces/{id}/keys returns {has_key: false}

  Scenario: resolve_provider_key returns plaintext for inference
    Given teemo_workspaces has non-null encrypted_api_key for workspace_id X
    When resolve_provider_key(workspace_id=X, supabase=...) is called
    Then it returns the decrypted plaintext API key string
    And raises ValueError if no key is configured for that workspace
```

---

## 8. Open Questions
| Question | Options | Impact | Owner | Status |
|----------|---------|--------|-------|--------|
| Should `ai_model` be set at key-save time? | A: Yes — include `ai_model` in `KeyCreate` for convenience; B: No — model is set separately in setup wizard | Affects B01 `KeyCreate` schema | Solo dev | **Decided — Option A** (include `ai_model` as optional field in `KeyCreate`; defaults to provider's conversation-tier model if omitted per Charter §3.4) |
| Route prefix: workspace-scoped `/api/workspaces/{id}/keys` vs. standalone `/api/keys` | A: workspace-scoped; B: standalone with `workspace_id` in body | URL semantics | Solo dev | **Decided — Option A**: keys are scoped to a workspace in Tee-Mo (unlike new_app where they were user-scoped). Validate stays at `/api/keys/validate` (stateless, no scope needed). |

---

## 9. Artifact Links

**Stories (Status Tracking):**
- [ ] STORY-004-01-backend-key-routes → Backlog
- [ ] STORY-004-02-provider-resolvers → Backlog
- [ ] STORY-004-03-frontend-hooks → Backlog
- [ ] STORY-004-04-key-section-ui → Backlog

**References:**
- Charter: [Tee-Mo Charter §3.3 + §5.2 + §10 BYOK Epic](../strategy/tee_mo_charter.md)
- Copy source: `new_app/backend/app/api/routes/keys.py` (strip: instance keys, multi-key, impact check, scope)
- Copy source: `new_app/backend/app/models/key.py` (strip: `scope`, `editable`, `KeyRename`)
- Copy source: `new_app/backend/app/core/keys.py` (strip: instance-key fallback path)
- ADR-002: AES-256-GCM encryption
- Roadmap: [tee_mo_roadmap.md §2 Release 2](../strategy/tee_mo_roadmap.md)

## Change Log
| Date | Change | By |
|------|--------|-----|
| 2026-04-12 | Epic created from Charter §10 BYOK Epic Seed Map + codebase research | Claude (doc-manager) |
