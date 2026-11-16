"""Entity Core v1 (Phase 22) — integration and provenance tests.

Covers: schema v3 migration paths (fresh, populated-v2, idempotent
reopen, partial-migration recovery, record preservation), DB-level
integrity triggers (cross-case, dangling, self-match, duplicate alias),
CLI flows, event-chain auditability, review-state semantics (rejected
retained, nothing merged), and report Entities-section honesty.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest

from tracefield import SCHEMA_VERSION
from tracefield.core.domain import ReviewState
from tracefield.core.entities import (
    Entity,
    EntityAlias,
    EntityMatchCandidate,
    EntityMention,
    normalize_alias,
)
from tracefield.storage.database import Database

pytestmark = pytest.mark.integration

EXIT_USAGE = 3
EXIT_NOT_FOUND = 2


def run_cli(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    args: list[str],
    env: dict[str, str] | None = None,
) -> tuple[int, str, str]:
    """Run the CLI in-process; return (code, stdout, stderr). Mirrors the
    capsys pattern from test_cli.py because Rich binds its console at
    import time, so contextlib.redirect_stdout cannot capture it."""
    for key, value in (env or {}).items():
        monkeypatch.setenv(key, value)
    from tracefield.cli.main import run

    monkeypatch.setattr(sys, "argv", ["tracefield", *args])
    capsys.readouterr()  # discard prior output
    code: int | None = None
    try:
        run()
    except SystemExit as exc:
        raw = exc.code
        code = raw if isinstance(raw, int) else (0 if raw is None else 1)
    captured = capsys.readouterr()
    return (code if code is not None else 0), captured.out, captured.err


# ---------------------------------------------------------------------------
# Unit-level: domain invariants
# ---------------------------------------------------------------------------


class TestDomainInvariants:
    def test_alias_normalization_is_deterministic_and_lexical(self) -> None:
        assert normalize_alias("  Jane   Q. ") == "jane q."
        assert normalize_alias("Jane Q.") == normalize_alias("  jane   q.  ")
        # NFKC folds compatibility characters (fullwidth -> ascii).
        assert normalize_alias("ＪＡＮＥ") == "jane"  # noqa: RUF001 — fullwidth chars are the test
        # Purely lexical: normalization says nothing about identity.
        assert normalize_alias("Bob") != normalize_alias("Robert")

    def test_entity_ids_are_stable_and_prefixed(self) -> None:
        ids = {Entity(case_id="c", canonical_label="x").id for _ in range(50)}
        assert len(ids) == 50
        assert all(i.startswith("ent_") and len(i) == 20 for i in ids)

    def test_mention_class_values(self) -> None:
        from tracefield.core.entities import MentionClass

        assert {m.value for m in MentionClass} == {"exact", "stated", "inferred"}


# ---------------------------------------------------------------------------
# Migration tests (schema v3)
# ---------------------------------------------------------------------------


@contextmanager
def raw_v2_database(path):
    """Build a genuine schema-v2 database via the committed v1+v2 scripts,
    populate it with records, and leave the file for Database() to open."""

    from tracefield.storage.database import _MIGRATION_1, _MIGRATION_2

    conn = sqlite3.connect(path)
    try:
        conn.executescript(_MIGRATION_1)
        conn.executescript(_MIGRATION_2)
        conn.execute(
            "INSERT INTO cases(id,title,purpose,scope,created_at,updated_at) VALUES(?,?,?,?,?,?)",
            (
                "case_v2aabbccddeeff01",
                "v2 case",
                "p",
                "s",
                "2026-01-01T00:00:00Z",
                "2026-01-01T00:00:00Z",
            ),
        )
        conn.execute(
            "INSERT INTO sources(id,case_id,locator,first_seen_at) VALUES(?,?,?,?)",
            (
                "src_v2aabbccddeeff01",
                "case_v2aabbccddeeff01",
                "https://example.com/v2",
                "2026-01-01T00:00:00Z",
            ),
        )
        conn.execute(
            "INSERT INTO claims(id,case_id,text,created_at) VALUES(?,?,?,?)",
            ("clm_v2aabbccddeeff01", "case_v2aabbccddeeff01", "v2 claim", "2026-01-01T00:00:00Z"),
        )
        conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','2')")
        conn.commit()
    finally:
        conn.close()
    yield path


class TestMigration:
    def test_fresh_database_is_schema_v3(self, settings) -> None:
        db = Database(settings.db_path)
        try:
            assert db.schema_version == 3 == SCHEMA_VERSION
            tables = {
                r["name"]
                for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            }
            assert {
                "entities",
                "entity_aliases",
                "entity_mentions",
                "entity_match_candidates",
            } <= tables
        finally:
            db.close()

    def test_populated_v2_database_migrates_and_preserves_records(self, settings, tmp_path) -> None:
        path = tmp_path / "v2.sqlite3"
        with raw_v2_database(path):
            db = Database(path)
            try:
                assert db.schema_version == 3
                # v2 records survive byte-for-byte.
                src = db.execute("SELECT * FROM sources WHERE id='src_v2aabbccddeeff01'").fetchone()
                assert src is not None and src["locator"] == "https://example.com/v2"
                claim = db.execute(
                    "SELECT * FROM claims WHERE id='clm_v2aabbccddeeff01'"
                ).fetchone()
                assert claim is not None and claim["text"] == "v2 claim"
                # Entity tables exist and are usable.
                assert db.execute("SELECT COUNT(*) FROM entities").fetchone()[0] == 0
            finally:
                db.close()

    def test_reopen_is_idempotent(self, settings) -> None:
        db = Database(settings.db_path)
        db.close()
        db2 = Database(settings.db_path)
        try:
            assert db2.schema_version == 3
        finally:
            db2.close()

    def test_partial_migration_recovers(self, settings) -> None:
        """Simulate an interrupted v3 migration: the script partially ran
        (one table exists) but the version was never stamped. Reopening
        must complete cleanly because every step is IF NOT EXISTS."""

        db = Database(settings.db_path)
        db.close()
        conn = sqlite3.connect(settings.db_path)
        try:
            # Partial application: entities table exists, version NOT bumped.
            conn.execute(
                "CREATE TABLE IF NOT EXISTS entities "
                "(id TEXT PRIMARY KEY, case_id TEXT NOT NULL, entity_type TEXT, "
                "canonical_label TEXT, notes TEXT, created_at TEXT, updated_at TEXT)"
            )
            conn.commit()
        finally:
            conn.close()
        db2 = Database(settings.db_path)
        try:
            assert db2.schema_version == 3
            # The real (constrained) table is in place.
            cols = [r["name"] for r in db2.execute("PRAGMA table_info(entities)").fetchall()]
            assert "entity_type" in cols
        finally:
            db2.close()

    def test_case_deletion_cascades_entities(self, db, case_factory) -> None:
        from tracefield.storage.repositories import (
            EntityAliasRepo,
            EntityMatchRepo,
            EntityMentionRepo,
            EntityRepo,
        )

        case = case_factory("cascade")
        other = case_factory("survivor")
        entity = Entity(case_id=case.id, canonical_label="gone")
        EntityRepo(db).add(entity)
        alias = EntityAlias(
            case_id=case.id,
            entity_id=entity.id,
            alias="gone alias",
            normalized=normalize_alias("gone alias"),
        )
        EntityAliasRepo(db).add(alias)
        # A same-case record so the mention reference is valid.
        from tracefield.core.domain import Source
        from tracefield.storage.repositories import SourceRepo

        source = Source(case_id=case.id, locator="https://example.com/cascade")
        SourceRepo(db).add(source)
        EntityMentionRepo(db).add(
            EntityMention(case_id=case.id, entity_id=entity.id, record_id=source.id)
        )
        second = Entity(case_id=case.id, canonical_label="gone two")
        EntityRepo(db).add(second)
        EntityMatchRepo(db).add(
            EntityMatchCandidate(case_id=case.id, entity_a_id=entity.id, entity_b_id=second.id)
        )
        survivor = Entity(case_id=other.id, canonical_label="survivor")
        EntityRepo(db).add(survivor)

        from tracefield.storage.repositories import CaseRepo

        CaseRepo(db).delete(case.id)

        assert EntityRepo(db).list_for_case(case.id) == []
        assert EntityAliasRepo(db).list_for_entity(entity.id) == []
        assert EntityMentionRepo(db).list_for_entity(entity.id) == []
        assert EntityMatchRepo(db).list_for_case(case.id) == []
        # The unrelated case is untouched.
        assert [e.id for e in EntityRepo(db).list_for_case(other.id)] == [survivor.id]


# ---------------------------------------------------------------------------
# DB-level integrity triggers (via repositories)
# ---------------------------------------------------------------------------


class TestIntegrityTriggers:
    def test_cross_case_mention_refused(self, db, case_factory) -> None:
        from tracefield.storage.repositories import EntityMentionRepo, EntityRepo

        case_a = case_factory("case-a")
        case_b = case_factory("case-b")
        entity_b = Entity(case_id=case_b.id, canonical_label="B")
        EntityRepo(db).add(entity_b)
        # entity_b exists, but in another case -> trigger must refuse.
        with pytest.raises(Exception, match="same case"):
            EntityMentionRepo(db).add(
                EntityMention(case_id=case_a.id, entity_id=entity_b.id, record_id="clm_x")
            )

    def test_dangling_mention_record_refused(self, db, case_factory) -> None:
        from tracefield.storage.repositories import EntityMentionRepo, EntityRepo

        case = case_factory("dangling")
        entity = Entity(case_id=case.id, canonical_label="D")
        EntityRepo(db).add(entity)
        with pytest.raises(Exception, match="record in the same case"):
            EntityMentionRepo(db).add(
                EntityMention(case_id=case.id, entity_id=entity.id, record_id="clm_nope00deadbeef")
            )

    def test_mention_referenceing_real_records_succeeds(self, db, case_factory) -> None:
        """Each polymorphic record type must be accepted when real + in-case."""
        from tracefield.core.domain import Assertion, Claim, Observation, Source
        from tracefield.storage.repositories import (
            AssertionRepo,
            ClaimRepo,
            EntityMentionRepo,
            EntityRepo,
            ObservationRepo,
            SourceRepo,
        )

        case = case_factory("mentions-ok")
        entity = Entity(case_id=case.id, canonical_label="M")
        EntityRepo(db).add(entity)
        source = Source(case_id=case.id, locator="https://example.com/m")
        SourceRepo(db).add(source)
        claim = Claim(case_id=case.id, text="a claim")
        ClaimRepo(db).add(claim)
        obs = Observation(case_id=case.id, tool_name="test-tool", summary="an observation")
        ObservationRepo(db).add(obs)
        asr = Assertion(case_id=case.id, claim_id=claim.id, statement="an assertion")
        AssertionRepo(db).add(asr)
        for record_id in (source.id, claim.id, obs.id, asr.id):
            mention = EntityMentionRepo(db).add(
                EntityMention(case_id=case.id, entity_id=entity.id, record_id=record_id)
            )
            assert mention.record_id == record_id

    def test_duplicate_alias_refused_case_scoped(self, db, case_factory) -> None:
        from tracefield.storage.repositories import (
            EntityAliasRepo,
            EntityRepo,
            RepositoryError,
        )

        case = case_factory("alias-dup")
        entity = Entity(case_id=case.id, canonical_label="Jane Q.")
        EntityRepo(db).add(entity)
        EntityAliasRepo(db).add(
            EntityAlias(
                case_id=case.id,
                entity_id=entity.id,
                alias="Jane",
                normalized=normalize_alias("Jane"),
            )
        )
        with pytest.raises(RepositoryError, match="UNIQUE"):
            EntityAliasRepo(db).add(
                EntityAlias(
                    case_id=case.id,
                    entity_id=entity.id,
                    alias="  jane  ",
                    normalized=normalize_alias("  jane  "),
                )
            )

    def test_alias_on_other_case_same_entity_refused(self, db, case_factory) -> None:
        """An alias row pointing at another case's entity must be refused."""
        from tracefield.storage.repositories import EntityAliasRepo, EntityRepo

        case_a = case_factory("alias-a")
        case_b = case_factory("alias-b")
        entity_b = Entity(case_id=case_b.id, canonical_label="B-entity")
        EntityRepo(db).add(entity_b)
        with pytest.raises(Exception, match="same case"):
            EntityAliasRepo(db).add(
                EntityAlias(
                    case_id=case_a.id,
                    entity_id=entity_b.id,
                    alias="B",
                    normalized=normalize_alias("B"),
                )
            )

    def test_self_match_refused(self, db, case_factory) -> None:
        from tracefield.storage.repositories import EntityMatchRepo, RepositoryError

        case = case_factory("self-match")
        entity = Entity(case_id=case.id, canonical_label="S")
        from tracefield.storage.repositories import EntityRepo

        EntityRepo(db).add(entity)
        with pytest.raises(RepositoryError, match="endpoints"):
            EntityMatchRepo(db).add(
                EntityMatchCandidate(case_id=case.id, entity_a_id=entity.id, entity_b_id=entity.id)
            )

    def test_match_pair_canonicalized_and_lookup_unordered(self, db, case_factory) -> None:
        from tracefield.storage.repositories import EntityMatchRepo, EntityRepo

        case = case_factory("pair-order")
        e1 = Entity(case_id=case.id, canonical_label="aaa")
        e2 = Entity(case_id=case.id, canonical_label="bbb")
        repo = EntityRepo(db)
        repo.add(e1)
        repo.add(e2)
        high, low = max(e1.id, e2.id), min(e1.id, e2.id)
        stored = EntityMatchRepo(db).add(
            EntityMatchCandidate(case_id=case.id, entity_a_id=high, entity_b_id=low)
        )
        # Canonical order is enforced regardless of input order.
        assert (stored.entity_a_id, stored.entity_b_id) == (low, high)
        found = EntityMatchRepo(db).find_unordered_pair(case.id, high, low)
        assert found is not None and found.id == stored.id

    def test_cross_case_match_refused(self, db, case_factory) -> None:
        from tracefield.storage.repositories import EntityMatchRepo, EntityRepo

        case_a = case_factory("match-a")
        case_b = case_factory("match-b")
        repo = EntityRepo(db)
        ea = Entity(case_id=case_a.id, canonical_label="A")
        eb = Entity(case_id=case_b.id, canonical_label="B")
        repo.add(ea)
        repo.add(eb)
        with pytest.raises(Exception, match="same case"):
            EntityMatchRepo(db).add(
                EntityMatchCandidate(case_id=case_a.id, entity_a_id=ea.id, entity_b_id=eb.id)
            )

    def test_malformed_labels_accepted_verbatim_but_escaped_in_reports(
        self, db, case_factory
    ) -> None:
        """DB never interprets label content; reporting must escape it."""
        from tracefield.storage.repositories import EntityRepo

        case = case_factory("labels")
        malicious = '<script>alert("x")</script> & "quotes"'
        entity = Entity(case_id=case.id, canonical_label=malicious)
        EntityRepo(db).add(entity)
        assert EntityRepo(db).get(entity.id).canonical_label == malicious  # round-trip


