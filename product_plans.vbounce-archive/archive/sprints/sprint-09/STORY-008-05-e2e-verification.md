---
story_id: "STORY-008-05-e2e-verification"
parent_epic_ref: "EPIC-008"
status: "Refinement"
ambiguity: "🟢 Low"
context_source: "Epic §7 / Charter §5.3, §5.5 / Codebase"
actor: "Hackathon Judge"
complexity_label: "L2"
---

# STORY-008-05: E2E Setup Flow Verification

**Complexity: L2** — Manual verification across full flow, defect fixes, ~2-4hr

---

## 1. The Spec (The Contract)

### 1.1 User Story
This story verifies the complete first-time user journey end-to-end on the deployed environment. It catches integration seams that unit tests miss: OAuth redirect re-entry, cross-page navigation, data flow between guided setup steps, and visual coherence across the full dashboard. Any defects found are fixed in-place.

### 1.2 Detailed Requirements
- **R1**: Execute the full golden path on the deployed environment (`https://teemo.soula.ge`):
  1. Register new account → login → empty dashboard with top nav
  2. Install Slack → team appears
  3. Click team → workspace list → "New Workspace" → name it → navigate to guided setup
  4. Step 1: Connect Drive (OAuth round-trip → return → step completes)
  5. Step 2: Configure AI key (select provider → enter key → validate → save → step completes)
  6. Step 3: Add file from Picker (select file → AI description generates → step completes)
  7. Step 4: Bind channel (pick channel → chip shows "Pending /invite" → copy snippet)
  8. Setup complete → normal detail view visible
  9. In Slack: run `/invite @tee-mo` in the bound channel → dashboard refresh shows "Active" status
  10. In Slack: @mention Tee-Mo with a question about the indexed file → bot answers in thread
- **R2**: Verify second-workspace flow: from the same team, create another workspace. Confirm guided setup activates, Slack install is NOT repeated, channel picker excludes channels already bound to the first workspace.
- **R3**: Verify edge cases:
  - OAuth cancel: clicking "Cancel" on Google consent screen returns to workspace detail without error, Drive step remains incomplete
  - Back navigation: pressing browser back during guided setup returns to workspace list, re-entering workspace re-activates guided mode at correct step
  - BYOK gate: step 3 (Files) is gated until step 2 (Key) is complete — "Add File" button is not accessible
  - File cap: if workspace has 15 files, "Add File" is disabled with clear indicator
  - Channel 409: binding a channel already bound to another workspace shows error toast/message
  - Missing team token: if Slack team token is invalid/revoked, channel list fails gracefully
- **R4**: Visual coherence check:
  - Top nav present on every `/app/*` page
  - No hardcoded `#E94560` visible (all coral is via brand tokens)
  - Buttons use consistent styling (Button component variants)
  - Typography follows design guide (Inter font, max font-semibold, correct text colors)
  - Toasts fire for OAuth callbacks (no FlashBanner remnants)
  - Empty states use dashed border pattern where applicable
- **R5**: Fix any defects found during verification. Each fix is committed with a descriptive message referencing this story.
- **R6**: Update the roadmap §7 Delivery Log with the sprint entry.

### 1.3 Out of Scope
- Performance optimization
- Accessibility audit (EPIC-009 territory)
- Seed data creation (EPIC-010)
- Skills demonstration (already verified in S-07)

### TDD Red Phase: No
> Manual E2E verification story — no automated Red phase.

