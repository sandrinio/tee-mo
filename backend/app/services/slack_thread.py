"""Thread history service for Slack conversations.

Fetches the reply history for a Slack thread and annotates each message
with a speaker role ("user" or "assistant") and a display name.

The trigger message (the last message in the thread — the user's most
recent request that initiated the bot response cycle) is excluded from
the returned history; callers pass it separately as the current prompt.

FLASHCARDS compliance:
  - [S-04] AsyncWebClient imported at module level so tests can monkeypatch
    `_make_client` via monkeypatch.setattr.
  - No FastAPI imports — this module is pure async service logic.
"""

from __future__ import annotations

from pydantic_ai.messages import ModelRequest, ModelResponse, UserPromptPart, TextPart
from slack_sdk.web.async_client import AsyncWebClient


def _make_client(bot_token: str) -> AsyncWebClient:
    """Create a Slack AsyncWebClient authenticated with the given bot token.

    Defined as a module-level factory so that tests can monkeypatch it to
    inject a FakeAsyncWebClient without any network calls.

    Args:
        bot_token: A Slack bot OAuth token (``xoxb-...``).

    Returns:
        An ``AsyncWebClient`` instance configured with the supplied token.
    """
    return AsyncWebClient(token=bot_token)


async def fetch_thread_history(
    bot_token: str,
    channel: str,
    thread_ts: str,
    bot_user_id: str,
) -> list[dict]:
    """Fetch and annotate the reply history for a Slack thread.

    Calls ``conversations.replies`` to retrieve all messages in the thread
    identified by ``channel`` + ``thread_ts``, then maps each message to a
    dict with ``role``, ``name``, and ``content`` fields.

    The **last** message in the thread is treated as the trigger (the prompt
    that caused this handler to be invoked) and is excluded from the result.
    This allows callers to pass the trigger separately as the active user
    prompt.

    Speaker identification rules (evaluated in order):
    1. If the message has a ``bot_id`` field → role ``"assistant"``, name ``"Tee-Mo"``.
    2. If ``msg["user"] == bot_user_id`` → role ``"assistant"``, name ``"Tee-Mo"``.
    3. Otherwise → role ``"user"``, name resolved from ``users.info``.

    User name resolution is cached per call (a ``dict`` built during this
    invocation) to avoid redundant API calls when the same user appears
    multiple times in the thread.  On any exception from ``users.info``,
    the name falls back to ``f"User {user_id}"``.

    Args:
        bot_token: Slack bot OAuth token used to authenticate API calls.
        channel: Slack channel ID that contains the thread.
        thread_ts: Timestamp of the root (parent) message of the thread.
        bot_user_id: The bot's Slack user ID (``UBOT...``).  Messages from
            this user ID are treated as assistant turns.

    Returns:
        A list of pydantic-ai ``ModelMessage`` objects (``ModelRequest`` for
        user turns, ``ModelResponse`` for assistant turns) in chronological
        order.  The trigger (last) message is not included.
    """
    client = _make_client(bot_token)

    response = await client.conversations_replies(channel=channel, ts=thread_ts)
    messages: list[dict] = response.get("messages", [])

    # Exclude the trigger — the last message in the thread
    history = messages[:-1] if messages else []

    # Per-call cache: user_id → resolved display name
    user_name_cache: dict[str, str] = {}

    result: list = []

    for msg in history:
        text: str = msg.get("text", "")
        # Determine role first — bot_id field takes priority over user match
        if msg.get("bot_id") or msg.get("user") == bot_user_id:
            result.append(ModelResponse(parts=[TextPart(content=text)]))
        else:
            user_id: str = msg.get("user", "unknown")
            name = await _resolve_user_name(client, user_id, user_name_cache)
            result.append(ModelRequest(parts=[UserPromptPart(content=f"{name}: {text}")]))

    return result


async def _resolve_user_name(
    client: AsyncWebClient,
    user_id: str,
    cache: dict[str, str],
) -> str:
    """Resolve a Slack user ID to a display name, with in-memory caching.

    Attempts to look up ``user_id`` in ``cache`` first.  On a cache miss,
    calls ``users.info`` and stores the result before returning it.

    Falls back to ``f"User {user_id}"`` on any exception (network error,
    invalid user, permission denied, etc.).

    Args:
        client: The ``AsyncWebClient`` to use for the API call.
        user_id: The Slack user ID to resolve (e.g. ``"U001"``).
        cache: Mutable dict shared across the current
            ``fetch_thread_history`` invocation; updated in-place.

    Returns:
        The user's display name, or ``f"User {user_id}"`` on failure.
    """
    if user_id in cache:
        return cache[user_id]

    try:
        info = await client.users_info(user=user_id)
        profile = info.get("user", {}).get("profile", {})
        # Prefer display_name; fall back to real_name
        name = profile.get("display_name") or profile.get("real_name") or f"User {user_id}"
    except Exception:
        name = f"User {user_id}"

    cache[user_id] = name
    return name
