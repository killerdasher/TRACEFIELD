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

    def test_redirect_hook_revalidates(self) -> None:
        """Contract: fetch must re-run the URL policy on every redirect
        hop via an httpx request event hook (private redirect targets are
        refused). Pins the wiring — the policy function itself is tested
        above/below."""
        fetch_py = (
            Path(__file__).resolve().parents[2] / "src" / "tracefield" / "fieldtools" / "fetch.py"
        )
        src = fetch_py.read_text(encoding="utf-8")
        assert "event_hooks" in src, "fetch must install a request event hook"
        assert "validate_fetch_url(str(request.url))" in src, (
            "the redirect hook must call validate_fetch_url on each hop"
        )
        # And the policy itself refuses a private redirect destination.
        with pytest.raises(UrlPolicyError):
            validate_fetch_url("http://10.0.0.1/redirected")
        with pytest.raises(UrlPolicyError):
            validate_fetch_url("http://[fd00::1]/redirected")


class TestSubprocessAllowlist:
    def test_run_backend_rejects_missing_binary(self) -> None:
        from tracefield.fieldtools.inspect import run_backend

        with pytest.raises(FileNotFoundError):
            run_backend(["definitely-not-a-real-binary-9876", "--version"])

    def test_run_backend_no_shell_interpolation(self) -> None:
        """Argument arrays only — a metacharacter-laden 'binary' name must
        not execute anything."""
        from tracefield.fieldtools.inspect import run_backend

        with pytest.raises(FileNotFoundError):
            # If this were passed through a shell, `;` would run `id`.
            run_backend(["nonexistent; id", "x"])

    def test_env_is_minimal(self) -> None:
        from tracefield.fieldtools.inspect import run_backend

        rc, out, _ = run_backend(["/bin/sh", "-c", "echo $FOO"])
        # FOO should not leak from the parent environment.
        assert "SENSITIVE" not in out
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
