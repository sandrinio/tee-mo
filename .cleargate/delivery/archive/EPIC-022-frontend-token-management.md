---
epic_id: "EPIC-022"
status: "Shipped"
approved: true
children:
  - "STORY-022-01-api-refresh-interceptor"
ambiguity: "🟢"
context_source: "PROPOSAL-001-teemo-platform.md"
owner: "Team Lead"
target_date: "TBD"
created_at: "2026-04-10T00:00:00Z"
updated_at: "2026-04-24T00:00:00Z"
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
> **Ported from V-Bounce.** Original: `product_plans.vbounce-archive/backlog/EPIC-022_frontend_token_management/EPIC-022_frontend_token_management.md`. Carried forward during ClearGate migration 2026-04-24.

# EPIC-022: Frontend Token Management

## 1. Problem & Value

### 1.1 The Problem
Currently, the Tee-Mo frontend HTTP wrappers (`api.ts`) do not automatically intercept `401 Unauthorized` responses. The `access_token` lives for 15 minutes. When it expires, all subsequent API fetches fail silently with network errors, effectively "logging out" active users abruptly, regardless of whether they have a valid 7-day `refresh_token`.

### 1.2 The Solution
Implement an intelligent retry wrapper in `frontend/src/lib/api.ts` that catches 401s, momentarily pauses pending API calls using a Promise lock, hits the `/api/auth/refresh` endpoint to renew the `access_token`, and transparently replays the original requests.

### 1.3 Success Metrics (North Star)
- 0% of active sessions forcibly terminated before the 7-day refresh token expires.
- Concurrent failing API queries generate exactly 1 network request to `/refresh`.

---

## 2. Scope Boundaries

### ✅ IN-SCOPE (Build This)
- [x] Create a `fetchWithAuth` wrapper in `api.ts`.
- [x] Implement a concurrent refresh promise lock.
- [x] Catch 401 errors, invoke the refresh endpoint, and retry logic.
- [x] Throw explicit errors/force logout if the refresh request itself fails (i.e. refresh_token expired).

### ❌ OUT-OF-SCOPE (Do NOT Build This)
- Backend authorization or cookie lifespan modifications (already covered in EPIC-002).
- Axios migration (Tee-Mo uses native `fetch`).

---

## 3. Context

### 3.1 Constraints
| Type | Constraint |
|------|------------|
| **Performance** | Refresh lock must not block non-401 queries globally, only those retrying. |
| **UX** | Re-authentication must be 100% invisible to the user component layer. |

---

## 4. Technical Context

### 4.1 Affected Areas
| Area | Files/Modules | Change Type |
|------|---------------|-------------|
| API | `frontend/src/lib/api.ts` | Modify |

### 4.2 Dependencies
| Type | Dependency | Status |
|------|------------|--------|
| **Requires** | EPIC-002: Backend Auth Routes | Done |

---

## 7. Acceptance Criteria (Epic-Level)

```gherkin
Feature: Frontend Token Management

  Scenario: Complete Happy Path
    Given the user has an expired access_token but a valid refresh_token
    When the user makes an authenticated request (e.g. GET /me)
    Then the client intercepts the 401 rejection
    And successfully calls POST /api/auth/refresh
    And replays the request, successfully surfacing the data to the UI with no flashing components.

  Scenario: Key Error Case
    Given the user's refresh_token has also expired
    When the user makes a request and the background refresh returns 401
    Then the client rejects the promise
    And the auth store correctly forces a transition to the Login route.
```

---

## 8. Open Questions
| Question | Options | Impact | Owner | Status |
|----------|---------|--------|-------|--------|
| Should `api.ts` import the `authStore` to trigger explicit logout upon final 401? | A: Yes (circular import risk bypassed by lazy loading), B: No (let TanStack catch boundaries handle it). | Eject UX | Human | Decided (A) |

---

## 9. Artifact Links

**Stories (Status Tracking):**
- [x] STORY-022-01-api-refresh-interceptor -> Done

## Change Log
| Date | Change | By |
|------|--------|-----|
| 2026-04-24 | Ported to ClearGate v0.2.1. | ClearGate migration |
