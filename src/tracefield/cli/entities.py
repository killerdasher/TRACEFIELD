"""Entity Core v1 CLI (Phase 22) — a dedicated sub-app module.

Lives outside ``cli/main.py`` so the 50-command monolith does not absorb a
new domain (architecture-report finding): ``main`` registers this module's
``entity_app`` and gains only two lines. Shared helpers are imported
lazily inside command bodies to avoid a module-level import cycle.

Honesty contract: every command states or implies that an entity is a
recorded analytical object, never proof of a real-world identity; mention
classes describe how a reference was obtained, never whether it is true;
match reviews record analyst decisions without merging anything.
"""

from __future__ import annotations

from typing import Any

import typer
from rich.table import Table

from tracefield.core.domain import ReviewState
from tracefield.core.entities import (
    ENTITY_TYPES,
    MENTION_CLASSES,
    Entity,
    EntityAlias,
    EntityMatchCandidate,
    EntityMention,
    normalize_alias,
)

entity_app = typer.Typer(
    help="Recorded analytical objects (person, organisation, account, ...).",
    no_args_is_help=True,
)

_EXIT_NOT_FOUND = 2
_EXIT_ERROR = 1
_EXIT_USAGE = 3


def _open_case(case_ref: str) -> tuple[Any, Any, Any, Any]:
    """Shared command preamble: settings, db, resolved case, workspace.

    Returns (settings, db, case_obj, ws). The caller owns ``db.close()``.
    """
    from tracefield.cli.main import open_db, resolve_case
    from tracefield.config import load_settings
    from tracefield.storage import CaseWorkspace
    from tracefield.storage.repositories import CaseRepo

    settings = load_settings()
    db = open_db(settings)
    try:
        case_obj = resolve_case(CaseRepo(db), case_ref)
        ws = CaseWorkspace(settings.cases_root, db)
    except Exception:
        db.close()
        raise
    return settings, db, case_obj, ws


@entity_app.command("add")
def entity_add(
    label: str = typer.Option(..., "--label", help="Canonical label as recorded (analyst-owned)."),
    case: str = typer.Option(..., "--case", help="Case ID or title."),
    kind: str = typer.Option(
        "other", "--type", help=f"Entity type: {', '.join(sorted(ENTITY_TYPES))}."
    ),
    notes: str = typer.Option("", "--notes", help="Analyst notes (optional)."),
    as_json: bool = typer.Option(False, "--json", help="Machine-readable output."),
) -> None:
    """Record a new entity. An entity is a recorded analytical object —
    never proof that a real-world identity has been established."""
    from tracefield.cli.main import console, emit, fail, open_db, resolve_case
    from tracefield.config import load_settings
    from tracefield.core.entities import EntityType
    from tracefield.storage import CaseWorkspace
    from tracefield.storage.repositories import CaseRepo, EntityRepo, RepositoryError

    if kind not in ENTITY_TYPES:
        fail(
            f"invalid entity type {kind!r}; use one of: {', '.join(sorted(ENTITY_TYPES))}",
            _EXIT_USAGE,
        )
    try:
        entity = Entity(
            case_id="pending",
            entity_type=EntityType(kind),
            canonical_label=label,
            notes=notes,
        )
    except ValueError as exc:
        fail(f"invalid entity: {exc}", _EXIT_USAGE)

    settings = load_settings()
    db = open_db(settings)
    try:
        case_obj = resolve_case(CaseRepo(db), case)
        entity = entity.model_copy(update={"case_id": case_obj.id})
        try:
            EntityRepo(db).add(entity)
        except RepositoryError as exc:
            fail(str(exc), _EXIT_ERROR)
        ws = CaseWorkspace(settings.cases_root, db)
        from tracefield.cli.main import _append_event

        _append_event(ws, case_obj.id, "entity.add", [entity.canonical_label], [entity.id])

        def render(e: dict[str, Any]) -> None:
            console.print(f"[green]added[/green] entity [bold]{e['id']}[/bold]")
            console.print(f"  type:   {e['entity_type']}")
            console.print(f"  label:  {_s(e['canonical_label'], 120)}")
            console.print(
                "  note:   recorded analytical object — not an established real-world identity"
            )

        emit(entity.model_dump(), as_json, render)
    finally:
        db.close()


