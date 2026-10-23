"""Unit tests for the deterministic mission planner (Phase 4 acceptance).

All tests are offline and deterministic by contract: the planner must not
import network or subprocess machinery, must not consult a clock or RNG,
and must rank paths by a documented integer score — never a probability.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tracefield.planner import PLANNER_VERSION, build_plan

pytestmark = pytest.mark.unit

SYNTHETIC_QUESTION = (
    "verify the image hash and extract its exif metadata, "
    "then check whether the website article was copied elsewhere"
)


class TestDeterminism:
    def test_same_question_same_plan(self) -> None:
        a = build_plan(SYNTHETIC_QUESTION)
        b = build_plan(SYNTHETIC_QUESTION)
        assert a == b
        # And byte-identical when serialised the way the CLI emits it.
        assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)

    def test_plan_is_json_serialisable(self) -> None:
        payload = build_plan(SYNTHETIC_QUESTION)
        assert json.loads(json.dumps(payload))["planner_version"] == PLANNER_VERSION


class TestOfflineContract:
    def test_planner_module_never_touches_network_or_subprocess(self) -> None:
        src = (Path(__file__).resolve().parents[2] / "src" / "tracefield" / "planner.py").read_text(
            encoding="utf-8"
        )
        for banned in ("httpx", "urllib.request", "socket", "subprocess"):
            assert banned not in src, f"planner must not import {banned}"

    def test_plan_builds_with_socket_disabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import socket

        def _blocked(*args: object, **kwargs: object) -> None:
            raise OSError("network disabled for this test")

        monkeypatch.setattr(socket, "socket", _blocked)
        payload = build_plan(SYNTHETIC_QUESTION)
        assert payload["paths"]


class TestExplainability:
    def test_every_step_states_why(self) -> None:
        payload = build_plan(SYNTHETIC_QUESTION)
        for path in payload["paths"]:
            assert path["rationale"]
            for step in path["steps"]:
                assert step["why"]
                assert step["goal"]
                assert step["command"]

    def test_score_matches_criteria_breakdown(self) -> None:
        payload = build_plan(SYNTHETIC_QUESTION)
        for path in payload["paths"]:
            c = path["criteria"]
            assert path["score"] == [
                c["covered_terms"],
                -c["step_count"],
                -c["network_steps"],
            ]

    def test_paths_are_sorted_deterministically(self) -> None:
        payload = build_plan(SYNTHETIC_QUESTION)
        keys = [(tuple(p["score"]), p["id"]) for p in payload["paths"]]
        assert keys == sorted(keys, reverse=True)


class TestHonesty:
    def test_synthetic_question_hits_expected_capabilities(self) -> None:
        payload = build_plan(SYNTHETIC_QUESTION)
        by_id = {p["id"]: p for p in payload["paths"]}
        offline_caps = {s["capability"] for s in by_id["offline-first"]["steps"]}
        network_caps = {s["capability"] for s in by_id["bounded-network"]["steps"]}
        # Local capabilities appear in BOTH paths.
        assert {"hash-verify", "metadata-inspect", "origin-analysis", "close-out"} <= offline_caps
        # Network capabilities appear ONLY in the bounded-network path.
        assert "web-fetch" in network_caps
        assert "web-fetch" not in offline_caps

    def test_network_steps_carry_opt_in_note(self) -> None:
        payload = build_plan(SYNTHETIC_QUESTION)
        for path in payload["paths"]:
            for step in path["steps"]:
                if step["needs_network"]:
                    assert "TRACEFIELD_ALLOW_NETWORK=1" in step["risk_note"]
                    assert "opt-in" in step["risk_note"]

    def test_gibberish_reports_unresolved_terms(self) -> None:
        payload = build_plan("quxlorp zzzzwww qqq123")
        assert payload["unresolved_terms"]
        for path in payload["paths"]:
            assert path["criteria"]["step_count"] == 0  # nothing invented
            assert path["steps"] == []

    def test_scores_are_never_percentages(self) -> None:
        payload = build_plan(SYNTHETIC_QUESTION)
        for path in payload["paths"]:
            assert isinstance(path["score"], list)
            assert all(isinstance(x, int) for x in path["score"])

    def test_catalogue_suggestions_marked_inert(self) -> None:
        payload = build_plan(SYNTHETIC_QUESTION)
        cs = payload["catalogue_suggestions"]
        if cs["available"]:
            assert "inert" in cs["note"] or "listings" in cs["note"]

    def test_missing_catalogue_is_honest_not_fatal(self) -> None:
        payload = build_plan("verify hash", catalog_path=Path("/nonexistent/catalog.jsonl"))
        assert payload["catalogue_suggestions"]["available"] is False
        assert payload["paths"]

    def test_global_caveats_present(self) -> None:
        payload = build_plan(SYNTHETIC_QUESTION)
        joined = " ".join(payload["global_caveats"]).lower()
        assert "proposal" in joined
        assert "not probabilities" in joined
