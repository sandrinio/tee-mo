"""
Tests for Google env vars in Settings — STORY-006-01 (Red Phase).

Covers Gherkin scenario:
  - Config loads Google env vars
    Given GOOGLE_API_CLIENT_ID and GOOGLE_API_SECRET are set in .env
    When Settings() is instantiated
    Then google_api_client_id and google_api_secret are populated
    And google_picker_api_key defaults to empty string if not set
    And google_oauth_redirect_uri loads from env

These tests verify the R1 requirement from STORY-006-01 §1.2:
  Add google_api_client_id, google_api_secret, google_picker_api_key (optional,
  default empty string), google_oauth_redirect_uri to Settings in config.py.

Test pattern:
  - Uses monkeypatch to set env vars before Settings instantiation.
  - Calls get_settings.cache_clear() before each test so the lru_cache singleton
    does not bleed state between tests (same pattern as all other config tests
    in this codebase — verified from config.py docstring).
  - All required non-Google env vars are set to valid values to prevent
    ValidationError on other fields (encryption key is 32 raw bytes, base64url encoded).
"""

from __future__ import annotations

import base64
import os

import pytest


# ---------------------------------------------------------------------------
# Shared fixture: provide all required env vars so Settings() validates cleanly
# ---------------------------------------------------------------------------

# A valid 32-byte AES key in base64url format (no padding, as secrets.token_urlsafe generates)
_VALID_ENCRYPTION_KEY = base64.urlsafe_b64encode(b"A" * 32).decode().rstrip("=")

# A JWT secret >= 32 bytes (required by ADR-017 startup validator)
_VALID_JWT_SECRET = "a-sufficiently-long-jwt-secret-key-for-tests-00"


@pytest.fixture(autouse=True)
def clear_settings_cache():
    """Clear the lru_cache on get_settings() before and after each test.

    This ensures monkeypatched env vars take effect (a cached Settings instance
    would ignore env var changes). Pattern matches the existing auth test suite.
    """
    from app.core.config import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def base_env(monkeypatch):
    """Set all required Settings fields (non-Google) to valid values.

    Tests that focus on Google vars call this fixture to avoid ValidationError
    on unrelated required fields.
    """
    monkeypatch.setenv("SUPABASE_URL", "https://db.example.com")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key-value")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-key-value")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", _VALID_JWT_SECRET)
    monkeypatch.setenv("SLACK_CLIENT_ID", "slack-client-id-test")
    monkeypatch.setenv("SLACK_CLIENT_SECRET", "slack-client-secret-test")
    monkeypatch.setenv("SLACK_SIGNING_SECRET", "slack-signing-secret-test")
    monkeypatch.setenv("SLACK_REDIRECT_URL", "https://example.com/slack/callback")
    monkeypatch.setenv("TEEMO_ENCRYPTION_KEY", _VALID_ENCRYPTION_KEY)


# ---------------------------------------------------------------------------
# Tests: google_api_client_id
# ---------------------------------------------------------------------------

class TestGoogleApiClientId:
    """Settings.google_api_client_id loads from GOOGLE_API_CLIENT_ID env var."""

    def test_loads_google_api_client_id_from_env(self, monkeypatch, base_env):
        """google_api_client_id must equal GOOGLE_API_CLIENT_ID env var value."""
        monkeypatch.setenv("GOOGLE_API_CLIENT_ID", "test-google-client-id-001")
        monkeypatch.setenv("GOOGLE_API_SECRET", "test-google-secret-001")
        monkeypatch.setenv("GOOGLE_OAUTH_REDIRECT_URI", "https://example.com/auth/google/callback")

        from app.core.config import Settings
        settings = Settings()  # type: ignore[call-arg]

        assert settings.google_api_client_id == "test-google-client-id-001"


# ---------------------------------------------------------------------------
# Tests: google_api_secret
# ---------------------------------------------------------------------------

class TestGoogleApiSecret:
    """Settings.google_api_secret loads from GOOGLE_API_SECRET env var."""

    def test_loads_google_api_secret_from_env(self, monkeypatch, base_env):
        """google_api_secret must equal GOOGLE_API_SECRET env var value."""
        monkeypatch.setenv("GOOGLE_API_CLIENT_ID", "test-google-client-id-002")
        monkeypatch.setenv("GOOGLE_API_SECRET", "test-google-secret-value-002")
        monkeypatch.setenv("GOOGLE_OAUTH_REDIRECT_URI", "https://example.com/auth/google/callback")

        from app.core.config import Settings
        settings = Settings()  # type: ignore[call-arg]

        assert settings.google_api_secret == "test-google-secret-value-002"


# ---------------------------------------------------------------------------
# Tests: google_picker_api_key (optional, default empty string)
# ---------------------------------------------------------------------------

class TestGooglePickerApiKey:
    """Settings.google_picker_api_key defaults to empty string when not set."""

    def test_defaults_to_empty_string_when_not_set(self, monkeypatch, base_env):
        """google_picker_api_key must default to empty string if GOOGLE_PICKER_API_KEY is absent."""
        monkeypatch.setenv("GOOGLE_API_CLIENT_ID", "test-google-client-id-003")
        monkeypatch.setenv("GOOGLE_API_SECRET", "test-google-secret-003")
        monkeypatch.setenv("GOOGLE_OAUTH_REDIRECT_URI", "https://example.com/auth/google/callback")
        # Explicitly remove picker key if it happens to be in env
        monkeypatch.delenv("GOOGLE_PICKER_API_KEY", raising=False)

        from app.core.config import Settings
        settings = Settings()  # type: ignore[call-arg]

        assert settings.google_picker_api_key == ""

    def test_loads_picker_api_key_when_set(self, monkeypatch, base_env):
        """google_picker_api_key must load the env var value when GOOGLE_PICKER_API_KEY is set."""
        monkeypatch.setenv("GOOGLE_API_CLIENT_ID", "test-google-client-id-004")
        monkeypatch.setenv("GOOGLE_API_SECRET", "test-google-secret-004")
        monkeypatch.setenv("GOOGLE_OAUTH_REDIRECT_URI", "https://example.com/auth/google/callback")
        monkeypatch.setenv("GOOGLE_PICKER_API_KEY", "my-picker-key-value")

        from app.core.config import Settings
        settings = Settings()  # type: ignore[call-arg]

        assert settings.google_picker_api_key == "my-picker-key-value"


# ---------------------------------------------------------------------------
# Tests: google_oauth_redirect_uri
# ---------------------------------------------------------------------------

class TestGoogleOauthRedirectUri:
    """Settings.google_oauth_redirect_uri loads from GOOGLE_OAUTH_REDIRECT_URI env var."""

    def test_loads_google_oauth_redirect_uri_from_env(self, monkeypatch, base_env):
        """google_oauth_redirect_uri must equal GOOGLE_OAUTH_REDIRECT_URI env var value."""
        monkeypatch.setenv("GOOGLE_API_CLIENT_ID", "test-google-client-id-005")
        monkeypatch.setenv("GOOGLE_API_SECRET", "test-google-secret-005")
        redirect_uri = "https://app.example.com/auth/google/callback"
        monkeypatch.setenv("GOOGLE_OAUTH_REDIRECT_URI", redirect_uri)

        from app.core.config import Settings
        settings = Settings()  # type: ignore[call-arg]

        assert settings.google_oauth_redirect_uri == redirect_uri
