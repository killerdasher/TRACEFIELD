"""TRACEFIELD interactive TUI.

Every TUI feature has a CLI path; the TUI never replaces CLI automation.

Keymap (TS-2: parsed by tests/tui/test_journeys.py; parity-tested against
the live BINDINGS so this table can never drift):

  scope    key        action
  global   q          quit (prompts only while an operation is in flight)
  global   ?          help overlay (closes on ? or Esc)
  global   g          jump palette (six workspaces)
  global   1-6        jump to workspace n
  global   c          case picker (Enter sets the active case, Esc cancels)
  global   Esc        back: overlay -> detail -> previous workspace
  global   Ctrl+C     cancel the in-flight operation; second press exits
  lists    Tab        next pane (only where a workspace has >1 pane)
  lists    Enter      inspect the selected row
  lists    /          filter the current list (n/total match count)
  mission  v          verify stored evidence hashes (chunked, cancellable)
  field    Enter      hash the file at the path input
  field    a          attach the hashed file to the active case
  claims   n          new claim in the active case
  claims   r          relate selected evidence to the selected claim
  runs     v          verify the event hash chain

Honesty rules enforced by tests: the subtitle says "live workspace data"
unless TRACEFIELD_DEMO_FIXTURES=1 (then the demo marker is shown);
the status line always reads ``<workspace> | case: <id> | <op-state>``;
no view ever renders placeholder rows.
"""

from __future__ import annotations

import os
import time
from typing import TYPE_CHECKING, Any, ClassVar

from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Header, Input, OptionList, Static
from textual.widgets.option_list import Option

from tracefield.config import load_settings
from tracefield.config.logging import get_logger
from tracefield.core.domain import Case
from tracefield.security import sanitize_for_terminal
from tracefield.storage import CaseWorkspace, Database
from tracefield.storage.repositories import (
    CaseRepo,
    ClaimRepo,
    EventRepo,
    EvidenceRepo,
    RelationRepo,
    SourceRepo,
)

