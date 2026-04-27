"""
Slack event dispatch service — STORY-007-05.

Routes incoming Slack event_callback payloads to the appropriate handler:
  - ``app_mention`` (bot @-mentioned in a channel) → ``_handle_app_mention``
  - ``message`` with ``channel_type == "im"`` (DM to the bot) → ``_handle_dm``

Design decisions:
  - NO FastAPI imports. This module is pure async business logic; the HTTP
    layer (slack_events.py) calls ``handle_slack_event`` via asyncio.create_task.
  - All dependencies (get_supabase, decrypt, build_agent, fetch_thread_history,
    AsyncWebClient) are imported at MODULE LEVEL so tests can monkeypatch them
    via ``monkeypatch.setattr(module, "name", mock)`` without binding issues.
    (FLASHCARDS.md S-04 rule.)
  - The Supabase client is obtained fresh per event via ``get_supabase()``
    (FLASHCARDS.md health contract rule — never instantiate ad-hoc).
  - ValueError("no_key_configured") from build_agent is caught and converted
    to a user-facing Slack message rather than a silent failure.

Table access patterns:
  - teemo_workspace_channels: .select().eq("slack_channel_id").limit(1)
  - teemo_slack_teams: .select().eq("slack_team_id").limit(1)
  - teemo_workspaces: .select().eq("slack_team_id").eq("is_default_for_team", True).maybe_single()
"""

from __future__ import annotations

import asyncio
import logging
import re
from contextlib import AsyncExitStack

from slack_sdk.web.async_client import AsyncWebClient

import app.agents.agent as _agent_module
import app.core.db as _db_module
import app.core.encryption as _enc_module
import app.services.slack_thread as _thread_module
from app.services.slack_formatter import markdown_to_mrkdwn

# Re-export names so tests can monkeypatch them at this module's namespace level.
# Tests do:
#   monkeypatch.setattr(dispatch_module, "AsyncWebClient", ...)
# — AsyncWebClient is already a direct import above.
#
# For the other dependencies, we call them through the module references
# (e.g. _agent_module.build_agent) so that patching the source module
# (app.agents.agent.build_agent) takes effect without needing a separate
# re-patch here. However, to satisfy tests that patch these at agent_module
# and thread_module levels we call via module references.

logger = logging.getLogger(__name__)

# Minimum interval between Slack chat_update calls (seconds).
# Slack rate-limits chat.update to ~50/min per channel.
_STREAM_UPDATE_INTERVAL = 1.0
# Minimum character delta before triggering an update (avoids tiny flickers).
_STREAM_MIN_CHARS = 80


async def _resolve_channel_name(
    client: AsyncWebClient, channel_id: str
) -> str | None:
    """Look up a Slack channel's human-readable name via ``conversations.info``.

    Returns ``None`` on any failure (missing scope, channel not visible to the
    bot, network blip) — the agent prompt falls back to citing the ID alone in
    that case rather than blocking dispatch on an enrichment hop.
    """
    if not channel_id:
        return None
    try:
        info = await client.conversations_info(channel=channel_id)
        return info.get("channel", {}).get("name") or None
    except Exception as exc:
        logger.warning("conversations.info failed for %s: %s", channel_id, exc)
        return None


def _format_user_prompt(
    *,
    sender_name: str,
    text: str,
    channel_id: str | None,
    channel_name: str | None,
) -> str:
    """Wrap the user's text with an inline channel-context prefix.

    Models follow user-message context FAR more reliably than instructions
    buried in ``## Section`` headers in the system prompt. Putting the literal
    channel id (and name when ``conversations.info`` succeeded) right next to
    the question prevents the LLM from confabulating a similar-looking but
    fabricated channel id when it echoes the channel back to the user.

    Resulting shape::

        [context: in #ai-news, channel_id=C0B0BMH3Q1X]
        sandro.suladze: schedule a daily news digest...

    When the channel name is unknown (``conversations.info`` failed or the
    caller is not Slack), the name segment is dropped but the id is still
    inlined. When neither is available, the prefix is omitted entirely so
    non-Slack callers get the legacy shape unchanged.
    """
    parts: list[str] = []
    if channel_name:
        parts.append(f"in #{channel_name}")
    if channel_id:
        parts.append(f"channel_id={channel_id}")

    if not parts:
        return f"{sender_name}: {text}"

    return f"[context: {', '.join(parts)}]\n{sender_name}: {text}"


