"""TUI journey tests (TS-1..TS-7, J1..J5) — headless, deterministic.

Every journey drives the REAL app through simulated key presses
(``run_test``/``Pilot``); no internal state is faked except:

- ``app.chunk_delay`` — a real cancellation checkpoint between row chunks
  (default 0 = a plain event-loop yield). Tests raise it so Ctrl+C can be
  observed landing mid-load (J5). No fake progress either way.
- Field path input is set programmatically then submitted with Enter —
  the real ``Input.Submitted`` handler, the real hash op, the real store.

Each TUI journey that claims CLI equivalence (J2, J3) is cross-checked
against the actual CLI sequence in a second, fresh data home.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, ClassVar

import pytest

pytestmark = pytest.mark.integration

CLAIM_TEXT = "the exhibit exists"
EXIFTOOL_ID = "tool_001b8f8a85"

# ANSI escape sequences (emitted by rich whenever the render runs under a
# forced terminal — as on GitHub Actions, where typer's rich_utils sets
# FORCE_TERMINAL from GITHUB_ACTIONS at import time).
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes so flag/text assertions are style-independent."""
    return _ANSI_RE.sub("", text)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def run_cli_out(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    args: list[str],
) -> tuple[int, str, str]:
    """Invoke the real console entry point; return (code, stdout, stderr)."""
    from tracefield.cli.main import run

    capsys.readouterr()  # discard prior output
    monkeypatch.setattr(sys, "argv", ["tracefield", *args])
    code: int | None = None
    try:
        run()
    except SystemExit as exc:
        raw = exc.code
        code = raw if isinstance(raw, int) else (0 if raw is None else 1)
    captured = capsys.readouterr()
    return (code if code is not None else 0), captured.out, captured.err


def make_app(**kwargs):
    from tracefield.tui.app import TracefieldApp

    return TracefieldApp(**kwargs)


def seed_case_with_evidence(db, settings, title: str, exhibit: Path):
    """Create a case with one attached evidence item; return (case, evidence)."""
    from tracefield.core.domain import AccessMethod, Case, Source, SourceType
    from tracefield.storage import CaseWorkspace
    from tracefield.storage.repositories import CaseRepo, SourceRepo

    case = CaseRepo(db).create(Case(title=title, purpose="journey test"))
    repo = SourceRepo(db)
    src = repo.add(
        Source(
            case_id=case.id,
            locator=str(exhibit),
            source_type=SourceType.LOCAL_FILE,
            access_method=AccessMethod.MANUAL,
        )
    )
    ws = CaseWorkspace(settings.cases_root, db)
    evidence = ws.attach_file(case.id, src.id, str(exhibit), media_type="text/plain")
    db.commit()
    return case, evidence


def status_matches_spec(text: str) -> bool:
    """TS-4 format: ``<workspace> | case: <id> | <op-state>`` (+ optional hint)."""
    return bool(
        re.fullmatch(
            r"[A-Za-z]+ \| case: (none|case_[0-9a-f]+) \| "
            r"(idle|running[^\n]*|done[^\n]*|failed[^\n]*|cancelled[^\n]*)"
            r"(  ·  .+)?",
            text,
        )
    )


# ---------------------------------------------------------------------------
# TS-2: keymap parity — the docstring table can never drift from BINDINGS
# ---------------------------------------------------------------------------
class TestKeymapParity:
    KEY_ALIASES: ClassVar[dict[str, str]] = {
        "Esc": "escape",
        "Tab": "tab",
        "Enter": "enter",
        "Ctrl+C": "ctrl+c",
        "/": "slash",
        "?": "question_mark",
    }

    @staticmethod
    def _parse_docstring_table() -> dict[str, set[str]]:
        import tracefield.tui.app as app_mod

        table: dict[str, set[str]] = {}
        for line in (app_mod.__doc__ or "").splitlines():
            m = re.match(r"^  (\w+)\s+(\S+)\s\s+(.+)$", line)
            if not m:
                continue
            scope, key = m.group(1), m.group(2)
            if scope == "scope":  # header row
                continue
            keys = TestKeymapParity.KEY_ALIASES.get(key)
            if keys is None:
                if re.fullmatch(r"\d-\d", key):  # e.g. "1-6"
                    lo, hi = (int(x) for x in key.split("-"))
                    resolved = [str(i) for i in range(lo, hi + 1)]
                else:
                    resolved = [key.lower()]
            else:
                resolved = [keys]
            table.setdefault(scope, set()).update(resolved)
        return table

    def test_docstring_table_matches_live_bindings(self) -> None:
        from tracefield.tui.app import TracefieldApp
        from tracefield.tui.views import (
            ClaimsView,
            FieldView,
            ListView,
            MissionView,
            RunsView,
        )

        parsed = self._parse_docstring_table()
        list_base = {b.key for b in ListView.BINDINGS}
        expected: dict[str, set[str]] = {
            "global": {b.key for b in TracefieldApp.BINDINGS},
            "lists": list_base,
            "mission": {b.key for b in MissionView.BINDINGS},
            # field "Enter" is widget-native (Input.Submitted); asserted below.
            "field": {b.key for b in FieldView.BINDINGS} | {"enter"},
            "claims": {b.key for b in ClaimsView.BINDINGS} - list_base,
            "runs": {b.key for b in RunsView.BINDINGS} - list_base,
        }
        assert parsed == expected, (
            f"keymap docstring drifted from BINDINGS:\n"
            f"  docstring: {parsed}\n  bindings:  {expected}"
        )

    def test_field_enter_is_the_real_input_submit(self) -> None:
        """The one widget-native key in the table must have a live handler."""
        from tracefield.tui.views import FieldView

        assert hasattr(FieldView, "on_input_submitted"), (
            "docstring advertises field Enter (Input.Submitted) but no handler exists"
        )

    def test_every_advertised_binding_has_an_action(self) -> None:
        """No surface may advertise a key that does nothing (T4 rule)."""
        from tracefield.tui.app import TracefieldApp
        from tracefield.tui.views import (
            ArsenalView,
            ClaimsView,
            EvidenceView,
            FieldView,
            ListView,
            MissionView,
            RunsView,
        )

        for cls in (
            TracefieldApp,
            ListView,
            MissionView,
            EvidenceView,
            ClaimsView,
            ArsenalView,
            FieldView,
            RunsView,
        ):
            for binding in cls.BINDINGS:
                action = binding.action.split("(")[0]
                assert hasattr(cls, f"action_{action}"), (
                    f"{cls.__name__} binds {binding.key!r} to missing action_{action}"
                )

    def test_monopane_views_never_bind_tab(self) -> None:
        """T4: a workspace with one pane must not advertise pane switching."""
        from tracefield.tui.views import FieldView, ListView, MissionView

        for cls in (MissionView, FieldView):
            keys = {b.key for b in cls.BINDINGS}
            assert "tab" not in keys and "enter" not in keys
            assert cls.MULTI_PANE is False
        assert "tab" in {b.key for b in ListView.BINDINGS}
        assert ListView.MULTI_PANE is True


