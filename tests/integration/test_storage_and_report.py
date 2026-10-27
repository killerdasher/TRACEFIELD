"""Integration tests: database migrations, repositories, workspace,
provenance chain, reports, export, catalogue."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from tracefield.core.domain import (
    Case,
    Claim,
    EvidenceItem,
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
    AssertionRepo,
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
    def test_fresh_db_is_current(self, settings) -> None:
        from tracefield import SCHEMA_VERSION

        db = Database(settings.db_path)
        assert db.schema_version == SCHEMA_VERSION == 2
        db.close()

    def test_migrate_is_idempotent(self, settings) -> None:
        db = Database(settings.db_path)
        db.migrate()
        db.migrate()
        assert db.schema_version == 2
        db.close()

    def test_migration_from_v1_database(self, settings) -> None:
        """A database created with only migration 1 reruns opens on v2.

        Additive-migrations invariant: upgrading never rewrites or drops
        v1 data — it only adds tables and triggers.
        """
        from tracefield.storage.database import _MIGRATION_1

        path = settings.db_path
        old = sqlite3.connect(path)
        old.executescript(_MIGRATION_1)
        old.execute(
            "INSERT INTO cases(id,title,created_at,updated_at) VALUES('case_x','x','t1','t1')"
        )
        old.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','1')")
        old.commit()
        old.close()

        db = Database(path)  # opens and migrates in __init__
        assert db.schema_version == 2
        row = db.execute("SELECT title FROM cases WHERE id='case_x'").fetchone()
        assert row is not None and row["title"] == "x"
        # New tables exist and report the guard triggers are installed.
        names = {
            r["name"]
            for r in db.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE 'trg_%ins'"
            ).fetchall()
        }
        assert {
            "trg_relations_integrity_ins",
            "trg_assertions_integrity_ins",
        } <= names
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
        """Repo-level roundtrip with REAL record ids — a relation's endpoints
        and evidence links must all exist in the case (see the v2 integrity
        guards: invented ids are no longer storable)."""
        case = case_factory()
        src = SourceRepo(db).add(Source(case_id=case.id, locator="https://example.org/a"))
        claim = ClaimRepo(db).add(Claim(case_id=case.id, text="c"))
        ev = EvidenceRepo(db).add(
            EvidenceItem(
                case_id=case.id,
                source_id=src.id,
                sha256="1" * 64,
                media_type="text/plain",
                storage_ref="evidence/x",
                captured_at="2026-01-01T00:00:00Z",
            )
        )
        rel = Relation(
            case_id=case.id,
            from_id=src.id,
            to_id=claim.id,
            relation=RelationType.SUPPORTS,
            evidence_ids=[ev.id],
        )
        RelationRepo(db).add(rel)
        got = RelationRepo(db).get(rel.id)
        assert got is not None and got.evidence_ids == [ev.id]


class TestSchemaV2IntegrityTriggers:
    """DB-level referential guards (schema v2): invented, cross-case, or
    dangling ids are refused at write time as corruption.

    These tests write RAW SQL deliberately — the guards exist to protect
    against bad data entering below the app layer, so the guard is probed
    exactly where it stands."""

    @staticmethod
    def _seed_case(db: Any, case_factory: Any, suffix: str) -> tuple[Any, Any, Any, Any]:
        case = case_factory(f"trig-{suffix}")
        src = SourceRepo(db).add(Source(case_id=case.id, locator=f"https://x.test/{suffix}"))
        claim = ClaimRepo(db).add(Claim(case_id=case.id, text=f"c {suffix}"))
        ev = EvidenceRepo(db).add(
            EvidenceItem(
                case_id=case.id,
                source_id=src.id,
                sha256="2" * 64,
                media_type="text/plain",
                storage_ref=f"evidence/{suffix}",
                captured_at="2026-01-01T00:00:00Z",
            )
        )
        return case, src, claim, ev

    def test_relation_endpoint_must_exist_in_same_case(self, db, case_factory) -> None:
        # Two parallel cases with real records: any case-blind "id exists
        # somewhere" check would accept the rejected rows below, so every
        # refusal here proves the same-case filter is enforced.
        a_case, a_src, a_claim, _a_ev = self._seed_case(db, case_factory, "pe-a")
        b_case, b_src, b_claim, _b_ev = self._seed_case(db, case_factory, "pe-b")
        valid = Relation(
            case_id=a_case.id,
            from_id=a_src.id,
            to_id=a_claim.id,
            relation=RelationType.SUPPORTS,
        )
        RelationRepo(db).add(valid)  # the repo path with real ids passes
        bad_froms = [
            (a_case, b_src.id),  # exists, wrong case
            (a_case, "src_invented"),  # does not exist at all
            (b_case, a_claim.id),  # mirrored direction, still cross-case
        ]
        for case, endpoint in bad_froms:
            with pytest.raises(sqlite3.IntegrityError, match="from_id must reference"):
                db.execute(
                    "INSERT INTO relations(id,case_id,from_id,to_id,relation,"
                    "created_at) VALUES(?,?,?,?,?,?)",
                    ("rel_x", case.id, endpoint, endpoint, "supports", "t"),
                )
                db.commit()
        # Cross-case or invented to_id with a valid from_id: refused too.
        with pytest.raises(sqlite3.IntegrityError, match="to_id must reference"):
            db.execute(
                "INSERT INTO relations(id,case_id,from_id,to_id,relation,"
                "created_at) VALUES(?,?,?,?,?,?)",
                ("rel_y", a_case.id, a_src.id, b_claim.id, "supports", "t"),
            )
            db.commit()
        with pytest.raises(sqlite3.IntegrityError, match="to_id must reference"):
            db.execute(
                "INSERT INTO relations(id,case_id,from_id,to_id,relation,"
                "created_at) VALUES(?,?,?,?,?,?)",
                ("rel_z", a_case.id, a_src.id, "clm_invented", "supports", "t"),
            )
            db.commit()
        # The valid row is untouched by the refusals.
        assert RelationRepo(db).get(valid.id) is not None

    def test_relation_endpoint_update_is_guarded_too(self, db, case_factory) -> None:
        a_case, a_src, a_claim, _a_ev = self._seed_case(db, case_factory, "upd-a")
        b_case, b_src, _b_claim, _b_ev = self._seed_case(db, case_factory, "upd-b")
        rel = RelationRepo(db).add(
            Relation(
                case_id=a_case.id,
                from_id=a_src.id,
                to_id=a_claim.id,
                relation=RelationType.SUPPORTS,
            )
        )
        # Rewire the relation to a cross-case endpoint: refused.
        with pytest.raises(sqlite3.IntegrityError, match="to_id must reference"):
            db.execute("UPDATE relations SET to_id=? WHERE id=?", (b_src.id, rel.id))
            db.commit()
        # Moving the row to another case leaves its endpoints behind: refused.
        with pytest.raises(sqlite3.IntegrityError, match="from_id must reference"):
            db.execute("UPDATE relations SET case_id=? WHERE id=?", (b_case.id, rel.id))
            db.commit()
        # Same-case rewiring stays legal.
        a_claim2 = ClaimRepo(db).add(Claim(case_id=a_case.id, text="c2"))
        db.execute("UPDATE relations SET to_id=? WHERE id=?", (a_claim2.id, rel.id))
        db.commit()
        assert RelationRepo(db).get(rel.id).to_id == a_claim2.id

    def test_relation_evidence_ids_guard(self, db, case_factory) -> None:
        a_case, a_src, a_claim, a_ev = self._seed_case(db, case_factory, "ev-a")
        b_case, _b_src, _b_claim, b_ev = self._seed_case(db, case_factory, "ev-b")
        bad_cases = [
            "not-json",  # invalid JSON
            "[1]",  # non-text element
            f'["{b_ev.id}"]',  # existing id, other case
            f'["{a_ev.id}","{b_ev.id}"]',  # mixed: one dangling for this case
            "[]extra",  # truncated JSON
        ]
        for raw in bad_cases:
            with pytest.raises(
                sqlite3.IntegrityError, match="must be valid JSON listing evidence ids"
            ):
                db.execute(
                    "INSERT INTO relations(id,case_id,from_id,to_id,relation,"
                    "evidence_ids,created_at) VALUES(?,?,?,?,?,?,?)",
                    ("rel_e", a_case.id, a_src.id, a_claim.id, "supports", raw, "t"),
                )
                db.commit()
        # Valid: the real same-case evidence id.
        db.execute(
            "INSERT INTO relations(id,case_id,from_id,to_id,relation,evidence_ids,"
            "created_at) VALUES(?,?,?,?,?,?,?)",
            ("rel_ok", a_case.id, a_src.id, a_claim.id, "supports", f'["{a_ev.id}"]', "t"),
        )
        db.commit()
        # Cross-case reference update: refused.
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "UPDATE relations SET evidence_ids=? WHERE id=?", (f'["{b_ev.id}"]', "rel_ok")
            )
            db.commit()
        del b_case

    def test_assertion_guards(self, db, case_factory) -> None:
        from tracefield.core.domain import Assertion

        a_case, _a_src, a_claim, a_ev = self._seed_case(db, case_factory, "as-a")
        _b_case, _b_src, b_claim, b_ev = self._seed_case(db, case_factory, "as-b")
        # Dangling evidence in an assertion — refused.
        with pytest.raises(sqlite3.IntegrityError, match=r"assertions\.evidence_ids"):
            db.execute(
                "INSERT INTO assertions(id,case_id,claim_id,statement,method,"
                "evidence_ids,created_at) VALUES(?,?,?,?,?,?,?)",
                ("asr_x", a_case.id, a_claim.id, "s", "analyst", f'["{b_ev.id}"]', "t"),
            )
            db.commit()
        # Cross-case claim link — refused.
        with pytest.raises(sqlite3.IntegrityError, match=r"assertions\.claim_id"):
            db.execute(
                "INSERT INTO assertions(id,case_id,claim_id,statement,method,"
                "evidence_ids,created_at) VALUES(?,?,?,?,?,?,?)",
                ("asr_y", a_case.id, b_claim.id, "s", "analyst", "[]", "t"),
            )
            db.commit()
        # Valid assertion (repo path) with real same-case refs.
        asr = AssertionRepo(db).add(
            Assertion(
                case_id=a_case.id,
                claim_id=a_claim.id,
                statement="A interprets the evidence",
                evidence_ids=[a_ev.id],
            )
        )
        got = AssertionRepo(db).list_for_case(a_case.id)
        assert [a.id for a in got] == [asr.id]
        # Dangling evidence afterward is refused on UPDATE.
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "UPDATE assertions SET evidence_ids=? WHERE id=?",
                (json.dumps([b_ev.id]), asr.id),
            )
            db.commit()


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
        assert payload["report_schema_version"] == 3
        assert payload["case"]["id"] == case.id
        assert payload["global_caveats"]
        # Dissemination block (OOVS-09): generated_at, tool, author/revision/
        # corrections always present; an unset author is stated honestly, and
        # an unregistered payload says so instead of inventing an identity.
        assert payload["generated_at"].endswith("Z")  # tz-aware UTC
        assert payload["tool"]["name"] == "tracefield"
        assert payload["document"]["author"] == "author not set"
        assert payload["document"]["revision"] == "unregistered"
        assert payload["document"]["report_id"] == ""
        assert payload["document"]["corrections"] == []

    def test_report_carries_configured_author(self, settings, db, case_factory) -> None:
        """A configured author identity is carried into all formats."""
        case, _ = self._seed(settings, db, case_factory)
        settings.report_author = "Test Operator <op@example.org>"
        payload = json.loads(build_report(settings, db, case, fmt="json"))
        assert payload["document"]["author"] == "Test Operator <op@example.org>"
        md = build_report(settings, db, case, fmt="markdown")
        assert "Test Operator <op@example.org>" in md
        html_out = build_report(settings, db, case, fmt="html")
        assert "Test Operator &lt;op@example.org&gt;" in html_out  # escaped

    def test_report_reflects_current_state_after_claim_correction(
        self, settings, db, case_factory
    ) -> None:
        """Correction-propagation invariant: reports are derived on demand
        from current case state — there is no cached derived artefact, so a
        corrected claim propagates into the next report by construction.
        The report carries a `corrections` audit list; empty here because
        this correction path predates correction records."""

        case, _ = self._seed(settings, db, case_factory)
        claims = ClaimRepo(db).list_for_case(case.id)
        claim = claims[0]
        before = build_report(settings, db, case, fmt="markdown")
        assert claim.text in before

        # Correct the claim text directly at the storage layer (a claim
        # edit is a first-class record mutation, not a new cached report).
        db.execute("UPDATE claims SET text=? WHERE id=?", ("CORRECTED claim text", claim.id))
        after = build_report(settings, db, case, fmt="markdown")
        assert "CORRECTED claim text" in after
        assert claim.text not in after  # stale text no longer rendered

    def test_timestamps_are_utc_aware(self, settings, db, case_factory) -> None:
        """Temporal-evidence invariant: every stored/generated timestamp is
        timezone-aware UTC — naive timestamps would silently corrupt any
        later temporal comparison or replay."""
        case, _ = self._seed(settings, db, case_factory)
        payload = json.loads(build_report(settings, db, case, fmt="json"))
        for s in payload["sources"]:
            assert s["first_seen_at"].endswith("Z")
            if s["collected_at"]:
                assert s["collected_at"].endswith("Z")
        assert payload["generated_at"].endswith("Z")
        assert case.created_at.endswith("Z")

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

    def test_register_chain(self, db, case_factory) -> None:
        """Durable report identity chain (OOVS-09): revision N supersedes
        N-1; the register names the replacement."""
        from tracefield.storage.repositories import ReportRepo

        case = case_factory("rep-chain")
        repo = ReportRepo(db)
        r1 = repo.register(case.id)
        r2 = repo.register(case.id)
        assert (r1.revision, r2.revision) == (1, 2)
        assert r2.supersedes == r1.id
        # r1 was returned before the supersession happened — re-read from
        # storage for the post-linkage state.
        assert repo.get(r1.id).superseded_by == r2.id
        assert [r.id for r in repo.list_for_case(case.id)] == [r1.id, r2.id]
        assert repo.get(r1.id) is not None

    def test_registered_payload_carries_identity(self, settings, db, case_factory) -> None:
        from tracefield.reporting.build import build_registered_report, build_report

        case, _ = self._seed(settings, db, case_factory)
        text1, r1 = build_registered_report(settings, db, case, fmt="json")
        p1 = json.loads(text1)
        assert p1["document"]["report_id"] == r1.id
        assert p1["document"]["revision"] == 1
        # The --no-register path stays identity-free and honest.
        p0 = json.loads(build_report(settings, db, case, fmt="json", register=False))
        assert p0["document"]["report_id"] == ""

    def test_markdown_renders_identity_and_lineage(self, settings, db, case_factory) -> None:
        from tracefield.reporting.build import build_registered_report

        case, _ = self._seed(settings, db, case_factory)
        _t1, r1 = build_registered_report(settings, db, case, fmt="json")
        _t2, r2 = build_registered_report(settings, db, case, fmt="json")
        _t3, r3 = build_registered_report(settings, db, case, fmt="markdown")
        assert f"- **Report ID:** `{r3.id}`" in _t3
        assert f"- **Supersedes:** `{r2.id}`" in _t3
        assert "- **Superseded by:**" not in _t3  # r3 is current
        # An earlier revision's marker is discoverable in the register
        # (re-read from storage — the returned objects predate the links).
        from tracefield.storage.repositories import ReportRepo

        repo = ReportRepo(db)
        assert repo.get(r1.id).superseded_by == r2.id
        assert repo.get(r2.id).superseded_by == r3.id

    def test_correction_travels_with_lineage(self, settings, db, case_factory) -> None:
        from tracefield.reporting.build import build_case_payload, build_registered_report
        from tracefield.storage.repositories import ReportRepo

        case, _ = self._seed(settings, db, case_factory)
        _t1, r1 = build_registered_report(settings, db, case, fmt="json")
        correction = ReportRepo(db).add_correction(case.id, r1.id, "claim summary misquoted")
        _t2, r2 = build_registered_report(settings, db, case, fmt="json")
        payload2 = build_case_payload(settings, db, case)  # unregistered baseline
        assert payload2["document"]["corrections"] == []
        chain = ReportRepo(db).corrections_for_chain(r2.id)
        assert [c.id for c in chain] == [correction.id]
        assert chain[0].corrected_report_id == r1.id

    def test_export_renders_one_identity_once(self, settings, db, case_factory) -> None:
        """case-export: json + markdown are two renderings of ONE registered
        identity (no double registration), and the README records it."""
        from tracefield.storage.repositories import ReportRepo

        case, ws = self._seed(settings, db, case_factory)
        out = settings.data_root / "export-identity"
        export_case(settings, db, ws, case, out, redact=True, recipient="field editor")
        p = json.loads((out / "report.json").read_text(encoding="utf-8"))
        rid = p["document"]["report_id"]
        assert rid and p["document"]["revision"] == 1
        md = (out / "report.md").read_text(encoding="utf-8")
        assert f"`{rid}`" in md  # same identity in both renderings
        readme = (out / "EXPORT_README.txt").read_text(encoding="utf-8")
        assert f"report {rid} (revision 1" in readme
        assert 'to recipient "field editor"' in readme
        shipments = ReportRepo(db).shipments_for_case(case.id)
        assert len(shipments) == 1 and shipments[0].report_id == rid
        # Exactly one revision was minted for one export.
        assert [r.revision for r in ReportRepo(db).list_for_case(case.id)] == [1]
        ok, problems = verify_manifest(out)
        assert ok, problems


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

    def test_stale_entries_flag_old_and_unknown_dates(self) -> None:
        """FS-20/D7 decision: freshness listing, never a health verdict."""
        from datetime import UTC, datetime, timedelta

        from tracefield.registry import Catalog, CatalogEntry, EntryType, checked_age_days

        stale_date = (datetime.now(UTC) - timedelta(days=200)).isoformat(timespec="seconds")
        fresh_date = (datetime.now(UTC) - timedelta(days=3)).isoformat(timespec="seconds")
        cat = Catalog()  # constructed entries only, no file
        for entry_id, last_checked in (
            ("old-tool", stale_date),
            ("fresh-tool", fresh_date),
            ("no-date", ""),
            ("bad-date", "not-a-date"),
        ):
            cat.add(
                CatalogEntry(
                    id=entry_id,
                    canonical_name=entry_id.upper(),
                    entry_type=EntryType.CLI_TOOL,
                    first_seen="2026-01-01T00:00:00Z",
                    last_checked=last_checked,
                )
            )
        rows, unknown = cat.stale_entries(max_age_days=180)
        ids = {r["id"] for r in rows}
        assert ids == {"old-tool", "no-date", "bad-date"}
        assert unknown == 2  # unknown freshness is REPORTED, not guessed
        ages = {r["id"]: r["age_days"] for r in rows}
        assert ages["no-date"] is None
        assert ages["bad-date"] is None
        assert ages["old-tool"] >= 200
        assert checked_age_days(fresh_date, datetime.now(UTC)) == 3
