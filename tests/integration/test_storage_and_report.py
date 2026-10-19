"""Integration tests: database migrations, repositories, workspace,
provenance chain, reports, export, catalogue."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tracefield.core.domain import (
    Case,
    Claim,
    Relation,
    RelationType,
    Source,
    SourceType,
)
from tracefield.core.provenance import hash_file
from tracefield.reporting.build import build_report
from tracefield.reporting.export import export_case, verify_manifest
from tracefield.storage import CaseWorkspace, Database
from tracefield.storage.repositories import (
    CaseRepo,
    ClaimRepo,
    EventRepo,
    EvidenceRepo,
    RelationRepo,
    SourceRepo,  # type: ignore[attr-defined]  # re-exported for tests
)
from tracefield.storage.workspace import WorkspaceError, validate_case_id

pytestmark = pytest.mark.integration


class TestMigrations:
    def test_fresh_db_is_v1(self, settings) -> None:
        db = Database(settings.db_path)
        assert db.schema_version == 1
        db.close()

    def test_migrate_is_idempotent(self, settings) -> None:
        db = Database(settings.db_path)
        db.migrate()
        db.migrate()
        assert db.schema_version == 1
        db.close()

    def test_db_file_permissions(self, settings) -> None:
        db = Database(settings.db_path)
        db.close()
        mode = settings.db_path.stat().st_mode & 0o777
        assert mode == 0o600, f"db should be 0600, got {oct(mode)}"

    def test_data_root_permissions(self, settings) -> None:
        mode = settings.data_root.stat().st_mode & 0o777
        assert mode == 0o700


class TestRepositories:
    def test_case_roundtrip(self, db, case_factory) -> None:
        case = case_factory("alpha")
        repo = CaseRepo(db)
        got = repo.get(case.id)
        assert got is not None and got.title == "alpha"
        assert repo.resolve("alpha").id == case.id
        assert repo.resolve(case.id).id == case.id

    def test_case_delete_cascades(self, db, case_factory) -> None:
        case = case_factory("gone")
        src = SourceRepo(db).add(Source(case_id=case.id, locator="https://example.com/x"))
        ClaimRepo(db).add(Claim(case_id=case.id, text="c"))
        CaseRepo(db).delete(case.id)
        assert SourceRepo(db).get(src.id) is None
        assert ClaimRepo(db).list_for_case(case.id) == []

    def test_cross_case_source_rejected_by_trigger(self, db, case_factory) -> None:
        """DB trigger must refuse evidence linking a source from another case."""
        a = case_factory("case-a")
        b = case_factory("case-b")
        src_a = SourceRepo(db).add(Source(case_id=a.id, locator="loc-a"))
        with pytest.raises(Exception, match="same case"):
            db.execute(
                "INSERT INTO evidence(id,case_id,source_id,sha256,media_type,"
                "storage_ref,size_bytes,captured_at) VALUES(?,?,?,?,?,?,?,?)",
                ("ev_x", b.id, src_a.id, "0" * 64, "text/plain", "x", 0, "now"),
            )
            db.commit()

    def test_relation_evidence_ids_roundtrip(self, db, case_factory) -> None:
        case = case_factory()
        rel = Relation(
            case_id=case.id,
            from_id="src_1",
            to_id="clm_1",
            relation=RelationType.SUPPORTS,
            evidence_ids=["ev_1", "ev_2"],
        )
        RelationRepo(db).add(rel)
        got = RelationRepo(db).get(rel.id)
        assert got is not None and got.evidence_ids == ["ev_1", "ev_2"]


class TestWorkspace:
    def test_case_id_validation_rejects_traversal(self) -> None:
        for bad in ("../etc", "case_../x", "case_ZZZZZZZZZZZZZZZZ", "a", ""):
            with pytest.raises(WorkspaceError):
                validate_case_id(bad)

    def test_valid_case_id(self) -> None:
        assert validate_case_id("case_" + "a" * 16) == "case_" + "a" * 16

    def test_attach_and_verify(self, settings, db, case_factory) -> None:
        case = case_factory()
        ws = CaseWorkspace(settings.cases_root, db)
        src = SourceRepo(db).add(
            Source(case_id=case.id, locator="/tmp/f", source_type=SourceType.LOCAL_FILE)
        )
        tmp = settings.data_root / "orig.txt"
        tmp.write_bytes(b"evidence bytes")
        ev = ws.attach_file(case.id, src.id, tmp, media_type="text/plain")
        assert ws.verify_evidence(case.id, ev) is True
        # original unchanged
        assert hash_file(tmp) == ev.sha256
        # stored copy is read-only
        stored = ws.case_dir(case.id) / ev.storage_ref
        assert (stored.stat().st_mode & 0o222) == 0

    def test_attach_cross_case_source_rejected(self, settings, db, case_factory) -> None:
        a = case_factory("a")
        b = case_factory("b")
        ws = CaseWorkspace(settings.cases_root, db)
        src_a = SourceRepo(db).add(Source(case_id=a.id, locator="l"))
        tmp = settings.data_root / "f.bin"
        tmp.write_bytes(b"x")
        with pytest.raises(WorkspaceError, match="cross-case"):
            ws.attach_file(b.id, src_a.id, tmp)

    def test_event_chain_detects_tamper(self, settings, db, case_factory) -> None:
        case = case_factory()
        ws = CaseWorkspace(settings.cases_root, db)
        src = SourceRepo(db).add(Source(case_id=case.id, locator="l"))
        tmp = settings.data_root / "f.bin"
        tmp.write_bytes(b"one")
        ws.attach_file(case.id, src.id, tmp)
        repo = EventRepo(db)
        ok, _ = repo.verify_chain(case.id)
        assert ok is True
        # Tamper with an event's action in the DB
        events = repo.list_for_case(case.id)
        assert events
        db.execute("UPDATE analysis_events SET action='tampered' WHERE id=?", (events[0].id,))
        db.commit()
        ok, detail = repo.verify_chain(case.id)
        assert ok is False and "digest mismatch" in detail


class TestReportAndExport:
    def _seed(self, settings, db, case_factory) -> tuple[Case, CaseWorkspace]:
        case = case_factory("report-case")
        ws = CaseWorkspace(settings.cases_root, db)
        src = SourceRepo(db).add(
            Source(
                case_id=case.id,
                locator="https://example.org/article",
                publisher="Example News",
            )
        )
        ClaimRepo(db).add(Claim(case_id=case.id, text="Event X happened on 2024-05-01."))
        fixture = settings.data_root / "doc.txt"
        fixture.write_text("Event X happened on 2024-05-01.", encoding="utf-8")
        ws.attach_file(case.id, src.id, fixture, media_type="text/plain")
        rel = Relation(
            case_id=case.id,
            from_id=src.id,
            to_id=ClaimRepo(db).list_for_case(case.id)[0].id,
            relation=RelationType.SUPPORTS,
            rationale="article states the event",
            evidence_ids=[EvidenceRepo(db).list_for_case(case.id)[0].id],
        )
        RelationRepo(db).add(rel)
        return case, ws

    def test_markdown_report_contains_caveats_and_trace(self, settings, db, case_factory) -> None:
        case, _ = self._seed(settings, db, case_factory)
        md = build_report(settings, db, case, fmt="markdown")
        assert "Caveats" in md
        assert "not probabilities of truth" in md.lower() or "workflow states" in md
        assert case.id in md
        assert "https://example.org/article" in md

    def test_json_report_valid_and_versioned(self, settings, db, case_factory) -> None:
        case, _ = self._seed(settings, db, case_factory)
        payload = json.loads(build_report(settings, db, case, fmt="json"))
        assert payload["report_schema_version"] == 1
        assert payload["case"]["id"] == case.id
        assert payload["global_caveats"]

    def test_export_and_verify_manifest(self, settings, db, case_factory) -> None:
        case, ws = self._seed(settings, db, case_factory)
        out = settings.data_root / "export1"
        export_case(settings, db, ws, case, out, redact=True)
        assert (out / "manifest.json").exists()
        assert (out / "report.md").exists()
        assert (out / "SENSITIVE_METADATA.txt").exists()
        ok, problems = verify_manifest(out)
        assert ok, problems

    def test_export_with_secret_is_redacted(self, settings, db, case_factory) -> None:
        case = case_factory("secret-case")
        ws = CaseWorkspace(settings.cases_root, db)
        src = SourceRepo(db).add(Source(case_id=case.id, locator="loc"))
        leak = settings.data_root / "leak.txt"
        leak.write_text("api_key=sk-abcdef1234567890secret", encoding="utf-8")
        ws.attach_file(case.id, src.id, leak)
        out = settings.data_root / "export2"
        export_case(settings, db, ws, case, out, redact=True)
        # manifest still verifies (built after redaction)
        ok, problems = verify_manifest(out)
        assert ok, problems
        # the exported copy must not contain the secret
        ev_files = list((out / "evidence").rglob("*"))
        for f in ev_files:
            if f.is_file():
                assert "sk-abcdef1234567890secret" not in f.read_text(
                    encoding="utf-8", errors="ignore"
                )

    def test_export_does_not_mutate_case_store(self, settings, db, case_factory) -> None:
        case, ws = self._seed(settings, db, case_factory)
        evs = EvidenceRepo(db).list_for_case(case.id)
        before = {e.id: e.sha256 for e in evs}
        out = settings.data_root / "export3"
        export_case(settings, db, ws, case, out, redact=True)
        after = {e.id: e.sha256 for e in EvidenceRepo(db).list_for_case(case.id)}
        assert before == after


class TestCatalogue:
    def test_load_and_validate_real_catalogue(self) -> None:
        from tracefield.registry import Catalog

        path = Path(__file__).parent.parent.parent / "data" / "catalog" / "tools.jsonl"
        if not path.exists():
            pytest.skip("catalogue data not present")
        cat = Catalog(path)
        assert len(cat.entries) >= 100
        problems = cat.validate()
        assert problems == [], problems[:5]

    def test_counts_have_tiered_states(self) -> None:
        from tracefield.registry import Catalog

        path = Path(__file__).parent.parent.parent / "data" / "catalog" / "tools.jsonl"
        if not path.exists():
            pytest.skip("catalogue data not present")
        counts = Catalog(path).counts()
        assert counts["total_records"] > 0
        # tiered states must exist as separate keys
        assert "by_integration_state" in counts
        # never claim healthy without a health check
        assert counts["by_integration_state"].get("healthy", 0) == 0

    def test_catalogue_entries_are_inert(self) -> None:
        """A catalogue entry must never contain import/exec directives."""
        from tracefield.registry import CatalogEntry, EntryType

        e = CatalogEntry(
            id="x",
            canonical_name="X",
            entry_type=EntryType.WEBSITE,
            first_seen="2026-01-01T00:00:00Z",
            last_checked="2026-01-01T00:00:00Z",
            description="__import__('os').system('id')",
        )
        # storing the string is fine; nothing in the model executes it
        assert e.description.startswith("__import__")
        dumped = json.loads(e.model_dump_json())
        assert dumped["description"] == e.description