@entity_app.command("alias")
def entity_alias(
    entity_id: str = typer.Option(..., "--entity", help="Entity ID."),
    alias: str = typer.Option(..., "--alias", help="Alternative label as recorded."),
    case: str = typer.Option(..., "--case", help="Case ID or title."),
    as_json: bool = typer.Option(False, "--json", help="Machine-readable output."),
) -> None:
    """Record an alternative label for an entity. Duplicates (same
    normalized alias on the same entity) are refused."""
    from tracefield.cli.main import console, emit, fail
    from tracefield.storage.repositories import (
        EntityAliasRepo,
        EntityRepo,
        RepositoryError,
    )

    _, db, case_obj, _ws = _open_case(case)
    try:
        owner = EntityRepo(db).get(entity_id)
        if owner is None or owner.case_id != case_obj.id:
            fail(f"entity not found in this case: {entity_id!r}", _EXIT_NOT_FOUND)
        normalized = normalize_alias(alias)
        if not normalized:
            fail("alias must not be empty", _EXIT_USAGE)
        if not owner.canonical_label or normalized == normalize_alias(owner.canonical_label):
            fail(
                "alias is identical to the canonical label (after normalization); "
                "use a genuinely different label",
                _EXIT_USAGE,
            )
        dup = EntityAliasRepo(db).find_duplicate(entity_id, normalized)
        if dup is not None:
            fail(
                f"alias already recorded for this entity: {dup.id!r} "
                f"(normalized {normalized!r}) — duplicates are refused",
                _EXIT_USAGE,
            )
        record = EntityAlias(
            case_id=case_obj.id, entity_id=entity_id, alias=alias, normalized=normalized
        )
        try:
            EntityAliasRepo(db).add(record)
        except RepositoryError as exc:
            fail(str(exc), _EXIT_ERROR)
        EntityRepo(db).touch(entity_id)
        from tracefield.cli.main import _append_event

        _append_event(_ws, case_obj.id, "entity.alias.add", [alias], [record.id])

        def render(a: dict[str, Any]) -> None:
            console.print(f"[green]added[/green] alias [bold]{a['id']}[/bold]")
            console.print(f"  alias:      {_s(a['alias'], 120)}")
            console.print(f"  normalized: {a['normalized']}")

        emit(record.model_dump(), as_json, render)
    finally:
        db.close()