# ---------------------------------------------------------------------------
# TS-4 / TS-5: status line, subtitle honesty, themes
# ---------------------------------------------------------------------------
class TestHonestyAndThemes:
    def test_status_line_format(self, tf_home) -> None:
        from tracefield.core.domain import Case
        from tracefield.storage import Database
        from tracefield.storage.repositories import CaseRepo

        db = Database(str(tf_home / "tracefield.sqlite3"))
        case = CaseRepo(db).create(Case(title="status-case"))
        db.close()

        async def scenario() -> list[str]:
            app = make_app()
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause(0.5)
                return [
                    app._status_text(),
                    str(app.query_one("#status").render()),
                    str(app.query_one("#subtitle").render()),
                ]

        idle, rendered, subtitle = asyncio.run(scenario())
        assert status_matches_spec(idle), idle
        assert case.id in idle
        # The rendered status widget shows the same workspace label (sanitized).
        assert rendered.startswith("Mission |"), rendered
        # TS-7 honesty: subtitle claims live data unless demo env is set.
        assert subtitle == "live workspace data", subtitle

    def test_demo_marker_only_with_env(self, tf_home, monkeypatch) -> None:
        monkeypatch.setenv("TRACEFIELD_DEMO_FIXTURES", "1")

        async def scenario() -> str:
            app = make_app()
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause(0.5)
                return str(app.query_one("#subtitle").render())

        subtitle = asyncio.run(scenario())
        assert "DEMO FIXTURES" in subtitle, subtitle

    def test_status_words_survive_no_color(self, tf_home, monkeypatch) -> None:
        """Colour may never carry meaning alone: every state is a word."""
        from tracefield.tui.state import OpState

        monkeypatch.setenv("NO_COLOR", "1")
        assert OpState().status_text() == "idle"
        assert "running" in OpState(state="running", label="x").status_text()
        assert "done" in OpState(state="done", label="x", count=3).status_text()
        assert "failed" in OpState(state="failed", label="x", exit_code=2).status_text()
        assert "not found" in OpState(state="failed", label="x", exit_code=2).status_text()
        assert "cancelled" in OpState(state="cancelled", label="x").status_text()

    def test_theme_resolution_and_registration(self) -> None:
        from tracefield.tui.state import build_themes, resolve_theme

        assert resolve_theme("light") == "tracefield-light"
        assert resolve_theme("dark") == "tracefield-dark"
        assert resolve_theme("auto") in {"tracefield-dark", "tracefield-light"}
        themes = build_themes()
        assert set(themes) == {"tracefield-dark", "tracefield-light"}
        dark_vars = set(themes["tracefield-dark"].variables)
        light_vars = set(themes["tracefield-light"].variables)
        assert dark_vars == light_vars == {"fg", "muted", "ok", "warn", "err"}

    def test_theme_flag_selects_theme(self) -> None:
        app = make_app(theme="light")
        assert app.theme == "tracefield-light"
        app_dark = make_app(theme="dark")
        assert app_dark.theme == "tracefield-dark"

    def test_no_color_flag_sets_env(self, tf_home, monkeypatch) -> None:
        from tracefield.tui import app as app_mod

        captured: dict[str, str] = {}

        def fake_run(self) -> None:
            captured["theme"] = self.theme

        monkeypatch.delenv("NO_COLOR", raising=False)
        monkeypatch.setattr(app_mod.TracefieldApp, "run", fake_run)
        app_mod.run_tui(theme="light", no_color=True)
        assert os.environ.get("NO_COLOR") == "1"
        assert captured["theme"] == "tracefield-light"

    def test_tui_help_documents_flags(self, tf_home, monkeypatch, capsys) -> None:
        code, out, _ = run_cli_out(monkeypatch, capsys, ["tui", "--help"])
        assert code == 0
        # On GitHub Actions typer's rich help renders with FORCE_TERMINAL
        # and inserts ANSI resets INSIDE option tokens (--theme -> ESC +
        # '-' + ESC + '-theme'), so raw-substring matching is brittle.
        # The contract is that the rendered help documents both flags; the
        # strip makes the check style-independent.
        plain = strip_ansi(out)
        assert "--theme" in plain and "--no-color" in plain

    def test_tui_help_documents_flags_when_ci_forces_terminal(
        self, tf_home, monkeypatch, capsys, tmp_path
    ) -> None:
        """Regression for CI run 39967712054: typer's rich_utils sets
        FORCE_TERMINAL=True whenever GITHUB_ACTIONS is set (read at module
        import), rendering the help with ANSI resets even inside option
        tokens (--theme -> ESC '-' ESC '-theme'). The help must still
        document --theme/--no-color after stripping ANSI, in a subprocess
        whose environment forces the terminal render deterministically."""
        env = dict(os.environ)
        env["GITHUB_ACTIONS"] = "1"
        env["TRACEFIELD_HOME"] = str(tmp_path / "forced-home")
        renderer = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys; sys.argv=['tracefield','tui','--help']"
                "; from tracefield.cli.main import run; run()",
            ],
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
            check=False,
        )
        assert renderer.returncode == 0
        assert "\x1b[" in renderer.stdout, (
            "this regression requires the forced-terminal render (typer rich help)"
        )
        plain = strip_ansi(renderer.stdout)
        assert "--theme" in plain and "--no-color" in plain

    def test_invalid_theme_is_usage_error(self, tf_home, monkeypatch, capsys) -> None:
        code, _out, err = run_cli_out(monkeypatch, capsys, ["tui", "--theme", "neon"])
        assert code == 3, "an invalid --theme must fail usage, not launch the TUI"
        assert "invalid theme 'neon'" in err


