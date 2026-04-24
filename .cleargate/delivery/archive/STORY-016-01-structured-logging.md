---
story_id: "STORY-016-01-structured-logging"
parent_epic_ref: "EPIC-016"
status: "Shipped"
ambiguity: "🟢"
context_source: "PROPOSAL-001-teemo-platform.md"
complexity_label: "L2"
parallel_eligible: false
expected_bounce_exposure: "low"
approved: true
created_at: "2026-04-10T00:00:00Z"
updated_at: "2026-04-14T00:00:00Z"
created_at_version: "vbounce-backlog"
updated_at_version: "cleargate-migration-2026-04-24"
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
> **Ported from V-Bounce (shipped).** Original: `product_plans.vbounce-archive/archive/sprints/sprint-11/STORY-016-01-structured-logging.md`. Shipped in sprint S-11, carried forward during ClearGate migration 2026-04-24.

# STORY-016-01: Structured Logging with JSON Output, Redaction & Lifecycle Events

**Complexity: L2** — 3-4 new files, known patterns (stdlib logging), ~4hr

---

## 1. The Spec (The Contract)

### 1.1 User Story
> This story adds centralized structured logging to the Tee-Mo backend because production debugging is currently impossible — logs are unformatted, default WARNING level hides operational events, and there is no way to correlate log lines to a specific Slack event or HTTP request.

### 1.2 Detailed Requirements

- **R1 — Centralized config**: A single `app/core/logging_config.py` module configures the root logger on app startup. All 12 existing files using `logging.getLogger(__name__)` continue working with zero call-site changes.
- **R2 — Dual-surface output** (inspired by OpenClaw):
  - **Console (stdout)**: JSON Lines format. Level controlled by `LOG_LEVEL` env var (default: `INFO`). Sensitive data redacted.
  - **File**: JSON Lines format. Always `DEBUG` level. Daily rotation, 7-day retention, 100MB max per file. Written to `/tmp/teemo/teemo-YYYY-MM-DD.log`. Sensitive data NOT redacted (for secure production debugging).
- **R3 — Structured fields**: Every log line includes: `timestamp` (ISO 8601), `level`, `logger` (module name), `message`, `request_id` (from middleware, or `"–"` for non-request contexts like Slack dispatch background tasks).
- **R4 — Request correlation middleware**: FastAPI middleware generates a UUID `request_id` per request, stores it in a `contextvars.ContextVar`, and injects it into every log line via a custom filter. The response includes an `X-Request-Id` header.
- **R5 — Sensitive data redaction** (console only): A `RedactingFilter` masks patterns matching:
  - Slack bot tokens (`xoxb-`, `xoxp-`, `xapp-`)
  - OpenAI keys (`sk-`)
  - Google API keys (`AIza`)
  - GitHub tokens (`ghp_`, `github_pat_`)
  - Generic patterns: any JSON field named `token`, `secret`, `api_key`, `password`, `refresh_token`, `encrypted_*`
  - Masking strategy: tokens < 18 chars → `***`; longer → first 6 + `…` + last 4
- **R6 — FastAPI access log**: Middleware logs each completed request at INFO level: `{"event": "http.request", "method": "GET", "path": "/api/health", "status": 200, "duration_ms": 12, "request_id": "..."}`.
- **R7 — Slack dispatch lifecycle events**: Add structured log calls at key points in `slack_dispatch.py`:
  - `event.received` — event type, channel, team
  - `agent.built` — workspace_id, provider, model_id, duration_ms
  - `tool.called` — tool name, drive_file_id (if applicable), duration_ms
  - `response.sent` — channel, thread_ts, text length, total_duration_ms
  - `event.error` — error type, message (already exists but upgrade to structured format)
- **R8 — LOG_LEVEL env var**: Accepts standard Python level names (`DEBUG`, `INFO`, `WARNING`, `ERROR`). Validated at startup. Invalid values fall back to `INFO` with a warning.
- **R9 — Startup banner**: On startup, log at INFO: configured log level, file log path, redaction status, app version (if available).

### 1.3 Out of Scope
- OpenTelemetry / tracing spans — deferred to future EPIC
- Log aggregation or shipping to external services
- Frontend logging
- Changing existing `logger.info(...)` / `logger.error(...)` call sites (they work as-is)
- Agent tool-level metrics (token counts, cost) — that's a separate observability story