@entity_app.command("mention")
def entity_mention(
    entity_id: str = typer.Option(..., "--entity", help="Entity ID."),
    record_id: str = typer.Option(
        ...,
        "--record",
        help="Record ID that mentions the entity (source/evidence/claim/observation/assertion).",
    ),
    case: str = typer.Option(..., "--case", help="Case ID or title."),
    mention_class: str = typer.Option(
        "stated",
        "--class",
        help=f"How the reference was obtained: {', '.join(sorted(MENTION_CLASSES))}.",
    ),
    note: str = typer.Option("", "--note", help="Analyst note (optional)."),
    as_json: bool = typer.Option(False, "--json", help="Machine-readable output."),
) -> None:
    """Link an existing case record to an entity as a traceable mention.

    A mention is evidence of a reference, not proof of identity. The
    record must already exist in this case — dangling or cross-case
    references are refused by the database itself.
    """
    from tracefield.cli.main import console, emit, fail
    from tracefield.core.entities import MentionClass
    from tracefield.storage.repositories import (
        EntityMentionRepo,
        EntityRepo,
        RepositoryError,
    )

    if mention_class not in MENTION_CLASSES:
        fail(
            f"invalid mention class {mention_class!r}; use one of: "
            f"{', '.join(sorted(MENTION_CLASSES))}",
            _EXIT_USAGE,
        )
    _, db, case_obj, ws = _open_case(case)
    try:
        owner = EntityRepo(db).get(entity_id)
        if owner is None or owner.case_id != case_obj.id:
            fail(f"entity not found in this case: {entity_id!r}", _EXIT_NOT_FOUND)
        record = EntityMention(
            case_id=case_obj.id,
            entity_id=entity_id,
            record_id=record_id,
            mention_class=MentionClass(mention_class),
            note=note,
        )
        try:
            EntityMentionRepo(db).add(record)
        except RepositoryError as exc:
            fail(
                f"{exc} — the record id must be an existing source/evidence/claim/"
                "observation/assertion in this case",
                _EXIT_USAGE,
            )
        from tracefield.cli.main import _append_event

        _append_event(ws, case_obj.id, "entity.mention.add", [entity_id, record_id], [record.id])

        def render(m: dict[str, Any]) -> None:
            console.print(f"[green]added[/green] mention [bold]{m['id']}[/bold]")
            console.print(f"  entity: {m['entity_id']}")
            console.print(f"  record: {m['record_id']}")
            console.print(f"  class:  {m['mention_class']} (how the reference was obtained)")

        emit(record.model_dump(), as_json, render)
    finally:
        db.close()


@entity_app.command("list")
def entity_list(
    case: str = typer.Option(..., "--case", help="Case ID or title."),
    kind: str = typer.Option("", "--type", help="Filter by entity type."),
    as_json: bool = typer.Option(False, "--json", help="Machine-readable output."),
) -> None:
    """List entities for a case with their mention counts."""
    from tracefield.cli.main import console, emit
    from tracefield.storage.repositories import (
        EntityMentionRepo,
        EntityRepo,
    )

    if kind and kind not in ENTITY_TYPES:
        from tracefield.cli.main import fail

        fail(
            f"invalid entity type {kind!r}; use one of: {', '.join(sorted(ENTITY_TYPES))}",
            _EXIT_USAGE,
        )
    _settings, db, case_obj, _ws = _open_case(case)
    try:
        entities = EntityRepo(db).list_for_case(case_obj.id)
        if kind:
            entities = [e for e in entities if e.entity_type.value == kind]
        payload = []
        for e in entities:
            d = e.model_dump()
            d["mention_count"] = len(EntityMentionRepo(db).list_for_entity(e.id))
            payload.append(d)

        def render(items: list[dict[str, Any]]) -> None:
            if not items:
                console.print("no entities")
                return
            table = Table(title=f"entities — {_s(case_obj.title)}")
            table.add_column("id")
            table.add_column("type")
            table.add_column("label")
            table.add_column("mentions")
            for e in items:
                table.add_row(
                    e["id"],
                    e["entity_type"],
                    _s(e["canonical_label"], 50),
                    str(e["mention_count"]),
                )
            console.print(table)

        emit(payload, as_json, render)
    finally:
        db.close()


