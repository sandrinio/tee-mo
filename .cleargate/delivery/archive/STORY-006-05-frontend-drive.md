---
story_id: "STORY-006-05-frontend-drive"
parent_epic_ref: "EPIC-006"
status: "Shipped"
ambiguity: "🟢"
context_source: "PROPOSAL-001-teemo-platform.md"
complexity_label: "L3"
parallel_eligible: false
expected_bounce_exposure: "low"
approved: true
created_at: "2026-04-10T00:00:00Z"
updated_at: "2026-04-13T00:00:00Z"
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
> **Ported from V-Bounce (shipped).** Original: `product_plans.vbounce-archive/archive/sprints/sprint-08/STORY-006-05-frontend-drive.md`. Shipped in sprint S-08, carried forward during ClearGate migration 2026-04-24.

# STORY-006-05: Frontend — Workspace Detail Page + Drive Connect + Picker + File List

**Complexity: L3** — New route, Google Picker integration, multiple UI sections

---

## 1. The Spec (The Contract)

### 1.1 User Story
> As a **Workspace Admin**,
> I want to **connect Google Drive, pick files, and see my knowledge base from the dashboard**,
> So that **I can manage what the bot knows about**.

### 1.2 Detailed Requirements
- **R1**: New route `/app/teams/$teamId/$workspaceId` — workspace detail page with sections: Drive Connection, Knowledge Files, (BYOK key section already exists in WorkspaceCard but may need relocation here).
- **R2**: **Drive Connection section**: shows "Connected as user@email.com" with "Disconnect" button, OR "Not connected" with "Connect Google Drive" button. Connect button navigates to `GET /api/workspaces/{id}/drive/connect` (full-page redirect, same as Slack OAuth pattern).
- **R3**: **Google Picker button**: visible only when Drive is connected AND BYOK key is configured. Loads Google Picker API via `gapi.load('picker')`, uses access token from `GET /api/workspaces/{id}/drive/picker-token`. On file select, calls `POST /api/workspaces/{id}/knowledge` with file metadata. Shows loading state while AI description is being generated.
- **R4**: **Knowledge file list**: table/list showing title, AI description (truncated), MIME type icon, "Remove" button. Empty state: "No files indexed yet. Use the picker above to add files."
- **R5**: **15-file indicator**: show "X/15 files" count. Disable picker button at 15 with tooltip.
- **R6**: **BYOK gate**: if no BYOK key configured, show disabled picker with "Configure an API key first" message.
- **R7**: Follow design system from `tee_mo_design_guide.md` (ADR-022) — Asana-inspired, coral accents, slate neutrals, Inter font, Lucide icons.
- **R8**: **Truncation warning**: if the `POST /knowledge` response includes a `warning` field (file >50K chars), show a toast/banner: "File content truncated to 50,000 characters. The bot may not see the full document."

### 1.3 Out of Scope
- Channel binding UI (future)
- Rescan button per file (EPIC-009)
- Wiki page viewer (EPIC-013)
- Drag-and-drop file reordering

### TDD Red Phase: No — frontend component, manual verification primary

---

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria (Gherkin/Pseudocode)
```gherkin
Feature: Frontend Drive Integration

  Scenario: Workspace detail page renders
    Given a logged-in user navigating to /app/teams/t1/ws-1
    Then the page shows workspace name, Drive connection status, and file list

  Scenario: Connect Drive button works
    Given Drive is NOT connected for workspace ws-1
    When user clicks "Connect Google Drive"
    Then browser navigates to /api/workspaces/ws-1/drive/connect (full-page redirect)

  Scenario: Drive connected state shows email
    Given Drive IS connected for workspace ws-1
    Then the page shows "Connected as user@example.com"
    And shows a "Disconnect" button

  Scenario: Picker opens and indexes file
    Given Drive connected AND BYOK key configured
    When user clicks "Add File" and selects a file from Picker
    Then a POST is sent to /api/workspaces/ws-1/knowledge
    And loading state is shown while AI generates description
    And the file appears in the list with its AI description

  Scenario: 15-file cap shown
    Given workspace has 15 indexed files
    Then the count shows "15/15 files"
    And the "Add File" button is disabled with tooltip

  Scenario: Remove file
    Given a file in the knowledge list
    When user clicks "Remove"
    Then a DELETE is sent
    And the file disappears from the list
```

