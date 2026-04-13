"""
Scan-tier AI description generation service — EPIC-006, STORY-006-01.

Generates short AI summaries of indexed Drive file content using the smallest
(cheapest) model available for each BYOK provider. This is the "scan tier"
described in ADR-004 — one summary per file at index time, re-generated only
when content hash changes (ADR-006 self-healing descriptions).

Model mapping (ADR-004 scan tier):
  google    → gemini-2.5-flash
  anthropic → claude-haiku-4-5
  openai    → gpt-4o-mini

Design note on module access pattern:
  This module accesses the pydantic-ai Agent and model classes via the
  ``app.agents.agent`` module object (imported as ``_agent_module``), NOT via
  direct ``from ... import`` statements. This allows tests to monkeypatch
  ``agent_module.Agent`` (the module-level global) and have the patched value
  take effect here — a direct import would bind to the original class and
  ignore the patch. See FLASHCARDS.md httpx pattern for the same principle.
"""

from __future__ import annotations

from app.agents import agent as _agent_module

# ADR-004: Scan-tier model IDs — smallest model per provider for cost efficiency.
SCAN_TIER_MODELS: dict[str, str] = {
    "google": "gemini-2.5-flash",
    "anthropic": "claude-haiku-4-5",
    "openai": "gpt-4o-mini",
}

_SUMMARIZE_SYSTEM_PROMPT = (
    "Summarize this document in 2-3 sentences, focusing on what questions it answers."
)


async def generate_ai_description(content: str, provider: str, api_key: str) -> str:
    """Generate a short AI summary of document content using the scan-tier model.

    Uses the smallest model available for the given provider (ADR-004) to produce
    a 2-3 sentence summary focused on what questions the document answers. Summaries
    are stored as ``ai_description`` in the knowledge index and used by the agent
    to select relevant files without reading full content (ADR-005 real-time retrieval).

    The function accesses ``_agent_module.Agent`` and related globals via the module
    reference so that monkeypatching in tests takes effect (the globals are None at
    load time and patched to non-None before this function is called by test fixtures).

    Args:
        content:  Full text content of the document (already extracted by drive_service).
        provider: BYOK provider slug — one of "google", "anthropic", "openai".
        api_key:  Decrypted plaintext BYOK API key for the provider.

    Returns:
        A 2-3 sentence summary string from the scan-tier model.

    Raises:
        ValueError: If provider is not one of "google", "anthropic", "openai".
        KeyError:   If provider is not in SCAN_TIER_MODELS.
    """
    model_id = SCAN_TIER_MODELS[provider]

    # Lazy-import pydantic-ai classes for this provider into agent module globals.
    # If tests have already monkeypatched these globals to non-None mocks,
    # _ensure_model_imports will skip the real import and keep the mock in place.
    _agent_module._ensure_model_imports(provider)

    # Build a scan-tier model instance using the agent module's builder.
    # Reads GoogleModel, AnthropicModel, etc. from _agent_module's globals —
    # this is the same reference that tests patch via monkeypatch.setattr(agent_module, ...).
    model = _agent_module._build_pydantic_ai_model(model_id, provider, api_key)

    # Instantiate a single-use Agent for this scan operation.
    # _agent_module.Agent is the module-level global (initially None, set by
    # _ensure_model_imports, or patched by tests). Accessing it via the module
    # object ensures the patched value is used.
    scan_agent = _agent_module.Agent(model, system_prompt=_SUMMARIZE_SYSTEM_PROMPT)

    result = await scan_agent.run(content)
    return result.output


async def extract_content_multimodal(
    pdf_bytes: bytes, provider: str, api_key: str,
) -> str:
    """Extract text from a scanned PDF using the scan-tier multimodal model (STORY-006-08).

    Called by drive_service.fetch_file_content when pymupdf4llm returns fewer than
    _MULTIMODAL_FALLBACK_THRESHOLD characters — indicating an image-only or scanned
    PDF that OCR cannot process.  Only supported for "google" and "openai" providers,
    which can accept raw PDF bytes as multimodal input.

    The function encodes the PDF as base64 and sends it to the scan-tier model
    (SCAN_TIER_MODELS[provider]) via a single-use pydantic-ai Agent, instructing the
    model to extract all text content and preserve tables and headings.

    Like generate_ai_description, model classes are accessed via the ``_agent_module``
    object reference so that test monkeypatches on agent.Agent / agent.GoogleModel etc.
    take effect here (direct ``from ... import`` would bind to the pre-patch value).

    Args:
        pdf_bytes: Raw PDF file bytes from Google Drive.
        provider:  BYOK provider slug — "google" or "openai" (not "anthropic").
        api_key:   Decrypted plaintext BYOK API key for the provider.

    Returns:
        Extracted text content as a plain string (may include markdown tables/headings).

    Raises:
        KeyError: If provider is not in SCAN_TIER_MODELS.
    """
    import base64

    model_id = SCAN_TIER_MODELS[provider]

    # Ensure provider-specific pydantic-ai imports are available in agent module globals.
    # If tests have already monkeypatched these to non-None mocks,
    # _ensure_model_imports will skip the real import and keep the mock in place.
    _agent_module._ensure_model_imports(provider)

    # Build a scan-tier model instance via the agent module's builder so that
    # tests can monkeypatch _agent_module.GoogleModel / OpenAIChatModel etc.
    model = _agent_module._build_pydantic_ai_model(model_id, provider, api_key)

    scan_agent = _agent_module.Agent(
        model,
        system_prompt=(
            "Extract all text content from this PDF document. "
            "Preserve tables as markdown tables. "
            "Preserve headings and structure."
        ),
    )

    b64_pdf = base64.b64encode(pdf_bytes).decode()
    result = await scan_agent.run(
        f"Extract all text from the following base64-encoded PDF:\n{b64_pdf}"
    )
    return result.output
