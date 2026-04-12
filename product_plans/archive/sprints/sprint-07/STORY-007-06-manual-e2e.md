---
story_id: "STORY-007-06-manual-e2e"
parent_epic_ref: "EPIC-007"
status: "Ready to Bounce"
ambiguity: "🟢 Low"
context_source: "Epic §7 / Charter §5.1"
actor: "Workspace Admin"
complexity_label: "L1"
---

# STORY-007-06: Manual E2E Verification + Provider Smoke Test

**Complexity: L1** — Trivial: manual testing checklist, no code changes.

---

## 1. The Spec (The Contract)

### 1.1 User Story
As a **Workspace Admin**, I want to verify end-to-end that the bot works with all three BYOK providers in a real Slack workspace, so that I can confirm the agent system is production-ready.

### 1.2 Detailed Requirements
- **R1**: Test the `app_mention` flow in a real Slack channel with each of the 3 providers (OpenAI, Anthropic, Google).
- **R2**: Test the `message.im` flow (DM the bot).
- **R3**: Test thread continuation — reply in an existing thread, verify the bot uses prior messages as context.
- **R4**: Test speaker identification — have a thread with 2+ human speakers, ask the bot to summarize what a specific person said.
- **R5**: Test skill creation — ask the bot to create a skill, then verify it appears in subsequent prompts.
- **R6**: Test error paths: unbound channel nudge, no BYOK key error.
- **R7**: Configure Slack app event subscriptions if not already done: add `app_mention` and `message.im` events at `https://teemo.soula.ge/api/slack/events`.
- **R8**: Bind at least one Slack channel to a workspace via the channel binding API (STORY-007-04).

### 1.3 Out of Scope
- Automated E2E tests — manual verification only
- Performance benchmarking — qualitative check only
- Frontend UI verification — all testing happens in Slack + API calls

### TDD Red Phase: No

---

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria (Gherkin/Pseudocode)
```gherkin
Feature: End-to-End Agent Verification

  Scenario: OpenAI provider works
    Given workspace W1 configured with ai_provider="openai", ai_model="gpt-4o"
    When user @mentions @tee-mo in a bound channel
    Then bot replies in-thread with a correct answer

  Scenario: Anthropic provider works
    Given workspace W1 reconfigured with ai_provider="anthropic", ai_model="claude-sonnet-4-6"
    When user @mentions @tee-mo
    Then bot replies in-thread

  Scenario: Google provider works
    Given workspace W1 reconfigured with ai_provider="google", ai_model="gemini-2.5-flash"
    When user @mentions @tee-mo
    Then bot replies in-thread

  Scenario: Thread continuation
    Given a thread with 3+ messages between the user and bot
    When user asks a follow-up question referencing earlier context
    Then bot's reply demonstrates awareness of thread history

  Scenario: Speaker identification
    Given a thread with messages from Alice and Bob
    When user asks "what did Alice say?"
    Then bot's reply correctly attributes Alice's messages

  Scenario: Skill creation and usage
    Given workspace with no skills
    When user says "@tee-mo create a skill called greeting that says hello in 3 languages"
    Then bot confirms skill creation
    When user later says "@tee-mo use the greeting skill"
    Then bot loads and applies the skill

  Scenario: Unbound channel nudge
    Given a channel with no workspace binding
    When user @mentions @tee-mo
    Then bot posts a nudge message with dashboard link

  Scenario: DM works
    Given a team with a default workspace
    When user sends a DM to the bot
    Then bot replies in the DM thread
```

### 2.2 Verification Steps (Manual)
- [ ] Slack app event subscriptions configured (app_mention + message.im)
- [ ] At least one channel bound to a workspace via API
- [ ] OpenAI: @mention in bound channel → reply received
- [ ] Anthropic: switch provider → @mention → reply received
- [ ] Google: switch provider → @mention → reply received
- [ ] Thread continuation: follow-up in existing thread → context-aware reply
- [ ] Speaker ID: multi-user thread → bot identifies speakers correctly
- [ ] Skill CRUD: create → use → delete via chat
- [ ] Unbound channel: @mention in unbound channel → nudge message
- [ ] DM: message bot directly → reply received
- [ ] Self-message filter: bot does NOT reply to its own DM messages

---

## 3. The Implementation Guide (AI-to-AI)

### 3.0 Environment Prerequisites
| Prerequisite | Value | Verified? |
|-------------|-------|-----------|
| **Prior Stories** | All STORY-007-01 through 007-05 merged and deployed | [ ] |
| **Slack App** | Event subscriptions: `app_mention`, `message.im` at `https://teemo.soula.ge/api/slack/events` | [ ] |
| **BYOK Keys** | Valid API keys for OpenAI, Anthropic, and Google configured on a workspace | [ ] |
| **Channel Binding** | At least one channel bound via `POST /api/workspaces/{id}/channels` | [ ] |

### 3.1 Test Implementation
- No automated tests — this is a manual verification story.
- Document results in the story's execution log.

### 3.2 Context & Files
| Item | Value |
|------|-------|
| **Primary File** | None — manual testing |
| **New Files Needed** | No |

### 3.3 Technical Logic

**Pre-test setup (user must do before this story runs):**

1. Configure Slack app event subscriptions in the Slack API dashboard:
   - Navigate to **Event Subscriptions** → toggle ON
   - Request URL: `https://teemo.soula.ge/api/slack/events`
   - Subscribe to bot events: `app_mention`, `message` (with `message.im` filter)
   - Save changes

2. Bind a channel via API:
   ```bash
   # Get auth cookie first (login)
   curl -X POST https://teemo.soula.ge/api/auth/login \
     -H "Content-Type: application/json" \
     -d '{"email":"...", "password":"..."}' -c cookies.txt

   # Bind a channel
   curl -X POST https://teemo.soula.ge/api/workspaces/{WORKSPACE_ID}/channels \
     -H "Content-Type: application/json" \
     -b cookies.txt \
     -d '{"slack_channel_id":"C0123..."}'
   ```

3. Ensure workspace has a BYOK key configured (done in S-06).

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations
| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Manual verification | 11 | All checkboxes in §2.2 |

### 4.2 Definition of Done (The Gate)
- [ ] All 11 manual verification steps checked.
- [ ] At least 2 of the 3 providers verified working (3rd may be blocked by key availability).
- [ ] No unhandled exceptions in server logs during testing.

---

## Token Usage
| Agent | Input | Output | Total |
|-------|-------|--------|-------|
