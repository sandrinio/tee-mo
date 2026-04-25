---
story_id: "STORY-014-03-frontend-upload"
parent_epic_ref: "EPIC-014"
status: "Shipped"
approved: true
shipping_commit: "e36e74c"
shipping_sprint: "SPRINT-15"
ambiguity: "🟢"
context_source: "PROPOSAL-001-teemo-platform.md"
actor: "Workspace Admin"
complexity_label: "L2"
parallel_eligible: false
expected_bounce_exposure: "low"
created_at: "2026-04-25T00:00:00Z"
updated_at: "2026-04-25T00:00:00Z"
created_at_version: "cleargate-pre-S15"
updated_at_version: "cleargate-pre-S15"
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

# STORY-014-03: Frontend Upload Button

**Complexity: L2** — One new API function, one new TanStack mutation hook, one new button + hidden file input next to the existing "Add File" Drive picker. Source badges and document-type rendering are **already shipped** in `KnowledgeList` (Drive / Upload / Agent variants). Blocked by STORY-014-02 (needs the backend route).

---

## 1. The Spec (The Contract)

### 1.1 User Story
As a **Workspace Admin**, I want to upload a local file directly from the workspace dashboard, so that I can index documents without going through Google Drive.

### 1.2 Detailed Requirements
- **R1.** Add a new API helper `uploadKnowledgeFile(workspaceId: string, file: File)` in `frontend/src/lib/api.ts`. POSTs `multipart/form-data` (single field `file`) to `/api/workspaces/{workspaceId}/documents/upload`. Returns the parsed `KnowledgeFile` row (same shape as the existing index/list rows).
- **R2.** Add a TanStack mutation hook `useUploadKnowledgeMutation(workspaceId)` in `frontend/src/hooks/useKnowledge.ts`. On success, invalidates the same `['knowledge', workspaceId]` query key the existing `useAddKnowledgeMutation` invalidates so the list re-renders.
- **R3.** In `frontend/src/routes/app.teams.$teamId.$workspaceId.tsx`, alongside the existing "Add File" (Drive picker) button, add an **"Upload File"** button. Reuse the existing `atCap` predicate (`fileCount >= MAX_FILES` where `MAX_FILES = 100`, declared at `:71`). Same gating rules:
  - Disabled when BYOK key is not configured (with the same explanatory tooltip / message as the picker).
  - Disabled when `atCap` is true (with the same `${fileCount}/${MAX_FILES} files` count badge text already used at `:403`).
  - Visible regardless of Drive connection status (this is the whole point — uploads do not require Drive).
- **R4.** The button opens a hidden `<input type="file" accept=".pdf,.docx,.xlsx,.txt,.md,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/plain,text/markdown">` and triggers it via `inputRef.current?.click()`.
- **R5.** On file selection: client-side guard — if `file.size > 10 * 1024 * 1024`, show inline error "File exceeds 10MB limit" without calling the backend. Otherwise call the mutation.
- **R6.** While the mutation is pending, the button label switches to "Uploading…" and is disabled. On success, no toast — the row appearing in the list is sufficient feedback (matches Drive picker UX). On error, render the backend's `detail` string inline next to the button (matches existing picker error pattern at `frontend/src/routes/app.teams.$teamId.$workspaceId.tsx:376`).
- **R7.** No source-badge work, no `KnowledgeList` modification, no agent-side change. The `'upload'` badge already renders correctly via `sourceBadgeProps` once the backend returns rows with `source='upload'`.

### 1.3 Out of Scope
- Drag-and-drop. Click-to-select only for v1.
- Multi-file selection. Single file per click.
- Upload progress percentage. The pending state on the button is the only progress signal (uploads are usually <5s).
- New badge variants or `KnowledgeList` layout changes.
- Any backend, agent, or schema work.

---

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria (Gherkin)