from .state import (
    OP_CANCELLED,
    OP_DONE,
    OP_FAILED,
    OP_RUNNING,
    QUIT_WINDOW_S,
    WORKSPACE_HELP,
    WORKSPACES,
    BackStack,
    OpState,
    build_themes,
    resolve_theme,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    pass

# Re-exported for tests and the CLI.
__all__ = ["WORKSPACES", "TracefieldApp", "run_tui"]


# ---------------------------------------------------------------------------
# Overlays (modals: they never destroy the underlying content — T1)
# ---------------------------------------------------------------------------
class HelpScreen(ModalScreen[None]):
    """Context help. Workspace-context section first, then global keys."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("question_mark", "dismiss", "Close"),
        Binding("escape", "dismiss", "Close"),
    ]

    def __init__(self, context: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.context = context

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static("Help — context first", classes="overlay-title"),
            Static(self.context, id="help-context"),
            Static("Global keys", classes="overlay-title"),
            Static(
                "q quit   ? help   g jump palette   1-6 workspace\n"
                "c case picker   Esc back   Ctrl+C cancel in-flight op",
                id="help-global",
            ),
            Static("Every TUI feature has a CLI path.", classes="overlay-note"),
            id="help-box",
        )

    # Close comes from the supertype action_dismiss(result=None) — no override
    # needed; the bindings above route ? and Esc to it.


class JumpScreen(ModalScreen[int | None]):
    """Jump palette: type a number, or arrows + Enter."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "cancel", "Close"),
        # Type a number to jump directly (arrows + Enter also work).
        Binding("1", "number(1)", "Jump 1", show=False),
        Binding("2", "number(2)", "Jump 2", show=False),
        Binding("3", "number(3)", "Jump 3", show=False),
        Binding("4", "number(4)", "Jump 4", show=False),
        Binding("5", "number(5)", "Jump 5", show=False),
        Binding("6", "number(6)", "Jump 6", show=False),
    ]

    def __init__(self, current: int, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.current = current

    def compose(self) -> ComposeResult:
        options = []
        for i, (_ws_id, label) in enumerate(WORKSPACES, start=1):
            mark = " * " if i - 1 == self.current else "   "
            options.append(Option(f"{mark}{i}  {label}", id=str(i - 1)))
        yield Vertical(
            Static("Jump to workspace", classes="overlay-title"),
            OptionList(*options, id="jump-list"),
            Static("type a number, or arrows + Enter; Esc closes", classes="overlay-note"),
            id="jump-box",
        )

    def on_mount(self) -> None:
        self.query_one("#jump-list", OptionList).highlighted = min(self.current, 5)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option.id is not None:
            self.dismiss(int(event.option.id))

    def action_number(self, n: int) -> None:  # pragma: no cover - digit bindings
        self.dismiss(n - 1)

    def action_cancel(self) -> None:
        self.dismiss(None)


class CasePickerScreen(ModalScreen[str | None]):
    """Case picker (TS-1): Enter sets the active case, Esc cancels."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, cases: list[Case], current: str | None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.cases = cases
        self.current = current

    def compose(self) -> ComposeResult:
        options = []
        for c in self.cases:
            mark = " * " if c.id == self.current else "   "
            options.append(Option(f"{mark}{c.id}  {c.title[:50]}", id=c.id))
        yield Vertical(
            Static("Select the active case", classes="overlay-title"),
            OptionList(*options, id="case-list")
            if options
            else Static(
                "No cases yet — create one:\n  tracefield case create --title '<title>'",
                id="case-empty",
            ),
            Static("Enter selects; Esc cancels", classes="overlay-note"),
            id="case-box",
        )

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option.id is not None:
            self.dismiss(str(event.option.id))

    def action_cancel(self) -> None:
        self.dismiss(None)


class TextPromptScreen(ModalScreen[str | None]):
    """Single-line text prompt (new claim, hash path …)."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, prompt: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.prompt = prompt

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static(self.prompt, classes="overlay-title"),
            Input(id="prompt-input"),
            id="prompt-box",
        )

    def on_mount(self) -> None:
        self.query_one("#prompt-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value)

    def action_cancel(self) -> None:
        self.dismiss(None)


class ChoicePromptScreen(ModalScreen[str | None]):
    """Choice prompt (relate evidence): Enter selects, Esc cancels."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, prompt: str, options: list[tuple[str, str]], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.prompt = prompt
        self.options = options

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static(self.prompt, classes="overlay-title"),
            OptionList(*(Option(label, id=val) for label, val in self.options), id="choice-list"),
            id="choice-box",
        )

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option.id is not None:
            self.dismiss(str(event.option.id))

    def action_cancel(self) -> None:
        self.dismiss(None)


class QuitConfirmScreen(ModalScreen[bool]):
    """Quit confirmation — only pushed while an operation is in flight."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("y", "confirm", "Quit"),
        Binding("n", "cancel", "Stay"),
        Binding("escape", "cancel", "Stay"),
    ]

    def __init__(self, label: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.label = label

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static("Operation in flight", classes="overlay-title"),
            Static(f"  {self.label}"),
            Static("Quit anyway? (y=quit, n/Esc=stay)", classes="overlay-note"),
            id="quit-box",
        )

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)


