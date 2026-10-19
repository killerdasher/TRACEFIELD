"""TRACEFIELD command-line interface.

Keyboard-first, JSON-capable, deterministic exit codes, no network by
default. Every advertised command has a real implementation. All untrusted
strings are sanitized before terminal rendering; secrets are redacted.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, NoReturn

import typer
from rich.console import Console
from rich.table import Table

try:
    # typer >= 0.16 vendors its own click fork
    from typer._click.exceptions import ClickException, UsageError
except ImportError:  # pragma: no cover - fallback for typer bundling real click
    from click.exceptions import ClickException, UsageError  # type: ignore[assignment]

from tracefield import __version__
from tracefield.config import Settings, load_settings
from tracefield.core.domain import (
    AccessMethod,
    Case,
    Claim,
    Observation,
    Relation,
    RelationType,
    ReviewState,
    Source,
    SourceType,
    utcnow,
)
from tracefield.core.provenance import compute_event_digest
from tracefield.security import sanitize_for_terminal
from tracefield.storage import CaseWorkspace, Database
from tracefield.storage.repositories import (
    CaseRepo,
    ClaimRepo,
    ClusterRepo,
    EventRepo,
    EvidenceRepo,
    ObservationRepo,
    RelationRepo,
    SourceRepo,
)

# ---------------------------------------------------------------------------
# Exit codes — stable contract for scripts.
# ---------------------------------------------------------------------------
EXIT_OK = 0
EXIT_ERROR = 1
EXIT_NOT_FOUND = 2
EXIT_USAGE = 3
EXIT_NETWORK_BLOCKED = 4
EXIT_UNAVAILABLE = 5

app = typer.Typer(
    name="tracefield",
    help="Terminal-first OSINT field workbench with evidence provenance.",
    no_args_is_help=True,
    add_completion=True,
    pretty_exceptions_enable=False,
)
case_app = typer.Typer(help="Case lifecycle.", no_args_is_help=True)
source_app = typer.Typer(help="Source records.", no_args_is_help=True)
claim_app = typer.Typer(help="Claims.", no_args_is_help=True)
evidence_app = typer.Typer(help="Evidence attachment.", no_args_is_help=True)
observation_app = typer.Typer(help="Raw tool observations (uninterpreted).", no_args_is_help=True)
relation_app = typer.Typer(help="Relations between records.", no_args_is_help=True)
analyze_app = typer.Typer(help="Analysis engine.", no_args_is_help=True)
tools_app = typer.Typer(help="Tool catalogue (inert metadata).", no_args_is_help=True)
catalog_app = typer.Typer(help="Catalogue import/validation.", no_args_is_help=True)
username_app = typer.Typer(help="Public username checks (opt-in network).", no_args_is_help=True)
app.add_typer(case_app, name="case")
app.add_typer(source_app, name="source")
app.add_typer(claim_app, name="claim")
app.add_typer(evidence_app, name="evidence")
app.add_typer(observation_app, name="observation")
app.add_typer(relation_app, name="relation")
app.add_typer(analyze_app, name="analyze")
app.add_typer(tools_app, name="tools")
app.add_typer(catalog_app, name="catalog")
app.add_typer(username_app, name="username")

console = Console()
err_console = Console(stderr=True)


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------


def s(text: str, max_length: int | None = 200) -> str:
    """Sanitize an untrusted string for terminal display.

    Strips control sequences AND escapes rich markup, so hostile titles,
    locators, or provider text cannot emit escape codes or spoof styling.
    """
    from rich.markup import escape

    return escape(sanitize_for_terminal(text, max_length=max_length))


def emit(
    payload: dict[str, Any] | list[Any],
    as_json: bool,
    render: Callable[[Any], None] | None = None,
) -> None:
    if as_json:
        console.print_json(json.dumps(payload))
    elif render is not None:
        render(payload)


def fail(message: str, code: int = EXIT_ERROR) -> NoReturn:
    from tracefield.config.logging import get_logger

    get_logger("cli").error(message, extra={"event": "fail", "exit_code": code})
    err_console.print(f"[red]error:[/red] {s(message, 400)}")
    raise SystemExit(code)


def open_db(settings: Settings) -> Database:
    settings.ensure_dirs()
    return Database(settings.db_path)


def resolve_case(repo: CaseRepo, ref: str) -> Case:
    case = repo.resolve(ref)
    if case is None:
        fail(f"case not found: {ref!r}", EXIT_NOT_FOUND)
    return case


def _append_event(
    ws: CaseWorkspace, case_id: str, action: str, inputs: list[str], outputs: list[str]
) -> None:
    prev = ws.events.last_digest(case_id)
    occurred = utcnow()
    from tracefield.core.domain import AnalysisEvent

    ev = AnalysisEvent(
        case_id=case_id,
        action=action,
        inputs=inputs,
        outputs=outputs,
        tool_fingerprint=f"tracefield/{__version__}",
        prev_digest=prev,
        occurred_at=occurred,
    )
    ev.digest = compute_event_digest(ev.action, ev.inputs, ev.outputs, prev, occurred)
    ws.events.append(ev)


# ---------------------------------------------------------------------------
# Root commands
# ---------------------------------------------------------------------------


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"tracefield {__version__}")
        raise SystemExit(EXIT_OK)


@app.callback()
def main_callback(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        callback=_version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """TRACEFIELD — terminal-first OSINT field workbench."""


@app.command()
def doctor(
    as_json: bool = typer.Option(False, "--json", help="Machine-readable output."),
) -> None:
    """Check local environment. Never makes network calls."""
    import shutil as _shutil

    settings = load_settings()
    checks: list[dict[str, str]] = []

    checks.append(
        {
            "name": "python",
            "status": "ok",
            "detail": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        }
    )
    checks.append({"name": "version", "status": "ok", "detail": __version__})

    try:
        settings.ensure_dirs()
        db = Database(settings.db_path)
        checks.append(
            {
                "name": "database",
                "status": "ok",
                "detail": f"schema v{db.schema_version} at {settings.db_path}",
            }
        )
        db.close()
    except Exception as exc:
        checks.append({"name": "database", "status": "fail", "detail": str(exc)})

    for tool, label in (
        ("exiftool", "metadata extraction"),
        ("ffprobe", "media stream metadata"),
        ("tesseract", "OCR backend"),
    ):
        path = _shutil.which(tool)
        checks.append(
            {
                "name": tool,
                "status": "ok" if path else "missing",
                "detail": path
                or f"{label} unavailable — related commands will report UNAVAILABLE, not success",
            }
        )

    checks.append(
        {
            "name": "network",
            "status": "blocked" if not settings.allow_network else "allowed",
            "detail": "fetches disabled by default; enable with "
            "TRACEFIELD_ALLOW_NETWORK=1 (still validated per-URL, "
            "SSRF-guarded, IP-pinned)",
        }
    )
    checks.append(
        {
            "name": "username_check",
            "status": "enabled" if settings.username_check_enabled else "disabled",
            "detail": "enable with TRACEFIELD_USERNAME_CHECK=1; conservative, "
            "curated providers only, no bulk mode",
        }
    )
    checks.append(
        {"name": "telemetry", "status": "none", "detail": "this release contains no telemetry"}
    )

    def render(_: dict[str, Any]) -> None:
        table = Table(title="tracefield doctor", show_lines=False)
        table.add_column("check")
        table.add_column("status")
        table.add_column("detail")
        for c in checks:
            color = {
                "ok": "green",
                "fail": "red",
                "missing": "yellow",
                "blocked": "yellow",
                "disabled": "yellow",
                "allowed": "green",
                "enabled": "green",
                "none": "green",
            }.get(c["status"], "white")
            table.add_row(c["name"], f"[{color}]{c['status']}[/{color}]", s(c["detail"], 120))
        console.print(table)
        if any(c["status"] == "fail" for c in checks):
            err_console.print("[red]doctor found failing checks[/red]")

    emit({"checks": checks}, as_json, render)
    if any(c["status"] == "fail" for c in checks):
        raise SystemExit(EXIT_ERROR)


@app.command("init")
def init_cmd(
    force: bool = typer.Option(False, "--force", help="Re-initialize data root."),
) -> None:
    """Initialize the local data directory and database."""
    settings = load_settings()
    if settings.data_root.exists() and not force:
        console.print(f"already initialized: {settings.data_root}")
    else:
        settings.ensure_dirs()
        db = Database(settings.db_path)
        db.close()
        console.print(f"initialized: {settings.data_root}")


# ---------------------------------------------------------------------------
# case
# ---------------------------------------------------------------------------


@case_app.command("create")
def case_create(
    name: str = typer.Argument(..., help="Case title."),
    purpose: str = typer.Option("", "--purpose", help="Declared purpose."),
    scope: str = typer.Option("", "--scope", help="Declared scope."),
    as_json: bool = typer.Option(False, "--json", help="Machine-readable output."),
) -> None:
    """Create a new case."""
    settings = load_settings()
    db = open_db(settings)
    try:
        repo = CaseRepo(db)
        existing = repo.get_by_title(name)
        if existing:
            fail(f"case with title {name!r} already exists: {existing.id}", EXIT_USAGE)
        case = Case(title=name, purpose=purpose, scope=scope)
        ws = CaseWorkspace(settings.cases_root, db)
        ws.case_dir(case.id)
        repo.create(case)

        def render(c: dict[str, Any]) -> None:
            console.print(f"[green]created[/green] case [bold]{c['id']}[/bold]")
            console.print(f"  title:   {s(c['title'])}")
            if c.get("purpose"):
                console.print(f"  purpose: {s(c['purpose'])}")
            if c.get("scope"):
                console.print(f"  scope:   {s(c['scope'])}")

        emit(case.model_dump(), as_json, render)
    finally:
        db.close()


@case_app.command("list")
def case_list(
    as_json: bool = typer.Option(False, "--json", help="Machine-readable output."),
) -> None:
    """List cases."""
    settings = load_settings()
    db = open_db(settings)
    try:
        cases = CaseRepo(db).list()
        payload = [c.model_dump() for c in cases]

        def render(items: list[dict[str, Any]]) -> None:
            if not items:
                console.print("no cases yet — create one with: tracefield case create <name>")
                return
            table = Table(title="cases")
            table.add_column("id")
            table.add_column("title")
            table.add_column("status")
            table.add_column("created")
            for c in items:
                table.add_row(c["id"], s(c["title"]), c["status"], c["created_at"])
            console.print(table)

        emit(payload, as_json, render)
    finally:
        db.close()


@case_app.command("show")
def case_show(
    ref: str = typer.Argument(..., help="Case ID or title."),
    as_json: bool = typer.Option(False, "--json", help="Machine-readable output."),
) -> None:
    """Show one case with its sources, claims, and evidence counts."""
    settings = load_settings()
    db = open_db(settings)
    try:
        repo = CaseRepo(db)
        case = resolve_case(repo, ref)
        sources = SourceRepo(db).list_for_case(case.id)
        claims = ClaimRepo(db).list_for_case(case.id)
        evidence = EvidenceRepo(db).list_for_case(case.id)
        relations = RelationRepo(db).list_for_case(case.id)
        payload = {
            **case.model_dump(),
            "counts": {
                "sources": len(sources),
                "claims": len(claims),
                "evidence": len(evidence),
                "relations": len(relations),
            },
        }

        def render(p: dict[str, Any]) -> None:
            console.print(f"[bold]{p['id']}[/bold] — {s(p['title'])}")
            console.print(f"  status:  {p['status']}")
            console.print(f"  purpose: {s(p['purpose']) or '(none declared)'}")
            console.print(f"  scope:   {s(p['scope']) or '(none declared)'}")
            console.print(f"  created: {p['created_at']}")
            counts = p["counts"]
            console.print(
                f"  records: {counts['sources']} sources, "
                f"{counts['claims']} claims, {counts['evidence']} evidence, "
                f"{counts['relations']} relations"
            )

        emit(payload, as_json, render)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# source
# ---------------------------------------------------------------------------


@source_app.command("add")
def source_add(
    locator: str = typer.Argument(..., help="URL or local path."),
    case: str = typer.Option(..., "--case", help="Case ID or title."),
    publisher: str = typer.Option("", "--publisher", help="Publisher/outlet name, if known."),
    limitations: str = typer.Option(
        "",
        "--limitations",
        help="Collection notes / honest limitations (also used by origin "
        "clustering as document text).",
    ),
    fetch: bool = typer.Option(
        False,
        "--fetch",
        help="Fetch the URL now (requires network opt-in).",
    ),
    as_json: bool = typer.Option(False, "--json", help="Machine-readable output."),
) -> None:
    """Register a source. Does NOT fetch unless --fetch is passed."""
    settings = load_settings()
    db = open_db(settings)
    try:
        case_obj = resolve_case(CaseRepo(db), case)
        is_url = locator.startswith(("http://", "https://"))
        source = Source(
            case_id=case_obj.id,
            locator=locator,
            publisher=publisher,
            limitations=limitations,
            source_type=SourceType.WEB_PAGE if is_url else SourceType.LOCAL_FILE,
            access_method=AccessMethod.MANUAL,
            first_seen_at=utcnow(),
        )

        if fetch:
            from tracefield.fieldtools.fetch import FetchError, fetch_source
            from tracefield.security import UrlPolicyError

            if not settings.allow_network:
                fail(
                    "network is disabled by default; set TRACEFIELD_ALLOW_NETWORK=1 "
                    "to permit fetches (URLs are still validated per-request)",
                    EXIT_NETWORK_BLOCKED,
                )
            try:
                source = fetch_source(source, settings)
            except UrlPolicyError as exc:
                fail(f"URL rejected by safety policy: {exc}", EXIT_NETWORK_BLOCKED)
            except FetchError as exc:
                source.limitations = f"fetch failed: {exc}"
                err_console.print(
                    f"[yellow]warning:[/yellow] fetch failed, source registered "
                    f"with error note: {s(str(exc))}"
                )

        SourceRepo(db).add(source)
        ws = CaseWorkspace(settings.cases_root, db)
        _append_event(ws, case_obj.id, "source.add", [locator], [source.id])

        def render(src: dict[str, Any]) -> None:
            console.print(f"[green]added[/green] source [bold]{src['id']}[/bold]")
            console.print(f"  locator: {s(src['locator'])}")
            console.print(f"  type:    {src['source_type']}")
            if src.get("publisher"):
                console.print(f"  publisher: {s(src['publisher'], 120)}")
            if src.get("limitations"):
                console.print(f"  note:    {s(src['limitations'], 300)}")

        emit(source.model_dump(), as_json, render)
    finally:
        db.close()


@source_app.command("list")
def source_list(
    case: str = typer.Option(..., "--case", help="Case ID or title."),
    as_json: bool = typer.Option(False, "--json", help="Machine-readable output."),
) -> None:
    """List sources for a case."""
    settings = load_settings()
    db = open_db(settings)
    try:
        case_obj = resolve_case(CaseRepo(db), case)
        sources = SourceRepo(db).list_for_case(case_obj.id)
        payload = [src.model_dump() for src in sources]

        def render(items: list[dict[str, Any]]) -> None:
            if not items:
                console.print("no sources")
                return
            table = Table(title=f"sources — {s(case_obj.title)}")
            table.add_column("id")
            table.add_column("locator")
            table.add_column("type")
            table.add_column("first_seen")
            for src in items:
                table.add_row(
                    src["id"],
                    s(src["locator"], 60),
                    src["source_type"],
                    src["first_seen_at"],
                )
            console.print(table)

        emit(payload, as_json, render)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# claim
# ---------------------------------------------------------------------------


@claim_app.command("add")
def claim_add(
    text: str = typer.Option(..., "--text", help="Exact, narrowly scoped claim."),
    case: str = typer.Option(..., "--case", help="Case ID or title."),
    claim_type: str = typer.Option("factual", "--type", help="Claim type."),
    as_json: bool = typer.Option(False, "--json", help="Machine-readable output."),
) -> None:
    """Add a claim to a case."""
    settings = load_settings()
    db = open_db(settings)
    try:
        case_obj = resolve_case(CaseRepo(db), case)
        claim = Claim(case_id=case_obj.id, text=text, claim_type=claim_type)
        ClaimRepo(db).add(claim)

        def render(c: dict[str, Any]) -> None:
            console.print(f"[green]added[/green] claim [bold]{c['id']}[/bold]")
            console.print(f"  {s(c['text'], 300)}")

        emit(claim.model_dump(), as_json, render)
    finally:
        db.close()


@claim_app.command("list")
def claim_list(
    case: str = typer.Option(..., "--case", help="Case ID or title."),
    as_json: bool = typer.Option(False, "--json", help="Machine-readable output."),
) -> None:
    """List claims for a case."""
    settings = load_settings()
    db = open_db(settings)
    try:
        case_obj = resolve_case(CaseRepo(db), case)
        claims = ClaimRepo(db).list_for_case(case_obj.id)
        payload = [c.model_dump() for c in claims]

        def render(items: list[dict[str, Any]]) -> None:
            if not items:
                console.print("no claims")
                return
            table = Table(title=f"claims — {s(case_obj.title)}")
            table.add_column("id")
            table.add_column("text")
            table.add_column("status")
            table.add_column("review")
            for c in items:
                table.add_row(c["id"], s(c["text"], 70), c["status"], c["review_state"])
            console.print(table)

        emit(payload, as_json, render)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# evidence
# ---------------------------------------------------------------------------


@evidence_app.command("attach")
def evidence_attach(
    path: Path = typer.Argument(..., exists=True, readable=True, dir_okay=False),
    case: str = typer.Option(..., "--case", help="Case ID or title."),
    source: str = typer.Option(
        "",
        "--source",
        help="Source ID (created automatically for local files).",
    ),
    excerpt: str = typer.Option(
        "",
        "--excerpt",
        help="Faithful short text excerpt; enables structured contradiction "
        "comparison against other excerpts in this case.",
    ),
    as_json: bool = typer.Option(False, "--json", help="Machine-readable output."),
) -> None:
    """Attach a local file as immutable evidence (content-addressed copy)."""
    settings = load_settings()
    db = open_db(settings)
    try:
        case_obj = resolve_case(CaseRepo(db), case)
        src_repo = SourceRepo(db)
        if source:
            src = src_repo.get(source)
            if src is None:
                fail(f"source not found: {source!r}", EXIT_NOT_FOUND)
            if src.case_id != case_obj.id:
                fail(
                    "source belongs to a different case (cross-case provenance is not permitted)",
                    EXIT_USAGE,
                )
        else:
            src = Source(
                case_id=case_obj.id,
                locator=str(path.resolve()),
                source_type=SourceType.LOCAL_FILE,
                access_method=AccessMethod.PROVIDED,
            )
            src_repo.add(src)

        from tracefield.fieldtools.inspect import detect_media_type
        from tracefield.storage.workspace import WorkspaceError

        ws = CaseWorkspace(settings.cases_root, db)
        media_type = detect_media_type(path)
        try:
            ev = ws.attach_file(case_obj.id, src.id, path, media_type=media_type, excerpt=excerpt)
        except WorkspaceError as exc:
            fail(str(exc), EXIT_USAGE)

        def render(e: dict[str, Any]) -> None:
            console.print(f"[green]attached[/green] evidence [bold]{e['id']}[/bold]")
            console.print(f"  sha256:    {e['sha256']}")
            console.print(f"  media:     {e['media_type']}")
            console.print(f"  size:      {e['size_bytes']} bytes")
            console.print(f"  storage:   {s(e['storage_ref'])}")

        emit(ev.model_dump(), as_json, render)
    finally:
        db.close()


@evidence_app.command("list")
def evidence_list(
    case: str = typer.Option(..., "--case", help="Case ID or title."),
    as_json: bool = typer.Option(False, "--json", help="Machine-readable output."),
) -> None:
    """List evidence for a case."""
    settings = load_settings()
    db = open_db(settings)
    try:
        case_obj = resolve_case(CaseRepo(db), case)
        evs = EvidenceRepo(db).list_for_case(case_obj.id)
        payload = [e.model_dump() for e in evs]

        def render(items: list[dict[str, Any]]) -> None:
            if not items:
                console.print("no evidence attached")
                return
            table = Table(title=f"evidence — {s(case_obj.title)}")
            table.add_column("id")
            table.add_column("sha256")
            table.add_column("media")
            table.add_column("size")
            table.add_column("source")
            for e in items:
                table.add_row(
                    e["id"],
                    e["sha256"][:16] + "…",
                    e["media_type"],
                    str(e["size_bytes"]),
                    e["source_id"],
                )
            console.print(table)

        emit(payload, as_json, render)
    finally:
        db.close()


@evidence_app.command("verify")
def evidence_verify(
    case: str = typer.Option(..., "--case", help="Case ID or title."),
    as_json: bool = typer.Option(False, "--json", help="Machine-readable output."),
) -> None:
    """Re-hash stored evidence and compare against recorded digests."""
    settings = load_settings()
    db = open_db(settings)
    try:
        case_obj = resolve_case(CaseRepo(db), case)
        ws = CaseWorkspace(settings.cases_root, db)
        results = []
        all_ok = True
        for ev in EvidenceRepo(db).list_for_case(case_obj.id):
            ok = ws.verify_evidence(case_obj.id, ev)
            all_ok = all_ok and ok
            results.append({"id": ev.id, "sha256": ev.sha256, "intact": ok})

        def render(payload: dict[str, Any]) -> None:
            for r in payload["files"]:
                mark = "[green]OK[/green]" if r["intact"] else "[red]MISMATCH[/red]"
                console.print(f"{mark}  {r['id']}  {r['sha256'][:16]}…")
            console.print(
                f"{len(payload['files'])} files checked; "
                f"{'all intact' if payload['all_intact'] else 'FAILURES PRESENT'}"
            )

        emit({"files": results, "all_intact": all_ok}, as_json, render)
        if not all_ok:
            raise SystemExit(EXIT_ERROR)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# observation — raw, uninterpreted tool returns
# ---------------------------------------------------------------------------


@observation_app.command("add")
def observation_add(
    case: str = typer.Option(..., "--case", help="Case ID or title."),
    tool: str = typer.Option(..., "--tool", help="Tool/service that produced this."),
    summary: str = typer.Option("", "--summary", help="One-line summary of the return."),
    evidence: str = typer.Option("", "--evidence", help="Related evidence ID (optional)."),
    raw_ref: str = typer.Option("", "--raw-ref", help="Storage ref of the raw response."),
    tool_version: str = typer.Option("", "--tool-version", help="Tool version if known."),
    as_json: bool = typer.Option(False, "--json", help="Machine-readable output."),
) -> None:
    """Record a raw tool observation. Never interpreted as a finding."""
    settings = load_settings()
    db = open_db(settings)
    try:
        case_obj = resolve_case(CaseRepo(db), case)
        if evidence:
            ev = EvidenceRepo(db).get(evidence)
            if ev is None or ev.case_id != case_obj.id:
                fail(f"evidence not found in this case: {evidence!r}", EXIT_NOT_FOUND)
        obs = Observation(
            case_id=case_obj.id,
            evidence_id=evidence,
            tool_name=s(tool, 200),
            tool_version=s(tool_version, 100),
            raw_ref=s(raw_ref, 400),
            summary=s(summary, 500),
        )
        ObservationRepo(db).add(obs)
        ws = CaseWorkspace(settings.cases_root, db)
        _append_event(ws, case_obj.id, "observation.add", [obs.tool_name], [obs.id])

        def render(o: dict[str, Any]) -> None:
            console.print(f"[green]recorded[/green] observation [bold]{o['id']}[/bold]")
            console.print(f"  tool:   {s(o['tool_name'])}")
            if o.get("summary"):
                console.print(f"  summary:{' '}{s(o['summary'])}")
            console.print(
                "[dim]an observation is a raw return — not a verified fact until reviewed[/dim]"
            )

        emit(obs.model_dump(), as_json, render)
    finally:
        db.close()


@observation_app.command("list")
def observation_list(
    case: str = typer.Option(..., "--case", help="Case ID or title."),
    as_json: bool = typer.Option(False, "--json", help="Machine-readable output."),
) -> None:
    """List recorded observations for a case."""
    settings = load_settings()
    db = open_db(settings)
    try:
        case_obj = resolve_case(CaseRepo(db), case)
        items = ObservationRepo(db).list_for_case(case_obj.id)

        def render(rows: list[dict[str, Any]]) -> None:
            if not rows:
                console.print("no observations recorded")
                return
            table = Table(title="observations")
            table.add_column("id")
            table.add_column("tool")
            table.add_column("returned")
            table.add_column("summary")
            for o in rows:
                table.add_row(o["id"], s(o["tool_name"], 40), o["returned_at"], s(o["summary"], 60))
            console.print(table)

        emit([o.model_dump() for o in items], as_json, render)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# relation
# ---------------------------------------------------------------------------


@relation_app.command("add")
def relation_add(
    case: str = typer.Option(..., "--case", help="Case ID or title."),
    from_id: str = typer.Option(..., "--from", help="Source record ID (origin)."),
    to_id: str = typer.Option(..., "--to", help="Target record ID (claim/evidence)."),
    kind: str = typer.Option(
        ...,
        "--type",
        help="supports|contradicts|corroborates|derived_from|mentions|origin_hypothesis",
    ),
    rationale: str = typer.Option("", "--rationale", help="Why this relation exists."),
    evidence: str = typer.Option(
        "",
        "--evidence",
        help="Comma-separated evidence IDs backing this relation.",
    ),
    as_json: bool = typer.Option(False, "--json", help="Machine-readable output."),
) -> None:
    """Create an evidence-linked relation between two records."""
    settings = load_settings()
    db = open_db(settings)
    try:
        case_obj = resolve_case(CaseRepo(db), case)
        try:
            rtype = RelationType(kind)
        except ValueError:
            fail(
                f"invalid relation type {kind!r}; use one of: "
                + ", ".join(rt.value for rt in RelationType),
                EXIT_USAGE,
            )
        ev_ids = [e.strip() for e in evidence.split(",") if e.strip()]
        for eid in ev_ids:
            ev = EvidenceRepo(db).get(eid)
            if ev is None or ev.case_id != case_obj.id:
                fail(f"evidence not found in this case: {eid!r}", EXIT_NOT_FOUND)
        rel = Relation(
            case_id=case_obj.id,
            from_id=from_id,
            to_id=to_id,
            relation=rtype,
            rationale=rationale,
            method="analyst",
            review_state=ReviewState.UNREVIEWED,
            evidence_ids=ev_ids,
        )
        RelationRepo(db).add(rel)
        ws = CaseWorkspace(settings.cases_root, db)
        _append_event(ws, case_obj.id, "relation.add", [from_id, to_id], [rel.id])

        def render(r: dict[str, Any]) -> None:
            console.print(f"[green]added[/green] relation [bold]{r['id']}[/bold]")
            console.print(
                f"  {r['from_id']} —[{r['relation']}]→ {r['to_id']}  [{r['review_state']}]"
            )
            if r["evidence_ids"]:
                console.print(f"  evidence: {', '.join(r['evidence_ids'])}")
            console.print(
                "[dim]unreviewed relations are not evidence — review with: "
                f"tracefield relation review {r['id']} --state confirmed[/dim]"
            )

        emit(rel.model_dump(), as_json, render)
    finally:
        db.close()


@relation_app.command("review")
def relation_review(
    relation_id: str = typer.Argument(..., help="Relation ID."),
    state: str = typer.Option(
        ...,
        "--state",
        help="confirmed|rejected|unresolved|unreviewed",
    ),
) -> None:
    """Set the analyst review state of a relation."""
    settings = load_settings()
    db = open_db(settings)
    try:
        repo = RelationRepo(db)
        rel = repo.get(relation_id)
        if rel is None:
            fail(f"relation not found: {relation_id!r}", EXIT_NOT_FOUND)
        try:
            new_state = ReviewState(state)
        except ValueError:
            fail(f"invalid state {state!r}", EXIT_USAGE)
        repo.set_review_state(relation_id, new_state)
        console.print(f"relation {relation_id} → {new_state.value}")
    finally:
        db.close()


@relation_app.command("list")
def relation_list(
    case: str = typer.Option(..., "--case", help="Case ID or title."),
    as_json: bool = typer.Option(False, "--json", help="Machine-readable output."),
) -> None:
    """List relations for a case."""
    settings = load_settings()
    db = open_db(settings)
    try:
        case_obj = resolve_case(CaseRepo(db), case)
        rels = RelationRepo(db).list_for_case(case_obj.id)
        payload = [r.model_dump() for r in rels]

        def render(items: list[dict[str, Any]]) -> None:
            if not items:
                console.print("no relations")
                return
            table = Table(title=f"relations — {s(case_obj.title)}")
            table.add_column("id")
            table.add_column("from")
            table.add_column("type")
            table.add_column("to")
            table.add_column("review")
            for r in items:
                table.add_row(r["id"], r["from_id"], r["relation"], r["to_id"], r["review_state"])
            console.print(table)

        emit(payload, as_json, render)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# analyze
# ---------------------------------------------------------------------------


@analyze_app.command("claim")
def analyze_claim_cmd(
    claim_id: str = typer.Argument(..., help="Claim ID."),
    case: str = typer.Option(..., "--case", help="Case ID or title."),
    as_json: bool = typer.Option(False, "--json", help="Machine-readable output."),
) -> None:
    """Assess a claim using documented, deterministic rules; explain the vector."""
    settings = load_settings()
    db = open_db(settings)
    try:
        case_obj = resolve_case(CaseRepo(db), case)
        claim = ClaimRepo(db).get(claim_id)
        if claim is None or claim.case_id != case_obj.id:
            fail(f"claim not found in this case: {claim_id!r}", EXIT_NOT_FOUND)
        relations = RelationRepo(db).list_for_case(case_obj.id)
        claim_rels = [r for r in relations if r.from_id == claim.id or r.to_id == claim.id]
        # Relations whose from_id is a source supporting this claim via evidence.
        clusters = ClusterRepo(db).list_for_case(case_obj.id)
        clustered_ids: set[str] = set()
        for c in clusters:
            clustered_ids.update(c.member_ids)

        from tracefield.core.analysis import assess_claim

        v = assess_claim(
            claim,
            claim_rels,
            origin_clusters=len(clusters),
            clustered_origin_ids=clustered_ids,
        )

        def render(p: dict[str, Any]) -> None:
            console.print(f"[bold]claim[/bold] {p['claim_id']}")
            console.print(f"  outcome:   [bold]{p['outcome']}[/bold]")
            console.print(f"  rules:     {p['rule_version']}")
            console.print(f"  provenance:{p['provenance_completeness']}")
            console.print(f"  directness:{p['evidence_directness']}")
            console.print(f"  indep.:    {s(p['independence'], 120)}")
            console.print(
                f"  support/contradict: {p['supporting_count']}/{p['contradicting_count']}"
            )
            for caveat in p["caveats"]:
                console.print(f"  [yellow]caveat:[/yellow] {s(caveat, 200)}")

        emit(v.model_dump(), as_json, render)
    finally:
        db.close()


@analyze_app.command("origins")
def analyze_origins_cmd(
    case: str = typer.Option(..., "--case", help="Case ID or title."),
    as_json: bool = typer.Option(False, "--json", help="Machine-readable output."),
) -> None:
    """Run origin clustering over the case's sources (URL + limitations text).

    Produces HYPOTHESIS clusters with explainable indicators; review each
    with `relation review`-style confirmation before relying on them.
    """
    settings = load_settings()
    db = open_db(settings)
    try:
        case_obj = resolve_case(CaseRepo(db), case)
        sources = SourceRepo(db).list_for_case(case_obj.id)
        if len(sources) < 2:
            fail("need at least 2 sources to cluster", EXIT_USAGE)
        from tracefield.core.origins import DocInput, cluster_from_edges, find_origin_edges

        # Local file paths are NOT document text: every source in one case
        # shares the analyst's directory structure, and absolute paths
        # cluster spuriously on their common prefix (observed: two unrelated
        # fixture files merged under a long temp-dir path). Only http(s)
        # locators, limitations, and publisher names are shingled.
        docs: list[DocInput] = []
        skipped = 0
        for src in sources:
            is_url = src.locator.startswith("http")
            text = " ".join(
                p for p in (src.locator if is_url else "", src.limitations, src.publisher) if p
            ).strip()
            if len(text.split()) < 6:
                skipped += 1
                continue
            docs.append(DocInput(doc_id=src.id, url=src.locator if is_url else "", text=text))
        edges, e_note = find_origin_edges(docs)
        notes = [
            n
            for n in (
                f"skipped {skipped} source(s) with no clusterable document text" if skipped else "",
                "fewer than 2 sources carry clusterable text; no clustering performed"
                if len(docs) < 2
                else "",
                e_note,
            )
            if n
        ]
        note = "; ".join(notes)
        clusters = cluster_from_edges(case_obj.id, docs, edges)
        ws = CaseWorkspace(settings.cases_root, db)
        crepo = ClusterRepo(db)
        for c in clusters:
            crepo.add(c)
        _append_event(
            ws,
            case_obj.id,
            "analyze.origins",
            [d.doc_id for d in docs],
            [c.id for c in clusters],
        )

        def render(p: dict[str, Any]) -> None:
            if p["note"]:
                console.print(f"[yellow]note:[/yellow] {s(p['note'])}")
            if not p["clusters"]:
                console.print("no origin clusters found (all sources distinct)")
                return
            for c in p["clusters"]:
                console.print(
                    f"[bold]cluster[/bold] {c['id']}  [{c['review_state']}/{c['confidence_label']}]"
                )
                console.print(f"  members: {', '.join(c['member_ids'])}")
                for ind in c["indicators"]:
                    console.print(f"  indicator: {s(ind, 150)}")
            console.print(
                "[dim]clusters are hypotheses — confirm/reject after review; "
                "copies in one cluster must not be counted as independent "
                "confirmations[/dim]"
            )

        emit(
            {
                "clusters": [c.model_dump() for c in clusters],
                "edge_count": len(edges),
                "note": note,
            },
            as_json,
            render,
        )
    finally:
        db.close()


@analyze_app.command("contradictions")
def analyze_contradictions_cmd(
    case: str = typer.Option(..., "--case", help="Case ID or title."),
    as_json: bool = typer.Option(False, "--json", help="Machine-readable output."),
) -> None:
    """Deterministic contradiction candidates across the case's evidence excerpts."""
    settings = load_settings()
    db = open_db(settings)
    try:
        case_obj = resolve_case(CaseRepo(db), case)
        evs = EvidenceRepo(db).list_for_case(case_obj.id)
        from tracefield.core.contradictions import find_contradictions

        candidates: list[dict[str, Any]] = []
        for i, a in enumerate(evs):
            for b in evs[i + 1 :]:
                if not a.excerpt or not b.excerpt:
                    continue
                for cand in find_contradictions(a.excerpt, a.id, b.excerpt, b.id):
                    candidates.append(
                        {
                            "aspect": cand.aspect,
                            "value_a": cand.value_a,
                            "value_b": cand.value_b,
                            "evidence_a": cand.evidence_a,
                            "evidence_b": cand.evidence_b,
                            "severity": cand.severity,
                            "rule": cand.rule,
                        }
                    )

        def render(p: dict[str, Any]) -> None:
            if not p["candidates"]:
                console.print(
                    "no structured contradiction candidates "
                    "(only evidence excerpts are compared; add excerpts via "
                    "source/evidence workflow)"
                )
                return
            for c in p["candidates"]:
                console.print(
                    f"[yellow]candidate[/yellow] {c['aspect']}: "
                    f"{s(c['value_a'], 60)} vs {s(c['value_b'], 60)}"
                )
                console.print(
                    f"  {c['evidence_a']} vs {c['evidence_b']}  "
                    f"(rules {c['rule']}, severity={c['severity']})"
                )
            console.print(
                "[dim]candidates require analyst review — they are never "
                "silently treated as findings[/dim]"
            )

        emit({"candidates": candidates}, as_json, render)
    finally:
        db.close()


