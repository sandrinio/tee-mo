"""
Tests for scan_service.py — STORY-006-01 (Red Phase).

Covers all Gherkin scenarios from §2.1:
  1. generate_ai_description with provider "google" → uses model "gemini-2.5-flash"
  2. generate_ai_description with provider "anthropic" → uses model "claude-haiku-4-5"
  3. generate_ai_description with provider "openai" → uses model "gpt-4o-mini"
  4. Returns the summary string from the agent run

Mock strategy:
  - The module-level globals in agent.py (Agent, GoogleModel, AnthropicModel,
    OpenAIChatModel, etc.) are patched via monkeypatch.setattr on the agent module
    before scan_service calls _ensure_model_imports and _build_pydantic_ai_model.
    Because _ensure_model_imports checks `if X is None` before importing, a non-None
    mock placed there before the call prevents the real import from running.
  - The pydantic-ai Agent is mocked to return a predictable result.
  - Tests are async — scan_service.generate_ai_description is an async function.
  - No real LLM calls are made.

ADR compliance:
  - ADR-004 scan-tier model mapping:
      google    → gemini-2.5-flash
      anthropic → claude-haiku-4-5
      openai    → gpt-4o-mini
  - ADR-016: provider slugs are lowercase: "google", "anthropic", "openai"
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio


# ---------------------------------------------------------------------------
# Import guard — module does not exist yet (RED phase)
# ---------------------------------------------------------------------------

scan_service = None
agent_module = None

try:
    import app.services.scan_service as _ss  # type: ignore[import]
    scan_service = _ss
except ImportError:
    pass  # Expected during RED phase — implementation not yet written

try:
    import app.agents.agent as _agent_mod  # type: ignore[import]
    agent_module = _agent_mod
except ImportError:
    pass


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

SAMPLE_CONTENT = (
    "This document describes the quarterly financial results for Tee-Mo Inc. "
    "Revenue grew 42% year-over-year. Operating expenses were reduced by 15%."
)
EXPECTED_SUMMARY = "The document covers Q3 financials with strong revenue growth."
FAKE_API_KEY = "test-api-key-scan-tier"


def _patch_agent_module_globals(monkeypatch):
    """Patch module-level globals in agent.py so _ensure_model_imports skips real imports.

    The lazy import guard in _ensure_model_imports checks ``if X is None`` —
    setting a MagicMock (truthy, non-None) causes it to skip the real import
    and keep the mock in place. This allows tests to run without the pydantic-ai
    provider extras installed.
    """
    if agent_module is None:
        return {}

    mock_agent_cls = MagicMock()
    mock_google_model = MagicMock()
    mock_google_provider = MagicMock()
    mock_anthropic_model = MagicMock()
    mock_anthropic_provider = MagicMock()
    mock_openai_model = MagicMock()
    mock_openai_provider = MagicMock()

    monkeypatch.setattr(agent_module, "Agent", mock_agent_cls)
    monkeypatch.setattr(agent_module, "GoogleModel", mock_google_model)
    monkeypatch.setattr(agent_module, "GoogleProvider", mock_google_provider)
    monkeypatch.setattr(agent_module, "AnthropicModel", mock_anthropic_model)
    monkeypatch.setattr(agent_module, "AnthropicProvider", mock_anthropic_provider)
    monkeypatch.setattr(agent_module, "OpenAIChatModel", mock_openai_model)
    monkeypatch.setattr(agent_module, "OpenAIProvider", mock_openai_provider)

    return {
        "Agent": mock_agent_cls,
        "GoogleModel": mock_google_model,
        "GoogleProvider": mock_google_provider,
        "AnthropicModel": mock_anthropic_model,
        "AnthropicProvider": mock_anthropic_provider,
        "OpenAIChatModel": mock_openai_model,
        "OpenAIProvider": mock_openai_provider,
    }


# ---------------------------------------------------------------------------
# Scenario 1: Provider "google" → scan-tier model "gemini-2.5-flash"
# ---------------------------------------------------------------------------

class TestGenerateAiDescriptionGoogle:
    """generate_ai_description with provider='google' must use 'gemini-2.5-flash'."""

    @pytest.mark.asyncio
    async def test_google_provider_uses_gemini_flash(self, monkeypatch):
        """generate_ai_description must build model with 'gemini-2.5-flash' for 'google' provider."""
        if scan_service is None:
            pytest.skip("scan_service not yet implemented (RED phase)")

        mocks = _patch_agent_module_globals(monkeypatch)

        # Configure the Agent mock to return a summary when run() is called
        mock_agent_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.output = EXPECTED_SUMMARY
        mock_agent_instance.run = AsyncMock(return_value=mock_result)
        mocks["Agent"].return_value = mock_agent_instance

        result = await scan_service.generate_ai_description(
            content=SAMPLE_CONTENT,
            provider="google",
            api_key=FAKE_API_KEY,
        )

        # Verify the GoogleModel was instantiated with the scan-tier model ID
        mocks["GoogleModel"].assert_called_once_with(
            "gemini-2.5-flash",
            provider=mocks["GoogleProvider"].return_value,
        )

    @pytest.mark.asyncio
    async def test_google_provider_returns_summary_string(self, monkeypatch):
        """generate_ai_description must return the summary string from the agent run."""
        if scan_service is None:
            pytest.skip("scan_service not yet implemented (RED phase)")

        mocks = _patch_agent_module_globals(monkeypatch)

        mock_agent_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.output = EXPECTED_SUMMARY
        mock_agent_instance.run = AsyncMock(return_value=mock_result)
        mocks["Agent"].return_value = mock_agent_instance

        result = await scan_service.generate_ai_description(
            content=SAMPLE_CONTENT,
            provider="google",
            api_key=FAKE_API_KEY,
        )

        assert result == EXPECTED_SUMMARY


# ---------------------------------------------------------------------------
# Scenario 2: Provider "anthropic" → scan-tier model "claude-haiku-4-5"
# ---------------------------------------------------------------------------

class TestGenerateAiDescriptionAnthropic:
    """generate_ai_description with provider='anthropic' must use 'claude-haiku-4-5'."""

    @pytest.mark.asyncio
    async def test_anthropic_provider_uses_claude_haiku(self, monkeypatch):
        """generate_ai_description must build model with 'claude-haiku-4-5' for 'anthropic' provider."""
        if scan_service is None:
            pytest.skip("scan_service not yet implemented (RED phase)")

        mocks = _patch_agent_module_globals(monkeypatch)

        mock_agent_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.output = EXPECTED_SUMMARY
        mock_agent_instance.run = AsyncMock(return_value=mock_result)
        mocks["Agent"].return_value = mock_agent_instance

        result = await scan_service.generate_ai_description(
            content=SAMPLE_CONTENT,
            provider="anthropic",
            api_key=FAKE_API_KEY,
        )

        mocks["AnthropicModel"].assert_called_once_with(
            "claude-haiku-4-5",
            provider=mocks["AnthropicProvider"].return_value,
        )

    @pytest.mark.asyncio
    async def test_anthropic_provider_returns_summary_string(self, monkeypatch):
        """generate_ai_description must return the summary string for 'anthropic' provider."""
        if scan_service is None:
            pytest.skip("scan_service not yet implemented (RED phase)")

        mocks = _patch_agent_module_globals(monkeypatch)

        mock_agent_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.output = EXPECTED_SUMMARY
        mock_agent_instance.run = AsyncMock(return_value=mock_result)
        mocks["Agent"].return_value = mock_agent_instance

        result = await scan_service.generate_ai_description(
            content=SAMPLE_CONTENT,
            provider="anthropic",
            api_key=FAKE_API_KEY,
        )

        assert result == EXPECTED_SUMMARY


# ---------------------------------------------------------------------------
# Scenario 3: Provider "openai" → scan-tier model "gpt-4o-mini"
# ---------------------------------------------------------------------------

class TestGenerateAiDescriptionOpenAI:
    """generate_ai_description with provider='openai' must use 'gpt-4o-mini'."""

    @pytest.mark.asyncio
    async def test_openai_provider_uses_gpt4o_mini(self, monkeypatch):
        """generate_ai_description must build model with 'gpt-4o-mini' for 'openai' provider."""
        if scan_service is None:
            pytest.skip("scan_service not yet implemented (RED phase)")

        mocks = _patch_agent_module_globals(monkeypatch)

        mock_agent_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.output = EXPECTED_SUMMARY
        mock_agent_instance.run = AsyncMock(return_value=mock_result)
        mocks["Agent"].return_value = mock_agent_instance

        result = await scan_service.generate_ai_description(
            content=SAMPLE_CONTENT,
            provider="openai",
            api_key=FAKE_API_KEY,
        )

        mocks["OpenAIChatModel"].assert_called_once_with(
            "gpt-4o-mini",
            provider=mocks["OpenAIProvider"].return_value,
        )

    @pytest.mark.asyncio
    async def test_openai_provider_returns_summary_string(self, monkeypatch):
        """generate_ai_description must return the summary string for 'openai' provider."""
        if scan_service is None:
            pytest.skip("scan_service not yet implemented (RED phase)")

        mocks = _patch_agent_module_globals(monkeypatch)

        mock_agent_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.output = EXPECTED_SUMMARY
        mock_agent_instance.run = AsyncMock(return_value=mock_result)
        mocks["Agent"].return_value = mock_agent_instance

        result = await scan_service.generate_ai_description(
            content=SAMPLE_CONTENT,
            provider="openai",
            api_key=FAKE_API_KEY,
        )

        assert result == EXPECTED_SUMMARY


# ---------------------------------------------------------------------------
# Scenario 4: Verify the summarization prompt is used
# ---------------------------------------------------------------------------

class TestGenerateAiDescriptionPrompt:
    """generate_ai_description must pass the correct summarization prompt to the agent."""

    @pytest.mark.asyncio
    async def test_agent_run_called_with_content(self, monkeypatch):
        """generate_ai_description must call agent.run() with the provided content."""
        if scan_service is None:
            pytest.skip("scan_service not yet implemented (RED phase)")

        mocks = _patch_agent_module_globals(monkeypatch)

        mock_agent_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.output = EXPECTED_SUMMARY
        mock_agent_instance.run = AsyncMock(return_value=mock_result)
        mocks["Agent"].return_value = mock_agent_instance

        await scan_service.generate_ai_description(
            content=SAMPLE_CONTENT,
            provider="anthropic",
            api_key=FAKE_API_KEY,
        )

        # agent.run() must have been called with a prompt that includes the content
        mock_agent_instance.run.assert_called_once()
        call_args = mock_agent_instance.run.call_args
        prompt_arg = call_args.args[0] if call_args.args else call_args.kwargs.get("user_prompt", "")
        assert SAMPLE_CONTENT in prompt_arg or "Summarize" in prompt_arg

    @pytest.mark.asyncio
    async def test_api_key_passed_to_provider(self, monkeypatch):
        """generate_ai_description must pass the api_key to the provider constructor."""
        if scan_service is None:
            pytest.skip("scan_service not yet implemented (RED phase)")

        mocks = _patch_agent_module_globals(monkeypatch)

        mock_agent_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.output = EXPECTED_SUMMARY
        mock_agent_instance.run = AsyncMock(return_value=mock_result)
        mocks["Agent"].return_value = mock_agent_instance

        await scan_service.generate_ai_description(
            content=SAMPLE_CONTENT,
            provider="openai",
            api_key=FAKE_API_KEY,
        )

        mocks["OpenAIProvider"].assert_called_once_with(api_key=FAKE_API_KEY)


# ---------------------------------------------------------------------------
# STORY-006-08: extract_content_multimodal — multimodal PDF extraction
# ---------------------------------------------------------------------------

# Raw fake PDF bytes (content doesn't matter — only passed to the model)
_FAKE_PDF_BYTES = b"%PDF-1.4 fake scanned pdf content for multimodal test"
_MULTIMODAL_RESULT = "Extracted text from scanned PDF via multimodal model."


class TestExtractContentMultimodal:
    """STORY-006-08: extract_content_multimodal builds a scan-tier agent and returns result.

    ``extract_content_multimodal(pdf_bytes, provider, api_key)`` is a new async
    function added to scan_service.  It accepts raw PDF bytes, the provider slug,
    and a decrypted API key, then sends the PDF as a native multimodal message to
    the scan-tier model (SCAN_TIER_MODELS[provider]) and returns the text result.

    Supported providers: "google", "openai" (Anthropic cannot process raw PDFs).

    Mock strategy:
    - agent_module globals (Agent, *Model, *Provider) are patched via
      _patch_agent_module_globals so no real LLM calls are made.
    - The Agent mock instance's run() is an AsyncMock returning a predictable result.
    - SCAN_TIER_MODELS is consulted for the expected model ID.
    """

    @pytest.mark.asyncio
    async def test_google_provider_uses_scan_tier_model(self, monkeypatch):
        """extract_content_multimodal must build a GoogleModel with SCAN_TIER_MODELS['google']."""
        if scan_service is None:
            pytest.skip("scan_service not yet implemented (RED phase)")

        mocks = _patch_agent_module_globals(monkeypatch)

        mock_agent_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.output = _MULTIMODAL_RESULT
        mock_agent_instance.run = AsyncMock(return_value=mock_result)
        mocks["Agent"].return_value = mock_agent_instance

        result = await scan_service.extract_content_multimodal(
            pdf_bytes=_FAKE_PDF_BYTES,
            provider="google",
            api_key=FAKE_API_KEY,
        )

        expected_model_id = scan_service.SCAN_TIER_MODELS["google"]
        mocks["GoogleModel"].assert_called_once_with(
            expected_model_id,
            provider=mocks["GoogleProvider"].return_value,
        )

    @pytest.mark.asyncio
    async def test_openai_provider_uses_scan_tier_model(self, monkeypatch):
        """extract_content_multimodal must build an OpenAIChatModel with SCAN_TIER_MODELS['openai']."""
        if scan_service is None:
            pytest.skip("scan_service not yet implemented (RED phase)")

        mocks = _patch_agent_module_globals(monkeypatch)

        mock_agent_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.output = _MULTIMODAL_RESULT
        mock_agent_instance.run = AsyncMock(return_value=mock_result)
        mocks["Agent"].return_value = mock_agent_instance

        result = await scan_service.extract_content_multimodal(
            pdf_bytes=_FAKE_PDF_BYTES,
            provider="openai",
            api_key=FAKE_API_KEY,
        )

        expected_model_id = scan_service.SCAN_TIER_MODELS["openai"]
        mocks["OpenAIChatModel"].assert_called_once_with(
            expected_model_id,
            provider=mocks["OpenAIProvider"].return_value,
        )

    @pytest.mark.asyncio
    async def test_agent_run_called_with_pdf_content(self, monkeypatch):
        """extract_content_multimodal must call agent.run() with the PDF bytes content."""
        if scan_service is None:
            pytest.skip("scan_service not yet implemented (RED phase)")

        mocks = _patch_agent_module_globals(monkeypatch)

        mock_agent_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.output = _MULTIMODAL_RESULT
        mock_agent_instance.run = AsyncMock(return_value=mock_result)
        mocks["Agent"].return_value = mock_agent_instance

        await scan_service.extract_content_multimodal(
            pdf_bytes=_FAKE_PDF_BYTES,
            provider="google",
            api_key=FAKE_API_KEY,
        )

        # agent.run() must have been called once
        mock_agent_instance.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_model_output_string(self, monkeypatch):
        """extract_content_multimodal must return the text output from the agent run."""
        if scan_service is None:
            pytest.skip("scan_service not yet implemented (RED phase)")

        mocks = _patch_agent_module_globals(monkeypatch)

        mock_agent_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.output = _MULTIMODAL_RESULT
        mock_agent_instance.run = AsyncMock(return_value=mock_result)
        mocks["Agent"].return_value = mock_agent_instance

        result = await scan_service.extract_content_multimodal(
            pdf_bytes=_FAKE_PDF_BYTES,
            provider="openai",
            api_key=FAKE_API_KEY,
        )

        assert result == _MULTIMODAL_RESULT

    @pytest.mark.asyncio
    async def test_api_key_passed_to_google_provider(self, monkeypatch):
        """extract_content_multimodal must pass the api_key to GoogleProvider constructor."""
        if scan_service is None:
            pytest.skip("scan_service not yet implemented (RED phase)")

        mocks = _patch_agent_module_globals(monkeypatch)

        mock_agent_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.output = _MULTIMODAL_RESULT
        mock_agent_instance.run = AsyncMock(return_value=mock_result)
        mocks["Agent"].return_value = mock_agent_instance

        await scan_service.extract_content_multimodal(
            pdf_bytes=_FAKE_PDF_BYTES,
            provider="google",
            api_key=FAKE_API_KEY,
        )

        mocks["GoogleProvider"].assert_called_once_with(api_key=FAKE_API_KEY)
