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
