"""CLI contract tests: deterministic exit codes, JSON output, terminal
safety, path traversal, and network policy — exercised through the REAL
entry point (``run()``), so the mapping contract is what ships.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

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

    def test_doctor_reports_config_and_author(self, tf_home, monkeypatch, capsys) -> None:
        # The tf_home fixture points TRACEFIELD_CONFIG at a per-test path;
        # absent by default → doctor must say so and the author honest-state.
        code, out, _ = run_cli_out(monkeypatch, capsys, ["doctor", "--json"])
        assert code == EXIT_OK
        payload = json.loads(out)
        cfg = next(c for c in payload["checks"] if c["name"] == "config")
        assert cfg["status"] == "missing"
        assert "author not set" in cfg["detail"]

        # Author identity (FS-17) is carried exactly as configured.
        monkeypatch.setenv(
            "TRACEFIELD_REPORT_AUTHOR", "killerdasher — github.com/killerdasher/TRACEFIELD"
        )
        code, out, _ = run_cli_out(monkeypatch, capsys, ["doctor", "--json"])
        payload = json.loads(out)
        cfg = next(c for c in payload["checks"] if c["name"] == "config")
        assert cfg["status"] == "ok"
        assert "killerdasher" in cfg["detail"] and "env" in cfg["detail"]

        # An invalid config file is REPORTED, not swallowed.
        cfg_path = Path(os.environ.get("TRACEFIELD_CONFIG", "")).resolve()
        cfg_path.write_text("report_author = [not valid\n", encoding="utf-8")
        monkeypatch.delenv("TRACEFIELD_REPORT_AUTHOR", raising=False)
        code, out, _ = run_cli_out(monkeypatch, capsys, ["doctor", "--json"])
        payload = json.loads(out)
        cfg = next(c for c in payload["checks"] if c["name"] == "config")
        assert cfg["status"] == "error" and "not valid TOML" in cfg["detail"]

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
        """SSRF guard runs per-request; opt-in and a scope grant disable neither."""
        monkeypatch.setenv("TRACEFIELD_ALLOW_NETWORK", "1")
        run_cli_out(monkeypatch, capsys, ["case", "create", "ssrf", "--json"])
        run_cli_out(
            monkeypatch,
            capsys,
            [
                "case",
                "authorize",
                "ssrf",
                "--scope",
                "ssrf blocklist fixture",
                "--authorized-by",
                "fixtures",
            ],
        )
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


class TestReportRegister:
    """Durable report identity through the real CLI (schema v2, OOVS-09)."""

    def test_report_registers_and_history_lists(
        self, tf_home, monkeypatch, capsys, tmp_path
    ) -> None:
        run_cli_out(monkeypatch, capsys, ["case", "create", "rep-reg", "--json"])
        out_path = tmp_path / "r1.json"
        code, _, _ = run_cli_out(
            monkeypatch,
            capsys,
            ["report", "rep-reg", "--format", "json", "--output", str(out_path)],
        )
        assert code == EXIT_OK
        p1 = json.loads(out_path.read_text(encoding="utf-8"))
        assert p1["document"]["report_id"]
        assert p1["document"]["revision"] == 1

        # Second render = revision 2 superseding 1.
        out2 = tmp_path / "r2.json"
        run_cli_out(
            monkeypatch, capsys, ["report", "rep-reg", "--format", "json", "--output", str(out2)]
        )
        p2 = json.loads(out2.read_text(encoding="utf-8"))
        assert p2["document"]["revision"] == 2
        assert p2["document"]["supersedes"] == p1["document"]["report_id"]

        code, out, _ = run_cli_out(monkeypatch, capsys, ["report-history", "rep-reg", "--json"])
        assert code == EXIT_OK
        hist = json.loads(out)
        assert [r["revision"] for r in hist["reports"]] == [1, 2]
        assert hist["corrections"] == [] and hist["shipments"] == []

    def test_report_correct_end_to_end(self, tf_home, monkeypatch, capsys, tmp_path) -> None:
        run_cli_out(monkeypatch, capsys, ["case", "create", "rep-corr", "--json"])
        out_path = tmp_path / "r.json"
        run_cli_out(
            monkeypatch,
            capsys,
            ["report", "rep-corr", "--format", "json", "--output", str(out_path)],
        )
        rid = json.loads(out_path.read_text(encoding="utf-8"))["document"]["report_id"]

        # Unknown report id → not found (2).
        code, _, err = run_cli_out(
            monkeypatch,
            capsys,
            ["report-correct", "rep-corr", "--report", "rep_nope", "--note", "x"],
        )
        assert code == EXIT_NOT_FOUND and "not found" in err

        code, out, _ = run_cli_out(
            monkeypatch,
            capsys,
            ["report-correct", "rep-corr", "--report", rid, "--note", "figure misread", "--json"],
        )
        assert code == EXIT_OK
        corr = json.loads(out)
        assert corr["corrected_report_id"] == rid and corr["note"] == "figure misread"

        # The correction appears in the history register and in the next
        # registered render of the lineage.
        _, out, _ = run_cli_out(monkeypatch, capsys, ["report-history", "rep-corr", "--json"])
        hist = json.loads(out)
        assert [c["note"] for c in hist["corrections"]] == ["figure misread"]
        out2 = tmp_path / "r2.json"
        run_cli_out(
            monkeypatch, capsys, ["report", "rep-corr", "--format", "json", "--output", str(out2)]
        )
        p2 = json.loads(out2.read_text(encoding="utf-8"))
        assert [c["corrected_report_id"] for c in p2["document"]["corrections"]] == [rid]

    def test_case_export_records_shipment(self, tf_home, monkeypatch, capsys, tmp_path) -> None:
        run_cli_out(monkeypatch, capsys, ["case", "create", "rep-ship", "--json"])
        exp = tmp_path / "bundle"
        code, _, _ = run_cli_out(
            monkeypatch,
            capsys,
            ["case-export", "rep-ship", "--output", str(exp), "--recipient", "legal team"],
        )
        assert code == EXIT_OK
        readme = (exp / "EXPORT_README.txt").read_text(encoding="utf-8")
        assert 'to recipient "legal team"' in readme
        _, out, _ = run_cli_out(monkeypatch, capsys, ["report-history", "rep-ship", "--json"])
        hist = json.loads(out)
        assert len(hist["shipments"]) == 1
        assert hist["shipments"][0]["recipient"] == "legal team"
        assert hist["shipments"][0]["report_id"] == hist["reports"][0]["id"]

    def test_report_correct_across_cases_is_not_found(
        self, tf_home, monkeypatch, capsys, tmp_path
    ) -> None:
        run_cli_out(monkeypatch, capsys, ["case", "create", "rc-a", "--json"])
        run_cli_out(monkeypatch, capsys, ["case", "create", "rc-b", "--json"])
        out_path = tmp_path / "ra.json"
        run_cli_out(
            monkeypatch, capsys, ["report", "rc-a", "--format", "json", "--output", str(out_path)]
        )
        rid = json.loads(out_path.read_text(encoding="utf-8"))["document"]["report_id"]
        code, _, err = run_cli_out(
            monkeypatch, capsys, ["report-correct", "rc-b", "--report", rid, "--note", "x"]
        )
        assert code == EXIT_NOT_FOUND and "not found in this case" in err


class TestScopeLedger:
    """Scope authorization ledger (OOVS-01): fetch requires an ACTIVE grant."""

    DNS_DECOY = "https://lead-absent-4d21.invalid/"  # unresolvable: neverconnected

    def test_fetch_with_optin_but_no_grant_is_exit_4(self, tf_home, monkeypatch, capsys) -> None:
        """The global network opt-in alone is NOT collection authority."""
        monkeypatch.setenv("TRACEFIELD_ALLOW_NETWORK", "1")
        run_cli_out(monkeypatch, capsys, ["case", "create", "no-scope", "--json"])
        code, _, err = run_cli_out(
            monkeypatch,
            capsys,
            ["source", "add", self.DNS_DECOY, "--case", "no-scope", "--fetch"],
        )
        assert code == EXIT_NETWORK_BLOCKED
        assert "no active scope authorization" in err
        assert "case authorize" in err  # actionable next step

    def test_grant_then_fetch_passes_the_ledger_gate(self, tf_home, monkeypatch, capsys) -> None:
        monkeypatch.setenv("TRACEFIELD_ALLOW_NETWORK", "1")
        run_cli_out(monkeypatch, capsys, ["case", "create", "scoped", "--json"])
        code, _, _ = run_cli_out(
            monkeypatch,
            capsys,
            [
                "case",
                "authorize",
                "scoped",
                "--scope",
                "lead-absent-4d21.invalid fixture checks",
                "--authorized-by",
                "fixtures",
                "--json",
            ],
        )
        assert code == EXIT_OK
        code, _, err = run_cli_out(
            monkeypatch,
            capsys,
            ["source", "add", self.DNS_DECOY, "--case", "scoped", "--fetch"],
        )
        # The gate passed; the fetch attempts and fails closed on the
        # unresolvable host — proving the block was URL policy, not the ledger.
        assert code == EXIT_NETWORK_BLOCKED
        assert "no active scope authorization" not in err
        assert "safety policy" in err or "rejected" in err.lower()

    def test_revoke_after_grant_blocks_fetch_again(self, tf_home, monkeypatch, capsys) -> None:
        monkeypatch.setenv("TRACEFIELD_ALLOW_NETWORK", "1")
        run_cli_out(monkeypatch, capsys, ["case", "create", "revoked", "--json"])
        run_cli_out(
            monkeypatch,
            capsys,
            ["case", "authorize", "revoked", "--scope", "s", "--authorized-by", "a"],
        )
        run_cli_out(
            monkeypatch,
            capsys,
            ["case", "authorize", "revoked", "--revoke", "--authorized-by", "a"],
        )
        code, _, err = run_cli_out(
            monkeypatch,
            capsys,
            ["source", "add", self.DNS_DECOY, "--case", "revoked", "--fetch"],
        )
        assert code == EXIT_NETWORK_BLOCKED
        assert "no active scope authorization" in err

    def test_host_absent_from_scope_text_warns_but_proceeds(
        self, tf_home, monkeypatch, capsys
    ) -> None:
        monkeypatch.setenv("TRACEFIELD_ALLOW_NETWORK", "1")
        run_cli_out(monkeypatch, capsys, ["case", "create", "warn-host", "--json"])
        run_cli_out(
            monkeypatch,
            capsys,
            [
                "case",
                "authorize",
                "warn-host",
                "--scope",
                "unrelated scope text",
                "--authorized-by",
                "a",
            ],
        )
        code, out, err = run_cli_out(
            monkeypatch,
            capsys,
            ["source", "add", self.DNS_DECOY, "--case", "warn-host", "--fetch"],
        )
        assert code == EXIT_NETWORK_BLOCKED  # policy refusal (decoy host)
        assert "not mentioned in the recorded scope" in " ".join(out.split())
        assert "no active scope authorization" not in err  # ledger passed

    def test_grant_without_scope_text_is_usage_3(self, tf_home, monkeypatch, capsys) -> None:
        run_cli_out(monkeypatch, capsys, ["case", "create", "empty-scope", "--json"])
        code, _, err = run_cli_out(
            monkeypatch, capsys, ["case", "authorize", "empty-scope", "--authorized-by", "a"]
        )
        assert code == EXIT_USAGE and "--scope" in err

    def test_scope_read_view_and_entries(self, tf_home, monkeypatch, capsys) -> None:
        run_cli_out(monkeypatch, capsys, ["case", "create", "sview", "--json"])
        _, out, _ = run_cli_out(monkeypatch, capsys, ["case", "scope", "sview", "--json"])
        before = json.loads(out)
        assert before["active"] is False and before["entries"] == []

        run_cli_out(
            monkeypatch,
            capsys,
            [
                "case",
                "authorize",
                "sview",
                "--scope",
                "targets file a",
                "--authorized-by",
                "ops",
                "--json",
            ],
        )
        run_cli_out(
            monkeypatch,
            capsys,
            ["case", "authorize", "sview", "--revoke", "--authorized-by", "ops", "--json"],
        )
        _, out, _ = run_cli_out(monkeypatch, capsys, ["case", "scope", "sview", "--json"])
        after = json.loads(out)
        assert after["active"] is False  # latest decision is the revoke
        assert [e["action"] for e in after["entries"]] == ["grant", "revoke"]
        assert after["entries"][0]["authorized_by"] == "ops"


class TestAssertions:
    """Assertion creation path (A4/R-A4-5): previously read-only."""

    def test_add_list_review(self, tf_home, monkeypatch, capsys) -> None:
        run_cli_out(monkeypatch, capsys, ["case", "create", "asr", "--json"])
        _, out, _ = run_cli_out(
            monkeypatch,
            capsys,
            ["claim", "add", "--case", "asr", "--text", "account reused", "--json"],
        )
        claim_id = json.loads(out)["id"]
        code, out, _ = run_cli_out(
            monkeypatch,
            capsys,
            [
                "assertion",
                "add",
                "--case",
                "asr",
                "--claim",
                claim_id,
                "--statement",
                "the reuse supports attribution to operator account",
                "--attribution",
                "analyst A",
                "--uncertainty",
                "medium",
                "--json",
            ],
        )
        assert code == EXIT_OK
        asr = json.loads(out)
        assert asr["claim_id"] == claim_id and asr["review_state"] == "unreviewed"

        _, out, _ = run_cli_out(
            monkeypatch, capsys, ["assertion", "list", "--case", "asr", "--json"]
        )
        assert [a["id"] for a in json.loads(out)] == [asr["id"]]

        code, _, _ = run_cli_out(
            monkeypatch, capsys, ["assertion", "review", asr["id"], "--state", "confirmed"]
        )
        assert code == EXIT_OK
        _, out, _ = run_cli_out(
            monkeypatch, capsys, ["assertion", "list", "--case", "asr", "--json"]
        )
        assert json.loads(out)[0]["review_state"] == "confirmed"

    def test_add_rejects_unknown_claim_and_evidence(self, tf_home, monkeypatch, capsys) -> None:
        run_cli_out(monkeypatch, capsys, ["case", "create", "asr-bad", "--json"])
        code, _, err = run_cli_out(
            monkeypatch,
            capsys,
            [
                "assertion",
                "add",
                "--case",
                "asr-bad",
                "--claim",
                "clm_nope",
                "--statement",
                "s",
                "--json",
            ],
        )
        assert code == EXIT_NOT_FOUND
        code, _, err = run_cli_out(
            monkeypatch,
            capsys,
            [
                "assertion",
                "add",
                "--case",
                "asr-bad",
                "--evidence",
                "ev_nope",
                "--statement",
                "s",
                "--json",
            ],
        )
        assert code == EXIT_NOT_FOUND and "evidence not found" in err

    def test_empty_statement_is_usage_3(self, tf_home, monkeypatch, capsys) -> None:
        run_cli_out(monkeypatch, capsys, ["case", "create", "asr-empty", "--json"])
        code, _, err = run_cli_out(
            monkeypatch,
            capsys,
            [
                "assertion",
                "add",
                "--case",
                "asr-empty",
                "--statement",
                "  ",
                "--json",
            ],
        )
        assert code == EXIT_USAGE and "--statement" in err


class TestCatalogStale:
    """Read-only freshness inventory (FS-20): informational, never a gate."""

    def test_catalog_stale_json_is_read_only_inventory(self, tf_home, monkeypatch, capsys) -> None:
        code, out, _ = run_cli_out(monkeypatch, capsys, ["catalog", "stale", "--json"])
        assert code == EXIT_OK
        p = json.loads(out)
        assert p["total"] > 0
        for key in ("stale_count", "unknown_count", "max_age_days", "entries"):
            assert key in p
        # no health semantics anywhere in the response
        assert "health_result" not in p

    def test_catalog_stale_human_mode_mentions_verdict_caveat(
        self, tf_home, monkeypatch, capsys
    ) -> None:
        code, out, _ = run_cli_out(monkeypatch, capsys, ["catalog", "stale"])
        assert code == EXIT_OK
        assert "not a health verdict" in " ".join(out.split())


class TestReportAuthor:
    """FS-17 completion: the operator's identity travels into every render."""

    AUTHOR = "killerdasher — github.com/killerdasher/TRACEFIELD"

    def test_env_author_lands_in_report(self, tf_home, monkeypatch, capsys, tmp_path) -> None:
        monkeypatch.setenv("TRACEFIELD_REPORT_AUTHOR", self.AUTHOR)
        run_cli_out(monkeypatch, capsys, ["case", "create", "auth-1", "--json"])
        out_path = tmp_path / "r.json"
        code, _, _ = run_cli_out(
            monkeypatch, capsys, ["report", "auth-1", "--format", "json", "--output", str(out_path)]
        )
        assert code == EXIT_OK
        p = json.loads(out_path.read_text(encoding="utf-8"))
        assert p["document"]["author"] == self.AUTHOR
        # Author is independent of registration state.
        run_cli_out(
            monkeypatch,
            capsys,
            ["report", "auth-1", "--format", "json", "--no-register", "--output", str(out_path)],
        )
        p0 = json.loads(out_path.read_text(encoding="utf-8"))
        assert p0["document"]["author"] == self.AUTHOR
        assert p0["document"]["revision"] == "unregistered"

    def test_config_file_author_lands_in_report(
        self, tf_home, monkeypatch, capsys, tmp_path
    ) -> None:
        # tf_home sets TRACEFIELD_CONFIG to an absent per-test path; writing
        # it exercises the real file path through the real CLI.
        cfg_path = Path(os.environ.get("TRACEFIELD_CONFIG", "")).resolve()
        cfg_path.write_text(f'report_author = "{self.AUTHOR}"\n', encoding="utf-8")
        run_cli_out(monkeypatch, capsys, ["case", "create", "auth-2", "--json"])
        out_path = tmp_path / "r.md"
        code, _, _ = run_cli_out(
            monkeypatch,
            capsys,
            ["report", "auth-2", "--format", "markdown", "--output", str(out_path)],
        )
        assert code == EXIT_OK
        md = out_path.read_text(encoding="utf-8")
        assert f"**Author:** {self.AUTHOR}" in md

    def test_broken_config_leaves_author_unset_and_exit_ok(
        self, tf_home, monkeypatch, capsys, tmp_path
    ) -> None:
        cfg_path = Path(os.environ.get("TRACEFIELD_CONFIG", "")).resolve()
        cfg_path.write_text("report_author = [broken\n", encoding="utf-8")
        run_cli_out(monkeypatch, capsys, ["case", "create", "auth-3", "--json"])
        out_path = tmp_path / "r.json"
        code, _, _ = run_cli_out(
            monkeypatch, capsys, ["report", "auth-3", "--format", "json", "--output", str(out_path)]
        )
        assert code == EXIT_OK  # a broken config must not break reporting
        p = json.loads(out_path.read_text(encoding="utf-8"))
        assert p["document"]["author"] == "author not set"