@analyze_app.command("events")
def analyze_events_cmd(
    case: str = typer.Option(..., "--case", help="Case ID or title."),
    as_json: bool = typer.Option(False, "--json", help="Machine-readable output."),
) -> None:
    """Show and verify the case's hash-chained analysis event log."""
    settings = load_settings()
    db = open_db(settings)
    try:
        case_obj = resolve_case(CaseRepo(db), case)
        repo = EventRepo(db)
        events = repo.list_for_case(case_obj.id)
        ok, detail = repo.verify_chain(case_obj.id)

        def render(p: dict[str, Any]) -> None:
            for ev in p["events"]:
                console.print(f"{ev['occurred_at']}  {s(ev['action'], 40)}  {ev['digest'][:12]}…")
            mark = "[green]VERIFIED[/green]" if p["chain_ok"] else "[red]BROKEN[/red]"
            console.print(f"chain: {mark} — {s(p['chain_detail'])}")
            console.print(
                "[dim]tamper-evident within this store's threat model; not a "
                "blockchain — a privileged operator rewriting every row can "
                "defeat it[/dim]"
            )

        emit(
            {
                "events": [e.model_dump() for e in events],
                "chain_ok": ok,
                "chain_detail": detail,
            },
            as_json,
            render,
        )
        if not ok:
            raise SystemExit(EXIT_ERROR)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# tools / catalog
