"""Drive OAuth models (STORY-006-02).

Provides dataclasses used by the Drive OAuth state token helpers in
``app.core.security`` and the Drive OAuth route handlers in
``app.api.routes.drive_oauth``.
"""

from dataclasses import dataclass


@dataclass
class DriveConnectState:
    """Decoded Drive OAuth state JWT payload.

    Returned by ``verify_drive_state_token`` after a successful JWT decode.
    Embeds the user identity and target workspace so the callback handler can
    associate the Google authorization code with the right user and workspace
    without maintaining server-side session state.

    Fields:
        user_id:      The authenticated user's ID string (from the ``user_id`` JWT claim).
        workspace_id: The target workspace ID string (from the ``workspace_id`` JWT claim).
        exp:          Token expiry as a Unix timestamp int (from the ``exp`` JWT claim).

    Audience is ``"drive-connect"`` — enforced during decode by PyJWT.
    Expiry window is 5 minutes (300 seconds) from issue time.
    """

    user_id: str
    workspace_id: str
    exp: int
