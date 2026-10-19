"""Unit tests: structured JSONL logging formatter — redaction, terminal
sanitization, field capping, and JSON validity. No file I/O beyond tmp logs.
"""

from __future__ import annotations

import json
import logging
import stat

import pytest

pytestmark = pytest.mark.unit


def _format(msg: str, level: int = logging.INFO, **fields) -> dict:
    from tracefield.config.logging import JsonlFormatter

    rec = logging.LogRecord(
        name="tracefield.test",
        level=level,
        pathname=__file__,
        lineno=7,
        msg=msg,
        args=(),
        exc_info=None,
    )
    for k, v in fields.items():
        setattr(rec, k, v)
    line = JsonlFormatter().format(rec)
    assert "\n" not in line, "log lines must be single-line JSON"
    return json.loads(line)


class TestJsonlFormatter:
    def test_basic_fields(self) -> None:
        payload = _format("hello", event="command")
        assert payload["msg"] == "hello"
        assert payload["event"] == "command"
        assert payload["level"] == "INFO"
        assert payload["ts"].endswith("Z")
        assert payload["logger"] == "tracefield.test"

    def test_secrets_redacted(self) -> None:
        payload = _format(
            "connecting with token=ghp_abcdef1234567890abcdef1234567890abcd",
            event="probe",
        )
        assert "ghp_abcdef" not in payload["msg"]
        assert "[REDACTED]" in payload["msg"]

    def test_extra_fields_redacted_and_capped(self) -> None:
        from tracefield.config.logging import MAX_FIELD

        payload = _format(
            "x",
            event="fields",
            locator="https://example.test/?api_key=SUPERSECRETVALUE",
            huge="y" * (MAX_FIELD + 100),
        )
        assert "SUPERSECRETVALUE" not in payload["locator"]
        assert len(payload["huge"]) <= MAX_FIELD

    def test_ansi_escapes_stripped(self) -> None:
        payload = _format("before \x1b[2J after", event="ansi")
        assert "\x1b" not in payload["msg"]

    def test_non_string_fields_survive(self) -> None:
        payload = _format("n", event="types", exit_code=3, ratio=0.5, ok=True, none=None)
        assert payload["exit_code"] == 3
        assert payload["ratio"] == 0.5
        assert payload["ok"] is True
        assert payload["none"] is None

    def test_exception_included(self) -> None:
        from tracefield.config.logging import JsonlFormatter

        rec = logging.LogRecord(
            name="tracefield.test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="boom",
            args=(),
            exc_info=None,
        )
        try:
            raise ValueError("inner-secret" if False else "kaboom")
        except ValueError:
            import sys

            rec.exc_info = sys.exc_info()
        payload = json.loads(JsonlFormatter().format(rec))
        assert "ValueError" in payload["exc"]
        assert "kaboom" in payload["exc"]


class TestSetupLogging:
    def test_writes_and_permissions(self, tf_home, tmp_path) -> None:
        from tracefield.config.logging import get_logger, setup_logging

        log_path = setup_logging(tf_home)
        assert log_path == tf_home / "logs" / "tracefield.jsonl"
        get_logger("test").info("unit event", extra={"event": "unit"})
        # force flush
        for h in get_logger("test").handlers or []:
            h.flush()
        import logging as _logging

        for h in _logging.getLogger("tracefield").handlers:
            h.flush()
        lines = log_path.read_text(encoding="utf-8").splitlines()
        assert lines, "log file must contain the emitted record"
        parsed = json.loads(lines[-1])
        assert parsed["event"] == "unit"
        assert parsed["msg"] == "unit event"
        mode = stat.S_IMODE(log_path.stat().st_mode)
        assert mode == 0o600, oct(mode)

    def test_rebinds_on_new_home(self, tf_home) -> None:
        from tracefield.config.logging import setup_logging

        first = setup_logging(tf_home)
        second_root = tf_home / "other-home"
        second = setup_logging(second_root)
        assert first != second
        assert second.parent.exists()
        # exactly one file handler after rebinding
        import logging as _logging

        handlers = [
            h
            for h in _logging.getLogger("tracefield").handlers
            if not isinstance(h, _logging.NullHandler)
        ]
        assert len(handlers) == 1
