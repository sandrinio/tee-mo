---
story_id: "STORY-015-06"
parent_epic_ref: "EPIC-015"
status: "Shipped"
ambiguity: "🟢"
context_source: "PROPOSAL-001-teemo-platform.md"
complexity_label: "L1"
parallel_eligible: false
expected_bounce_exposure: "low"
approved: true
created_at: "2026-04-10T00:00:00Z"
updated_at: "2026-04-14T00:00:00Z"
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
> **Ported from V-Bounce (shipped).** Original: `product_plans.vbounce-archive/archive/sprints/sprint-11/STORY-015-06-frontend-update.md`. Shipped in sprint S-11, carried forward during ClearGate migration 2026-04-24.

# STORY-015-06: Frontend — Source Badges + New API Shape

**Complexity: L1** — 3 frontend files, ~1.5hr

---

## 1. The Spec (The Contract)

### 1.1 User Story
> Update the workspace detail page to work with the new `teemo_documents` API response shape. Add source badges (Drive / Upload / Agent) to each document in the knowledge list.

### 1.2 Detailed Requirements

- **R1 — API types**: Update TypeScript types to match new response: `source` field (`google_drive` | `upload` | `agent`), `doc_type` field, `external_id` (nullable), `external_link` (nullable).
- **R2 — Source badges**: Each document in the knowledge list shows a Badge component:
  - `google_drive` → "Drive" badge (default/neutral style)
  - `upload` → "Upload" badge
  - `agent` → "Agent" badge
- **R3 — Link behavior**: Only Drive documents have an external link. Upload and agent docs show title only (no link icon).
- **R4 — Delete**: All documents deletable via the existing delete button (no source restriction on frontend — backend handles it).

### 1.3 Out of Scope
- Upload UI (EPIC-014)
- "Create Document" button (future)
- Wiki page viewer (future)

---

## 2. The Truth (Executable Tests)

```gherkin
Feature: Frontend Source Badges

  Scenario: Drive document shows Drive badge with link
    Given a workspace with a Drive document
    Then the knowledge list shows "Drive" badge and a link icon

  Scenario: Agent document shows Agent badge without link
    Given a workspace with an agent-created document
    Then the knowledge list shows "Agent" badge and no link icon
```

---

## 3. The Implementation Guide (AI-to-AI)

### 3.1 Files
| Item | Value |
|------|-------|
| **Modified files** | `frontend/src/routes/app.teams.$teamId.$workspaceId.tsx`, `frontend/src/hooks/useKnowledge.ts`, `frontend/src/lib/api.ts` |

### 3.2 Technical Logic
1. Update API response types to include `source`, `doc_type`.
2. Add Badge rendering in the knowledge list component based on `source`.
3. Conditionally render link icon only when `external_link` is non-null.

---

## Change Log
| Date | Author | Change |
|------|--------|--------|
| 2026-04-13 | Claude (doc-manager) | Initial draft for S-11. |

---

## Token Usage

| Agent | Input | Output | Total |
|-------|-------|--------|-------|
| Developer | 41 | 2,003 | 2,044 |
