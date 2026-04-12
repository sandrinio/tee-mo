"""Tests for STORY-007-03 — Thread History Service with Speaker Identification.

Covers all 5 Gherkin scenarios from the story spec §2.1:
1. Fetch thread with multiple speakers (Alice, Bob, bot)
2. User name resolution failure (users.info raises) → graceful fallback
3. Empty thread (only trigger message) → returns empty list
4. Bot message identified by bot_id field (no user == bot_user_id match)
5. Messages in chronological order (5 messages → first 4 returned)

Strategy:
- Module under test: app.services.slack_thread
- Function: fetch_thread_history(bot_token, channel, thread_ts, bot_user_id)
- Uses a hand-rolled FakeAsyncWebClient that satisfies AsyncWebClient's
  conversations_replies() and users_info() async interface.
- Tests are async, decorated with @pytest.mark.asyncio.
- All tests FAIL in RED phase because app/services/slack_thread.py does not exist yet.

Sprint context: S-07 rule — first use of AsyncWebClient; test with FakeAsyncWebClient.
FLASHCARDS.md consulted:
- [S-04] httpx/slack imports at module level so tests can monkeypatch.
- [S-05] Worktree .env copy required before running backend tests.
"""

from __future__ import annotations

from typing import Any

import pytest
import pytest_asyncio  # noqa: F401 — ensures pytest-asyncio is importable

from app.services.slack_thread import fetch_thread_history  # type: ignore[import]


# ---------------------------------------------------------------------------
# FakeAsyncWebClient — hand-rolled mock matching AsyncWebClient's interface.
# Supports conversations_replies(channel, ts) and users_info(user) calls.
# Both methods are async to match the real client's coroutine interface.
# ---------------------------------------------------------------------------


class FakeAsyncWebClient:
    """Minimal fake for slack_sdk.web.async_client.AsyncWebClient.

    Configured with fixture data at construction time. Raises SlackApiError
    for users whose IDs are in the `failing_user_ids` set, simulating a
    Slack API failure for those specific lookups.
    """

    def __init__(
        self,
        messages: list[dict[str, Any]],
        user_profiles: dict[str, dict[str, Any]] | None = None,
        failing_user_ids: set[str] | None = None,
    ) -> None:
        """Initialise the fake client.

        Args:
            messages: Full list of message dicts to return from conversations_replies,
                      including the trigger message as the last item.
            user_profiles: Mapping of user_id → profile dict with keys
                           ``display_name`` and/or ``real_name``.
            failing_user_ids: Set of user IDs for which users_info should raise
                              an exception, simulating API failure.
        """
        self._messages = messages
        self._user_profiles = user_profiles or {}
        self._failing_user_ids = failing_user_ids or set()

    async def conversations_replies(
        self, *, channel: str, ts: str
    ) -> dict[str, Any]:
        """Return a fake conversations.replies payload."""
        return {"ok": True, "messages": self._messages}

    async def users_info(self, *, user: str) -> dict[str, Any]:
        """Return a fake users.info payload or raise for failing user IDs."""
        if user in self._failing_user_ids:
            # Simulate a Slack API error for this user
            raise Exception(f"users_info failed for {user}")
        profile = self._user_profiles.get(user, {})
        return {
            "ok": True,
            "user": {
                "id": user,
                "profile": {
                    "display_name": profile.get("display_name", ""),
                    "real_name": profile.get("real_name", f"User {user}"),
                },
                "real_name": profile.get("real_name", f"User {user}"),
            },
        }


# ---------------------------------------------------------------------------
# Helper — build a user message dict
# ---------------------------------------------------------------------------


def _user_msg(user: str, text: str, ts: str) -> dict[str, Any]:
    """Build a minimal Slack user message dict."""
    return {"type": "message", "user": user, "text": text, "ts": ts}


def _bot_msg_by_user(user: str, text: str, ts: str) -> dict[str, Any]:
    """Build a Slack bot message identified by matching user == bot_user_id."""
    return {"type": "message", "user": user, "text": text, "ts": ts}


def _bot_msg_by_bot_id(bot_id: str, text: str, ts: str) -> dict[str, Any]:
    """Build a Slack bot message identified by the bot_id field (no user field)."""
    return {"type": "message", "bot_id": bot_id, "text": text, "ts": ts}


# ---------------------------------------------------------------------------
# Scenario 1: Fetch thread with multiple speakers
# Given a thread with messages from Alice (U001), Bob (U002), and bot (UBOT)
# When fetch_thread_history is called
# Then it returns role/name dicts for each non-trigger message:
#   Alice → role="user", name="Alice"
#   Bob   → role="user", name="Bob"
#   Bot   → role="assistant", name="Tee-Mo"
# And the trigger message (last) is excluded from the result
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_multiple_speakers_roles_and_names(monkeypatch: pytest.MonkeyPatch) -> None:
    """Thread with Alice, Bob, and bot messages → correct roles and names."""
    messages = [
        _user_msg("U001", "Hello from Alice", "1000.001"),
        _user_msg("U002", "Hello from Bob", "1000.002"),
        _bot_msg_by_user("UBOT", "Hello from Tee-Mo", "1000.003"),
        _user_msg("U001", "This is the trigger", "1000.004"),  # excluded
    ]
    profiles = {
        "U001": {"display_name": "Alice", "real_name": "Alice Smith"},
        "U002": {"display_name": "Bob", "real_name": "Bob Jones"},
    }
    fake_client = FakeAsyncWebClient(messages=messages, user_profiles=profiles)

    import app.services.slack_thread as slack_thread_module  # type: ignore[import]

    monkeypatch.setattr(
        slack_thread_module,
        "_make_client",
        lambda token: fake_client,
    )

    result = await fetch_thread_history(
        bot_token="xoxb-test",
        channel="C001",
        thread_ts="1000.001",
        bot_user_id="UBOT",
    )

    assert len(result) == 3
    assert result[0] == {"role": "user", "name": "Alice", "content": "Hello from Alice"}
    assert result[1] == {"role": "user", "name": "Bob", "content": "Hello from Bob"}
    assert result[2] == {"role": "assistant", "name": "Tee-Mo", "content": "Hello from Tee-Mo"}


