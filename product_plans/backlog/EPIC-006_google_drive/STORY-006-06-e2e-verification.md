---
story_id: "STORY-006-06-e2e-verification"
parent_epic_ref: "EPIC-006"
status: "Refinement"
ambiguity: "🟢 Low"
context_source: "Epic §7 / Charter §1.3 Success Definition"
actor: "Solo dev"
complexity_label: "L1"
---

# STORY-006-06: Manual E2E Verification — Drive → Slack Answer Pipeline

**Complexity: L1** — No code, manual verification of full pipeline

---

## 1. The Spec (The Contract)

### 1.1 User Story
This story verifies the complete Drive knowledge pipeline end-to-end: connect Drive, index a file, @mention the bot in Slack, and confirm the bot reads the file and answers correctly. No code — purely manual verification on live infrastructure.

### 1.2 Detailed Requirements
- **R1**: Complete Google Cloud Console setup (origins, redirect URIs, APIs enabled, test users — per setup guide).
- **R2**: Connect Google Drive to a workspace via dashboard.
- **R3**: Index at least 2 files of different MIME types (e.g., a Google Doc + a PDF).
- **R4**: Verify AI descriptions are generated and visible in the dashboard file list.
- **R5**: @mention the bot in a bound Slack channel with a question answerable from one of the indexed files.
- **R6**: Confirm the bot reads the relevant file (visible in agent behavior — it should reference file content in its answer).
- **R7**: Verify self-healing: change the Drive file content, ask the bot again, confirm `ai_description` updates.
- **R8**: Test all 3 providers if keys available (at minimum test 1 provider end-to-end).

### 1.3 Out of Scope
- Automated E2E tests (not feasible — requires real Google OAuth + Slack)
- Performance testing
- Error scenario testing (deferred to EPIC-009)

### TDD Red Phase: No — manual verification only

---

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria (Gherkin/Pseudocode)
```gherkin
Feature: Full Drive Pipeline E2E

  Scenario: Connect Drive and index a file
    Given a workspace with BYOK key and Slack channel bound
    When the admin connects Google Drive via OAuth
    And picks a Google Doc via Picker
    Then the file appears in the dashboard with an AI-generated description

  Scenario: Bot answers from Drive file
    Given a workspace with an indexed Google Doc about "refund policy"
    When a user @mentions the bot: "What is our refund policy?"
    Then the bot replies in-thread with information from the indexed file

  Scenario: Self-healing on file change
    Given an indexed file whose content the admin has just edited in Google Drive
    When the bot reads the file on the next question
    Then the ai_description in the database is updated to reflect the new content

  Scenario: Multi-provider smoke test
    Given workspaces configured with each available provider
    When a question is asked in each workspace
    Then each provider returns a valid answer
```

### 2.2 Verification Steps (Manual)
- [ ] Google Cloud Console: JS origins, redirect URIs, Drive API, Picker API all configured
- [ ] Dashboard: "Connect Google Drive" → OAuth flow → "Connected as email@..." shown
- [ ] Dashboard: Picker opens → select a Google Doc → file appears with AI description
- [ ] Dashboard: Picker opens → select a PDF → file appears with AI description
- [ ] Dashboard: File count shows correctly (e.g., "2/15 files")
- [ ] Slack: @mention bot with question about Doc content → bot answers correctly in-thread
- [ ] Slack: @mention bot with question about PDF content → bot answers correctly
- [ ] Drive: Edit the Google Doc → @mention bot again → answer reflects updated content
- [ ] Dashboard: AI description for the changed file has been updated
- [ ] (Optional) Repeat with Anthropic, OpenAI, Google providers

---

## 3. The Implementation Guide (AI-to-AI)

### 3.0 Environment Prerequisites
| Prerequisite | Value | Verified? |
|-------------|-------|-----------|
| **Dependencies** | ALL prior EPIC-006 stories merged and deployed | [ ] |
| **Google Cloud** | Setup guide steps 1-5 complete | [ ] |
| **Slack** | App configured with event subscriptions + channel bound to workspace | [ ] |
| **BYOK** | At least 1 provider key configured on the workspace | [ ] |

### 3.1 Test Implementation
- No code. This is a manual verification story.

### 3.2 Context & Files
| Item | Value |
|------|-------|
| **Primary File** | N/A — manual verification |
| **Related Files** | `google-cloud-setup-guide.md` (follow the checklist) |
| **New Files Needed** | No |
| **ADR References** | All EPIC-006 ADRs |
| **First-Use Pattern** | No |

### 3.3 Technical Logic
- Follow the verification steps in §2.2 sequentially.
- Record any issues found as bugs or flashcards.

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations
| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Unit tests | 0 | N/A — manual |
| E2E tests | 0 | N/A — this IS the E2E verification |

### 4.2 Definition of Done (The Gate)
- [ ] All verification steps in §2.2 checked off.
- [ ] At least 1 full pipeline run (Drive connect → file index → Slack answer) successful.
- [ ] Any issues filed as bugs or flashcards.

---

## Token Usage
| Agent | Input | Output | Total |
|-------|-------|--------|-------|
