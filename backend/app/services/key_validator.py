"""LLM provider API key validator.

STORY-004-01: Backend Key Routes + Models + Validator

Probes a provider's public API endpoint with the supplied key to determine
whether the key is valid. This is a lightweight, stateless check — no data
is written to the database.

FLASHCARDS.md rule (S-04): ``import httpx`` at MODULE LEVEL so that tests
can monkeypatch ``httpx.AsyncClient`` on this module's ``httpx`` reference:

    import app.services.key_validator as kv_module
    monkeypatch.setattr(kv_module.httpx, "AsyncClient", FakeAsyncClient)

If ``import httpx`` were inside the function body, the module would have no
``httpx`` attribute and monkeypatching would raise ``AttributeError``.
"""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

# Provider-specific probe configuration.
# Kept as module-level constants so they are easy to audit and test.
_OPENAI_MODELS_URL = "https://api.openai.com/v1/models"
_ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
_GOOGLE_MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models"

# Minimal Anthropic messages payload — chosen to be cheap on tokens while
# still triggering auth validation. We check only that the response is NOT
# a 401/403 (any real content or 400 means the key was accepted).
_ANTHROPIC_PROBE_PAYLOAD = {
    "model": "claude-haiku-20240307",
    "max_tokens": 1,
    "messages": [{"role": "user", "content": "hi"}],
}


async def validate_key(provider: str, key: str) -> tuple[bool, str]:
    """Probe the given provider API with ``key`` and return (valid, message).

    Each provider uses a different endpoint and auth scheme:
    - ``openai``:    GET /v1/models with ``Authorization: Bearer {key}``
    - ``anthropic``: POST /v1/messages minimal payload with ``x-api-key: {key}``
    - ``google``:    GET /v1beta/models?key={key} (key in query string)

    HTTP 429 from any provider is treated as a rate-limit, NOT as key
    invalidation — the caller should surface this distinctly to the user.

    Auth errors (401, 403) are treated as an invalid key.
    Any 2xx response (or 400 on Anthropic, which means the key was accepted
    but the minimal payload failed Anthropic's schema check) is treated as
    a valid key.

    Parameters
    ----------
    provider : str
        One of ``"openai"``, ``"anthropic"``, ``"google"``.
    key : str
        The plaintext API key to probe.

    Returns
    -------
    tuple[bool, str]
        ``(True, "Valid")`` if the key appears valid.
        ``(False, "Rate limited — try again shortly")`` on HTTP 429.
        ``(False, "<error description>")`` on auth failure or unknown provider.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            if provider == "openai":
                return await _validate_openai(client, key)
            elif provider == "anthropic":
                return await _validate_anthropic(client, key)
            elif provider == "google":
                return await _validate_google(client, key)
            else:
                logger.warning("validate_key: unknown provider %r", provider)
                return (False, f"Unknown provider: {provider}")
    except httpx.TimeoutException:
        logger.warning("validate_key: timeout probing provider %r", provider)
        return (False, "Request timed out — provider may be unreachable")
    except httpx.RequestError as exc:
        logger.warning("validate_key: network error probing %r: %s", provider, exc)
        return (False, "Network error — could not reach provider API")


async def _validate_openai(client: httpx.AsyncClient, key: str) -> tuple[bool, str]:
    """Probe the OpenAI /v1/models endpoint.

    A 200 response means the key is valid. 401 means invalid.
    429 is a rate limit. Any other non-200 status is surfaced as-is.

    Parameters
    ----------
    client : httpx.AsyncClient
        An open httpx async client.
    key : str
        The plaintext OpenAI API key.

    Returns
    -------
    tuple[bool, str]
        ``(True, "Valid")`` or ``(False, message)``.
    """
    resp = await client.get(
        _OPENAI_MODELS_URL,
        headers={"Authorization": f"Bearer {key}"},
    )
    if resp.status_code == 200:
        return (True, "Valid")
    if resp.status_code == 429:
        return (False, "Rate limited — try again shortly")
    # 401 or any other auth failure
    try:
        detail = resp.json().get("error", {}).get("message", resp.text)
    except Exception:
        detail = resp.text
    return (False, detail or f"HTTP {resp.status_code}")


async def _validate_anthropic(client: httpx.AsyncClient, key: str) -> tuple[bool, str]:
    """Probe the Anthropic /v1/messages endpoint with a minimal payload.

    Anthropic returns 401 for bad keys. A 400 (bad request, e.g. if the
    minimal model name is unknown to their current API) still means the key
    itself was accepted — we treat anything that is NOT 401/403/429 as valid.

    Parameters
    ----------
    client : httpx.AsyncClient
        An open httpx async client.
    key : str
        The plaintext Anthropic API key.

    Returns
    -------
    tuple[bool, str]
        ``(True, "Valid")`` or ``(False, message)``.
    """
    resp = await client.post(
        _ANTHROPIC_MESSAGES_URL,
        json=_ANTHROPIC_PROBE_PAYLOAD,
        headers={
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
    )
    if resp.status_code == 429:
        return (False, "Rate limited — try again shortly")
    if resp.status_code in (401, 403):
        try:
            detail = resp.json().get("error", {}).get("message", resp.text)
        except Exception:
            detail = resp.text
        return (False, detail or f"HTTP {resp.status_code}")
    # 200, 400, or any other status — key was accepted by auth layer
    return (True, "Valid")


async def _validate_google(client: httpx.AsyncClient, key: str) -> tuple[bool, str]:
    """Probe the Google Generative Language API /v1beta/models endpoint.

    The key is passed as a query parameter (Google's standard pattern for
    the REST API). A 200 response means the key is valid. 400/403 means
    invalid. 429 is a rate limit.

    Parameters
    ----------
    client : httpx.AsyncClient
        An open httpx async client.
    key : str
        The plaintext Google API key.

    Returns
    -------
    tuple[bool, str]
        ``(True, "Valid")`` or ``(False, message)``.
    """
    resp = await client.get(
        _GOOGLE_MODELS_URL,
        params={"key": key},
    )
    if resp.status_code == 200:
        return (True, "Valid")
    if resp.status_code == 429:
        return (False, "Rate limited — try again shortly")
    try:
        error_body = resp.json()
        detail = (
            error_body.get("error", {}).get("message")
            or error_body.get("error", {}).get("status")
            or resp.text
        )
    except Exception:
        detail = resp.text
    return (False, detail or f"HTTP {resp.status_code}")
