"""Tests for STORY-006-10 — read_drive_file cache behavior in app/agents/agent.py.

Covers all cache-related Gherkin scenarios from STORY-006-10 §2.1:

  Test 2: Cache hit — if ``cached_content`` is non-NULL, return it immediately
          without calling get_drive_client.
  Test 3: Cache miss (cached_content = None) — fetch from Drive, backfill
          ``cached_content`` via upsert.
  Test 4: Cache miss + hash change — re-generates AI description, upsert includes
          ai_description + cached_content + content_hash.
  Test 5: Cache miss + no hash change — does NOT call generate_ai_description,
          upsert includes cached_content but NOT ai_description.

Invocation strategy:
  ``read_drive_file`` is an async nested function inside ``build_agent()`` in
  ``app/agents/agent.py``. We extract it by calling ``build_agent()`` with fully
  mocked pydantic-ai internals (Agent class, model imports) and intercepting the
  ``tools=[...]`` list passed to ``Agent()``. The extracted coroutine is then called
  with a synthetic ``ctx`` (fake RunContext with fake deps).

  This approach exercises the ACTUAL implementation in agent.py — not a re-implementation
  — so RED failures come from the real code missing the cached_content logic.

Mock layers:
  - pydantic-ai Agent class → MagicMock that captures ``tools`` kwarg
  - Model class globals (_AnthropicModel, _OpenAIChatModel, _GoogleModel, etc.) → MagicMock
  - app.core.encryption.decrypt → returns FAKE_DECRYPTED_API_KEY
  - app.services.skill_service.list_skills → returns []
  - app.services.drive_service.get_drive_client → MagicMock
  - app.services.drive_service.fetch_file_content → AsyncMock returning content
  - app.services.drive_service.compute_content_hash → MagicMock returning hash
  - app.services.scan_service.generate_ai_description → AsyncMock returning description
  - Supabase client → MagicMock with per-table routing

FLASHCARDS.md consulted:
  - Hermetic mocks hide column-name mismatches — verify column names against migration SQL.
  - Supabase .upsert() — omit DEFAULT NOW() columns from payload.
  - Worktree-relative paths only in Edit/Write calls.

ADR compliance:
  - ADR-006: AI description re-generated only on hash change.

RED PHASE: Tests 2-5 FAIL because ``read_drive_file`` in agent.py does not yet
implement the cached_content fast-path or backfill upsert:
  - Test 2 fails: function calls Drive even when cached_content is non-NULL.
  - Test 3 fails: upsert payload missing cached_content.
  - Test 4 fails: upsert payload (hash-change branch) missing cached_content.
  - Test 5 fails: no upsert at all when hash is unchanged (cached_content never backfilled).
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FAKE_WORKSPACE_ID = "ws-rdf-test-001"
FAKE_USER_ID = "user-rdf-test-001"
FAKE_DRIVE_FILE_ID = "drive-rdf-file-001"
FAKE_MIME_TYPE = "application/vnd.google-apps.document"
FAKE_CACHED_CONTENT = "Cached content from a previous fetch — no Drive call needed."
FAKE_FRESH_CONTENT = "Fresh content fetched directly from Google Drive."
FAKE_OLD_HASH = "hash-old-aabbcc"
FAKE_NEW_HASH = "hash-new-ddeeff"
FAKE_SAME_HASH = "hash-same-112233"
FAKE_AI_DESCRIPTION = "An AI-generated summary of the document."
FAKE_ENCRYPTED_REFRESH_TOKEN = "enc:refresh:token"
FAKE_ENCRYPTED_API_KEY = "enc:api:key"
FAKE_DECRYPTED_API_KEY = "plaintext-api-key"
FAKE_AI_PROVIDER = "anthropic"
FAKE_AI_MODEL = "claude-3-5-sonnet-20241022"


# ---------------------------------------------------------------------------
# Helpers — fake RunContext and deps
# ---------------------------------------------------------------------------


class _FakeDeps:
    """Minimal stand-in for AgentDeps passed into read_drive_file via ctx.deps.

    Args:
        workspace_id: Workspace UUID string.
        user_id: User UUID string.
        supabase: MagicMock Supabase client.
    """

    def __init__(self, workspace_id: str, user_id: str, supabase: MagicMock) -> None:
        self.workspace_id = workspace_id
        self.user_id = user_id
        self.supabase = supabase


class _FakeCtx:
    """Minimal stand-in for pydantic-ai RunContext passed as first arg to tools.

    Args:
        deps: _FakeDeps instance.
    """

    def __init__(self, deps: _FakeDeps) -> None:
        self.deps = deps


# ---------------------------------------------------------------------------
# Helpers — Supabase mock factories
# ---------------------------------------------------------------------------


def _make_knowledge_index_select_chain(file_row: dict | None) -> MagicMock:
    """Build the Supabase SELECT chain for teemo_knowledge_index.

    Configures: .select("*").eq(workspace_id).eq(drive_file_id).execute()
    → result.data = [file_row] if non-None, else [].

    Args:
        file_row: File row dict to return, or None for "not found".

    Returns:
        MagicMock configured as the table mock.
    """
    result = MagicMock()
    result.data = [file_row] if file_row else []

    inner_eq = MagicMock()
    inner_eq.execute.return_value = result

    outer_eq = MagicMock()
    outer_eq.eq.return_value = inner_eq

    select_mock = MagicMock()
    select_mock.eq.return_value = outer_eq

    table_mock = MagicMock()
    table_mock.select.return_value = select_mock
    return table_mock


def _make_workspaces_select_chain(ws_row: dict | None) -> MagicMock:
    """Build the Supabase SELECT chain for teemo_workspaces.

    Configures: .select(...).eq(workspace_id).maybe_single().execute()
    → result.data = ws_row.

    Args:
        ws_row: Workspace row dict, or None to simulate missing workspace.

    Returns:
        MagicMock configured as the table mock.
    """
    result = MagicMock()
    result.data = ws_row

    maybe_single = MagicMock()
    maybe_single.execute.return_value = result

    eq_mock = MagicMock()
    eq_mock.maybe_single.return_value = maybe_single

    select_mock = MagicMock()
    select_mock.eq.return_value = eq_mock

    table_mock = MagicMock()
    table_mock.select.return_value = select_mock
    return table_mock


def _make_upsert_chain() -> tuple[MagicMock, list[dict]]:
    """Build the Supabase upsert chain and a list capturing upserted payloads.

    Returns:
        Tuple of (table_mock, captured_payloads). After any .upsert(payload).execute()
        call, ``payload`` is appended to captured_payloads.
    """
    captured: list[dict] = []

    upsert_result = MagicMock()
    upsert_result.data = []

    execute_mock = MagicMock(return_value=upsert_result)
    upsert_mock = MagicMock()
    upsert_mock.execute = execute_mock

    table_mock = MagicMock()

    def _upsert(payload: dict, **kwargs: Any) -> MagicMock:
        captured.append(payload)
        return upsert_mock

    table_mock.upsert = _upsert
    return table_mock, captured


def _make_supabase_mock(
    *,
    file_row: dict | None,
    ws_row: dict | None = None,
    upsert_table_mock: MagicMock | None = None,
) -> MagicMock:
    """Build a full Supabase client mock with per-table routing.

    Args:
        file_row: File row returned by teemo_knowledge_index SELECT.
        ws_row: Workspace row returned by teemo_workspaces SELECT.
            Defaults to a workspace with Drive token, API key, and provider set.
        upsert_table_mock: When provided, upsert() calls on teemo_knowledge_index
            are routed to this mock (allowing payload capture).

    Returns:
        MagicMock Supabase client.
    """
    if ws_row is None:
        ws_row = {
            "id": FAKE_WORKSPACE_ID,
            "encrypted_google_refresh_token": FAKE_ENCRYPTED_REFRESH_TOKEN,
            "encrypted_api_key": FAKE_ENCRYPTED_API_KEY,
            "ai_provider": FAKE_AI_PROVIDER,
        }

    ki_select_mock = _make_knowledge_index_select_chain(file_row)
    ws_select_mock = _make_workspaces_select_chain(ws_row)

    def _table_router(table_name: str) -> MagicMock:
        if table_name == "teemo_workspaces":
            return ws_select_mock
        if table_name == "teemo_knowledge_index":
            if upsert_table_mock is not None:
                # Composite: select from ki_select_mock, upsert from upsert_table_mock.
                composite = MagicMock()
                composite.select.return_value = ki_select_mock.select.return_value
                composite.upsert = upsert_table_mock.upsert
                return composite
            return ki_select_mock
        return MagicMock()

    supabase = MagicMock()
    supabase.table.side_effect = _table_router
    return supabase


# ---------------------------------------------------------------------------
# Core helper — extract and invoke read_drive_file from the actual agent.py
# ---------------------------------------------------------------------------


async def _build_supabase_mock_for_agent(workspace_row: dict) -> MagicMock:
    """Build a Supabase mock for the build_agent workspace query.

    build_agent queries teemo_workspaces for provider/model/key and
    teemo_knowledge_index for the knowledge catalog. Both must be mocked.

    Args:
        workspace_row: Row returned for the workspace lookup in build_agent.

    Returns:
        MagicMock Supabase client.
    """
    ws_result = MagicMock()
    ws_result.data = workspace_row

    maybe_single_mock = MagicMock()
    maybe_single_mock.execute.return_value = ws_result

    eq_mock = MagicMock()
    eq_mock.maybe_single.return_value = maybe_single_mock

    ws_select_mock = MagicMock()
    ws_select_mock.eq.return_value = eq_mock

    ws_table_mock = MagicMock()
    ws_table_mock.select.return_value = ws_select_mock

    # Knowledge catalog for system prompt (build_agent step 7.5)
    ki_result = MagicMock()
    ki_result.data = []  # empty catalog is fine for our tests

    ki_eq_mock = MagicMock()
    ki_eq_mock.execute.return_value = ki_result

    ki_select_mock = MagicMock()
    ki_select_mock.eq.return_value = ki_eq_mock

    ki_table_mock = MagicMock()
    ki_table_mock.select.return_value = ki_select_mock

    def _table_router(table_name: str) -> MagicMock:
        if table_name == "teemo_workspaces":
            return ws_table_mock
        if table_name == "teemo_knowledge_index":
            return ki_table_mock
        return MagicMock()

    supabase = MagicMock()
    supabase.table.side_effect = _table_router
    return supabase


async def _extract_read_drive_file_tool() -> Any:
    """Extract the read_drive_file coroutine from build_agent by running it with mocked deps.

    Patches pydantic-ai's Agent class to capture the ``tools`` list passed during
    construction, then finds and returns the read_drive_file function reference.

    Returns:
        Async callable — the read_drive_file tool function defined in agent.py.

    Raises:
        ImportError: If app.agents.agent cannot be imported.
        AttributeError: If read_drive_file is not found in the captured tools list.
    """
    import app.agents.agent as agent_mod  # type: ignore[import]

    captured_tools: list[Any] = []

    def _fake_agent_cls(*args: Any, tools: list | None = None, **kwargs: Any) -> MagicMock:
        """Intercept Agent(..., tools=[...]) to capture tool functions."""
        if tools:
            captured_tools.extend(tools)
        return MagicMock()

    build_agent_ws_row = {
        "ai_provider": FAKE_AI_PROVIDER,
        "ai_model": FAKE_AI_MODEL,
        "encrypted_api_key": FAKE_ENCRYPTED_API_KEY,
    }
    build_supabase = await _build_supabase_mock_for_agent(build_agent_ws_row)

    # Patch all pydantic-ai globals that build_agent relies on.
    mock_model_cls = MagicMock()
    mock_provider_cls = MagicMock()

    with (
        patch.object(agent_mod, "Agent", _fake_agent_cls, create=True),
        patch("app.core.encryption.decrypt", return_value=FAKE_DECRYPTED_API_KEY),
        patch("app.services.skill_service.list_skills", return_value=[]),
        # _ensure_model_imports patches globals — simulate their presence.
        patch.object(agent_mod, "_AnthropicModel", mock_model_cls, create=True),
        patch.object(agent_mod, "_OpenAIChatModel", mock_model_cls, create=True),
        patch.object(agent_mod, "_GoogleModel", mock_model_cls, create=True),
        patch.object(agent_mod, "_AnthropicProvider", mock_provider_cls, create=True),
        patch.object(agent_mod, "_OpenAIProvider", mock_provider_cls, create=True),
        patch.object(agent_mod, "_GoogleProvider", mock_provider_cls, create=True),
        # _build_pydantic_ai_model calls the provider/model constructors — mock result.
        patch.object(agent_mod, "_build_pydantic_ai_model", return_value=MagicMock()),
        # _build_system_prompt needs no patching (pure string assembly).
    ):
        try:
            await agent_mod.build_agent(
                workspace_id=FAKE_WORKSPACE_ID,
                user_id=FAKE_USER_ID,
                supabase=build_supabase,
            )
        except Exception:
            # build_agent may raise after tool capture — tolerate as long as we got tools.
            if not captured_tools:
                raise

    # Find read_drive_file in the captured list.
    rdf_fn: Any = None
    for tool in captured_tools:
        fn_name = getattr(tool, "__name__", "") or getattr(tool, "name", "")
        if fn_name == "read_drive_file":
            rdf_fn = tool
            break

    if rdf_fn is None:
        raise AttributeError(
            f"read_drive_file not found in Agent tools. "
            f"Captured: {[getattr(t, '__name__', repr(t)) for t in captured_tools]}"
        )

    return rdf_fn


# ---------------------------------------------------------------------------
# Test 2: Cache hit — no Drive API call
# ---------------------------------------------------------------------------


class TestReadDriveFileCacheHit:
    """STORY-006-10 Test 2: Cache hit returns cached_content without calling Drive.

    Given a file row with cached_content = "some cached text",
    When read_drive_file is called,
    Then it returns "some cached text" immediately,
    And get_drive_client is NOT called.

    RED: Fails because the current read_drive_file implementation always calls
    get_drive_client regardless of cached_content (no fast-path exists yet).
    """

    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached_content_without_drive_call(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """read_drive_file must return cached_content directly when it is non-NULL.

        The Drive client must not be instantiated on a cache hit.

        RED: Fails — agent.py reads from Drive unconditionally. After STORY-006-10
        Green phase adds the cached_content fast-path, this test will pass.
        """
        file_row = {
            "id": "kid-001",
            "workspace_id": FAKE_WORKSPACE_ID,
            "drive_file_id": FAKE_DRIVE_FILE_ID,
            "mime_type": FAKE_MIME_TYPE,
            "content_hash": FAKE_SAME_HASH,
            "cached_content": FAKE_CACHED_CONTENT,  # non-NULL → cache hit
        }

        # This supabase is used by the extracted read_drive_file, NOT by build_agent.
        supabase = _make_supabase_mock(file_row=file_row)
        deps = _FakeDeps(
            workspace_id=FAKE_WORKSPACE_ID,
            user_id=FAKE_USER_ID,
            supabase=supabase,
        )
        ctx = _FakeCtx(deps=deps)

        get_drive_client_mock = MagicMock(return_value=MagicMock())
        # agent.py calls fetch_file_content as a sync function (no await).
        fetch_mock = MagicMock(return_value=FAKE_FRESH_CONTENT)
        compute_hash_mock = MagicMock(return_value=FAKE_SAME_HASH)
        # Prevent real Anthropic API call — cache hit test should not reach this.
        generate_desc_mock = AsyncMock(return_value=FAKE_AI_DESCRIPTION)

        try:
            import app.services.drive_service as ds  # type: ignore[import]
            monkeypatch.setattr(ds, "get_drive_client", get_drive_client_mock)
            monkeypatch.setattr(ds, "fetch_file_content", fetch_mock)
            monkeypatch.setattr(ds, "compute_content_hash", compute_hash_mock)
        except (ImportError, AttributeError):
            pass

        try:
            import app.services.scan_service as ss  # type: ignore[import]
            monkeypatch.setattr(ss, "generate_ai_description", generate_desc_mock)
        except (ImportError, AttributeError):
            pass

        try:
            import app.core.encryption as enc  # type: ignore[import]
            monkeypatch.setattr(enc, "decrypt", lambda _: FAKE_DECRYPTED_API_KEY)
        except (ImportError, AttributeError):
            pass

        read_drive_file = await _extract_read_drive_file_tool()
        result = await read_drive_file(ctx, FAKE_DRIVE_FILE_ID)

        assert result == FAKE_CACHED_CONTENT, (
            f"Expected cached content to be returned directly on cache hit. "
            f"Got: {result!r}. "
            f"STORY-006-10: when cached_content is non-NULL, skip Drive and return immediately."
        )

        assert not get_drive_client_mock.called, (
            "get_drive_client must NOT be called on a cache hit. "
            "STORY-006-10: Drive API should not be invoked when cached_content is present."
        )


# ---------------------------------------------------------------------------
# Test 3: Cache miss — Drive fetch + backfill
# ---------------------------------------------------------------------------


class TestReadDriveFileCacheMiss:
    """STORY-006-10 Test 3: Cache miss fetches from Drive and backfills cached_content.

    Given a file row with cached_content = None,
    When read_drive_file is called,
    Then get_drive_client IS called,
    And fetch_file_content IS called,
    And teemo_knowledge_index.upsert() is called with cached_content in the payload.

    RED: Fails because the current upsert in agent.py omits cached_content.
    """

    @pytest.mark.asyncio
    async def test_cache_miss_fetches_from_drive_and_backfills(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Cache miss must fetch from Drive and upsert cached_content to the database.

        RED: upsert payload does not include cached_content — fails until Green adds it.
        """
        file_row = {
            "id": "kid-002",
            "workspace_id": FAKE_WORKSPACE_ID,
            "drive_file_id": FAKE_DRIVE_FILE_ID,
            "mime_type": FAKE_MIME_TYPE,
            "content_hash": FAKE_SAME_HASH,
            "cached_content": None,  # NULL → cache miss
        }

        upsert_table_mock, upsert_captured = _make_upsert_chain()
        supabase = _make_supabase_mock(
            file_row=file_row,
            upsert_table_mock=upsert_table_mock,
        )
        deps = _FakeDeps(
            workspace_id=FAKE_WORKSPACE_ID,
            user_id=FAKE_USER_ID,
            supabase=supabase,
        )
        ctx = _FakeCtx(deps=deps)

        get_drive_client_mock = MagicMock(return_value=MagicMock())
        # agent.py calls fetch_file_content as sync (no await).
        fetch_mock = MagicMock(return_value=FAKE_FRESH_CONTENT)
        # Hash unchanged — no description re-generation.
        compute_hash_mock = MagicMock(return_value=FAKE_SAME_HASH)

        try:
            import app.services.drive_service as ds  # type: ignore[import]
            monkeypatch.setattr(ds, "get_drive_client", get_drive_client_mock)
            monkeypatch.setattr(ds, "fetch_file_content", fetch_mock)
            monkeypatch.setattr(ds, "compute_content_hash", compute_hash_mock)
        except (ImportError, AttributeError):
            pass

        try:
            import app.core.encryption as enc  # type: ignore[import]
            monkeypatch.setattr(enc, "decrypt", lambda _: FAKE_DECRYPTED_API_KEY)
        except (ImportError, AttributeError):
            pass

        read_drive_file = await _extract_read_drive_file_tool()
        result = await read_drive_file(ctx, FAKE_DRIVE_FILE_ID)

        assert FAKE_FRESH_CONTENT in result, (
            f"Expected fresh content in result on cache miss. Got: {result!r}"
        )

        assert get_drive_client_mock.called, (
            "get_drive_client must be called on a cache miss."
        )

        assert upsert_captured, (
            "teemo_knowledge_index.upsert() must be called on cache miss to backfill cached_content. "
            "RED: current agent.py does not upsert cached_content when hash is unchanged."
        )

        upserted = upsert_captured[0]
        assert "cached_content" in upserted, (
            f"Upsert payload must include 'cached_content'. "
            f"STORY-006-10 requires backfilling content on cache miss. "
            f"Keys found: {list(upserted.keys())}"
        )
        assert upserted["cached_content"] == FAKE_FRESH_CONTENT, (
            f"Upserted cached_content must equal the fetched content. "
            f"Expected: {FAKE_FRESH_CONTENT!r}. Got: {upserted.get('cached_content')!r}"
        )


