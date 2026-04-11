"""Pydantic models for Slack OAuth install flow.

STORY-005A-03 adds ``SlackInstallState`` (state JWT payload).
STORY-005A-04 will add ``TeamResponse`` and related callback models here.
"""

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