# ---------------------------------------------------------------------------
# TS-1: case model — 0/1/2+ cases, picker, scoping
# ---------------------------------------------------------------------------
class TestCaseModel:
    def test_zero_cases_guides_not_guesses(self, tf_home) -> None:
        async def scenario() -> tuple[str, str | None]:
            app = make_app()
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause(0.5)
                body = str(app.query_one("#mission-body").render())
                return body, app.active_case_id

        body, active = asyncio.run(scenario())
        assert "No cases yet" in body
        assert "tracefield case create" in body  # actionable guidance
        assert active is None
        status = asyncio.run(self._status_only())[0]
        assert "case: none" in status

    @staticmethod
    async def _status_only() -> list[str]:
        app = make_app()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause(0.5)
            return [app._status_text()]

    def test_single_case_auto_selects(self, tf_home) -> None:
        from tracefield.core.domain import Case
        from tracefield.storage import Database
        from tracefield.storage.repositories import CaseRepo

        db = Database(str(tf_home / "tracefield.sqlite3"))
        case = CaseRepo(db).create(Case(title="only-case"))
        db.close()

        async def scenario() -> tuple[str | None, str]:
            app = make_app()
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause(0.5)
                return app.active_case_id, app._status_text()

        active, status = asyncio.run(scenario())
        assert active == case.id
        assert case.id in status

    def test_two_cases_never_guess_and_picker_works(self, tf_home, settings, db, tmp_path) -> None:
        exhibit_a = tmp_path / "a.txt"
        exhibit_a.write_text("alpha evidence", encoding="utf-8")
        exhibit_b = tmp_path / "b.txt"
        exhibit_b.write_text("bravo evidence", encoding="utf-8")
        case_a, ev_a = seed_case_with_evidence(db, settings, "case-alpha", exhibit_a)
        case_b, ev_b = seed_case_with_evidence(db, settings, "case-bravo", exhibit_b)
        db.close()

        async def scenario() -> tuple[str | None, str | None, list[str], list[str]]:
            app = make_app()
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause(0.5)
                assert app.active_case_id is None, "2 cases must never auto-select"
                # Open the picker, select case B explicitly.
                await pilot.press("c")
                await pilot.pause(0.3)
                picker = app.screen
                options = picker.query_one("#case-list")
                options.highlighted = 1  # second case in repo order
                await pilot.press("enter")
                await pilot.pause(1.0)
                active = app.active_case_id
                ev_view = app.view_by_index(1)
                rows_b = list(ev_view._visible_keys)
                # Switch to case A via the picker; rows must be case-scoped.
                await pilot.press("c")
                await pilot.pause(0.3)
                app.screen.query_one("#case-list").highlighted = 0
                await pilot.press("enter")
                await pilot.pause(1.0)
                rows_a = list(ev_view._visible_keys)
                return active, app.active_case_id, rows_a, rows_b

        first_active, second_active, rows_a, rows_b = asyncio.run(scenario())
        assert first_active == case_b.id
        assert second_active == case_a.id
        # Case-scoping (P-TS-4): each view shows only the active case's rows.
        assert ev_a.id in rows_a and ev_b.id not in rows_a
        assert ev_b.id in rows_b and ev_a.id not in rows_b
        # And the other case's evidence id is genuinely distinct.
        assert ev_a.id != ev_b.id

    def test_two_case_isolation_across_views_and_reload(
        self, tf_home, settings, db, tmp_path
    ) -> None:
        """P-TS-4 end to end: with TWO seeded cases (distinct evidence,
        claims, and analysis events), no view — Evidence, Claims, or Runs —
        may show the other case's rows: after selection, after navigation,
        and after a full app reload."""
        from tracefield.core.domain import AnalysisEvent, Claim
        from tracefield.storage.repositories import ClaimRepo, EventRepo

        exhibit_a = tmp_path / "iso-a.txt"
        exhibit_a.write_text("alpha", encoding="utf-8")
        exhibit_b = tmp_path / "iso-b.txt"
        exhibit_b.write_text("bravo", encoding="utf-8")
        case_a, ev_a = seed_case_with_evidence(db, settings, "iso-alpha", exhibit_a)
        case_b, ev_b = seed_case_with_evidence(db, settings, "iso-bravo", exhibit_b)
        claim_a = ClaimRepo(db).add(Claim(case_id=case_a.id, text="alpha claim"))
        claim_b = ClaimRepo(db).add(Claim(case_id=case_b.id, text="bravo claim"))
        evt_a = EventRepo(db).append(AnalysisEvent(case_id=case_a.id, action="probe: alpha"))
        evt_b = EventRepo(db).append(AnalysisEvent(case_id=case_b.id, action="probe: bravo"))
        db.close()

        b_items = {ev_b.id, claim_b.id, evt_b.id}  # case-B rows
        a_items = {ev_a.id, claim_a.id, evt_a.id}  # case-A rows

        async def collect_for_case_b(
            app,
            pilot: Any,
        ) -> dict[str, list[str]]:
            await pilot.press("c")
            await pilot.pause(0.3)
            app.screen.query_one("#case-list").highlighted = 1  # case B (2nd row)
            await pilot.press("enter")
            await pilot.pause(1.0)
            scoped: dict[str, list[str]] = {}
            for index in (1, 2, 5):  # Evidence, Claims, Runs
                await pilot.press(str(index + 1))
                await pilot.pause(0.8)
                scoped[str(index)] = list(app.view_by_index(index)._visible_keys)
            return scoped

        async def scenario() -> tuple[dict[str, list[str]], dict[str, list[str]]]:
            app = make_app()
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause(0.5)
                scoped = await collect_for_case_b(app, pilot)
            app2 = make_app()  # full app reload over the same TRACEFIELD home
            async with app2.run_test(size=(120, 40)) as pilot:
                await pilot.pause(0.5)
                reloaded = await collect_for_case_b(app2, pilot)
            return scoped, reloaded

        scoped, reloaded = asyncio.run(scenario())
        for label, snap in (("selection", scoped), ("reload", reloaded)):
            evidence, claims, runs = snap["1"], snap["2"], snap["5"]
            for view, items in (("evidence", evidence), ("claims", claims), ("runs", runs)):
                assert items, f"{label}/{view} must show the active case's rows"
                found_b = b_items & set(items)
                assert found_b, f"{label}/{view} must contain case-B rows: {items}"
                assert not (a_items & set(items)), (
                    f"{label}/{view} leaked another case's rows: {a_items & set(items)}"
                )


