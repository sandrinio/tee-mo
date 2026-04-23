---
story_id: "STORY-004-02"
epic_id: "EPIC-004"
title: "Provider Key Resolvers (Non-Inference + Inference Path)"
status: "Draft"
v_bounce_state: "Ready to Bounce"
complexity_label: "L1"
ambiguity: "🟢 Low"
depends_on: ["STORY-004-01"]
unlocks: ["EPIC-007"]
estimated_effort: "~1h"
---

# STORY-004-02: Provider Key Resolvers (Non-Inference + Inference Path)

## 1. The Spec

### 1.1 Goal
Create two resolver functions that EPIC-007 (AI Agent) and EPIC-006 (Google Drive) will call to retrieve the workspace's decrypted BYOK key at runtime. These are the only safe path through which `encrypted_api_key` is ever decrypted — no other code is permitted to call `decrypt()` directly on a workspace key.

Two resolvers are needed (matching the new_app architecture split):

1. **`get_workspace_key(supabase, workspace_id)`** — for non-inference call paths (e.g., file indexing in EPIC-006, pre-flight checks). Returns `str | None`.
2. **`resolve_provider_key(workspace_id, supabase)`** — for the inference path (called by `build_agent()` in EPIC-007). Raises `ValueError` if no key is configured, so the agent factory gets a clean error.

### 1.2 What is COPY, what is NEW

| Item | Action | Source |
|------|--------|--------|
| `backend/app/core/keys.py` | **Copy + strip** | `new_app/backend/app/core/keys.py` → `get_workspace_key()`. **Strip**: instance-key fallback (no `chy_instance_provider_keys` in Tee-Mo), settings fallback path. **Change**: query `teemo_workspaces` by `workspace_id` (not `chy_provider_keys` by `user_id + provider`). |
| `backend/app/services/provider_resolver.py` | **Copy + strip** | `new_app/backend/app/services/provider_resolver.py` → `resolve_provider_key()`. **Strip**: `scope`, `key_id` metadata return (Tee-Mo doesn't log usage). **Simplify**: single return value (plaintext key string), raises ValueError on missing. |

---

## 2. The Truth (Acceptance Criteria)

```gherkin
Feature: Provider Key Resolvers

  Scenario: get_workspace_key — key exists
    Given teemo_workspaces has encrypted_api_key = AES("sk-real-key") for workspace W1
    When get_workspace_key(supabase, workspace_id="W1") is called
    Then it returns "sk-real-key" (decrypted plaintext)

  Scenario: get_workspace_key — no key configured
    Given teemo_workspaces has encrypted_api_key = NULL for workspace W2
    When get_workspace_key(supabase, workspace_id="W2") is called
    Then it returns None

  Scenario: resolve_provider_key — key exists
    Given workspace W1 has a valid encrypted_api_key
    When resolve_provider_key(workspace_id="W1", supabase=...) is called
    Then it returns the decrypted plaintext key string

  Scenario: resolve_provider_key — no key configured
    Given workspace W2 has encrypted_api_key = NULL
    When resolve_provider_key(workspace_id="W2", supabase=...) is called
    Then it raises ValueError("No API key configured for workspace W2. Add one in the dashboard.")
```

---

## 3. Implementation Guide

### 3.1 `backend/app/core/keys.py` — new file

```python
"""
Centralized BYOK key resolution for Tee-Mo — non-inference call paths.

Provides get_workspace_key() as the single point for resolving the workspace's
API key for non-inference operations (file indexing, pre-flight checks).

For the inference call path (agent factory), use services/provider_resolver.py.
"""
from __future__ import annotations
from app.core.encryption import decrypt


def get_workspace_key(supabase, workspace_id: str) -> str | None:
    """
    Resolve the BYOK API key for a workspace.

    Queries teemo_workspaces for the encrypted_api_key of the given workspace_id.
    If a non-null value is found, it is decrypted with AES-256-GCM and returned.
    Returns None if no key is configured.

    Args:
        supabase:      Authenticated Supabase client (service-role or user-scoped).
        workspace_id:  UUID string of the workspace to resolve.

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
```

### 3.2 `backend/app/services/provider_resolver.py` — new file

```python
"""
Inference-path key resolution for Tee-Mo.

resolve_provider_key() is the single entry point for the agent factory
(EPIC-007 build_agent) to obtain a workspace's decrypted BYOK key.
It raises ValueError (not None) so the agent factory gets a hard failure
with a user-friendly message rather than a silent None.
"""
from __future__ import annotations
from app.core.keys import get_workspace_key


def resolve_provider_key(workspace_id: str, supabase) -> str:
    """
    Resolve and return the BYOK API key for a workspace (inference path).

    Delegates to get_workspace_key() and raises ValueError if no key is
    configured — callers (agent factory) should catch this and return a
    user-facing error (e.g., post to Slack thread: "No API key configured").

    Args:
        workspace_id:  UUID string of the Tee-Mo workspace.
        supabase:      Authenticated Supabase client.

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
```

### 3.3 File placement
```
backend/app/core/keys.py              ← NEW
backend/app/services/__init__.py      ← NEW (empty — created in STORY-004-01)
backend/app/services/provider_resolver.py  ← NEW
```

### 3.4 ADR compliance
- ADR-002: `decrypt()` is only called inside `get_workspace_key` — never outside.
- ADR-005: The resolver never pre-loads file content; it only provides the key.
- `workspace_id` is passed in — the resolver does NOT accept a user-supplied plaintext key.

---

## 4. Test Requirements

Write tests in `backend/tests/test_key_resolvers.py`:

1. `test_get_workspace_key_returns_decrypted` — mock Supabase to return a row with `encrypted_api_key = encrypt("sk-test")`. Assert returns `"sk-test"`.
2. `test_get_workspace_key_returns_none_when_null` — mock returns row with `encrypted_api_key = None`. Assert returns `None`.
3. `test_get_workspace_key_returns_none_when_no_row` — mock returns empty data. Assert returns `None`.
4. `test_resolve_provider_key_success` — calls through to `get_workspace_key`, asserts returns plaintext.
5. `test_resolve_provider_key_raises_when_no_key` — mock `get_workspace_key` returns `None`, asserts `ValueError` is raised with a human-readable message.

Minimum: **5 unit tests** (pure Python, no live Supabase calls needed — mock the client).

---

## Change Log
| Date | Change | By |
|------|--------|-----|
| 2026-04-12 | Story created from EPIC-004 decomposition | Claude (doc-manager) |
