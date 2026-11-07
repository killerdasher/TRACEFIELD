"""B-02 ingest suite against the REAL version-pinned Sherlock fixture.

Contract: ``TRACEFIELD_02_PRODUCT_DIRECTION.md`` B-02 + R-SEC-1..8; fixture
facts (v0.16.2, capture date, sha256) are pinned in
``docs/ingest/SHERLOCK_CSV_SCHEMA.md``. The fixture is loaded read-only —
these tests never run Sherlock and never touch the network.
"""

from __future__ import annotations

import hashlib
import json
import socket
import urllib.request
from pathlib import Path

import pytest

from tracefield.core.domain import Case, Source
from tracefield.ingest import (
    CrossCaseRefusal,
    FormatIdentity,
    IngestRefusal,
    OversizedFileRefusal,
    UnmappableFormatRefusal,
    UnsupportedMajorVersionRefusal,
    ZeroRowsRefusal,
    detect_format,
    run_import,
)
from tracefield.ingest.errors import RowShapeRefusal
from tracefield.ingest.registry import require_supported_version
from tracefield.ingest.sherlock_csv import SHERLOCK_CSV_HEADER, parse_sherlock_csv
from tracefield.storage.repositories import CaseRepo, EvidenceRepo, ObservationRepo, SourceRepo

pytestmark = pytest.mark.unit

FIXTURE = (
    Path(__file__).parents[1]
    / "fixtures"
    / "ingest"
    / "sherlock_v0.16.2_killerdasher_2026-11-07.csv"
)
FIXTURE_SHA256 = (  # sha256 recorded in docs/ingest/SHERLOCK_CSV_SCHEMA.md
    "29309604564665664f9757623b9ee67f63f08bd5c61c25a01da708b791d62add"
)
EXPECTED_ROWS = 10  # capture 2026-11-07: 10 claimed rows (console count matched)


# ---------------------------------------------------------------------------
# positive: the true fixture loads and maps verbatim
# ---------------------------------------------------------------------------
class TestFixtureLoad:
    def test_fixture_bytes_are_the_recorded_capture(self) -> None:
        content = FIXTURE.read_bytes()

        assert hashlib.sha256(content).hexdigest() == FIXTURE_SHA256
        assert b"\r\n" in content  # CRLF line endings, byte-level fact

    def test_full_import_of_the_true_fixture(self, settings, db, case_factory) -> None:
        case = case_factory("ingest-fixture")
        res = run_import(settings, db, case, FIXTURE)
        assert res.row_count == EXPECTED_ROWS
        assert res.evidence_sha256 == FIXTURE_SHA256
        assert res.extra_columns == []
        assert res.declared_version == ""  # the file declares no version

        rows = list(db.execute("SELECT * FROM evidence WHERE case_id=?", (case.id,)))
        assert len(rows) == 1
        assert rows[0]["sha256"] == FIXTURE_SHA256

    def test_observations_map_rows_verbatim(self, settings, db, case_factory) -> None:
        case = case_factory("ingest-obs")
        run_import(settings, db, case, FIXTURE)
        obs = ObservationRepo(db).list_for_case(case.id)
        assert len(obs) == EXPECTED_ROWS
        assert all(o.tool_name == "sherlock" for o in obs)
        assert all(o.tool_version == "unknown" for o in obs)  # R-SEC-4

        github = next(o for o in obs if "GitHub" in o.summary)
        assert "exists=Claimed" in github.summary
        assert "http_status=200" in github.summary
        # raw_ref points INTO the immutable copy, not a duplicate of it
        gh_row = parse_sherlock_csv(FIXTURE).rows[4]  # fixture row 5 of 10 data rows
        assert gh_row.name == "GitHub"
        assert github.raw_ref.endswith(f"#row={gh_row.row_no}")

        # the copied bytes are the original bytes (raw-first, not reconstructed)
        ev = EvidenceRepo(db).list_for_case(case.id)[0]
        stored = (settings.cases_root / case.id / ev.storage_ref).read_bytes()
        assert stored == FIXTURE.read_bytes()

    def test_row_shapes_are_not_reformatted(self) -> None:
        parsed = parse_sherlock_csv(FIXTURE)
        assert parsed.extra_columns == ()
        xbox = next(r for r in parsed.rows if r.name == "Xbox Gamertag")
        assert xbox.url_user == "https://xboxgamertag.com/search/killerdasher"
        assert xbox.response_time_s.startswith("12.")  # verbatim float text
        assert xbox.exists == "Claimed"
        assert xbox.http_status == "200"


