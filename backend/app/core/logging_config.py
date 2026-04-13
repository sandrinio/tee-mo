"""
Centralized structured logging configuration for the Tee-Mo backend.

This module configures the root logger once on application startup. All
existing files that call ``logging.getLogger(__name__)`` continue working
without any call-site changes — they inherit the root logger's handlers.

Design:
  - Console (stdout): JSON Lines via python-json-logger, sensitive data redacted,
    level controlled by ``LOG_LEVEL`` env var.
  - File (/tmp/teemo/teemo.log): JSON Lines, always DEBUG, daily rotation with
    7-day retention, NO redaction (for secure production debugging).
  - ``RequestIdFilter``: injects ``request_id`` from a ``contextvars.ContextVar``
    into every log record so log lines can be correlated to HTTP requests.
  - ``RedactingFilter``: masks Slack tokens, OpenAI keys, Google API keys, GitHub
    tokens, and generic secret field names in the console output.

Usage::

    from app.core.logging_config import setup_logging, request_id_ctx
    setup_logging(log_level="INFO")

STORY-016-01 — ADR-002: NEVER log plaintext keys; only key_fingerprint() from
encryption.py is permitted in log output for encryption-related events.
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import re
import sys
from contextvars import ContextVar
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Request-ID context variable
# ---------------------------------------------------------------------------

#: ContextVar that FastAPI middleware writes once per request.
#: All log records read this to include ``request_id`` in JSON output.
request_id_ctx: ContextVar[Optional[str]] = ContextVar("_request_id_var", default=None)


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------


class RequestIdFilter(logging.Filter):
    """Logging filter that injects the current request ID into every log record.

    Reads from ``request_id_ctx`` (a ``contextvars.ContextVar``). Falls back to
    ``"–"`` (en-dash) when no request is in flight, e.g. during Slack dispatch
    background tasks or startup logging.

    Applied to ALL handlers so that every log line (console and file) includes
    ``request_id``.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Add ``request_id`` attribute to the log record.

        Parameters
        ----------
        record:
            The log record to augment.

        Returns
        -------
        bool
            Always ``True`` — this filter never drops records.
        """
        record.request_id = request_id_ctx.get() or "–"
        return True


class RedactingFilter(logging.Filter):
    """Logging filter that masks sensitive credentials in log output.

    Applied to the **console handler only**. The file handler intentionally
    does NOT use this filter so that full tokens are available for secure
    production debugging.

    Masked patterns:
    - Slack tokens: ``xoxb-``, ``xoxp-``, ``xapp-`` prefixes
    - OpenAI keys: ``sk-`` prefix
    - Google API keys: ``AIza`` prefix
    - GitHub tokens: ``ghp_``, ``github_pat_`` prefixes
    - Generic JSON fields: ``token``, ``secret``, ``api_key``, ``password``,
      ``refresh_token``, ``encrypted_*`` (field name + value pairs)

    Masking strategy:
    - Token value < 18 characters → ``***``
    - Token value >= 18 characters → first 6 chars + ``…`` + last 4 chars
    """

    # Pre-compiled regex patterns for each sensitive token type.
    # Each pattern captures the full token value in group 1.
    _TOKEN_PATTERNS: list[re.Pattern[str]] = [
        # Slack bot/user/app tokens
        re.compile(r"(xoxb-[A-Za-z0-9\-]+)"),
        re.compile(r"(xoxp-[A-Za-z0-9\-]+)"),
        re.compile(r"(xapp-[A-Za-z0-9\-]+)"),
        # OpenAI API keys (sk- followed by at least one char)
        re.compile(r"(sk-[A-Za-z0-9\-_]+)"),
        # Google API keys (AIza followed by alphanumeric)
        re.compile(r"(AIza[A-Za-z0-9\-_]+)"),
        # GitHub tokens
        re.compile(r"(ghp_[A-Za-z0-9]+)"),
        re.compile(r"(github_pat_[A-Za-z0-9_]+)"),
    ]

    # Generic field patterns: match "fieldname": "value" or fieldname=value
    # Covers: token, secret, api_key, password, refresh_token, encrypted_*
    _FIELD_PATTERNS: list[re.Pattern[str]] = [
        re.compile(
            r'("(?:token|secret|api_key|password|refresh_token|encrypted_[^"]*)"'
            r'\s*:\s*")([^"]{4,})(")',
            re.IGNORECASE,
        ),
        re.compile(
            r'((?:token|secret|api_key|password|refresh_token|encrypted_\w+)=)([^\s,&"]{4,})',
            re.IGNORECASE,
        ),
    ]

    @staticmethod
    def _mask(value: str) -> str:
        """Return masked version of ``value``.

        Parameters
        ----------
        value:
            The sensitive token or credential string to mask.

        Returns
        -------
        str
            ``"***"`` if ``len(value) < 18``, otherwise ``first6…last4``.
        """
        if len(value) < 18:
            return "***"
        return f"{value[:6]}…{value[-4:]}"

    def _redact(self, text: str) -> str:
        """Apply all redaction patterns to ``text`` and return the result.

        Parameters
        ----------
        text:
            The raw log message string to redact.

        Returns
        -------
        str
            The redacted message with sensitive values replaced.
        """
        # Replace bare token patterns first
        for pattern in self._TOKEN_PATTERNS:
            text = pattern.sub(lambda m: self._mask(m.group(1)), text)

        # Replace generic field value patterns
        for pattern in self._FIELD_PATTERNS:
            # Field patterns have a different group structure
            if pattern.groups == 3:
                # JSON-style: group1=prefix_quote, group2=value, group3=closing_quote
                text = pattern.sub(
                    lambda m: m.group(1) + self._mask(m.group(2)) + m.group(3),
                    text,
                )
            else:
                # key=value style: group1=key=, group2=value
                text = pattern.sub(
                    lambda m: m.group(1) + self._mask(m.group(2)),
                    text,
                )

        return text

    def filter(self, record: logging.LogRecord) -> bool:
        """Redact sensitive credentials from the log record's message.

        Modifies ``record.msg`` and ``record.getMessage()`` output in-place.
        Also redacts any string items in ``record.args`` if they exist.

        Parameters
        ----------
        record:
            The log record to redact.

        Returns
        -------
        bool
            Always ``True`` — this filter never drops records.
        """
        # Redact the formatted message
        if isinstance(record.msg, str):
            record.msg = self._redact(record.msg)

        # Redact args (these are % formatting substitutions)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: self._redact(v) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    self._redact(v) if isinstance(v, str) else v
                    for v in record.args
                )

        return True


# ---------------------------------------------------------------------------
# Setup function
# ---------------------------------------------------------------------------

#: Noisy third-party loggers suppressed to WARNING to reduce log volume.
_NOISY_LOGGERS = (
    "httpx",
    "httpcore",
    "slack_sdk",
    "googleapiclient",
    "urllib3",
)

#: Standard Python logging level names accepted by LOG_LEVEL env var.
_VALID_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}

#: Default path for the rotating log file.
_LOG_FILE_PATH = Path("/tmp/teemo/teemo.log")


def setup_logging(log_level: str = "INFO") -> None:
    """Configure the root logger with dual-surface JSON output.

    Sets up two handlers:
      1. **Console** (stdout): JSON Lines, level from ``log_level``, with
         ``RedactingFilter`` and ``RequestIdFilter`` applied.
      2. **File** (/tmp/teemo/teemo.log): JSON Lines, always ``DEBUG``, daily
         rotation (7-day retention), with ``RequestIdFilter`` only — no redaction.

    The root logger level is set to ``DEBUG`` so that both handlers receive all
    records; each handler's own level gates what it ultimately emits.

    Suppresses noisy third-party loggers (httpx, httpcore, slack_sdk,
    googleapiclient, urllib3) to ``WARNING``.

    Parameters
    ----------
    log_level:
        Desired console log level string. Accepts standard Python level names
        (``DEBUG``, ``INFO``, ``WARNING``, ``ERROR``). Invalid values fall back
        to ``INFO`` with a warning message printed to stderr.

    Notes
    -----
    Calling this function multiple times is safe — if the root logger already
    has handlers, the function returns immediately without adding duplicates.
    The recommended usage is a single call from ``app/main.py`` at startup.
    """
    # Idempotency guard: don't add handlers twice (e.g. in tests)
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return

    # Validate log level; fall back to INFO on invalid input
    normalized = log_level.upper()
    if normalized not in _VALID_LEVELS:
        # Can't use logger here yet — write directly to stderr
        print(
            f"[logging_config] WARNING: Invalid LOG_LEVEL={log_level!r}. "
            f"Falling back to INFO. Valid levels: {sorted(_VALID_LEVELS)}",
            file=sys.stderr,
        )
        normalized = "INFO"

    numeric_level = getattr(logging, normalized)

    # Root logger captures everything; handlers filter further
    root_logger.setLevel(logging.DEBUG)

    # Shared filters
    request_id_filter = RequestIdFilter()
    redacting_filter = RedactingFilter()

    # ------------------------------------------------------------------
    # JSON formatter (shared across both handlers)
    # ------------------------------------------------------------------
    try:
        # python-json-logger >= 3.x moved the module to pythonjsonlogger.json;
        # < 3.x used pythonjsonlogger.jsonlogger. Try the new location first.
        try:
            from pythonjsonlogger.json import JsonFormatter  # type: ignore[import]
        except ImportError:
            from pythonjsonlogger.jsonlogger import JsonFormatter  # type: ignore[import]

        fmt = JsonFormatter(
            fmt="%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
            rename_fields={"asctime": "timestamp", "levelname": "level", "name": "logger"},
        )
    except ImportError:
        # Graceful degradation: fall back to standard formatter if package missing
        fmt = logging.Formatter(  # type: ignore[assignment]
            fmt="%(asctime)s %(levelname)s %(name)s %(message)s [%(request_id)s]",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )

    # ------------------------------------------------------------------
    # Console handler
    # ------------------------------------------------------------------
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(fmt)
    console_handler.addFilter(request_id_filter)
    console_handler.addFilter(redacting_filter)
    root_logger.addHandler(console_handler)

    # ------------------------------------------------------------------
    # File handler (always DEBUG, no redaction)
    # ------------------------------------------------------------------
    try:
        _LOG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.TimedRotatingFileHandler(
            filename=str(_LOG_FILE_PATH),
            when="midnight",
            backupCount=7,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(fmt)
        file_handler.addFilter(request_id_filter)
        root_logger.addHandler(file_handler)
    except OSError as exc:
        # Non-fatal: if /tmp/teemo can't be created (e.g. read-only filesystem),
        # log to console only and warn.
        print(
            f"[logging_config] WARNING: Could not create log file at {_LOG_FILE_PATH}: {exc}",
            file=sys.stderr,
        )

    # ------------------------------------------------------------------
    # Suppress noisy third-party loggers
    # ------------------------------------------------------------------
    for logger_name in _NOISY_LOGGERS:
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    # ------------------------------------------------------------------
    # Startup banner
    # ------------------------------------------------------------------
    startup_logger = logging.getLogger(__name__)
    startup_logger.info(
        "Logging initialized",
        extra={
            "log_level": normalized,
            "file_log_path": str(_LOG_FILE_PATH),
            "redaction_enabled": True,
            "file_redaction_enabled": False,
        },
    )