@entity_app.command("show")
def entity_show(
    entity_id: str = typer.Argument(..., help="Entity ID."),
    case: str = typer.Option(..., "--case", help="Case ID or title."),
    as_json: bool = typer.Option(False, "--json", help="Machine-readable output."),
) -> None:
    """Show one entity with aliases and mentions (full provenance)."""
    from tracefield.cli.main import console, emit, fail
    from tracefield.storage.repositories import (
        EntityAliasRepo,
        EntityMentionRepo,
        EntityRepo,
    )

    _settings, db, case_obj, _ws = _open_case(case)
    try:
        entity = EntityRepo(db).get(entity_id)
        if entity is None or entity.case_id != case_obj.id:
            fail(f"entity not found in this case: {entity_id!r}", _EXIT_NOT_FOUND)
        payload = {
            **entity.model_dump(),
            "aliases": [a.model_dump() for a in EntityAliasRepo(db).list_for_entity(entity.id)],
            "mentions": [m.model_dump() for m in EntityMentionRepo(db).list_for_entity(entity.id)],
        }

        def render(e: dict[str, Any]) -> None:
            console.print(f"[bold]{e['id']}[/bold]  ({e['entity_type']})")
            console.print(f"  label:  {_s(e['canonical_label'], 120)}")
            if e["notes"]:
                console.print(f"  notes:  {_s(e['notes'], 200)}")
            aliases = e["aliases"]
            console.print(f"  aliases: {len(aliases)}")
            for a in aliases:
                console.print(f"    - {_s(a['alias'], 80)} (normalized: {a['normalized']})")
            mentions = e["mentions"]
            console.print(f"  mentions: {len(mentions)}")
            for m in mentions:
                console.print(
                    f"    - {_s(m['record_id'], 60)} [{m['mention_class']}] ({_s(m['note'], 60)})"
                    if m["note"]
                    else f"    - {_s(m['record_id'], 60)} [{m['mention_class']}]"
                )
            console.print(
                "  entity: a recorded analytical object — not an established real-world identity"
            )

        emit(payload, as_json, render)
    finally:
        db.close()


@entity_app.command("matches")
def entity_matches(
    case: str = typer.Option(..., "--case", help="Case ID or title."),
    state: str = typer.Option("", "--state", help="Filter by review state."),
    as_json: bool = typer.Option(False, "--json", help="Machine-readable output."),
) -> None:
    """List pairwise identity-match candidates for a case."""
    from tracefield.cli.main import console, emit, fail
    from tracefield.storage.repositories import EntityMatchRepo

    if state and state not in {s.value for s in ReviewState}:
        fail(
            f"invalid review state {state!r}; use one of: "
            f"{', '.join(sorted(s.value for s in ReviewState))}",
            _EXIT_USAGE,
        )
    _settings, db, case_obj, _ws = _open_case(case)
    try:
        matches = EntityMatchRepo(db).list_for_case(case_obj.id)
        if state:
            matches = [m for m in matches if m.review_state.value == state]
        payload = [m.model_dump() for m in matches]

        def render(items: list[dict[str, Any]]) -> None:
            if not items:
                console.print("no match candidates")
                return
            table = Table(title=f"match candidates — {_s(case_obj.title)}")
            table.add_column("id")
            table.add_column("a")
            table.add_column("b")
            table.add_column("review")
            for m in items:
                table.add_row(m["id"], m["entity_a_id"], m["entity_b_id"], m["review_state"])
            console.print(table)
            console.print(
                "  review decides whether two recorded entities denote the same "
                "subject; nothing is merged and no record is deleted"
            )

        emit(payload, as_json, render)
    finally:
        db.close()


