import uuid
from datetime import datetime, timezone

from app.models.workspace import WorkspaceResponse


def test_workspace_response_omits_secrets():
    """Verify that the response model does not leak secret columns."""
    # Simulate a raw database dictionary that contains secrets
    raw_db_row = {
        "id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "name": "My Workspace",
        "slack_team_id": "T12345",
        "ai_provider": "anthropic",
        "ai_model": "claude-3-5-sonnet",
        "is_default_for_team": True,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        # Secrets that should NOT be serialized
        "encrypted_api_key": "some_secret_key_123",
        "encrypted_google_refresh_token": "some_refresh_token_456"
    }

    # Init Pydantic model (simulating SQLAlchemy/DB mapping logic or dict unpacking)
    model = WorkspaceResponse(**raw_db_row)

    # Dump to dict/JSON
    serialized = model.model_dump()

    # Check what got exposed
    assert "name" in serialized
    assert serialized["name"] == "My Workspace"
    assert "encrypted_api_key" not in serialized
    assert "encrypted_google_refresh_token" not in serialized

    # Explict property check
    assert not hasattr(model, "encrypted_api_key")
