"""Slack OAuth install flow routes.

STORY-005A-03 adds ``GET /api/slack/install`` — builds the Slack authorize URL
and issues a 307 redirect so the browser initiates the OAuth consent flow.

STORY-005A-04 adds ``GET /api/slack/oauth/callback`` — verifies state, exchanges
the auth code for a bot token via Slack's oauth.v2.access, encrypts the token,
and upserts the teemo_slack_teams row.

STORY-005A-05 will add ``GET /api/slack/teams`` here.

Scopes are defined by ADR-021 + ADR-025. The exact 7-scope set is encoded
as a comma-separated string in the ``scope`` query parameter.
"""

import logging
import httpx  # MUST be at module level so tests can monkeypatch httpx.AsyncClient
import jwt    # needed for jwt.ExpiredSignatureError, jwt.InvalidTokenError in callback
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.api.deps import get_current_user_id, get_current_user_id_optional
from app.core.config import get_settings
from app.core.db import get_supabase, execute_async
from app.core.encryption import encrypt
from app.core.security import create_slack_state_token, verify_slack_state_token
from app.models.slack import SlackTeamResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/slack", tags=["slack"])

# ADR-021 + ADR-025: exact 7-scope tuple required for Tee-Mo Slack app install.
# Do NOT add or remove scopes without an ADR amendment — the Slack app manifest
# must stay in sync with this list.
SLACK_SCOPES = (
    "app_mentions:read,channels:history,channels:read,"
    "chat:write,groups:history,groups:read,im:history"
)


@router.get("/install")
async def slack_install(
    user_id: str = Depends(get_current_user_id),
) -> RedirectResponse:
    """Redirect the authenticated user to Slack's OAuth consent screen.

    Builds the Slack ``/oauth/v2/authorize`` URL with the required query
    parameters and issues a 307 (Temporary Redirect) so the browser re-issues
    the GET to Slack. 307 preserves the request method — 302 would be
    semantically incorrect for a GET-initiated OAuth flow.

    The ``state`` parameter is a short-lived (5 min) JWT signed with
    ``supabase_jwt_secret`` and audience ``"slack-install"``. It embeds the
    ``user_id`` so the callback handler can associate the authorization code
    with the initiating user without storing server-side session state.

    The state token is NEVER logged — it contains a signed user identity.

    Args:
        user_id: Injected by ``get_current_user_id``; raises 401 if missing/invalid.

    Returns:
        307 RedirectResponse to ``https://slack.com/oauth/v2/authorize`` with
        ``client_id``, ``scope``, ``redirect_uri``, and ``state`` query params.
    """
    s = get_settings()
    state = create_slack_state_token(user_id)
    qs = urlencode(
        {
            "client_id": s.slack_client_id,
            "scope": SLACK_SCOPES,
            "redirect_uri": s.slack_redirect_url,
            "state": state,
        }
    )
    return RedirectResponse(
        url=f"https://slack.com/oauth/v2/authorize?{qs}",
        status_code=307,
    )