# ---------------------------------------------------------------------------
# The application
# ---------------------------------------------------------------------------
class TracefieldApp(App[None]):
    """Six workspaces over live workspace data — never placeholder rows."""

    CSS = """
    Screen { layout: vertical; }
    #top { height: 3; padding: 0 1; }
    #title { text-style: bold; color: $accent; }
    #subtitle { color: $muted; }
    #main-row { height: 1fr; }
    #sidebar { width: 24; padding: 0 1; background: $surface; }
    .ws-item { color: $muted; padding: 0 1; }
    .ws-item.-active { color: $accent; text-style: bold; }
    #views { width: 1fr; }
    #views > * { padding: 0 1; }
    #status { dock: bottom; height: 1; padding: 0 1; background: $surface; color: $fg; }
    .op-done { color: $ok; }
    .op-failed { color: $err; }
    .op-cancelled { color: $warn; }
    .op-running { color: $fg; }
    .detail-pane { height: auto; max-height: 40%; border-top: solid $panel; padding: 0 1; }
    .detail-hidden { display: none; }
    Input { dock: top; margin: 0 0 1 0; }
    #field-hint { color: $muted; }
    #field-result { padding: 1 0; }
    #runs-ops { dock: bottom; color: $muted; padding: 0 1; }
    #runs-verify { color: $fg; padding: 0 1; }
    .overlay-title { text-style: bold; color: $accent; }
    .overlay-note { color: $muted; }
    #help-box, #jump-box, #case-box, #prompt-box, #choice-box, #quit-box {
        width: 60%; height: auto; border: round $accent; padding: 1 2;
        background: $surface; margin: 2 4;
    }
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("q", "quit", "Quit"),
        Binding("question_mark", "help", "Help"),
        Binding("g", "goto", "Jump"),
        Binding("1", "ws(0)", "Mission"),
        Binding("2", "ws(1)", "Evidence"),
        Binding("3", "ws(2)", "Claims"),
        Binding("4", "ws(3)", "Arsenal"),
        Binding("5", "ws(4)", "Field"),
        Binding("6", "ws(5)", "Runs"),
        Binding("c", "pick_case", "Case"),
        Binding("escape", "back", "Back"),
        Binding("ctrl+c", "cancel_or_quit", "Cancel/quit", priority=True),
    ]

    # -- lifecycle ---------------------------------------------------------
    def __init__(self, theme: str = "auto", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        for t in build_themes().values():
            self.register_theme(t)
        self.theme = resolve_theme(theme)
        self.settings = load_settings()
        self.db: Database | None = None
        self.workspace: CaseWorkspace | None = None
        self.cases: list[Case] = []
        self.active_case_id: str | None = None
        self.ws_index = 0
        self.back = BackStack()
        self.op = OpState()
        self.op_log: list[dict[str, Any]] = []
        self.cancel_requested = False
        self.chunk_delay = 0.0  # tests raise this to observe cancel checkpoints
        self.integrity_badge: dict[str, str] = {}
        self._op_started = 0.0
        self._ctrl_c_at: float | None = None
        self._hint = ""
        self._hint_at = 0.0
        # Repositories, opened in on_mount once the DB handle exists.
        self.case_repo: CaseRepo
        self.source_repo: SourceRepo
        self.evidence_repo: EvidenceRepo
        self.claim_repo: ClaimRepo
        self.relation_repo: RelationRepo
        self.event_repo: EventRepo

    async def on_mount(self) -> None:
        self.settings.ensure_dirs()
        self.db = Database(self.settings.db_path)
        self.workspace = CaseWorkspace(self.settings.cases_root, self.db)
        self.case_repo = CaseRepo(self.db)
        self.source_repo = SourceRepo(self.db)
        self.evidence_repo = EvidenceRepo(self.db)
        self.claim_repo = ClaimRepo(self.db)
        self.relation_repo = RelationRepo(self.db)
        self.event_repo = EventRepo(self.db)
        self.cases = self.case_repo.list()
        # TS-1: 1 case auto-selects; 0/2+ never guess silently.
        if len(self.cases) == 1:
            self.active_case_id = self.cases[0].id
        elif len(self.cases) > 1:
            self.hint("select a case: c")
        await self._mount_views()
        self.set_interval(1.0, self._tick_status)

    async def on_shutdown(self) -> None:
        self._close_db()

    async def on_unmount(self) -> None:  # run_test() dispatches Unmount only
        self._close_db()

    def _close_db(self) -> None:
        if self.db is not None:
            self.db.close()
            self.db = None

    # -- compose -----------------------------------------------------------
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True, id="header")
        yield Horizontal(
            Vertical(*(self._ws_item(i) for i in range(len(WORKSPACES))), id="sidebar"),
            Vertical(
                Static("", id="title"),
                Static("", id="subtitle"),
                Vertical(id="views"),
                id="main",
            ),
            id="main-row",
        )
        yield Static("", id="status")

    def _ws_item(self, i: int) -> Static:
        return Static(WORKSPACES[i][1], id=f"ws-{i}", classes="ws-item")

    # -- views -------------------------------------------------------------
    def view_by_index(self, i: int) -> Any:
        view_ids = ["ws-mission", "ws-evidence", "ws-claims", "ws-arsenal", "ws-field", "ws-runs"]
        return self.query_one(f"#{view_ids[i]}")

    async def _mount_views(self) -> None:
        from tracefield.tui.views import (
            ArsenalView,
            ClaimsView,
            EvidenceView,
            FieldView,
            MissionView,
            RunsView,
        )

        views = self.query_one("#views")
        view_classes = [MissionView, EvidenceView, ClaimsView, ArsenalView, FieldView, RunsView]
        view_ids = ["ws-mission", "ws-evidence", "ws-claims", "ws-arsenal", "ws-field", "ws-runs"]
        for cls, vid in zip(view_classes, view_ids, strict=True):
            await views.mount(cls(self, id=vid))
        await self.switch_ws(self.ws_index, push=False)
        self._refresh_all_views()

    def _refresh_all_views(self) -> None:
        self.view_by_index(0).refresh_sync()  # mission is sync

    # -- status line (TS-4) -------------------------------------------------
    def _status_text(self) -> str:
        ws_label = WORKSPACES[self.ws_index][1]
        case = self.active_case_id or "none"
        op_text = self.op.status_text()
        hint = ""
        if self._hint and time.monotonic() - self._hint_at < 4.0:
            hint = f"  ·  {self._hint}"
        return f"{ws_label} | case: {case} | {op_text}{hint}"

    def _tick_status(self) -> None:
        if self.op.state == OP_RUNNING:
            self._render_status()
        if self._hint and time.monotonic() - self._hint_at >= 4.0:
            self._hint = ""
            self._render_status()

    def _render_status(self) -> None:
        status = self.query_one("#status", Static)
        status.update(sanitize_for_terminal(self._status_text()))
        cls = f"op-{self.op.state}"
        for name in ("op-idle", "op-running", "op-done", "op-failed", "op-cancelled"):
            status.remove_class(name)
        status.add_class(cls)

    def hint(self, message: str) -> None:
        self._hint = sanitize_for_terminal(message)
        self._hint_at = time.monotonic()
        self._render_status()

    # -- operation model (TS-3) --------------------------------------------
    def begin_op(self, label: str) -> None:
        if self.op.state == OP_RUNNING:
            self.hint(f"busy: {self.op.label} — Ctrl+C cancels it first")
            return
        self.cancel_requested = False
        self.op = OpState(state=OP_RUNNING, label=label, started_at=time.monotonic())
        self._op_started = time.monotonic()
        self._render_status()

    def report_progress(self, count: int) -> None:
        """Real milestone counts only — never an estimated percentage."""
        if self.op.state == OP_RUNNING:
            self.op.count = count
            self._render_status()

    def finish_op(
        self,
        state: str,
        *,
        count: int | None = None,
        exit_code: int | None = None,
        message: str = "",
    ) -> None:
        if state not in (OP_DONE, OP_FAILED, OP_CANCELLED):
            raise ValueError(f"terminal state required, got {state!r}")
        if count is not None:
            self.op.count = count
        self.op.state = state
        self.op.exit_code = exit_code
        self.op.message = message
        self.op.finished_at = time.monotonic()
        self.record_op_terminal(self.op.label, state, count=self.op.count, exit_code=exit_code)
        self._render_status()

    def record_op_terminal(
        self,
        label: str,
        state: str,
        *,
        count: int = 0,
        exit_code: int | None = None,
    ) -> None:
        from tracefield.core.domain import utcnow

        entry = {
            "at": utcnow(),
            "state": state,
            "label": label,
            "count": count,
            "exit_code": exit_code,
        }
        self.op_log.append(entry)
        get_logger("tui").info(
            "tui operation terminal",
            extra={"event": "tui_op", **entry},
        )
        try:
            from tracefield.tui.views import RunsView

            view = self.view_by_index(5)
            if isinstance(view, RunsView):
                view.refresh_op_log()
        except Exception:  # views may not be mounted yet
            pass

    # -- case model (TS-1) --------------------------------------------------
    def case_by_id(self, case_id: str) -> Case:
        for c in self.cases:
            if c.id == case_id:
                return c
        raise KeyError(case_id)

    def set_active_case(self, case_id: str | None) -> None:
        self.active_case_id = case_id
        if case_id:
            self.hint(f"active case: {case_id}")
        self._refresh_all_views()
        self.run_view_refresh(self.view_by_index(1))  # evidence
        self.run_view_refresh(self.view_by_index(2))  # claims
        self.run_view_refresh(self.view_by_index(3))  # arsenal
        self.run_view_refresh(self.view_by_index(5))  # runs
        self._render_status()

    def run_view_refresh(self, view: Any) -> None:
        if hasattr(view, "reload_rows"):
            self.run_worker(view.reload_rows())

    # -- navigation ---------------------------------------------------------
    def note_back(self, entry: Any) -> None:
        self.back.push(entry)

    async def switch_ws(self, index: int, *, push: bool = True) -> None:
        if index == self.ws_index and not push:
            pass  # initial mount
        elif index == self.ws_index:
            return
        if push:
            self.back.push(("ws", self.ws_index))
        self.ws_index = index
        for i in range(len(WORKSPACES)):
            view = self.view_by_index(i)
            view.display = i == index
            item = self.query_one(f"#ws-{i}", Static)
            item.set_class(i == index, "-active")
        self.query_one("#title", Static).update(WORKSPACES[index][1])
        demo = os.environ.get("TRACEFIELD_DEMO_FIXTURES", "").strip() in {"1", "true", "yes"}
        subtitle = "DEMO FIXTURES (TRACEFIELD_DEMO_FIXTURES=1)" if demo else "live workspace data"
        self.query_one("#subtitle", Static).update(subtitle)
        self._render_status()
        view = self.view_by_index(index)
        # Focus follows the active workspace: never leave focus stranded on
        # a widget inside a hidden view (keys would type into it instead of
        # reaching the app bindings).
        try:
            from textual.widgets import DataTable as _DT

            view.query_one(_DT).focus()
        except Exception:
            try:
                view.query_one(Input).focus()
            except Exception:
                self.set_focus(None)
        if hasattr(view, "reload_rows"):
            self.run_view_refresh(view)
        elif hasattr(view, "refresh_sync"):
            view.refresh_sync()

    # -- actions ------------------------------------------------------------
    def action_ws(self, index: int) -> None:
        self.run_worker(self.switch_ws(index))

    def action_goto(self) -> None:
        def chosen(index: int | None) -> None:
            if index is not None:
                self.action_ws(index)

        self.push_screen(JumpScreen(self.ws_index), chosen)

    def action_help(self) -> None:
        context = WORKSPACE_HELP.get(WORKSPACES[self.ws_index][0], "")
        self.push_screen(HelpScreen(context))

    def action_pick_case(self) -> None:
        def chosen(case_id: str | None) -> None:
            if case_id is not None:
                self.set_active_case(case_id)

        self.cases = self.case_repo.list()
        self.push_screen(CasePickerScreen(self.cases, self.active_case_id), chosen)

    async def action_back(self) -> None:
        # Overlay handled by the modal itself. Then an open detail pane,
        # then the previous workspace from the back-stack. Never forces
        # Mission (T5).
        view = self.view_by_index(self.ws_index)
        if getattr(view, "detail_open", False):
            view.close_detail()
            return
        entry = self.back.pop()
        if entry is None:
            self.hint("nothing to go back to")
            return
        if isinstance(entry, tuple) and entry and entry[0] == "ws":
            # push=False: going back must not re-push the current
            # workspace, or the stack would ping-pong forever.
            self.run_worker(self.switch_ws(int(entry[1]), push=False))

    def action_cancel_or_quit(self) -> None:
        if self.op.state == OP_RUNNING:
            self.cancel_requested = True
            self.hint(f"cancelling: {self.op.label}…")
            return
        now = time.monotonic()
        if self._ctrl_c_at is not None and now - self._ctrl_c_at < QUIT_WINDOW_S:
            self.exit()
        self._ctrl_c_at = now
        self.hint("Ctrl+C again to quit")

    async def action_quit(self) -> None:
        if self.op.state == OP_RUNNING:

            def confirm(keep_going: bool | None) -> None:
                if keep_going is False:
                    self.exit()

            self.push_screen(QuitConfirmScreen(self.op.label), confirm)
            return
        self.exit()

    def prompt_text(self, prompt: str, callback: Any) -> None:
        def chosen(value: str | None) -> None:
            if value:
                callback(value)

        self.push_screen(TextPromptScreen(prompt), chosen)

    def prompt_choice(self, prompt: str, options: list[tuple[str, str]], callback: Any) -> None:
        def chosen(value: str | None) -> None:
            if value:
                callback(value)

        self.push_screen(ChoicePromptScreen(prompt, options), chosen)


def run_tui(theme: str = "auto", no_color: bool = False) -> None:
    """Launch the TUI. ``--no-color`` maps to NO_COLOR (text-only state
    labels remain: colour never carries meaning alone)."""
    if no_color:
        os.environ["NO_COLOR"] = "1"
    app = TracefieldApp(theme=theme)
    app.run()
