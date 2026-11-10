# Changelog

All notable changes to TRACEFIELD are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased] — 0.2.0 (ingest slice), 2026-11-07 → 2026-11-08

### Added

- **Offline ingest (B-02)**: `src/tracefield/ingest/` — typed format
  registry (`detect_format` + `require_supported_version`), stdlib-`csv`
  Sherlock parser, and the import service. Fail-closed pre-conditions
  (R-SEC-1..4): oversize refuses before parse; unrecognized headers refuse
  the whole file with the observed header named; declared-but-unsupported
  major versions refuse; absent versions import as `unknown`, never guessed;
  zero-row files refuse. Rows map verbatim to observations whose `raw_ref`
  points INTO the immutable content-addressed copy (`evidence/<2-char>/<sha>
  #row=<record>`); file bytes are copied via the existing streamed `0o400`
  path. Extra CSV columns are accepted but flagged in each observation's
  summary — never dropped (R-SEC-3 amendment).
- **`case-import` CLI (B-03)**: `case-import --file <path> --case <case>`
  (offline; zero egress), `case-import status --case` (last import event +
  live counts, `--json` parity), and review actions `source promote`,
  `source dismiss --reason`, `source defer` over the same observation spine
  with the exit-code contract (refusals → 3, not-found → 2).
- **Review-event discipline (R-SEC-8)**: promote/dismiss/defer are
  hash-chained analysis events; a blank `--reason` dismissal is refused; a
  dismissed observation cannot be re-promoted without a fresh recorded
  analyst decision; double promotion is refused. Promotion records full
  provenance (tool, version or `unknown`, file sha256, row record number,
  `exists`/`http_status`) on the new `Source` row and never fetches the URL.
- **Sherlock format gate (B-01)**: real version-pinned fixture
  `tests/fixtures/ingest/sherlock_v0.16.2_killerdasher_2026-11-07.csv`
  (operator-owned capture, sha256 recorded) + field-level schema doc
  (`docs/ingest/SHERLOCK_CSV_SCHEMA.md`) documenting the CRLF line endings,
  the claimed-row-only default, the empty-`response_time_s` case, the
  `--csv`-is-a-boolean trap, and a rotation policy (fixtures are frozen;
  rotation is a dated, test-migrated event).
- **TUI ingest triage (B-06)**: triage overlay on `t` (promote/dismiss with
  reason/defer over live observations), Mission last-import block with
  honest counts, and an in-TUI import op (`i`) built on the SAME ingest
  code path with committed-batch cancellation: cancelled imports are
  labelled `incomplete=cancelled rows_written=<N>` on the chain event
  (J7); cancelled-in-flight ops are recorded in Runs.

### Verified

- 0.2 ingest slice battery: 369 tests (332 prior + 27 ingest + 10 adversarial-
  review pins), ruff clean, mypy `--strict` clean — offline only; the
  zero-egress pin test asserts importing performs no fetch; echo-sanitation
  tests assert a secret-carrying row never leaves the immutable copy into
  summaries, excerpts, or terminal output.
- Ingest E2E (B-04): import → triage → relate → assess → report → export →
  manifest verify → tamper detection, mirroring the synthetic demo's
  honesty assertions.

### Fixed

Fresh-context adversarial review (2026-11-08) of the ingest slice; every
fix is pinned by a named regression test, never softened:

- **Surplus row values silently dropped** (R-SEC-3 breach): a data row with
  more values than the header declares is now REFUSED ("beyond the header…")
  — `csv.DictReader` stashes surplus values under its restkey, which the
  former `None`-value guard never caught.
- **Hard failure mid-import left commits eventless**: the chain event now
  closes with `incomplete=error rows_written=<N>` (D28's documented
  close-out, never actually emitted before) and the TUI import op always
  reaches a terminal state; a chain-closure test walks the resulting chain.
- **Invalid `--privacy-label`** exited 1 with a pydantic traceback and left
  a dangling Source row behind: now a typed refusal (exit 3) validated
  before any database write; the help text enumerates the four labels.
- **Review target lookup**: promote/dismiss/defer of a nonexistent
  observation is a NOT_FOUND (exit 2), no longer a stuttering
  "refused (refused)" (exit 3).
- **Dismissal refusal message promised a re-consider path that does not
  exist** (dishonesty found by review): message now states dismissal is
  terminal in this build (D29); the triage overlay displays the enforced
  state (dismissal wins over a later defer), not the last action.