@router.get("/oauth/callback")
async def slack_oauth_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    user_id: str | None = Depends(get_current_user_id_optional),
) -> RedirectResponse:
    """Handle the Slack OAuth redirect after user consent.

    Verifies the signed state param, exchanges the auth code for a bot token
    via Slack's ``oauth.v2.access`` API, encrypts the token (ADR-002/010),
    upserts the ``teemo_slack_teams`` row (ADR-024), and redirects back to
    ``/app``.

    5 redirect branches:
      - ``/app?slack_install=cancelled`` — user clicked "Cancel" at Slack consent
      - ``/app?slack_install=expired``   — state JWT has expired (>5 min)
      - ``/login?next=/app&slack_install=session_lost`` — auth cookie missing/invalid
      - ``/app?slack_install=error``     — Slack API returned ok=false or missing fields
      - ``/app?slack_install=ok``        — success

    3 hard-fail branches (raise HTTPException, no redirect):
      - 400 — missing ``code`` or ``state``, or tampered state signature
      - 403 — state user_id != authenticated user_id (cross-user hijack attempt)
      - 409 — team already installed under a different account

    Security constraints (spec Req 11, ADR-002/010):
      - Bot token is NEVER logged in plaintext or ciphertext form.
      - The different-owner check (409) runs BEFORE any upsert write.

    Args:
        request:  Incoming FastAPI request (injected automatically).
        code:     Slack OAuth authorization code (query param from Slack).
        state:    Signed JWT state param (query param from Slack).
        error:    Slack error string e.g. ``"access_denied"`` (query param).
        user_id:  Authenticated user ID from cookie, or None if no session.

    Returns:
        302 RedirectResponse to the appropriate URL.

    Raises:
        HTTPException(400): Missing params or tampered state.
        HTTPException(403): Cross-user state mismatch.
        HTTPException(409): Team already installed under a different account.
    """
    # --- 1. Cancellation branch — no API calls, no DB writes ---
    if error == "access_denied":
        return RedirectResponse("/app?slack_install=cancelled", status_code=302)

    # --- 2. Required params ---
    if not state or not code:
        raise HTTPException(status_code=400, detail="missing code or state")

    # --- 3. State verification: expired vs tampered are distinct branches ---
    try:
        state_payload = verify_slack_state_token(state)
    except jwt.ExpiredSignatureError:
        return RedirectResponse("/app?slack_install=expired", status_code=302)
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=400, detail="invalid state")

    # --- 4. Cross-user / session-lost checks ---
    if user_id is None:
        return RedirectResponse(
            "/login?next=/app&slack_install=session_lost", status_code=302
        )
    if user_id != state_payload.user_id:
        raise HTTPException(status_code=403, detail="state user mismatch")

    # --- 5. Exchange the auth code for a bot token ---
    s = get_settings()
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            "https://slack.com/api/oauth.v2.access",
            data={
                "code": code,
                "client_id": s.slack_client_id,
                "client_secret": s.slack_client_secret,
                "redirect_uri": s.slack_redirect_url,
            },
        )
    payload = resp.json()

    if not payload.get("ok"):
        logger.warning(
            "oauth.v2.access failed: error=%s", payload.get("error", "unknown")
        )
        return RedirectResponse("/app?slack_install=error", status_code=302)

    team_id = payload.get("team", {}).get("id")
    team_name = payload.get("team", {}).get("name", "")
    bot_user_id = payload.get("bot_user_id")
    bot_token = payload.get("access_token")
    if not team_id or not bot_user_id or not bot_token:
        logger.warning("oauth.v2.access missing bot_user_id or team or access_token")
        return RedirectResponse("/app?slack_install=error", status_code=302)

    # --- 6. Check if team already exists ---
    sb = get_supabase()
    existing = (
        await execute_async(sb.table("teemo_slack_teams")
        .select("owner_user_id")
        .eq("slack_team_id", team_id)
        .limit(1)
        )
    )
    is_new_team = not existing.data
    is_owner = is_new_team or existing.data[0]["owner_user_id"] == user_id

    # --- 7. Upsert team row (only if owner or new install) ---
    # NOTE: bot_token is NEVER passed to logger — ADR-002/010 security constraint.
    # installed_at is intentionally excluded from the upsert dict so the
    # DEFAULT NOW() value from the first insert is preserved on re-install.
    if is_owner:
        encrypted = encrypt(bot_token)
        upsert_data: dict = {
            "slack_team_id": team_id,
            "owner_user_id": user_id,
            "slack_bot_user_id": bot_user_id,
            "encrypted_slack_bot_token": encrypted,
        }
        if team_name:
            upsert_data["slack_team_name"] = team_name
        await execute_async(sb.table("teemo_slack_teams").upsert(upsert_data))

    # --- 8. Upsert membership row ---
    # Owner gets 'owner' role, other users get 'member'.
    # joined_at excluded so DEFAULT NOW() is preserved on re-install.
    await execute_async(sb.table("teemo_slack_team_members").upsert(
        {
            "slack_team_id": team_id,
            "user_id": user_id,
            "role": "owner" if is_owner else "member",
        }
    ))

    return RedirectResponse("/app?slack_install=ok", status_code=302)


@router.get("/teams")
async def list_slack_teams(user_id: str = Depends(get_current_user_id)) -> dict:
    """Return Slack teams the authenticated user is a member of.

    Joins ``teemo_slack_team_members`` with ``teemo_slack_teams`` to return
    teams where the user has any role (owner or member). Each response row
    includes the user's ``role`` so the frontend can show/hide admin controls.

    The ``encrypted_slack_bot_token`` column is never fetched — defense in
    depth per ADR-010.
    """
    sb = get_supabase()

    # Fetch memberships for this user
    memberships = (
        await execute_async(sb.table("teemo_slack_team_members")
        .select("slack_team_id, role")
        .eq("user_id", user_id)
        )
    )
    if not memberships.data:
        return {"teams": []}

    # Build a map of team_id → role
    role_map = {m["slack_team_id"]: m["role"] for m in memberships.data}
    team_ids = list(role_map.keys())

    # Fetch team details (safe columns only)
    teams = (
        await execute_async(sb.table("teemo_slack_teams")
        .select("slack_team_id, slack_team_name, slack_bot_user_id, installed_at")
        .in_("slack_team_id", team_ids)
        .order("installed_at", desc=True)
        )
    )

    return {
        "teams": [
            SlackTeamResponse(
                **row,
                role=role_map.get(row["slack_team_id"], "member"),
            ).model_dump(mode="json")
            for row in (teams.data or [])
        ]
    }


@router.delete("/teams/{team_id}")
async def delete_slack_team(
    team_id: str,
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """Delete a Slack team and ALL related data. Owner-only.

    Cascade deletes: workspaces, workspace_channels, knowledge_index,
    skills, and team_members are all removed by ON DELETE CASCADE.
    """
    sb = get_supabase()

    # Verify caller is the team owner
    membership = (
        await execute_async(sb.table("teemo_slack_team_members")
        .select("role")
        .eq("slack_team_id", team_id)
        .eq("user_id", user_id)
        .limit(1)
        )
    )
    if not membership.data or membership.data[0]["role"] != "owner":
        raise HTTPException(status_code=403, detail="Only the team owner can delete a team.")

    # Delete the team row — ON DELETE CASCADE handles everything else
    await execute_async(sb.table("teemo_slack_teams").delete().eq("slack_team_id", team_id))

    return {"message": f"Team {team_id} and all related data deleted."}
