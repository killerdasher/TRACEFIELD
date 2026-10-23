"""The six TUI workspaces.

Every view reads live workspace data (no placeholder rows, ever). All
case-scoped views render only the ACTIVE case's rows (P-TS-4). Heavy row
loads are chunked and cooperative-cancellable (TS-3). Text is sanitized
through ``sanitize_for_terminal`` before rendering (D11).
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, ClassVar

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.widgets import DataTable, Input, Static

from tracefield.core.analysis import RULE_VERSION
from tracefield.core.provenance import hash_file
from tracefield.security import sanitize_for_terminal

from .state import OP_CANCELLED, OP_DONE, OP_FAILED

if TYPE_CHECKING:  # pragma: no cover - typing only
    from tracefield.tui.app import TracefieldApp

CHUNK = 200  # rows per chunk; cancel is checked between chunks


def _view(tui: TracefieldApp) -> TracefieldApp:
    return tui


class ListView(Vertical):
    """List + detail panes with incremental filter.

    Subclasses implement :meth:`fetch_rows` (sync DB read, keyed rows) and
    :meth:`render_detail` (full un-truncated record for one row).
    ``MULTI_PANE`` gates whether Tab/Enter are advertised (footer built
    from live bindings: a mono-pane view never advertises Tab).
    """

    VIEW_TITLE = ""
    MULTI_PANE: ClassVar[bool] = True
    COLUMNS: ClassVar[list[str]] = []
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("tab", "next_pane", "Next pane", show=True),
        Binding("enter", "open_detail", "Inspect", show=True),
        Binding("slash", "filter", "Filter", show=True),
    ]

    def __init__(self, tui: TracefieldApp, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.tui = tui
        self._all_rows: list[tuple[str, list[str], str]] = []  # (key, cells, haystack)
        self._visible_keys: list[str] = []
        self._filter = ""
        self._loaded = False

    # -- construction ------------------------------------------------------
    def compose(self) -> ComposeResult:
        yield DataTable(id=f"{self.id}-table", zebra_stripes=True)
        yield Static("", id=f"{self.id}-detail", classes="detail-pane detail-hidden")
        yield Input(placeholder="/ to filter this list", id=f"{self.id}-filter")
        yield Static("", id=f"{self.id}-filter-info")

    def on_mount(self) -> None:
        table = self.query_one(f"#{self.id}-table", DataTable)
        table.cursor_type = "row"  # Enter selects a row -> RowSelected
        for header in self.COLUMNS:
            table.add_column(header)

    # -- data --------------------------------------------------------------
    def fetch_rows(self) -> list[tuple[str, list[str], str]]:
        """Return (row_key, display_cells, search_haystack) rows."""
        raise NotImplementedError

    def render_detail(self, key: str) -> str:
        """Full, un-truncated detail text for one row key."""
        raise NotImplementedError

    async def reload_rows(self) -> None:
        """Reload all rows chunked (cancellable), then apply the filter.

        Named ``reload_rows`` (not ``refresh``) because Textual's
        ``Widget.refresh`` is the layout invalidation method.
        """
        rows = self.fetch_rows()
        self._all_rows = rows
        self._loaded = True
        await self._render_rows(rows, f"{self.VIEW_TITLE}: load")

    async def _render_rows(self, rows: list[tuple[str, list[str], str]], label: str) -> None:
        tui = self.tui
        table = self.query_one(f"#{self.id}-table", DataTable)
        table.clear()
        self._visible_keys = []
        if not rows and self._filter:
            self.query_one(f"#{self.id}-detail", Static)
            self._set_filter_info(0, 0, empty=True)
            return
        tui.begin_op(label)
        total = len(rows)
        try:
            for i in range(0, total, CHUNK):
                if tui.cancel_requested:
                    table.clear()
                    self._visible_keys = []
                    tui.finish_op(OP_CANCELLED)
                    self._set_filter_info(0, total)
                    return
                for key, cells, haystack in rows[i : i + CHUNK]:
                    if not self._filter or self._filter in haystack:
                        table.add_row(*(cells or ()), key=key)
                        self._visible_keys.append(key)
                tui.report_progress(min(i + CHUNK, total))
                # Cancellation checkpoint between chunks. The default 0 is a
                # plain event-loop yield; tests raise tui.chunk_delay to make
                # the checkpoint observable (no fake progress either way).
                await asyncio.sleep(tui.chunk_delay)
            tui.finish_op(OP_DONE, count=total)
        except Exception as exc:  # pragma: no cover - defensive
            table.clear()
            self._visible_keys = []
            tui.finish_op(OP_FAILED, message=str(exc))
            return
        self._set_filter_info(len(self._visible_keys), total)

    def apply_filter_sync(self) -> None:
        """Re-render from cached rows without a new DB read (no fake op)."""
        table = self.query_one(f"#{self.id}-table", DataTable)
        table.clear()
        self._visible_keys = []
        for key, cells, haystack in self._all_rows:
            if not self._filter or self._filter in haystack:
                table.add_row(*(cells or ()), key=key)
                self._visible_keys.append(key)
        self._set_filter_info(len(self._visible_keys), len(self._all_rows))

    def _set_filter_info(self, shown: int, total: int, *, empty: bool = False) -> None:
        info = self.query_one(f"#{self.id}-filter-info", Static)
        if self._filter:
            if empty or shown == 0:
                info.update(f"no match for {self._filter!r} (0/{total})")
            else:
                info.update(f"{self._filter!r}: {shown}/{total}")
        else:
            info.update(f"{total} rows")

    # -- events ------------------------------------------------------------
    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        # DataTable consumes Enter itself; open the detail here.
        if event.data_table.id == f"{self.id}-table":
            self.action_open_detail()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != f"{self.id}-filter":
            return
        self._filter = event.value.strip().lower()
        self.apply_filter_sync()

    # -- actions -----------------------------------------------------------
    @property
    def detail_open(self) -> bool:
        return not self.query_one(f"#{self.id}-detail", Static).has_class("detail-hidden")

    def action_open_detail(self) -> None:
        if not self.MULTI_PANE or not self._visible_keys:
            return
        table = self.query_one(f"#{self.id}-table", DataTable)
        row = table.cursor_row
        if row < 0 or row >= len(self._visible_keys):
            return
        key = self._visible_keys[row]
        detail = self.query_one(f"#{self.id}-detail", Static)
        detail.update(sanitize_for_terminal(self.render_detail(key)))
        detail.remove_class("detail-hidden")
        detail.can_focus = True
        detail.focus()

    def close_detail(self) -> None:
        detail = self.query_one(f"#{self.id}-detail", Static)
        detail.add_class("detail-hidden")
        self.query_one(f"#{self.id}-table", DataTable).focus()

    def action_next_pane(self) -> None:
        detail = self.query_one(f"#{self.id}-detail", Static)
        if detail.has_class("detail-hidden"):
            self.action_open_detail()
        else:
            self.close_detail()

    def action_filter(self) -> None:
        self.query_one(f"#{self.id}-filter", Input).focus()


class MissionView(Vertical):
    """Orientation for the ACTIVE case: purpose, scope, tiered counts,
    recent events, evidence-integrity badge."""

    VIEW_TITLE = "Mission"
    MULTI_PANE = False
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("v", "verify_evidence", "Verify evidence", show=True),
    ]

    def __init__(self, tui: TracefieldApp, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.tui = tui

    def compose(self) -> ComposeResult:
        yield Static("", id="mission-body")

    def refresh_sync(self) -> None:
        body = self.query_one("#mission-body", Static)
        tui = self.tui
        cid = tui.active_case_id
        if cid is None:
            cases = tui.cases
            if not cases:
                text = (
                    "No cases yet.\n\n"
                    "Create one (CLI):\n"
                    "  tracefield case create --title '<title>'\n"
                    "then reload this view."
                )
            else:
                text = (
                    f"{len(cases)} cases in this workspace — select one:\n"
                    "  c  open the case picker\n"
                )
            body.update(sanitize_for_terminal(text))
            return
        case = tui.case_by_id(cid)
        ev = tui.evidence_repo.list_for_case(cid)
        sources = tui.source_repo.list_for_case(cid)
        claims = tui.claim_repo.list_for_case(cid)
        relations = tui.relation_repo.list_for_case(cid)
        events = tui.event_repo.list_for_case(cid)
        lines = [
            f"[bold]{sanitize_for_terminal(case.title)}[/bold]  ({case.id})",
            f"status: {case.status}   created: {case.created_at}",
        ]
        if case.purpose:
            lines.append(f"purpose: {sanitize_for_terminal(case.purpose)}")
        if case.scope:
            lines.append(f"scope: {sanitize_for_terminal(case.scope)}")
        lines.append("")
        lines.append("tiered counts (live):")
        lines.append(f"  sources   {len(sources)}")
        lines.append(f"  evidence  {len(ev)}")
        lines.append(f"  claims    {len(claims)}")
        lines.append(f"  relations {len(relations)}")
        lines.append("")
        badge = tui.integrity_badge.get(cid)
        lines.append(f"evidence integrity: {badge or 'not checked (v to verify)'}")
        lines.append("")
        lines.append("recent events:")
        for e in events[-5:]:
            lines.append(f"  {e.occurred_at}  {e.action}  {e.digest[:12]}…")
        body.update("\n".join(sanitize_for_terminal(ln) for ln in lines))

    async def action_verify_evidence(self) -> None:
        """Re-hash every stored evidence file (chunked, cancellable)."""
        tui = self.tui
        cid = tui.active_case_id
        if cid is None:
            tui.hint("no active case — press c to select one")
            return
        items = tui.evidence_repo.list_for_case(cid)
        if not items:
            tui.hint("no evidence in the active case")
            return
        ws = tui.workspace
        if ws is None:
            tui.hint("workspace not ready — retry in a moment")
            return
        tui.begin_op("mission: verify evidence")
        ok = mismatch = 0
        for i, item in enumerate(items):
            if tui.cancel_requested:
                tui.integrity_badge[cid] = "cancelled — result unknown"
                tui.finish_op(OP_CANCELLED)
                self.refresh_sync()
                return
            path = ws.case_dir(cid) / item.storage_ref
            try:
                if hash_file(path) == item.sha256:
                    ok += 1
                else:
                    mismatch += 1
            except OSError:
                mismatch += 1
            tui.report_progress(i + 1)
            await asyncio.sleep(tui.chunk_delay)
        if mismatch:
            tui.integrity_badge[cid] = f"MISMATCH ({mismatch} of {len(items)})"
        else:
            tui.integrity_badge[cid] = f"intact ({ok}/{len(items)})"
        tui.finish_op(OP_DONE, count=len(items))
        self.refresh_sync()


class EvidenceView(ListView):
    """Sources + evidence items of the ACTIVE case only."""

    VIEW_TITLE = "Evidence"
    COLUMNS: ClassVar[list[str]] = ["kind", "id", "locator / sha256", "media", "size"]

    def fetch_rows(self) -> list[tuple[str, list[str], str]]:
        cid = self.tui.active_case_id
        if cid is None:
            return []
        rows: list[tuple[str, list[str], str]] = []
        for s in self.tui.source_repo.list_for_case(cid):
            hay = f"{s.id} {s.locator} source".lower()
            rows.append((s.id, ["source", s.id, s.locator[:60], s.first_seen_at[:10]], hay))
        for e in self.tui.evidence_repo.list_for_case(cid):
            hay = f"{e.id} {e.sha256} {e.media_type} evidence".lower()
            rows.append(
                (
                    e.id,
                    ["evidence", e.id, e.sha256[:16] + "…", e.media_type, str(e.size_bytes)],
                    hay,
                )
            )
        return rows

    def render_detail(self, key: str) -> str:
        cid = self.tui.active_case_id
        ev = self.tui.evidence_repo.get(key)
        if ev is not None and ev.case_id == cid:
            return "\n".join(
                [
                    f"evidence {ev.id}",
                    f"  case          {ev.case_id}",
                    f"  source        {ev.source_id}",
                    f"  sha256        {ev.sha256}",
                    f"  media type    {ev.media_type}",
                    f"  size          {ev.size_bytes} bytes",
                    f"  storage       {ev.storage_ref}",
                    f"  captured at   {ev.captured_at}",
                    f"  acquisition   {ev.acquisition_method}",
                    f"  privacy label {ev.privacy_label}",
                    f"  excerpt       {sanitize_for_terminal(ev.excerpt[:500])}",
                    "",
                    "integrity: recorded facts only — press v in Mission to re-hash",
                ]
            )
        src = self.tui.source_repo.get(key)
        if src is not None and src.case_id == cid:
            return "\n".join(
                [
                    f"source {src.id}",
                    f"  case          {src.case_id}",
                    f"  locator       {sanitize_for_terminal(src.locator)}",
                    f"  source type   {src.source_type}",
                    f"  access method {src.access_method}",
                    f"  first seen    {src.first_seen_at}",
                    f"  published at  {src.published_at or '(unverified)'}",
                    f"  publisher     {sanitize_for_terminal(src.publisher) or '(unstated)'}",
                ]
            )
        return "record not found in the active case"


class ClaimsView(ListView):
    """Claims of the ACTIVE case with decision-table assessments."""

    VIEW_TITLE = "Claims"
    COLUMNS: ClassVar[list[str]] = ["id", "text", "status", "review"]
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("tab", "next_pane", "Next pane", show=True),
        Binding("enter", "open_detail", "Inspect", show=True),
        Binding("slash", "filter", "Filter", show=True),
        Binding("n", "new_claim", "New claim", show=True),
        Binding("r", "relate_evidence", "Relate evidence", show=True),
    ]

    def fetch_rows(self) -> list[tuple[str, list[str], str]]:
        cid = self.tui.active_case_id
        if cid is None:
            return []
        rows = []
        for c in self.tui.claim_repo.list_for_case(cid):
            hay = f"{c.id} {c.text} {c.status}".lower()
            rows.append((c.id, [c.id, c.text[:60], c.status, c.review_state], hay))
        return rows

    def render_detail(self, key: str) -> str:
        from tracefield.core.analysis import assess_claim

        cid = self.tui.active_case_id
        claim = self.tui.claim_repo.get(key)
        if claim is None or claim.case_id != cid:
            return "claim not found in the active case"
        rels = self.tui.relation_repo.list_for_case(cid)
        claim_rels = [r for r in rels if r.from_id == claim.id or r.to_id == claim.id]
        outcome = assess_claim(claim, claim_rels, origin_clusters=0)
        lines = [
            f"claim {claim.id}",
            f"  text      {sanitize_for_terminal(claim.text)}",
            f"  type      {claim.claim_type}",
            f"  status    {claim.status}   review: {claim.review_state}",
            "",
            "relations:",
        ]
        if not claim_rels:
            lines.append("  (none)")
        for r in claim_rels:
            lines.append(f"  {r.relation:<10} {r.from_id} -> {r.to_id}")
        lines += [
            "",
            f"assessment (rule {RULE_VERSION}):",
            f"  outcome          {outcome.outcome}",
            f"  provenance       {outcome.provenance_completeness}",
            f"  directness       {outcome.evidence_directness}",
            f"  independence     {outcome.independence}",
            f"  supporting count {outcome.supporting_count}",
            f"  contradicting    {outcome.contradicting_count}",
        ]
        for caveat in outcome.caveats:
            lines.append(f"  caveat           {sanitize_for_terminal(caveat)}")
        return "\n".join(lines)

    def action_new_claim(self) -> None:
        if self.tui.active_case_id is None:
            self.tui.hint("no active case — press c to select one")
            return
        self.tui.prompt_text("new claim text:", self._add_claim)

    def _add_claim(self, text: str) -> None:
        from tracefield.core.domain import Claim

        cid = self.tui.active_case_id
        if not text.strip() or cid is None:
            return
        claim = Claim(case_id=cid, text=text.strip())
        self.tui.claim_repo.add(claim)
        self.tui.record_op_terminal("claims: add", OP_DONE, count=1)
        self.tui.hint(f"added claim {claim.id}")
        self.tui.run_view_refresh(self)

    def action_relate_evidence(self) -> None:
        cid = self.tui.active_case_id
        if cid is None:
            self.tui.hint("no active case — press c to select one")
            return
        table = self.query_one(f"#{self.id}-table", DataTable)
        row = table.cursor_row
        if row < 0 or row >= len(self._visible_keys):
            self.tui.hint("select a claim first (Enter inspects it)")
            return
        claim = self.tui.claim_repo.get(self._visible_keys[row])
        if claim is None:
            return
        items = self.tui.evidence_repo.list_for_case(cid)
        if not items:
            self.tui.hint("no evidence in this case — hash/attach in Field first")
            return
        options = [(f"{e.id}  {e.sha256[:12]}…", e.id) for e in items]
        self.tui.prompt_choice(
            "relate which evidence:", options, lambda eid, c=claim: self._relate(c, eid)
        )

    def _relate(self, claim: Any, evidence_id: str) -> None:
        from tracefield.core.domain import Relation, RelationType

        relation = Relation(
            case_id=claim.case_id,
            from_id=evidence_id,  # evidence supports the claim
            to_id=claim.id,
            relation=RelationType.SUPPORTS,
            rationale="linked in TUI",
            method="analyst",
        )
        self.tui.relation_repo.add(relation)
        self.tui.record_op_terminal("claims: relate", OP_DONE, count=1)
        self.tui.hint(f"evidence {evidence_id} supports {claim.id}")
        self.tui.run_view_refresh(self)


class ArsenalView(ListView):
    """Inert tool catalogue (data, never code)."""

    VIEW_TITLE = "Arsenal"
    COLUMNS: ClassVar[list[str]] = ["id", "name", "license", "integration"]

    def fetch_rows(self) -> list[tuple[str, list[str], str]]:
        from tracefield.registry import Catalog, default_catalog_path

        catalog = Catalog(default_catalog_path())
        rows = []
        for e in catalog.entries.values():
            hay = f"{e.id} {e.canonical_name} {e.license_id} {e.description}".lower()
            rows.append(
                (
                    e.id,
                    [e.id, e.canonical_name[:30], (e.license_id or "?")[:16], e.integration_state],
                    hay,
                )
            )
        return rows

    def render_detail(self, key: str) -> str:
        from tracefield.registry import Catalog, default_catalog_path

        catalog = Catalog(default_catalog_path())
        e = catalog.get(key)
        if e is not None:
            return "\n".join(
                [
                    f"{e.canonical_name}  ({e.id})",
                    f"  entry type       {e.entry_type}",
                    f"  upstream         {sanitize_for_terminal(e.upstream_url)}",
                    f"  license          {e.license_id or '(unreviewed)'}",
                    f"  license review   {e.license_review_state}",
                    f"  first seen       {e.first_seen}",
                    f"  last checked     {e.last_checked}",
                    f"  verification     {e.verification_state}",
                    f"  maintenance      {e.maintenance_status}",
                    f"  network required {e.network_required}",
                    f"  integration      {e.integration_state}",
                    "",
                    "tier states are verbatim catalogue records:",
                    "indexed/verified mean the RECORD was checked;",
                    "nothing here is 'healthy' — health needs a",
                    "dated runtime check (not implemented).",
                ]
            )
        return "catalogue entry not found"


class FieldView(Vertical):
    """Local utilities bound to the active case (CLI-equivalent steps)."""

    VIEW_TITLE = "Field"
    MULTI_PANE = False
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("a", "attach_path", "Attach to case", show=True),
    ]

    def __init__(self, tui: TracefieldApp, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.tui = tui
        self.last_hash: tuple[str, str] | None = None  # (path, sha256)

    def compose(self) -> ComposeResult:
        yield Input(placeholder="path to a local file (Enter hashes it)", id="field-path")
        yield Static("Enter  hash the file    a  attach to the active case", id="field-hint")
        yield Static("", id="field-result", classes="detail-pane")

    def _path(self) -> str:
        return self.query_one("#field-path", Input).value.strip()

    def _result(self) -> Static:
        return self.query_one("#field-result", Static)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "field-path":
            self.run_worker(self.action_hash_path())

    async def action_hash_path(self) -> None:
        tui = self.tui
        path = self._path()
        if not path:
            tui.hint("enter a file path first")
            return
        tui.begin_op("field: hash")
        try:
            digest = await asyncio.to_thread(hash_file, path)
        except OSError as exc:
            self.last_hash = None
            self._result().update(sanitize_for_terminal(f"hash failed: {exc}"))
            tui.finish_op(OP_FAILED, exit_code=2, message=str(exc))
            return
        self.last_hash = (path, digest)
        result = self._result()
        result.update(sanitize_for_terminal(f"sha256 {digest}"))
        # Move focus off the path Input so `a` reaches the view binding
        # instead of typing into the field.
        result.can_focus = True
        result.focus()
        tui.finish_op(OP_DONE)

    async def action_attach_path(self) -> None:
        tui = self.tui
        path = self._path()
        cid = tui.active_case_id
        if cid is None:
            tui.hint("no active case — press c to select one")
            return
        if not path:
            tui.hint("enter a file path first")
            return
        tui.begin_op("field: attach")
        from tracefield.core.domain import AccessMethod, Source, SourceType
        from tracefield.fieldtools.inspect import detect_media_type

        try:
            media_type = detect_media_type(path)
            source = Source(
                case_id=cid,
                locator=path,
                source_type=SourceType.LOCAL_FILE,
                access_method=AccessMethod.MANUAL,
            )
            tui.source_repo.add(source)
            ws = tui.workspace
            if ws is None:
                raise RuntimeError("workspace not ready")
            evidence = await asyncio.to_thread(
                ws.attach_file,
                cid,
                source.id,
                path,
                media_type=media_type,
            )
        except Exception as exc:
            self._result().update(sanitize_for_terminal(f"attach failed: {exc}"))
            tui.finish_op(OP_FAILED, exit_code=1, message=str(exc))
            return
        self.last_hash = (path, evidence.sha256)
        self._result().update(
            sanitize_for_terminal(
                f"evidence {evidence.id}\n  source {source.id}\n  sha256 {evidence.sha256}\n"
                f"  media {evidence.media_type}  size {evidence.size_bytes}"
            )
        )
        tui.finish_op(OP_DONE)
        tui.run_view_refresh(tui.view_by_index(1))  # refresh Evidence


class RunsView(ListView):
    """Event history of the ACTIVE case plus this session's op log."""

    VIEW_TITLE = "Runs"
    COLUMNS: ClassVar[list[str]] = ["occurred at", "action", "digest"]
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("tab", "next_pane", "Next pane", show=True),
        Binding("enter", "open_detail", "Inspect", show=True),
        Binding("slash", "filter", "Filter", show=True),
        Binding("v", "verify_chain", "Verify chain", show=True),
    ]

    def compose(self) -> ComposeResult:
        yield from super().compose()
        yield Static("", id="runs-verify")
        yield Static("", id="runs-ops")

    def fetch_rows(self) -> list[tuple[str, list[str], str]]:
        cid = self.tui.active_case_id
        if cid is None:
            return []
        rows = []
        for e in self.tui.event_repo.list_for_case(cid):
            hay = f"{e.id} {e.action} {e.digest}".lower()
            rows.append((e.id, [e.occurred_at, e.action, e.digest[:12] + "…"], hay))
        return rows

    def render_detail(self, key: str) -> str:
        cid = self.tui.active_case_id
        ev = self.tui.event_repo.get(key)
        if ev is None or ev.case_id != cid:
            return "event not found in the active case"
        return "\n".join(
            [
                f"event {ev.id}",
                f"  action       {ev.action}",
                f"  occurred at  {ev.occurred_at}",
                f"  digest       {ev.digest}",
                f"  prev digest  {ev.prev_digest or '(genesis)'}",
                f"  inputs       {', '.join(ev.inputs) or '(none)'}",
                f"  outputs      {', '.join(ev.outputs) or '(none)'}",
                f"  tool         {ev.tool_fingerprint or '(none)'}",
            ]
        )

    def on_mount(self) -> None:
        super().on_mount()
        self.refresh_op_log()

    def refresh_op_log(self) -> None:
        ops = self.query_one("#runs-ops", Static)
        entries = self.tui.op_log[-10:]
        if not entries:
            ops.update("session operations: (none yet)")
            return
        lines = ["session operations (this TUI run only):"]
        for entry in entries:
            code = f" exit {entry['exit_code']}" if entry.get("exit_code") else ""
            count = f" ({entry['count']})" if entry.get("count") else ""
            lines.append(f"  {entry['at']}  {entry['state']:<9}  {entry['label']}{count}{code}")
        ops.update(sanitize_for_terminal("\n".join(lines)))

    async def action_verify_chain(self) -> None:
        tui = self.tui
        cid = tui.active_case_id
        if cid is None:
            tui.hint("no active case — press c to select one")
            return
        tui.begin_op("runs: verify chain")
        ok, summary = tui.event_repo.verify_chain(cid)
        verdict = "VERIFIED" if ok else "BROKEN"
        self.query_one("#runs-verify", Static).update(f"chain: {verdict} — {summary}")
        tui.finish_op(OP_DONE if ok else OP_FAILED, exit_code=None if ok else 1)
