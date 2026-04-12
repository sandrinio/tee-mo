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

import asyncio  # noqa: F401 — imported for re-export / test compatibility
import logging
import re

from slack_sdk.web.async_client import AsyncWebClient

import app.agents.agent as _agent_module
import app.core.db as _db_module
import app.core.encryption as _enc_module
import app.services.slack_thread as _thread_module

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


# ---------------------------------------------------------------------------
# Public top-level dispatcher
# ---------------------------------------------------------------------------


async def handle_slack_event(payload: dict) -> None:
    """Top-level dispatcher — routes to _handle_app_mention or _handle_dm.

    Called by the Slack events endpoint (via asyncio.create_task) after
    signature verification. Extracts the inner ``event`` dict from the
    event_callback envelope and dispatches based on ``event.type``.

    Args:
        payload: The full Slack event_callback JSON payload (already parsed).

    Returns:
        None. All errors are caught internally and posted back to Slack.
    """
    event: dict = payload.get("event", {})
    event_type: str = event.get("type", "")
    channel_type: str = event.get("channel_type", "")

    if event_type == "app_mention":
        await _handle_app_mention(event)
    elif event_type == "message" and channel_type == "im":
        await _handle_dm(event)
    else:
        logger.debug(
            "slack_dispatch: unhandled event type=%r channel_type=%r — ignoring",
            event_type,
            channel_type,
        )


# ---------------------------------------------------------------------------
# app_mention handler
# ---------------------------------------------------------------------------


async def _handle_app_mention(event: dict) -> None:
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

    Args:
        event: The inner Slack event dict from the event_callback envelope.
    """
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

    # 6. Strip mention prefix: "<@UBOT123> some question" → "some question"
    stripped_text = re.sub(r"<@[A-Z0-9]+>\s*", "", text).strip()

    # 6b. Resolve sender display name so the agent knows who is speaking
    sender_user_id: str = event.get("user", "")
    sender_name = sender_user_id  # fallback
    if sender_user_id:
        try:
            user_info = await client.users_info(user=sender_user_id)
            user_data = user_info.get("user", {})
            profile = user_data.get("profile", {})
            dn = (profile.get("display_name") or "").strip()
            rn = (user_data.get("real_name") or "").strip()
            sender_name = dn or rn or sender_user_id
        except Exception as e:
            logger.warning("Failed to resolve display name for %s: %s", sender_user_id, e)
            sender_name = sender_user_id

    user_prompt = f"{sender_name}: {stripped_text}"

    try:
        # 7. Build agent first — raises ValueError("no_key_configured") if no BYOK key
        #    We build before fetching thread history so we short-circuit cheaply on missing keys.
        agent, deps = await _agent_module.build_agent(
            workspace_id=workspace_id,
            user_id=owner_user_id,
            supabase=supabase,
        )

        # 8. Fetch thread history for multi-turn context (only if agent was built successfully)
        history = await _thread_module.fetch_thread_history(
            bot_token=bot_token,
            channel=channel,
            thread_ts=thread_ts,
            bot_user_id=bot_user_id,
        )

        # 9. Run agent
        result = await agent.run(user_prompt, message_history=history, deps=deps)

        # 10. Post reply
        await client.chat_postMessage(
            channel=channel,
            text=str(result.output),
            thread_ts=thread_ts,
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
        logger.error(
            "slack_dispatch: agent error in _handle_app_mention channel=%s: %s",
            channel,
            type(exc).__name__,
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


async def _handle_dm(event: dict) -> None:
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

    Args:
        event: The inner Slack event dict from the event_callback envelope.
    """
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

    # Resolve sender display name
    sender_user_id: str = event.get("user", "")
    sender_name = sender_user_id
    if sender_user_id:
        try:
            user_info = await client.users_info(user=sender_user_id)
            user_data = user_info.get("user", {})
            profile = user_data.get("profile", {})
            dn = (profile.get("display_name") or "").strip()
            rn = (user_data.get("real_name") or "").strip()
            sender_name = dn or rn or sender_user_id
        except Exception:
            sender_name = sender_user_id

    user_prompt = f"{sender_name}: {text}"

    try:
        # 5. Build agent first — raises ValueError("no_key_configured") if no BYOK key
        agent, deps = await _agent_module.build_agent(
            workspace_id=workspace_id,
            user_id=owner_user_id,
            supabase=supabase,
        )

        # 6. Run agent — DMs don't use threaded history (no parent thread context)
        result = await agent.run(user_prompt, deps=deps)

        # 7. Post reply to DM channel
        await client.chat_postMessage(
            channel=channel,
            text=str(result.output),
            thread_ts=thread_ts,
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
        logger.error(
            "slack_dispatch: agent error in _handle_dm channel=%s: %s",
            channel,
            type(exc).__name__,
        )
        try:
            await client.chat_postMessage(
                channel=channel,
                text="Something went wrong. Please try again.",
                thread_ts=thread_ts,
            )
        except Exception:
            logger.error("slack_dispatch: failed to post error message to %s", channel)
