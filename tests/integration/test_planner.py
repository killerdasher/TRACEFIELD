"""CLI contract tests for `tracefield plan` (Phase 4 acceptance) — through
the REAL entry point, so the shipped exit-code contract is what is tested.
"""

from __future__ import annotations

import json

import pytest

from tests.integration.test_cli import run_cli_out

pytestmark = pytest.mark.integration


class TestPlanCli:
    def test_plan_json_exits_zero_and_is_deterministic(
        self, tf_home, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        args = ["plan", "verify", "the", "image", "hash", "--json"]
        code, out, _err = run_cli_out(monkeypatch, capsys, args)
        assert code == 0
        payload = json.loads(out)
        assert payload["planner_version"] == "plan-r1"
        assert payload["question"] == "verify the image hash"
        assert {p["id"] for p in payload["paths"]} == {"offline-first", "bounded-network"}

        code2, out2, _ = run_cli_out(monkeypatch, capsys, args)
        assert code2 == 0
        assert out == out2  # byte-identical: deterministic

    def test_plan_human_mode_exits_zero(
        self, tf_home, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code, out, _ = run_cli_out(
            monkeypatch, capsys, ["plan", "check", "the", "username", "handle"]
        )
        assert code == 0
        assert "offline-first" in out
        assert "bounded-network" in out
        # The honesty caveat must be visible in human output too.
        assert "proposal" in out.lower()

    def test_plan_network_step_is_labelled(
        self, tf_home, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code, out, _ = run_cli_out(
            monkeypatch, capsys, ["plan", "check", "this", "username", "--json"]
        )
        assert code == 0
        payload = json.loads(out)
        by_id = {p["id"]: p for p in payload["paths"]}
        net = [s for s in by_id["bounded-network"]["steps"] if s["needs_network"]]
        assert net and all("TRACEFIELD_ALLOW_NETWORK=1" in s["risk_note"] for s in net)
        assert "username-check" in {s["capability"] for s in net}

    def test_plan_empty_question_is_usage_error(
        self, tf_home, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code, _out, err = run_cli_out(monkeypatch, capsys, ["plan", ""])
        assert code == 3
        assert "usage" in err.lower() or "question" in err.lower()