# ---------------------------------------------------------------------------
# Scenario 2: User name resolution failure
# Given users.info fails for U999
# When fetch_thread_history is called
# Then the message has name="User U999" and no exception is raised
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_user_name_resolution_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """users.info failure for U999 → graceful fallback name, no exception."""
    messages = [
        _user_msg("U999", "A mystery message", "1000.001"),
        _user_msg("U001", "The trigger", "1000.002"),  # excluded
    ]
    fake_client = FakeAsyncWebClient(
        messages=messages,
        user_profiles={"U001": {"display_name": "Known User"}},
        failing_user_ids={"U999"},
    )

    import app.services.slack_thread as slack_thread_module  # type: ignore[import]

    monkeypatch.setattr(
        slack_thread_module,
        "_make_client",
        lambda token: fake_client,
    )

    result = await fetch_thread_history(
        bot_token="xoxb-test",
        channel="C001",
        thread_ts="1000.001",
        bot_user_id="UBOT",
    )

    assert len(result) == 1
    assert result[0]["name"] == "User U999"
    assert result[0]["role"] == "user"
    assert result[0]["content"] == "A mystery message"


# ---------------------------------------------------------------------------
# Scenario 3: Empty thread (only trigger message)
# Given a thread that has only the top-level trigger message
# When fetch_thread_history is called
# Then it returns an empty list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_thread_only_trigger(monkeypatch: pytest.MonkeyPatch) -> None:
    """Thread with only the trigger message → returns empty list."""
    messages = [
        _user_msg("U001", "Just the trigger, no replies", "1000.001"),
    ]
    fake_client = FakeAsyncWebClient(messages=messages, user_profiles={})

    import app.services.slack_thread as slack_thread_module  # type: ignore[import]

    monkeypatch.setattr(
        slack_thread_module,
        "_make_client",
        lambda token: fake_client,
    )

    result = await fetch_thread_history(
        bot_token="xoxb-test",
        channel="C001",
        thread_ts="1000.001",
        bot_user_id="UBOT",
    )

    assert result == []


# ---------------------------------------------------------------------------
# Scenario 4: Bot message identified by bot_id field
# Given a message with bot_id="B123" (no user field matching bot_user_id)
# When fetch_thread_history is called
# Then that message has role="assistant", name="Tee-Mo"
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bot_identified_by_bot_id_field(monkeypatch: pytest.MonkeyPatch) -> None:
    """Message with bot_id field (no user match) → role="assistant", name="Tee-Mo"."""
    messages = [
        _bot_msg_by_bot_id("B123", "I am a bot response via bot_id", "1000.001"),
        _user_msg("U001", "The trigger", "1000.002"),  # excluded
    ]
    fake_client = FakeAsyncWebClient(messages=messages, user_profiles={})

    import app.services.slack_thread as slack_thread_module  # type: ignore[import]

    monkeypatch.setattr(
        slack_thread_module,
        "_make_client",
        lambda token: fake_client,
    )

    result = await fetch_thread_history(
        bot_token="xoxb-test",
        channel="C001",
        thread_ts="1000.001",
        bot_user_id="UBOT",  # does NOT match "B123" — identified by bot_id instead
    )

    assert len(result) == 1
    assert result[0]["role"] == "assistant"
    assert result[0]["name"] == "Tee-Mo"
    assert result[0]["content"] == "I am a bot response via bot_id"


# ---------------------------------------------------------------------------
# Scenario 5: Messages in chronological order
# Given a thread with 5 messages
# When fetch_thread_history is called
# Then the first 4 are returned in order (5th excluded as trigger)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_messages_returned_in_chronological_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """5 thread messages → first 4 returned in chronological order; 5th (trigger) excluded."""
    messages = [
        _user_msg("U001", "Message 1", "1000.001"),
        _user_msg("U002", "Message 2", "1000.002"),
        _bot_msg_by_user("UBOT", "Message 3 from bot", "1000.003"),
        _user_msg("U001", "Message 4", "1000.004"),
        _user_msg("U002", "Message 5 — the trigger", "1000.005"),  # excluded
    ]
    profiles = {
        "U001": {"display_name": "Alice"},
        "U002": {"display_name": "Bob"},
    }
    fake_client = FakeAsyncWebClient(messages=messages, user_profiles=profiles)

    import app.services.slack_thread as slack_thread_module  # type: ignore[import]

    monkeypatch.setattr(
        slack_thread_module,
        "_make_client",
        lambda token: fake_client,
    )

    result = await fetch_thread_history(
        bot_token="xoxb-test",
        channel="C001",
        thread_ts="1000.001",
        bot_user_id="UBOT",
    )

    assert len(result) == 4
    assert result[0]["content"] == "Message 1"
    assert result[1]["content"] == "Message 2"
    assert result[2]["content"] == "Message 3 from bot"
    assert result[3]["content"] == "Message 4"
    # Verify role assignment is correct in the ordered list
    assert result[0]["role"] == "user"
    assert result[1]["role"] == "user"
    assert result[2]["role"] == "assistant"
    assert result[3]["role"] == "user"