# ---------------------------------------------------------------------------
# J-NAV: the jump palette must be a real palette, not an advertised stub
# ---------------------------------------------------------------------------
class TestJumpPalette:
    def test_g_opens_jump_palette_and_jumps(self, tf_home, settings, db, tmp_path) -> None:
        exhibit = tmp_path / "nav.txt"
        exhibit.write_text("x", encoding="utf-8")
        seed_case_with_evidence(db, settings, "nav-case", exhibit)
        db.close()

        async def scenario() -> list[str]:
            seen: list[str] = []
            app = make_app()
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause(0.5)
                await pilot.press("g")
                await pilot.pause(0.3)
                assert type(app.screen).__name__ == "JumpScreen"
                # The palette carries a real, labelled entry per workspace.
                options = app.screen.query_one("#jump-list")
                labels = [
                    str(option.prompt)
                    for option in options._options  # type: ignore[attr-defined]
                ]
                assert len(labels) == 6, labels
                assert any("Claims" in label for label in labels)
                # Esc cancels without jumping.
                await pilot.press("escape")
                await pilot.pause(0.3)
                seen.append(app._status_text())
                # Selecting an entry jumps for real (type-to-jump: "3" = Claims).
                await pilot.press("g")
                await pilot.pause(0.3)
                await pilot.press("3")
                await pilot.pause(0.8)
                seen.append(app._status_text())
            return seen

        cancelled_then_jumped = asyncio.run(scenario())
        assert cancelled_then_jumped[0].startswith("Mission |"), (
            "Esc on the palette must close it without jumping"
        )
        assert cancelled_then_jumped[1].startswith("Claims |"), (
            "jump entry must land on the chosen workspace"
        )


