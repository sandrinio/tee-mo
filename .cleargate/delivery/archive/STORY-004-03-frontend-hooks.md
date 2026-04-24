---
story_id: "STORY-004-03"
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

> **Ported from V-Bounce (shipped).** Original: `product_plans.vbounce-archive/archive/sprints/sprint-06/STORY-004-03-frontend-hooks.md`. Shipped in sprint S-06, carried forward during ClearGate migration 2026-04-24.

# STORY-004-03: Frontend API Wrappers + TanStack Query Hooks

## 1. The Spec

### 1.1 Goal
Wire the 4 backend key endpoints into the frontend by adding typed API wrappers to `lib/api.ts` and writing three TanStack Query hooks in a new `hooks/useKey.ts`. The UI story (STORY-004-04) consumes these hooks directly — no prop-drilling.

### 1.2 Deliverables
| File | Change |
|------|--------|
| `frontend/src/lib/api.ts` | **ADDITIVE** — add `ProviderKey` interface + `validateKey()`, `saveKey()`, `getKey()`, `deleteKey()` wrappers. Must NOT modify existing exports. |
| `frontend/src/hooks/useKey.ts` | **NEW** — `useKeyQuery`, `useSaveKeyMutation`, `useDeleteKeyMutation` |
| `frontend/src/hooks/useKey.test.tsx` | **NEW** — ≥4 unit tests |

---

## 2. The Truth (Acceptance Criteria)

```gherkin
Feature: Frontend Key Hooks

  Scenario: useKeyQuery fetches key status for a workspace
    Given workspace W1 has a key configured
    When useKeyQuery("W1") is called in a component
    Then it returns {has_key: true, provider: "openai", key_mask: "sk-a...xyz9"}
    And re-fetches on a 60s stale window

  Scenario: useSaveKeyMutation saves a key
    Given the mutation is triggered with {workspaceId: "W1", provider: "openai", key: "sk-valid", ai_model: "gpt-4o"}
    When the mutation resolves
    Then the useKeyQuery cache for "W1" is invalidated
    And the useWorkspacesQuery cache for the parent teamId is invalidated

  Scenario: useDeleteKeyMutation clears the key
    Given the mutation is triggered with workspaceId "W1"
    When the mutation resolves
    Then the key cache for "W1" is invalidated
    And the workspace cache is invalidated

  Scenario: useKeyQuery returns has_key: false for unconfigured workspace
    Given workspace W2 has no key
    When useKeyQuery("W2") is called
    Then data.has_key === false and data.provider === null
```

---

## 3. Implementation Guide

### 3.1 Additions to `frontend/src/lib/api.ts`

Add the following **below** the existing workspace wrappers:

```typescript
export interface ProviderKey {
  has_key: boolean;
  provider: string | null;
  key_mask: string | null;
  ai_model: string | null;
}

export interface SaveKeyRequest {
  provider: 'google' | 'openai' | 'anthropic';
  key: string;
  ai_model?: string;
}

export interface ValidateKeyRequest {
  provider: 'google' | 'openai' | 'anthropic';
  key: string;
}

export interface ValidateKeyResponse {
  valid: boolean;
  message: string;
}

export function getKey(workspaceId: string): Promise<ProviderKey> {
  return apiGet<ProviderKey>(`/api/workspaces/${encodeURIComponent(workspaceId)}/keys`);
}

export function saveKey(workspaceId: string, body: SaveKeyRequest): Promise<ProviderKey> {
  return apiPost<SaveKeyRequest, ProviderKey>(
    `/api/workspaces/${encodeURIComponent(workspaceId)}/keys`,
    body,
  );
}

export async function deleteWorkspaceKey(workspaceId: string): Promise<{ message: string }> {
  const r = await fetch(`${API_URL}/api/workspaces/${encodeURIComponent(workspaceId)}/keys`, {
    method: 'DELETE',
    credentials: 'include',
  });
  if (!r.ok) {
    const payload = await r.json().catch(() => ({}));
    throw new Error(payload?.detail ?? `HTTP ${r.status}`);
  }
  return r.json();
}

export function validateKey(body: ValidateKeyRequest): Promise<ValidateKeyResponse> {
  return apiPost<ValidateKeyRequest, ValidateKeyResponse>('/api/keys/validate', body);
}
```

### 3.2 New file: `frontend/src/hooks/useKey.ts`

```typescript
/**
 * TanStack Query hooks for BYOK key management (STORY-004-03).
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { deleteWorkspaceKey, getKey, saveKey, type SaveKeyRequest } from '../lib/api';

export const keyKeys = {
  all: ['keys'] as const,
  byWorkspace: (workspaceId: string) => ['keys', workspaceId] as const,
};

export function useKeyQuery(workspaceId: string) {
  return useQuery({
    queryKey: keyKeys.byWorkspace(workspaceId),
    queryFn: () => getKey(workspaceId),
    enabled: Boolean(workspaceId),
    staleTime: 60_000,
  });
}

export function useSaveKeyMutation(teamId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ workspaceId, ...body }: { workspaceId: string } & SaveKeyRequest) =>
      saveKey(workspaceId, body),
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({ queryKey: keyKeys.byWorkspace(variables.workspaceId) });
      qc.invalidateQueries({ queryKey: ['workspaces', teamId] });
    },
  });
}

export function useDeleteKeyMutation(teamId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (workspaceId: string) => deleteWorkspaceKey(workspaceId),
    onSuccess: (_data, workspaceId) => {
      qc.invalidateQueries({ queryKey: keyKeys.byWorkspace(workspaceId) });
      qc.invalidateQueries({ queryKey: ['workspaces', teamId] });
    },
  });
}
```

### 3.3 Cache invalidation note
The workspace query key in `useWorkspaces.ts` uses `['workspaces', teamId]`. Confirm this matches before writing `useKey.ts`.

---

## 4. Test Requirements

Write tests in `frontend/src/hooks/useKey.test.tsx` (min 4 tests):

1. `useKeyQuery returns data when key exists` — mock `getKey` → `{has_key: true, provider: "openai", key_mask: "sk-a...xyz9"}`. Assert hook data matches.
2. `useKeyQuery returns has_key false` — mock `getKey` → `{has_key: false, provider: null, key_mask: null}`. Assert `data.has_key === false`.
3. `useSaveKeyMutation invalidates key cache on success` — spy on `queryClient.invalidateQueries`, assert called with correct key.
4. `useDeleteKeyMutation invalidates key cache on success` — same pattern.

---

## Change Log
| Date | Change | By |
|------|--------|-----|
| 2026-04-12 | Story created from EPIC-004 decomposition | Claude (doc-manager) |
