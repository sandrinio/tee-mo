---
story_id: "STORY-016-01"
agent: "Developer"
status: "implemented"
correction_tax: 5
input_tokens: 538
output_tokens: 1887
total_tokens: 2425
tests_written: 21
files_modified:
  - "backend/app/core/logging_config.py"
  - "backend/app/main.py"
  - "backend/app/core/config.py"
  - "backend/app/services/slack_dispatch.py"
  - "backend/pyproject.toml"
  - "backend/tests/test_logging_config.py"
  - "backend/tests/test_access_log.py"
flashcards_flagged: 2
---

# Developer Implementation Report: STORY-016-01-structured-logging

## Files Modified

- `backend/app/core/logging_config.py` (NEW) — Core module implementing `setup_logging()`, `RequestIdFilter`, `RedactingFilter`, and the exported `request_id_ctx` ContextVar. Dual-surface output: redacting JSON console handler at configurable level, always-DEBUG file handler at `/tmp/teemo/teemo.log` with daily rotation.
- `backend/app/main.py` — Wired `setup_logging(settings.log_level)` early (before route registration). Added `RequestIdMiddleware` (generates UUID4, sets ContextVar, adds `X-Request-Id` header) and `AccessLogMiddleware` (INFO log per non-health request with event, method, path, status, duration_ms).
- `backend/app/core/config.py` — Added `log_level: str = "INFO"` field sourced from `LOG_LEVEL` env var.
- `backend/app/services/slack_dispatch.py` — Added R7 lifecycle events: `event.received` in `handle_slack_event`, `agent.built` + `response.sent` in both `_handle_app_mention` and `_handle_dm`, `event.error` replacing the bare `logger.error` in the outer exception handlers. Passed `_dispatch_start` monotonic timestamp through for `total_duration_ms`.
- `backend/pyproject.toml` — Added `python-json-logger>=2.0.0`.
- `backend/tests/test_logging_config.py` (NEW) — 16 unit tests covering JSON format keys, message/level values, request_id default and injection, Slack/OpenAI/Google/GitHub token redaction, masking strategy (short → `***`, long → `first6…last4`), LOG_LEVEL validation logic, and `setup_logging` idempotency.
- `backend/tests/test_access_log.py` (NEW) — 5 integration tests via `TestClient`: X-Request-Id header present, UUID4 format, uniqueness per request, access log emitted for non-health endpoints, health endpoint excluded.

## Logic Summary

The core module uses Python's stdlib `logging` with `python-json-logger` as the formatter. `setup_logging()` is idempotent (returns early if root logger already has handlers) so it is safe to call from module scope in `main.py`. The root logger is set to `DEBUG` and handlers control their own levels — this is the canonical Python dual-level pattern.

`RedactingFilter` modifies `record.msg` and `record.args` in-place before the formatter runs, so redaction applies to the final formatted string. The filter is only applied to the console handler; the file handler intentionally omits it. `RequestIdFilter` reads from `request_id_ctx` (a `contextvars.ContextVar`) and defaults to `"–"` (en-dash) for non-request contexts like background Slack dispatch tasks.

The middleware stack order matters: `RequestIdMiddleware` must execute before `AccessLogMiddleware` so the ContextVar is populated when the access log is written. Starlette adds middleware in reverse registration order (LIFO), so `AccessLogMiddleware` is registered first and `RequestIdMiddleware` second — this ensures `RequestIdMiddleware` wraps the outer call and sets the context before `AccessLogMiddleware` reads it.

## Correction Tax

- Self-assessed: 5%
- Human interventions needed:
  - None. The worktree `.env` was not present (known sprint-context rule: "copy .env to worktree root") — handled proactively without bouncing.
  - The `python-json-logger` package changed its module path in v3.x (`pythonjsonlogger.jsonlogger` → `pythonjsonlogger.json`) causing a DeprecationWarning. Fixed with a dual-import try/except pattern.

## Flashcards Flagged

1. **python-json-logger v3.x module rename**: `pythonjsonlogger.jsonlogger` is deprecated in favor of `pythonjsonlogger.json`. Any future story importing from this package must use the dual-import pattern: `try: from pythonjsonlogger.json import JsonFormatter except ImportError: from pythonjsonlogger.jsonlogger import JsonFormatter`.

2. **Starlette BaseHTTPMiddleware registration is LIFO**: When registering two middlewares where A must run before B in request order, register B first then A (`app.add_middleware(B); app.add_middleware(A)`). Applied here: `AccessLogMiddleware` is registered before `RequestIdMiddleware` so that `RequestIdMiddleware` (which sets the ContextVar) wraps the outside of `AccessLogMiddleware` (which reads the ContextVar).

## Product Docs Affected

- None. This story adds new infrastructure (logging) without changing any existing user-visible API behavior. The `X-Request-Id` response header is additive.

## Pre-existing Test Failures (not caused by this story)

The following 15 tests were failing before this implementation and remain failing after it. Confirmed via `git stash` comparison:

- `test_slack_dispatch.py`: `test_app_mention_bound_channel_happy_path`, `test_dm_happy_path`, `test_mention_prefix_stripped_before_agent` — fail due to `AsyncMock` stream iterator issue in `_stream_agent_to_slack` (pre-existing mock setup problem)
- `test_channel_binding.py::test_list_channel_bindings_returns_200_with_list`
- `test_health_db.py::test_health_reports_all_six_teemo_tables`
- `test_config_google.py::TestGooglePickerApiKey::test_defaults_to_empty_string_when_not_set`
- `test_drive_oauth.py` (3 tests)
- `test_knowledge_routes.py::TestConcurrentIndexingSerialized::test_two_sequential_posts_both_succeed`
- `test_slack_oauth_callback.py::test_reinstall_different_owner_returns_409`
- `test_slack_teams_list.py` (3 tests)

## Status

- [x] Code compiles without errors
- [x] Automated tests were written and pass (21/21 new tests pass)
- [x] FLASHCARDS.md was read before implementation
- [x] ADRs from Roadmap §3 were followed (ADR-002: only key_fingerprint() in logs, never raw keys)
- [x] Code is self-documenting (JSDoc/docstrings on all exports and middleware classes)
- [x] No new patterns or libraries introduced beyond `python-json-logger` (approved in story spec §3)
- [x] Token tracking completed (count_tokens.mjs --self ran successfully)

## Process Feedback

- The worktree `.env` lesson is in FLASHCARDS.md S-11 sprint context but easy to forget since the error only appears at test runtime, not import time. A `conftest.py` that asserts `.env` existence at test collection time would make this fail-fast.
- The `python-json-logger` v3 module rename was not documented in the story spec — required a small discovery loop. Worth adding to FLASHCARDS.md.
