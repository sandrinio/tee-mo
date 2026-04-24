---
story_id: "STORY-004-04"
epic_id: "EPIC-004"
title: "Frontend Key Section UI on WorkspaceCard + Manual E2E Verification"
status: "Draft"
v_bounce_state: "Ready to Bounce"
complexity_label: "L2"
ambiguity: "🟢 Low"
depends_on: ["STORY-004-03"]
unlocks: ["EPIC-006", "EPIC-007"]
estimated_effort: "~3h"
---

# STORY-004-04: Frontend Key Section UI on WorkspaceCard + Manual E2E Verification

## 1. The Spec

### 1.1 Goal
Add a BYOK key management section to the existing `WorkspaceCard` in `app.teams.$teamId.tsx`. Users should be able to:
- See current key status (masked key + provider badge, or "No key configured")
- Validate a new key before saving
- Save and update a key
- Delete a key with confirmation

This story is the **last gate before EPIC-006** — once a workspace has a key, the "Add File" button becomes enabled.

### 1.2 UI Design
Per ADR-022 + `tee_mo_design_guide.md` — warm minimalism, coral accent `#F43F5E`, slate neutrals, Inter typography. No heavy component libraries.

The key section lives inside the existing workspace card, below the workspace header and above the channel chips section. It uses a compact inline form — not a modal.

```
┌─ Workspace Card ─────────────────────────────────────────────────────────┐
│ Marketing Knowledge                    [Make Default] [Rename] [Delete]  │
│ 📨 DMs route here                                                         │
│                                                                           │
│ ┌─ API Key ──────────────────────────────────────────────────────────┐   │
│ │  Provider: [OpenAI ▼]  Key: [sk-a...xyz9 🔑]   [Update] [Delete]  │   │
│ │  Status: ✅ Configured                                              │   │
│ └────────────────────────────────────────────────────────────────────┘   │
│                                                                           │
│ Channels: [#marketing ✅] [#social ⚠] [+ Add channel]                   │
│                                                                           │
│ Add File button: ✅ enabled (key configured) / ⚠️ disabled (no key)      │
└───────────────────────────────────────────────────────────────────────────┘
```

**Collapsed state (no key):**
```
│  API Key: ⚠️ No key configured   [+ Add key]
```

**Add/Update key inline form (expanded):**
```
│  Provider [OpenAI ▼]  Key [________________ 👁]  [Validate]  [Save] [Cancel]
│  Validation: ✅ Valid  /  ❌ Invalid: "Incorrect API key"
```

### 1.3 Interaction flow
1. Card loads → `useKeyQuery(workspaceId)` → show collapsed status
2. User clicks **"+ Add key"** → inline form expands (Provider dropdown + Key input + Validate button)
3. User types key → clicks **Validate** → calls `validateKey` API → shows inline result (`✅ Valid` / `❌ error message`)
4. User clicks **Save** → calls `useSaveKeyMutation` → on success, form collapses to showing masked key
5. **Update**: same form, pre-filled provider shown, key input blank (mask shown not editable)
6. **Delete**: clicking Delete shows a confirm inline message → on confirm calls `useDeleteKeyMutation`

---

## 2. The Truth (Acceptance Criteria)

```gherkin
Feature: BYOK Key UI on WorkspaceCard

  Scenario: Card shows "No key" state for unconfigured workspace
    Given useKeyQuery for workspaceId returns {has_key: false}
    When the WorkspaceCard renders
    Then a "No key configured" label is visible with a "+ Add key" button
    And the "Add File" button (if present) is disabled with tooltip "Configure your AI provider first"

  Scenario: Card shows masked key for configured workspace
    Given useKeyQuery returns {has_key: true, provider: "openai", key_mask: "sk-a...xyz9"}
    When the WorkspaceCard renders
    Then "sk-a...xyz9" and "OpenAI" badge are visible
    And "Update" and "Delete" buttons are present

  Scenario: Validate flow — success
    Given the key input form is expanded with provider="openai" key="sk-valid"
    When the user clicks Validate
    Then POST /api/keys/validate is called
    And "✅ Valid" confirmation text appears inline

  Scenario: Validate flow — failure
    Given the key input has an invalid key
    When the user clicks Validate
    Then "❌ <error message from API>" appears inline
    And the Save button remains disabled

  Scenario: Save key — success
    Given validation succeeded
    When the user clicks Save
    Then POST /api/workspaces/{id}/keys is called
    And the form collapses showing the new masked key
    And query cache is invalidated (card re-renders with updated state)

  Scenario: Delete key — confirm flow
    Given the card shows a configured key
    When user clicks Delete → confirms
    Then DELETE /api/workspaces/{id}/keys is called
    And the card shows "No key configured" state

  Scenario: Add File is disabled when no key
    Given the WorkspaceCard shows has_key: false
    Then the Add File button/link is disabled or hidden (enforced in UI)
    And a tooltip reads "Configure your AI provider first"
```

