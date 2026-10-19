"""Content hashing, integrity manifests, and hash-chained event digests.

Pure functions and data structures — no storage/network/TUI imports.
Case-directory management lives in :mod:`tracefield.storage.workspace`.

A SHA-256 proves byte-level integrity of the retained object, not
truthfulness, authorship, or authenticity of any claim within it.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from tracefield.core.domain import utcnow

HASH_ALGORITHM = "sha256"
_CHUNK = 1024 * 1024


def hash_file(path: str | Path) -> str:
    """SHA-256 of a file, streamed. Never modifies the original."""
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        while chunk := f.read(_CHUNK):
            h.update(chunk)
    return h.hexdigest()


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def compute_event_digest(
    action: str,
    inputs: list[str],
    outputs: list[str],
    prev_digest: str,
    occurred_at: str = "",
) -> str:
    """Digest over the full event content including its timestamp, so
    backdating an event breaks the chain."""
    payload = json.dumps(
        {
            "action": action,
            "inputs": inputs,
            "outputs": outputs,
            "prev": prev_digest,
            "occurred_at": occurred_at,
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class IntegrityManifest:
    """Export manifest: every file with its digest and size.

    Verifying a manifest re-hashes files and compares — it proves the
    exported bytes match at export time, nothing more.
    """

    def __init__(
        self,
        case_id: str,
        schema_version: int,
        files: list[dict[str, Any]],
        *,
        redaction_applied: bool = False,
    ) -> None:
        self.case_id = case_id
        self.schema_version = schema_version
        self.files = files
        self.redaction_applied = redaction_applied
        self.generated_at = utcnow()

    def to_json(self) -> str:
        return json.dumps(
            {
                "case_id": self.case_id,
                "schema_version": self.schema_version,
                "generated_at": self.generated_at,
                "redaction_applied": self.redaction_applied,
                "files": self.files,
                "caveat": (
                    "SHA-256 digests prove byte-level integrity of exported files "
                    "at manifest generation time. They do not prove truthfulness, "
                    "authorship, or authenticity of content. When redaction is "
                    "applied, digests cover the REDACTED export copies; the "
                    "originals remain in the active case store unchanged."
                ),
            },
            indent=2,
            sort_keys=True,
        )

    @staticmethod
    def build_from_dir(
        case_id: str,
        export_dir: Path,
        *,
        redaction_applied: bool = False,
    ) -> IntegrityManifest:
        """Build a manifest by hashing the final files inside ``export_dir``.

        This is called AFTER any redaction so digests always match the
        bytes that actually ship in the export.
        """
        from tracefield import SCHEMA_VERSION

        files: list[dict[str, Any]] = []
        ev_dir = export_dir / "evidence"
        if ev_dir.exists():
            for path in sorted(ev_dir.rglob("*")):
                if not path.is_file():
                    continue
                rel = path.relative_to(ev_dir).as_posix()
                files.append(
                    {
                        "storage_ref": rel,
                        "sha256": hash_file(path),
                        "size_bytes": path.stat().st_size,
                    }
                )
        return IntegrityManifest(
            case_id,
            SCHEMA_VERSION,
            files,
            redaction_applied=redaction_applied,
        )
