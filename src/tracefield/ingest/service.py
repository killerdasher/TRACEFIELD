"""Ingest service: file → (Source, Evidence, Observations, event) — offline.

Hard rules implemented here (contract: `TRACEFIELD_02_PRODUCT_DIRECTION.md`
R-SEC-1..8):

* Size cap enforced BEFORE parse (R-SEC-2).
* Format identity must be recognized, else refuse the WHOLE file (R-SEC-3).
* Declared-but-unsupported major versions refuse; absent versions import as
  ``unknown`` (R-SEC-3/4).
* Raw-first: the exact file bytes are copied content-addressed (0o400) via
  the standard evidence path; observations point INTO that copy
  (``<storage_ref>#row=<n>``) instead of duplicating raw values (R-SEC-5).
* Zero egress: import performs no fetch and no subprocess (R-SEC-6); URLs
  in rows stay in the copy until an analyst promotes one.
* Everything is case-scoped; foreign-case records refuse (R-SEC-7).
* Review actions (promote/dismiss/defer) are hash-chained events; dismiss
  without a reason is refused; a dismissed record cannot be promoted
  (R-SEC-8).
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from pydantic import BaseModel

from tracefield import __version__
from tracefield.config.settings import Settings
from tracefield.core.domain import (
    AccessMethod,
    AnalysisEvent,
    Case,
    EvidenceItem,
    Observation,
    Source,
    SourceType,
    utcnow,
)
from tracefield.core.provenance import compute_event_digest
from tracefield.ingest.errors import (
    CrossCaseRefusal,
    EvidenceIntegrityRefusal,
    IngestRefusal,
    MissingReasonRefusal,
    OversizedFileRefusal,
    RowShapeRefusal,
)
from tracefield.ingest.registry import (
    SUPPORTED_FORMATS,
    detect_format,
    require_supported_version,
)
from tracefield.ingest.sherlock_csv import SherlockRow, parse_sherlock_csv
from tracefield.storage.database import Database
from tracefield.storage.repositories import ObservationRepo, SourceRepo
from tracefield.storage.workspace import CaseWorkspace

#: review actions, in audit order
REVIEW_ACTIONS = ("candidate.promote", "candidate.dismiss", "candidate.defer")


class ImportResult(BaseModel):
    case_id: str
    format_name: str
    source_id: str
    evidence_id: str
    evidence_sha256: str
    storage_ref: str
    observation_ids: list[str]
    extra_columns: list[str]
    declared_version: str  # "" → recorded as "unknown" on observations
    event_id: str
    row_count: int


class ProvenanceString(BaseModel):
    """The provenance a promoted Source row records (B-03/B-04 contract)."""

    tool: str
    tool_version: str
    file_sha256: str
    row_no: int
    exists: str
    http_status: str


def run_import(
    settings: Settings,
    db: Database,
    case: Case,
    path: str | Path,
    *,
    source_id: str = "",
    privacy_label: str = "unknown",
) -> ImportResult:
    """Import one operator-supplied tool-output file into ``case``.

    Fail-closed: every refusal below happens before ANY database write, so a
    refused file leaves zero partial rows.
    """
    path = Path(path)
    # R-SEC-2 — size cap BEFORE parse.
    size = path.stat().st_size
    if size > settings.max_fetch_bytes:
        raise OversizedFileRefusal(
            f"file is {size} bytes; ingest cap is {settings.max_fetch_bytes} "
            f"bytes (Settings.max_fetch_bytes). Refusing before parse."
        )

    # R-SEC-3 — recognize the identity; fail closed on the unknown.
    identity = detect_format(str(path))
    require_supported_version(identity)
    spec = SUPPORTED_FORMATS[identity.format_name]
    if identity.format_name != "sherlock_csv":  # pragma: no cover — single format today
        raise IngestRefusal(f"no mapping registered for {identity.format_name!r}")
    parsed = parse_sherlock_csv(path)

    # Resolve the source the import hangs from (R-SEC-7: case-scoped).
    sources = SourceRepo(db)
    if source_id:
        src = sources.get(source_id)
        if src is None:
            raise IngestRefusal(f"source not found: {source_id!r}")
        if src.case_id != case.id:
            raise CrossCaseRefusal(
                f"source {source_id!r} belongs to case {src.case_id!r}, not "
                f"{case.id!r} — cross-case import is not permitted"
            )
    else:
        src = sources.add(
            Source(
                case_id=case.id,
                locator=str(path.resolve()),
                publisher=spec.producer,
                source_type=SourceType.LOCAL_FILE,
                access_method=AccessMethod.IMPORTED,
            )
        )

    # Raw-first: exact bytes, content-addressed, immutable (streamed copy).
    ws = CaseWorkspace(settings.cases_root, db)
    ev = ws.attach_file(
        case.id,
        src.id,
        path,
        media_type="text/csv",
        excerpt="",  # R-SEC-5: raw content is never copied into excerpts
        privacy_label=privacy_label,
    )

    observations = ObservationRepo(db)
    tool_version = identity.declared_version or "unknown"
    flag = f" extra_columns={','.join(parsed.extra_columns)}" if parsed.extra_columns else ""
    obs_ids: list[str] = []
    for row in parsed.rows:
        obs = observations.add(
            Observation(
                case_id=case.id,
                evidence_id=ev.id,
                tool_name=spec.producer,
                tool_version=tool_version,
                raw_ref=f"{ev.storage_ref}#row={row.row_no}",
                summary=(
                    f"{row.name}: exists={row.exists} http_status={row.http_status}"
                    f"{flag}"
                ),
            )
        )
        obs_ids.append(obs.id)

    event = _append_event(
        db,
        case.id,
        "ingest.file",
        inputs=[str(path.resolve()), ev.sha256],
        outputs=[ev.id, *obs_ids],
    )

    return ImportResult(
        case_id=case.id,
        format_name=identity.format_name,
        source_id=src.id,
        evidence_id=ev.id,
        evidence_sha256=ev.sha256,
        storage_ref=ev.storage_ref,
        observation_ids=obs_ids,
        extra_columns=list(parsed.extra_columns),
        declared_version=identity.declared_version,
        event_id=event.id,
        row_count=len(parsed.rows),
    )


def get_observation(db: Database, obs_id: str) -> Observation | None:
    r = db.execute("SELECT * FROM observations WHERE id=?", (obs_id,)).fetchone()
    if r is None:
        return None
    return Observation(
        id=r["id"],
        case_id=r["case_id"],
        evidence_id=r["evidence_id"],
        tool_name=r["tool_name"],
        tool_version=r["tool_version"],
        raw_ref=r["raw_ref"],
        returned_at=r["returned_at"],
        summary=r["summary"],
    )


def _review_events(db: Database, case_id: str, obs_id: str) -> list[AnalysisEvent]:
    rows = db.execute(
        "SELECT * FROM analysis_events WHERE case_id=? AND action IN "
        "('candidate.promote','candidate.dismiss','candidate.defer') "
        "ORDER BY rowid",
        (case_id,),
    ).fetchall()
    out: list[AnalysisEvent] = []
    for r in rows:
        inputs = json.loads(r["inputs"])
        if obs_id in inputs:
            out.append(
                AnalysisEvent(
                    id=r["id"],
                    case_id=r["case_id"],
                    action=r["action"],
                    inputs=inputs,
                    outputs=json.loads(r["outputs"]),
                    tool_fingerprint=r["tool_fingerprint"],
                    prev_digest=r["prev_digest"],
                    digest=r["digest"],
                    occurred_at=r["occurred_at"],
                )
            )
    return out


def review_history(db: Database, case_id: str, obs_id: str) -> list[AnalysisEvent]:
    return _review_events(db, case_id, obs_id)


def promote_observation(
    settings: Settings,
    db: Database,
    case: Case,
    obs_id: str,
) -> tuple[Source, AnalysisEvent, ProvenanceString]:
    """Analyst-triggered promotion of ONE observation to a Source row.

    No network: the Source is a recorded claim about a URL, promotion never
    fetches it (R-SEC-6/8).
    """
    obs = get_observation(db, obs_id)
    if obs is None:
        raise IngestRefusal(f"observation not found: {obs_id!r}")
    if obs.case_id != case.id:
        raise CrossCaseRefusal(
            f"observation {obs_id!r} belongs to case {obs.case_id!r}, not "
            f"{case.id!r} — cross-case promotion is not permitted"
        )
    history = _review_events(db, case.id, obs_id)
    for ev in history:
        if ev.action == "candidate.promote":
            raise IngestRefusal(
                f"observation {obs_id!r} was already promoted (event {ev.id})"
            )
        if ev.action == "candidate.dismiss":
            raise IngestRefusal(
                f"observation {obs_id!r} was dismissed by reason: "
                f"{ev.inputs[1] if len(ev.inputs) > 1 else '(unrecorded)'} — "
                "promoting a dismissed record requires a fresh analyst "
                "decision recorded as a new dismiss/review event"
            )

    ws = CaseWorkspace(settings.cases_root, db)
    ev_item = ws.evidence.get(obs.evidence_id)
    if ev_item is None or ev_item.case_id != case.id:
        raise CrossCaseRefusal(f"observation's evidence is missing or foreign: {obs.evidence_id!r}")
    row = _read_row_from_evidence(ws, case.id, ev_item, obs.raw_ref)

    provenance = ProvenanceString(
        tool=obs.tool_name,
        tool_version=obs.tool_version,
        file_sha256=ev_item.sha256,
        row_no=row.row_no,
        exists=row.exists,
        http_status=row.http_status,
    )
    sources = SourceRepo(db)
    src = sources.add(
        Source(
            case_id=case.id,
            locator=row.url_user,
            publisher=row.name,
            source_type=SourceType.WEB_PAGE,
            access_method=AccessMethod.MANUAL,
            limitations=(
                f"candidate from {provenance.tool} {provenance.tool_version} "
                f"output sha256={provenance.file_sha256[:12]} row={row.row_no}: "
                f"exists={row.exists} http_status={row.http_status}; recorded, "
                "never verified by TRACEFIELD"
            ),
        )
    )
    event = _append_event(
        db,
        case.id,
        "candidate.promote",
        inputs=[obs_id, row.url_user],
        outputs=[src.id],
    )
    return src, event, provenance


def dismiss_observation(
    db: Database,
    case: Case,
    obs_id: str,
    reason: str,
) -> AnalysisEvent:
    """Record a reasoned dismissal (R-SEC-8: no reason → refusal)."""
    obs = get_observation(db, obs_id)
    if obs is None:
        raise IngestRefusal(f"observation not found: {obs_id!r}")
    if obs.case_id != case.id:
        raise CrossCaseRefusal(
            f"observation {obs_id!r} belongs to case {obs.case_id!r} — "
            "cross-case dismissal is not permitted"
        )
    if not reason.strip():
        raise MissingReasonRefusal(
            "dismiss requires a --reason; a bare dismissal is an unrecorded "
            "judgment and is refused"
        )
    return _append_event(
        db,
        case.id,
        "candidate.dismiss",
        inputs=[obs_id, reason],
        outputs=[obs_id],
    )


def defer_observation(
    db: Database,
    case: Case,
    obs_id: str,
    reason: str = "",
) -> AnalysisEvent:
    obs = get_observation(db, obs_id)
    if obs is None:
        raise IngestRefusal(f"observation not found: {obs_id!r}")
    if obs.case_id != case.id:
        raise CrossCaseRefusal(
            f"observation {obs_id!r} belongs to case {obs.case_id!r} — "
            "cross-case deferral is not permitted"
        )
    return _append_event(
        db,
        case.id,
        "candidate.defer",
        inputs=[obs_id, reason] if reason else [obs_id],
        outputs=[obs_id],
    )


def _read_row_from_evidence(
    ws: CaseWorkspace, case_id: str, ev: EvidenceItem, raw_ref: str
) -> SherlockRow:
    """Re-read exactly one row from the immutable copy (promote path).

    The copy is sha-verified first: promoting from unverified bytes is
    refused, never deprecated silently.
    """
    if not raw_ref.startswith(ev.storage_ref + "#row="):
        raise RowShapeRefusal(f"raw_ref {raw_ref!r} does not point into {ev.storage_ref!r}")
    if not ws.verify_evidence(case_id, ev):
        raise EvidenceIntegrityRefusal(
            f"stored copy {ev.storage_ref!r} no longer matches its recorded "
            f"sha256 — refusing promotion (integrity failure, not a usage error)"
        )
    row_no = int(raw_ref.rsplit("=", 1)[1])
    path = ws.case_dir(case_id) / ev.storage_ref
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for current, raw in enumerate(reader, start=1):
            if current == row_no:
                return SherlockRow(
                    row_no=row_no,
                    username=raw.get("username") or "",
                    name=raw.get("name") or "",
                    url_main=raw.get("url_main") or "",
                    url_user=raw.get("url_user") or "",
                    exists=raw.get("exists") or "",
                    http_status=raw.get("http_status") or "",
                    response_time_s=raw.get("response_time_s") or "",
                )
        raise RowShapeRefusal(
            f"row {row_no} absent from stored copy (file has {current} records)"
        )


def _append_event(
    db: Database, case_id: str, action: str, inputs: list[str], outputs: list[str]
) -> AnalysisEvent:
    """Same hash-chain discipline as CaseWorkspace._append_event (shared with
    repositories.EventRepo state, so ingest events sit on the case's chain)."""
    from tracefield.storage.repositories import EventRepo

    events = EventRepo(db)
    prev = events.last_digest(case_id)
    occurred = utcnow()
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
    events.append(ev)
    return ev
