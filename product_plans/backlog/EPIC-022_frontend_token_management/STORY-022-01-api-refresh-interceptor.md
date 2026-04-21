---
story_id: "STORY-022-01-api-refresh-interceptor"
parent_epic_ref: "EPIC-022"
status: "Ready to Bounce"
ambiguity: "🟢 Low"
context_source: "Epic §4 / Codebase / User Input"
actor: "Dashboard User"
complexity_label: "L2"
---

# STORY-022-01: Auto-Renew Expiring Access Tokens in Frontend Client

**Complexity: L2** — Modifies a single file (`api.ts`) but introduces interceptor and promise-locking patterns to the generic fetch wrappers, requiring testing edge cases like infinite loops.

---

## 1. The Spec (The Contract)
> Human-Readable Requirements. The "What".
> Target Audience: PM, BA, Stakeholders, Developer Agent.

### 1.1 User Story
> As a **Dashboard User**,
> I want to **have my session automatically renewed in the background**,
> So that **I don't experience random page failures and artificial logouts when my 15-minute access token expires.**

### 1.2 Detailed Requirements
- **Requirement 1**: Intercept exactly `401 Unauthorized` responses in the frontend API caller.
- **Requirement 2**: Block concurrent failing requests under a single `refreshPromise` so that only 1 call is made to `POST /api/auth/refresh`.
- **Requirement 3**: If the refresh token exchange is successful, automatically replay the original request and resolve transparency.
- **Requirement 4**: If the refresh request itself returns a non-200 code (e.g., the 7-day token expired), forcefully clear the `authStore` via dynamic lazy loading to avoid circular dependencies.

### 1.3 Out of Scope
- Modifying backend models or auth routes (already implemented).
- Converting the app to use `axios`. Native `fetch` wraps must be maintained.

### TDD Red Phase: No
> Pure infrastructure fetch wrapper modification.

---

## 2. The Truth (Executable Tests)
> The QA Agent uses this to verify the work. If these don't pass, the Bounce failed.
> Target Audience: QA Agent (with vibe-code-review skill).

### 2.1 Acceptance Criteria (Gherkin/Pseudocode)
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

### 2.2 Verification Steps (Manual)
- [ ] Inspect `frontend/src/lib/api.ts` to ensure `fetch` calls are replaced by a centralized `fetchWithAuth`.
- [ ] Ensure `useAuth.getState().logout()` is safely imported using similar lazy loading as `getQueryClient` in `authStore.ts` to prevent circular dependencies.

---

## 3. The Implementation Guide (AI-to-AI)
> Instructions for the Developer Agent. The "How".
> Target Audience: Developer Agent (with react-best-practices + lesson skills).

### 3.0 Environment Prerequisites
| Prerequisite | Value | Verified? |
|-------------|-------|-----------|
| **Env Vars** | `.env` loaded via backend/frontend | [ ] |

### 3.1 Test Implementation
- Manually check logic or add a mock check for testing API wrappers if there's an existing `frontend/src/lib/__tests__/api.test.ts`. If no such file exists, standard UI testing via QA suffices per L2.

### 3.2 Context & Files
| Item | Value |
|------|-------|
| **Primary File** | `frontend/src/lib/api.ts` |
| **New Files Needed** | No |
| **First-Use Pattern** | Yes — Singleton Promise Refresh Locking over raw fetch |

### 3.3 Technical Logic
- In `frontend/src/lib/api.ts`:
  1. Define `let refreshPromise: Promise<void> | null = null;`
  2. Create an `async function fetchWithAuth(url: string, options?: RequestInit): Promise<Response>` that wraps standard `fetch`.
  3. Change all hardcoded `fetch` occurrences in `apiGet`, `apiPost`, `apiPatch`, `deleteSlackTeam`, `deleteWorkspace`, `unbindChannel`, and `removeKnowledgeFile` to call `fetchWithAuth(url, options)`. Note that `API_URL` prefix rules should remain inside those functions or be pushed down correctly into `fetchWithAuth`. *Recommendation*: leave `API_URL` prefixing in the parent functions, and just have `fetchWithAuth` take the final ready-to-call URL.
  4. Interception code inside `fetchWithAuth`:
     ```typescript
     let response = await fetch(url, options);
     if (response.status === 401 && !url.includes('/api/auth/refresh')) {
       if (!refreshPromise) {
         refreshPromise = fetch(`${API_URL}/api/auth/refresh`, {
           method: 'POST', credentials: 'include'
         }).then(res => {
           if (!res.ok) throw new Error('Refresh failed');
         }).finally(() => {
           refreshPromise = null;
         });
       }
       try {
         await refreshPromise;
       } catch (error) {
         // Perform logout via lazy import
         const { useAuth } = await import('../stores/authStore');
         await useAuth.getState().logout();
         return response; // Return the 401 response
       }
       // Retry Original Request
       response = await fetch(url, options);
     }
     return response;
     ```

### 3.4 API Contract (If applicable)
N/A

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations
| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Unit tests | 0 — N/A | Fetch wrapper is covered under e2e testing. |
| Component tests | 0 — N/A | |
| E2E / acceptance tests | 1 | Basic page load after token expiry. |

### 4.2 Definition of Done (The Gate)
- [ ] Minimum test expectations (§4.1) met.
- [ ] No violations of Roadmap ADRs.
- [ ] `fetchWithAuth` replaces raw `fetch` for all authenticated calls.

---

## Token Usage
> Auto-populated by agents. Each agent runs `node .vbounce/scripts/count_tokens.mjs --self --append <this-file> --name <Agent>` before writing their report.

| Agent | Input | Output | Total |
|-------|-------|--------|-------|