async def _stream_agent_to_slack(
    agent: object,
    user_prompt: str,
    client: AsyncWebClient,
    channel: str,
    thread_ts: str,
    *,
    deps: object,
    message_history: list | None = None,
) -> None:
    """Run the agent with streaming and progressively update a Slack message.

    Posts an initial "Thinking..." message, then streams tokens from the agent
    via ``agent.run_stream()``. The Slack message is updated periodically
    (rate-limited to avoid Slack API throttling).

    Args:
        agent: Pydantic AI Agent instance.
        user_prompt: The user's message text.
        client: Slack AsyncWebClient with bot token.
        channel: Slack channel ID to post in.
        thread_ts: Thread timestamp to reply in.
        deps: AgentDeps instance for the agent.
        message_history: Optional conversation history for multi-turn context.
    """
    import time

    # Post initial placeholder
    initial = await client.chat_postMessage(
        channel=channel,
        text="_Thinking..._",
        thread_ts=thread_ts,
    )
    msg_ts = initial["ts"]

    accumulated = ""
    last_update_time = time.monotonic()
    last_update_len = 0

    try:
        run_kwargs: dict = {"deps": deps}
        if message_history is not None:
            run_kwargs["message_history"] = message_history

        # AsyncExitStack enters each MCP server as an async context manager
        # BEFORE run_stream so __aexit__ runs even if run_stream raises.
        # getattr guard keeps existing test fixtures that build bare-bones fakes
        # (without mcp_servers) working without changes (precedent: _add_citation).
        # When mcp_servers is empty (the 99% case), the stack is a no-op.
        #
        # Resilience: a single broken MCP server (404, expired token, network)
        # MUST NOT crash the whole agent run. We try each server independently,
        # log + skip failures, and strip them from the agent's toolset list for
        # this run so the model can't try to call their tools mid-run.
        async with AsyncExitStack() as stack:
            failed_servers: list = []
            for server in getattr(deps, "mcp_servers", []):
                try:
                    await stack.enter_async_context(server)
                except Exception as mcp_exc:
                    logger.warning(
                        "mcp.server_unavailable",
                        extra={
                            "event": "mcp.server_unavailable",
                            "url": getattr(server, "url", None),
                            "error_type": type(mcp_exc).__name__,
                            "error_message": str(mcp_exc),
                        },
                    )
                    failed_servers.append(server)

            saved_toolsets = None
            if failed_servers and hasattr(agent, "_user_toolsets"):
                failed_ids = {id(s) for s in failed_servers}
                saved_toolsets = list(agent._user_toolsets)
                agent._user_toolsets = [
                    t for t in saved_toolsets if id(t) not in failed_ids
                ]
            try:
                async with agent.run_stream(user_prompt, **run_kwargs) as stream:
                    async for chunk in stream.stream_text(delta=True):
                        accumulated += chunk
                        now = time.monotonic()
                        char_delta = len(accumulated) - last_update_len
                        time_delta = now - last_update_time

                        if time_delta >= _STREAM_UPDATE_INTERVAL and char_delta >= _STREAM_MIN_CHARS:
                            try:
                                await client.chat_update(
                                    channel=channel,
                                    ts=msg_ts,
                                    text=markdown_to_mrkdwn(accumulated) + " ▎",
                                )
                                last_update_time = now
                                last_update_len = len(accumulated)
                            except Exception:
                                pass  # Non-fatal — final update will catch up

                    # Final update with complete text (no cursor) — inside async with
                    final_text = accumulated.strip()
                    if not final_text:
                        # Fallback: stream produced no text chunks (tool-only response)
                        result = stream.get_output()
                        final_text = str(result)
                    final_mrkdwn = markdown_to_mrkdwn(final_text)
                    final_kwargs = _final_update_kwargs(final_mrkdwn, deps)
                    await client.chat_update(
                        channel=channel,
                        ts=msg_ts,
                        **final_kwargs,
                    )
            finally:
                if saved_toolsets is not None:
                    agent._user_toolsets = saved_toolsets
    except Exception:
        # If streaming fails, fall back to the accumulated text or error
        if accumulated.strip():
            fallback_mrkdwn = markdown_to_mrkdwn(accumulated.strip())
            fallback_kwargs = _final_update_kwargs(fallback_mrkdwn, deps)
            await client.chat_update(
                channel=channel,
                ts=msg_ts,
                **fallback_kwargs,
            )
        else:
            raise  # Re-raise so the caller's error handling kicks in