- **Short-row refusals mislabeled** as "more fields": now honestly named
  ("missing fields …").
- **Source-row provenance truncated**: persisted `limitations` carries the
  full file sha256, `row_record=<n>` and the raw_ref (D30); blank-reason
  dismissal hint in the TUI is now reachable (blank submits are delivered,
  not silently dropped); duplicate re-imports name the earlier evidence
  instead of silently doubling counts (D30).
- **Baseline-reproducibility flake root-caused**: the assessment vector
  carries a wall-clock `computed_at` stamp; full-payload equality compared
  it and flaked when two `utcnow()` calls straddled a tick. This is the
  root cause of both the new `TestIngest` baseline flake AND the long-
  standing 1-in-19 e2e demo flake (B-05/D26): comparisons now exclude the
  stamp (and assert its presence), so D26's "watch" policy can retire the
  suspicion without hiding it — stamps are still asserted present.

## [Unreleased] — 0.1.0 (pre-first-commit)

Initial implementation. Shipped across the first build sessions,
2026-10-16 → 2026-10-19; there is no prior release.

### Added

- **Case & evidence core**: case lifecycle; content-addressed immutable
  evidence (SHA-256, streamed copy, `0o400`); hash-chained `analysis_events`;
  `evidence verify`; `case-verify` (export manifest re-hash); `case-export`
  (redact-then-manifest ordering).
- **Analytic engine**: sources, claims, observations, assertions, relations
  with analyst review; origin clustering (origin-r3 containment, ordered
  k=3/4/5 shingles, `related_text` advisory edges); contradiction candidates
  (dates, digests, quantities — always severity `candidate`); `analyze claim`
  decision table pinned by tests; `report` (Markdown/JSON/HTML) with caveats,
  rule versions, `generated_at`; HTML reports are self-contained, fully
  escaped, and load no external resources.
- **Field tools**: `hash`, `inspect [--deep]` (exiftool/ffprobe with honest
  UNAVAILABLE states), `ocr` (tesseract wrapper), `fetch --fetch`
  (doubly-opt-in, connection-pinned, SSRF-guarded), `username check`
  (curated providers, soft-404 markers, 1 req/s politeness, no
  HTTP-200-as-match).
- **Tool catalogue**: 2,264 inert records with attribution and licence-review
  state; `tools search/show/status` (tiered counts); `catalog validate/sync`.
- **CLI**: deterministic exit codes 0/1/2/3/4/5; `--json` on data commands;
  top-level exception mapping; catch-all handler that logs unhandled
  exceptions instead of dumping raw tracebacks (`TRACEFIELD_DEBUG=1` for
  detail); `doctor` (local-only).
- **Structured logging**: JSONL audit log at `<data_root>/logs/tracefield.jsonl`
  (`0700` dir, `0600` file); `command`/`fail`/`unhandled` events; argv and
  message secret-redaction, ANSI sanitization, field/line size caps that never
  truncate JSON mid-string.
- **TUI**: Textual shell with keyboard workflow, headless-tested via
  `run_test()`; every feature also has a CLI path.
- **Security**: SSRF deny-list + connection pinning; terminal-injection
  sanitization and rich-markup escape at every render site; secret redaction
  (`&`-safe, JSON-aware); at-rest `0700`/`0600` permissions; strict case-ID
  validation; cross-case provenance enforcement.
- **Quality**: 203 tests (81 unit, 98 integration, 23 security, 1 e2e —
  incl. a full §16 synthetic demo case exercising provenance, clustering,
  contradictions, assessment review, export and tamper detection);
  `mypy --strict` clean across 34 files; ruff lint + format gates; CI
  workflow (ruff, mypy, pytest × Python 3.11/3.12/3.13, catalogue validate,
  `pip-audit --strict`).
- **Docs**: README with honest feature matrix and non-guarantees; strategy
  docs (competitor matrix, research register, decision log, risk register,
  implementation status); CONTRIBUTING, SECURITY, CODE_OF_CONDUCT, CHANGELOG;
  GitHub issue templates (bug, feature, catalogue, adapter) + PR template;
  OOVS v0.1.0 self-assessment mapping (`docs/oovs/OOVS_MAPPING.md`); synthetic
  §16 demo script + recorded session (`docs/demo/`).

### Fixed