---

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria (Gherkin/Pseudocode)
```gherkin
Feature: E2E Setup Flow Verification

  Scenario: Full golden path — registration to bot answer
    Given a fresh user account on https://teemo.soula.ge
    When the user completes the full setup flow (register → Slack → workspace → Drive → BYOK → file → channel → @mention)
    Then the bot answers the @mention in a Slack thread using knowledge from the indexed Drive file

  Scenario: Second workspace setup
    Given a team with one fully configured workspace
    When the user creates a second workspace
    Then guided setup activates for the new workspace
    And the Slack install step is not shown (team already installed)
    And the channel picker excludes channels bound to the first workspace

  Scenario: OAuth cancel recovery
    Given a user on step 1 (Connect Drive) in guided setup
    When they click "Connect Drive" then cancel on Google consent
    Then they return to the workspace detail page
    And step 1 remains incomplete (no error, no crash)

  Scenario: Browser back navigation
    Given a user on step 2 in guided setup
    When they press browser back
    Then they return to the workspace list
    And re-navigating to the workspace shows step 2 still active

  Scenario: BYOK gates file step
    Given a workspace with Drive connected but no BYOK key
    When the user views the guided setup
    Then step 3 (Files) is collapsed and non-interactive
    And the step indicator shows steps 3-4 as grayed out

  Scenario: Channel 409 conflict
    Given #general is bound to workspace A
    When the user tries to bind #general to workspace B
    Then an error message explains the channel is already bound

  Scenario: Visual coherence
    Given the user is on any /app page
    When the page renders
    Then the top nav shows "Tee-Mo" logo, "Workspaces" link, user email, and logout
    And no #E94560 hex is visible in computed styles (all coral is brand-500)
    And toasts appear for OAuth callbacks
```

### 2.2 Verification Steps (Manual)
- [ ] Golden path: register → login → install Slack → create workspace → Drive OAuth → BYOK → file → channel → @mention → bot answers
- [ ] Second workspace: create, setup, channel exclusion works
- [ ] OAuth cancel: Drive cancel recovers gracefully
- [ ] Back navigation: preserves guided setup state
- [ ] BYOK gate: step 3 inaccessible without step 2
- [ ] Channel 409: error displayed on conflict
- [ ] Visual: top nav on all pages, brand tokens, Button components, toasts, empty states
- [ ] `npm run build` succeeds (no regression)
- [ ] `npx vitest run` — all tests pass
- [ ] `pytest` — all backend tests pass
- [ ] Roadmap §7 updated

---

## 3. The Implementation Guide (AI-to-AI)

### 3.0 Environment Prerequisites
| Prerequisite | Value | Verified? |
|-------------|-------|-----------|
| **Env Vars** | All production env vars configured on Coolify | [ ] |
| **Services** | `https://teemo.soula.ge` accessible | [ ] |
| **Slack** | Test Slack workspace with Tee-Mo app installed | [ ] |
| **Google** | Google Cloud project with OAuth configured, test Google account with Drive files | [ ] |
| **BYOK** | Valid API key for at least one provider (OpenAI, Anthropic, or Google) | [ ] |
| **Stories** | STORY-008-01 through 008-04 all merged to main | [ ] |

### 3.1 Test Implementation
- No new automated tests. This story is manual E2E verification.
- Existing test suites (`vitest`, `pytest`) must pass as a regression gate.

### 3.2 Context & Files
| Item | Value |
|------|-------|
| **Primary File** | N/A — verification story, fixes touch whatever is broken |
| **Related Files** | All files from STORY-008-01 through 008-04 |
| **New Files Needed** | No (unless defect fixes require new files) |
| **ADR References** | ADR-022, ADR-024, ADR-025 |
| **First-Use Pattern** | No |

### 3.3 Technical Logic
- Deploy latest main to Coolify (push triggers auto-deploy per ADR-026)
- Walk through each verification step manually
- For each defect:
  1. Document the symptom
  2. Identify the root cause
  3. Fix in the appropriate file
  4. Verify the fix
  5. Commit with message referencing this story
- After all fixes: re-run `npm run build`, `npx vitest run`, `pytest` as regression gates

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations
| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Manual E2E | 7 | One per scenario in §2.1 |
| Regression | All | `vitest run` + `pytest` must pass |

### 4.2 Definition of Done (The Gate)
- [ ] All 7 verification scenarios in §2.1 pass on deployed environment.
- [ ] All defects found are fixed and committed.
- [ ] `npm run build` passes.
- [ ] `npx vitest run` passes.
- [ ] `pytest` passes.
- [ ] FLASHCARDS.md consulted. Any new lessons from defect fixes are flagged.
- [ ] Roadmap §7 Delivery Log updated with sprint entry.

---

## Token Usage
| Agent | Input | Output | Total |
|-------|-------|--------|-------|
