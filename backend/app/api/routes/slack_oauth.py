"""Slack OAuth install flow routes.

STORY-005A-03 adds ``GET /api/slack/install`` — builds the Slack authorize URL
and issues a 307 redirect so the browser initiates the OAuth consent flow.

STORY-005A-04 will add ``GET /api/slack/oauth/callback`` here.
STORY-005A-05 will add ``GET /api/slack/teams`` here.

Scopes are defined by ADR-021 + ADR-025. The exact 7-scope set is encoded
as a comma-separated string in the ``scope`` query parameter.
"""

from urllib.parse import urlencode

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse

from app.api.deps import get_current_user_id
from app.core.config import get_settings
from app.core.security import create_slack_state_token

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
