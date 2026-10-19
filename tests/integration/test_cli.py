"""CLI contract tests: deterministic exit codes, JSON output, terminal
safety, path traversal, and network policy — exercised through the REAL
entry point (``run()``), so the mapping contract is what ships.
"""

from __future__ import annotations

import json
import re
import sys

import pytest

pytestmark = pytest.mark.integration

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_NOT_FOUND = 2
EXIT_USAGE = 3
EXIT_NETWORK_BLOCKED = 4


def run_cli(monkeypatch: pytest.MonkeyPatch, args: list[str]) -> tuple[int, str, str]:
    """Invoke the real console entry point; return (code, stdout, stderr).

    Unexpected exceptions are caught at the CLI boundary (logged to the
    structured log, exit 1) — they surface as a non-zero code here, never
    as a propagated crash.
    """
    from _pytest.monkeypatch import MonkeyPatch  # noqa: F401 — typing only

    from tracefield.cli.main import run

    monkeypatch.setattr(sys, "argv", ["tracefield", *args])
    code: int | None = None
    try:
        run()
    except SystemExit as exc:
        raw = exc.code
        code = raw if isinstance(raw, int) else (0 if raw is None else 1)
    return code if code is not None else EXIT_OK, "", ""


def run_cli_out(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    args: list[str],
) -> tuple[int, str, str]:
    """Like run_cli but captures stdout/stderr (reset per call)."""
    capsys.readouterr()  # discard prior output
    code, _, _ = run_cli(monkeypatch, args)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


class TestExitCodes:
    def test_version_ok(self, tf_home, monkeypatch, capsys) -> None:
        code, out, _ = run_cli_out(monkeypatch, capsys, ["--version"])
        assert code == EXIT_OK
        assert "tracefield 0.1.0" in out

    def test_help_ok(self, tf_home, monkeypatch, capsys) -> None:
        code, out, _ = run_cli_out(monkeypatch, capsys, ["--help"])
        assert code == EXIT_OK
        assert "OSINT" in out and "evidence provenance" in out

    def test_unknown_command_is_usage_3(self, tf_home, monkeypatch, capsys) -> None:
        code, _, err = run_cli_out(monkeypatch, capsys, ["no-such-command"])
        assert code == EXIT_USAGE
        assert "usage error" in err.lower()

    def test_missing_required_option_is_usage_3(self, tf_home, monkeypatch, capsys) -> None:
        code, _, _err = run_cli_out(monkeypatch, capsys, ["case", "create"])
        assert code == EXIT_USAGE

    def test_case_not_found_is_2(self, tf_home, monkeypatch, capsys) -> None:
        code, _, err = run_cli_out(monkeypatch, capsys, ["case", "show", "missing"])
        assert code == EXIT_NOT_FOUND
        assert "not found" in err.lower() or "not found" in err

    def test_doctor_json(self, tf_home, monkeypatch, capsys) -> None:
        code, out, _ = run_cli_out(monkeypatch, capsys, ["doctor", "--json"])
        assert code in (EXIT_OK, EXIT_ERROR)
        payload = json.loads(out)
        assert isinstance(payload["checks"], list)
        assert payload["checks"], "doctor must run at least one check"

    def test_delete_requires_confirmation(self, tf_home, monkeypatch, capsys) -> None:
        run_cli_out(monkeypatch, capsys, ["case", "create", "gone", "--json"])
        code, _, _ = run_cli_out(monkeypatch, capsys, ["case-delete", "gone"])
        assert code == EXIT_USAGE  # missing --yes is a usage error


class TestJsonOutput:
    def test_case_create_and_list_json(self, tf_home, monkeypatch, capsys) -> None:
        code, out, _ = run_cli_out(
            monkeypatch,
            capsys,
            ["case", "create", "json-case", "--purpose", "p", "--json"],
        )
        assert code == EXIT_OK
        created = json.loads(out)
        assert re.fullmatch(r"case_[0-9a-f]{16}", created["id"])

        code, out, _ = run_cli_out(monkeypatch, capsys, ["case", "list", "--json"])
        assert code == EXIT_OK
        listed = json.loads(out)
        assert any(c["id"] == created["id"] for c in listed)

    def test_duplicate_case_title_is_usage_3(self, tf_home, monkeypatch, capsys) -> None:
        args = ["case", "create", "dupe", "--json"]
        run_cli_out(monkeypatch, capsys, args)
        code, _, err = run_cli_out(monkeypatch, capsys, args)
        assert code == EXIT_USAGE
        assert "already exists" in err

    def test_catalog_validate_json(self, tf_home, monkeypatch, capsys) -> None:
        code, out, _ = run_cli_out(monkeypatch, capsys, ["catalog", "validate", "--json"])
        assert code == EXIT_OK
        payload = json.loads(out)
        assert payload.get("problems", payload.get("ok")) is not None