def _final_update_kwargs(reply_mrkdwn: str, deps: object) -> dict:
    """Assemble the kwargs for the final chat_update posting the agent reply.

    Returns ``{"text": ..., "blocks": ...}`` when ``deps.citations`` is
    non-empty, or ``{"text": ...}`` otherwise. ``text=`` is always
    populated so Slack notifications and clients that don't render
    blocks still show the reply content.

    Isolated into a helper so the success path and the streaming-failure
    fallback path apply citation blocks the same way.
    """
    from app.services.slack_blocks import build_reply_blocks

    citations = getattr(deps, "citations", None) or []
    blocks = build_reply_blocks(reply_mrkdwn, citations)
    if blocks is None:
        return {"text": reply_mrkdwn}
    return {"text": reply_mrkdwn, "blocks": blocks}


# ---------------------------------------------------------------------------
# Public top-level dispatcher
# ---------------------------------------------------------------------------


async def handle_slack_event(payload: dict) -> None:
    """Top-level dispatcher — routes to _handle_app_mention or _handle_dm.

    Called by the Slack events endpoint (via asyncio.create_task) after
    signature verification. Extracts the inner ``event`` dict from the
    event_callback envelope and dispatches based on ``event.type``.

    Emits ``event.received`` lifecycle log at entry so that every inbound
    Slack event is traceable in the structured log stream (STORY-016-01 R7).

    Args:
        payload: The full Slack event_callback JSON payload (already parsed).

    Returns:
        None. All errors are caught internally and posted back to Slack.
    """
    import time as _time

    event: dict = payload.get("event", {})
    event_type: str = event.get("type", "")
    channel_type: str = event.get("channel_type", "")
    channel: str = event.get("channel", "")
    team: str = event.get("team", "") or payload.get("team_id", "")

    # R7: lifecycle event — log every received Slack event for observability
    logger.info(
        "event.received",
        extra={
            "event": "event.received",
            "event_type": event_type,
            "channel": channel,
            "team": team,
        },
    )

    _dispatch_start = _time.monotonic()

    if event_type == "app_mention":
        await _handle_app_mention(event, _dispatch_start=_dispatch_start)
    elif event_type == "message" and channel_type == "im":
        await _handle_dm(event, _dispatch_start=_dispatch_start)
    else:
        logger.debug(
            "slack_dispatch: unhandled event type=%r channel_type=%r — ignoring",
            event_type,
            channel_type,
        )


# ---------------------------------------------------------------------------
# app_mention handler
# ---------------------------------------------------------------------------