# ---------------------------------------------------------------------------
# the five refusal pre-conditions (fail-closed, zero partial writes)
# ---------------------------------------------------------------------------
def _counts(db, case_id: str) -> tuple[int, int, int]:
    ev = db.execute("SELECT COUNT(*) c FROM evidence WHERE case_id=?", (case_id,)).fetchone()["c"]
    ob = db.execute(
        "SELECT COUNT(*) c FROM observations WHERE case_id=?", (case_id,)
    ).fetchone()["c"]
    sr = db.execute("SELECT COUNT(*) c FROM sources WHERE case_id=?", (case_id,)).fetchone()["c"]
    return ev, ob, sr


class TestRefusals:
    def test_oversized_file_refused_before_parse(
        self, settings, db, case_factory, tmp_path
    ) -> None:
        case = case_factory("oversize")
        big = tmp_path / "big.csv"
        big.write_text("x" * 2048)  # any bytes; cap is checked pre-parse
        settings.max_fetch_bytes = 1024
        with pytest.raises(OversizedFileRefusal):
            run_import(settings, db, case, big)
        assert _counts(db, case.id) == (0, 0, 0)  # nothing partially imported

    def test_unmappable_format_refused_with_named_cause(
        self, settings, db, case_factory, tmp_path
    ) -> None:
        case = case_factory("unmappable")
        bad = tmp_path / "bad.csv"
        bad.write_text("a,b,c\n1,2,3\n", newline="")
        with pytest.raises(UnmappableFormatRefusal) as excinfo:
            run_import(settings, db, case, bad)
        assert "no ingest format matches header" in str(excinfo.value)
        assert "known formats" in str(excinfo.value)  # names the register
        with pytest.raises(UnmappableFormatRefusal):
            detect_format(str(bad))
        assert _counts(db, case.id) == (0, 0, 0)

    def test_declared_but_unsupported_major_version_refused(self) -> None:
        with pytest.raises(UnsupportedMajorVersionRefusal) as excinfo:
            require_supported_version(
                FormatIdentity(format_name="sherlock_csv", declared_version="9.1")
            )
        assert "declares version 9.1" in str(excinfo.value)
        assert "partial import is not permitted" in str(excinfo.value)
        # absent version is NOT a refusal case (R-SEC-3 amendment)
        require_supported_version(FormatIdentity(format_name="sherlock_csv"))

    def test_cross_case_import_refused(self, settings, db, case_factory, tmp_path) -> None:

        case_a = case_factory("case-a")
        case_b = CaseRepo(db).create(Case(title="case-b", purpose="", scope=""))
        foreign = SourceRepo(db).add(
            Source(case_id=case_b.id, locator=str(tmp_path / "owned-by-b"))
        )
        with pytest.raises(CrossCaseRefusal) as excinfo:
            run_import(settings, db, case_a, FIXTURE, source_id=foreign.id)
        assert "belongs to case" in str(excinfo.value)
        # the foreign case is untouched, and so is case A
        assert _counts(db, case_a.id) == (0, 0, 0)
        assert len(EvidenceRepo(db).list_for_case(case_b.id)) == 0

    def test_zero_rows_refused(self, settings, db, case_factory, tmp_path) -> None:
        case = case_factory("zero")
        empty = tmp_path / "empty.csv"
        empty.write_text(",".join(SHERLOCK_CSV_HEADER) + "\r\n", newline="")
        with pytest.raises(ZeroRowsRefusal) as excinfo:
            run_import(settings, db, case, empty)
        assert "zero data rows" in str(excinfo.value)
        assert _counts(db, case.id) == (0, 0, 0)

    def test_missing_required_column_refused(self, settings, db, case_factory, tmp_path) -> None:
        """A mutated fixture that REMOVES a known column is not additive.
        The refusal may come from detect_format (header no longer matches
        any register entry) or from the parser — either way: fail-closed,
        zero partial writes."""
        case = case_factory("missing-col")
        lines = FIXTURE.read_text(encoding="utf-8").splitlines()
        header = lines[0].split(",")
        col = header.index("response_time_s")
        body = [",".join(h for i, h in enumerate(header) if i != col)]
        body += [",".join(v for i, v in enumerate(line.split(",")) if i != col) for line in lines[1:]]
        mutated = tmp_path / "mutated.csv"
        mutated.write_text("\r\n".join(body) + "\r\n", newline="")
        with pytest.raises(IngestRefusal) as excinfo:
            run_import(settings, db, case, mutated)
        # detect_format refuses with the observed header named
        assert "no ingest format matches header" in str(excinfo.value)
        assert "http_status" not in str(excinfo.value).split("header")[0]
        assert _counts(db, case.id) == (0, 0, 0)

    def test_parser_rejects_missing_and_reordered_headers_directly(
        self, tmp_path
    ) -> None:
        """Second line of defense: the parser itself fails closed when
        called directly on a non-additive mutation."""
        seven_missing = tmp_path / "seven.csv"

        seven_missing.write_text("a,b,c\n1,2,3\n", newline="")
        with pytest.raises(RowShapeRefusal, match="does not carry the required columns"):
            parse_sherlock_csv(seven_missing)

        lines = FIXTURE.read_text(encoding="utf-8").splitlines()
        reordered = tmp_path / "reordered.csv"
        fields = lines[0].split(",")
        swapped = [fields[1], fields[0], *fields[2:]]  # username/name swapped
        reordered.write_text(",".join(swapped) + "\r\n" + lines[1] + "\r\n", newline="")
        with pytest.raises(RowShapeRefusal, match="not in canonical order"):
            parse_sherlock_csv(reordered)