### TDD Red Phase: No
> Configuration + middleware story. Validated via integration-style tests checking log output format, not Gherkin-driven behavior.

---

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria (Gherkin/Pseudocode)
```gherkin
Feature: Structured Logging

  Scenario: Console output is JSON with required fields
    Given the logging system is configured with LOG_LEVEL=INFO
    When logger.info("test message") is called
    Then stdout contains a JSON line with keys: timestamp, level, logger, message, request_id

  Scenario: File output captures DEBUG even when console is INFO
    Given LOG_LEVEL=INFO
    When logger.debug("only in file") is called
    Then the file log contains the message
    And console output does NOT contain the message

  Scenario: Slack token is redacted in console output
    Given a log message contains "xoxb-1234567890-abcdefghij"
    When it is formatted for console
    Then the output contains "xoxb-1***…ghij" (or equivalent masked form)
    And the file log contains the original unredacted token

  Scenario: Request ID propagation
    Given a FastAPI request is in progress
    When any logger call is made during that request
    Then the log line includes the same request_id UUID
    And the HTTP response contains X-Request-Id header with that UUID

  Scenario: Access log emitted for each request
    Given a client sends GET /api/health
    When the request completes with 200
    Then an INFO log line is emitted with event=http.request, method=GET, path=/api/health, status=200, duration_ms

  Scenario: Slack dispatch lifecycle events
    Given a Slack app_mention event is received
    When the dispatch handler processes it through to response
    Then log lines are emitted for event.received, agent.built, tool.called (if applicable), response.sent

  Scenario: Invalid LOG_LEVEL falls back to INFO
    Given LOG_LEVEL=BANANA
    When the app starts
    Then a warning is logged about invalid level
    And the effective level is INFO
```

### 2.2 Verification Steps (Manual)
- [ ] Start backend with `LOG_LEVEL=DEBUG` — verify console shows debug messages in JSON format
- [ ] Start backend with `LOG_LEVEL=INFO` — verify debug messages appear in file but not console
- [ ] Trigger a Slack @mention — verify lifecycle events appear in logs with matching request context
- [ ] Check `/tmp/teemo/teemo-YYYY-MM-DD.log` exists and contains JSON lines
- [ ] Grep log file for any raw `xoxb-` tokens — should only appear in file logs, never console
- [ ] Verify `X-Request-Id` header in HTTP responses

---

## 3. The Implementation Guide (AI-to-AI)

### 3.0 Environment Prerequisites

| Prerequisite | Value | Verified? |
|-------------|-------|-----------|
| **Env Vars** | `LOG_LEVEL` (optional, default INFO) | [ ] |
| **Services Running** | Backend via `uvicorn app.main:app --reload` | [ ] |
| **Dependencies** | `pip install python-json-logger` (new) | [ ] |

### 3.1 Test Implementation
- Create `backend/tests/test_logging_config.py`:
  - Test JSON output format (capture log output, parse as JSON, assert keys)
  - Test redaction filter (pass known token patterns, assert masked)
  - Test request_id injection via ContextVar
  - Test LOG_LEVEL env var parsing (valid levels + invalid fallback)
- Create `backend/tests/test_access_log.py`:
  - Test access log middleware emits correct fields via TestClient

### 3.2 Context & Files
| Item | Value |
|------|-------|
| **Primary File** | `backend/app/core/logging_config.py` (NEW) |
| **Related Files** | `backend/app/main.py` (startup hook + middleware), `backend/app/services/slack_dispatch.py` (lifecycle events), `backend/app/core/config.py` (LOG_LEVEL setting) |
| **New Files Needed** | Yes — `app/core/logging_config.py`, `tests/test_logging_config.py`, `tests/test_access_log.py` |
| **ADR References** | ADR-002 (encryption — never log plaintext keys, only `key_fingerprint()`) |
| **First-Use Pattern** | Yes — `python-json-logger` and `contextvars` for request correlation |

### 3.3 Technical Logic

**`app/core/logging_config.py`** — the core module:

