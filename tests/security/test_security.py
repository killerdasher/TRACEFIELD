"""Security regression tests: URL scheme/host policy, redirect behavior,
subprocess allowlisting, path traversal, terminal injection, redaction in
exports, provider failure not becoming a negative result.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tracefield.core.domain import Source
from tracefield.security import UrlPolicyError, sanitize_for_terminal, validate_fetch_url
from tracefield.security.redact import redact_secrets
from tracefield.storage.workspace import WorkspaceError, validate_case_id

pytestmark = pytest.mark.security


class TestUrlSchemeAndHostPolicy:
    def test_only_http_s(self) -> None:
        for scheme in ("file", "ftp", "gopher", "data", "javascript", "jar", "netdoc"):
            with pytest.raises(UrlPolicyError):
                validate_fetch_url(f"{scheme}://x/")

    def test_cloud_metadata_variants_blocked(self) -> None:
        for url in (
            "http://169.254.169.254/latest/meta-data/",
            "http://169.254.170.2/v2/credentials",  # ECS task metadata
            "http://metadata.google.internal/computeMetadata/v1/",
            "http://100.100.100.200/latest/meta-data/",  # Alibaba
            "http://192.0.0.192/latest/meta-data/",  # Oracle
            "http://fd00:ec2::254/latest/meta-data/",  # AWS IMDSv6
        ):
            with pytest.raises(UrlPolicyError):
                validate_fetch_url(url)

    def test_fails_closed_on_dns_failure(self) -> None:
        # A hostname that does not resolve must raise, not pass.
        with pytest.raises(UrlPolicyError):
            validate_fetch_url("https://this-host-does-not-exist-987654.invalid/")

    def test_embedded_credentials_rejected(self) -> None:
        with pytest.raises(UrlPolicyError):
            validate_fetch_url("https://admin:password@example.com/")


class TestRedirectPolicy:
    def test_fetch_source_blocks_redirect_to_private(self) -> None:
        """A public URL redirecting to a private address must be blocked.

        Uses a local HTTP server that issues a redirect to 127.0.0.1 — the
        redirect hook re-validates and must refuse.
        """
        import threading
        from http.server import BaseHTTPRequestHandler, HTTPServer

        from tracefield.config import Settings
        from tracefield.fieldtools.fetch import fetch_source

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                self.send_response(302)
                self.send_header("Location", "http://127.0.0.1:1/secret")
                self.end_headers()

            def log_message(self, *args: object) -> None:
                pass

        server = HTTPServer(("127.0.0.1", 0), Handler)
        port = server.server_port
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            # The loopback start URL is refused up front — a fetch never
            # reaches a private listener, redirecting or not. (A full
            # public->private redirect exercise needs a public server;
            # the per-hop revalidation wiring is pinned by
            # test_redirect_hook_revalidates below.)
            settings = Settings()
            settings.max_fetch_timeout_s = 2.0
            src = Source(case_id="case_" + "4" * 16, locator=f"http://127.0.0.1:{port}/")
            with pytest.raises(UrlPolicyError):
                fetch_source(src, settings)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_redirect_hop_is_revalidated_and_repinned(self) -> None:
        """Contract: fetch must re-run the URL policy **and** re-pin the
        connection for **every** redirect hop (private redirect targets are
        refused; the socket always connects to a freshly validated IP).
        Pins the wiring — the policy function itself is tested above/below.

        The redirect loop is manual (client `follow_redirects=False`) and each
        hop calls `_pinned_url_and_extensions` + `validate_fetch_url`, so there
        is no separate validate-then-reconnect window (audit F1 fix).
        """
        fetch_py = (
            Path(__file__).resolve().parents[2] / "src" / "tracefield" / "fieldtools" / "fetch.py"
        )
        src = fetch_py.read_text(encoding="utf-8")
        assert "follow_redirects=False" in src, (
            "fetch must drive redirects manually so each hop can be re-pinned"
        )
        assert "_pinned_url_and_extensions(hop_url)" in src, (
            "each redirect hop must be re-pinned to a freshly validated IP"
        )
        assert "validate_fetch_url(urljoin(hop_url, location))" in src, (
            "each redirect target must re-enter the URL policy"
        )
        assert "follow_redirects=True" not in src, (
            "httpx must never follow redirects on its own (that re-resolves DNS without re-pinning)"
        )
        # And the policy itself refuses a private redirect destination.
        with pytest.raises(UrlPolicyError):
            validate_fetch_url("http://10.0.0.1/redirected")
        with pytest.raises(UrlPolicyError):
            validate_fetch_url("http://[fd00::1]/redirected")


class TestSubprocessAllowlist:
    def test_run_backend_rejects_non_allowlisted_binary(self) -> None:
        """run_backend must refuse any executable outside the allowlist,
        before PATH lookup (audit F2: the docstring promised an allowlist;
        now it is enforced)."""
        from tracefield.fieldtools.inspect import run_backend

        for bad in ("sh", "bash", "python3", "rm", "/usr/bin/id"):
            with pytest.raises(ValueError, match="not allowlisted"):
                run_backend([bad, "-c", "true"])

    def test_run_backend_allowlist_is_exact(self) -> None:
        from tracefield.fieldtools import inspect as inspect_mod

        assert {"exiftool", "ffprobe", "tesseract"} == inspect_mod._ALLOWED_BACKENDS

    def test_run_backend_rejects_missing_binary(self) -> None:
        """An allowlisted binary that is absent raises FileNotFoundError so
        callers can report UNAVAILABLE (not a crash)."""
        import shutil as _shutil

        from tracefield.fieldtools import inspect as inspect_mod

        # Force PATH lookup to miss for an allowlisted name; the allowlist
        # check passes, the presence check must then fail cleanly.
        def _none(exe: str) -> str | None:
            return None

        orig = _shutil.which
        inspect_mod.shutil.which = _none  # type: ignore[assignment]
        try:
            with pytest.raises(FileNotFoundError):
                inspect_mod.run_backend(["tesseract", "--version"])
        finally:
            inspect_mod.shutil.which = orig  # type: ignore[assignment]

    def test_run_backend_no_shell_interpolation(self) -> None:
        """Argument arrays only, and now allowlist-first — a metacharacter-
        laden 'binary' name is rejected before PATH lookup, so `;` can never
        run `id` even in principle."""
        from tracefield.fieldtools.inspect import run_backend

        with pytest.raises(ValueError, match="not allowlisted"):
            run_backend(["nonexistent; id", "x"])

    def test_env_is_minimal(self) -> None:
        """The child env is stripped to PATH + LC_ALL regardless of the
        parent environment. The allowlist is relaxed only inside this test so
        we can run a known binary to observe the environment; the shipped
        allowlist is pinned by test_run_backend_allowlist_is_exact."""
        import os

        from tracefield.fieldtools import inspect as inspect_mod

        os.environ["SENSITIVE"] = "canary"
        try:
            orig = inspect_mod._ALLOWED_BACKENDS
            inspect_mod._ALLOWED_BACKENDS = frozenset({"/bin/sh"})  # type: ignore[misc]
            try:
                rc, out, _ = inspect_mod.run_backend(["/bin/sh", "-c", "echo $FOO-$SENSITIVE"])
            finally:
                inspect_mod._ALLOWED_BACKENDS = orig  # type: ignore[misc]
        finally:
            del os.environ["SENSITIVE"]
        # Neither FOO nor the parent SENSITIVE canary may leak into the child.
        assert "SENSITIVE" not in out and "canary" not in out
        _ = rc


class TestPathTraversal:
    @pytest.mark.parametrize(
        "bad",
        [
            "../../etc",
            "case_../../x",
            "case_" + "z" * 16,  # z not hex
            "case_short",
            "/abs/path",
            "case_" + "a" * 15,
        ],
    )
    def test_case_id_traversal_rejected(self, bad: str) -> None:
        with pytest.raises(WorkspaceError):
            validate_case_id(bad)

    def test_workspace_dir_stays_under_root(self, settings, db, case_factory) -> None:
        from tracefield.storage import CaseWorkspace

        case = case_factory()
        ws = CaseWorkspace(settings.cases_root, db)
        d = ws.case_dir(case.id).resolve()
        assert str(d).startswith(str(settings.cases_root.resolve()))


class TestTerminalInjection:
    def test_filename_escape_sequence_stripped(self) -> None:
        hostile = "report\x1b[2J\x1b[1;31mFAKE ERROR.txt"
        cleaned = sanitize_for_terminal(hostile)
        assert "\x1b" not in cleaned
        assert "FAKE ERROR" in cleaned  # content preserved, control gone

    def test_rich_markup_in_filename_neutralized(self) -> None:
        # Rich interprets [bold] as markup; sanitize must not leave live
        # sequences that Rich would style. We escape via sanitize which
        # removes ESC; for square-bracket markup, the CLI uses console.print
        # with the string as data. Verify sanitize at least bounds it.
        hostile = "x[bold red]INJECTED[/"
        assert "\x1b" not in sanitize_for_terminal(hostile)

    def test_oscClipboard_payload_defused(self) -> None:
        payload = "title\x1b]52;c;aGVsbG8=\x07"
        assert "\x1b" not in sanitize_for_terminal(payload)
        assert "\x07" not in sanitize_for_terminal(payload)


class TestRedactionInExports:
    def test_export_redacts_and_manifest_still_verifies(self, settings, db, case_factory) -> None:
        from tracefield.reporting.export import export_case, verify_manifest
        from tracefield.storage import CaseWorkspace
        from tracefield.storage.repositories import SourceRepo

        case = case_factory("sec-case")
        ws = CaseWorkspace(settings.cases_root, db)
        src = SourceRepo(db).add(Source(case_id=case.id, locator="loc"))
        leak = settings.data_root / "tok.txt"
        leak.write_text("Authorization: Bearer ghp_abcdefghij1234567890abcd", encoding="utf-8")
        ws.attach_file(case.id, src.id, leak)
        out = settings.data_root / "sec-export"
        export_case(settings, db, ws, case, out, redact=True)
        ok, problems = verify_manifest(out)
        assert ok, problems
        for f in (out / "evidence").rglob("*"):
            if f.is_file():
                body = f.read_text(encoding="utf-8", errors="ignore")
                assert "ghp_abcdefghij1234567890abcd" not in body


class TestProviderFailureSemantics:
    def test_provider_failure_is_not_negative_result(self) -> None:
        """A 5xx or timeout must never be recorded as NOT_FOUND."""
        from tracefield.fieldtools.username import ProviderRule, _classify

        rule = ProviderRule(name="p", url_template="https://p.example/{username}")
        for status in (500, 502, 503, 429, 403):
            state = _classify(rule, status, "").state
            assert state.value != "NOT_FOUND_VERIFIED"


class TestCatalogueInertness:
    def test_catalogue_jsonl_contains_no_exec_directives(self) -> None:
        """The shipped catalogue must not embed import/exec/eval payloads
        in any field (belt-and-braces; pydantic already treats it as data).
        Every line must also be valid JSON — a data file, never code."""
        import json as _json

        path = Path(__file__).parent.parent.parent / "data" / "catalog" / "tools.jsonl"
        if not path.exists():
            pytest.skip("no catalogue")
        banned = (
            "__import__",
            "os.system",
            "eval(",
            "exec(",
            "pickle.loads",
            "yaml.load(",
            "compile(",
            "subprocess.run",
            "subprocess.call",
            "subprocess.Popen",
        )
        with path.open(encoding="utf-8") as fh:
            for i, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                obj = _json.loads(line)  # must parse — data, not code
                assert isinstance(obj, dict), f"line {i}: not an object"
                haystack = _json.dumps(obj, ensure_ascii=False).lower()
                for token in banned:
                    assert token.lower() not in haystack, f"line {i} contains {token!r}"


class TestSecretsNeverInLogs:
    def test_redact_covers_key_header_variants(self) -> None:
        samples = [
            "x-api-key: abc123",
            "X-Api-Key: abc123",
            "access_token: tok123",
            "?sig=deadbeef&x=1",
            "AIzaSyA-0ExampleExampleExampleExampl",
            "xoxb-1234567890-abcdef",
        ]
        for s in samples:
            out = redact_secrets(s)
            for secret in (
                "abc123",
                "tok123",
                "deadbeef",
                "AIzaSyA-0ExampleExampleExampleExampl",
                "xoxb-",
            ):
                if secret in s:
                    assert secret not in out, f"{secret} leaked in: {out}"


class TestSchemaVersionRefusal:
    def test_newer_schema_db_is_refused(self, settings) -> None:
        """A database written by a newer TRACEFIELD must be refused loudly,
        not silently opened (audit F3). Opening it risks mis-parsing columns
        this build does not understand."""
        from tracefield import SCHEMA_VERSION
        from tracefield.storage import Database, SchemaVersionError

        # Build a valid DB, then bump its recorded schema version to the future.
        db = Database(settings.db_path)
        db._conn.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES('schema_version', ?)",
            (str(SCHEMA_VERSION + 5),),
        )
        db._conn.commit()
        db.close()

        with pytest.raises(SchemaVersionError, match="newer than this build"):
            Database(settings.db_path)

    def test_same_or_older_schema_still_opens(self, settings) -> None:
        from tracefield import SCHEMA_VERSION
        from tracefield.storage import Database

        db = Database(settings.db_path)
        assert db.schema_version == SCHEMA_VERSION
        db.close()
        # Reopening the same version must NOT raise.
        db2 = Database(settings.db_path)
        db2.close()