# ---------------------------------------------------------------------------
# positive absent-version → unknown + integrity + hygiene pins
# ---------------------------------------------------------------------------
class TestPins:
    def test_hash_chain_closure_across_ingest_events(self, settings, db, case_factory) -> None:
        from tracefield.core.provenance import compute_event_digest

        case = case_factory("chain")
        run_import(settings, db, case, FIXTURE)
        run_import(settings, db, case, FIXTURE)  # second import → second event
        rows = db.execute(
            "SELECT * FROM analysis_events WHERE case_id=? ORDER BY occurred_at, rowid",
            (case.id,),
        ).fetchall()
        assert rows, "events must exist"
        prev = ""
        for r in rows:
            recomputed = compute_event_digest(
                r["action"],
                json.loads(r["inputs"]),
                json.loads(r["outputs"]),
                r["prev_digest"],
                r["occurred_at"],
            )
            assert r["digest"] == recomputed, f"digest broken at {r['action']}"
            assert r["prev_digest"] == prev, f"chain link broken at {r['action']}"
            prev = recomputed
        actions = [r["action"] for r in rows]
        assert actions[0] == "evidence.attach"  # workspace chain comes first
        assert "ingest.file" in actions

    def test_zero_egress_pin(
        self, settings, db, case_factory, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """R-SEC-6: import performs no fetch — any socket/urlopen use fails
        the test loudly; the import itself must still succeed."""

        class _Forbidden(Exception):
            pass

        def _no_socket(*a, **k):  # type: ignore[no-untyped-def]
            raise _Forbidden("egress attempted during import")

        monkeypatch.setattr(socket, "socket", _no_socket)
        monkeypatch.setattr(urllib.request, "urlopen", _no_socket)
        case = case_factory("zero-egress")
        res = run_import(settings, db, case, FIXTURE)
        assert res.row_count == EXPECTED_ROWS

    def test_echo_sanitation_secret_values_never_reach_excerpts_or_summaries(
        self, settings, db, case_factory, tmp_path, capsys
    ) -> None:
        """R-SEC-5: a secret-carrying locator stays in the immutable copy;
        summaries, excerpts, and the import path never echo it."""
        case = case_factory("echo")
        secret = "SECRETTOKEN9a4f"
        hostile = tmp_path / "hostile.csv"
        header = ",".join(SHERLOCK_CSV_HEADER)
        rows_txt = (
            f"killerdasher,Probe,https://probe.test/,"
            f"https://probe.test/u/killerdasher?token={secret},Claimed,200,0.5\r\n"
            "killerdasher,GitHub,https://www.github.com/,https://www.github.com/killerdasher,Claimed,200,0.6\r\n"
        )
        hostile.write_text(header + "\r\n" + rows_txt, newline="")
        res = run_import(settings, db, case, hostile)
        assert res.row_count == 2

        out = capsys.readouterr()  # nothing printed anyway; assert on DB side
        del out
        obs = ObservationRepo(db).list_for_case(case.id)
        summaries = "\n".join(o.summary for o in obs)
        excerpts = [e.excerpt for e in EvidenceRepo(db).list_for_case(case.id)]
        assert secret not in summaries
        assert "probe.test/u" not in summaries  # locators live in the copy only
        assert all(secret not in x for x in excerpts)

        # raw-first: the immutable copy DOES contain the raw row (by design)
        ev = EvidenceRepo(db).list_for_case(case.id)[0]
        stored = (settings.cases_root / case.id / ev.storage_ref).read_text(encoding="utf-8")
        assert secret in stored

    def test_extra_columns_accepted_but_flagged(self, settings, db, case_factory, tmp_path) -> None:
        """B-01: additive unknown fields → accepted, recorded as a flag,
        never silently dropped."""
        case = case_factory("extra")
        csv_file = tmp_path / "extra.csv"
        header = ",".join([*SHERLOCK_CSV_HEADER, "site_note"])
        body_parts = FIXTURE.read_text(encoding="utf-8").splitlines()[1].split(",")
        row = ",".join([*body_parts, "operator-note"])
        csv_file.write_text(header + "\r\n" + row + "\r\n", newline="")
        res = run_import(settings, db, case, csv_file)
        assert res.row_count == 1
        parsed = parse_sherlock_csv(csv_file)
        assert parsed.extra_columns == ("site_note",)
        obs = ObservationRepo(db).list_for_case(case.id)
        assert all("extra_columns=site_note" in o.summary for o in obs)
        assert "site_note" not in SHERLOCK_CSV_HEADER  # known header untouched

    def test_promotion_recovers_exactly_the_pointed_row(
        self, settings, db, case_factory
    ) -> None:
        """raw_ref counts file RECORDS (header = record 1). Promoting the
        GitHub observation must recover the GitHub URL, not a row off by
        one."""
        from tracefield.ingest import promote_observation

        case = case_factory("promote-row")
        run_import(settings, db, case, FIXTURE)
        obs = ObservationRepo(db).list_for_case(case.id)
        github = next(o for o in obs if "GitHub" in o.summary)
        expected_row = next(r for r in parse_sherlock_csv(FIXTURE).rows if r.name == "GitHub")
        assert int(github.raw_ref.rsplit("=", 1)[1]) == expected_row.row_no

        src, _event, prov = promote_observation(settings, db, case, github.id)
        assert src.locator == expected_row.url_user == "https://www.github.com/killerdasher"
        assert prov.row_no == expected_row.row_no
        assert prov.file_sha256 == FIXTURE_SHA256

    def test_ids_are_never_reused_across_imports(self, settings, db, case_factory) -> None:

        case = case_factory("ids")
        r1 = run_import(settings, db, case, FIXTURE)
        r2 = run_import(settings, db, case, FIXTURE)
        assert r1.observation_ids and r2.observation_ids
        assert set(r1.observation_ids).isdisjoint(set(r2.observation_ids))
        # separate sources: two file imports each record their own source row
        assert r1.source_id != r2.source_id