# ---------------------------------------------------------------------------
# J1 + T1 + T5: evidence browse, detail, help restore, back-stack
# ---------------------------------------------------------------------------
class TestJ1BrowseAndBack:
    def test_detail_help_restore_and_backstack(self, tf_home, settings, db, tmp_path) -> None:
        exhibit = tmp_path / "exhibit.txt"
        exhibit.write_text("hello", encoding="utf-8")
        case, evidence = seed_case_with_evidence(db, settings, "j1-case", exhibit)
        assert case.id == evidence.case_id
        db.close()

        async def scenario() -> tuple[bool, str, bool, str, int]:
            app = make_app()
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause(0.5)
                # 1 case -> auto-selected; go to Evidence.
                await pilot.press("2")
                await pilot.pause(1.0)
                ev_view = app.view_by_index(1)
                assert evidence.id in ev_view._visible_keys
                # Open detail on the EVIDENCE row (sources are listed first).
                ev_view.query_one("#ws-evidence-table").move_cursor(
                    row=ev_view._visible_keys.index(evidence.id)
                )
                await pilot.press("enter")
                await pilot.pause(0.3)
                detail = ev_view.query_one("#ws-evidence-detail")
                assert ev_view.detail_open
                before = str(detail.render())
                assert evidence.id in before and evidence.sha256 in before
                # T1: help overlay must not destroy the underlying content.
                await pilot.press("question_mark")
                await pilot.pause(0.3)
                assert type(app.screen).__name__ == "HelpScreen"
                help_text = str(app.screen.query_one("#help-context").render())
                assert "Evidence:" in help_text  # workspace-context section first
                await pilot.press("question_mark")
                await pilot.pause(0.3)
                after = str(detail.render())
                assert ev_view.detail_open, "help overlay must not close the detail"
                assert after == before, "help overlay must not alter the detail (T1)"
                # Esc closes the detail first (not the workspace).
                await pilot.press("escape")
                await pilot.pause(0.3)
                assert not ev_view.detail_open
                # T5: one more workspace hop, then Esc goes BACK, not to Mission.
                await pilot.press("3")
                await pilot.pause(1.0)
                assert app.ws_index == 2
                await pilot.press("escape")
                await pilot.pause(0.5)
                back_ws = app.ws_index
                await pilot.press("escape")
                await pilot.pause(0.5)
                final_ws = app.ws_index
                depth_seen = app.back.max_depth_seen
                return ev_view.detail_open, before, True, f"{back_ws}->{final_ws}", depth_seen

        detail_open, _before, restored, hops, depth = asyncio.run(scenario())
        assert detail_open is False, "Esc must close the detail before walking history"
        assert restored
        assert hops == "1->0", "Esc must walk the back-stack (evidence -> mission)"
        assert depth >= 2


# ---------------------------------------------------------------------------
# J2: field hash -> attach -> claim -> relate -> assess; CLI cross-check
# ---------------------------------------------------------------------------
class TestJ2FieldToClaim:
    def test_tui_journey_matches_cli_sequence(
        self, tf_home, settings, db, tmp_path, monkeypatch, capsys
    ) -> None:
        from tracefield.core.domain import Case
        from tracefield.storage import Database
        from tracefield.storage.repositories import CaseRepo

        exhibit = tmp_path / "exhibit.txt"
        exhibit.write_text("the exhibit exists in bytes", encoding="utf-8")
        case = CaseRepo(db).create(Case(title="j2-case", purpose="field->claim"))
        db.close()

        async def scenario() -> tuple[str, str, str]:
            app = make_app()
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause(0.5)
                # Field: hash the exhibit (Enter), then attach it (a).
                await pilot.press("5")
                await pilot.pause(0.5)
                path_input = app.query_one("#field-path")
                path_input.value = str(exhibit)
                await pilot.press("enter")
                await pilot.pause(1.0)
                hash_text = str(app.query_one("#field-result").render())
                assert "sha256 " in hash_text
                await pilot.press("a")
                await pilot.pause(1.5)
                attach_text = str(app.query_one("#field-result").render())
                assert "evidence " in attach_text and "source " in attach_text
                # Claims: new claim (n), relate evidence (r), inspect (Enter).
                await pilot.press("3")
                await pilot.pause(1.0)
                await pilot.press("n")
                await pilot.pause(0.3)
                for ch in CLAIM_TEXT:
                    await pilot.press(ch)
                await pilot.press("enter")
                await pilot.pause(1.0)
                await pilot.press("r")
                await pilot.pause(0.5)
                await pilot.press("enter")  # the single evidence option
                await pilot.pause(1.0)
                cl_view = app.view_by_index(2)
                await pilot.press("enter")
                await pilot.pause(0.5)
                detail = str(cl_view.query_one("#ws-claims-detail").render())
                assert "assessment (rule assess-r2):" in detail
                assert "INSUFFICIENT_EVIDENCE" in detail
                # Snapshot the TUI-written store.
                snap_db = Database(str(settings.db_path))
                from tracefield.storage.repositories import (
                    ClaimRepo,
                    EvidenceRepo,
                    RelationRepo,
                )

                evs = EvidenceRepo(snap_db).list_for_case(case.id)
                claims = ClaimRepo(snap_db).list_for_case(case.id)
                rels = RelationRepo(snap_db).list_for_case(case.id)
                snap = (
                    evs[0].sha256,
                    evs[0].media_type,
                    claims[0].text,
                    rels[0].relation.value,
                    rels[0].from_id,
                    rels[0].to_id,
                )
                snap_db.close()
                return (*snap, detail)

        (
            tui_sha,
            tui_media,
            tui_claim_text,
            tui_rel_kind,
            tui_rel_from,
            tui_rel_to,
            tui_detail,
        ) = asyncio.run(scenario())
        assert tui_rel_kind == "supports"
        assert tui_rel_from.startswith("ev_") and tui_rel_to.startswith("clm_")

        # ---- CLI sequence in a second, fresh home -------------------------
        home_b = tmp_path / "cli-home"
        monkeypatch.setenv("TRACEFIELD_HOME", str(home_b))
        code, _out, _err = run_cli_out(
            monkeypatch, capsys, ["case", "create", "cli-j2-case", "--purpose", "p"]
        )
        assert code == 0
        code, out, _err = run_cli_out(
            monkeypatch,
            capsys,
            ["evidence", "attach", str(exhibit), "--case", "cli-j2-case", "--json"],
        )
        assert code == 0
        cli_ev = json.loads(out)
        code, out, _err = run_cli_out(
            monkeypatch,
            capsys,
            [
                "claim",
                "add",
                "--text",
                CLAIM_TEXT,
                "--case",
                "cli-j2-case",
                "--json",
            ],
        )
        assert code == 0
        cli_claim = json.loads(out)
        code, _out, _err = run_cli_out(
            monkeypatch,
            capsys,
            [
                "relation",
                "add",
                "--case",
                "cli-j2-case",
                "--from",
                cli_ev["id"],
                "--to",
                cli_claim["id"],
                "--type",
                "supports",
                "--json",
            ],
        )
        assert code == 0

        # ---- Cross-check: identical structured facts ----------------------
        from tracefield.config import Settings
        from tracefield.core.analysis import assess_claim
        from tracefield.core.domain import Claim

        assert tui_sha == cli_ev["sha256"], "content-addressed hash must match"
        assert tui_media == cli_ev["media_type"]
        assert tui_claim_text == cli_claim["text"] == CLAIM_TEXT

        # The CLI-built relation must have the same shape as the TUI-built one.
        s_b = Settings(data_root=home_b)
        db_b = Database(s_b.db_path)
        rel_rows = db_b.execute("SELECT from_id, to_id, relation FROM relations").fetchall()
        db_b.close()
        assert len(rel_rows) == 1
        assert tuple(rel_rows[0]) == (cli_ev["id"], cli_claim["id"], tui_rel_kind)

        # Same deterministic assessment engine on both stores -> same outcome.
        # Mirror the TUI's inputs: claim + its single UNREVIEWED supports edge.
        from tracefield.core.domain import Relation, RelationType

        def _outcome(from_id: str, to_id: str):
            claim = Claim(case_id="x", text=CLAIM_TEXT)
            rel = Relation(
                case_id="x",
                from_id=from_id,
                to_id=to_id,
                relation=RelationType.SUPPORTS,
            )
            return assess_claim(claim, [rel], origin_clusters=0).outcome

        tui_outcome = _outcome(tui_rel_from, tui_rel_to)
        cli_outcome = _outcome(cli_ev["id"], cli_claim["id"])
        assert tui_outcome == cli_outcome
        assert str(tui_outcome) in tui_detail