async def _handle_app_mention(event: dict, *, _dispatch_start: float | None = None) -> None:
    """Handle an @mention of the bot in a Slack channel.

    Resolution steps:
      1. Look up channel binding in teemo_workspace_channels.
      2. If no binding → post a setup nudge and return.
      3. Get workspace_id from binding.
      4. Look up the Slack team row in teemo_slack_teams to get the bot token.
      5. Decrypt the bot token.
      6. Strip the ``<@UBOT>`` mention prefix from the message text.
      7. Fetch the thread reply history (for multi-turn context).
      8. Build the pydantic-ai agent for the workspace.
      9. Run the agent with the stripped user prompt.
      10. Post the agent's reply to the thread via chat.postMessage.
      Errors from ValueError("no_key_configured") are posted as user-facing
      error messages rather than propagated.

    Emits ``agent.built``, ``tool.called`` (delegated to agent), and
    ``response.sent`` lifecycle logs for STORY-016-01 R7 observability.

    Args:
        event: The inner Slack event dict from the event_callback envelope.
        _dispatch_start: Optional monotonic start time from handle_slack_event
            used to compute total_duration_ms in the ``response.sent`` event.
    """
    import time as _time
    channel: str = event.get("channel", "")
    team: str = event.get("team", "")
    text: str = event.get("text", "")
    # R7: prefer thread_ts (in-thread reply) over ts (new thread) so @mentions inside
    # an existing thread reply into that thread rather than starting a new one.
    thread_ts: str = event.get("thread_ts") or event.get("ts", "")

    supabase = _db_module.get_supabase()

    # 1. Look up channel binding
    binding_result = (
        supabase.table("teemo_workspace_channels")
        .select("*")
        .eq("slack_channel_id", channel)
        .limit(1)
        .execute()
    )
    binding_data: list[dict] = binding_result.data or []

    if not binding_data:
        # 2. No binding → look up team row to get bot token for the nudge
        team_result = (
            supabase.table("teemo_slack_teams")
            .select("*")
            .eq("slack_team_id", team)
            .limit(1)
            .execute()
        )
        team_rows: list[dict] = team_result.data or []
        if team_rows:
            bot_token = _enc_module.decrypt(team_rows[0]["encrypted_slack_bot_token"])
            client = AsyncWebClient(token=bot_token)
        else:
            # No team found — cannot post at all; log and bail
            logger.warning("slack_dispatch: no team row for team_id=%r, cannot post nudge", team)
            return

        await client.chat_postMessage(
            channel=channel,
            text=(
                "This channel hasn't been linked to a Tee-Mo workspace yet. "
                "Visit the Tee-Mo dashboard to bind a workspace to this channel."
            ),
            thread_ts=thread_ts,
        )
        return

    # 3. Get workspace_id from binding
    workspace_id: str = binding_data[0]["workspace_id"]

    # 4. Look up team row
    team_result = (
        supabase.table("teemo_slack_teams")
        .select("*")
        .eq("slack_team_id", team)
        .limit(1)
        .execute()
    )
    team_rows = team_result.data or []
    if not team_rows:
        logger.warning("slack_dispatch: no team row for team_id=%r", team)
        return

    team_row = team_rows[0]
    bot_user_id: str = team_row.get("slack_bot_user_id", "")
    owner_user_id: str = team_row.get("owner_user_id", "")

    # 5. Decrypt bot token
    bot_token = _enc_module.decrypt(team_row["encrypted_slack_bot_token"])

    # Create Slack client
    client = AsyncWebClient(token=bot_token)

    # 6. Kick off conversations.info for the source channel in parallel with
    #    the rest of dispatch setup. Slack message events only carry the
    #    channel ID, not the name — the agent needs the name to resolve "this
    #    channel" / "here" references and to honour the user's mental model
    #    where they refer to channels by name. The lookup runs concurrently
    #    with users_info + DB work below; it's awaited just before build_agent.
    _channel_info_task = asyncio.create_task(_resolve_channel_name(client, channel))

    # 6. Strip mention prefix: "<@UBOT123> some question" → "some question"
    stripped_text = re.sub(r"<@[A-Z0-9]+>\s*", "", text).strip()

    # 6b. Resolve sender display name so the agent knows who is speaking.
    #     Never pass a raw Slack user ID (U...) to the agent — always resolve
    #     to a human-readable name. Fallback to "there" for greeting safety.
    sender_user_id: str = event.get("user", "")
    sender_name = "there"  # fallback — never expose raw user IDs
    sender_tz = "UTC"  # R1/R7 (STORY-018-08): profile tz, default UTC on failure
    if sender_user_id:
        try:
            user_info = await client.users_info(user=sender_user_id)
            user_data = user_info.get("user", {})
            profile = user_data.get("profile", {})
            dn = (profile.get("display_name") or "").strip()
            rn = (user_data.get("real_name") or "").strip()
            sender_name = dn or rn or "there"
            # R1: extract IANA tz from Slack profile. Strip whitespace; fallback to "UTC".
            sender_tz = (user_data.get("tz") or "").strip() or "UTC"
        except Exception as e:
            logger.warning("Failed to resolve display name for %s: %s", sender_user_id, e)
            # R7: users_info failure → sender_tz stays "UTC"; softer prompt variant renders.

    # Await the channel-name lookup. It's been running in parallel with the
    # users_info/sender_tz work above, so this almost always resolves
    # immediately without adding wall-clock latency.
    try:
        current_channel_name = await _channel_info_task
    except Exception:
        current_channel_name = None

    # Inline channel context in the user prompt itself. Models follow
    # user-message context far more reliably than ``## Section`` headers
    # in the system prompt — this puts the literal channel id (and name
    # when available) right next to the user's question so the LLM
    # cannot fabricate a different ID when echoing it back.
    user_prompt = _format_user_prompt(
        sender_name=sender_name,
        text=stripped_text,
        channel_id=channel,
        channel_name=current_channel_name,
    )

    try:
        # 7. Build agent first — raises ValueError("no_key_configured") if no BYOK key
        #    We build before fetching thread history so we short-circuit cheaply on missing keys.
        _agent_build_start = _time.monotonic()
        agent, deps = await _agent_module.build_agent(
            workspace_id=workspace_id,
            user_id=owner_user_id,
            supabase=supabase,
            sender_tz=sender_tz,
            current_channel_id=channel,
            current_channel_name=current_channel_name,
        )
        _agent_build_ms = round((_time.monotonic() - _agent_build_start) * 1000)

        # R7: lifecycle — agent.built
        logger.info(
            "agent.built",
            extra={
                "event": "agent.built",
                "workspace_id": workspace_id,
                "duration_ms": _agent_build_ms,
            },
        )

        # 8. Fetch thread history for multi-turn context (only if agent was built successfully)
        history = await _thread_module.fetch_thread_history(
            bot_token=bot_token,
            channel=channel,
            thread_ts=thread_ts,
            bot_user_id=bot_user_id,
        )

        # 9. Run agent with streaming → progressive Slack message updates
        await _stream_agent_to_slack(
            agent,
            user_prompt,
            client,
            channel,
            thread_ts,
            deps=deps,
            message_history=history,
        )

        # R7: lifecycle — response.sent
        _total_ms = (
            round((_time.monotonic() - _dispatch_start) * 1000)
            if _dispatch_start is not None
            else None
        )
        logger.info(
            "response.sent",
            extra={
                "event": "response.sent",
                "channel": channel,
                "thread_ts": thread_ts,
                "total_duration_ms": _total_ms,
            },
        )

    except ValueError as exc:
        # R6 error categories 1 & 2: known ValueError sentinels from build_agent.
        msg = str(exc)
        if "no_key_configured" in msg:
            logger.warning(
                "slack_dispatch: no API key configured for workspace_id=%r", workspace_id
            )
            try:
                await client.chat_postMessage(
                    channel=channel,
                    text=(
                        "No API key is configured for this workspace. "
                        "Please add your BYOK API key in the Tee-Mo dashboard to enable AI responses."
                    ),
                    thread_ts=thread_ts,
                )
            except Exception:
                logger.error("slack_dispatch: failed to post no_key_configured error to %s", channel)
        elif "no_workspace" in msg:
            logger.warning(
                "slack_dispatch: workspace not found for workspace_id=%r", workspace_id
            )
            try:
                await client.chat_postMessage(
                    channel=channel,
                    text=(
                        "Workspace not found. "
                        "Please check your Tee-Mo dashboard configuration."
                    ),
                    thread_ts=thread_ts,
                )
            except Exception:
                logger.error("slack_dispatch: failed to post no_workspace error to %s", channel)
        else:
            logger.error("slack_dispatch: Unexpected ValueError in _handle_app_mention: %s", msg)
            try:
                await client.chat_postMessage(
                    channel=channel,
                    text="Something went wrong. Please try again.",
                    thread_ts=thread_ts,
                )
            except Exception:
                logger.error("slack_dispatch: failed to post unexpected ValueError error to %s", channel)
    except Exception as exc:
        # R6 error categories 3, 4, 5: provider errors, rate-limit, and any other exception.
        # R7: lifecycle — event.error (structured)
        logger.error(
            "event.error",
            extra={
                "event": "event.error",
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "channel": channel,
            },
            exc_info=True,
        )
        try:
            await client.chat_postMessage(
                channel=channel,
                text="Something went wrong. Please try again.",
                thread_ts=thread_ts,
            )
        except Exception:
            logger.error("slack_dispatch: failed to post error message to %s", channel)