# ---------------------------------------------------------------------------
# CLI flows
# ---------------------------------------------------------------------------


@pytest.fixture()
def cli_env(tf_home: Path) -> dict[str, str]:
    return {
        "TRACEFIELD_REPORT_AUTHOR": "tester",
    }


class TestCliEntityFlow:
    def _case_id(self, out: str) -> str:
        import re

        m = re.search(r"case_[0-9a-f]{16}", out)
        assert m, out
        return m.group(0)

    def _create_case(self, monkeypatch, capsys) -> str:
        code, out, err = run_cli(
            monkeypatch,
            capsys,
            ["case", "create", "cli-case", "--purpose", "p", "--scope", "s"],
        )
        assert code == 0, (out, err)
        return self._case_id(out + err)

    def _entity_id(self, monkeypatch, capsys, case: str, label: str) -> str:
        import re

        code, out, err = run_cli(
            monkeypatch,
            capsys,
            ["entity", "add", "--label", label, "--case", case, "--type", "person"],
        )
        assert code == 0, (out, err)
        m = re.search(r"ent_[0-9a-f]{16}", out)
        assert m, out
        return m.group(0)

    def test_full_flow_add_alias_mention_match_review(self, monkeypatch, cli_env, capsys) -> None:
        case = self._create_case(monkeypatch, capsys)
        ent_a = self._entity_id(monkeypatch, capsys, case, "Jane Q. Example")
        ent_b = self._entity_id(monkeypatch, capsys, case, "Jane Q")

        # Alias.
        code, out, err = run_cli(
            monkeypatch,
            capsys,
            ["entity", "alias", "--entity", ent_a, "--alias", "Jane Doe", "--case", case],
            cli_env,
        )
        assert code == 0, (out, err)
        assert "added alias" in out

        # Duplicate alias refused with exit 3.
        code, out, err = run_cli(
            monkeypatch,
            capsys,
            ["entity", "alias", "--entity", ent_a, "--alias", "jane   doe", "--case", case],
            cli_env,
        )
        assert code == EXIT_USAGE, (out, err)
        assert "duplicates are refused" in out + err

        # Alias equal to canonical label refused.
        code, out, err = run_cli(
            monkeypatch,
            capsys,
            ["entity", "alias", "--entity", ent_a, "--alias", "Jane Q. Example", "--case", case],
            cli_env,
        )
        assert code == EXIT_USAGE, (out, err)
        assert "identical to the canonical label" in out + err

        # Mention requires an existing record: create evidence first.
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as fh:
            fh.write(b"note")
            path = fh.name
        code, out, err = run_cli(
            monkeypatch,
            capsys,
            ["evidence", "attach", path, "--case", case],
            cli_env,
        )
        assert code == 0, (out, err)
        import re as _re

        m = _re.search(r"ev_[0-9a-f]{16}", out + err)
        assert m, (out, err)
        ev_id = m.group(0)
        code, out, err = run_cli(
            monkeypatch,
            capsys,
            [
                "entity",
                "mention",
                "--entity",
                ent_a,
                "--record",
                ev_id,
                "--case",
                case,
                "--class",
                "exact",
            ],
            cli_env,
        )
        assert code == 0, (out, err)
        assert "added mention" in out

        # Dangling record refused (exit 3, message names the constraint).
        code, out, err = run_cli(
            monkeypatch,
            capsys,
            ["entity", "mention", "--entity", ent_a, "--record", "src_nope00dead", "--case", case],
            cli_env,
        )
        assert code == EXIT_USAGE, (out, err)
        flat = " ".join((out + err).split())
        assert "must reference a record in the same case" in flat

        # Match: self refused, cross refused, valid filed once.
        code, out, err = run_cli(
            monkeypatch,
            capsys,
            ["entity", "match", "--a", ent_a, "--b", ent_a, "--case", case],
            cli_env,
        )
        assert code == EXIT_USAGE, (out, err)
        code, out, err = run_cli(
            monkeypatch,
            capsys,
            ["entity", "match", "--a", ent_a, "--b", ent_b, "--case", case, "--rationale", "r"],
            cli_env,
        )
        assert code == 0, (out, err)
        import re as _re2

        m = _re2.search(r"emc_[0-9a-f]{16}", out + err)
        assert m, (out, err)
        match_id = m.group(0)
        code, out, err = run_cli(
            monkeypatch,
            capsys,
            ["entity", "match", "--a", ent_b, "--b", ent_a, "--case", case],
            cli_env,
        )
        assert code == EXIT_USAGE, (out, err)
        assert "already exists" in out + err

        # Review: invalid state exit 3; rejected retained; nothing merged.
        code, out, err = run_cli(
            monkeypatch,
            capsys,
            ["entity", "review", "--match", match_id, "--case", case, "--state", "maybe"],
            cli_env,
        )
        assert code == EXIT_USAGE, (out, err)
        code, out, err = run_cli(
            monkeypatch,
            capsys,
            [
                "entity",
                "review",
                "--match",
                match_id,
                "--case",
                case,
                "--state",
                "rejected",
                "--note",
                "different people",
            ],
            cli_env,
        )
        assert code == 0, (out, err)
        assert "rejected" in out

        # Not-found exits.
        code, out, err = run_cli(
            monkeypatch, capsys, ["entity", "show", "ent_0000000000000000", "--case", case], cli_env
        )
        assert code == EXIT_NOT_FOUND, (out, err)
        code, out, err = run_cli(
            monkeypatch,
            capsys,
            [
                "entity",
                "review",
                "--match",
                "emc_0000000000000000",
                "--case",
                case,
                "--state",
                "confirmed",
            ],
            cli_env,
        )
        assert code == EXIT_NOT_FOUND, (out, err)

        # Invalid type / class exit 3.
        code, out, err = run_cli(
            monkeypatch,
            capsys,
            ["entity", "add", "--label", "x", "--case", case, "--type", "dragon"],
            cli_env,
        )
        assert code == EXIT_USAGE, (out, err)
        code, out, err = run_cli(
            monkeypatch,
            capsys,
            [
                "entity",
                "mention",
                "--entity",
                ent_a,
                "--record",
                ev_id,
                "--case",
                case,
                "--class",
                "guessed",
            ],
            cli_env,
        )
        assert code == EXIT_USAGE, (out, err)

        # Nothing was merged: both entities still exist.
        code, out, err = run_cli(
            monkeypatch, capsys, ["entity", "list", "--case", case, "--json"], cli_env
        )
        assert code == 0, (out, err)
        entities = json.loads(out)
        assert len(entities) == 2

    def test_events_recorded_and_chain_verifies(
        self, monkeypatch, cli_env, capsys, settings
    ) -> None:
        case = self._create_case(monkeypatch, capsys)
        ent_a = self._entity_id(monkeypatch, capsys, case, "Alice")
        ent_b = self._entity_id(monkeypatch, capsys, case, "Bob")
        code, out, err = run_cli(
            monkeypatch,
            capsys,
            ["entity", "match", "--a", ent_a, "--b", ent_b, "--case", case],
            cli_env,
        )
        assert code == 0, (out, err)
        import re

        match_id = re.search(r"emc_[0-9a-f]{16}", out + err).group(0)
        code, out, err = run_cli(
            monkeypatch,
            capsys,
            ["entity", "review", "--match", match_id, "--case", case, "--state", "unresolved"],
            cli_env,
        )
        assert code == 0, (out, err)

        code, out, err = run_cli(
            monkeypatch, capsys, ["analyze", "events", "--case", case, "--json"], cli_env
        )
        assert code == 0, (out, err)
        events = json.loads(out)["events"]
        actions = [e["action"] for e in events]
        assert actions.count("entity.add") == 2
        assert "entity.match.add" in actions
        assert "entity.match.review" in actions

        from tracefield.storage.repositories import EventRepo

        db = Database(settings.db_path)
        try:
            ok, detail = EventRepo(db).verify_chain(case)
            assert ok, detail
        finally:
            db.close()

    def test_cross_case_entity_hidden_from_other_case_cli(
        self, monkeypatch, cli_env, capsys
    ) -> None:
        case_a = self._create_case(monkeypatch, capsys)
        ent = self._entity_id(monkeypatch, capsys, case_a, "Hidden")
        code, out, err = run_cli(
            monkeypatch,
            capsys,
            ["case", "create", "cli-case-2", "--purpose", "p", "--scope", "s"],
        )
        case_b = self._case_id(out + err)
        code, out, err = run_cli(
            monkeypatch, capsys, ["entity", "show", ent, "--case", case_b], cli_env
        )
        assert code == EXIT_NOT_FOUND, (out, err)


