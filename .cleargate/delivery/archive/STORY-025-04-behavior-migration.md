---
story_id: "STORY-025-04"
parent_epic_ref: "EPIC-025"
status: "Shipped"
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

# STORY-025-04: Behavior Group Migration
**Complexity:** L1 — chrome only, ~1.5hr

## 1. The Spec

### 1.1 User Story
As a workspace admin, I want Persona / Skills / Automation rendered inside the new shell with the redesigned content treatments, so that Tee-Mo's behavior settings are organized into one tab.

### 1.2 Detailed Requirements
- **PersonaSection** — extract from route into its own file. Existing textarea + Save mutation + character counter + saved/error toast preserved verbatim. Only the surrounding card chrome and header treatment update (h2 header inside ModuleSection, no inner double border).
- **SkillsSection** — re-skin existing read-only list. Divider list per row: sparkles icon (lucide) + mono `/teemo skill-name` (rose-500 bg-rose-50 chip) + caption "{summary}" (slate-500 12px). NO Edit button (ADR-023 chat-only CRUD).
- **AutomationsSection** — re-skin only the empty state: 40×40 slate-100 zap-icon tile + "No automations yet" (16px/600) + caption "Trigger Tee-Mo on a schedule, on a Slack event, or from a webhook." + "Create automation" secondary button. Populated state preserved verbatim.
- All 3 mounted as ModuleSection children of the Behavior group.
- Status resolvers: **Persona `ok` if `bot_persona` non-empty, `empty` otherwise — the textarea always renders regardless of state, status dot just reflects the truth (no "must fill" warning).** Skills `ok` if any skills, `empty` otherwise; Automation `ok` if any triggers, `empty` otherwise.

### 1.3 Out of Scope
- Voice preset 4-button picker (dropped per epic §6 Q2 — Persona stays as-is).
- Skill Edit action (chat-only per ADR-023).
- Automation populated-state visual changes.

## 2. The Truth

### 2.1 Acceptance Criteria

```gherkin
Feature: Behavior group migration

  Scenario: Persona behavior preserved
    Given the user changes the persona text and clicks Save
    Then the existing useUpdateWorkspaceMutation fires with the new bot_persona
    And on success a "Saved successfully" pill appears

  Scenario: Skills divider list renders without Edit
    Given the workspace has 2 skills
    Then 2 rows render separated by dividers
    And each row shows the sparkles icon, mono /teemo skill-name chip, and summary caption
    And no Edit button is rendered

  Scenario: Automation empty state matches handoff
    Given the workspace has zero automations
    Then the empty state shows the slate-100 zap tile, "No automations yet" headline, caption, and Create automation secondary button

  Scenario: Automation populated state preserved
    Given the workspace has 2 automations
    Then the existing populated list renders unchanged from current behavior

  Scenario: Persona status reflects empty vs filled
    Given bot_persona is "" (empty string)
    Then the Persona statusResolver returns "empty"
    And the textarea still renders with placeholder text
    Given bot_persona is "Helpful internal assistant."
    Then the Persona statusResolver returns "ok"
```

### 2.2 Verification Steps (Manual)
- [ ] Edit persona text → save → reload → text persists. Existing behavior intact.
- [ ] Empty state visuals match handoff README §"Module bodies" → Automation.
- [ ] Skills row renders for each skill with no Edit affordance.

## 3. Implementation Guide

### 3.1 Files

| Item | Value |
|---|---|
| New | `frontend/src/components/workspace/PersonaSection.tsx` (extracted from route) |
| New | `frontend/src/components/workspace/SkillsSection.tsx` (extracted from route) |
| Modify | `frontend/src/components/workspace/AutomationsSection.tsx` — empty-state markup only |
| Modify | `frontend/src/routes/app.teams.$teamId.$workspaceId.tsx` — remove inline PersonaSection + SkillsSection definitions |
| Modify | `frontend/src/components/workspace/moduleRegistry.ts` — Behavior group entries + status resolvers |

### 3.2 Technical Logic
- PersonaSection: copy lines 739-806 of the route file into its own file; replace the inner `<Card>` + h2 with the ModuleSection header (passed via parent) so styling doesn't double.
- SkillsSection: copy lines 831-875 likewise. The existing `<Card>` wraps the divider list; replace per-row card with `divide-y divide-slate-100` container.
- AutomationsSection: locate the existing empty-state JSX (search for the current empty branch) and replace markup with handoff spec. Populated branch untouched.

### 3.3 API Contract
None new.

## 4. Quality Gates

### 4.1 Minimum Test Expectations

| Test Type | Min | Notes |
|---|---|---|
| Vitest unit | 5 | One per Gherkin scenario (incl. Persona resolver empty-vs-filled) |
| Existing | green | AutomationsSection, useWorkspaces, useSkills tests must pass unchanged |

### 4.2 Definition of Done
- [ ] All §2.1 scenarios covered.
- [ ] `npm run typecheck` clean.
- [ ] No regression in AutomationsSection / SetupStepper / KeySection test suites.
- [ ] Manual verification §2.2 completed.

---

## ClearGate Ambiguity Gate
**Current Status: 🟢 Low — Ready for Execution**
