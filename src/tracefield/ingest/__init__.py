"""Offline ingest of operator-supplied tool outputs (the 0.2 ingest slice).

Public surface: :func:`run_import`, review actions, the typed refusal
classes, and the format registry. Everything here is offline by
construction — importing a file performs no fetch and no subprocess.
"""

from __future__ import annotations

from tracefield.ingest.errors import (
    CrossCaseRefusal,
    EvidenceIntegrityRefusal,
    IngestRefusal,
    MissingReasonRefusal,
    OversizedFileRefusal,
    RowShapeRefusal,
    UnmappableFormatRefusal,
    UnsupportedMajorVersionRefusal,
    ZeroRowsRefusal,
)
from tracefield.ingest.registry import (
    SUPPORTED_FORMATS,
    FormatIdentity,
    FormatSpec,
    detect_format,
    require_supported_version,
)
from tracefield.ingest.service import (
    ImportResult,
    ProvenanceString,
    defer_observation,
    dismiss_observation,
    get_observation,
    promote_observation,
    review_history,
    run_import,
)

__all__ = [
    "REVIEW_ACTIONS",
    "SUPPORTED_FORMATS",
    "CrossCaseRefusal",
    "EvidenceIntegrityRefusal",
    "FormatIdentity",
    "FormatSpec",
    "ImportResult",
    "IngestRefusal",
    "MissingReasonRefusal",
    "OversizedFileRefusal",
    "ProvenanceString",
    "RowShapeRefusal",
    "UnmappableFormatRefusal",
    "UnsupportedMajorVersionRefusal",
    "ZeroRowsRefusal",
    "defer_observation",
    "detect_format",
    "dismiss_observation",
    "get_observation",
    "promote_observation",
    "require_supported_version",
    "review_history",
    "run_import",
]
