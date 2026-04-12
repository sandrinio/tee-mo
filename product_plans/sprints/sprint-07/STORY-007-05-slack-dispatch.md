---
story_id: "STORY-007-05-slack-dispatch"
parent_epic_ref: "EPIC-007"
status: "Ready to Bounce"
ambiguity: "🟢 Low"
context_source: "Epic §2 / Charter §5.1 / ADR-021, ADR-024, ADR-025"
actor: "Slack User"
complexity_label: "L3"
---

# STORY-007-05: Slack Event Dispatch (app_mention + DM handlers)

**Complexity: L3** — Cross-cutting: wires agent factory + thread history + channel binding + Slack Web API. Core integration story.

---

## 1. The Spec (The Contract)

### 1.1 User Story
As a **Slack User**, I want to @mention @tee-mo in a channel and receive an AI-powered reply in the same thread, so that I can get answers without leaving Slack.

### 1.2 Detailed Requirements
- **R1**: Replace the 202 passthrough in `slack_events.py` with real event dispatch. After signature verification passes and event type is `event_callback`, hand off to `slack_dispatch.py`.
- **R2**: `slack_events.py` returns 200 immediately for all `event_callback` payloads (Slack 3-second timeout). The agent work runs in `asyncio.create_task`.
- **R3**: `backend/app/services/slack_dispatch.py` — new module, the orchestration layer:
    - `handle_slack_event(event_payload: dict) -> None` — async top-level dispatcher.
    - Routes to `_handle_app_mention(event)` or `_handle_dm(event)` based on `event.type`.
- **R4**: `_handle_app_mention(event)`:
    1. Extract `channel`, `ts` (or `thread_ts` if in-thread), `team`, `text`.
    2. Query `teemo_workspace_channels` for workspace bound to this channel.
    3. If no binding → post unbound-channel nudge in-thread and return.
    4. Fetch thread history via `slack_thread.fetch_thread_history()`.
    5. Decrypt bot token from `teemo_slack_teams` (by `team`).
    6. Build agent via `build_agent(workspace_id, owner_user_id, supabase)`.
    7. Run agent with user message + history.
    8. Post reply via `chat.postMessage(channel, thread_ts, text=result)`.
- **R5**: `_handle_dm(event)`:
    1. Self-message filter: skip if `event.get("bot_id")` is set OR `event.get("user") == bot_user_id`.
    2. Query `teemo_workspaces` for default workspace (`is_default_for_team=true`) of the team.
    3. If no default → post "set up a workspace" nudge and return.
    4. Same agent flow as app_mention (steps 4-8 above).
- **R6**: Error handling — wrap the entire dispatch in try/except:
    - `ValueError("no_key_configured")` → post "No API key configured" message.
    - `ValueError("no_workspace")` → post "Workspace not found" message.
    - Any Pydantic AI provider error → post "Your API key was rejected by {provider}."
    - `SlackApiError` with `ratelimited` → post graceful "Tee-Mo is busy" message (best-effort — the rate limit may prevent even this).
    - Any unhandled exception → log the error, post generic "Something went wrong" message.
- **R7**: All `chat.postMessage` calls use `thread_ts` to reply in-thread. Top-level mentions use `event["ts"]` as `thread_ts`. In-thread mentions use `event["thread_ts"]`.
- **R8**: Bot token for posting comes from `teemo_slack_teams` (by `event["team"]`), NOT from the workspace.
- **R9**: Strip the `@tee-mo` mention prefix from the user message before passing to the agent (Slack includes `<@UBOT123>` in the text).
- **R10**: Module imports from `app.agents.agent` (build_agent) and `app.services.slack_thread` (fetch_thread_history). Uses `AsyncWebClient` for posting. Does NOT import FastAPI.

### 1.3 Out of Scope
- Event deduplication — V1 risk accepted
- Context pruning for long threads — EPIC-009
- `read_drive_file` tool on the agent — EPIC-006
- Frontend UI for any of this — the entire flow is Slack-native

### TDD Red Phase: Yes

---

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria (Gherkin/Pseudocode)
```gherkin
Feature: Slack Event Dispatch

  Scenario: app_mention in bound channel
    Given channel C001 is bound to workspace W1 with a valid BYOK key
    And the thread has 2 prior messages from Alice and Bob
    When an app_mention event arrives for channel C001
    Then the agent is built with workspace W1's config
    And the agent receives the thread history with Alice and Bob identified
    And chat.postMessage is called with thread_ts = event.ts
    And the response text is non-empty

  Scenario: app_mention in unbound channel
    Given channel C999 has no workspace binding
    When an app_mention event arrives for channel C999
    Then a nudge message is posted in-thread
    And no agent is built (no LLM call)

  Scenario: DM happy path
    Given team T001 has a default workspace W1 with a valid BYOK key
    When a message.im event arrives from user U001
    Then the agent runs with workspace W1
    And the reply is posted in-thread

  Scenario: DM self-message filter
    Given the bot's user_id is UBOT
    When a message.im event arrives with user=UBOT
    Then no processing occurs (early return)

  Scenario: DM with bot_id field
    Given a message.im event with bot_id="B123"
    Then no processing occurs (early return)

  Scenario: No BYOK key
    Given channel C001 is bound to workspace W1 with NO key
    When an app_mention event arrives
    Then a "No API key configured" message is posted in-thread
    And no LLM call is made

  Scenario: No default workspace for DM
    Given team T001 has no workspace with is_default_for_team=true
    When a message.im event arrives
    Then a "Set up a workspace first" nudge is posted

  Scenario: Slack events endpoint returns 200 immediately
    Given a valid signed event_callback payload
    When POST /api/slack/events
    Then 200 is returned within <100ms
    And the agent work runs asynchronously

  Scenario: Mention prefix stripped
    Given the event text is "<@UBOT123> what is the capital of France?"
    When the dispatch processes the event
    Then the agent receives "what is the capital of France?" (no mention prefix)
```

