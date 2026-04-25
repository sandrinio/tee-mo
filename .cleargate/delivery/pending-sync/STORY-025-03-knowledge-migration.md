---
story_id: "STORY-025-03"
parent_epic_ref: "EPIC-025"
status: "Draft"
ambiguity: "🟢 Low"
context_source: "EPIC-025-workspace-v2-redesign.md"
actor: "Workspace admin"
complexity_label: "L1"
created_at: "2026-04-25T00:00:00Z"
updated_at: "2026-04-25T00:00:00Z"
created_at_version: "cleargate-s16-kickoff"
updated_at_version: "cleargate-s16-kickoff"
server_pushed_at_version: null
draft_tokens: { input: null, output: null, cache_read: null, cache_creation: null, model: null, sessions: [] }
cached_gate_result: { pass: null, failing_criteria: [], last_gate_check: null }
---

# STORY-025-03: Knowledge Group Migration
**Complexity:** L1 — chrome only, ~2hr

## 1. The Spec

### 1.1 User Story
As a workspace admin, I want the Files module rendered inside the new shell with a header strip + divider list, so that file count and Add action are at-a-glance.

### 1.2 Detailed Requirements
- **FilesSection** — single module card with two regions:
  - Header strip: "{N} of {M} files indexed" left, "Add file" primary button + "Upload" secondary button right. Truncation/indexing banners render below header strip when active (preserve existing TruncationToast + indexing banner).
  - Divider list (no per-row cards): lucide file icon + filename + 1-line italic AI description (slate-500, max 1 line via `line-clamp-1`) + Remove button revealed on row hover.
- All existing PickerSection logic preserved — Drive picker, BYOK gate, file cap, reindex, upload mutation. Chrome only.
- KnowledgeList component re-skin: divider list instead of stacked Card per row; hover-reveal Remove (`group-hover:opacity-100 opacity-0 transition`).
- Status resolver: `ok` if files ≥ 1, `partial` if files ≥ 1 and < 15 (carry over current "<15 partial" rule from handoff), `empty` if 0.

### 1.3 Out of Scope
- Files content cap raise (currently 100; handoff "15" is an upper "partial" boundary, not a cap).
- Drag-and-drop upload (deferred per EPIC-014 §1.3).
- Multi-file selection (deferred per EPIC-014).

## 2. The Truth

### 2.1 Acceptance Criteria

```gherkin
Feature: Knowledge group migration

  Scenario: Header strip renders count + actions
    Given the workspace has 12 indexed files
    Then the header strip shows "12 of 100 files indexed"
    And renders an Add file primary button and Upload secondary button

  Scenario: Divider list renders rows without per-row cards
    Given 3 indexed files
    Then the file list renders 3 rows separated by horizontal dividers
    And no Card border surrounds individual rows

  Scenario: Remove button hover-reveals
    Given a file row not under hover
    Then the Remove button has opacity 0
    When the user hovers over the row
    Then the Remove button has opacity 100

  Scenario: Existing add/upload behavior preserved
    When the user clicks Add file
    Then the existing Google Picker token fetch + picker open flow runs unchanged
    When the user clicks Upload and selects a 5MB PDF
    Then the existing useUploadKnowledgeMutation fires unchanged
```

### 2.2 Verification Steps (Manual)
- [ ] Add a file via Drive picker — TruncationToast displays under header strip if backend warns.
- [ ] Upload a local file — indexing banner shows; success row appears in divider list.
- [ ] Hover a row — Remove fades in; click → row removed.
- [ ] Reindex — existing mutation success/failure messages render under header strip.

## 3. Implementation Guide

### 3.1 Files

| Item | Value |
|---|---|
| New | `frontend/src/components/workspace/FilesSection.tsx` (extracted from route) |
| Modify | `frontend/src/routes/app.teams.$teamId.$workspaceId.tsx` — remove inline `PickerSection` + `KnowledgeList` definitions |
| Modify | `frontend/src/components/workspace/moduleRegistry.ts` — Knowledge group entry + status resolver |

### 3.2 Technical Logic
- The extracted FilesSection accepts the same props PickerSection currently accepts (workspaceId, driveConnected, hasKey, fileCount, onFileIndexed, onIndexingChange) plus a `files: KnowledgeFile[]` prop and renders the list internally.
- Hover-reveal pattern: row uses Tailwind `group` class; Remove button uses `opacity-0 group-hover:opacity-100 transition-opacity duration-150`.
- Header strip uses `flex items-center justify-between gap-3 border-b border-slate-200 px-4 py-3`.
- Divider rows use `divide-y divide-slate-100` on the container.

### 3.3 API Contract
None new.

## 4. Quality Gates

### 4.1 Minimum Test Expectations

| Test Type | Min | Notes |
|---|---|---|
| Vitest unit | 4 | One per Gherkin scenario |
| Existing | green | useKnowledge tests, picker tests must pass unchanged |

### 4.2 Definition of Done
- [ ] All §2.1 scenarios covered.
- [ ] `npm run typecheck` clean.
- [ ] No regression in existing knowledge test suites.
- [ ] Manual verification §2.2 completed.

---

## ClearGate Ambiguity Gate
**Current Status: 🟢 Low — Ready for Execution**
