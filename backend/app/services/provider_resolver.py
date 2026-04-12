"""
Inference-path key resolution for Tee-Mo.

resolve_provider_key() is the single entry point for the agent factory
(EPIC-007 build_agent) to obtain a workspace's decrypted BYOK key.
It raises ValueError (not None) so the agent factory gets a hard failure
with a user-friendly message rather than a silent None.

This separation from app.core.keys follows the new_app architecture split:
- core/keys.py → non-inference paths (file indexing, pre-flight checks)
- services/provider_resolver.py → inference path (agent factory)
"""
from __future__ import annotations

from app.core.keys import get_workspace_key


def resolve_provider_key(workspace_id: str, supabase) -> str:
    """Resolve and return the BYOK API key for a workspace (inference path).

    Delegates to get_workspace_key() and raises ValueError if no key is
    configured — callers (agent factory) should catch this and return a
    user-facing error (e.g., post to Slack thread: "No API key configured").

    Args:
        workspace_id: UUID string of the Tee-Mo workspace.
        supabase:     Authenticated Supabase client.

    Returns:
        Decrypted plaintext API key string.

    Raises:
        ValueError: If no BYOK key is configured for this workspace.
    """
    key = get_workspace_key(supabase, workspace_id)
    if key is None:
        raise ValueError(
            f"No API key configured for workspace {workspace_id}. "
            "Add your provider key in the Tee-Mo dashboard."
        )
    return key
