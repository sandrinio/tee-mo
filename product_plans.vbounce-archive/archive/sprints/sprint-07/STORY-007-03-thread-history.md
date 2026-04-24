---
story_id: "STORY-007-03-thread-history"
parent_epic_ref: "EPIC-007"
status: "Ready to Bounce"
ambiguity: "🟢 Low"
context_source: "Epic §2 / Charter §5.1 step 5"
actor: "Agent (internal consumer)"
complexity_label: "L2"
---

# STORY-007-03: Thread History Service with Speaker Identification

**Complexity: L2** — Standard: 1 new service file + 1 test file, Slack Web API integration.

---

## 1. The Spec (The Contract)

### 1.1 User Story
This story creates `backend/app/services/slack_thread.py` — a service that fetches Slack thread messages via `conversations.replies` and formats them with speaker display names for the AI agent's conversation context.

### 1.2 Detailed Requirements
- **R1**: `fetch_thread_history(bot_token, channel, thread_ts, bot_user_id) -> list[dict]` — returns formatted thread messages.
- **R2**: Each message in the returned list is `{"role": "user" | "assistant", "name": str, "content": str}`.
    - Messages from `bot_user_id` get `role: "assistant"`, `name: "Tee-Mo"`.
    - Messages from other users get `role: "user"`, `name: "<display_name>"`.
- **R3**: Speaker display names are resolved via `users.info` API call. Cache user lookups within a single `fetch_thread_history` call (a thread may have the same user multiple times).
- **R4**: If `users.info` fails for a user, fall back to `"User <user_id>"` — never crash on name resolution.
- **R5**: The bot's own messages (matched by `bot_user_id` OR `bot_id` field) are labeled as assistant messages so the AI model gets proper role separation.
- **R6**: Messages are returned in chronological order (oldest first), excluding the very last message (which is the trigger — the dispatch will pass it separately as the user prompt).
- **R7**: Uses `slack_sdk.web.async_client.AsyncWebClient` with the decrypted bot token. Does NOT use the Slack Bolt app — direct Web API calls.
- **R8**: Module has NO FastAPI imports. Pure async function taking a token string.

### 1.3 Out of Scope
- Thread history caching across requests — each event gets a fresh fetch
- Token counting / truncation of long threads — EPIC-009
- Rich message formatting (blocks, attachments) — V1 extracts `.text` only
- File/image attachments in thread messages — text only

### TDD Red Phase: Yes

---

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria (Gherkin/Pseudocode)
```gherkin
Feature: Thread History Service

  Scenario: Fetch thread with multiple speakers
    Given a thread with messages from Alice (U001), Bob (U002), and the bot (UBOT)
    When fetch_thread_history(token, channel, ts, "UBOT") is called
    Then 3 message dicts are returned (excluding the trigger message)
    And Alice's messages have role="user", name="Alice"
    And Bob's messages have role="user", name="Bob"
    And the bot's messages have role="assistant", name="Tee-Mo"

  Scenario: User name resolution failure
    Given a thread with a message from user U999 whose users.info call fails
    When fetch_thread_history() is called
    Then the message has role="user", name="User U999"
    And no exception is raised

  Scenario: Empty thread (top-level trigger)
    Given a thread_ts that has only the trigger message
    When fetch_thread_history() is called
    Then an empty list is returned

  Scenario: Bot message identified by bot_id field
    Given a thread message with bot_id="B123" (no user field matching bot_user_id)
    When fetch_thread_history() is called
    Then the message has role="assistant", name="Tee-Mo"

  Scenario: Messages in chronological order
    Given 5 messages in a thread with timestamps t1 < t2 < t3 < t4 < t5
    When fetch_thread_history() is called
    Then messages are returned ordered t1, t2, t3, t4 (t5 excluded as trigger)
```

### 2.2 Verification Steps (Manual)
- [ ] All tests pass with `pytest backend/tests/test_slack_thread.py -v`
- [ ] Full backend suite passes

---

## 3. The Implementation Guide (AI-to-AI)

### 3.0 Environment Prerequisites
| Prerequisite | Value | Verified? |
|-------------|-------|-----------|
| **Dependencies** | `slack_sdk` (already installed via `slack-bolt`) | [ ] |

### 3.1 Test Implementation
- Create `backend/tests/test_slack_thread.py`
- 5+ tests matching Gherkin scenarios
- Mock `AsyncWebClient` — create a `FakeAsyncWebClient` class that returns canned responses for `conversations_replies` and `users_info`
- Test the user name caching within a single call (same user_id should only trigger one `users_info` call)

### 3.2 Context & Files
| Item | Value |
|------|-------|
| **Primary File** | `backend/app/services/slack_thread.py` (new) |
| **Related Files** | None — self-contained |
| **New Files Needed** | Yes — `slack_thread.py`, `tests/test_slack_thread.py` |
| **ADR References** | ADR-021 (Slack event scope), ADR-010 (bot token security) |
| **First-Use Pattern** | **Yes** — first use of `AsyncWebClient` directly (prior Slack code uses Bolt or raw httpx). |

### 3.3 Technical Logic
```python
from slack_sdk.web.async_client import AsyncWebClient

async def fetch_thread_history(
    bot_token: str,
    channel: str,
    thread_ts: str,
    bot_user_id: str,
) -> list[dict]:
    client = AsyncWebClient(token=bot_token)
    result = await client.conversations_replies(channel=channel, ts=thread_ts)
    messages = result.get("messages", [])

    # Exclude last message (the trigger)
    history = messages[:-1] if len(messages) > 1 else []

    # Cache user display names within this call
    user_names: dict[str, str] = {}

    formatted = []
    for msg in history:
        user_id = msg.get("user", "")
        is_bot = msg.get("bot_id") or user_id == bot_user_id

        if is_bot:
            formatted.append({"role": "assistant", "name": "Tee-Mo", "content": msg.get("text", "")})
        else:
            name = user_names.get(user_id)
            if name is None:
                try:
                    info = await client.users_info(user=user_id)
                    name = info["user"]["profile"].get("display_name") or info["user"].get("real_name", f"User {user_id}")
                except Exception:
                    name = f"User {user_id}"
                user_names[user_id] = name
            formatted.append({"role": "user", "name": name, "content": msg.get("text", "")})

    return formatted
```

Key design decisions:
- `AsyncWebClient` is instantiated per call with the bot token — no caching the client (tokens differ by team).
- User name cache is scoped to the function call — no cross-request state.
- `.text` only — rich blocks/attachments are ignored in V1.
- Returns list of dicts, not Pydantic AI message objects. The dispatch layer (STORY-007-05) will convert to the appropriate format.

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations
| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Unit tests | 5 | 1 per Gherkin scenario |
| Integration tests | 0 | N/A — mocked Slack client |

### 4.2 Definition of Done (The Gate)
- [ ] TDD enforced: Red phase tests written and verified failing before Green phase.
- [ ] 5+ tests passing.
- [ ] FLASHCARDS.md consulted.
- [ ] No FastAPI imports in module.

---

## Token Usage
| Agent | Input | Output | Total |
|-------|-------|--------|-------|
| Developer | 159 | 1,078 | 1,237 |
| Developer | 21 | 1,253 | 1,274 |