# ---------------------------------------------------------------------------
# DM (message.im) handler
# ---------------------------------------------------------------------------


async def _handle_dm(event: dict, *, _dispatch_start: float | None = None) -> None:
    """Handle a direct message to the bot.

    Self-message filter: DMs sent by the bot itself (identified by either a
    ``bot_id`` field OR ``user == bot_user_id`` from the team row) are
    silently discarded to prevent reply loops.

    Resolution steps:
      1. Look up the Slack team row (needed for bot_user_id and bot token).
      2. Self-message filter: discard if event.bot_id is set OR event.user == bot_user_id.
      3. Look up the default workspace for the team.
      4. If no default workspace → post a setup nudge and return.
      5. Same agent flow as _handle_app_mention (steps 5-10, without thread history).

    Emits ``agent.built``, ``response.sent``, and ``event.error`` lifecycle logs
    for STORY-016-01 R7 observability.

    Args:
        event: The inner Slack event dict from the event_callback envelope.
        _dispatch_start: Optional monotonic start time from handle_slack_event
            used to compute total_duration_ms in the ``response.sent`` event.
    """
    import time as _time
    channel: str = event.get("channel", "")
    team: str = event.get("team", "")
    text: str = event.get("text", "")
    # R7: prefer thread_ts (in-thread reply) over ts so replies in existing DM threads
    # stay in that thread rather than branching into a new one.
    thread_ts: str = event.get("thread_ts") or event.get("ts", "")

    supabase = _db_module.get_supabase()

    # 1. Look up team row first (needed for bot_user_id to do self-message filter)
    team_result = (
        supabase.table("teemo_slack_teams")
        .select("*")
        .eq("slack_team_id", team)
        .limit(1)
        .execute()
    )
    team_rows: list[dict] = team_result.data or []
    if not team_rows:
        logger.warning("slack_dispatch: no team row for DM team_id=%r", team)
        return

    team_row = team_rows[0]
    bot_user_id: str = team_row.get("slack_bot_user_id", "")
    owner_user_id: str = team_row.get("owner_user_id", "")

    # 2. Self-message filter — discard bot's own messages
    if event.get("bot_id") or event.get("user") == bot_user_id:
        logger.debug("slack_dispatch: ignoring self-message in DM channel=%r", channel)
        return

    # Decrypt bot token (needed for posting)
    bot_token = _enc_module.decrypt(team_row["encrypted_slack_bot_token"])
    client = AsyncWebClient(token=bot_token)

    # Kick off conversations.info concurrently with the rest of dispatch setup.
    # See _handle_app_mention for rationale; same pattern.
    _channel_info_task = asyncio.create_task(_resolve_channel_name(client, channel))

    # 3. Look up default workspace for this team
    workspace_result = (
        supabase.table("teemo_workspaces")
        .select("*")
        .eq("slack_team_id", team)
        .eq("is_default_for_team", True)
        .maybe_single()
        .execute()
    )
    workspace_row = workspace_result.data

    if workspace_row is None:
        # 4. No default workspace → nudge
        await client.chat_postMessage(
            channel=channel,
            text=(
                "No default workspace is configured for your team. "
                "Visit the Tee-Mo dashboard to create and set a default workspace."
            ),
            thread_ts=thread_ts,
        )
        return

    workspace_id: str = workspace_row["id"]

    # Resolve sender display name — never expose raw user IDs.
    sender_user_id: str = event.get("user", "")
    sender_name = "there"
    sender_tz = "UTC"  # R1/R7 (STORY-018-08): profile tz, default UTC on failure
    if sender_user_id:
        try:
            user_info = await client.users_info(user=sender_user_id)
            user_data = user_info.get("user", {})
            profile = user_data.get("profile", {})
            dn = (profile.get("display_name") or "").strip()
            rn = (user_data.get("real_name") or "").strip()
            sender_name = dn or rn or "there"
            # R1: extract IANA tz from Slack profile. Strip whitespace; fallback to "UTC".
            sender_tz = (user_data.get("tz") or "").strip() or "UTC"
        except Exception:
            pass  # R7: users_info failure → sender_tz stays "UTC"

    try:
        current_channel_name = await _channel_info_task
    except Exception:
        current_channel_name = None

    # Same inline-context wrapper as _handle_app_mention — keeps the channel
    # id literal next to the user's question so Gemini-class models don't
    # confabulate a different ID when echoing it back.
    user_prompt = _format_user_prompt(
        sender_name=sender_name,
        text=text,
        channel_id=channel,
        channel_name=current_channel_name,
    )

    try:
        # 5. Build agent first — raises ValueError("no_key_configured") if no BYOK key
        _agent_build_start = _time.monotonic()
        agent, deps = await _agent_module.build_agent(
            workspace_id=workspace_id,
            user_id=owner_user_id,
            supabase=supabase,
            sender_tz=sender_tz,
            current_channel_id=channel,
            current_channel_name=current_channel_name,
        )
        _agent_build_ms = round((_time.monotonic() - _agent_build_start) * 1000)

        # R7: lifecycle — agent.built
        logger.info(
            "agent.built",
            extra={
                "event": "agent.built",
                "workspace_id": workspace_id,
                "duration_ms": _agent_build_ms,
            },
        )

        # 6. Run agent with streaming — DMs don't use threaded history
        await _stream_agent_to_slack(
            agent,
            user_prompt,
            client,
            channel,
            thread_ts,
            deps=deps,
        )

        # R7: lifecycle — response.sent
        _total_ms = (
            round((_time.monotonic() - _dispatch_start) * 1000)
            if _dispatch_start is not None
            else None
        )
        logger.info(
            "response.sent",
            extra={
                "event": "response.sent",
                "channel": channel,
                "thread_ts": thread_ts,
                "total_duration_ms": _total_ms,
            },
        )

    except ValueError as exc:
        # R6 error categories 1 & 2: known ValueError sentinels from build_agent.
        msg = str(exc)
        if "no_key_configured" in msg:
            logger.warning(
                "slack_dispatch: no API key configured for workspace_id=%r", workspace_id
            )
            try:
                await client.chat_postMessage(
                    channel=channel,
                    text=(
                        "No API key is configured for this workspace. "
                        "Please add your BYOK API key in the Tee-Mo dashboard to enable AI responses."
                    ),
                    thread_ts=thread_ts,
                )
            except Exception:
                logger.error("slack_dispatch: failed to post no_key_configured error to %s", channel)
        elif "no_workspace" in msg:
            logger.warning(
                "slack_dispatch: workspace not found for workspace_id=%r", workspace_id
            )
            try:
                await client.chat_postMessage(
                    channel=channel,
                    text=(
                        "Workspace not found. "
                        "Please check your Tee-Mo dashboard configuration."
                    ),
                    thread_ts=thread_ts,
                )
            except Exception:
                logger.error("slack_dispatch: failed to post no_workspace error to %s", channel)
        else:
            logger.error("slack_dispatch: Unexpected ValueError in _handle_dm: %s", msg)
            try:
                await client.chat_postMessage(
                    channel=channel,
                    text="Something went wrong. Please try again.",
                    thread_ts=thread_ts,
                )
            except Exception:
                logger.error("slack_dispatch: failed to post unexpected ValueError error to %s", channel)
    except Exception as exc:
        # R6 error categories 3, 4, 5: provider errors, rate-limit, and any other exception.
        # R7: lifecycle — event.error (structured)
        logger.error(
            "event.error",
            extra={
                "event": "event.error",
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "channel": channel,
            },
            exc_info=True,
        )
        try:
            await client.chat_postMessage(
                channel=channel,
                text="Something went wrong. Please try again.",
                thread_ts=thread_ts,
            )
        except Exception:
            logger.error("slack_dispatch: failed to post error message to %s", channel)