### 2.2 Verification Steps (Manual)
- [ ] Navigate to `/app/teams/$teamId/$workspaceId` — page renders
- [ ] Drive status shows correctly (connected/not connected)
- [ ] Google Picker opens and returns file metadata
- [ ] File appears in list after indexing
- [ ] Remove button works
- [ ] 15/15 disables picker
- [ ] BYOK gate disables picker with message

---

## 3. The Implementation Guide (AI-to-AI)

### 3.0 Environment Prerequisites
| Prerequisite | Value | Verified? |
|-------------|-------|-----------|
| **Dependencies** | STORY-006-02 (drive_oauth) and STORY-006-03 (knowledge routes) merged | [ ] |
| **Services Running** | Backend on localhost:8000, Vite on localhost:5173 | [ ] |

### 3.1 Test Implementation
- Create `frontend/src/hooks/useKnowledge.test.tsx` — test query/mutation hooks
- Create `frontend/src/hooks/useDrive.test.tsx` — test drive status hook

### 3.2 Context & Files
| Item | Value |
|------|-------|
| **Primary File** | `frontend/src/routes/app.teams.$teamId.$workspaceId.tsx` (new) |
| **Related Files** | `frontend/src/hooks/useKnowledge.ts` (new), `frontend/src/hooks/useDrive.ts` (new), `frontend/src/lib/api.ts` (add typed wrappers) |
| **New Files Needed** | Yes — route file, 2 hooks files |
| **ADR References** | ADR-022 (design system) |
| **First-Use Pattern** | Yes — Google Picker API in React (gapi.load, picker.PickerBuilder) |

### 3.3 Technical Logic

**Route structure:**
```
/app/teams/$teamId/$workspaceId → WorkspaceDetailPage
  ├── DriveSection (connect/disconnect + status)
  ├── PickerSection (Google Picker button)
  └── KnowledgeList (file table + remove)
```

**Google Picker integration:**
```typescript
// 1. Load gapi: <script src="https://apis.google.com/js/api.js">
// 2. On "Add File" click:
//    a. GET /api/workspaces/{id}/drive/picker-token → { access_token, picker_api_key }
//    b. gapi.load('picker', () => {
//         new google.picker.PickerBuilder()
//           .setOAuthToken(access_token)
//           .setDeveloperKey(picker_api_key)
//           .addView(google.picker.ViewId.DOCS)
//           .setCallback(pickerCallback)
//           .build()
//           .setVisible(true);
//       });
// 3. pickerCallback: extract { id, name, url, mimeType } → POST /api/workspaces/{id}/knowledge
```

**TanStack Query hooks:**
- `useKnowledgeQuery(workspaceId)` — GET knowledge list
- `useAddKnowledgeMutation(workspaceId)` — POST new file
- `useRemoveKnowledgeMutation(workspaceId)` — DELETE file
- `useDriveStatusQuery(workspaceId)` — GET drive/status
- `useDisconnectDriveMutation(workspaceId)` — POST drive/disconnect

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations
| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Component tests | 4 | Hook tests for knowledge + drive queries/mutations |
| Unit tests | 0 | N/A — UI logic is in hooks |
| E2E tests | 0 | Manual browser verification |

### 4.2 Definition of Done (The Gate)
- [ ] Route accessible and renders.
- [ ] Google Picker opens and returns file data.
- [ ] File list populates after indexing.
- [ ] Design system compliance (ADR-022).
- [ ] Browser-tested: Drive connect → Picker → file appears → remove.

---

## Token Usage
| Agent | Input | Output | Total |
|-------|-------|--------|-------|
| Developer | 108 | 4,721 | 4,829 |
| QA | 12 | 243 | 255 |
| Architect | 13 | 183 | 196 |
