"""Sherlock ``--csv`` row parser (stdlib ``csv`` only — R-SEC-1).

Field semantics are pinned by ``docs/ingest/SHERLOCK_CSV_SCHEMA.md`` and the
version-pinned fixture ``tests/fixtures/ingest/``. The parser stores values
verbatim: it never renames, reformats, rounds, or "improves" a field — the
raw row is the evidence; interpretation happens downstream, never here.
"""

from __future__ import annotations

import csv
from pathlib import Path

from pydantic import BaseModel

from tracefield.ingest.errors import RowShapeRefusal, ZeroRowsRefusal
from tracefield.ingest.registry import SUPPORTED_FORMATS

# Parser hygiene bounds (R-SEC-1): a hostile "CSV" cannot make us allocate
# unbounded structures or recurse. Row count and field sizes are bounded
# BEFORE any row is turned into a record.
MAX_ROWS = 50_000
MAX_FIELD_CHARS = 4096

SHERLOCK_CSV_HEADER = SUPPORTED_FORMATS["sherlock_csv"].header


class SherlockRow(BaseModel):
    """One fixture row, verbatim. Every field stays a string."""

    row_no: int  # 1-based record number in the file (header is record 1)
    username: str
    name: str
    url_main: str
    url_user: str
    exists: str
    http_status: str
    response_time_s: str


class ParsedSherlockCsv(BaseModel):
    extra_columns: tuple[str, ...] = ()
    rows: list[SherlockRow]


def parse_sherlock_csv(path: str | Path) -> ParsedSherlockCsv:
    path = Path(path)
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = reader.fieldnames
        if fieldnames is None or len(fieldnames) < len(SHERLOCK_CSV_HEADER):
            raise RowShapeRefusal(
                f"declared header {tuple(fieldnames or ())} does not carry the "
                f"required columns {SHERLOCK_CSV_HEADER}"
            )
        known = list(SHERLOCK_CSV_HEADER)
        head = fieldnames[: len(known)]
        if tuple(head) != SHERLOCK_CSV_HEADER:
            missing = [c for c in known if c not in fieldnames]
            if missing:
                raise RowShapeRefusal(
                    f"required column(s) {missing} absent from header "
                    f"{tuple(fieldnames)}; partial mapping is not permitted"
                )
            raise RowShapeRefusal(
                f"required columns present but not in canonical order "
                f"({SHERLOCK_CSV_HEADER}); header {tuple(fieldnames)} is not "
                "mapped in any other order — refusing the whole file"
            )
        extra_columns = tuple(fieldnames[len(known) :])

        rows: list[SherlockRow] = []
        record_no = 1
        for raw in reader:
            record_no += 1
            if record_no > MAX_ROWS + 1:
                raise RowShapeRefusal(
                    f"row count exceeds the ingest bound ({MAX_ROWS} rows); refusing the whole file"
                )
            for col, value in raw.items():
                if value is not None and len(value) > MAX_FIELD_CHARS:
                    raise RowShapeRefusal(
                        f"row {record_no} field {col!r} exceeds "
                        f"{MAX_FIELD_CHARS} chars — refusing the whole file"
                    )
            extras = raw.get(None)  # csv restkey: values beyond the header
            if extras:
                raise RowShapeRefusal(
                    f"row {record_no} has {len(extras)} value(s) beyond the "
                    f"header's {len(fieldnames)} columns; surplus values are "
                    "unmappable and must never be silently dropped — "
                    "refusing the whole file"
                )
            if None in raw.values():
                missing = [c for c in fieldnames if raw.get(c) is None]
                raise RowShapeRefusal(
                    f"row {record_no} is missing fields {tuple(missing)} "
                    "(fewer values than the header declares); refusing "
                    "the whole file"
                )
            rows.append(
                SherlockRow(
                    row_no=record_no,
                    username=_f(raw, "username", record_no),
                    name=_f(raw, "name", record_no),
                    url_main=_f(raw, "url_main", record_no),
                    url_user=_f(raw, "url_user", record_no),
                    exists=_f(raw, "exists", record_no),
                    http_status=_f(raw, "http_status", record_no),
                    response_time_s=_f(raw, "response_time_s", record_no),
                )
            )

    if not rows:
        raise ZeroRowsRefusal("file parsed to zero data rows (header only) — nothing to import")
    return ParsedSherlockCsv(extra_columns=extra_columns, rows=rows)


def _f(raw: dict[str, str | None], col: str, record_no: int) -> str:
    value = raw.get(col)
    if value is None:
        raise RowShapeRefusal(f"row {record_no} is missing column {col!r}")
    return value