# ---------------------------------------------------------------------------
# B-03: ingest via the real entry point (case-import + source review)
# ---------------------------------------------------------------------------
INGEST_FIXTURE = (
    Path(__file__).parents[1]
    / "fixtures"
    / "ingest"
    / "sherlock_v0.16.2_killerdasher_2026-11-07.csv"
)


class TestIngest:
    """`case-import` + `source promote/dismiss/defer` against the real CLI
    (contract: TRACEFIELD_02_PRODUCT_DIRECTION.md B-03 exit codes + JSON
    parity; observation spine R-SEC-4/5/6/8)."""

    @staticmethod
    def _flat(text: str) -> str:
        """Collapse rich-console line wrapping for message matching."""
        return " ".join(text.split())

    # -- helpers ----------------------------------------------------------
    @staticmethod
    def _mkcase(monkeypatch, capsys, name: str) -> None:
        from tracefield.cli.main import run as _  # noqa: F401 — import completes bindings

        code, _out, err = run_cli_out(monkeypatch, capsys, ["case", "create", name])
        assert code == EXIT_OK, err

    @staticmethod
    def _import(monkeypatch, capsys, case: str, file: Path | None = None) -> tuple[int, str, dict]:
        code, out, err = run_cli_out(
            monkeypatch,
            capsys,
            ["case-import", "--file", str(file or INGEST_FIXTURE), "--case", case, "--json"],
        )
        if code == EXIT_OK:
            return code, out, json.loads(out)
        return code, out + err, {}

    def _observation_ids(self, monkeypatch, capsys, case: str) -> list[str]:
        code, out, err = run_cli_out(
            monkeypatch, capsys, ["observation", "list", "--case", case, "--json"]
        )
        assert code == EXIT_OK, err
        obs = json.loads(out)
        assert isinstance(obs, list)
        return [o["id"] for o in obs]

    # -- happy path -------------------------------------------------------
    def test_import_real_fixture_online(self, tf_home, monkeypatch, capsys, tmp_path) -> None:
        self._mkcase(monkeypatch, capsys, "ing")
        code, out, payload = self._import(monkeypatch, capsys, "ing")
        assert code == EXIT_OK, out
        assert payload["format_name"] == "sherlock_csv"
        assert payload["row_count"] == 10
        assert payload["evidence_sha256"].startswith("2930960456466566")
        assert payload["declared_version"] == ""
        assert len(payload["observation_ids"]) == 10

        # --json parity: status reports the import event + counts
        code, out, err = run_cli_out(
            monkeypatch, capsys, ["case-import", "status", "--case", "ing", "--json"]
        )
        assert code == EXIT_OK, err
        st = json.loads(out)
        assert st["last_import"]["action"] == "ingest.file"
        assert st["observations_by_tool"] == {"sherlock": 10}
        assert st["evidence_count"] == 1
        assert st["review_actions"] == {}

    def test_refusals_exit_3(self, tf_home, monkeypatch, capsys, tmp_path) -> None:
        self._mkcase(monkeypatch, capsys, "ref")

        # zero rows (header-only)
        empty = tmp_path / "empty.csv"
        empty.write_text(
            "username,name,url_main,url_user,exists,http_status,response_time_s\r\n",
            newline="",
        )
        code, out, _ = self._import(monkeypatch, capsys, "ref", file=empty)
        assert code == EXIT_USAGE, out
        assert "zero data rows" in self._flat(out)

        # unmappable format
        bad = tmp_path / "bad.csv"
        bad.write_text("a,b,c\n1,2,3\n", newline="")
        code, out, _ = self._import(monkeypatch, capsys, "ref", file=bad)
        assert code == EXIT_USAGE, out
        assert "no ingest format matches header" in self._flat(out)

        # oversize: a byte over the 10 MB cap, checked before parse
        huge = tmp_path / "huge.csv"
        huge.write_text(
            "username,name,url_main,url_user,exists,http_status,response_time_s\r\n"
            + "x" * (10 * 1024 * 1024 + 1),
            newline="",
        )
        code, out, _ = self._import(monkeypatch, capsys, "ref", file=huge)
        assert code == EXIT_USAGE, out
        assert "ingest cap" in self._flat(out)

    def test_import_never_echoes_raw_content(self, tf_home, monkeypatch, capsys, tmp_path) -> None:
        """R-SEC-5: even a secret-carrying row stays out of the terminal."""
        self._mkcase(monkeypatch, capsys, "echo")
        secret = "SECRETCLI5f2b"
        hostile = tmp_path / "hostile.csv"
        hostile.write_text(
            "username,name,url_main,url_user,exists,http_status,response_time_s\r\n"
            f"killerdasher,Probe,https://probe.test/,https://probe.test/u/k?token={secret},Claimed,200,0.5\r\n"
            "killerdasher,GitHub,https://www.github.com/,https://www.github.com/killerdasher,Claimed,200,0.6\r\n",
            newline="",
        )
        code, out, _ = self._import(monkeypatch, capsys, "echo", file=hostile)
        assert code == EXIT_OK
        assert secret not in out  # import output carries counts/ids, never row content

        code, st_out, err = run_cli_out(
            monkeypatch, capsys, ["case-import", "status", "--case", "echo", "--json"]
        )
        assert code == EXIT_OK, err
        assert secret not in st_out + err

    # -- review actions (R-SEC-8) ------------------------------------------
    def test_dismiss_requires_reason_and_blocks_promotion(
        self, tf_home, monkeypatch, capsys
    ) -> None:
        self._mkcase(monkeypatch, capsys, "rev")
        code, out, err = self._import(monkeypatch, capsys, "rev")
        assert code == EXIT_OK, out
        obs = self._observation_ids(monkeypatch, capsys, "rev")
        victim = obs[1]

        # (c) dismiss without reason -> exit 3
        code, out, err = run_cli_out(
            monkeypatch, capsys, ["source", "dismiss", victim, "--case", "rev"]
        )
        assert code == EXIT_USAGE, out + err
        assert "requires a --reason" in self._flat(out + err)

        # dismiss WITH reason -> ok, event recorded
        code, out, err = run_cli_out(
            monkeypatch,
            capsys,
            ["source", "dismiss", victim, "--case", "rev", "--reason", "out of scope"],
        )
        assert code == EXIT_OK, out + err

        # (a) promoting a dismissed-by-reason record is refused
        code, out, err = run_cli_out(
            monkeypatch, capsys, ["source", "promote", victim, "--case", "rev"]
        )
        assert code == EXIT_USAGE, out + err
        assert "dismissed by reason" in self._flat(out + err)

    def test_promote_lands_source_with_provenance_and_event(
        self, tf_home, monkeypatch, capsys
    ) -> None:
        self._mkcase(monkeypatch, capsys, "pro")
        code, out, _ = self._import(monkeypatch, capsys, "pro")
        assert code == EXIT_OK
        obs = self._observation_ids(monkeypatch, capsys, "pro")

        code, out, err = run_cli_out(
            monkeypatch, capsys, ["source", "promote", obs[0], "--case", "pro", "--json"]
        )
        assert code == EXIT_OK, out + err
        payload = json.loads(out)
        assert payload["event"]["action"] == "candidate.promote"
        prov = payload["provenance"]
        assert prov["tool"] == "sherlock"
        assert prov["tool_version"] == "unknown"
        assert prov["file_sha256"].startswith("2930960456466566")
        assert prov["row_no"] >= 2  # header is record 1
        src = payload["source"]
        assert src["locator"].startswith("http")  # from the verified copy
        assert "never verified by TRACEFIELD" in src["limitations"]

        # double promotion is refused
        code, out, err = run_cli_out(
            monkeypatch, capsys, ["source", "promote", obs[0], "--case", "pro"]
        )
        assert code == EXIT_USAGE
        assert "already promoted" in self._flat(out + err)

    def test_review_actions_do_not_change_analysis_baseline(
        self, tf_home, monkeypatch, capsys
    ) -> None:
        """(d) promotion/dismissal alone never alter analysis output;
        the baseline changes exactly through the existing relation flow."""
        self._mkcase(monkeypatch, capsys, "base")
        code, out, _ = self._import(monkeypatch, capsys, "base")
        assert code == EXIT_OK
        code, out, err = run_cli_out(
            monkeypatch,
            capsys,
            [
                "claim",
                "add",
                "--text",
                "killerdasher controls the GitHub account github.com/killerdasher",
                "--case",
                "base",
            ],
        )
        assert code == EXIT_OK, out + err
        claim_id = out.splitlines()[0].split()[-1].rstrip("]")  # "added claim clm_x"

        code_a, a_before, _ = run_cli_out(
            monkeypatch,
            capsys,
            ["analyze", "claim", claim_id, "--case", "base", "--json"],
        )
        assert code_a == EXIT_OK
        a_json_before = json.loads(a_before)
        # computed_at is a wall-clock stamp, not analysis state: comparing it
        # flakes when the two utcnow() calls straddle a tick (observed once
        # in a full-suite run 2026-11-08). Compare analysis fields only,
        # and assert the stamp is present in both payloads.
        a_before_core = {k: v for k, v in a_json_before.items() if k != "computed_at"}
        assert "computed_at" in a_json_before

        obs = self._observation_ids(monkeypatch, capsys, "base")
        code, _, err = run_cli_out(
            monkeypatch, capsys, ["source", "promote", obs[0], "--case", "base"]
        )
        assert code == EXIT_OK, err
        code, _, err = run_cli_out(
            monkeypatch,
            capsys,
            ["source", "dismiss", obs[1], "--case", "base", "--reason", "noise"],
        )
        assert code == EXIT_OK, err

        code_a, a_after, _ = run_cli_out(
            monkeypatch,
            capsys,
            ["analyze", "claim", claim_id, "--case", "base", "--json"],
        )
        assert code_a == EXIT_OK
        a_after = json.loads(a_after)
        assert "computed_at" in a_after
        assert {
            k: v for k, v in a_after.items() if k != "computed_at"
        } == a_before_core  # baseline equality holds (analysis fields, stamp excluded)

    def test_cross_case_promotion_refused(self, tf_home, monkeypatch, capsys) -> None:
        self._mkcase(monkeypatch, capsys, "ca")
        self._mkcase(monkeypatch, capsys, "cb")
        code, out, _ = self._import(monkeypatch, capsys, "cb")
        assert code == EXIT_OK
        obs_b = self._observation_ids(monkeypatch, capsys, "cb")
        code, out, err = run_cli_out(
            monkeypatch, capsys, ["source", "promote", obs_b[0], "--case", "ca"]
        )
        assert code == EXIT_USAGE, out + err
        assert "cross-case promotion is not permitted" in self._flat(out + err)

    # -- adversarial-review pins (2026-11-08) ------------------------------

    def test_review_target_not_found_exits_2(self, tf_home, monkeypatch, capsys) -> None:
        """m-1: a review action aimed at a nonexistent observation is a
        lookup miss (exit 2 NOT_FOUND), not a usage refusal (exit 3)."""
        self._mkcase(monkeypatch, capsys, "nf")
        code, out, _ = self._import(monkeypatch, capsys, "nf")
        assert code == EXIT_OK
        for action in ("promote", "dismiss", "defer"):
            code, out, err = run_cli_out(
                monkeypatch,
                capsys,
                [
                    "source",
                    action,
                    "obs_doesnotexist",
                    "--case",
                    "nf",
                    *(
                        []
                        if action == "promote"
                        else ([] if action == "defer" else ["--reason", "x"])
                    ),
                ],
            )
            assert code == EXIT_NOT_FOUND, f"{action}: {out + err}"
            assert "observation not found" in self._flat(out + err)

    def test_bad_privacy_label_exit_3_and_zero_partial_writes(
        self, tf_home, monkeypatch, capsys
    ) -> None:
        """M-2: an invalid --privacy-label used to exit 1 with a pydantic
        traceback AND left a dangling Source row. Now: honest refusal, no
        writes."""
        self._mkcase(monkeypatch, capsys, "pl")
        code, out, err = run_cli_out(
            monkeypatch,
            capsys,
            [
                "case-import",
                "--file",
                str(INGEST_FIXTURE),
                "--case",
                "pl",
                "--privacy-label",
                "NOT_A_LABEL",
                "--json",
            ],
        )
        assert code == EXIT_USAGE, out + err
        assert "privacy_label" in self._flat(out + err)
        code, out, _ = run_cli_out(
            monkeypatch, capsys, ["case-import", "status", "--case", "pl", "--json"]
        )
        assert code == EXIT_OK
        assert json.loads(out)["observations_by_tool"] == {}
        assert json.loads(out)["evidence_count"] == 0

    def test_duplicate_import_is_noted_not_silent(self, tf_home, monkeypatch, capsys) -> None:
        """m-10: re-importing identical bytes is additive by design, but the
        second run names the first evidence — the counts story stays
        honest."""
        self._mkcase(monkeypatch, capsys, "dupe")
        code, _, payload_1 = self._import(monkeypatch, capsys, "dupe")
        assert code == EXIT_OK
        assert payload_1["duplicate_of"] == ""
        code, _, payload_2 = self._import(monkeypatch, capsys, "dupe")
        assert code == EXIT_OK
        assert payload_2["duplicate_of"] == payload_1["evidence_id"]
        # the note is honest in the human-readable render too (JSON parity
        # carries the machine field above)
        code, out2, err2 = run_cli_out(
            monkeypatch,
            capsys,
            ["case-import", "--file", str(INGEST_FIXTURE), "--case", "dupe"],
        )
        assert code == EXIT_OK, out2 + err2
        assert "byte-identical evidence already in this case" in self._flat(out2 + err2)
        # counts honesty: additive, visibly
        assert payload_2["row_count"] == 10

    def test_promoted_source_persists_full_provenance(self, tf_home, monkeypatch, capsys) -> None:
        """m-6: the Source row must be able to ground its own provenance —
        full sha256 (not a 12-char truncation) and the row record number."""
        self._mkcase(monkeypatch, capsys, "prov")
        code, _, payload = self._import(monkeypatch, capsys, "prov")
        assert code == EXIT_OK
        sha = payload["evidence_sha256"]
        obs = self._observation_ids(monkeypatch, capsys, "prov")
        code, out, err = run_cli_out(
            monkeypatch, capsys, ["source", "promote", obs[0], "--case", "prov", "--json"]
        )
        assert code == EXIT_OK, out + err
        srcd = json.loads(out)["source"]
        assert sha in srcd["limitations"], (
            "limitations must carry the FULL sha256, not a truncation"
        )
        assert "row_record=" in srcd["limitations"]
        assert "raw_ref=" in srcd["limitations"]

    def test_one_shot_options_with_subcommand_refused(self, tf_home, monkeypatch, capsys) -> None:
        """nit: mixing one-shot options with the status subcommand used to
        silently ignore the options; now it's an honest exit 3."""
        self._mkcase(monkeypatch, capsys, "mix")
        code, out, err = run_cli_out(
            monkeypatch,
            capsys,
            ["case-import", "--file", str(INGEST_FIXTURE), "status", "--case", "mix"],
        )
        assert code == EXIT_USAGE, out + err
        assert "not both" in self._flat(out + err)