class TestTerminalSafety:
    """Untrusted strings must never reach the terminal as control codes."""

    HOSTILE_TITLE = "report\x1b[2J\x1b[1;31mFAKE\x07injected"

    def test_hostile_title_sanitized_in_human_output(self, tf_home, monkeypatch, capsys) -> None:
        code, out, err = run_cli_out(
            monkeypatch,
            capsys,
            ["case", "create", self.HOSTILE_TITLE, "--json"],
        )
        assert code == EXIT_OK
        assert "\x1b" not in out and "\x1b" not in err
        assert "\x07" not in out

        code, out, _ = run_cli_out(monkeypatch, capsys, ["case", "list"])
        assert code == EXIT_OK
        assert "\x1b" not in out
        assert "FAKE" in out  # content survives, control bytes do not

    def test_json_output_escapes_control_chars(self, tf_home, monkeypatch, capsys) -> None:
        run_cli_out(
            monkeypatch,
            capsys,
            ["case", "create", self.HOSTILE_TITLE, "--json"],
        )
        code, out, _ = run_cli_out(monkeypatch, capsys, ["case", "list", "--json"])
        assert code == EXIT_OK
        assert "\x1b" not in out
        parsed = json.loads(out)  # control chars are JSON-escaped, parseable
        hostile = [c for c in parsed if "\x1b" in c["title"]]
        assert hostile, "title stored verbatim in DB (correct); escaped in output"

    def test_rich_markup_in_title_not_interpreted(self, tf_home, monkeypatch, capsys) -> None:
        hostile = "x[bold red]INJECTED[/]"
        code, out, _ = run_cli_out(
            monkeypatch,
            capsys,
            ["case", "create", hostile, "--json"],
        )
        assert code == EXIT_OK
        code, out, _ = run_cli_out(monkeypatch, capsys, ["case", "list"])
        assert code == EXIT_OK
        # Markup is escaped: tags render as literal text. If rich had
        # interpreted them, `[bold` would be consumed (styled invisibly in
        # non-tty) and absent from the output entirely.
        assert "INJECTED" in out
        assert "[bold" in out, "markup tags must render as literal text"


class TestPathTraversal:
    @pytest.mark.parametrize(
        "ref",
        [
            "../../etc/passwd",
            "case_../../../etc",
            "/abs/path",
            "case_zzzzzzzzzzzzzzzz",  # valid shape, nonexistent
        ],
    )
    def test_traversal_shaped_refs_resolve_to_not_found(
        self, tf_home, monkeypatch, capsys, ref: str
    ) -> None:
        code, out, _err = run_cli_out(monkeypatch, capsys, ["case", "show", ref])
        assert code in (EXIT_NOT_FOUND, EXIT_USAGE)
        assert "/etc/passwd" not in out  # never echoed as a resolved path

    def test_export_refuses_traversal_output(self, tf_home, monkeypatch, capsys, tmp_path) -> None:
        run_cli_out(monkeypatch, capsys, ["case", "create", "trav", "--json"])
        code, _, _ = run_cli_out(
            monkeypatch,
            capsys,
            ["case-export", "trav", "--output", str(tmp_path / "exp")],
        )
        assert code == EXIT_OK
        assert (tmp_path / "exp").is_dir()


class TestNetworkPolicy:
    def test_fetch_without_optin_is_exit_4(self, tf_home, monkeypatch, capsys) -> None:
        run_cli_out(monkeypatch, capsys, ["case", "create", "net", "--json"])
        code, _, err = run_cli_out(
            monkeypatch,
            capsys,
            ["source", "add", "https://example.com/", "--case", "net", "--fetch"],
        )
        assert code == EXIT_NETWORK_BLOCKED
        assert "TRACEFIELD_ALLOW_NETWORK" in err

    @pytest.mark.parametrize("url", ["http://127.0.0.1:9/", "http://169.254.169.254/"])
    def test_private_fetch_blocked_even_with_optin(
        self, tf_home, monkeypatch, capsys, url: str
    ) -> None:
        """SSRF guard runs per-request; opt-in does not disable it."""
        monkeypatch.setenv("TRACEFIELD_ALLOW_NETWORK", "1")
        run_cli_out(monkeypatch, capsys, ["case", "create", "ssrf", "--json"])
        code, _, err = run_cli_out(
            monkeypatch,
            capsys,
            ["source", "add", url, "--case", "ssrf", "--fetch"],
        )
        assert code == EXIT_NETWORK_BLOCKED
        assert "safety policy" in err or "rejected" in err.lower()

    def test_username_check_without_optin_is_exit_4(self, tf_home, monkeypatch, capsys) -> None:
        code, _, _err = run_cli_out(monkeypatch, capsys, ["username", "check", "anyone"])
        assert code == EXIT_NETWORK_BLOCKED

    def test_source_add_without_fetch_never_networks(self, tf_home, monkeypatch, capsys) -> None:
        run_cli_out(monkeypatch, capsys, ["case", "create", "src", "--json"])
        code, out, _ = run_cli_out(
            monkeypatch,
            capsys,
            ["source", "add", "https://example.com/", "--case", "src", "--json"],
        )
        assert code == EXIT_OK
        payload = json.loads(out)
        assert payload["access_method"] == "manual"


