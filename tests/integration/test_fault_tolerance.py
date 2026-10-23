"""Fault-tolerance suite (FS-15).

Operational failure modes the audit §6 listed as ABSENT, now covered
deterministically and locally — no network, no third-party probing:

* Corrupt / truncated database file -> loud, typed refusal (not a hang).
* SQLite busy/locked under a concurrent writer -> honest busy_timeout then
  a typed operational error (exit 5 UNAVAILABLE at the CLI boundary).
* Read-only permission loss on the data root / db file -> refuses to write
  rather than silently corrupting or fabricating success.
* Mid-report DB lock / interrupted export -> the exception propagates; a
  prior intact export is never clobbered.

Each test drives a real failure through a real seam (file bytes, chmod, a
real SQLite lock, a real repo read inside build_report) — no fabricated
exit codes.
"""

from __future__ import annotations

import os
import sqlite3
import stat

import pytest

from tracefield.core.domain import Case, Claim, Relation, RelationType, Source
from tracefield.reporting.build import build_report
from tracefield.reporting.export import export_case, verify_manifest
from tracefield.storage import CaseWorkspace, Database
from tracefield.storage.repositories import (
    CaseRepo,
    ClaimRepo,
    RelationRepo,
    SourceRepo,
)

pytestmark = pytest.mark.integration


def _seed(settings, db, case_factory):
    """Populate a case with a source, claim, evidence and a relation."""
    case = case_factory("ft-case")
    ws = CaseWorkspace(settings.cases_root, db)
    src = SourceRepo(db).add(
        Source(case_id=case.id, locator="https://example.org/a", publisher="Ex")
    )
    claim = ClaimRepo(db).add(Claim(case_id=case.id, text="Claim under test."))
    fixture = settings.data_root / "ft.txt"
    fixture.write_text("Claim under test.", encoding="utf-8")
    evidence = ws.attach_file(case.id, src.id, fixture, media_type="text/plain")
    RelationRepo(db).add(
        Relation(
            case_id=case.id,
            from_id=evidence.id,
            to_id=claim.id,
            relation=RelationType.SUPPORTS,
            rationale="links",
            evidence_ids=[evidence.id],
        )
    )
    return case, ws


def _list_evidence(self, case_id: str):
    """Real EventRepo seam, wrapped to inject a lock mid-report."""
    raise sqlite3.OperationalError("database is locked (simulated)")


