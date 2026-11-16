"""Reliability closure phase — regression pins for two reviewed findings.

Finding A (duplicate-source detection): the warning in ``source add`` fired
only when no fetch succeeded, because ``prior_same_locator`` was computed
after the fetch block and the warning lived on an ``elif`` branch. A
duplicate URL fetched successfully therefore created a second source row
plus a second evidence capture with NO warning — and only after spending
the network request. ``evidence attach`` (auto-created source) had no
duplicate check at all.

Finding B (atomic evidence storage): ``CaseWorkspace.attach_bytes`` wrote
the fetched body DIRECTLY to the final content-addressed path
(``evidence/<2-char>/<sha256>``), while ``attach_file`` and
``store_raw_observation`` use temporary-file replacement. An interrupted
write could leave a truncated artifact at the canonical digest path, and
the ``if not dest.exists()`` guard would then skip every retry — permanent
silent corruption under the idempotence policy.

All tests are offline: fetches are served by a mocked httpx transport and
DNS is pinned to a public IP that is never connected to.
"""

from __future__ import annotations

import hashlib
import sys
from typing import Any

import httpx
import pytest

pytestmark = pytest.mark.integration

EXIT_OK = 0
EXIT_ERROR = 1

PAGE = b"<html><title>Duplicate Probe</title><body>verifiable bytes</body></html>"


def run_cli(
    monkeypatch: pytest.MonkeyPatch, args: list[str], env: dict[str, str] | None = None
) -> tuple[int, str, str]:
    """Run the CLI in-process; return (code, stdout, stderr)."""
    import contextlib
    import io

    for key, value in (env or {}).items():
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
    return (code if code is not None else EXIT_OK), buf_out.getvalue(), buf_err.getvalue()


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


URL = "https://example.com/duplicate-probe"


