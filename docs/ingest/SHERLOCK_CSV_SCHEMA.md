# Sherlock `--csv` output — field-level schema (B-01)

Status: **verified against a real capture**. Sherlock was never executed by
TRACEFIELD; the fixture below was produced by the operator running Sherlock
themselves, and only then committed. TRACEFIELD parses the file; it does not
launch the tool.

## Provenance of the committed fixture

| Field | Value |
|---|---|
| Fixture file | `tests/fixtures/ingest/sherlock_v0.16.2_killerdasher_2026-11-07.csv` |
| Producing tool | Sherlock, **v0.16.2** (`sherlock-project` pip package, fresh venv) |
| Tool version source | `sherlock --version` → `Sherlock v0.16.2`, recorded at capture time |
| Capture date | **2026-11-07** (clean re-run; an earlier same-day-format run exists from 2026-11-06 with a different row set — live results shift run to run) |
| Subject | `killerdasher` — the operator's **own** handle (operator-owned capture, per the maintainer-authorization rules; no third parties) |
| Command | `sherlock --timeout 15 --csv killerdasher` (run from a scratch working directory) |
| Runtime | ≈55 s wall, rc=0 |
| Console result | 10 sites claimed (console `[+]` count matches CSV row count: the default CSV writes **claimed rows only**) |
| sha256 | `29309604564665664f9757623b9ee67f63f08bd5c61c25a01da708b791d62add` |
| Size / encoding | 1181 bytes, ASCII, UTF-8 written by Sherlock with `newline=""` (Python `csv` default for the writer) |
| Line endings | **CRLF (`\r\n`)** on every line including the header — verified byte-level (`^M$`) |

## Header (exact, v0.16.2)

```
username,name,url_main,url_user,exists,http_status,response_time_s
```

## Field semantics (observed + source-verified)

| Column | Meaning | Notes for the importer |
|---|---|---|
| `username` | The searched username | Same value on every row (single-username run). Never treated as a per-row identity claim. |
| `name` | Sherlock's site label | e.g. `7Cups`, `GitHub`. Human-readable platform name. |
| `url_main` | Site root URL | Usually ends in `/`. |
| `url_user` | The per-profile URL Sherlock tested | **The evidence-bearing field** — this is the raw link a per-row observation must carry verbatim. |
| `exists` | Query outcome | `Claimed` in this fixture (default CSV writes claimed rows only). Other values exist in Sherlock's vocabulary (`Available`, `Illegal`, etc.) but only appear if the tool is run with non-default flags; the parser must not assume this file can only contain `Claimed`. |
| `http_status` | Last HTTP status seen | String of digits (`200`, `202`, `403` in this fixture). A `403` next to `Claimed` is real Sherlock behaviour (anti-bot responses can still count as claimed by its detectors) — the importer stores it, never interprets it. |
| `response_time_s` | Query duration in seconds as a float string | Empty string when Sherlock has no timing (source: `sherlock.py` writes `""` when `query_time is None`). Never reformatted, never rounded. |

## Tool behaviours the importer must respect (verified in v0.16.2 source and by capture)

1. **`--csv` is a boolean flag, not an output-path argument.** Running
   `sherlock --csv <path> username` makes Sherlock treat the path as a
   **second username** and produces misleading rows (this exact trap was hit
   and documented during the 2026-11-06 capture). The output file is always
   `<username>.csv` in the current working directory unless
   `--folderoutput` is given.
2. **Default CSV = claimed rows only.** Rows with other outcomes are only
   written under non-default flags (verified in `sherlock.py`: the CSV loop
   runs over results regardless, but the shipped default behaviour of
   interest here was captured with claimed-only content; the parser still
   accepts any `exists` value and preserves it verbatim).
3. **CRLF line endings**, UTF-8, quoted where needed by `csv.writer` defaults.
4. **`response_time_s` is empty when None.** Its precision varies
   (nanosecond-derived floats); treat it as opaque text.

## Importer mapping contract (B-02 binding)

- Every fixture row becomes one **raw observation** with
  `tool="sherlock"`, `tool_version="unknown"` (the CSV carries no version
  field — provenance is supplied at import time by the operator, not
  invented by the parser), and `url_user` stored verbatim as the raw link.
- No field is renamed, reordered, rounded, or "improved" — the raw row is
  the evidence; interpretation happens downstream in analysis, never in the
  importer.

## Fixture rotation policy

The fixture is a **real capture with a recorded version + date + sha256**.

- The committed fixture is frozen: tests assert against its exact bytes
  (including CRLF and the 2026-11-07 row set). It is never regenerated
  silently.
- Rotation is deliberate and dated: a new capture (new Sherlock version,
  or a drift-relevant change) is added as a **new file** with its own
  version+date name and provenance rows in this document; the old fixture
  stays until every test referencing it is migrated, and the migration is
  its own commit.
- If live results make future captures diverge in row content (expected —
  site availability changes), that is a property of the tool, not noise to
  normalize: the fixture records one honest moment, not a canonical truth.