```gherkin
Feature: Local Document Upload — Frontend

  Scenario: Upload button appears next to Drive picker
    Given a workspace with a configured BYOK key and < 15 documents
    When the workspace detail route renders
    Then an "Upload File" button is visible next to the "Add File" Drive picker

  Scenario: BYOK gate
    Given a workspace with no BYOK key configured
    Then the "Upload File" button is disabled with the same gating message as the Drive picker

  Scenario: 100-document cap
    Given a workspace with 100 indexed documents
    Then the "Upload File" button is disabled with the count badge "100/100 files"

  Scenario: Client-side size guard
    Given the user selects a file > 10MB
    When the input fires onChange
    Then the upload is NOT sent to the backend
    And an inline error "File exceeds 10MB limit" is shown

  Scenario: Happy path
    Given the user selects a 1MB PDF
    When the upload mutation resolves with 201
    Then the knowledge query is invalidated
    And the new row appears in the list with an "Upload" badge

  Scenario: Backend rejection surfaces inline
    Given the backend returns 400 with detail "BYOK key required"
    Then the inline error renders the detail text verbatim
```

### 2.2 Verification Steps (Manual)
- [ ] Run `npm run dev`, open a workspace, click "Upload File", select a small PDF — row appears with "Upload" badge within ~3s.
- [ ] Click "Upload File" again with the same filename — backend returns 409 "already uploaded", inline error renders.
- [ ] Click with a 12MB PDF — inline error renders, no network request fired (verify in DevTools Network tab).
- [ ] Manually clear BYOK key → "Upload File" button disables.

---

## 3. The Implementation Guide

### 3.1 Context & Files

| Item | Value |
|---|---|
| Primary File | `frontend/src/routes/app.teams.$teamId.$workspaceId.tsx` (extend `PickerSection`) |
| Related Files | `frontend/src/lib/api.ts` (add `uploadKnowledgeFile`), `frontend/src/hooks/useKnowledge.ts` (add `useUploadKnowledgeMutation`) |
| New Files Needed | No |

### 3.2 Technical Logic

**API helper (`api.ts`):**
```ts
export async function uploadKnowledgeFile(workspaceId: string, file: File): Promise<KnowledgeFile> {
  const form = new FormData();
  form.append('file', file);
  const res = await apiFetch(`/api/workspaces/${workspaceId}/documents/upload`, {
    method: 'POST',
    body: form,
    // do NOT set Content-Type — browser sets multipart boundary
  });
  return res as KnowledgeFile;
}
```
Reuse the existing `apiFetch` (or whatever the project's fetch wrapper is named — see `useDrive.ts` / `useKnowledge.ts` for the canonical reference).

**Mutation hook (`useKnowledge.ts`):**
```ts
export function useUploadKnowledgeMutation(workspaceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => uploadKnowledgeFile(workspaceId, file),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['knowledge', workspaceId] }),
  });
}
```

**Button + input (`PickerSection` in the workspace route):**
- Place the new button immediately after the existing "Add File" button so they share the gating row.
- Reuse the existing `disabled` predicate (`!hasKey || files.length >= 15`).
- Hidden `<input ref={inputRef} type="file" accept="..." onChange={handleSelect} className="hidden" />`.
- `handleSelect` reads the first file, runs the size guard, and calls `uploadMutation.mutate(file)`.

### 3.3 API Contract
Consumes the contract defined in STORY-014-02 §3.3. No new backend surface invented here.

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations

| Test Type | Minimum Count | Notes |
|---|---|---|
| Component / hook tests (Vitest + RTL) | 4 | (a) button renders enabled when BYOK + `!atCap`; (b) button disabled at 100/100; (c) size guard rejects >10MB without network call; (d) successful upload invalidates the knowledge query. |
| Manual verification | 4 steps | §2.2 list. |

### 4.2 Definition of Done (The Gate)
- [ ] All 6 Gherkin scenarios in §2.1 covered (4 component tests + 2 manual verifications cover the happy/reject paths).
- [ ] `npm run typecheck` passes.
- [ ] `npm run test` shows the same pre-existing failure count (frontend baseline at S-14 close: 131 passed / 6 pre-existing failures).
- [ ] No changes to `KnowledgeList` rendering or `sourceBadgeProps` — `'upload'` badge already shipped.
- [ ] Upload route is gated identically to the picker (BYOK + 15-cap).

---

## ClearGate Ambiguity Gate (🟢 / 🟡 / 🔴)
**Current Status: 🟢 Green — Ready for Execution**

- [x] Gherkin covers R1–R6.
- [x] §3 maps to verified file paths (workspace route, `api.ts`, `useKnowledge.ts`).
- [x] No TBDs.
- [x] Blocked-by STORY-014-02 declared.
- [x] Pre-flight verified: source badge + agent path **already shipped** — this story is purely the upload trigger UI.