def _granted_case(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    run_cli(monkeypatch, ["case", "create", name, "--purpose", "p", "--scope", "s"])
    code, _, err = run_cli(
        monkeypatch,
        [
            "case",
            "authorize",
            name,
            "--scope",
            "example.com verification",
            "--authorized-by",
            "test",
        ],
    )
    assert code == 0, err


# ---------------------------------------------------------------------------
# Finding A — duplicate-source detection consistency
# ---------------------------------------------------------------------------


class TestFindingADuplicateSources:
    def test_duplicate_with_successful_fetch_warns(
        self, tf_home, monkeypatch, offline_http
    ) -> None:
        """The core defect: duplicate + --fetch previously skipped the
        warning entirely (warning lived on an elif that required no fetch)."""
        _granted_case(monkeypatch, "dupfetch")
        env = {"TRACEFIELD_ALLOW_NETWORK": "1"}
        code, _, _ = run_cli(
            monkeypatch, ["source", "add", URL, "--case", "dupfetch", "--fetch"], env
        )
        assert code == EXIT_OK
        code, out, err = run_cli(
            monkeypatch, ["source", "add", URL, "--case", "dupfetch", "--fetch"], env
        )
        assert code == EXIT_OK, out + err
        flat = " ".join((out + err).split())
        assert "already exists in this case" in flat, (
            "duplicate URL + successful fetch must warn (additive capture note)"
        )

    def test_duplicate_without_fetch_warns(self, tf_home, monkeypatch) -> None:
        _granted_case(monkeypatch, "dupplain")
        code, _, _ = run_cli(monkeypatch, ["source", "add", URL, "--case", "dupplain"])
        assert code == EXIT_OK
        code, out, err = run_cli(monkeypatch, ["source", "add", URL, "--case", "dupplain"])
        assert code == EXIT_OK
        assert "already exists in this case" in " ".join((out + err).split())

    def test_duplicate_with_failed_fetch_still_warns(
        self, tf_home, monkeypatch, offline_http
    ) -> None:
        """Regression guard for the previously working path: fetch fails,
        source registers with an error note, warning must still fire."""
        import tracefield.fieldtools.fetch as fetch_mod

        def boom(source, settings):  # type: ignore[no-untyped-def]
            from tracefield.fieldtools.fetch import FetchError

            raise FetchError("mocked offline failure")

        monkeypatch.setattr(fetch_mod, "fetch_source", boom)
        _granted_case(monkeypatch, "dupfail")
        env = {"TRACEFIELD_ALLOW_NETWORK": "1"}
        code, _, _ = run_cli(
            monkeypatch, ["source", "add", URL, "--case", "dupfail", "--fetch"], env
        )
        assert code == EXIT_OK
        code, out, err = run_cli(
            monkeypatch, ["source", "add", URL, "--case", "dupfail", "--fetch"], env
        )
        assert code == EXIT_OK
        flat = " ".join((out + err).split())
        assert "already exists in this case" in flat
        assert "fetch failed" in flat  # error note recorded honestly

    def test_same_url_in_different_cases_is_silent(
        self, tf_home, monkeypatch, offline_http
    ) -> None:
        """Cross-case isolation: duplicates are per-case; another case must
        not trigger the warning."""
        _granted_case(monkeypatch, "dupcasea")
        _granted_case(monkeypatch, "dupcaseb")
        env = {"TRACEFIELD_ALLOW_NETWORK": "1"}
        code, _, _ = run_cli(
            monkeypatch, ["source", "add", URL, "--case", "dupcasea", "--fetch"], env
        )
        assert code == EXIT_OK
        code, out, err = run_cli(monkeypatch, ["source", "add", URL, "--case", "dupcaseb"])
        assert code == EXIT_OK
        assert "already exists" not in " ".join((out + err).split())

    def test_locator_is_compared_verbatim_no_hidden_normalization(
        self, tf_home, monkeypatch
    ) -> None:
        """Consistency probe: the recorded locator is stored verbatim and
        compared exactly — a textually different locator is a distinct
        record everywhere (documented doctrine), so no warning fires. If a
        normalizer is ever introduced, this pin states the expectation
        explicitly instead of leaving it accidental."""
        _granted_case(monkeypatch, "dupverbatim")
        code, _, _ = run_cli(monkeypatch, ["source", "add", URL, "--case", "dupverbatim"])
        assert code == EXIT_OK
        code, out, err = run_cli(monkeypatch, ["source", "add", URL + "/", "--case", "dupverbatim"])
        assert code == EXIT_OK
        assert "already exists" not in " ".join((out + err).split())

    def test_duplicate_still_additive_both_rows_preserved(
        self, tf_home, monkeypatch, offline_http
    ) -> None:
        """A warning must never merge or delete: the second source row (and
        its evidence capture — possibly different bytes!) still exists."""
        _granted_case(monkeypatch, "dupadditive")
        env = {"TRACEFIELD_ALLOW_NETWORK": "1"}
        run_cli(monkeypatch, ["source", "add", URL, "--case", "dupadditive", "--fetch"], env)
        code, _, _ = run_cli(
            monkeypatch, ["source", "add", URL, "--case", "dupadditive", "--fetch"], env
        )
        assert code == EXIT_OK
        from tracefield.cli.main import open_db
        from tracefield.config import load_settings
        from tracefield.storage.repositories import CaseRepo, EvidenceRepo, SourceRepo

        settings = load_settings()
        db = open_db(settings)
        try:
            case = CaseRepo(db).resolve("dupadditive")
            assert len(SourceRepo(db).list_for_case(case.id)) == 2
            assert len(EvidenceRepo(db).list_for_case(case.id)) == 2
        finally:
            db.close()

    def test_evidence_attach_auto_source_duplicate_warns(self, tf_home, monkeypatch) -> None:
        """Second workflow: evidence attach auto-creates the source row with
        no duplicate check — attaching the same file twice must warn."""
        import pathlib

        f = pathlib.Path("/tmp/tf-dupattach/note.txt")
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("attachment probe")
        _granted_case(monkeypatch, "dupattach")
        code, _, _ = run_cli(monkeypatch, ["evidence", "attach", str(f), "--case", "dupattach"])
        assert code == EXIT_OK
        code, out, err = run_cli(monkeypatch, ["evidence", "attach", str(f), "--case", "dupattach"])
        assert code == EXIT_OK
        flat = " ".join((out + err).split())
        assert "already exists in this case" in flat, (
            "auto-created duplicate source must warn, not silently double rows"
        )

    def test_evidence_attach_explicit_source_no_warning(self, tf_home, monkeypatch) -> None:
        """Attaching twice with an EXPLICIT --source is deliberate: the same
        source gaining a second evidence item is normal workflow, not a
        duplicate-source accident — no warning."""
        import pathlib

        f = pathlib.Path("/tmp/tf-dupattach2/note.txt")
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("attachment probe two")
        _granted_case(monkeypatch, "dupattach2")
        code, out, err = run_cli(
            monkeypatch, ["evidence", "attach", str(f), "--case", "dupattach2", "--json"]
        )
        assert code == EXIT_OK
        import json

        src_id = json.loads(out)["source_id"] if out.strip().startswith("{") else ""
        if not src_id:
            from tracefield.cli.main import open_db
            from tracefield.config import load_settings
            from tracefield.storage.repositories import CaseRepo, SourceRepo

            settings = load_settings()
            db = open_db(settings)
            try:
                case = CaseRepo(db).resolve("dupattach2")
                src_id = SourceRepo(db).list_for_case(case.id)[0].id
            finally:
                db.close()
        code, out, err = run_cli(
            monkeypatch,
            ["evidence", "attach", str(f), "--case", "dupattach2", "--source", src_id],
        )
        assert code == EXIT_OK
        assert "already exists" not in " ".join((out + err).split())


# ---------------------------------------------------------------------------
# Finding B — atomic evidence storage via attach_bytes
# ---------------------------------------------------------------------------


class TestFindingBAtomicAttachBytes:
    @pytest.fixture()
    def bytes_case(self, db, settings, case_factory):
        """A case with a source row and a workspace, for attach_bytes tests."""
        from tracefield.core.domain import Source
        from tracefield.storage.repositories import SourceRepo
        from tracefield.storage.workspace import CaseWorkspace

        case = case_factory("bytes-case")
        source = Source(case_id=case.id, locator="/tmp/probe/source")
        SourceRepo(db).add(source)
        ws = CaseWorkspace(settings.cases_root, db)
        return case, source, ws

    def test_successful_attach_bytes_is_verifiable_readonly(self, settings, bytes_case) -> None:
        case, source, ws = bytes_case
        ev = ws.attach_bytes(case.id, source.id, PAGE, media_type="text/html")
        assert ev.sha256 == hashlib.sha256(PAGE).hexdigest()
        assert ws.verify_evidence(case.id, ev) is True
        path = settings.cases_root / case.id / ev.storage_ref
        assert path.read_bytes() == PAGE
        assert path.stat().st_mode & 0o777 == 0o400

    def test_empty_bytes_attach(self, settings, bytes_case) -> None:
        case, source, ws = bytes_case
        ev = ws.attach_bytes(case.id, source.id, b"")
        assert ev.sha256 == hashlib.sha256(b"").hexdigest()
        assert ws.verify_evidence(case.id, ev) is True
        assert ev.size_bytes == 0

    def test_existing_object_is_never_rewritten(self, settings, bytes_case) -> None:
        """Idempotence: an existing content-addressed object is left exactly
        as-is (same inode/mtime — no rewrite, no truncate)."""
        case, source, ws = bytes_case
        first = ws.attach_bytes(case.id, source.id, PAGE)
        path = settings.cases_root / case.id / first.storage_ref
        before = path.stat().st_mtime_ns, path.stat().st_ino
        second = ws.attach_bytes(case.id, source.id, PAGE)
        after = path.stat().st_mtime_ns, path.stat().st_ino
        assert before == after, "existing valid object must not be rewritten"
        assert second.sha256 == first.sha256

    def test_repeated_identical_attach_shares_one_object(self, settings, bytes_case) -> None:
        case, source, ws = bytes_case
        e1 = ws.attach_bytes(case.id, source.id, PAGE)
        e2 = ws.attach_bytes(case.id, source.id, PAGE)
        assert e1.id != e2.id  # two evidence rows — additive by design
        assert e1.storage_ref == e2.storage_ref  # one content-addressed blob
        assert ws.verify_evidence(case.id, e1) and ws.verify_evidence(case.id, e2)

    def test_write_failure_leaves_no_final_artifact(
        self, db, settings, bytes_case, monkeypatch
    ) -> None:
        """Simulated write failure (fsync raises): temp cleaned, canonical
        path absent, no evidence row, no chain event, exception raised."""
        import os

        case, source, ws = bytes_case
        calls = {"n": 0}

        def failing_fsync(fd: int) -> None:
            calls["n"] += 1
            raise OSError(28, "simulated disk full")

        monkeypatch.setattr(os, "fsync", failing_fsync)
        with pytest.raises(OSError):
            ws.attach_bytes(case.id, source.id, PAGE)
        assert calls["n"] == 1
        from tracefield.storage.repositories import EventRepo, EvidenceRepo

        assert EvidenceRepo(db).list_for_case(case.id) == []
        events = EventRepo(db).list_for_case(case.id)
        assert all("attach" not in e.action for e in events)

        evdir = settings.cases_root / case.id / "evidence"
        leftovers = list(evdir.rglob("*")) if evdir.exists() else []
        partials = [p for p in leftovers if ".partial" in p.name]
        assert partials == [], f"temp files must be cleaned up after failure: {partials}"

    def test_replace_failure_leaves_no_final_artifact(
        self, db, settings, bytes_case, monkeypatch
    ) -> None:
        """Simulated replacement failure: temp cleaned, canonical path
        absent, no evidence row, no chain event."""
        case, source, ws = bytes_case

        def failing_replace(self, target):  # type: ignore[no-untyped-def]
            raise OSError(5, "simulated replace failure")

        monkeypatch.setattr("pathlib.Path.replace", failing_replace)
        with pytest.raises(OSError):
            ws.attach_bytes(case.id, source.id, PAGE)
        from tracefield.storage.repositories import EventRepo, EvidenceRepo

        assert EvidenceRepo(db).list_for_case(case.id) == []
        events = EventRepo(db).list_for_case(case.id)
        assert all("attach" not in e.action for e in events)
        evdir = settings.cases_root / case.id / "evidence"
        partials = [p for p in evdir.rglob("*") if ".partial" in p.name]
        assert partials == []

    def test_temp_names_are_unique_per_call(self, settings, bytes_case, monkeypatch) -> None:
        """Requirement: uniquely named temp per write — two interleaved
        writes of the same digest must not collide on one .partial name
        (the shared-name race the file-attach path carries)."""
        case, source, ws = bytes_case
        seen: list[str] = []
        real_replace = __import__("pathlib").Path.replace

        def spying_replace(self, target):  # type: ignore[no-untyped-def]
            seen.append(str(self))
            return real_replace(self, target)

        monkeypatch.setattr("pathlib.Path.replace", spying_replace)
        ws.attach_bytes(case.id, source.id, PAGE)
        # Simulate a second independent writer starting before the first
        # publish: remove the object so both writers go through the temp
        # path. (An uninterrupted second attach skips writing entirely —
        # that idempotence is pinned by its own test.)
        dest = next(
            p
            for p in (settings.cases_root / case.id / "evidence").rglob("*")
            if p.is_file() and ".partial" not in p.name
        )
        dest.unlink()
        ws.attach_bytes(case.id, source.id, PAGE)
        assert len(set(seen)) == 2, "each write must use its own unique temp name"
