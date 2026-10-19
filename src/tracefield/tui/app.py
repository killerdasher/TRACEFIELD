"""TRACEFIELD TUI — keyboard-first, optional. Every feature here also has
a CLI path; the TUI is never the only route to a capability.

Keymap:
  ?          help
  /          search (filter current list)
  Tab        next panel
  Enter      inspect selected
  Esc        cancel / back
  q          quit (confirms if a view is dirty-safe to leave)
  g          go to workspace (mission/evidence/claims/arsenal/field/runs)
  1-6        jump to workspace directly
  Ctrl+C     cancel current operation first; second press exits
"""

from __future__ import annotations

from typing import ClassVar

from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Static

from tracefield import __version__
from tracefield.config import load_settings
from tracefield.core.domain import Case
from tracefield.security import sanitize_for_terminal
from tracefield.storage import Database
from tracefield.storage.repositories import (
    CaseRepo,
    ClaimRepo,
    EventRepo,
    EvidenceRepo,
    SourceRepo,
)

WORKSPACES = [
    ("mission", "Mission"),
    ("evidence", "Evidence"),
    ("claims", "Claims"),
    ("arsenal", "Arsenal"),
    ("field", "Field"),
    ("runs", "Runs"),
]


class StatusBar(Static):
    """Quiet status line — never colour-only signalling."""