# ---------------------------------------------------------------------------
# Test 4: Cache miss + hash change — re-generates description
# ---------------------------------------------------------------------------


class TestReadDriveFileCacheMissHashChange:
    """STORY-006-10 Test 4: Cache miss with hash change triggers description re-generation.

    Given cached_content = None AND stored content_hash = "old-hash",
    When read_drive_file fetches content that hashes to "new-hash",
    Then generate_ai_description IS called,
    And the upsert includes ai_description + cached_content + content_hash.

    RED: Fails because the hash-change upsert branch omits cached_content.
    """

    @pytest.mark.asyncio
    async def test_cache_miss_hash_change_upsert_includes_cached_content_and_description(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Hash-change branch must include cached_content in the upsert payload.

        RED: current hash-change upsert in agent.py only includes content_hash and
        ai_description — cached_content is missing.
        """
        file_row = {
            "id": "kid-003",
            "workspace_id": FAKE_WORKSPACE_ID,
            "drive_file_id": FAKE_DRIVE_FILE_ID,
            "mime_type": FAKE_MIME_TYPE,
            "content_hash": FAKE_OLD_HASH,  # stored hash differs from new hash
            "cached_content": None,
        }

        upsert_table_mock, upsert_captured = _make_upsert_chain()
        supabase = _make_supabase_mock(
            file_row=file_row,
            upsert_table_mock=upsert_table_mock,
        )
        deps = _FakeDeps(
            workspace_id=FAKE_WORKSPACE_ID,
            user_id=FAKE_USER_ID,
            supabase=supabase,
        )
        ctx = _FakeCtx(deps=deps)

        get_drive_client_mock = MagicMock(return_value=MagicMock())
        # agent.py calls fetch_file_content as sync (no await).
        fetch_mock = MagicMock(return_value=FAKE_FRESH_CONTENT)
        # Returns FAKE_NEW_HASH which differs from stored FAKE_OLD_HASH.
        compute_hash_mock = MagicMock(return_value=FAKE_NEW_HASH)
        generate_desc_mock = AsyncMock(return_value=FAKE_AI_DESCRIPTION)

        try:
            import app.services.drive_service as ds  # type: ignore[import]
            monkeypatch.setattr(ds, "get_drive_client", get_drive_client_mock)
            monkeypatch.setattr(ds, "fetch_file_content", fetch_mock)
            monkeypatch.setattr(ds, "compute_content_hash", compute_hash_mock)
        except (ImportError, AttributeError):
            pass

        try:
            import app.services.scan_service as ss  # type: ignore[import]
            monkeypatch.setattr(ss, "generate_ai_description", generate_desc_mock)
        except (ImportError, AttributeError):
            pass

        try:
            import app.core.encryption as enc  # type: ignore[import]
            monkeypatch.setattr(enc, "decrypt", lambda _: FAKE_DECRYPTED_API_KEY)
        except (ImportError, AttributeError):
            pass

        read_drive_file = await _extract_read_drive_file_tool()
        result = await read_drive_file(ctx, FAKE_DRIVE_FILE_ID)

        assert generate_desc_mock.called, (
            "generate_ai_description must be called when content hash changes. "
            "STORY-006-10 + ADR-006: self-healing re-generates description on change."
        )

        assert upsert_captured, (
            "teemo_knowledge_index.upsert() must be called when hash changes."
        )

        upserted = upsert_captured[0]

        assert "cached_content" in upserted, (
            f"Upsert payload (hash-change branch) must include 'cached_content'. "
            f"STORY-006-10 requires backfilling content whenever Drive is fetched. "
            f"Keys found: {list(upserted.keys())}"
        )
        assert upserted["cached_content"] == FAKE_FRESH_CONTENT, (
            f"cached_content in hash-change upsert must equal fetched content. "
            f"Expected: {FAKE_FRESH_CONTENT!r}. Got: {upserted.get('cached_content')!r}"
        )

        assert "ai_description" in upserted, (
            f"Upsert payload (hash-change branch) must include 'ai_description'. "
            f"Keys found: {list(upserted.keys())}"
        )
        assert upserted["ai_description"] == FAKE_AI_DESCRIPTION

        assert "content_hash" in upserted, (
            f"Upsert payload must include updated 'content_hash'. "
            f"Keys found: {list(upserted.keys())}"
        )
        assert upserted["content_hash"] == FAKE_NEW_HASH


# ---------------------------------------------------------------------------
# Test 5: Cache miss + no hash change — no description re-generation
# ---------------------------------------------------------------------------


class TestReadDriveFileCacheMissNoHashChange:
    """STORY-006-10 Test 5: Cache miss, hash unchanged — backfill cached_content only.

    Given cached_content = None AND stored content_hash matches the fetched content,
    When read_drive_file fetches content,
    Then generate_ai_description is NOT called,
    And the upsert includes cached_content but NOT ai_description.

    RED: Fails because agent.py skips the upsert entirely when hash is unchanged
    (no cached_content backfill occurs in the current implementation).
    """

    @pytest.mark.asyncio
    async def test_cache_miss_no_hash_change_backfills_cached_content_without_description(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """No hash change: description NOT re-generated; cached_content IS upserted.

        RED: Current agent.py does not call upsert when hash matches — meaning
        cached_content is never backfilled for unchanged files.
        """
        file_row = {
            "id": "kid-004",
            "workspace_id": FAKE_WORKSPACE_ID,
            "drive_file_id": FAKE_DRIVE_FILE_ID,
            "mime_type": FAKE_MIME_TYPE,
            "content_hash": FAKE_SAME_HASH,  # same as what compute_hash will return
            "cached_content": None,
        }

        upsert_table_mock, upsert_captured = _make_upsert_chain()
        supabase = _make_supabase_mock(
            file_row=file_row,
            upsert_table_mock=upsert_table_mock,
        )
        deps = _FakeDeps(
            workspace_id=FAKE_WORKSPACE_ID,
            user_id=FAKE_USER_ID,
            supabase=supabase,
        )
        ctx = _FakeCtx(deps=deps)

        get_drive_client_mock = MagicMock(return_value=MagicMock())
        # agent.py calls fetch_file_content as sync (no await).
        fetch_mock = MagicMock(return_value=FAKE_FRESH_CONTENT)
        # Returns same hash as stored → no hash change.
        compute_hash_mock = MagicMock(return_value=FAKE_SAME_HASH)
        generate_desc_mock = AsyncMock(return_value=FAKE_AI_DESCRIPTION)

        try:
            import app.services.drive_service as ds  # type: ignore[import]
            monkeypatch.setattr(ds, "get_drive_client", get_drive_client_mock)
            monkeypatch.setattr(ds, "fetch_file_content", fetch_mock)
            monkeypatch.setattr(ds, "compute_content_hash", compute_hash_mock)
        except (ImportError, AttributeError):
            pass

        try:
            import app.services.scan_service as ss  # type: ignore[import]
            monkeypatch.setattr(ss, "generate_ai_description", generate_desc_mock)
        except (ImportError, AttributeError):
            pass

        try:
            import app.core.encryption as enc  # type: ignore[import]
            monkeypatch.setattr(enc, "decrypt", lambda _: FAKE_DECRYPTED_API_KEY)
        except (ImportError, AttributeError):
            pass

        read_drive_file = await _extract_read_drive_file_tool()
        result = await read_drive_file(ctx, FAKE_DRIVE_FILE_ID)

        assert not generate_desc_mock.called, (
            "generate_ai_description must NOT be called when content hash is unchanged. "
            "STORY-006-10 + ADR-006: skip expensive re-generation when content is same."
        )

        assert upsert_captured, (
            "teemo_knowledge_index.upsert() must be called even when hash is unchanged, "
            "to backfill cached_content. "
            "RED: current agent.py skips upsert when hash matches — cached_content never gets set."
        )

        upserted = upsert_captured[0]

        assert "cached_content" in upserted, (
            f"Upsert payload (no-hash-change branch) must include 'cached_content'. "
            f"STORY-006-10: backfill cache even when hash is unchanged. "
            f"Keys found: {list(upserted.keys())}"
        )
        assert upserted["cached_content"] == FAKE_FRESH_CONTENT, (
            f"cached_content in no-hash-change upsert must equal fetched content."
        )

        assert "ai_description" not in upserted, (
            f"Upsert payload (no-hash-change branch) must NOT include 'ai_description'. "
            f"STORY-006-10: only re-generate description when hash changes. "
            f"Keys found: {list(upserted.keys())}"
        )
