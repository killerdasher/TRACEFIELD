"""§16 synthetic end-to-end demonstration.

One fully synthetic case — no real people, no real incidents, no network —
walked through the real CLI entry point: sources (syndicated copies + one
distinct + one contradictory), evidence with excerpts, origin clustering,
contradiction candidates, analyst review, assessment reproducibility, report,
privacy-aware export, manifest verification, and tamper detection.

The fixture is labelled SYNTHETIC in its title, purpose, and scope.
"""

from __future__ import annotations

import json
import struct
import sys
import zlib

import pytest

pytestmark = pytest.mark.e2e

EXIT_OK = 0
EXIT_ERROR = 1

# Shared wire-copy body: both syndicated sources carry this text (the second
# adds a short kicker), so ordered-shingle containment must merge them.
_WIRE_BODY = (
    "Acme Corp said on Monday that an internal review found unauthorized "
    "access to a customer records database. The company stated that the "
    "incident was discovered on 2026-03-01 after an alert from its monitoring "
    "provider, and that notification of affected customers began within 48 "
    "hours. No payment card data was stored in the affected system according "
    "to the statement published on the corporate website."
)
_DISTINCT_BODY = (
    "Regulators opened a separate inquiry into Acme Corp data-handling "
    "practices this week, according to a spokesperson for the authority. The "
    "inquiry is described as routine and unrelated to any specific incident "
    "at the company."
)
_CONTRARY_BODY = (
    "A timeline compiled by the outlets' own review places the first "
    "discovery of the Acme Corp intrusion at 2026-03-15, contradicting the "
    "earlier corporate statement. The discrepancy remains unexplained in "
    "public filings."
)


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
    return (code if code is not None else EXIT_OK), captured.out, captured.err


def _json(monkeypatch, capsys, args: list[str]):
    """Run a command expecting exit 0 and parse stdout as JSON."""
    code, out, err = _run(monkeypatch, capsys, args)
    assert code == EXIT_OK, f"{args} -> exit {code}: {out} {err}"
    return json.loads(out)


def _png_1x1() -> bytes:
    """Valid 1x1 RGB PNG built in-process (no external tooling)."""

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    idat = zlib.compress(b"\x00\xff\x00\x00")  # filter 0, one red pixel
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


@pytest.fixture()
def demo_env(tf_home, tmp_path, monkeypatch, capsys):
    """Run the full §16 workflow once; hand back parsed checkpoints."""
    case_title = "SYNTHETIC-demo-acme-breach"
    fx = tmp_path / "fixtures"
    fx.mkdir()
    return {"case": case_title, "fx": fx, "monkeypatch": monkeypatch, "capsys": capsys}