### 2.2 Verification Steps (Manual)
- [ ] All tests pass
- [ ] Full backend suite passes
- [ ] In real Slack: @mention bot in a bound channel → get AI reply
- [ ] In real Slack: DM the bot → get AI reply
- [ ] In real Slack: @mention in unbound channel → get nudge
- [ ] In real Slack: verify thread continuation works (reply in existing thread)

---

## 3. The Implementation Guide (AI-to-AI)

### 3.0 Environment Prerequisites
| Prerequisite | Value | Verified? |
|-------------|-------|-----------|
| **Prior Stories** | STORY-007-02 (agent factory), STORY-007-03 (thread history) must be merged | [ ] |
| **Env Vars** | `SLACK_SIGNING_SECRET`, `TEEMO_ENCRYPTION_KEY`, BYOK key on a workspace | [ ] |
| **Slack App** | Event subscriptions configured for `app_mention` + `message.im` at `https://teemo.soula.ge/api/slack/events` | [ ] |

### 3.1 Test Implementation
- Create `backend/tests/test_slack_dispatch.py`
- 9 tests matching Gherkin scenarios
- Mock: Supabase client, `build_agent` (return a mock agent), `fetch_thread_history`, `AsyncWebClient`
- For the integration test of `slack_events.py`, use the FastAPI TestClient with a valid signed payload
- The background task pattern (`asyncio.create_task`) makes direct assertion tricky — test the dispatch function directly, test the endpoint separately for 200 response

### 3.2 Context & Files
| Item | Value |
|------|-------|
| **Primary File** | `backend/app/services/slack_dispatch.py` (new) |
| **Related Files** | `backend/app/api/routes/slack_events.py` (modify), `backend/app/agents/agent.py` (read), `backend/app/services/slack_thread.py` (read), `backend/app/core/encryption.py` (decrypt bot token), `backend/app/core/db.py` (get_supabase) |
| **New Files Needed** | Yes — `slack_dispatch.py`, `tests/test_slack_dispatch.py` |
| **ADR References** | ADR-021 (event scope), ADR-024 (workspace model), ADR-025 (explicit binding), ADR-013 (no streaming) |
| **First-Use Pattern** | **Yes** — first use of `asyncio.create_task` for background work in Tee-Mo. |

### 3.3 Technical Logic

**Modify `slack_events.py`** — replace the 202 return with dispatch:
```python
import asyncio
from app.services.slack_dispatch import handle_slack_event

# After signature verification + JSON parse:
if payload.get("type") == "url_verification":
    return PlainTextResponse(payload.get("challenge", ""))

if payload.get("type") == "event_callback":
    asyncio.create_task(handle_slack_event(payload))
    return Response(status_code=200)

return Response(status_code=200)
```

**`slack_dispatch.py` structure:**
```python
async def handle_slack_event(payload: dict) -> None:
    event = payload.get("event", {})
    event_type = event.get("type")
    if event_type == "app_mention":
        await _handle_app_mention(event)
    elif event_type == "message" and event.get("channel_type") == "im":
        await _handle_dm(event)

async def _handle_app_mention(event: dict) -> None:
    # 1. Resolve workspace via workspace_channels
    # 2. If unbound → nudge
    # 3. Get bot token from slack_teams
    # 4. Fetch thread history
    # 5. Build agent
    # 6. Run agent
    # 7. Post reply

async def _handle_dm(event: dict) -> None:
    # 1. Self-message filter
    # 2. Resolve default workspace for team
    # 3. If no default → nudge
    # 4. Same as app_mention steps 3-7

async def _post_reply(bot_token: str, channel: str, thread_ts: str, text: str) -> None:
    client = AsyncWebClient(token=bot_token)
    await client.chat_postMessage(channel=channel, thread_ts=thread_ts, text=text)
```

**Mention stripping (R9):**
```python
import re
text = re.sub(r"<@[A-Z0-9]+>\s*", "", event.get("text", "")).strip()
```

**Thread_ts resolution (R7):**
```python
thread_ts = event.get("thread_ts") or event.get("ts")
```

**Agent invocation with history:**
```python
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, UserPromptPart

# Convert thread history dicts to Pydantic AI message objects
message_history = []
for msg in history:
    if msg["role"] == "user":
        message_history.append(ModelRequest(parts=[UserPromptPart(content=f'{msg["name"]}: {msg["content"]}')]))
    else:
        message_history.append(ModelResponse(parts=[TextPart(content=msg["content"])]))

result = await agent.run(user_prompt=f'{user_name}: {text}', message_history=message_history, deps=deps)
await _post_reply(bot_token, channel, thread_ts, result.data)
```

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations
| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Unit tests | 9 | 1 per Gherkin scenario |

### 4.2 Definition of Done (The Gate)
- [ ] TDD enforced: Red phase tests written and verified failing before Green phase.
- [ ] 9+ tests passing.
- [ ] `slack_events.py` returns 200 immediately (not blocking on agent).
- [ ] Self-message filter prevents bot reply loops.
- [ ] No FastAPI imports in `slack_dispatch.py`.
- [ ] FLASHCARDS.md consulted.

---

## Token Usage
| Agent | Input | Output | Total |
|-------|-------|--------|-------|
