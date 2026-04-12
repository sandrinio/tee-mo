"""
Unit tests for BYOK key resolver functions.

Tests:
- app.core.keys.get_workspace_key      (non-inference path)
- app.services.provider_resolver.resolve_provider_key  (inference path)

All tests mock the Supabase client chain — no live DB calls needed.
Tests 1-3 mock the full .table().select().eq().maybe_single().execute() chain.
Tests 4-5 patch get_workspace_key directly.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.core.encryption import encrypt
from app.core.keys import get_workspace_key
from app.services.provider_resolver import resolve_provider_key


def _make_supabase(data: dict | None) -> MagicMock:
    """Build a minimal Supabase client mock for the query chain.

    Mocks the chain:
        supabase.table(...).select(...).eq(...).maybe_single().execute()

    The ``execute()`` return value has a ``.data`` attribute set to ``data``.
    """
    mock_result = MagicMock()
    mock_result.data = data

    mock_maybe_single = MagicMock()
    mock_maybe_single.execute.return_value = mock_result

    mock_eq = MagicMock()
    mock_eq.maybe_single.return_value = mock_maybe_single

    mock_select = MagicMock()
    mock_select.eq.return_value = mock_eq

    mock_table = MagicMock()
    mock_table.select.return_value = mock_select

    mock_supabase = MagicMock()
    mock_supabase.table.return_value = mock_table

    return mock_supabase


class TestGetWorkspaceKey:
    """Tests for app.core.keys.get_workspace_key."""

    def test_get_workspace_key_returns_decrypted(self):
        """Scenario: key exists — returns decrypted plaintext.

        Given teemo_workspaces has encrypted_api_key = AES("sk-test") for workspace W1,
        when get_workspace_key(supabase, "W1") is called,
        then it returns "sk-test".
        """
        encrypted_value = encrypt("sk-test")
        supabase = _make_supabase(data={"encrypted_api_key": encrypted_value})

        result = get_workspace_key(supabase, "W1")

        assert result == "sk-test"

    def test_get_workspace_key_returns_none_when_null(self):
        """Scenario: key column is NULL — returns None.

        Given teemo_workspaces has encrypted_api_key = NULL for workspace W2,
        when get_workspace_key(supabase, "W2") is called,
        then it returns None.
        """
        supabase = _make_supabase(data={"encrypted_api_key": None})

        result = get_workspace_key(supabase, "W2")

        assert result is None

    def test_get_workspace_key_returns_none_when_no_row(self):
        """Scenario: workspace row does not exist — returns None.

        Given no row for workspace W3 exists in teemo_workspaces,
        when get_workspace_key(supabase, "W3") is called,
        then it returns None.
        """
        supabase = _make_supabase(data=None)

        result = get_workspace_key(supabase, "W3")

        assert result is None


class TestResolveProviderKey:
    """Tests for app.services.provider_resolver.resolve_provider_key."""

    def test_resolve_provider_key_success(self):
        """Scenario: key exists — returns decrypted plaintext.

        Given workspace W1 has a valid encrypted_api_key,
        when resolve_provider_key("W1", supabase) is called,
        then it returns the decrypted plaintext key string.
        """
        with patch("app.services.provider_resolver.get_workspace_key", return_value="sk-test") as mock_gwk:
            supabase = MagicMock()
            result = resolve_provider_key("W1", supabase)

        assert result == "sk-test"
        mock_gwk.assert_called_once_with(supabase, "W1")

    def test_resolve_provider_key_raises_when_no_key(self):
        """Scenario: no key configured — raises ValueError with human-readable message.

        Given workspace W2 has encrypted_api_key = NULL,
        when resolve_provider_key("W2", supabase) is called,
        then it raises ValueError containing "No API key configured".
        """
        with patch("app.services.provider_resolver.get_workspace_key", return_value=None):
            supabase = MagicMock()
            with pytest.raises(ValueError, match="No API key configured for workspace W2"):
                resolve_provider_key("W2", supabase)
