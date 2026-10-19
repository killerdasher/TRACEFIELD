"""Structured JSONL logging with redaction.

Operational log, separate from the hash-chained ``analysis_events`` chain:
commands run, failures, and unhandled errors are written as one JSON object
per line under ``<data_root>/logs/tracefield.jsonl`` so a deployment can ship
them elsewhere. Every string that reaches disk is passed through
``redact_secrets`` (no tokens/keys/passwords in logs) and
``sanitize_for_terminal`` (no ANSI/OSC escapes that could forge log lines in
a terminal), and every value is length-capped.

Evidence *content* is never passed to this logger — only command lines,
IDs, and error messages. The logger is silent (NullHandler) until
``setup_logging`` attaches a file handler, so importing the package or
running tests without a configured home never writes anywhere.
"""

from __future__ import annotations

import contextlib
import json
import logging
import logging.handlers
import os
import traceback
from datetime import UTC, datetime
from pathlib import Path

from tracefield.security.redact import redact_secrets
from tracefield.security.sanitize import sanitize_for_terminal

LOGGER_NAME = "tracefield"
LOG_DIRNAME = "logs"
LOG_FILENAME = "tracefield.jsonl"
MAX_FIELD = 2000
MAX_LINE = 8000

_RESERVED = frozenset(
    {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "taskName",
        "message",
        "asctime",
    }
)


def _clean(value: object, *, keep_tail: bool = False) -> object:
    """Redact + sanitize + cap anything that is about to hit the log.

    ``keep_tail`` truncates from the front instead of the back — used for
    tracebacks, where the actual exception type/message is the last line.
    """
    if isinstance(value, str):
        text = redact_secrets(value)
        text = sanitize_for_terminal(text)
        if keep_tail and len(text) > MAX_FIELD:
            return "…" + text[-MAX_FIELD:]
        return text[:MAX_FIELD]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    try:
        text = json.dumps(value, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        text = str(value)
    return _clean(text, keep_tail=keep_tail)


class _PrivateFileHandler(logging.handlers.RotatingFileHandler):
    """RotatingFileHandler that forces 0600 on every (re)open."""

    def _open(self):  # type: ignore[no-untyped-def]
        stream = super()._open()
        with contextlib.suppress(OSError):  # platform-dependent
            os.chmod(self.baseFilename, 0o600)
        return stream


class JsonlFormatter(logging.Formatter):
    """One JSON object per line; strings redacted, sanitized, and capped."""

    def format(self, record: logging.LogRecord) -> str:
        try:
            message = record.getMessage()
        except Exception:  # pragma: no cover — defensive against % typos
            message = str(record.msg)
        payload: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "event": getattr(record, "event", "") or record.funcName,
            "msg": _clean(message),
        }
        for key, value in record.__dict__.items():
            if key in _RESERVED or key.startswith("_") or key == "event":
                continue
            payload[key] = _clean(value)
        if record.exc_info:
            text = "".join(traceback.format_exception(*record.exc_info))
            payload["exc"] = _clean(text, keep_tail=True)
        line = json.dumps(payload, ensure_ascii=False, default=str)
        if len(line) <= MAX_LINE:
            return line
        # Oversized: shrink in priority order — never slice JSON mid-string.
        payload.pop("exc", None)
        line = json.dumps(payload, ensure_ascii=False, default=str)
        if len(line) <= MAX_LINE:
            return line
        for key in list(payload):
            if key not in ("ts", "level", "logger", "event", "msg"):
                payload.pop(key)
        payload["msg"] = str(payload.get("msg", ""))[-2000:]
        payload["truncated"] = True
        return json.dumps(payload, ensure_ascii=False, default=str)


def get_logger(suffix: str = "app") -> logging.Logger:
    """Logger under the ``tracefield`` namespace (silent until configured)."""
    return logging.getLogger(f"{LOGGER_NAME}.{suffix}")


def _root() -> logging.Logger:
    return logging.getLogger(LOGGER_NAME)


def setup_logging(data_root: Path, *, level: str | None = None) -> Path:
    """Attach (or rebind) the JSONL file handler under ``data_root/logs``.

    Idempotent and rebinding: calling again with a different data root moves
    the handler, so tests and repeated CLI invocations never stack handlers.
    Never raises — an unwritable log directory simply disables file logging.
    """
    root = _root()
    if not any(isinstance(h, logging.NullHandler) for h in root.handlers):
        root.addHandler(logging.NullHandler())
    root.propagate = False

    log_dir = data_root / LOG_DIRNAME
    path = log_dir / LOG_FILENAME
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(log_dir, 0o700)
    except OSError:
        return path

    wanted = level or os.environ.get("TRACEFIELD_LOG_LEVEL", "INFO")
    numeric = getattr(logging, wanted.upper(), logging.INFO)

    for handler in list(root.handlers):
        if isinstance(handler, logging.NullHandler):
            continue
        if getattr(handler, "_tracefield_path", None) == path:
            root.setLevel(numeric)
            return path
        root.removeHandler(handler)
        handler.close()

    try:
        handler = _PrivateFileHandler(
            path, maxBytes=5_000_000, backupCount=1, delay=True, encoding="utf-8"
        )
    except OSError:
        return path
    handler.setFormatter(JsonlFormatter())
    handler._tracefield_path = path  # type: ignore[attr-defined]
    root.addHandler(handler)
    root.setLevel(numeric)
    return path
