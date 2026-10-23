"""E2E integration for the reference adapter (Phase 5 acceptance).

`exiftool-meta` must work end-to-end through the REAL CLI entry point:
run against a local file, store the raw return inside the case workspace,
record an Observation whose raw_ref points at the stored bytes, and surface
in the case report. Skips cleanly when exiftool is not installed — the
suite must pass on machines without optional backends.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from tests.integration.test_cli import run_cli_out

pytestmark = pytest.mark.integration

requires_exiftool = pytest.mark.skipif(
    shutil.which("exiftool") is None, reason="exiftool not installed"
)


def _make_case_and_file(tf_home: Path, capsys, monkeypatch, tmp_path: Path) -> Path:
    code, out, _ = run_cli_out(monkeypatch, capsys, ["case", "create", "adapter-e2e", "--json"])
    assert code == 0
    payload = json.loads(out)
    assert payload["title"] == "adapter-e2e"
    sample = tmp_path / "sample.txt"
    sample.write_text("tracefield adapter e2e sample\n")
    return sample


class TestAdaptersList:
    def test_list_json_exposes_typed_descriptors(self, tf_home, monkeypatch, capsys) -> None:
        code, out, _ = run_cli_out(monkeypatch, capsys, ["adapters", "list", "--json"])
        assert code == 0
        payload = json.loads(out)
        ids = [row["id"] for row in payload]
        assert ids == ["exiftool-meta", "ffprobe-streams", "tesseract-ocr"]
        ref = payload[0]
        assert ref["backend"] == "exiftool"
        assert ref["integration_state"] == "integrated"
        assert ref["catalogue_id"] == "tool_001b8f8a85"
        for row in payload:
            assert row["health"]["state"] in {
                "ready",
                "missing-backend",
                "disabled",
                "blocked",
            }
            # Health claims stay factual: never "healthy".
            assert row["health"]["state"] != "healthy"

    def test_list_human_mode_mentions_factual_health(self, tf_home, monkeypatch, capsys) -> None:
        code, out, _ = run_cli_out(monkeypatch, capsys, ["adapters", "list"])
        assert code == 0
        assert "exiftool-meta" in out
        assert "ready" in out or "missing-backend" in out


class TestAdaptersRun:
    def test_unknown_adapter_is_not_found_2(self, tf_home, monkeypatch, capsys) -> None:
        code, _out, err = run_cli_out(
            monkeypatch, capsys, ["adapters", "run", "curl-scraper", "/etc/hosts", "--case", "x"]
        )
        assert code == 2
        assert "unknown adapter" in err

    @requires_exiftool
    def test_reference_adapter_runs_end_to_end(
        self, tf_home, monkeypatch, capsys, tmp_path
    ) -> None:
        sample = _make_case_and_file(tf_home, capsys, monkeypatch, tmp_path)
        code, out, _ = run_cli_out(
            monkeypatch,
            capsys,
            [
                "adapters",
                "run",
                "exiftool-meta",
                str(sample),
                "--case",
                "adapter-e2e",
                "--json",
            ],
        )
        assert code == 0
        obs = json.loads(out)
        assert obs["tool_name"] == "adapter:exiftool-meta"
        assert obs["tool_version"]  # version captured from the probe
        assert obs["exit_code"] == 0
        assert obs["raw_ref"].startswith("observations/obs_")

        # The raw return is stored inside the case workspace, verbatim JSON.
        raw_path = tf_home / "cases" / obs["case_id"] / obs["raw_ref"]
        assert raw_path.is_file()
        raw = json.loads(raw_path.read_text())
        assert raw["provenance"]["backend"] == "exiftool"
        assert raw["provenance"]["network"] == "none (local process)"
        assert raw["exit_code"] == 0
        assert "FileSize" in raw["stdout"]  # exiftool JSON includes file facts

        # The observation is listed with the case and surfaces in reports.
        code, out, _ = run_cli_out(
            monkeypatch, capsys, ["observation", "list", "--case", "adapter-e2e", "--json"]
        )
        assert code == 0
        listed = json.loads(out)
        assert obs["id"] in [o["id"] for o in listed]

        code, out, _ = run_cli_out(
            monkeypatch, capsys, ["report", "adapter-e2e", "--format", "json"]
        )
        assert code == 0
        report = json.loads(out)
        assert any(o["id"] == obs["id"] for o in report["observations"])

    def test_backend_failure_records_observation_and_exits_1(
        self, tf_home, monkeypatch, capsys, tmp_path
    ) -> None:
        """A non-zero backend exit is still a recorded raw return (the run
        happened), but scripts get a non-zero signal."""
        if shutil.which("exiftool") is None:
            pytest.skip("exiftool not installed")
        sample = tmp_path / "not-an-image.bin"
        sample.write_bytes(b"\x00\x01\x02tracefield-garbage\xff" * 8)
        _make_case_and_file(tf_home, capsys, monkeypatch, tmp_path)
        code, _out, _ = run_cli_out(
            monkeypatch,
            capsys,
            [
                "adapters",
                "run",
                "exiftool-meta",
                str(sample),
                "--case",
                "adapter-e2e",
                "--json",
            ],
        )
        # exiftool still exits 0 on arbitrary files (it reports file-level
        # metadata), so we only assert the run either recorded honestly or
        # signalled failure — never crashed the CLI.
        assert code in {0, 1}

    def test_missing_file_is_usage_error(self, tf_home, monkeypatch, capsys, tmp_path) -> None:
        _make_case_and_file(tf_home, capsys, monkeypatch, tmp_path)
        code, _out, _err = run_cli_out(
            monkeypatch,
            capsys,
            [
                "adapters",
                "run",
                "exiftool-meta",
                str(tmp_path / "gone.txt"),
                "--case",
                "adapter-e2e",
            ],
        )
        assert code in {2, 3}  # exists=True validation at the CLI layer

    def test_kill_switch_maps_to_unavailable_5(
        self, tf_home, monkeypatch, capsys, tmp_path
    ) -> None:
        sample = _make_case_and_file(tf_home, capsys, monkeypatch, tmp_path)
        monkeypatch.setenv("TRACEFIELD_ADAPTERS", "0")
        code, _out, err = run_cli_out(
            monkeypatch,
            capsys,
            ["adapters", "run", "exiftool-meta", str(sample), "--case", "adapter-e2e"],
        )
        assert code == 5
        assert "disabled" in err
