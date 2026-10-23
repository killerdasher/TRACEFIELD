"""Case-scoped workspace: directory layout + immutable evidence storage.

Evidence files are content-addressed (``evidence/<sha[:2]>/<sha>``),
written once, and chmod'd read-only. Originals are never modified in
place; any derived/normalized artifact must be a separate file.
"""

from __future__ import annotations

import contextlib
import re
import shutil
from pathlib import Path

from tracefield.core.domain import AnalysisEvent, EvidenceItem, utcnow
from tracefield.core.provenance import compute_event_digest, hash_bytes, hash_file
from tracefield.storage.database import Database
from tracefield.storage.repositories import (
    CaseRepo,
    EventRepo,
    EvidenceRepo,
    SourceRepo,
)

# Strict case-ID shape: rejects path traversal via crafted IDs.
_CASE_ID_RE = re.compile(r"^case_[0-9a-f]{16}$")
_CHUNK = 1024 * 1024


class WorkspaceError(ValueError):
    """Invalid workspace operation (e.g. path traversal attempt)."""


def validate_case_id(case_id: str) -> str:
    if not _CASE_ID_RE.match(case_id):
        raise WorkspaceError(f"invalid case id {case_id!r}: must match case_<16 hex chars>")
    return case_id


class CaseWorkspace:
    """Case-scoped directory + database handle."""

    def __init__(self, root: str | Path, db: Database) -> None:
        self.root = Path(root)
        self.db = db
        self.cases = CaseRepo(db)
        self.sources = SourceRepo(db)
        self.evidence = EvidenceRepo(db)
        self.events = EventRepo(db)

    def case_dir(self, case_id: str) -> Path:
        validate_case_id(case_id)
        d = self.root / case_id
        d.mkdir(parents=True, exist_ok=True)
        with contextlib.suppress(OSError):
            d.chmod(0o700)
        return d

    def evidence_path(self, case_id: str, sha256: str) -> Path:
        validate_case_id(case_id)
        if not re.fullmatch(r"[0-9a-f]{64}", sha256):
            raise WorkspaceError("invalid sha256")
        d = self.case_dir(case_id) / "evidence" / sha256[:2]
        d.mkdir(parents=True, exist_ok=True)
        return d / sha256

    def attach_file(
        self,
        case_id: str,
        source_id: str,
        path: str | Path,
        *,
        media_type: str = "application/octet-stream",
        excerpt: str = "",
        privacy_label: str = "unknown",
    ) -> EvidenceItem:
        """Stream-copy ``path`` into the case store immutably.

        Uses a streaming copy (never ``read_bytes``) so large exhibits do
        not exhaust memory.
        """
        src = Path(path)
        if not src.is_file():
            raise WorkspaceError(f"not a regular file: {src}")
        # Defense in depth: source must belong to this case.
        source = self.sources.get(source_id)
        if source is None or source.case_id != case_id:
            raise WorkspaceError(
                "source does not belong to this case (cross-case provenance is not permitted)"
            )
        digest = hash_file(src)
        dest = self.evidence_path(case_id, digest)
        if not dest.exists():
            tmp = dest.with_suffix(".partial")
            with src.open("rb") as fin, tmp.open("wb") as fout:
                shutil.copyfileobj(fin, fout, length=_CHUNK)
            tmp.chmod(0o600)
            tmp.replace(dest)
            dest.chmod(0o400)  # read-only: originals immutable by default
        ev = EvidenceItem(
            case_id=case_id,
            source_id=source_id,
            sha256=digest,
            media_type=media_type,
            storage_ref=str(dest.relative_to(self.case_dir(case_id))),
            size_bytes=src.stat().st_size,
            captured_at=utcnow(),
            excerpt=excerpt,
            privacy_label=privacy_label,  # type: ignore[arg-type]
        )
        self.evidence.add(ev)
        self._append_event(case_id, "evidence.attach", [str(src)], [ev.id])
        return ev

    def attach_bytes(
        self,
        case_id: str,
        source_id: str,
        data: bytes,
        *,
        media_type: str = "application/octet-stream",
        excerpt: str = "",
        privacy_label: str = "unknown",
    ) -> EvidenceItem:
        source = self.sources.get(source_id)
        if source is None or source.case_id != case_id:
            raise WorkspaceError("source does not belong to this case")
        digest = hash_bytes(data)
        dest = self.evidence_path(case_id, digest)
        if not dest.exists():
            dest.write_bytes(data)
            dest.chmod(0o400)
        ev = EvidenceItem(
            case_id=case_id,
            source_id=source_id,
            sha256=digest,
            media_type=media_type,
            storage_ref=str(dest.relative_to(self.case_dir(case_id))),
            size_bytes=len(data),
            captured_at=utcnow(),
            excerpt=excerpt,
            privacy_label=privacy_label,  # type: ignore[arg-type]
        )
        self.evidence.add(ev)
        self._append_event(case_id, "evidence.attach_bytes", [], [ev.id])
        return ev

    def verify_evidence(self, case_id: str, ev: EvidenceItem) -> bool:
        validate_case_id(case_id)
        path = self.case_dir(case_id) / ev.storage_ref
        if not path.exists():
            return False
        return hash_file(path) == ev.sha256

    def store_raw_observation(
        self, case_id: str, obs_id: str, data: bytes, *, suffix: str = ".txt"
    ) -> str:
        """Store a tool's raw (uninterpreted) return for an observation.

        Private to the case (0o600), never executed, never parsed here —
        the observation row references this file via ``raw_ref``. Returns
        the case-relative reference.
        """
        validate_case_id(case_id)
        if not re.fullmatch(r"obs_[0-9a-f]{16}", obs_id):
            raise WorkspaceError("invalid observation id")
        if suffix not in {".txt", ".json", ".log"}:
            raise WorkspaceError("unsupported raw suffix")
        d = self.case_dir(case_id) / "observations"
        d.mkdir(parents=True, exist_ok=True)
        dest = d / f"{obs_id}{suffix}"
        tmp = dest.with_suffix(suffix + ".partial")
        tmp.write_bytes(data)
        tmp.chmod(0o600)
        tmp.replace(dest)
        return str(dest.relative_to(self.case_dir(case_id)))

    def _append_event(
        self, case_id: str, action: str, inputs: list[str], outputs: list[str]
    ) -> None:
        from tracefield import __version__

        prev = self.events.last_digest(case_id)
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
        self.events.append(ev)
