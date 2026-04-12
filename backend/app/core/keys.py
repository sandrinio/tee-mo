"""
Centralized BYOK key resolution for Tee-Mo — non-inference call paths.

Provides get_workspace_key() as the single point for resolving the workspace's
API key for non-inference operations (file indexing, pre-flight checks).

For the inference call path (agent factory), use services/provider_resolver.py.

ADR compliance:
- ADR-002: decrypt() is only called inside this module — never outside.
- ADR-005: The resolver never pre-loads file content; it only provides the key.
"""
from __future__ import annotations

from app.core.encryption import decrypt


def get_workspace_key(supabase, workspace_id: str) -> str | None:
    """Resolve the BYOK API key for a workspace (non-inference path).

    Queries teemo_workspaces for the encrypted_api_key of the given workspace_id.
    If a non-null value is found, it is decrypted with AES-256-GCM and returned.
    Returns None if no key is configured.

    This is the single safe path through which encrypted_api_key is decrypted
    for non-inference use cases (file indexing, pre-flight key checks). No other
    code may call decrypt() directly on a workspace key — all callers must go
    through this function or resolve_provider_key() in services/provider_resolver.py.

    Args:
        supabase:     Authenticated Supabase client (service-role or user-scoped).
        workspace_id: UUID string of the workspace to resolve.

    Returns:
        Decrypted plaintext API key string, or None if no key is configured.
    """
    result = (
        supabase.table("teemo_workspaces")
        .select("encrypted_api_key")
        .eq("id", workspace_id)
        .maybe_single()
        .execute()
    )
    if not result or not result.data:
        return None
    encrypted = result.data.get("encrypted_api_key")
    if not encrypted:
        return None
    return decrypt(encrypted)