- **CI (Phase 10).** The GitHub Actions test jobs failed on
  `tests/tui/test_journeys.py::TestHonestyAndThemes::test_tui_help_documents_flags`
  because typer forces a terminal render whenever `GITHUB_ACTIONS` is set and
  rich inserted ANSI resets *inside* option tokens (`--theme` → `ESC` `-` `ESC`
  `-theme`), so the raw-substring assertion never matched on CI. Help text
  assertions now match the ANSI-stripped render, with a subprocess regression
  test reproducing the forced-terminal path. CI also installs exiftool so the
  one integrated adapter (`exiftool-meta`) runs its end-to-end test instead of
  silently skipping; tesseract/ffprobe stay absent (honest `spec-only`
  adapters). Added durable coverage: jump-palette behavior (`g`/Esc/typed
  jump) and two-case view isolation across Evidence/Claims/Runs + reload.

### Security

- SSRF guard uses an explicit deny list (multicast, loopback, link-local,
  reserved, private, `fec0::/10`) because Python's `ip.is_global` returns
  True for some multicast and site-local addresses; fetches pin the
  connection to pre-validated IPs with Host/SNI preserved.
- Export manifests are built **after** redaction over the final bytes, so
  redacted exports verify.
- Redaction patterns rewritten to stop corrupting adjacent values
  (`password: hunter2` → `password: [REDACTED]`, not `[REDACTED]word`).

### Added (Phase 11, 2026-10-27)

- **Data schema v2** (additive-only migration from v1; no data changes):
  report-identity register (`case_reports` with revision/supersedes chain),
  correction register (`report_corrections`), dissemination register
  (`dissemination`), and DB-level referential integrity triggers — relation
  endpoints must exist **in the same case** (INSERT and UPDATE), and
  `evidence_ids` must be valid JSON listing same-case evidence; assertions
  get the same claim/evidence guards. New writes only; pre-v2 rows are not
  retro-validated (documented in the migration).
- **Report identity & dissemination (OOVS-09 mechanism)**: every rendered
  report can carry a durable `report_id` + revision; revisions supersede
  explicitly; corrections are appended (never silently rewritten) and travel
  forward with the lineage into the next render; `report-correct` and
  `report-history` operate the register; report schema v3 (additive).
  `case-export` renders `report.json` + `report.md` from ONE registered
  identity and `--recipient` records the shipment in the register with
  recipient-notification duty in the export README.
- **Scope authorization ledger (OOVS-01)**: `case authorize --scope
  --authorized-by [--revoke]` records collection-authority decisions as
  hash-chained analysis events; `case scope` reads the ledger;
  `source add --fetch` fails (exit 4, actionable hint) unless the latest
  decision is an active grant — the network env opt-in alone is no longer
  collection authority; a host absent from the recorded scope text draws a
  soft advisory.
- **Assertion creation path**: `assertion add/list/review` (previously
  assertions could not be created from any command surface); same-case
  claim/evidence validation CLI-side, DB-triggered backstop.
- **`catalog stale [--max-age-days N]`**: read-only freshness listing of
  overdue/unparseable `last_checked` dates (explicitly NOT a health verdict;
  decided FS-20 — verification is operator-manual, no automated job).

### Fixed (Phase 11, 2026-10-27)

- `username.py` User-Agent lacked a contact route; it now carries the
  project's own repo contact route, matching `fetch.py`
  (`tracefield/0.1 (+https://github.com/killerdasher/TRACEFIELD)`).

### Added (Phase 12, 2026-10-29)

- **Operator config file** (FS-17): `~/.config/tracefield/config.toml`
  (stdlib `tomllib`, no new dependency) with a documented accepted-key
  allowlist (`report_author`); `TRACEFIELD_REPORT_AUTHOR` env var wins;
  config parse errors / unknown keys / wrong value types ignore the whole
  file and surface in `doctor` — fail-closed, never half-applied.
- **Report author identity (FS-17)**: reports carry the operating analyst's
  identity when configured; other installs keep the honest
  `author not set` fallback (no tool-level default by decision D23). The
  maintainer's environment carries the confirmed author string.
- **OOVS-09 re-verdict**: held `FAIL` since 2026-10-19; now `PASS (scoped)`
  with the mechanism (report identity/corrections/recipient register) plus
  the configured author, per the mapping's promotion policy. Notification
  of corrections to prior recipients remains an explicitly operator-
  executed workflow, stated in the scope limits.