# ---------------------------------------------------------------------------
# J3: arsenal filter + entry states vs `tools show --json`
# ---------------------------------------------------------------------------
class TestJ3ArsenalCrossCheck:
    def test_filter_and_tier_states_match_cli(self, tf_home, monkeypatch, capsys) -> None:
        from tracefield.registry import Catalog, default_catalog_path

        catalog = Catalog(default_catalog_path())
        expected_total = len(catalog.entries)
        expected_matches = sum(
            1
            for e in catalog.entries.values()
            if "exif" in f"{e.id} {e.canonical_name} {e.license_id} {e.description}".lower()
        )
        assert expected_matches >= 1

        async def scenario() -> tuple[str, int, str]:
            app = make_app()
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause(0.5)
                await pilot.press("4")
                await pilot.pause(2.0)  # catalogue load (2264 rows)
                ar_view = app.view_by_index(3)
                assert ar_view.query_one("#ws-arsenal-table").row_count == expected_total
                await pilot.press("slash")
                await pilot.pause(0.3)
                for ch in "exif":
                    await pilot.press(ch)
                await pilot.pause(0.5)
                info = str(ar_view.query_one("#ws-arsenal-filter-info").render())
                rows = ar_view.query_one("#ws-arsenal-table").row_count
                # Return focus to the table (user: Tab/click), select the
                # ExifTool row explicitly via its row key, then inspect it.
                table = ar_view.query_one("#ws-arsenal-table")
                table.focus()
                table.move_cursor(row=ar_view._visible_keys.index(EXIFTOOL_ID))
                await pilot.press("enter")
                await pilot.pause(0.5)
                detail = str(ar_view.query_one("#ws-arsenal-detail").render())
                return info, rows, detail

        info, rows, detail = asyncio.run(scenario())
        assert info == f"'exif': {expected_matches}/{expected_total}"
        assert rows == expected_matches
        assert EXIFTOOL_ID in detail

        # Cross-check every displayed tier state against `tools show --json`.
        code, out, _err = run_cli_out(monkeypatch, capsys, ["tools", "show", EXIFTOOL_ID, "--json"])
        assert code == 0
        payload = json.loads(out)
        for field in (
            "integration_state",
            "verification_state",
            "license_review_state",
            "maintenance_status",
            "last_checked",
        ):
            assert str(payload[field]) in detail, (
                f"TUI detail must show {field}={payload[field]!r} verbatim"
            )
        # Honesty: the pane says indexed/verified describe RECORDS, not health.
        assert "nothing here is 'healthy'" in detail


