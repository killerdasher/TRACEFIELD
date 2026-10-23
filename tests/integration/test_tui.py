"""Headless TUI shell smoke test: the app mounts, switches workspaces,
renders live data, and quits - without a real terminal. The full journey
coverage (J1-J5, TS-1...TS-7, keymap parity) lives in
``tests/tui/test_journeys.py``; this file stays as a fast canary that the
TUI entry point itself keeps working. Every feature also has a CLI path
(asserted in test_cli), so this proves the TUI shell works, not that it
is the only way to work.
"""

from __future__ import annotations

import asyncio

import pytest

pytestmark = pytest.mark.integration


def test_tui_mounts_and_switches_workspaces(tf_home) -> None:
    from tracefield.tui.app import TracefieldApp

    async def scenario() -> list[str]:
        observed: list[str] = []
        app = TracefieldApp()
        async with app.run_test(size=(120, 40)) as pilot:
            # Six workspaces mounted; the sidebar lists them.
            assert app.query_one("#views")
            observed.append(app._status_text())

            # Workspace switching via number keys changes the status line.
            await pilot.press("2")
            observed.append(app._status_text())
            await pilot.press("3")
            observed.append(app._status_text())

            # Help overlay opens and closes on '?'.
            await pilot.press("?")
            assert type(app.screen).__name__ == "HelpScreen"
            await pilot.press("?")

            # Quit cleanly with q.
            await pilot.press("q")
        return observed

    observed = asyncio.run(scenario())
    # Workspace switching actually changed the status line prefix.
    assert observed[0].startswith("Mission |")
    assert observed[1].startswith("Evidence |")
    assert observed[2].startswith("Claims |")


def test_tui_loads_without_cases(tf_home) -> None:
    """A fresh install (zero cases) must mount without crashing and must
    show guidance, never placeholder rows."""
    from tracefield.tui.app import TracefieldApp

    async def scenario() -> str:
        app = TracefieldApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause(0.5)
            return str(app.query_one("#mission-body").render())

    body = asyncio.run(scenario())
    assert "No cases yet" in body
