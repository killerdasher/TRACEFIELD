"""Regression pins for first-run tester findings (LOOP session 2026-11-14).

Two independent fresh-context testers completed the usability protocol
unaided and converged on these defects, each reproduced here:

1. `relation add --type supports --from <claim_id>` was accepted silently.
   assess-r2 counts confirmed relations' from_id as independent origins,
   so the README's old `--from <claim>` example made a claim corroborate
   ITSELF. The CLI now refuses the mis-oriented shape and the README
   teaches source -> claim.
2. `source add` with a locator that already exists in the case silently
   created a second source row (two rows, one origin, no warning).
3. `doctor` flagged the unset report author with no remedy hint.
4. case-verify digest mismatch named the path but not the digests.
"""

from __future__ import annotations

import sys

import pytest

pytestmark = pytest.mark.integration

EXIT_USAGE = 3


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
    return (code if code is not None else 0), buf_out.getvalue(), buf_err.getvalue()


def setup_case_with_claim_and_evidence(
    monkeypatch: pytest.MonkeyPatch, title: str
) -> tuple[str, str, str, str]:
    """case + attached evidence + claim; returns (case_title, source, evidence, claim) ids."""
    import json

    run_cli(monkeypatch, ["case", "create", title, "--purpose", "p", "--scope", "s"])
    ev_file = f"/tmp/tf-{title}/note.txt"
    import pathlib

    pathlib.Path(ev_file).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(ev_file).write_text("synthetic note")
    code, out, _ = run_cli(monkeypatch, ["evidence", "attach", ev_file, "--case", title, "--json"])
    assert code == 0, out
    payload = json.loads(out)
    code, out, _ = run_cli(monkeypatch, ["claim", "add", "--case", title, "--text", "c", "--json"])
    assert code == 0, out
    claim_id = json.loads(out)["id"]
    return title, payload["source_id"], payload["id"], claim_id


class TestRelationOrientationGuard:
    def test_supports_from_claim_is_refused(self, tf_home, monkeypatch) -> None:
        """The old README shape (claim as origin) must be refused with an
        actionable message — the claim would count as its own origin."""
        title, _src, ev, clm = setup_case_with_claim_and_evidence(monkeypatch, "orient-a")
        code, _, err = run_cli(
            monkeypatch,
            [
                "relation",
                "add",
                "--case",
                title,
                "--from",
                clm,
                "--to",
                ev,
                "--type",
                "supports",
                "--evidence",
                ev,
                "--json",
            ],
        )
        assert code == EXIT_USAGE, err
        norm = " ".join(err.split())
        assert "count as its own independent origin" in norm
        assert "--from <source_id>" in norm

    def test_corroborates_from_claim_is_refused(self, tf_home, monkeypatch) -> None:
        title, src, _ev, clm = setup_case_with_claim_and_evidence(monkeypatch, "orient-b")
        code, _, err = run_cli(
            monkeypatch,
            [
                "relation",
                "add",
                "--case",
                title,
                "--from",
                clm,
                "--to",
                src,
                "--type",
                "corroborates",
                "--json",
            ],
        )
        assert code == EXIT_USAGE, err

    def test_canonical_orientation_still_accepted(self, tf_home, monkeypatch) -> None:
        """src -> claim remains the accepted shape (e2e/demo contract)."""
        title, src, ev, clm = setup_case_with_claim_and_evidence(monkeypatch, "orient-c")
        code, out, err = run_cli(
            monkeypatch,
            [
                "relation",
                "add",
                "--case",
                title,
                "--from",
                src,
                "--to",
                clm,
                "--type",
                "supports",
                "--evidence",
                ev,
                "--json",
            ],
        )
        assert code == 0, out + err

    def test_self_loop_refused(self, tf_home, monkeypatch) -> None:
        title, _src, _ev, clm = setup_case_with_claim_and_evidence(monkeypatch, "orient-d")
        code, _, err = run_cli(
            monkeypatch,
            ["relation", "add", "--case", title, "--from", clm, "--to", clm, "--type", "mentions"],
        )
        assert code == EXIT_USAGE, err
        assert "endpoints must differ" in " ".join(err.split())

    def test_contradicts_stays_flexible_claim_to_claim(self, tf_home, monkeypatch) -> None:
        """contradicts between two claims is legitimate analysis and must
        NOT be refused (only supports/corroborates are guarded)."""
        run_cli(monkeypatch, ["case", "create", "orient-e", "--purpose", "p", "--scope", "s"])
        _, _, _, c1 = setup_case_with_claim_and_evidence(monkeypatch, "orient-e")
        _, _, _, c2 = setup_case_with_claim_and_evidence(monkeypatch, "orient-e")
        code, out, err = run_cli(
            monkeypatch,
            [
                "relation",
                "add",
                "--case",
                "orient-e",
                "--from",
                c1,
                "--to",
                c2,
                "--type",
                "contradicts",
                "--json",
            ],
        )
        assert code == 0, out + err