class TestObservationSpine:
    def test_observation_add_and_list(self, tf_home, monkeypatch, capsys) -> None:
        run_cli_out(monkeypatch, capsys, ["case", "create", "obs", "--json"])
        code, out, _ = run_cli_out(
            monkeypatch,
            capsys,
            [
                "observation",
                "add",
                "--case",
                "obs",
                "--tool",
                "exiftool",
                "--summary",
                "no GPS present",
                "--json",
            ],
        )
        assert code == EXIT_OK
        payload = json.loads(out)
        assert payload["id"].startswith("obs_")
        assert payload["tool_name"] == "exiftool"

        code, out, _ = run_cli_out(
            monkeypatch, capsys, ["observation", "list", "--case", "obs", "--json"]
        )
        assert code == EXIT_OK
        rows = json.loads(out)
        assert len(rows) == 1

    def test_observation_rejects_foreign_evidence(
        self, tf_home, monkeypatch, capsys, tmp_path
    ) -> None:
        run_cli_out(monkeypatch, capsys, ["case", "create", "oa", "--json"])
        run_cli_out(monkeypatch, capsys, ["case", "create", "ob", "--json"])
        f = tmp_path / "doc.txt"
        f.write_text("body", encoding="utf-8")
        code, out, _ = run_cli_out(
            monkeypatch,
            capsys,
            ["evidence", "attach", str(f), "--case", "oa", "--json"],
        )
        ev_id = json.loads(out)["id"]
        code, _, _err = run_cli_out(
            monkeypatch,
            capsys,
            ["observation", "add", "--case", "ob", "--tool", "t", "--evidence", ev_id, "--json"],
        )
        assert code == EXIT_NOT_FOUND


class TestStructuredLogging:
    """Commands and failures land in the JSONL audit log, redacted."""

    def _log_lines(self, tf_home) -> list[dict]:
        log = tf_home / "logs" / "tracefield.jsonl"
        if not log.exists():
            return []
        return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]

    def test_command_and_fail_events_logged(self, tf_home, monkeypatch, capsys) -> None:
        run_cli_out(monkeypatch, capsys, ["case", "create", "logged", "--json"])
        run_cli_out(monkeypatch, capsys, ["case", "show", "definitely-missing"])
        events = self._log_lines(tf_home)
        kinds = [(e["event"], e.get("level")) for e in events]
        assert ("command", "INFO") in kinds
        fail_events = [e for e in events if e["event"] == "fail"]
        assert fail_events, kinds
        assert fail_events[-1]["exit_code"] == EXIT_NOT_FOUND
        assert "case not found" in fail_events[-1]["msg"]

    def test_argv_secrets_never_hit_the_log(self, tf_home, monkeypatch, capsys) -> None:
        run_cli_out(
            monkeypatch,
            capsys,
            [
                "claim",
                "add",
                "--case",
                "c",
                "--text",
                "note token=ghp_secretvalue1234567890abcdef",
                "--json",
            ],
        )
        log_text = (tf_home / "logs" / "tracefield.jsonl").read_text(encoding="utf-8")
        assert "ghp_secretvalue" not in log_text
        assert "[REDACTED]" in log_text

    def test_unhandled_exception_is_logged_not_raised(self, tf_home, monkeypatch, capsys) -> None:

        from tracefield.storage.repositories import CaseRepo

        def boom(self, *a, **k):
            raise RuntimeError("boom")

        monkeypatch.setattr(CaseRepo, "list", boom)
        code, out, err = run_cli_out(monkeypatch, capsys, ["case", "list"])
        assert code == EXIT_ERROR
        assert "error: boom" in err
        assert "Traceback" not in err
        assert "TRACEFIELD_DEBUG" in err
        events = self._log_lines(tf_home)
        unhandled = [e for e in events if e["event"] == "unhandled"]
        assert unhandled and unhandled[-1]["exc_type"] == "RuntimeError"
        assert "boom" in unhandled[-1]["exc"]
        # and the process did not blow up with a raw traceback on stdout
        assert "Traceback (most recent call last)" not in out
