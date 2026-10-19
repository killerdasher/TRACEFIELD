"""Headless TUI smoke test: the keyboard workflow must start, switch
views, render, and quit — without a real terminal. Every feature also has
a CLI path (asserted in test_cli), so this proves the TUI shell works,
not that it is the only way to work.
"""

from __future__ import annotations

import asyncio

import pytest

pytestmark = pytest.mark.integration


def test_tui_keyboard_workflow(tf_home) -> None:
    from tracefield.tui.app import TracefieldApp

    async def scenario() -> list[str]:
        observed: list[str] = []
        app = TracefieldApp()
        async with app.run_test(size=(120, 40)) as pilot:
            # Mounted: content region exists and is populated.
            assert app.query_one("#content")
            observed.append(app._status_msg)

            # Workspace switching via number keys.
            await pilot.press("2")
            observed.append(app._status_msg)
            await pilot.press("3")
            observed.append(app._status_msg)

            # Help overlay text.
            await pilot.press("?")
            content = app.query_one("#content")
            observed.append(str(content.render()))
            assert "Keymap" in observed[-1]

            # Escape returns to workspace 0.
            await pilot.press("escape")
            observed.append(app._status_msg)

            # Quit cleanly.
            await pilot.press("q")
        return observed

    observed = asyncio.run(scenario())
    # Workspace switching actually changed the status line.
    assert len(set(observed[:4])) >= 3, observed
    # Escape/back landed on the mission workspace.
    assert "mission" in observed[4].lower() or "workspace" in observed[4].lower()


def test_tui_loads_without_cases(tf_home) -> None:
    """A fresh install (zero cases) must mount without crashing."""
    from tracefield.tui.app import TracefieldApp

    async def scenario() -> str:
        app = TracefieldApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            return str(app.query_one("#content").render())

    body = asyncio.run(scenario())
    assert body, "content region must render something on a fresh install"