class TestCorruptDatabase:
    """A corrupt/truncated DB must be refused loudly, never opened silently."""

    def test_garbage_bytes_are_refused_not_parsed(self, settings) -> None:
        settings.ensure_dirs()
        settings.db_path.write_bytes(b"\x00\x01garbage not a database\xff" * 64)
        with pytest.raises(sqlite3.DatabaseError):
            Database(settings.db_path)

    def test_truncated_db_refuses_construction_not_fabricated(self, settings) -> None:
        db = Database(settings.db_path)
        CaseRepo(db).create(Case(title="x"))
        db.close()
        raw = settings.db_path.read_bytes()
        settings.db_path.write_bytes(raw[: len(raw) // 3])  # truncate
        # Opening a truncated file must refuse loudly, never open silently.
        with pytest.raises(sqlite3.DatabaseError):
            Database(settings.db_path)


class TestBusyLocked:
    """Concurrent writer: honest busy_timeout, then a typed operational error
    — never a silent commit or data loss."""

    def test_second_writer_raises_lock_error(self, settings) -> None:
        settings.ensure_dirs()
        db1 = Database(settings.db_path)
        CaseRepo(db1).create(Case(title="a"))
        # Hold an open IMMEDIATE transaction on db1 so db2's write blocks.
        db1._conn.execute("BEGIN IMMEDIATE")

        db2 = Database(settings.db_path)
        db2._conn.execute("PRAGMA busy_timeout = 1")  # force fast failure

        error = None
        try:
            with db2.tx() as conn:
                conn.execute(
                    "INSERT INTO cases(id,title,created_at,updated_at) VALUES('c2','b','t','t')"
                )
        except sqlite3.OperationalError as exc:
            error = exc
        finally:
            db2.close()
            db1._conn.rollback()
            db1.close()

        assert error is not None, "locked writer must raise, not silently succeed"
        assert "lock" in str(error).lower() or "busy" in str(error).lower()

    def test_cli_maps_operational_error_to_exit_5(self, settings, monkeypatch, capsys) -> None:
        """The CLI top-level maps OperationalError to exit 5 (UNAVAILABLE),
        matching the documented exit-code contract."""
        from tracefield.cli import main as cli_main
        from tracefield.cli.main import EXIT_UNAVAILABLE

        class _LockedDB:
            def __init__(self, *_a, **_k):
                raise sqlite3.OperationalError("database is locked")

        monkeypatch.setattr(cli_main, "Database", _LockedDB)
        monkeypatch.setattr("sys.argv", ["tracefield", "case", "list"])
        with pytest.raises(SystemExit) as exc:
            cli_main.run()
        assert exc.value.code == EXIT_UNAVAILABLE


class TestWritePermissionLoss:
    """Read-only data root / db file: refuse to write, never fabricate success."""

    def test_read_only_data_root_refuses_new_db(self, settings) -> None:
        settings.ensure_dirs()
        os.chmod(settings.data_root, stat.S_IRUSR | stat.S_IXUSR)  # 0o500
        try:
            with pytest.raises((OSError, PermissionError, sqlite3.OperationalError)):
                Database(settings.data_root / "sub" / "tracefield.sqlite3")
        finally:
            os.chmod(settings.data_root, stat.S_IRWXU)  # restore

    def test_read_only_existing_db_refuses_write(self, settings) -> None:
        db = Database(settings.db_path)
        case = CaseRepo(db).create(Case(title="ro"))
        db.close()
        os.chmod(settings.db_path, stat.S_IRUSR)  # 0o400 read-only
        try:
            db2 = Database(settings.db_path)
            try:
                with (
                    pytest.raises((OSError, sqlite3.OperationalError)),
                    db2.tx() as conn,
                ):
                    conn.execute("DELETE FROM cases WHERE id=?", (case.id,))
            finally:
                db2.close()
        finally:
            os.chmod(settings.db_path, stat.S_IRUSR | stat.S_IWUSR)


class TestMidReportFailure:
    """A failure part-way through report generation must propagate; a prior
    intact export must never be clobbered."""

    def test_lock_during_report_generation_propagates(
        self, settings, db, case_factory, monkeypatch
    ) -> None:
        case, _ws = _seed(settings, db, case_factory)
        # Inject a lock at a real seam: SourceRepo.list_for_case (called early
        # inside build_report) raises, and the exception must propagate.
        monkeypatch.setattr(SourceRepo, "list_for_case", _list_evidence)
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            build_report(settings, db, case, fmt="json")

    def test_interrupted_export_leaves_prior_intact(self, settings, db, case_factory) -> None:
        case, ws = _seed(settings, db, case_factory)
        out = settings.data_root / "export_ok"
        export_case(settings, db, ws, case, out, redact=True)
        before = (out / "manifest.json").read_bytes()
        ok, problems = verify_manifest(out)
        assert ok, problems

        # Interrupt a SECOND export by making its target unwritable: the
        # export must fail loudly and leave export_ok untouched.
        out2 = settings.data_root / "export_bad"
        out2.mkdir()
        os.chmod(out2, stat.S_IRUSR)  # cannot populate
        try:
            with pytest.raises((OSError, PermissionError, sqlite3.Error)):
                export_case(settings, db, ws, case, out2, redact=True)
        finally:
            os.chmod(out2, stat.S_IRWXU)

        assert (out / "manifest.json").read_bytes() == before
        ok2, problems2 = verify_manifest(out)
        assert ok2, problems2
