---
story_id: "STORY-022-01-api-refresh-interceptor"
parent_epic_ref: "EPIC-022"
status: "Shipped"
approved: true
ambiguity: "🟢"
context_source: "PROPOSAL-001-teemo-platform.md"
owner: "TBD"
target_date: "TBD"
complexity_label: "L2"
parallel_eligible: false
expected_bounce_exposure: "low"
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

> **Ported from V-Bounce.** Original: `product_plans.vbounce-archive/backlog/EPIC-022_frontend_token_management/STORY-022-01-api-refresh-interceptor.md`. Carried forward during ClearGate migration 2026-04-24.

# STORY-022-01: Auto-Renew Expiring Access Tokens in Frontend Client

**Complexity: L2** — Modifies a single file (`api.ts`) but introduces interceptor and promise-locking patterns to the generic fetch wrappers, requiring testing edge cases like infinite loops.

---

## 1. The Spec (The Contract)

### 1.1 User Story
> As a **Dashboard User**,
> I want to **have my session automatically renewed in the background**,
> So that **I don't experience random page failures and artificial logouts when my 15-minute access token expires.**

### 1.2 Detailed Requirements
- **Requirement 1**: Intercept exactly `401 Unauthorized` responses in the frontend API caller.
- **Requirement 2**: Block concurrent failing requests under a single `refreshPromise` so that only 1 call is made to `POST /api/auth/refresh`.
- **Requirement 3**: If the refresh token exchange is successful, automatically replay the original request and resolve transparency.
- **Requirement 4**: If the refresh request itself returns a non-200 code, forcefully clear the `authStore` via dynamic lazy loading to avoid circular dependencies.

### 1.3 Out of Scope
- Modifying backend models or auth routes (already implemented).
- Converting the app to use `axios`. Native `fetch` wraps must be maintained.

### TDD Red Phase: No

---

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria

```gherkin
Feature: API Client 401 Interceptor

  Scenario: Token Expiration Flow
    Given an access_token has expired but refresh_token is valid
    When the user navigates a restricted view or makes an API call
    Then a 401 response is caught
    And exactly one POST to /api/auth/refresh is triggered
    And the original API call successfully recurs
    And the UI updates without requiring explicit login

  Scenario: Hard Expiration Ejection
    Given both access_token and refresh_token have expired
    When the user makes an API call
    And the /api/auth/refresh endpoint yields a 401
    Then the user is explicitly booted to the unauthenticated state ("anon")
```

---

## 3. The Implementation Guide (AI-to-AI)

### 3.2 Context & Files
| Item | Value |
|------|-------|
| **Primary File** | `frontend/src/lib/api.ts` |
| **New Files Needed** | No |
| **First-Use Pattern** | Yes — Singleton Promise Refresh Locking over raw fetch |

### 3.3 Technical Logic
In `frontend/src/lib/api.ts`:
1. Define `let refreshPromise: Promise<void> | null = null;`
2. Create `async function fetchWithAuth(url: string, options?: RequestInit): Promise<Response>`.
3. Change all hardcoded `fetch` occurrences in `apiGet`, `apiPost`, `apiPatch`, `deleteSlackTeam`, `deleteWorkspace`, `unbindChannel`, and `removeKnowledgeFile` to call `fetchWithAuth(url, options)`.
4. Interception code: if `response.status === 401` and URL does not include `/api/auth/refresh`, create or share `refreshPromise`. On refresh failure, lazy-import `useAuth` and call `logout()`. On success, retry original request.

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations
| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Unit tests | 0 — N/A | Fetch wrapper is covered under e2e testing. |
| E2E / acceptance tests | 1 | Basic page load after token expiry. |

### 4.2 Definition of Done (The Gate)
- [ ] `fetchWithAuth` replaces raw `fetch` for all authenticated calls.
- [ ] No violations of Roadmap ADRs.

---

## Token Usage

| Agent | Input | Output | Total |
|-------|-------|--------|-------|
