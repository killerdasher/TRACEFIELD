"""Shared state model for the TUI: workspaces, op state machine, themes,
back-stack. No widget imports here — pure data so tests can exercise the
contract without a screen.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from textual.theme import Theme

# (id, label) — the six workspaces, fixed order = fixed number keys.
WORKSPACES: list[tuple[str, str]] = [
    ("mission", "Mission"),
    ("evidence", "Evidence"),
    ("claims", "Claims"),
    ("arsenal", "Arsenal"),
    ("field", "Field"),
    ("runs", "Runs"),
]

# Terminal-state vocabulary for operations (TS-3). Real states only: no
# synthetic "loading…" theatre, no progress without a real count.
OP_IDLE = "idle"
OP_RUNNING = "running"
OP_DONE = "done"
OP_FAILED = "failed"
OP_CANCELLED = "cancelled"

# Exit-code meanings shown when an operation fails (same vocabulary as CLI).
EXIT_MEANINGS = {
    1: "error",
    2: "not found",
    3: "usage",
    4: "network blocked (opt-in required)",
    5: "unavailable",
}

QUIT_WINDOW_S = 2.0  # Ctrl+C twice within this window exits (TS-3 grammar)


@dataclass
class OpState:
    """One in-flight operation. Progress counts are real or absent."""

    state: str = OP_IDLE
    label: str = ""
    started_at: float = 0.0  # monotonic
    finished_at: float = 0.0
    count: int = 0  # real reported milestones only (rows/files/items)
    exit_code: int | None = None
    message: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "label": self.label,
            "count": self.count,
            "exit_code": self.exit_code,
            "message": self.message,
        }

    def status_text(self) -> str:
        """Honest, text-first status fragment (colour is reinforcement)."""
        if self.state == OP_IDLE:
            return "idle"
        if self.state == OP_RUNNING:
            extra = f", {self.count} done" if self.count else ""
            return f"running: {self.label}{extra}"
        if self.state == OP_DONE:
            extra = f" ({self.count})" if self.count else ""
            return f"done: {self.label}{extra}"
        if self.state == OP_FAILED:
            meaning = EXIT_MEANINGS.get(self.exit_code or 0, "error")
            code = f" exit {self.exit_code}" if self.exit_code is not None else ""
            return f"failed: {self.label} ({meaning}{code})"
        # cancelled
        return f"cancelled: {self.label}"


class BackStack:
    """Esc back-stack (T5): overlay -> detail -> previous workspace.

    Bounded; the maximum depth reached is recorded so tests and the Runs
    view can report it truthfully instead of pretending depth is unbounded.
    """

    MAX_DEPTH = 32

    def __init__(self) -> None:
        self._items: list[Any] = []
        self.max_depth_seen = 0

    def push(self, item: Any) -> None:
        self._items.append(item)
        self.max_depth_seen = max(self.max_depth_seen, len(self._items))
        if len(self._items) > self.MAX_DEPTH:
            self._items.pop(0)  # drop oldest; depth stays bounded

    def pop(self) -> Any | None:
        return self._items.pop() if self._items else None

    def __len__(self) -> int:
        return len(self._items)


def _is_light_terminal() -> bool:
    """Heuristic terminal-background detection for --theme auto.

    Uses $COLORFGBG when the terminal exports it; falls back to dark.
    A heuristic, stated as such in `tui --help` — not a guarantee.
    """
    raw = os.environ.get("COLORFGBG", "").strip()
    if not raw or ";" not in raw:
        return False
    bg = raw.split(";")[-1].strip()
    return bg in {"15", "7", "white", "default"}


def build_themes() -> dict[str, Theme]:
    """Semantic token themes (TS-5): light/dark pair, same variable names.

    CSS references $fg/$muted/$ok/$warn/$err so state text can never be
    colour-only: the word is always rendered, colour reinforces it.
    """
    dark = Theme(
        name="tracefield-dark",
        primary="#c4b5fd",
        background="#101014",
        surface="#14141a",
        panel="#2a2a35",
        foreground="#d4d4dc",
        accent="#c4b5fd",
        dark=True,
        variables={
            "fg": "#d4d4dc",
            "muted": "#8b8b9a",
            "ok": "#4ade80",
            "warn": "#fbbf24",
            "err": "#f87171",
        },
    )
    light = Theme(
        name="tracefield-light",
        primary="#6d28d9",
        background="#fafafa",
        surface="#f0f0f4",
        panel="#d8d8e0",
        foreground="#1b1b22",
        accent="#6d28d9",
        dark=False,
        variables={
            "fg": "#1b1b22",
            "muted": "#5c5c6b",
            "ok": "#15803d",
            "warn": "#b45309",
            "err": "#b91c1c",
        },
    )
    return {"tracefield-dark": dark, "tracefield-light": light}


def resolve_theme(choice: str) -> str:
    """Map --theme auto|dark|light to a registered theme name."""
    if choice == "light":
        return "tracefield-light"
    if choice == "dark":
        return "tracefield-dark"
    return "tracefield-light" if _is_light_terminal() else "tracefield-dark"


# Per-workspace help text, rendered after the workspace-context section
# of the help overlay (progressive disclosure: context first).
WORKSPACE_HELP: dict[str, str] = {
    "mission": (
        "Mission: orientation for the ACTIVE case only — purpose, scope,\n"
        "  tiered counts, recent events, evidence-integrity badge.\n"
        "  v  verify stored evidence hashes (cancellable)"
    ),
    "evidence": (
        "Evidence: sources and evidence items of the active case only.\n"
        "  Enter  inspect the selected row\n"
        "  Tab    switch between list and detail\n"
        "  /      filter this list (incremental, shows n/total)"
    ),
    "claims": (
        "Claims: claims of the active case with assessment outcomes.\n"
        "  Enter  inspect claim + decision-table assessment\n"
        "  n      new claim\n"
        "  r      relate an evidence item to the selected claim\n"
        "  /      filter this list"
    ),
    "arsenal": (
        "Arsenal: inert tool catalogue (data, never code).\n"
        "  Enter  inspect an entry — tier states are verbatim records\n"
        "  /      filter this list (e.g. 'exif')\n"
        "  indexed/verified describe records; nothing here is 'healthy'"
    ),
    "field": (
        "Field: local utilities bound to the active case.\n"
        "  Enter  hash the file at the path input\n"
        "  a      attach the hashed file to the active case as evidence\n"
        "  Every step has a CLI equivalent; the TUI never runs network ops"
    ),
    "runs": (
        "Runs: analysis/event history of the active case plus this\n"
        "  session's operation log (every terminal state is recorded).\n"
        "  Enter  inspect an event (digest chain)\n"
        "  v      verify the event hash chain\n"
        "  /      filter this list"
    ),
}
