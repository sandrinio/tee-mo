---
story_id: "STORY-004-03"
epic_id: "EPIC-004"
title: "Frontend API Wrappers + TanStack Query Hooks"
status: "Draft"
v_bounce_state: "Ready to Bounce"
complexity_label: "L2"
ambiguity: "🟢 Low"
depends_on: ["STORY-004-01"]
unlocks: ["STORY-004-04"]
estimated_effort: "~2h"
---

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

Add the following **below** the existing workspace wrappers — do NOT modify anything above line 265:

```typescript
// ---------------------------------------------------------------------------
// BYOK Key wrappers (STORY-004-03)
// ---------------------------------------------------------------------------

/** Response shape for GET /api/workspaces/{id}/keys */
export interface ProviderKey {
  /** true if an encrypted key is stored for this workspace */
  has_key: boolean;
  /** 'google' | 'openai' | 'anthropic' — null if has_key is false */
  provider: string | null;
  /** Masked key string e.g. "sk-a...xyz9" — null if has_key is false */
  key_mask: string | null;
  /** User-selected conversation-tier model ID */
  ai_model: string | null;
}

/** Request body for POST /api/workspaces/{id}/keys */
export interface SaveKeyRequest {
  provider: 'google' | 'openai' | 'anthropic';
  key: string;
  ai_model?: string;
}

/** Request body for POST /api/keys/validate */
export interface ValidateKeyRequest {
  provider: 'google' | 'openai' | 'anthropic';
  key: string;
}

/** Response from POST /api/keys/validate */
export interface ValidateKeyResponse {
  valid: boolean;
  message: string;
}

/**
 * GET /api/workspaces/{workspaceId}/keys
 * Returns key status for a workspace — never returns the plaintext key.
 */
export function getKey(workspaceId: string): Promise<ProviderKey> {
  return apiGet<ProviderKey>(`/api/workspaces/${encodeURIComponent(workspaceId)}/keys`);
}

/**
 * POST /api/workspaces/{workspaceId}/keys
 * Encrypt and store the user's BYOK API key for this workspace.
 */
export function saveKey(workspaceId: string, body: SaveKeyRequest): Promise<ProviderKey> {
  return apiPost<SaveKeyRequest, ProviderKey>(
    `/api/workspaces/${encodeURIComponent(workspaceId)}/keys`,
    body,
  );
}

/**
 * DELETE /api/workspaces/{workspaceId}/keys
 * Clears the stored key, ai_provider, and ai_model for this workspace.
 */
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

/**
 * POST /api/keys/validate
 * Probes the provider API with the key — does NOT store it.
 */
export function validateKey(body: ValidateKeyRequest): Promise<ValidateKeyResponse> {
  return apiPost<ValidateKeyRequest, ValidateKeyResponse>('/api/keys/validate', body);
}
```

### 3.2 New file: `frontend/src/hooks/useKey.ts`

Model this after the existing `hooks/useWorkspaces.ts` pattern (same TanStack Query + mutation structure):

```typescript
/**
 * TanStack Query hooks for BYOK key management (STORY-004-03).
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { deleteWorkspaceKey, getKey, saveKey, type SaveKeyRequest } from '../lib/api';

/** Query key factory — keeps cache keys consistent */
export const keyKeys = {
  all: ['keys'] as const,
  byWorkspace: (workspaceId: string) => ['keys', workspaceId] as const,
};

/**
 * Fetch the key status for a workspace.
 * Returns {has_key, provider, key_mask, ai_model}.
 * Enabled only when workspaceId is non-empty.
 */
export function useKeyQuery(workspaceId: string) {
  return useQuery({
    queryKey: keyKeys.byWorkspace(workspaceId),
    queryFn: () => getKey(workspaceId),
    enabled: Boolean(workspaceId),
    staleTime: 60_000,
  });
}

/**
 * Mutation: encrypt and store a BYOK key for a workspace.
 * On success, invalidates the key cache AND the workspace cache
 * (workspace response will reflect the updated ai_provider/ai_model).
 */
export function useSaveKeyMutation(teamId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      workspaceId,
      ...body
    }: { workspaceId: string } & SaveKeyRequest) => saveKey(workspaceId, body),
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({ queryKey: keyKeys.byWorkspace(variables.workspaceId) });
      // Invalidate workspaces list so provider badge updates
      qc.invalidateQueries({ queryKey: ['workspaces', teamId] });
    },
  });
}

/**
 * Mutation: delete the BYOK key for a workspace.
 * On success, invalidates the key cache and workspace list cache.
 */
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
The workspace query key in `useWorkspaces.ts` uses `['workspaces', teamId]`. Confirm this matches before writing `useKey.ts` — read `hooks/useWorkspaces.ts` for the exact key shape and mirror it.

### 3.4 `apiDelete` helper consideration
`deleteWorkspaceKey` needs `DELETE` — there is no `apiDelete` helper yet in `api.ts`. Implement it inline in the wrapper function (as shown in §3.1) rather than adding a top-level helper — keeps the change additive and avoids touching the existing helper section.

---

## 4. Test Requirements

Write tests in `frontend/src/hooks/useKey.test.tsx` (min 4 tests):

1. `useKeyQuery returns data when key exists` — mock `getKey` → `{has_key: true, provider: "openai", key_mask: "sk-a...xyz9"}`. Assert hook data matches.
2. `useKeyQuery returns has_key false` — mock `getKey` → `{has_key: false, provider: null, key_mask: null}`. Assert `data.has_key === false`.
3. `useSaveKeyMutation invalidates key cache on success` — spy on `queryClient.invalidateQueries`, assert called with correct key.
4. `useDeleteKeyMutation invalidates key cache on success` — same pattern.

Use the same RTL + Vitest + `jest-dom` infrastructure established in S-04 (see `vitest.config.ts`, `test-setup.ts`).

---

## Change Log
| Date | Change | By |
|------|--------|-----|
| 2026-04-12 | Story created from EPIC-004 decomposition | Claude (doc-manager) |

---

## Token Usage

| Agent | Input | Output | Total |
|-------|-------|--------|-------|
| Developer | 1,974 | 1,230 | 3,204 |