# ---------------------------------------------------------------------------


def _default_catalog_path() -> Path:
    import tracefield as _tf

    return Path(_tf.__file__).parent.parent.parent / "data" / "catalog" / "tools.jsonl"


@tools_app.command("search")
def tools_search(
    query: str = typer.Argument("", help="Free-text query."),
    entry_type: str = typer.Option("", "--type", help="cli_tool|api_service|website|..."),
    category: str = typer.Option("", "--category"),
    license_id: str = typer.Option("", "--license"),
    key_required: str = typer.Option("", "--key-required", help="yes|no|unknown"),
    integration_state: str = typer.Option(
        "", "--state", help="indexed|verified|integrated|healthy|..."
    ),
    limit: int = typer.Option(25, "--limit"),
    as_json: bool = typer.Option(False, "--json", help="Machine-readable output."),
) -> None:
    """Search the tool catalogue (inert metadata; nothing is executed)."""
    from tracefield.registry import Catalog

    path = _default_catalog_path()
    if not path.exists():
        fail(f"catalogue data not found at {path}; run: tracefield catalog sync", EXIT_NOT_FOUND)
    cat = Catalog(path)
    results = cat.search(
        query,
        entry_type=entry_type or None,
        category=category or None,
        license_id=license_id or None,
        key_required=key_required or None,
        integration_state=integration_state or None,
        limit=limit,
    )
    payload = [r.model_dump() for r in results]

    def render(items: list[dict[str, Any]]) -> None:
        if not items:
            console.print("no matches")
            return
        table = Table(title=f"catalogue — {len(items)} match(es)")
        table.add_column("id")
        table.add_column("name")
        table.add_column("type")
        table.add_column("license")
        table.add_column("state")
        table.add_column("checked")
        for e in items:
            table.add_row(
                e["id"],
                s(e["canonical_name"], 30),
                e["entry_type"],
                s(e["license_id"], 30),
                e["integration_state"],
                e["last_checked"][:10],
            )
        console.print(table)
        console.print(
            "[dim]indexed ≠ installed ≠ integrated ≠ healthy; entries are data, never code[/dim]"
        )

    emit(payload, as_json, render)