# ---------------------------------------------------------------------------
# J4: chain verify + tamper detection
# ---------------------------------------------------------------------------
class TestJ4ChainVerify:
    def test_verify_then_tamper_shows_broken(self, tf_home, settings, db, tmp_path) -> None:
        exhibit = tmp_path / "exhibit.txt"
        exhibit.write_text("chain me", encoding="utf-8")
        case, _ev = seed_case_with_evidence(db, settings, "j4-case", exhibit)
        db.close()

        async def scenario() -> tuple[str, str]:
            app = make_app()
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause(0.5)
                await pilot.press("6")
                await pilot.pause(1.0)
                runs_view = app.view_by_index(5)
                await pilot.press("v")
                await pilot.pause(1.0)
                clean = str(runs_view.query_one("#runs-verify").render())
                # Tamper the chain from outside the app (a real DB write).
                conn = sqlite3.connect(str(settings.db_path))
                conn.execute(
                    "UPDATE analysis_events SET digest='deadbeef' "
                    "WHERE case_id=? AND rowid=(SELECT MIN(rowid) "
                    "FROM analysis_events WHERE case_id=?)",
                    (case.id, case.id),
                )
                conn.commit()
                conn.close()
                await pilot.press("v")
                await pilot.pause(1.0)
                tampered = str(runs_view.query_one("#runs-verify").render())
                return clean, tampered

        clean, tampered = asyncio.run(scenario())
        assert "chain: VERIFIED" in clean, clean
        assert "chain: BROKEN" in tampered, tampered
        assert "digest mismatch" in tampered, tampered


# ---------------------------------------------------------------------------
# J5: cancel semantics (TS-3)
# ---------------------------------------------------------------------------
class TestJ5Cancel:
    def test_ctrl_c_cancels_inflight_load(self, tf_home, settings, db) -> None:
        from tracefield.core.domain import Case
        from tracefield.storage.repositories import CaseRepo

        case = CaseRepo(db).create(Case(title="j5-case", purpose="cancel"))
        rows = [
            (
                f"clm_{i:04d}",
                case.id,
                f"claim number {i}",
                "factual",
                "active",
                "unreviewed",
                "2026-01-01T00:00:00Z",
            )
            for i in range(1500)
        ]
        db.executemany(
            "INSERT INTO claims(id,case_id,text,claim_type,status,review_state,"
            "created_at) VALUES(?,?,?,?,?,?,?)",
            rows,
        )
        db.commit()
        db.close()

        async def scenario() -> tuple[str, int, int, str, int, str]:
            app = make_app()
            app.chunk_delay = 0.2  # observable cancellation checkpoints
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause(0.5)
                await pilot.press("3")  # claims: chunked load starts
                # Wait until the op is genuinely in flight with at least one
                # real reported chunk: a blind ctrl+c can land in the
                # scheduling gap between the workspace switch and begin_op,
                # which the product correctly treats as a quit hint (not a
                # cancel), leaving the load to complete. Runner scheduling
                # hits this gap inconsistently — seen once on a 3.11 CI job.
                for _ in range(100):
                    if app.op.state == "running" and (app.op.count or 0) > 0:
                        break
                    await pilot.pause(0.05)
                mid_state, mid_count = app.op.state, app.op.count
                await pilot.press("ctrl+c")  # cancel in-flight
                await pilot.pause(1.5)
                cl_view = app.view_by_index(2)
                cancelled_rows = cl_view.query_one("#ws-claims-table").row_count
                status = app._status_text()
                # Recovery: a later full load must succeed completely.
                app.chunk_delay = 0.0
                await pilot.press("2")
                await pilot.pause(0.5)
                await pilot.press("3")
                await pilot.pause(2.0)
                recovered_rows = cl_view.query_one("#ws-claims-table").row_count
                recovered_state = app.op.state
                return (
                    mid_state,
                    mid_count,
                    cancelled_rows,
                    status,
                    recovered_rows,
                    recovered_state,
                )

        (
            mid_state,
            mid_count,
            cancelled_rows,
            status,
            recovered_rows,
            recovered_state,
        ) = asyncio.run(scenario())
        assert mid_state == "running", "press must return while the op is in flight"
        assert mid_count > 0, "progress must be a REAL reported count"
        assert cancelled_rows == 0, "cancel must not leave partial rows (J5)"
        assert "cancelled: Claims: load" in status
        assert recovered_rows == 1500, "reload after cancel must complete fully"
        assert recovered_state == "done"

    def test_cancel_is_recorded_in_op_log(self, tf_home, settings, db) -> None:
        from tracefield.core.domain import Case
        from tracefield.storage.repositories import CaseRepo

        case = CaseRepo(db).create(Case(title="j5b-case"))
        db.executemany(
            "INSERT INTO claims(id,case_id,text,claim_type,status,review_state,"
            "created_at) VALUES(?,?,?,?,?,?,?)",
            [
                (
                    f"clm_{i:04d}",
                    case.id,
                    f"c {i}",
                    "factual",
                    "active",
                    "unreviewed",
                    "2026-01-01T00:00:00Z",
                )
                for i in range(600)
            ],
        )
        db.commit()
        db.close()

        async def scenario() -> list[dict]:
            app = make_app()
            app.chunk_delay = 0.2
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause(0.5)
                await pilot.press("3")
                # Wait until the load op has actually begun: a blind ctrl+c
                # can land in the scheduling gap between the workspace
                # switch and begin_op, which the product correctly treats
                # as a quit hint (not a cancel), leaving the load to
                # complete. Faster/slower runners hit this gap
                # inconsistently — seen once on a 3.11 CI job.
                for _ in range(100):
                    if app.op.state == "running":
                        break
                    await pilot.pause(0.05)
                await pilot.press("ctrl+c")
                await pilot.pause(1.5)
                return list(app.op_log)

        log = asyncio.run(scenario())
        cancelled = [e for e in log if e["state"] == "cancelled"]
        assert cancelled, f"cancel must be recorded in the op log, got {log}"
        assert cancelled[-1]["label"] == "Claims: load"
        # The log records the REAL count processed before the cancel (not 0,
        # not the full total) — honest milestones only.
        assert 0 < cancelled[-1]["count"] < 600

    def test_busy_op_is_not_silently_dropped(self, tf_home) -> None:
        async def scenario() -> tuple[str, str]:
            app = make_app()
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause(0.5)
                app.begin_op("op one")
                app.begin_op("op two")  # refused: op one still running
                return app.op.label, app._hint

        label, hint = asyncio.run(scenario())
        assert label == "op one"
        assert "busy: op one" in hint
        assert "Ctrl+C" in hint

    def test_failing_task_shows_error_and_stays_usable(self, tf_home, tmp_path) -> None:
        """A failing op must surface exit-code meaning and leave the app
        usable (the task fails; the shell does not)."""

        async def scenario() -> tuple[str, str, str]:
            app = make_app()
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause(0.5)
                await pilot.press("5")  # Field
                await pilot.pause(0.5)
                path_input = app.query_one("#field-path")
                path_input.value = str(tmp_path / "does-not-exist.bin")
                await pilot.press("enter")
                await pilot.pause(1.5)
                state = app.op.state
                status = app._status_text()
                result = str(app.query_one("#field-result").render())
                # The app must survive: switch workspaces and come back.
                await pilot.press("2")
                await pilot.pause(0.5)
                await pilot.press("5")
                await pilot.pause(0.5)
                return state, status + " || " + result, str(app.ws_index)

        state, status_and_result, ws_after = asyncio.run(scenario())
        assert state == "failed"
        assert "failed: field: hash" in status_and_result
        assert "(not found exit 2)" in status_and_result  # exit-code meaning
        assert "hash failed:" in status_and_result
        assert ws_after == "4", "app must remain navigable after a failed op"