class TracefieldApp(App[None]):
    TITLE = "TRACEFIELD"
    CSS = """
    Screen {
        background: #101014;
    }
    #sidebar {
        width: 24;
        border-right: solid #2a2a35;
        padding: 0 1;
        background: #14141a;
    }
    #sidebar .ws-item {
        padding: 0 1;
        color: #9a9aa8;
    }
    #sidebar .ws-item.-active {
        color: #c4b5fd;
        text-style: bold;
    }
    #main {
        padding: 1 2;
    }
    #title {
        color: #c4b5fd;
        text-style: bold;
        padding: 1 0;
    }
    #subtitle {
        color: #6b6b7a;
        padding-bottom: 1;
    }
    #content {
        color: #d4d4dc;
    }
    #status {
        dock: bottom;
        background: #14141a;
        color: #8b8b9a;
        padding: 0 1;
        border-top: solid #2a2a35;
    }
    DataTable {
        background: #101014;
    }
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("q", "quit", "Quit"),
        Binding("question_mark", "help", "Help"),
        Binding("g", "goto", "Go to"),
        Binding("1", "ws(0)", "Mission"),
        Binding("2", "ws(1)", "Evidence"),
        Binding("3", "ws(2)", "Claims"),
        Binding("4", "ws(3)", "Arsenal"),
        Binding("5", "ws(4)", "Field"),
        Binding("6", "ws(5)", "Runs"),
        Binding("slash", "focus_search", "Search"),
        Binding("escape", "back", "Back"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.settings = load_settings()
        self.db: Database | None = None
        self.cases: list[Case] = []
        self.active_ws = 0
        self._status_msg = "ready — press ? for help"

    def on_mount(self) -> None:
        self.settings.ensure_dirs()
        self.db = Database(self.settings.db_path)
        self.cases = CaseRepo(self.db).list()
        self.query_one("#content", Static).update(self._render_ws())
        self.query_one(StatusBar).update(self._status_msg)

    async def _shutdown(self) -> None:
        """Release the database connection on every shutdown path (quit
        action, Ctrl-C, or headless run_test teardown)."""
        try:
            await super()._shutdown()
        finally:
            if self.db is not None:
                self.db.close()
                self.db = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal():
            with Vertical(id="sidebar"):
                for i, (_, label) in enumerate(WORKSPACES):
                    yield Static(
                        f"{i + 1}. {label}",
                        id=f"ws-{i}",
                        classes="ws-item" + (" -active" if i == 0 else ""),
                    )
            with Vertical(id="main"):
                yield Static("TRACEFIELD", id="title")
                yield Static(
                    f"v{__version__} — local-first OSINT workbench "
                    "(synthetic/demo data only in this view)",
                    id="subtitle",
                )
                yield Static(self._render_ws(), id="content")
        yield StatusBar()
        yield Footer()

    def _render_ws(self) -> str:
        if self.db is None:
            return "initializing…"
        name = WORKSPACES[self.active_ws][0]
        if name == "mission":
            lines = ["[Mission / current case overview]", ""]
            if not self.cases:
                lines.append("No cases yet.")
                lines.append("Create one:  tracefield case create <name>")
            else:
                for c in self.cases:
                    srcs = SourceRepo(self.db).list_for_case(c.id)
                    clms = ClaimRepo(self.db).list_for_case(c.id)
                    evs = EvidenceRepo(self.db).list_for_case(c.id)
                    lines.append(
                        sanitize_for_terminal(
                            f"● {c.id}  {c.title}  "
                            f"[{len(srcs)} src / {len(clms)} clm / {len(evs)} ev]"
                        )
                    )
            lines.append("")
            lines.append("[dim]Every view here has a CLI equivalent.[/dim]")
            return "\n".join(lines)
        if name == "evidence":
            lines = ["[Evidence and source list]", ""]
            if not self.cases:
                return "no cases — create one with: tracefield case create <name>"
            for case in self.cases:
                lines.append(f"case {case.id} ({sanitize_for_terminal(case.title)})")
                for src in SourceRepo(self.db).list_for_case(case.id):
                    lines.append(sanitize_for_terminal(f"  SRC {src.id}  {src.locator[:70]}"))
                for e in EvidenceRepo(self.db).list_for_case(case.id):
                    lines.append(
                        sanitize_for_terminal(f"  EV  {e.id}  {e.sha256[:16]}…  {e.media_type}")
                    )
                lines.append("")
            return "\n".join(lines)
        if name == "claims":
            lines = ["[Claims and contradictions]", ""]
            if not self.cases:
                return "no cases"
            for case in self.cases:
                lines.append(f"case {case.id}")
                for cl in ClaimRepo(self.db).list_for_case(case.id):
                    lines.append(sanitize_for_terminal(f"  {cl.id}  {cl.text[:70]}  [{cl.status}]"))
            return "\n".join(lines) or "nothing yet"
        if name == "arsenal":
            from pathlib import Path

            import tracefield
            from tracefield.registry import Catalog

            data = (
                Path(tracefield.__file__).parent.parent.parent / "data" / "catalog" / "tools.jsonl"
            )
            if data.exists():
                cat = Catalog(data)
                counts = cat.counts()
                lines = ["[Tool arsenal — inert catalogue metadata]", ""]
                lines.append(f"records: {counts['total_records']}")
                for k, v in counts["by_integration_state"].items():
                    lines.append(f"  {k}: {v}")
                lines.append("")
                lines.append("[dim]Catalogue entries are data, never code.[/dim]")
                return "\n".join(lines)
            return "catalogue data not loaded"
        if name == "field":
            return (
                "[Field utilities — CLI equivalents]\n\n"
                "  tracefield inspect <file> [--deep] [--json]\n"
                "  tracefield hash <file> [--json]\n"
                "  tracefield ocr <image> [--json]\n"
                "  tracefield username check <name>   "
                "(requires TRACEFIELD_USERNAME_CHECK=1)\n"
            )
        # runs
        lines = ["[Task/run history and health]", ""]
        if not self.cases:
            return "no cases"
        for case in self.cases:
            lines.append(f"case {case.id}")
            for ev in EventRepo(self.db).list_for_case(case.id)[-15:]:
                lines.append(
                    sanitize_for_terminal(f"  {ev.occurred_at}  {ev.action}  {ev.digest[:12]}…")
                )
        lines.append("")
        lines.append(
            "[dim]Event log is hash-chained (tamper-evident within this "
            "store's threat model; not a blockchain). "
            "Verify via: tracefield analyze events --case <id>[/dim]"
        )
        return "\n".join(lines) or "no events"

    def _set_ws(self, idx: int) -> None:
        self.active_ws = idx % len(WORKSPACES)
        for i in range(len(WORKSPACES)):
            w = self.query_one(f"#ws-{i}", Static)
            w.set_class(i == self.active_ws, "-active")
        self.query_one("#content", Static).update(self._render_ws())
        self._status_msg = f"workspace: {WORKSPACES[self.active_ws][1]}"
        self.query_one(StatusBar).update(self._status_msg)

    def action_ws(self, idx: int) -> None:
        self._set_ws(idx)

    def action_goto(self) -> None:
        self._status_msg = "go to: press 1-6, or ? for help"
        self.query_one(StatusBar).update(self._status_msg)

    def action_help(self) -> None:
        self.query_one("#content", Static).update(
            "Keymap\n"
            "  1-6   switch workspace\n"
            "  g     go-to reminder\n"
            "  /     search (CLI: tracefield tools search)\n"
            "  ?     this help\n"
            "  q     quit\n"
            "  Esc   back\n\n"
            "CLI equivalents cover every feature; the TUI is optional."
        )

    async def action_back(self) -> None:
        self._set_ws(0)

    def action_focus_search(self) -> None:
        self._status_msg = (
            "search: use the CLI — tracefield tools search <query> (catalogue is local, no network)"
        )
        self.query_one(StatusBar).update(self._status_msg)


def run_tui() -> None:
    TracefieldApp().run()
