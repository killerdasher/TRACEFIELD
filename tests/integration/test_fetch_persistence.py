"""Regression: a successful `source add --fetch` must persist the body.

Found live (LOOP session 2026-11-14, real online case against example.com):
``fetch_source`` computed the body sha256 into the source note and then
discarded the body — the CLI stored a Source row and a `source.add` event,
but NO EvidenceItem and NO case file. The recorded digest named bytes that
existed nowhere, so it could never be re-verified: a direct contradiction
of the product thesis ("evidence is content-addressed and verifiable";
threat model: "Everything written to disk is content-addressed and
hash-chained"). No offline test had ever exercised a *successful* fetch
(the existing ones fail closed on DNS decoys), which is why it survived.

Fix: ``fetch_source`` returns the body (FetchResult); the CLI attaches the
bytes via ``CaseWorkspace.attach_bytes`` (content-addressed, 0400,
chain event evidence.attach_bytes) after the Source row exists.

These tests run the full CLI flow OFFLINE: a mocked httpx transport serves
the page, and DNS resolution is pinned to a public IP that is never
connected to.
"""

from __future__ import annotations

import sys
from typing import Any

import httpx
import pytest

from tracefield.storage.repositories import EvidenceRepo

pytestmark = pytest.mark.integration

PAGE = b"<html><title>Example Snapshot</title><body>verifiable bytes</body></html>"


def run_cli(
    monkeypatch: pytest.MonkeyPatch, args: list[str], env: dict[str, str]
) -> tuple[int, str, str]:
    """Run the CLI in-process with the given args/env; return (code, stdout, stderr)."""
    import contextlib
    import io

    for key, value in env.items():
        monkeypatch.setenv(key, value)
    from tracefield.cli.main import run

    monkeypatch.setattr(sys, "argv", ["tracefield", *args])
    buf_out, buf_err = io.StringIO(), io.StringIO()
    code: int | None = None
    try:
        with contextlib.redirect_stdout(buf_out), contextlib.redirect_stderr(buf_err):
            run()
    except SystemExit as exc:
        raw = exc.code
        code = raw if isinstance(raw, int) else (0 if raw is None else 1)
    return (code if code is not None else 0), buf_out.getvalue(), buf_err.getvalue()


@pytest.fixture()
def offline_http(monkeypatch: pytest.MonkeyPatch) -> None:
    """Serve PAGE from a mock transport; pin DNS to a public, uncontacted IP."""
    import tracefield.fieldtools.fetch as fetch_mod
    import tracefield.security.urls as urls_mod

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=PAGE,
            headers={"content-type": "text/html; charset=utf-8"},
        )

    real_client = httpx.Client

    def fake_client(**kwargs: Any) -> httpx.Client:
        kwargs.pop("trust_env", None)
        return real_client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(fetch_mod.httpx, "Client", fake_client)
    monkeypatch.setattr(fetch_mod, "validate_host", lambda host: ["93.184.216.34"])
    monkeypatch.setattr(urls_mod, "validate_host", lambda host: ["93.184.216.34"])


class TestFetchPersistsEvidence:
    def test_successful_fetch_attaches_verifiable_evidence(
        self, tf_home, monkeypatch, offline_http
    ) -> None:
        """The full CLI flow, offline: grant → fetch → evidence row exists,
        bytes on disk match the digest, `evidence verify` passes."""
        code, out, err = run_cli(
            monkeypatch, ["case", "create", "fetchpersist"], {"TRACEFIELD_REPORT_AUTHOR": "t"}
        )
        assert code == 0
        code, _, _ = run_cli(
            monkeypatch,
            [
                "case",
                "authorize",
                "fetchpersist",
                "--scope",
                "example.com verification",
                "--authorized-by",
                "test",
            ],
            {},
        )
        assert code == 0
        code, out, err = run_cli(
            monkeypatch,
            ["source", "add", "https://example.com/x", "--case", "fetchpersist", "--fetch"],
            {"TRACEFIELD_ALLOW_NETWORK": "1"},
        )
        assert code == 0, out + err
        assert "evidence: ev_" in out + err

        from tracefield.cli.main import open_db
        from tracefield.config import load_settings
        from tracefield.storage.repositories import CaseRepo, SourceRepo

        settings = load_settings()
        db = open_db(settings)
        try:
            case = CaseRepo(db).resolve("fetchpersist")
            src = SourceRepo(db).list_for_case(case.id)[0]
            evs = EvidenceRepo(db).list_for_case(case.id)
            assert len(evs) == 1, "the fetched body must become evidence"
            ev = evs[0]
            assert ev.source_id == src.id
            assert ev.sha256 in src.limitations  # note digest == stored digest
            stored = (settings.cases_root / case.id / ev.storage_ref).read_bytes()
            assert stored == PAGE
            assert ev.media_type == "text/html; charset=utf-8"
            mode = (settings.cases_root / case.id / ev.storage_ref).stat().st_mode & 0o777
            assert mode == 0o400

            from tracefield.storage.workspace import CaseWorkspace

            ws = CaseWorkspace(settings.cases_root, db)
            assert ws.verify_evidence(case.id, ev) is True
        finally:
            db.close()

    def test_chain_records_the_attach(self, tf_home, monkeypatch, offline_http) -> None:
        """The evidence event must be in the tamper-evident chain."""
        run_cli(monkeypatch, ["case", "create", "fetchevent"], {})
        run_cli(
            monkeypatch,
            [
                "case",
                "authorize",
                "fetchevent",
                "--scope",
                "example.com verification",
                "--authorized-by",
                "test",
            ],
            {},
        )
        code, out, err = run_cli(
            monkeypatch,
            ["source", "add", "https://example.com/y", "--case", "fetchevent", "--fetch"],
            {"TRACEFIELD_ALLOW_NETWORK": "1"},
        )
        assert code == 0, out + err

        from tracefield.cli.main import open_db
        from tracefield.config import load_settings
        from tracefield.storage.repositories import CaseRepo, EventRepo

        settings = load_settings()
        db = open_db(settings)
        try:
            case = CaseRepo(db).resolve("fetchevent")
            actions = [e.action for e in EventRepo(db).list_for_case(case.id)]
            assert "evidence.attach_bytes" in actions
        finally:
            db.close()

    def test_failed_fetch_still_stores_no_evidence(self, tf_home, monkeypatch) -> None:
        """Failure path stays honest: error note on the source, no fake
        snapshot, no evidence row."""
        run_cli(monkeypatch, ["case", "create", "fetchfail"], {})
        run_cli(
            monkeypatch,
            [
                "case",
                "authorize",
                "fetchfail",
                "--scope",
                "unreachable.invalid probe",
                "--authorized-by",
                "test",
            ],
            {},
        )
        # DNS for .invalid fails for real, offline-safe: fetch fails closed.
        # The failure may land at URL validation (fail-closed DNS -> exit 4)
        # or at the fetch itself (error note -> exit 0); both are honest.
        code, out, err = run_cli(
            monkeypatch,
            ["source", "add", "https://unreachable.invalid/", "--case", "fetchfail", "--fetch"],
            {"TRACEFIELD_ALLOW_NETWORK": "1"},
        )
        combined = out + err
        assert code in (0, 4), combined
        assert "fetch failed" in combined or "safety policy" in combined

        from tracefield.cli.main import open_db
        from tracefield.config import load_settings
        from tracefield.storage.repositories import CaseRepo, EvidenceRepo

        settings = load_settings()
        db = open_db(settings)
        try:
            case = CaseRepo(db).resolve("fetchfail")
            assert EvidenceRepo(db).list_for_case(case.id) == []
        finally:
            db.close()