1. **`setup_logging(log_level: str = "INFO")`** — called once from `app/main.py` on startup:
   - Parse and validate `log_level` (fall back to INFO on invalid)
   - Create root logger, set to DEBUG (handlers control their own levels)
   - **Console handler** (`logging.StreamHandler(sys.stdout)`):
     - Formatter: `pythonjsonlogger.jsonlogger.JsonFormatter` with `timestamp`, `level`, `name`, `message`, `request_id`
     - Filter: `RedactingFilter` (console only)
     - Level: from `log_level` parameter
   - **File handler** (`logging.handlers.TimedRotatingFileHandler`):
     - Path: `/tmp/teemo/teemo.log`, `when="midnight"`, `backupCount=7`
     - Formatter: same `JsonFormatter` (no redaction)
     - Level: `DEBUG` always
     - Create `/tmp/teemo/` directory on startup if missing
   - Suppress noisy third-party loggers: set `httpx`, `httpcore`, `slack_sdk`, `googleapiclient`, `urllib3` to WARNING

2. **`RequestIdFilter(logging.Filter)`**:
   - Reads from `contextvars.ContextVar[str]` named `_request_id_var`
   - Adds `request_id` field to every log record
   - Default value: `"–"` (for background tasks / non-request contexts)

3. **`RedactingFilter(logging.Filter)`**:
   - Runs AFTER formatting, on the `msg` string
   - Pattern list: compiled regexes for Slack, OpenAI, Google, GitHub, and generic secret field names
   - Masking: short tokens → `***`; long tokens → first 6 + `…` + last 4

4. **`request_id_ctx`** — the `ContextVar[str]` exported for middleware use

**`app/main.py`** — wiring:

1. Import `setup_logging` and call it early in module scope (before route registration)
2. Add `RequestIdMiddleware`:
   - `@app.middleware("http")` or `BaseHTTPMiddleware`
   - Generate UUID4, set `request_id_ctx`, add `X-Request-Id` response header
3. Add `AccessLogMiddleware`:
   - Log at INFO after response: `event=http.request`, method, path, status, duration_ms, request_id
   - Skip `/api/health` to avoid noise

**`app/core/config.py`** — add `log_level: str = "INFO"` to Settings model, sourced from `LOG_LEVEL` env var.

**`app/services/slack_dispatch.py`** — lifecycle events:

Replace ad-hoc `logger.info/error` calls with structured events using `extra={}` dict:
```python
logger.info("event.received", extra={"event_type": event_type, "channel": channel, "team": team})
logger.info("agent.built", extra={"workspace_id": workspace_id, "provider": provider, "duration_ms": dur})
logger.info("tool.called", extra={"tool": "read_drive_file", "drive_file_id": fid, "duration_ms": dur})
logger.info("response.sent", extra={"channel": channel, "text_length": len(text), "total_duration_ms": dur})
```

The `JsonFormatter` automatically includes `extra` fields in the JSON output — no special handling needed.

### 3.4 API Contract

No new API endpoints. One new response header:

| Header | Value | Notes |
|--------|-------|-------|
| `X-Request-Id` | UUID4 string | Added to every HTTP response by middleware |

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations

| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Unit tests | 6 | JSON format, redaction patterns (x4 token types), LOG_LEVEL fallback, request_id injection |
| Integration tests | 2 | Access log middleware via TestClient, X-Request-Id header presence |

### 4.2 Definition of Done (The Gate)
- [ ] `setup_logging()` called on startup; all backend log output is JSON
- [ ] `LOG_LEVEL` env var controls console verbosity
- [ ] File logs written to `/tmp/teemo/teemo.log` with daily rotation
- [ ] Sensitive tokens redacted in console, preserved in file
- [ ] `X-Request-Id` header in all HTTP responses
- [ ] Slack dispatch has structured lifecycle events (event.received through response.sent)
- [ ] No raw `xoxb-`, `sk-`, `AIza` tokens visible in console output
- [ ] Minimum test expectations met
- [ ] `python-json-logger` added to `pyproject.toml` dependencies
- [ ] FLASHCARDS.md updated with logging patterns for future stories

---

## Change Log

| Date | Author | Change |
|------|--------|--------|
| 2026-04-13 | Claude (doc-manager) | Initial draft. Architecture modeled after OpenClaw dual-surface logging (JSON file + redacting console), adapted for Python stdlib logging + python-json-logger on Coolify. |
