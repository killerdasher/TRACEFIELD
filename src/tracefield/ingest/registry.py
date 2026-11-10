"""Format registry: which file identities this build can map (R-SEC-3).

A file's *identity* is what the file itself declares — for Sherlock that is
the exact CSV header shape (the CSV carries no version field, so the
declared version is absent and imports record ``unknown`` per R-SEC-4).
Versioned formats declare their version in the file; this registry refuses
*declared-but-unsupported* major versions fail-closed, while an absent
version is never a refusal case.
"""

from __future__ import annotations

from pydantic import BaseModel

from tracefield.ingest.errors import (
    RowShapeRefusal,
    UnmappableFormatRefusal,
    UnsupportedMajorVersionRefusal,
)

_SHERLOCK_CSV_HEADER = (
    "username",
    "name",
    "url_main",
    "url_user",
    "exists",
    "http_status",
    "response_time_s",
)


class FormatIdentity(BaseModel):
    """What a file declares about itself (never guessed beyond structure)."""

    format_name: str
    #: empty string when the file declares no version (absent → "unknown")
    declared_version: str = ""


class FormatSpec(BaseModel):
    """A registered ingest format and the majors this build maps."""

    format_name: str
    header: tuple[str, ...]
    major_versions: tuple[int, ...]
    producer: str
    description: str


SUPPORTED_FORMATS: dict[str, FormatSpec] = {
    "sherlock_csv": FormatSpec(
        format_name="sherlock_csv",
        header=_SHERLOCK_CSV_HEADER,
        # Single major observed in the wild through v0.16.2. Later majors
        # are opt-in: adding one requires a NEW real fixture + schema doc
        # (B-01 rotation policy), never a silent parser change.
        major_versions=(1,),
        producer="sherlock",
        description="Sherlock --csv output (claimed-row default; CRLF; "
        "no version field — declared version absent)",
    ),
}


def _read_header_line(path: str, max_bytes: int = 8192) -> str:
    """First line only, bounded — never slurps the whole file to sniff."""
    with open(path, encoding="utf-8", newline="") as fh:
        line = fh.readline(max_bytes)
    if not line:
        raise UnmappableFormatRefusal(f"file is empty: {path}")
    return line.rstrip("\r\n")


def detect_format(path: str) -> FormatIdentity:
    """Identify a file by its declared header shape. Fail-closed.

    Raises UnmappableFormatRefusal naming what was observed when no known
    format matches. Never sniffs content beyond the header line.
    """
    import csv
    import io

    line = _read_header_line(path)
    try:
        fields = next(csv.reader(io.StringIO(line)))
    except csv.Error as exc:
        raise UnmappableFormatRefusal(f"header is not parseable CSV: {exc}") from exc

    for spec in SUPPORTED_FORMATS.values():
        # Exact match, or the known header present as a prefix subset with
        # ADDITIVE extra columns (recorded as an import flag downstream —
        # never silently dropped per R-SEC-3 amendment).
        if tuple(fields[: len(spec.header)]) == spec.header:
            return FormatIdentity(format_name=spec.format_name)

    raise UnmappableFormatRefusal(
        f"no ingest format matches header {tuple(fields)}; known formats: "
        f"{sorted(SUPPORTED_FORMATS)}"
    )


def require_supported_version(identity: FormatIdentity) -> None:
    """Refuse declared-but-unsupported major versions (R-SEC-3).

    An ABSENT declared version is not a refusal case: it imports as
    ``unknown`` (R-SEC-4).
    """
    spec = SUPPORTED_FORMATS.get(identity.format_name)
    if spec is None:
        raise UnmappableFormatRefusal(f"unregistered format {identity.format_name!r}")
    if not identity.declared_version:
        return
    major_text = identity.declared_version.split(".", 1)[0]
    if not major_text.isdigit():
        raise RowShapeRefusal(
            f"declared version {identity.declared_version!r} is not a plain "
            "major.minor version string"
        )
    if int(major_text) not in spec.major_versions:
        raise UnsupportedMajorVersionRefusal(
            f"format {identity.format_name!r} declares version "
            f"{identity.declared_version}; this build maps majors "
            f"{list(spec.major_versions)} only (refusing the whole file — "
            "partial import is not permitted)"
        )