---

## 3. Implementation Guide

### 3.1 File to modify
`frontend/src/routes/app.teams.$teamId.tsx` — **modify only** (do NOT create a new route file).

Read the full file first before making any changes. Identify:
- The `WorkspaceCard` component (or inline JSX block per workspace)
- Where channels chips are rendered
- Existing mutation patterns (rename, make-default)

### 3.2 KeySection component
Create an inline functional component **within the same file** (not a separate import) to keep the diff small:

```typescript
function KeySection({ workspaceId, teamId }: { workspaceId: string; teamId: string }) {
  const { data: keyData, isLoading } = useKeyQuery(workspaceId);
  const saveMutation = useSaveKeyMutation(teamId);
  const deleteMutation = useDeleteKeyMutation(teamId);
  const [showForm, setShowForm] = useState(false);
  const [provider, setProvider] = useState<'google' | 'openai' | 'anthropic'>('openai');
  const [keyInput, setKeyInput] = useState('');
  const [validationResult, setValidationResult] = useState<{ valid: boolean; message: string } | null>(null);
  const [validating, setValidating] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  // ... render logic
}
```

### 3.3 Provider dropdown options
```typescript
const PROVIDERS = [
  { value: 'openai', label: 'OpenAI' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'google', label: 'Google (Gemini)' },
] as const;
```

### 3.4 Styling guidelines (ADR-022)
- All styling via Tailwind 4 utility classes (CSS-first `@theme` tokens already set up in `app.css`)
- Coral accent: `text-rose-500` / `bg-rose-500` (maps to brand coral `#F43F5E`)
- Status icons: use Lucide `CheckCircle2` (✅ valid), `AlertCircle` (❌ error), `Key` (key icon)
- Key input type: `type="password"` with a show/hide toggle button (👁 icon)
- Section border: `border border-slate-200 dark:border-slate-700 rounded-lg p-4`
- Button styling: reuse existing button patterns from workspace card (rename/delete buttons)

### 3.5 Disable Add File button
After STORY-004-04 lands, the "Add File" button (to be built in EPIC-006) should check `has_key`. Since EPIC-006 hasn't landed yet, add a placeholder disabled state in the workspace card now:

```typescript
// Placeholder — wired up in EPIC-006
const canAddFile = keyData?.has_key === true;
// <button disabled={!canAddFile} title={!canAddFile ? "Configure your AI provider first" : undefined}>
//   Add File
// </button>
```
This sets up the guard so EPIC-006 just needs to render the real button component.

### 3.6 Manual E2E Verification Checklist
The Developer runs this against the live `https://teemo.soula.ge` after merging:

- [ ] Load `/app` → navigate to a Slack team → open a workspace
- [ ] Workspace with no key shows "No key configured" + "+ Add key" button
- [ ] Click "+ Add key" → form expands with provider dropdown + key input
- [ ] Type an **invalid** key → click Validate → "❌ Invalid" shows, Save button disabled
- [ ] Type a **valid** key → click Validate → "✅ Valid" shows, Save button enabled
- [ ] Click Save → form collapses → masked key + provider badge visible
- [ ] Refresh page → masked key still shown (persisted in DB)
- [ ] Click Update → form re-opens (provider pre-selected, key input empty)
- [ ] Click Delete → confirm appears → confirm → "No key configured" state returns
- [ ] Verify network tab: no plaintext key in response body of GET /api/workspaces/{id}/keys
- [ ] Verify console: no plaintext key logged anywhere

---

## 4. Test Requirements

Write `frontend/src/routes/__tests__/key-section.test.tsx` (min 3 tests):

1. `renders no-key state when has_key is false` — mock `useKeyQuery` → `{has_key: false}`. Assert "+ Add key" button visible.
2. `renders masked key when has_key is true` — mock → `{has_key: true, key_mask: "sk-a...xyz9", provider: "openai"}`. Assert mask text visible.
3. `validate button calls validateKey API` — fire Validate click, assert `validateKey` mock called with correct args.

---

## Change Log
| Date | Change | By |
|------|--------|-----|
| 2026-04-12 | Story created from EPIC-004 decomposition | Claude (doc-manager) |