@entity_app.command("match")
def entity_match(
    entity_a: str = typer.Option(..., "--a", help="First entity ID."),
    entity_b: str = typer.Option(..., "--b", help="Second entity ID."),
    case: str = typer.Option(..., "--case", help="Case ID or title."),
    rationale: str = typer.Option("", "--rationale", help="Why this pair is suspected (optional)."),
    as_json: bool = typer.Option(False, "--json", help="Machine-readable output."),
) -> None:
    """File a pairwise identity-match candidate between two entities.

    Filing a candidate asserts nothing: it is a question for analyst
    review, decided with 'entity review'. The same unordered pair cannot
    be filed twice.
    """
    from tracefield.cli.main import console, emit, fail
    from tracefield.storage.repositories import (
        EntityMatchRepo,
        EntityRepo,
        RepositoryError,
    )

    _, db, case_obj, ws = _open_case(case)
    try:
        repo = EntityRepo(db)
        for eid in (entity_a, entity_b):
            e = repo.get(eid)
            if e is None or e.case_id != case_obj.id:
                fail(f"entity not found in this case: {eid!r}", _EXIT_NOT_FOUND)
        if entity_a == entity_b:
            fail("match endpoints must differ (--a == --b)", _EXIT_USAGE)
        existing = EntityMatchRepo(db).find_unordered_pair(case_obj.id, entity_a, entity_b)
        if existing is not None:
            fail(
                f"a candidate for this unordered pair already exists: {existing.id!r} "
                f"(review state: {existing.review_state.value})",
                _EXIT_USAGE,
            )
        match = EntityMatchCandidate(
            case_id=case_obj.id,
            entity_a_id=entity_a,
            entity_b_id=entity_b,
            rationale=rationale,
        )
        try:
            match = EntityMatchRepo(db).add(match)
        except RepositoryError as exc:
            fail(str(exc), _EXIT_ERROR)
        from tracefield.cli.main import _append_event

        _append_event(ws, case_obj.id, "entity.match.add", [entity_a, entity_b], [match.id])

        def render(m: dict[str, Any]) -> None:
            console.print(f"[green]filed[/green] match candidate [bold]{m['id']}[/bold]")
            console.print(f"  a: {m['entity_a_id']}")
            console.print(f"  b: {m['entity_b_id']}")
            console.print(f"  review: {m['review_state']} (decide with: entity review)")

        emit(match.model_dump(), as_json, render)
    finally:
        db.close()


@entity_app.command("review")
def entity_review(
    match_id: str = typer.Option(..., "--match", help="Match candidate ID."),
    case: str = typer.Option(..., "--case", help="Case ID or title."),
    state: str = typer.Option(..., "--state", help="Decision: confirmed | rejected | unresolved."),
    note: str = typer.Option("", "--note", help="Analyst note on the decision."),
    as_json: bool = typer.Option(False, "--json", help="Machine-readable output."),
) -> None:
    """Record an analyst decision on a match candidate.

    Confirmed and rejected both mean the question was DECIDED; unresolved
    keeps it open. Rejected candidates are retained for audit. Nothing is
    merged, deleted, or re-scored — the entities stay separate records.
    """
    from tracefield.cli.main import console, emit, fail
    from tracefield.storage.repositories import EntityMatchRepo

    allowed = {ReviewState.CONFIRMED, ReviewState.REJECTED, ReviewState.UNRESOLVED}
    try:
        decision = ReviewState(state)
    except ValueError:
        fail(
            f"invalid decision {state!r}; use one of: "
            f"{', '.join(sorted(s.value for s in allowed))}",
            _EXIT_USAGE,
        )
    if decision not in allowed:
        fail(
            f"{state!r} is not a review decision; use one of: "
            f"{', '.join(sorted(s.value for s in allowed))}",
            _EXIT_USAGE,
        )
    _settings, db, case_obj, ws = _open_case(case)
    try:
        match = EntityMatchRepo(db).get(match_id)
        if match is None or match.case_id != case_obj.id:
            fail(f"match candidate not found in this case: {match_id!r}", _EXIT_NOT_FOUND)
        updated = EntityMatchRepo(db).review(match_id, decision, note)
        if updated is None:  # pragma: no cover — get() just returned the row
            fail(f"match candidate not found in this case: {match_id!r}", _EXIT_NOT_FOUND)
        from tracefield.cli.main import _append_event

        _append_event(ws, case_obj.id, "entity.match.review", [match_id], [decision.value])

        def render(m: dict[str, Any]) -> None:
            console.print(f"[green]reviewed[/green] match candidate [bold]{m['id']}[/bold]")
            console.print(f"  decision: {m['review_state']}")
            console.print(f"  note:     {_s(m['review_note'], 120) or '(none)'}")
            console.print("  entities remain separate records; nothing was merged or deleted")

        emit(updated.model_dump(), as_json, render)
    finally:
        db.close()


def _s(text: str, max_length: int = 200) -> str:
    """Terminal-safe truncation; delegates to main's helper at call time."""
    from tracefield.cli.main import s

    return s(text, max_length)
