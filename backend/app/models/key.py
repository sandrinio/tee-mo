"""Pydantic models for BYOK (Bring Your Own Key) key management.

STORY-004-01: Backend Key Routes + Models + Validator

These models define the request/response shapes for the workspace-scoped
key CRUD endpoints. Critically, the plaintext key is accepted in ``KeyCreate``
for write operations but NEVER appears in any response model — responses
always use ``KeyResponse`` which only surfaces the masked key.

ADR-002: Plaintext API keys must never appear in responses, logs, or DB.
``KeyCreate.key`` accepts plaintext for a single request lifetime; the route
handler immediately encrypts it via ``encrypt()`` before any DB write.
``__repr__`` is overridden to prevent the key from leaking into debug logs
or exception tracebacks.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, field_validator

# Canonical set of supported LLM providers.
# New providers require a Charter change (§3.4) before adding to this Literal.
ProviderLiteral = Literal["google", "openai", "anthropic"]


class KeyCreate(BaseModel):
    """Request body for ``POST /api/workspaces/{workspace_id}/keys``.

    Accepts a plaintext API key from the client. The plaintext is validated
    to be non-empty (after stripping whitespace) and is immediately encrypted
    inside the route handler — it is NEVER stored or returned in plaintext.

    Attributes:
        provider: The LLM provider the key belongs to.
        key: The plaintext API key. Stripped of leading/trailing whitespace.
            Must not be blank after stripping.
        ai_model: Optional model override. If omitted, the route handler
            applies the provider default (see §3.3 of the story spec).
    """

    provider: ProviderLiteral
    key: str
    ai_model: str | None = None

    @field_validator("key", mode="before")
    @classmethod
    def strip_and_require_nonempty(cls, v: str) -> str:
        """Strip whitespace and reject blank keys."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("key must not be blank")
        return stripped

    def __repr__(self) -> str:
        """Redact the key field in repr to prevent accidental log leakage."""
        return f"KeyCreate(provider={self.provider!r}, key='***', ai_model={self.ai_model!r})"


class KeyResponse(BaseModel):
    """Response shape for key CRUD read operations.

    The plaintext API key is NEVER included. Instead, the caller receives:
    - ``key_mask``: a short visual hint (first 4 + last 4 chars, separated by
      ``...``) so the user can confirm which key is stored without revealing it.
    - ``has_key``: a boolean indicating whether any key is currently stored.
    - ``provider``: the LLM provider associated with the stored key.
    - ``ai_model``: the model configured for this workspace, if any.

    All fields are optional/nullable to handle the "no key stored" state where
    ``has_key=False`` and everything else is ``None``.

    Attributes:
        provider: Provider name, or None if no key is stored.
        key_mask: Masked key hint (e.g. ``"sk-ab...xyz9"``), or None.
        has_key: True when an encrypted key is present on the workspace row.
        ai_model: Model identifier, or None if not set.
    """

    provider: str | None = None
    key_mask: str | None = None
    has_key: bool
    ai_model: str | None = None


class KeyValidateRequest(BaseModel):
    """Request body for ``POST /api/keys/validate`` (stateless probe).

    The key is sent in plaintext for a single request — it is probed against
    the provider's API and immediately discarded. It is never written to DB.

    Attributes:
        provider: The LLM provider to probe.
        key: The plaintext API key to validate.
    """

    provider: ProviderLiteral
    key: str

    def __repr__(self) -> str:
        """Redact the key field in repr to prevent accidental log leakage."""
        return f"KeyValidateRequest(provider={self.provider!r}, key='***')"


class KeyValidateResponse(BaseModel):
    """Response for ``POST /api/keys/validate``.

    Attributes:
        valid: True if the provider accepted the key; False otherwise.
        message: Human-readable result — ``"Valid"`` on success, or an error
            description (e.g. ``"Invalid API key"`` or
            ``"Rate limited — try again shortly"``).
    """

    valid: bool
    message: str
