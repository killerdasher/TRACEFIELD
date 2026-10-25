# Changelog

All notable changes to TRACEFIELD are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/).

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