class TestDuplicateSourceWarning:
    def test_same_locator_twice_warns(self, tf_home, monkeypatch, capsys) -> None:
        import pathlib

        f = pathlib.Path("/tmp/tf-dupsrc/note.txt")
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("x")
        run_cli(monkeypatch, ["case", "create", "dupsrc", "--purpose", "p", "--scope", "s"])
        code, _, _ = run_cli(monkeypatch, ["source", "add", str(f), "--case", "dupsrc", "--json"])
        assert code == 0
        code, out, err = run_cli(
            monkeypatch, ["source", "add", str(f), "--case", "dupsrc", "--json"]
        )
        assert code == 0
        norm = " ".join((out + err).split())
        assert "already exists in this case" in norm
        assert "independence scoring" in norm

    def test_first_add_never_warns(self, tf_home, monkeypatch) -> None:
        import pathlib

        f = pathlib.Path("/tmp/tf-dupsrc2/other.txt")
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("x")
        run_cli(monkeypatch, ["case", "create", "dupsrc2", "--purpose", "p", "--scope", "s"])
        code, out, err = run_cli(
            monkeypatch, ["source", "add", str(f), "--case", "dupsrc2", "--json"]
        )
        assert code == 0
        assert "already exists" not in " ".join((out + err).split())


class TestDoctorAndVerifyMessages:
    def test_doctor_author_hint_names_the_remedy(self, tf_home, monkeypatch) -> None:
        code, out, err = run_cli(monkeypatch, ["doctor"])
        assert code == 0
        norm = " ".join((out + err).split())
        assert "TRACEFIELD_REPORT_AUTHOR" in norm
        assert "report_author" in norm

    def test_tamper_message_shows_both_digests(self, tf_home, monkeypatch, tmp_path) -> None:
        import pathlib

        f = pathlib.Path("/tmp/tf-tamper/note.txt")
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("tamper target")
        run_cli(monkeypatch, ["case", "create", "tamper", "--purpose", "p", "--scope", "s"])
        run_cli(monkeypatch, ["evidence", "attach", str(f), "--case", "tamper"])
        code, out, _ = run_cli(
            monkeypatch, ["case-export", "tamper", "--output", str(tmp_path / "exp")]
        )
        assert code == 0, out
        exported = next((tmp_path / "exp").rglob("*9*"))  # evidence shard dir file
        with open(exported, "ab") as fh:
            fh.write(b"x")
        code, out, err = run_cli(monkeypatch, ["case-verify", str(tmp_path / "exp")])
        assert code != 0
        norm = " ".join((out + err).split())
        assert "manifest sha256" in norm and "file now hashes" in norm


class TestEndpointExistence:
    def test_dangling_endpoint_refused(self, tf_home, monkeypatch) -> None:
        """A relation with a from/to id that does not exist in the case must
        be refused — dangling ids were silently stored forever."""
        title, _src, _ev, _clm = setup_case_with_claim_and_evidence(monkeypatch, "dangling")
        code, _, err = run_cli(
            monkeypatch,
            [
                "relation",
                "add",
                "--case",
                title,
                "--from",
                "src_doesnotexist33",
                "--to",
                _clm,
                "--type",
                "supports",
                "--evidence",
                _ev,
            ],
        )
        assert code == 2, err  # EXIT_NOT_FOUND
        assert "relation endpoint not found in this case" in " ".join(err.split())