# ---------------------------------------------------------------------------
# Reporting: Entities section honesty, escaping, determinism
# ---------------------------------------------------------------------------


class TestReportingEntities:
    def _payload(self, settings, case):
        from tracefield.reporting.build import build_case_payload

        db = Database(settings.db_path)
        try:
            return build_case_payload(settings, db, case)
        finally:
            db.close()

    def test_payload_includes_entities_and_counts(self, db, case_factory, settings) -> None:
        from tracefield.storage.repositories import EntityRepo

        case = case_factory("report-entities")
        entity = Entity(case_id=case.id, canonical_label="Reported Entity")
        EntityRepo(db).add(entity)
        payload = self._payload(settings, case)
        assert payload["report_schema_version"] == 4
        assert [e["id"] for e in payload["entities"]] == [entity.id]
        assert payload["counts"]["entities"] == 1
        assert payload["entities"][0]["canonical_label"] == "Reported Entity"

    def test_payload_deterministic(self, db, case_factory, settings) -> None:
        from tracefield.storage.repositories import (
            EntityAliasRepo,
            EntityRepo,
        )

        case = case_factory("report-determinism")
        entity = Entity(case_id=case.id, canonical_label="Deterministic")
        EntityRepo(db).add(entity)
        EntityAliasRepo(db).add(
            EntityAlias(
                case_id=case.id,
                entity_id=entity.id,
                alias="Det",
                normalized=normalize_alias("Det"),
            )
        )
        first = self._payload(settings, case)["entities"]
        second = self._payload(settings, case)["entities"]
        assert first == second
        assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)

    def test_markdown_and_html_sections_with_honesty_and_escaping(
        self, db, case_factory, settings
    ) -> None:
        from tracefield.reporting.build import render_html, render_markdown
        from tracefield.storage.repositories import (
            EntityAliasRepo,
            EntityMatchRepo,
            EntityRepo,
        )

        case = case_factory("report-render")
        sneaky = Entity(case_id=case.id, canonical_label="<script>alert(1)</script>")
        EntityRepo(db).add(sneaky)
        EntityAliasRepo(db).add(
            EntityAlias(
                case_id=case.id,
                entity_id=sneaky.id,
                alias="<b>bold</b>",
                normalized=normalize_alias("<b>bold</b>"),
            )
        )
        second = Entity(case_id=case.id, canonical_label="Second")
        EntityRepo(db).add(second)
        match = EntityMatchRepo(db).add(
            EntityMatchCandidate(case_id=case.id, entity_a_id=sneaky.id, entity_b_id=second.id)
        )
        EntityMatchRepo(db).review(match.id, ReviewState.CONFIRMED, "same subject")
        payload = self._payload(settings, case)

        md = render_markdown(payload)
        assert "## Entities" in md
        assert "recorded analytical objects" in md
        assert "not established" in md
        assert "nothing is merged" in md
        assert f"`{sneaky.id}`" in md
        assert "<script>alert(1)</script>" in md  # markdown shows the recorded source text
        assert f"`{match.id}`" in md and "review: confirmed" in md

        html = render_html(payload)
        assert "<h2>Entities</h2>" in html
        # Malicious label must be escaped: no raw <script> tag survives.
        assert "<script>alert(1)</script>" not in html
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
        assert "&lt;b&gt;bold&lt;/b&gt;" in html
        assert "confirmed" in html

    def test_report_without_entities_has_no_entities_section(
        self, db, case_factory, settings
    ) -> None:
        from tracefield.reporting.build import render_html, render_markdown

        case = case_factory("report-empty")
        payload = self._payload(settings, case)
        assert payload["entities"] == []
        assert "## Entities" not in render_markdown(payload)
        assert "<h2>Entities</h2>" not in render_html(payload)

    def test_html_report_is_still_selfcontained_no_script_tag(
        self, db, case_factory, settings
    ) -> None:
        """Regression guard: entity content must not introduce executable HTML."""
        from tracefield.reporting.build import render_html
        from tracefield.storage.repositories import EntityRepo

        case = case_factory("report-nojs")
        EntityRepo(db).add(Entity(case_id=case.id, canonical_label="<img src=x onerror=alert(1)>"))
        payload = self._payload(settings, case)
        html = render_html(payload)
        assert "<script" not in html.lower()
        assert "onerror" in html and "<img" not in html.replace("&#x", "")
