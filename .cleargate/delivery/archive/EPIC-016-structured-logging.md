---
epic_id: "EPIC-016"
status: "Shipped"
ambiguity: "🟢"
context_source: "PROPOSAL-001-teemo-platform.md"
owner: "Team Lead"
target_date: "TBD"
approved: true
created_at: "2026-04-13T00:00:00Z"
updated_at: "2026-04-13T00:00:00Z"
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

> **Ported from V-Bounce (shipped).** Original: `product_plans.vbounce-archive/archive/epics/EPIC-016_structured_logging/EPIC-016_structured_logging.md`. Shipped in sprint S-11, carried forward during ClearGate migration 2026-04-24.

# EPIC-016: Structured Logging & Observability

## 1. Problem & Value

Tee-Mo's backend has 12 files with `logging.getLogger(__name__)` but no centralized configuration, no structured output, and no log file persistence. When production errors occur (e.g., the channel bind 500, the "Something went wrong" agent crash), debugging requires SSH access and guesswork. Coolify captures container stdout but the logs are unstructured plain text with Python's default WARNING level — most operational events are invisible.

**Value:** Structured JSON logs with lifecycle events, request correlation, and sensitive data redaction. Modeled after OpenClaw's dual-surface architecture adapted for Python/FastAPI on Coolify.

## 2. Scope Boundaries

**In scope:**
- Centralized logging configuration (JSON formatter, file + console handlers, independent levels)
- Sensitive data redaction on console output (Slack tokens, API keys, refresh tokens, encryption keys)
- Lifecycle diagnostic events for Slack dispatch (event received, agent built, tool called, response sent)
- Request correlation (request ID propagation through middleware)
- FastAPI access log middleware (method, path, status, duration)
- LOG_LEVEL environment variable (default: INFO)

**Out of scope:**
- OpenTelemetry / OTLP export (future EPIC)
- Frontend logging
- Log aggregation service (Coolify container logs are sufficient for now)
- Alerting or dashboards
- Performance metrics / histograms

## 3. Success Criteria

- Every backend log line is valid JSON with `timestamp`, `level`, `logger`, `message`, and `request_id` fields
- Sensitive patterns (xoxb-, sk-, API keys, refresh tokens) are redacted in console output
- Slack dispatch lifecycle is fully traceable from event receipt to response post
- LOG_LEVEL env var controls verbosity; file logs always capture DEBUG
- Zero secrets leaked in any log surface (extends ADR-002)

## 4. Technical Context

**Current state:** 12 files use `logging.getLogger(__name__)` with no config. Python default level is WARNING. Output is unformatted stdout only.

**Target state:** `app/core/logging_config.py` configures root logger on startup with two handlers — JSON file (rotating daily, DEBUG level) and redacting console (configurable level, default INFO). Middleware injects `request_id` into log context.

**Affected areas:**
- `app/main.py` — startup logging config, middleware registration
- `app/core/` — new `logging_config.py` module
- `app/services/slack_dispatch.py` — lifecycle events
- `app/agents/agent.py` — tool call logging
- All 12 files with existing loggers — format unchanged (stdlib compatible)

**Dependencies:** None. stdlib `logging` + `python-json-logger` (one new dependency).

## 5. Decomposition

| Story | Title | Complexity | Depends On |
|-------|-------|------------|------------|
| STORY-016-01 | Structured logging config with JSON output & redaction | L2 | — |

## 6. Risks & Edge Cases

| Risk | Mitigation |
|------|------------|
| Log file fills disk on VPS | Daily rotation + max 7 day retention + 100MB cap per file |
| Redaction misses a new secret pattern | Redaction filter is pattern-based and extensible; add patterns as new integrations land |
| Performance impact of JSON serialization | stdlib JSON formatter is negligible; file writes are append-only |
| Existing logger calls break | Zero changes to call sites — formatter handles everything at handler level |

## 7. Acceptance Criteria

```gherkin
Feature: Structured Logging

  Scenario: JSON log output
    Given the backend is running with LOG_LEVEL=INFO
    When any log event fires
    Then stdout contains a valid JSON line with timestamp, level, logger, message fields

  Scenario: Sensitive data redacted
    Given a log message contains "xoxb-fake-token-123"
    When it is written to console
    Then the token appears as "xoxb-***...n-123"

  Scenario: Request correlation
    Given a client sends an HTTP request
    When the request is processed
    Then all log lines for that request share the same request_id

  Scenario: Slack lifecycle tracing
    Given a Slack app_mention event arrives
    Then log lines are emitted for: event.received, agent.built, tool.called, response.sent
```

## 8. Open Questions

*None — scope is well-defined and all technical decisions are straightforward.*

## 9. Artifact Links

| Artifact | Path | Status |
|----------|------|--------|
| STORY-016-01 | `STORY-016-01-structured-logging.md` | Draft |

---

## Change Log

| Date | Author | Change |
|------|--------|--------|
| 2026-04-13 | Claude (doc-manager) | Initial draft. Modeled after OpenClaw logging architecture, adapted for Python/FastAPI/Coolify stack. |
