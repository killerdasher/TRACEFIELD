"""Typed ingest refusals (R-SEC-3: fail closed, never partially import).

Every refusal names what was unmappable or unmet; the CLI maps all of them
to exit code 3 (usage/refusal). Nothing in this package raises a bare
``Exception`` for a data-shaped problem — a refusal is a typed, documented
outcome, not a crash.
"""

from __future__ import annotations


class IngestRefusal(Exception):
    """Base class: the file/call cannot be imported; nothing was written."""

    #: stable machine-readable reason token for --json output
    reason = "refused"


class OversizedFileRefusal(IngestRefusal):
    """File exceeds the size cap (R-SEC-2); checked BEFORE any parse."""

    reason = "oversized"


class UnmappableFormatRefusal(IngestRefusal):
    """No known ingest format matches this file's declared structure."""

    reason = "unmappable_format"


class UnsupportedMajorVersionRefusal(IngestRefusal):
    """The file declares a format/tool major version this build cannot map."""

    reason = "unsupported_major_version"


class CrossCaseRefusal(IngestRefusal):
    """The would-be import touches a record that belongs to another case."""

    reason = "cross_case"


class ZeroRowsRefusal(IngestRefusal):
    """The file parsed to zero data rows — nothing to import."""

    reason = "zero_rows"


class RowShapeRefusal(IngestRefusal):
    """A named row/field violates the parser hygiene bounds (R-SEC-1)."""

    reason = "row_shape"


class MissingReasonRefusal(IngestRefusal):
    """A review action (dismiss) without a recorded reason (R-SEC-8)."""

    reason = "missing_reason"


class ReviewTargetNotFound(IngestRefusal):
    """The observation a review action targets does not exist in this case.

    Maps to exit 2 (NOT_FOUND), not 3: a unreachable target is a lookup
    miss, not a policy refusal.
    """

    reason = "not_found"


class EvidenceIntegrityRefusal(IngestRefusal):
    """The content-addressed copy no longer matches its recorded sha256."""

    reason = "evidence_integrity"