@tools_app.command("show")
def tools_show(
    tool_id: str = typer.Argument(..., help="Catalogue ID, name, or alias."),
    as_json: bool = typer.Option(False, "--json", help="Machine-readable output."),
) -> None:
    """Show one catalogue entry in full."""
    from tracefield.registry import Catalog

    path = _default_catalog_path()
    if not path.exists():
        fail(f"catalogue data not found at {path}", EXIT_NOT_FOUND)
    cat = Catalog(path)
    entry = cat.get(tool_id)
    if entry is None:
        fail(f"catalogue entry not found: {tool_id!r}", EXIT_NOT_FOUND)

    def render(e: dict[str, Any]) -> None:
        console.print(f"[bold]{s(e['canonical_name'], 80)}[/bold]  ({e['id']})")
        console.print(f"  type:        {e['entry_type']}")
        console.print(f"  description: {s(e['description'], 200)}")
        console.print(f"  upstream:    {s(e['upstream_url'], 100)}")
        console.print(f"  license:     {s(e['license_id'], 40)} ({e['license_review_state']})")
        console.print(f"  pricing:     {e['pricing_class']}")
        console.print(f"  key req.:    {e['key_required']}")
        console.print(f"  network:     {e['network_required']}")
        console.print(f"  passive/active: {e['passive_active']}")
        console.print(f"  maintenance: {e['maintenance_status']}")
        console.print(f"  integration: {e['integration_state']}")
        console.print(f"  last checked:{e['last_checked']}")
        if e["limitations"]:
            console.print(f"  limitations: {s(e['limitations'], 200)}")
        if e["attribution"]:
            console.print(f"  attribution: {s(e['attribution'], 200)}")

    emit(entry.model_dump(), as_json, render)


