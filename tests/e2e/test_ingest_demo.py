"""\u00a716/B-04 ingest end-to-end demonstration.

The operator's OWN Sherlock capture (v0.16.2, `killerdasher` — the
maintainer's handle; no third parties) is walked through the real CLI entry
point, OFFLINE: import → triage (dismiss/defer/promote) → claim → relation →
assessment → report → export → manifest verification → tamper detection.

Honesty pins per BLACK-02's P0 gate: the manifest verifies after the import
event, the report carries the promoted source's provenance string verbatim,
and a tampered byte still fails verification.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e

EXIT_OK = 0
EXIT_ERROR = 1

FIXTURE = (
    Path(__file__).parents[1]
    / "fixtures"
    / "ingest"
    / "sherlock_v0.16.2_killerdasher_2026-11-07.csv"
)
FIXTURE_SHA256 = "29309604564665664f9757623b9ee67f63f08bd5c61c25a01da708b791d62add"

CASE = "OPERATOR-OWNED-ingest-demo-killerdasher"


def _run(monkeypatch: pytest.MonkeyPatch, capsys, args: list[str]):
    """Invoke the real console entry point; return (code, stdout, stderr)."""
    from tracefield.cli.main import run

    capsys.readouterr()
    monkeypatch.setattr(sys, "argv", ["tracefield", *args])
    code: int | None = None
    try:
        run()
    except SystemExit as exc:
        raw = exc.code
        code = raw if isinstance(raw, int) else (0 if raw is None else 1)
    captured = capsys.readouterr()
    return (
        code if code is not None else EXIT_OK,
        captured.out,
        captured.err,
    )


def _json(monkeypatch: pytest.MonkeyPatch, capsys, args: list[str]) -> dict:
    code, out, err = _run(monkeypatch, capsys, args)
    assert code == EXIT_OK, err or out
    return json.loads(out)


def _flat(text: str) -> str:
    return " ".join(text.split())


def test_ingest_demo_end_to_end(tf_home, tmp_path, monkeypatch, capsys) -> None:
    # -- 1. Operator-owned case with a declared, honest scope ----------------
    created = _json(
        monkeypatch,
        capsys,
        [
            "case",
            "create",
            CASE,
            "--purpose",
            "Offline ingest demonstration from the operator's own Sherlock "
            "capture; no third parties, no network",
            "--scope",
            "one operator-owned CSV fixture only",
            "--json",
        ],
    )
    assert created["title"] == CASE

    # -- 2. Import (offline; zero egress) ------------------------------------
    imported = _json(
        monkeypatch,
        capsys,
        [
            "case-import",
            "--file",
            str(FIXTURE),
            "--case",
            CASE,
            "--json",
        ],
    )
    assert imported["format_name"] == "sherlock_csv"
    assert imported["row_count"] == 10
    assert imported["evidence_sha256"] == FIXTURE_SHA256
    assert len(imported["observation_ids"]) == 10
    ev_id = imported["evidence_id"]

    status = _json(
        monkeypatch,
        capsys,
        ["case-import", "status", "--case", CASE, "--json"],
    )
    assert status["last_import"]["action"] == "ingest.file"
    assert status["observations_by_tool"] == {"sherlock": 10}

    # -- 3. Triage: one dismissed (reasoned), one deferred, one promoted ------
    obs = _json(
        monkeypatch,
        capsys,
        ["observation", "list", "--case", CASE, "--json"],
    )
    assert len(obs) == 10
    github = next(o for o in obs if "GitHub" in o["summary"])
    aniworld = next(o for o in obs if "AniWorld" in o["summary"])
    f3 = next(o for o in obs if "F3.cool" in o["summary"])

    _run(
        monkeypatch,
        capsys,
        [
            "source",
            "dismiss",
            aniworld["id"],
            "--case",
            CASE,
            "--reason",
            "poster-detection false positive cluster",
        ],
    )
    _run(monkeypatch, capsys, ["source", "defer", f3["id"], "--case", CASE])
    promoted = _json(
        monkeypatch,
        capsys,
        ["source", "promote", github["id"], "--case", CASE, "--json"],
    )
    src = promoted["source"]
    assert src["locator"] == "https://www.github.com/killerdasher"
    assert promoted["provenance"]["file_sha256"] == FIXTURE_SHA256

    review_status = _json(
        monkeypatch,
        capsys,
        ["case-import", "status", "--case", CASE, "--json"],
    )
    assert review_status["review_actions"] == {
        "candidate.dismiss": 1,
        "candidate.defer": 1,
        "candidate.promote": 1,
    }

    # -- 4. Claim + one relation through the existing flow --------------------
    claim = _json(
        monkeypatch,
        capsys,
        [
            "claim",
            "add",
            "--case",
            CASE,
            "--text",
            "The profile URL github.com/killerdasher was recorded as claimed "
            "by the imported Sherlock capture.",
            "--json",
        ],
    )
    rel = _json(
        monkeypatch,
        capsys,
        [
            "relation",
            "add",
            "--case",
            CASE,
            "--from",
            src["id"],
            "--to",
            claim["id"],
            "--type",
            "supports",
            "--evidence",
            ev_id,
            "--rationale",
            "CSV copy row records exists=Claimed http_status=200 for the GitHub profile URL",
            "--json",
        ],
    )
    _run(
        monkeypatch,
        capsys,
        ["relation", "review", rel["id"], "--state", "confirmed"],
    )

    a_1 = _json(
        monkeypatch,
        capsys,
        ["analyze", "claim", claim["id"], "--case", CASE, "--json"],
    )
    a_2 = _json(
        monkeypatch,
        capsys,
        ["analyze", "claim", claim["id"], "--case", CASE, "--json"],
    )
    # Reproducibility: analysis fields only — the vector carries a
    # wall-clock computed_at stamp whose comparison flakes when the two
    # utcnow() calls straddle a tick (root cause found 2026-11-08, see
    # tests/e2e/test_demo_case.py note re D26/B-05).
    assert "computed_at" in a_1 and "computed_at" in a_2
    assert {k: v for k, v in a_1.items() if k != "computed_at"} == {
        k: v for k, v in a_2.items() if k != "computed_at"
    }, "assessment must be reproducible (same store, same rules)"

    events = _json(
        monkeypatch,
        capsys,
        ["analyze", "events", "--case", CASE, "--json"],
    )
    assert events["chain_ok"] is True, "hash chain must close across the import"

    # -- 5. Report carries the promoted source's provenance string ------------
    md_code, md_out, _ = _run(monkeypatch, capsys, ["report", CASE, "--format", "markdown"])
    assert md_code == EXIT_OK
    assert src["id"] in md_out
    assert src["locator"] in md_out
    assert "Limitations:" in md_out
    assert "never verified by TRACEFIELD" in md_out  # provenance string, verbatim
    assert "not truthfulness" in md_out  # global caveat

    report = _json(monkeypatch, capsys, ["report", CASE, "--format", "json"])
    srcs = {s["id"]: s for s in report["sources"]}
    assert src["id"] in srcs
    assert srcs[src["id"]]["access_method"] == "manual"  # promotion never fetched

    # -- 6. Export + verify + tamper ------------------------------------------
    out_dir = tmp_path / "ingest-export"
    code, _, err = _run(monkeypatch, capsys, ["case-export", CASE, "--output", str(out_dir)])
    assert code == EXIT_OK, err
    assert (out_dir / "manifest.json").exists()

    verified = _json(monkeypatch, capsys, ["case-verify", str(out_dir), "--json"])
    assert verified["ok"] is True and verified["problems"] == []

    evidence_files = [p for p in sorted((out_dir / "evidence").rglob("*")) if p.is_file()]
    target = evidence_files[0]
    target.write_bytes(target.read_bytes() + b"TAMPER")
    code, out, _ = _run(monkeypatch, capsys, ["case-verify", str(out_dir), "--json"])
    assert code == EXIT_ERROR, "tampered export must fail verification"
    assert json.loads(out)["ok"] is False
