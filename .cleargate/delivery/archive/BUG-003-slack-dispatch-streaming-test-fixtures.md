---
bug_id: "BUG-003"
parent_ref: "EPIC-007"
status: "Draft"
severity: "P2-Medium"
reporter: "@sandrinio"
approved: false
created_at: "2026-04-25T00:00:00Z"
updated_at: "2026-04-25T00:00:00Z"
created_at_version: "cleargate-pre-S15"
updated_at_version: "cleargate-pre-S15"
server_pushed_at_version: null
draft_tokens:
  input: null
  output: null
  cache_read: null
  cache_creation: null
  model: null
  sessions: []
cached_gate_result:
  pass: null
  failing_criteria: []
  last_gate_check: null
---

# BUG-003: `test_slack_dispatch.py` legacy `agent.run` mocks not migrated to streaming `run_stream`

## 1. The Anomaly (Expected vs. Actual)

**Expected Behavior:** All tests in `backend/tests/test_slack_dispatch.py` pass on a clean checkout. They exercise `slack_dispatch._handle_app_mention` / `_handle_dm`, which use streaming agent output via `agent.run_stream(...)` → `stream.stream_text(delta=True)`.

**Actual Behavior:** Three tests fail on the sprint-tip baseline:

- `test_app_mention_bound_channel_happy_path`
- `test_dm_happy_path`
- `test_mention_prefix_stripped_before_agent`

Root cause: the fixtures mock `mock_agent.run = AsyncMock(...)` (the legacy non-streaming entry point). The production path calls `mock_agent.run_stream(...)` instead, then iterates `stream.stream_text(delta=True)`. `AsyncMock(...)()` returns a coroutine, not an async-iterable, so `async for chunk in stream.stream_text(delta=True):` blows up at `slack_dispatch.py:105` with:

```
RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited
```

…and the assertions about `chat.postMessage` text never run because the dispatch path crashes before reaching the post.

## 2. Reproduction Protocol

1. From repo root: `cd backend && source .venv/bin/activate`.
2. `pytest tests/test_slack_dispatch.py --no-header -q`.
3. Observe: `3 failed, 8 passed`.

## 3. Evidence & Context

```
FAILED tests/test_slack_dispatch.py::test_app_mention_bound_channel_happy_path
FAILED tests/test_slack_dispatch.py::test_dm_happy_path - AssertionError: ...
FAILED tests/test_slack_dispatch.py::test_mention_prefix_stripped_before_agent

backend/app/services/slack_dispatch.py:105: RuntimeWarning:
  coroutine 'AsyncMockMixin._execute_mock_call' was never awaited
    async for chunk in stream.stream_text(delta=True):
```

**Production source line that the fixtures must satisfy** (`backend/app/services/slack_dispatch.py:104–105`):

```python
async with agent.run_stream(user_prompt, **run_kwargs) as stream:
    async for chunk in stream.stream_text(delta=True):
        ...
```

So `run_stream(...)` must return an async-context-manager whose `__aenter__` returns an object with `stream_text(delta=True)` that is itself an async iterator yielding string chunks.

**Note on origin:** these failures are pre-existing — they were flagged but not addressed in SPRINT-14 (REPORT.md §"What's unblocked for next sprint"). They contribute to the 46-failure baseline reported at S-14 close. Not a regression from this sprint.

## 4. Execution Sandbox (Suspected Blast Radius)

**Investigate / Modify:**
- `backend/tests/test_slack_dispatch.py` — fixtures for the 3 failing tests. Two coupled changes are required:
  1. Extend `FakeAsyncWebClient` (defined at `~:81–106`) with `chat_update` capture. Production `slack_dispatch.py` calls `client.chat_update(...)` at `:113`, `:131`, and `:141` during streaming — once the streaming path actually runs end-to-end (post-recipe), `chat_update` will hit `AttributeError` if not stubbed. Add a `update_calls: list[dict]` field + an async `chat_update(self, **kwargs)` method that appends `kwargs` and returns a fake `ok` response shape mirroring `chat_postMessage`.
  2. Replace `mock_agent.run = AsyncMock(...)` with a `run_stream` mock that yields a configurable list of string chunks (recipe in §5).
- Re-point text-content assertions to read from the **final streaming chunk-concatenation** captured in `update_calls[-1]`, not from the initial placeholder in `post_message_calls[0]`. The placeholder is posted before streaming begins; the full response arrives via successive `chat_update` calls.

**Do NOT modify:**
- `backend/app/services/slack_dispatch.py` — production code is correct; only the test fixtures are stale.
- `backend/app/agents/agent.py` — agent factory unaffected.
- The 5 currently-passing tests in `test_slack_dispatch.py` (including the new `_sender_tz_*` cases from STORY-018-08). Their fixtures may already mock `run_stream` — verify and reuse.

## 5. Verification Protocol (The Failing Test)

**Pre-fix command (must reproduce the failure):**
```
cd backend && source .venv/bin/activate
pytest tests/test_slack_dispatch.py::test_app_mention_bound_channel_happy_path \
       tests/test_slack_dispatch.py::test_dm_happy_path \
       tests/test_slack_dispatch.py::test_mention_prefix_stripped_before_agent --no-header -q
```
Expected: 3 failed.

**Post-fix command (must show clean):**
Same command. Expected: 3 passed.

**Whole-file regression command:**
```
pytest tests/test_slack_dispatch.py --no-header -q
```
Expected pre-fix: `3 failed, 8 passed`. Expected post-fix: `0 failed, 11 passed`.

**Recommended fixture shape (non-binding — implementer may choose an equivalent):**

```python
class _FakeStream:
    def __init__(self, chunks): self._chunks = chunks
    async def stream_text(self, delta=True):
        for c in self._chunks:
            yield c

class _FakeStreamCtx:
    def __init__(self, chunks): self._stream = _FakeStream(chunks)
    async def __aenter__(self): return self._stream
    async def __aexit__(self, *a): return False

mock_agent.run_stream = MagicMock(return_value=_FakeStreamCtx(["Hello ", "from agent!"]))
```

Then the existing assertions on `chat.postMessage` / `chat.update` text content remain valid — they just need to read the concatenated chunks.

---

## ClearGate Ambiguity Gate (🟢 / 🟡 / 🔴)
**Current Status: 🟢 Green — Ready for Fix**

- [x] Reproduction is 100% deterministic (single `pytest` command).
- [x] Actual vs. Expected explicitly defined with the exact warning + line ref.
- [x] Raw evidence attached (warning text + production line snippet).
- [x] Verification command provided (pre-fix + post-fix).
- [ ] `approved: true` — pending human Gate-1 sign-off as part of SPRINT-15 plan approval.