@tools_app.command("status")
def tools_status(
    as_json: bool = typer.Option(False, "--json", help="Machine-readable output."),
) -> None:
    """Report honest tiered catalogue counts (never a single padded number)."""
    from tracefield.registry import Catalog

    path = _default_catalog_path()
    if not path.exists():
        fail(f"catalogue data not found at {path}", EXIT_NOT_FOUND)
    cat = Catalog(path)
    counts = cat.counts()

    def render(p: dict[str, Any]) -> None:
        console.print(f"[bold]catalogue records:[/bold] {p['total_records']}")
        console.print("  by integration state:")
        for k, v in sorted(p["by_integration_state"].items()):
            console.print(f"    {k:14} {v}")
        console.print("  by entry type:")
        for k, v in sorted(p["by_entry_type"].items()):
            console.print(f"    {k:14} {v}")
        console.print("  by license (top):")
        for k, v in sorted(p["by_license"].items(), key=lambda x: -x[1])[:8]:
            console.print(f"    {k:14} {v}")
        if p["import_errors"]:
            console.print(f"  [yellow]import errors: {p['import_errors']}[/yellow]")
        console.print(
            "[dim]counts are factual; no entry is claimed healthy without a "
            "recorded successful health check[/dim]"
        )

    emit(counts, as_json, render)