# ---------------------------------------------------------------------------
# No placeholder rows (TS-7 honesty on a fresh install)
# ---------------------------------------------------------------------------
def test_fresh_install_shows_no_placeholder_rows(tf_home) -> None:
    async def scenario() -> tuple[int, int, int, str, str]:
        app = make_app()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause(0.5)
            counts = []
            for idx in (1, 2, 5):  # evidence, claims, runs
                await pilot.press(str(idx + 1))
                await pilot.pause(1.0)
                view = app.view_by_index(idx)
                counts.append(view.query_one(f"#{view.id}-table").row_count)
            mission = str(app.query_one("#mission-body").render())
            subtitle = str(app.query_one("#subtitle").render())
            return (*counts, mission, subtitle)

    evidence_rows, claims_rows, runs_rows, mission, subtitle = asyncio.run(scenario())
    assert evidence_rows == 0, "fresh install must not fabricate evidence rows"
    assert claims_rows == 0
    assert runs_rows == 0
    assert "No cases yet" in mission
    assert subtitle == "live workspace data"


# ---------------------------------------------------------------------------
# TS-7 baseline: switch/filter latency at 5 000 rows (generous bounds;
# recorded as a baseline in the Phase 6 report, not a benchmark gate)
# ---------------------------------------------------------------------------
def test_workspace_switch_and_filter_baseline(tf_home, settings, db) -> None:
    from tracefield.core.domain import Case
    from tracefield.storage.repositories import CaseRepo

    case = CaseRepo(db).create(Case(title="perf-case"))
    db.executemany(
        "INSERT INTO claims(id,case_id,text,claim_type,status,review_state,"
        "created_at) VALUES(?,?,?,?,?,?,?)",
        [
            (
                f"clm_perf{i:05d}",
                case.id,
                f"perf claim {i}",
                "factual",
                "active",
                "unreviewed",
                "2026-01-01T00:00:00Z",
            )
            for i in range(5000)
        ],
    )
    db.commit()
    db.close()

    async def scenario() -> tuple[float, float, int]:
        app = make_app()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause(0.5)
            t0 = time.monotonic()
            await pilot.press("3")  # switch to Claims: full 5 000-row load
            switch_s = time.monotonic() - t0
            cl_view = app.view_by_index(2)
            assert cl_view.query_one("#ws-claims-table").row_count == 5000
            cl_view._filter = "claim 49"
            t1 = time.monotonic()
            cl_view.apply_filter_sync()
            filter_s = time.monotonic() - t1
            filtered = cl_view.query_one("#ws-claims-table").row_count
            return switch_s, filter_s, filtered

    switch_s, filter_s, filtered = asyncio.run(scenario())
    print(
        f"\nTS-7 baseline @5000 rows: switch+load={switch_s:.3f}s "
        f"filter={filter_s:.3f}s ({filtered} matches)"
    )
    # Generous regression bounds only — the honest numbers are printed above
    # and recorded in the Phase 6 report.
    assert switch_s < 5.0, f"workspace switch regressed: {switch_s:.3f}s"
    assert filter_s < 2.0, f"list filter regressed: {filter_s:.3f}s"
    assert filtered > 0