def test_synthetic_demo_end_to_end(demo_env) -> None:
    monkeypatch, capsys = demo_env["monkeypatch"], demo_env["capsys"]
    case = demo_env["case"]
    fx = demo_env["fx"]

    # -- 1. Case with declared purpose and scope ----------------------------
    payload = _json(
        monkeypatch,
        capsys,
        [
            "case",
            "create",
            case,
            "--purpose",
            "SYNTHETIC demonstration of the provenance workflow",
            "--scope",
            "local synthetic fixtures only; no real persons",
            "--json",
        ],
    )
    assert payload["title"] == case
    assert "SYNTHETIC" in payload["purpose"]

    # -- 2. Four synthetic sources: 2 syndicated copies, 1 distinct, 1 contrary
    src_a1 = _json(
        monkeypatch,
        capsys,
        [
            "source",
            "add",
            "https://mirror-one.example/news/acme-breach",
            "--case",
            case,
            "--publisher",
            "Mirror One (wire copy)",
            "--limitations",
            _WIRE_BODY,
            "--json",
        ],
    )
    src_a2 = _json(
        monkeypatch,
        capsys,
        [
            "source",
            "add",
            "https://mirror-two.example/feeds/2026/acme-breach-remix",
            "--case",
            case,
            "--publisher",
            "Mirror Two (syndicated feed)",
            "--limitations",
            "LEAD KICKER: same story as it crossed the wire. " + _WIRE_BODY,
            "--json",
        ],
    )
    src_b = _json(
        monkeypatch,
        capsys,
        [
            "source",
            "add",
            "https://wire-service.example/exclusive/acme-regulator-inquiry",
            "--case",
            case,
            "--publisher",
            "Wire Service (exclusive)",
            "--limitations",
            _DISTINCT_BODY,
            "--json",
        ],
    )
    src_c = _json(
        monkeypatch,
        capsys,
        [
            "source",
            "add",
            "https://outlet.example/timeline/acme-intrusion-dates",
            "--case",
            case,
            "--publisher",
            "Outlet Review (contrary timeline)",
            "--limitations",
            _CONTRARY_BODY,
            "--json",
        ],
    )
    assert len({src_a1["id"], src_a2["id"], src_b["id"], src_c["id"]}) == 4

    # -- 3. Evidence with excerpts (drives contradiction candidates) --------
    def attach(name: str, body: str, source_id: str, excerpt: str) -> dict:
        p = fx / name
        p.write_text(body, encoding="utf-8")
        return _json(
            monkeypatch,
            capsys,
            [
                "evidence",
                "attach",
                str(p),
                "--case",
                case,
                "--source",
                source_id,
                "--excerpt",
                excerpt,
                "--json",
            ],
        )

    ev_a1 = attach(
        "article-a1.txt",
        _WIRE_BODY,
        src_a1["id"],
        "The incident was discovered on 2026-03-01 after an alert.",
    )
    ev_a2 = attach(
        "article-a2.txt",
        _WIRE_BODY,
        src_a2["id"],
        "The incident was discovered on 2026-03-01 after an alert.",
    )
    ev_b = attach(
        "article-b.txt",
        _DISTINCT_BODY,
        src_b["id"],
        "Regulators opened the inquiry this week; no date given for any incident discovery.",
    )
    ev_c = attach(
        "timeline-c.txt",
        _CONTRARY_BODY,
        src_c["id"],
        "The first discovery of the intrusion is placed at 2026-03-15.",
    )
    assert all(e["sha256"] for e in (ev_a1, ev_a2, ev_b, ev_c))

    # -- 4. Fixtures with known metadata: GPS-bearing JSON + PNG image ------
    gps_doc = fx / "device-metadata.json"
    gps_doc.write_text(
        json.dumps(
            {
                "device": "field-camera-01",
                "captured_at": "2026-10-16T12:00:00Z",
                "GPSCoordinates": "51.507400, -0.127800",
                "GPSLatitude": "51.507400",
                "GPSLongitude": "-0.127800",
                "note": "synthetic fixture; coordinates are a public landmark",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    ev_gps = _json(
        monkeypatch,
        capsys,
        ["evidence", "attach", str(gps_doc), "--case", case, "--json"],
    )
    img = fx / "fixture.png"
    img.write_bytes(_png_1x1())
    ev_img = _json(
        monkeypatch,
        capsys,
        ["evidence", "attach", str(img), "--case", case, "--json"],
    )
    assert ev_img["media_type"].startswith("image/"), ev_img["media_type"]

    # A raw tool observation ties the workflow to a (local) tool run.
    obs = _json(
        monkeypatch,
        capsys,
        [
            "observation",
            "add",
            "--case",
            case,
            "--tool",
            "manual-fixture-gen",
            "--summary",
            "generated synthetic fixtures for the demo case",
            "--evidence",
            ev_img["id"],
            "--json",
        ],
    )
    assert obs["tool_name"] == "manual-fixture-gen"

    # -- 5. Claim + relations (sources as origins, evidence linked) ---------
    claim = _json(
        monkeypatch,
        capsys,
        [
            "claim",
            "add",
            "--case",
            case,
            "--text",
            "The Acme Corp breach was discovered on 2026-03-01.",
            "--json",
        ],
    )

    def relate(src_id: str, kind: str, ev_id: str, rationale: str) -> dict:
        return _json(
            monkeypatch,
            capsys,
            [
                "relation",
                "add",
                "--case",
                case,
                "--from",
                src_id,
                "--to",
                claim["id"],
                "--type",
                kind,
                "--evidence",
                ev_id,
                "--rationale",
                rationale,
                "--json",
            ],
        )

    rel_a1 = relate(
        src_a1["id"], "supports", ev_a1["id"], "wire copy text carries the discovery date"
    )
    rel_a2 = relate(
        src_a2["id"], "corroborates", ev_a2["id"], "syndicated copy of the same wire story"
    )
    rel_b = relate(
        src_b["id"], "supports", ev_b["id"], "distinct reporting consistent with the claim"
    )
    rel_c = relate(
        src_c["id"], "contradicts", ev_c["id"], "contrary timeline places discovery on 2026-03-15"
    )

    # -- 6. Origin clustering: the two wire copies must merge ---------------
    origins = _json(monkeypatch, capsys, ["analyze", "origins", "--case", case, "--json"])
    # The two fixture-only sources (path, no document text) are skipped with
    # an honest note — paths must never cluster on shared directory prefixes.
    assert "skipped 2 source(s)" in origins["note"]
    clusters = origins["clusters"]
    assert len(clusters) == 1, json.dumps(clusters, indent=2)
    members = set(clusters[0]["member_ids"])
    assert members == {src_a1["id"], src_a2["id"]}, members
    assert clusters[0]["review_state"] == "unreviewed"
    assert clusters[0]["confidence_label"] == "hypothesis"
    assert any("near_duplicate_text" in ind for ind in clusters[0]["indicators"])

    # -- 7. Contradiction candidates from excerpts --------------------------
    contra = _json(monkeypatch, capsys, ["analyze", "contradictions", "--case", case, "--json"])
    dates = [c for c in contra["candidates"] if c["aspect"] == "date"]
    assert dates, contra["candidates"]
    assert all(c["severity"] == "candidate" for c in dates)
    values = {(c["value_a"], c["value_b"]) for c in dates}
    assert ("2026-03-01", "2026-03-15") in values or ("2026-03-15", "2026-03-01") in values

    # -- 8. Analyst review: confirm supports, then the contradiction --------
    for rel in (rel_a1, rel_a2, rel_b):
        code, _, err = _run(
            monkeypatch,
            capsys,
            ["relation", "review", rel["id"], "--state", "confirmed"],
        )
        assert code == EXIT_OK, err

    # Before the contradiction is confirmed: syndication blocks independence.
    a_before = _json(
        monkeypatch, capsys, ["analyze", "claim", claim["id"], "--case", case, "--json"]
    )
    assert a_before["outcome"] == "SUPPORTED_BUT_UNCONFIRMED"
    assert a_before["rule_version"]
    assert any("origin cluster" in c for c in a_before["caveats"])

    # Reproducibility: same store + same rules => identical assessment.
    a_again = _json(
        monkeypatch, capsys, ["analyze", "claim", claim["id"], "--case", case, "--json"]
    )
    assert a_again == a_before, "assessment must be reproducible"

    code, _, err = _run(
        monkeypatch, capsys, ["relation", "review", rel_c["id"], "--state", "confirmed"]
    )
    assert code == EXIT_OK, err
    a_after = _json(
        monkeypatch, capsys, ["analyze", "claim", claim["id"], "--case", case, "--json"]
    )
    assert a_after["outcome"] == "CONTESTED"
    assert a_after["rule_version"] == a_before["rule_version"]
    assert any("analyst must resolve" in c for c in a_after["caveats"])

    # Unreviewed relations remain visible but are never treated as evidence.
    code, _, _ = _run(
        monkeypatch, capsys, ["relation", "review", rel_c["id"], "--state", "unreviewed"]
    )
    assert code == EXIT_OK
    a_unrev = _json(
        monkeypatch, capsys, ["analyze", "claim", claim["id"], "--case", case, "--json"]
    )
    assert a_unrev["outcome"] == a_before["outcome"]

    # Event chain verifies after the whole workflow.
    events = _json(monkeypatch, capsys, ["analyze", "events", "--case", case, "--json"])
    assert events["chain_ok"] is True

    # -- 9. Reports: Markdown + JSON with links, IDs, digests, caveats ------
    md_code, md_out, _ = _run(monkeypatch, capsys, ["report", case, "--format", "markdown"])
    assert md_code == EXIT_OK
    assert ev_a1["sha256"] in md_out  # digest values
    assert "https://mirror-one.example/news/acme-breach" in md_out  # source links
    assert "rules " in md_out and a_before["rule_version"] in md_out  # rule version
    assert "Caveat:" in md_out
    assert "not truthfulness" in md_out  # global caveat

    report = _json(monkeypatch, capsys, ["report", case, "--format", "json"])
    assert report["case"]["title"] == case
    assert report["global_caveats"]
    assert any(e["sha256"] == ev_a1["sha256"] for e in report["evidence"])
    assessments = {a["claim_id"]: a for a in report["assessments"]}
    assert claim["id"] in assessments
    assert assessments[claim["id"]]["rule_version"] == a_unrev["rule_version"]

    # -- 10. Export: privacy-aware metadata advisory + manifest -------------
    out_dir = fx.parent / "export"
    code, _, err = _run(monkeypatch, capsys, ["case-export", case, "--output", str(out_dir)])
    assert code == EXIT_OK, err
    sensitive = (out_dir / "SENSITIVE_METADATA.txt").read_text(encoding="utf-8")
    # Advisory lists content-addressed evidence paths + key NAMES only.
    assert ev_gps["sha256"] in sensitive
    assert "GPSCoordinates" in sensitive
    assert "51.5074" not in sensitive  # coordinate VALUES never copied
    assert (out_dir / "manifest.json").exists()

    # Verify manifest: OK on untouched export, non-zero after tampering.
    ok = _json(monkeypatch, capsys, ["case-verify", str(out_dir), "--json"])
    assert ok["ok"] is True and ok["problems"] == []

    ev_files = sorted((out_dir / "evidence").rglob("*"))
    target = next(p for p in ev_files if p.is_file())
    target.write_bytes(target.read_bytes() + b"X")
    code, out, _ = _run(monkeypatch, capsys, ["case-verify", str(out_dir), "--json"])
    assert code == EXIT_ERROR, "tampered export must fail verification"
    assert json.loads(out)["ok"] is False