@catalog_app.command("validate")
def catalog_validate(
    as_json: bool = typer.Option(False, "--json", help="Machine-readable output."),
) -> None:
    """Lint the catalogue: schema, duplicates, missing links, stale claims."""
    from tracefield.registry import Catalog

    path = _default_catalog_path()
    if not path.exists():
        fail(f"catalogue data not found at {path}", EXIT_NOT_FOUND)
    cat = Catalog(path)
    problems = cat.validate()

    def render(p: dict[str, Any]) -> None:
        if not p["problems"]:
            console.print(f"[green]catalogue OK[/green] — {p['total']} records valid")
            return
        for problem in p["problems"]:
            console.print(f"[red]problem:[/red] {s(problem, 200)}")
        console.print(f"{len(p['problems'])} problem(s) in {p['total']} records")

    emit({"problems": problems, "total": len(cat.entries)}, as_json, render)
    if problems:
        raise SystemExit(EXIT_ERROR)


@catalog_app.command("sync")
def catalog_sync(
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be imported without writing.",
    ),
) -> None:
    """Import curated upstream lists into the local catalogue (attribution preserved)."""
    from tracefield.registry.importers import run_importers

    path = _default_catalog_path()
    result = run_importers(path, dry_run=dry_run)
    if dry_run:
        console.print(
            f"[yellow]dry-run[/yellow]: would add {result['added']} new records "
            f"({result['total_after']} total), skip {result['skipped']}"
        )
    else:
        console.print(
            f"[green]synced[/green]: added {result['added']} new records "
            f"({result['total_after']} total), skipped {result['skipped']}"
        )
        for note in result.get("notes", []):
            console.print(f"  [dim]{s(note, 160)}[/dim]")


