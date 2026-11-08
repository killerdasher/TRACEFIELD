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
    PreparedImport,
    ProvenanceString,
    defer_observation,
    dismiss_observation,
    finish_import_event,
    get_observation,
    prepare_import,
    promote_observation,
    review_history,
    run_import,
    write_rows_batch,
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
    "PreparedImport",
    "ProvenanceString",
    "RowShapeRefusal",
    "UnmappableFormatRefusal",
    "UnsupportedMajorVersionRefusal",
    "ZeroRowsRefusal",
    "defer_observation",
    "detect_format",
    "dismiss_observation",
    "finish_import_event",
    "get_observation",
    "prepare_import",
    "promote_observation",
    "require_supported_version",
    "review_history",
    "run_import",
    "write_rows_batch",
]
