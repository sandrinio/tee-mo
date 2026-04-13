"""Pydantic models for Slack OAuth install flow.

STORY-005A-03 adds ``SlackInstallState`` (state JWT payload).
STORY-005A-05 adds ``SlackTeamResponse`` (GET /api/slack/teams response shape).
"""

from datetime import datetime

from typing import Optional

from pydantic import BaseModel


class SlackInstallState(BaseModel):
    """State parameter payload decoded from the Slack OAuth authorize redirect JWT.

    The state query parameter in the Slack install URL is a signed JWT. After
    Slack redirects back to the callback URL, ``verify_slack_state_token``
    decodes the JWT and returns this model so the callback handler can
    associate the authorization code with the originating user.

    Fields:
        user_id: The authenticated user's ID string (from the ``user_id`` JWT claim).
        exp:     Token expiry as a Unix timestamp int (from the ``exp`` JWT claim).

    Audience is ``"slack-install"`` — enforced during decode by PyJWT.
    Expiry window is 5 minutes (300 seconds) from issue time.
    """

    user_id: str
    exp: int


class SlackTeamResponse(BaseModel):
    """API response shape for a single row in GET /api/slack/teams.

    NEVER include ``encrypted_slack_bot_token`` in this model. Adding it would
    cause FastAPI's JSON serialization to leak the encrypted bot token to API
    consumers. The token is encrypted at rest (ADR-002) AND must never appear
    in any API response (ADR-010). Defense in depth: the DB query also uses
    explicit-column ``.select(...)`` rather than ``*``, so the column is never
    fetched at all.
    """

    slack_team_id: str
    slack_team_name: Optional[str] = None
    slack_bot_user_id: str
    installed_at: datetime
    role: str = "owner"