# ---------------------------------------------------------------------------
# username
# ---------------------------------------------------------------------------


@username_app.command("check")
def username_check(
    username: str = typer.Argument(..., help="Single username to check."),
    providers: str = typer.Option(
        "",
        "--providers",
        help="Comma-separated names, or 'curated' (default).",
    ),
    as_json: bool = typer.Option(False, "--json", help="Machine-readable output."),
) -> None:
    """Check ONE username against curated public-profile providers (opt-in)."""
    settings = load_settings()
    if not settings.username_check_enabled:
        fail(
            "username checks are disabled by default; set "
            "TRACEFIELD_USERNAME_CHECK=1 to enable (conservative, curated "
            "providers only, no bulk mode)",
            EXIT_NETWORK_BLOCKED,
        )
    from tracefield.fieldtools.username import (
        CURATED_PROVIDERS,
        ProviderRule,
        check_username,
        validate_username,
    )

    try:
        validate_username(username)
    except ValueError as exc:
        fail(str(exc), EXIT_USAGE)

    if providers and providers != "curated":
        wanted = {p.strip() for p in providers.split(",") if p.strip()}
        rules: list[ProviderRule] = [p for p in CURATED_PROVIDERS if p.name in wanted]
        missing = wanted - {p.name for p in rules}
        if missing:
            fail(
                f"unknown provider(s): {', '.join(sorted(missing))}; "
                f"curated set: {', '.join(p.name for p in CURATED_PROVIDERS)}",
                EXIT_USAGE,
            )
    else:
        rules = list(CURATED_PROVIDERS)

    result = check_username(username, rules)

    def render(p: dict[str, Any]) -> None:
        console.print(f"username: [bold]{s(p['username'])}[/bold]")
        table = Table(title="provider results")
        table.add_column("provider")
        table.add_column("state")
        table.add_column("http")
        table.add_column("evidence")
        for r in p["results"]:
            state_color = {
                "CONFIRMED_PUBLIC_PROFILE": "green",
                "LIKELY_MATCH": "yellow",
                "NOT_FOUND_VERIFIED": "dim",
                "BLOCKED": "yellow",
                "RATE_LIMITED": "yellow",
                "PROVIDER_ERROR": "red",
                "INCONCLUSIVE": "yellow",
                "NOT_CHECKED": "dim",
            }.get(r["state"], "white")
            table.add_row(
                r["provider"],
                f"[{state_color}]{r['state']}[/{state_color}]",
                str(r["http_status"] or "-"),
                s("; ".join(r["evidence"])[:60]),
            )
        console.print(table)
        for caveat in p["caveats"]:
            console.print(f"[dim]{s(caveat, 180)}[/dim]")

    emit(result, as_json, render)


# ---------------------------------------------------------------------------
# hash / inspect / ocr
# ---------------------------------------------------------------------------


@app.command()
def hash(
    path: Path = typer.Argument(..., exists=True, readable=True, file_okay=True),
    algorithm: str = typer.Option("sha256", "--algorithm", "-a"),
    as_json: bool = typer.Option(False, "--json", help="Machine-readable output."),
) -> None:
    """Compute a content hash without modifying the file."""
    from tracefield.fieldtools.inspect import hash_command_impl

    hash_command_impl(path, algorithm, as_json, console)


@app.command()
def inspect(
    path: Path = typer.Argument(..., exists=True, readable=True, file_okay=True),
    deep: bool = typer.Option(
        False,
        "--deep",
        help="Use optional backends (exiftool/ffprobe).",
    ),
    as_json: bool = typer.Option(False, "--json", help="Machine-readable output."),
) -> None:
    """Inspect a local file: signature, hashes, timestamps, metadata."""
    from tracefield.fieldtools.inspect import inspect_command_impl

    inspect_command_impl(path, deep=deep, as_json=as_json, console=console)


@app.command()
def ocr(
    path: Path = typer.Argument(..., exists=True, readable=True, file_okay=True),
    as_json: bool = typer.Option(False, "--json", help="Machine-readable output."),
) -> None:
    """Extract text via local Tesseract OCR (if installed). Machine-derived."""
    from tracefield.fieldtools.ocr import ocr_command_impl

    ocr_command_impl(path, as_json=as_json, console=console)


# ---------------------------------------------------------------------------
# report / export
# ---------------------------------------------------------------------------


@app.command()
def report(
    case: str = typer.Argument(..., help="Case ID or title."),
    fmt: str = typer.Option("markdown", "--format", "-f", help="markdown|json"),
    output: Path = typer.Option(None, "--output", "-o", help="Write to file."),
) -> None:
    """Build a human-reviewable report with caveats and provenance."""
    from tracefield.reporting.build import build_report

    settings = load_settings()
    db = open_db(settings)
    try:
        case_obj = resolve_case(CaseRepo(db), case)
        if fmt not in ("markdown", "json"):
            fail(f"unsupported format {fmt!r} (use markdown or json)", EXIT_USAGE)
        text = build_report(settings, db, case_obj, fmt=fmt)
        if output:
            output.write_text(text, encoding="utf-8")
            console.print(f"wrote {s(str(output), 400)}")
        else:
            # Report content embeds source-derived text: render literally and
            # never word-wrap (wrapping would corrupt piped markdown).
            console.print(text, markup=False, highlight=False, soft_wrap=True)
    finally:
        db.close()


@app.command("case-export")
def case_export(
    case: str = typer.Argument(..., help="Case ID or title."),
    output: Path = typer.Option(..., "--output", "-o", help="Export directory."),
    redact: bool = typer.Option(
        True,
        "--redact/--no-redact",
        help="Redact secrets from text artifacts; emit GPS advisory.",
    ),
) -> None:
    """Export a case bundle with an integrity manifest (built after redaction)."""
    settings = load_settings()
    db = open_db(settings)
    try:
        case_obj = resolve_case(CaseRepo(db), case)
        ws = CaseWorkspace(settings.cases_root, db)
        from tracefield.reporting.export import export_case

        export_case(settings, db, ws, case_obj, output, redact=redact)
        console.print(f"[green]exported[/green] case {case_obj.id} → {s(str(output), 400)}")
        console.print(
            "[dim]note: deleting the active database does not erase this export "
            "or any other copies you have made[/dim]"
        )
    finally:
        db.close()


@app.command("case-verify")
def case_verify(
    export_dir: Path = typer.Argument(..., exists=True, file_okay=False),
    as_json: bool = typer.Option(False, "--json", help="Machine-readable output."),
) -> None:
    """Verify an exported case bundle against its integrity manifest."""
    from tracefield.reporting.export import verify_manifest

    ok, problems = verify_manifest(export_dir)
    payload = {"ok": ok, "problems": problems}

    def render(p: dict[str, Any]) -> None:
        if p["ok"]:
            console.print("[green]manifest verified[/green] — all digests match")
        else:
            for problem in p["problems"]:
                console.print(f"[red]problem:[/red] {s(problem)}")

    emit(payload, as_json, render)
    if not ok:
        raise SystemExit(EXIT_ERROR)


@app.command("case-delete")
def case_delete(
    case: str = typer.Argument(..., help="Case ID or title."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Confirm deletion."),
) -> None:
    """Delete a case, its records, and its stored binary evidence."""
    settings = load_settings()
    db = open_db(settings)
    try:
        case_obj = resolve_case(CaseRepo(db), case)
        if not yes:
            fail(
                f"refusing to delete {case_obj.id} without --yes "
                "(this removes records and stored evidence binaries)",
                EXIT_USAGE,
            )
        import shutil as _shutil

        from tracefield.storage.workspace import validate_case_id

        validate_case_id(case_obj.id)  # refuse any traversal-shaped ID
        case_dir = (settings.cases_root / case_obj.id).resolve()
        # Defense in depth: resolved path must stay under cases_root.
        if not str(case_dir).startswith(str(settings.cases_root.resolve())):
            fail("refusing to delete a path outside the cases root", EXIT_USAGE)
        CaseRepo(db).delete(case_obj.id)
        if case_dir.exists():
            _shutil.rmtree(case_dir)
        console.print(f"[yellow]deleted[/yellow] case {case_obj.id} and its evidence directory")
        console.print(
            "[dim]note: this does not erase copies you previously exported or backed up[/dim]"
        )
    finally:
        db.close()


# ---------------------------------------------------------------------------
# TUI entry
# ---------------------------------------------------------------------------


@app.command()
def tui() -> None:
    """Launch the interactive TUI (optional; every feature also has a CLI path)."""
    from tracefield.tui.app import run_tui

    run_tui()


def run() -> None:
    """Console-script entry point with deterministic exit-code mapping.

    Usage errors exit 3 (not click's default 2, which would collide with
    EXIT_NOT_FOUND); help/version exit 0; aborts exit 130; unexpected
    exceptions are logged to the structured JSONL log and exit 1 with a
    sanitized one-line error (TRACEFIELD_DEBUG=1 prints the traceback).
    """
    import os as _os

    from tracefield.config.logging import get_logger, setup_logging

    setup_logging(load_settings().data_root)
    log = get_logger("cli")
    log.info(
        " ".join(sys.argv[:1] + sys.argv[1:]) or "tracefield",
        extra={"event": "command"},
    )
    try:
        app(standalone_mode=False)
    except typer.Exit as exc:  # includes help/version (exit 0) and our fails
        sys.exit(exc.exit_code)
    except typer.Abort:
        err_console.print("[yellow]aborted[/yellow]")
        sys.exit(130)
    except UsageError as exc:
        log.warning(exc.format_message(), extra={"event": "usage_error"})
        err_console.print(f"[red]usage error:[/red] {s(exc.format_message(), 300)}")
        err_console.print("[dim]run 'tracefield --help'[/dim]")
        sys.exit(EXIT_USAGE)
    except ClickException as exc:
        log.warning(exc.format_message(), extra={"event": "click_error"})
        err_console.print(f"[red]error:[/red] {s(exc.format_message(), 300)}")
        sys.exit(EXIT_ERROR)
    except SystemExit:
        raise  # explicit exit codes raised by command bodies
    except Exception as exc:  # CLI boundary catch-all
        log.exception(
            "unhandled error", extra={"event": "unhandled", "exc_type": type(exc).__name__}
        )
        err_console.print(f"[red]error:[/red] {s(str(exc), 300)}")
        if _os.environ.get("TRACEFIELD_DEBUG"):
            import traceback as _traceback

            _traceback.print_exc()
        else:
            err_console.print("[dim]set TRACEFIELD_DEBUG=1 for a traceback[/dim]")
        sys.exit(EXIT_ERROR)
    sys.exit(EXIT_OK)


if __name__ == "__main__":
    run()
