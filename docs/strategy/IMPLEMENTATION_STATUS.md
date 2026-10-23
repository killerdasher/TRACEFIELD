# TRACEFIELD — Implementation Status

> Honest status snapshot, **2026-10-19 (post-build audit)**, for v0.1.0 at
> commit `e964409` (4 commits on `main`). Every number below was measured on
> this machine (`pytest`, `ruff check`, `mypy src`, `tracefield catalog
> validate`, wheel install test). Nothing in this document is aspirational;
> planned work is listed as planned. Full findings: `POST_BUILD_AUDIT.md`.

## Verification gates (state at 2026-10-19 audit)

| Gate | Result |
|---|---|
| `pytest -m "not network"` | **207 passed** (85 unit, 98 integration, 23 security, 1 e2e) |
| `ruff check src tests` | **clean** |
| `ruff format --check src tests` | **clean** (49 files) |
| `mypy src` (strict) | **clean**, 34 files |
| `tracefield catalog validate` | **catalogue OK — 2264 records valid** |
| `pip-audit --strict` (requirements minus editable self-line) | **clean** |
| **Fresh-venv wheel install** | **FAIL** — `data/` not packaged; `tools status` exits 2 with "catalogue data not found" (audit G7; debt #5 promoted to P0) |
| CI workflow | `.github/workflows/ci.yml`: ruff, mypy, pytest × {3.11, 3.12, 3.13}, catalogue validate, `pip-audit --strict`; green on `e964409` (not re-run this phase — no pushes) |

Test counts were measured on 2026-10-19 (marker breakdown via
`pytest -m <marker>`); every test file carries a strict marker.

Network-marked tests never run in CI (marker exists, zero tests currently use
it — live-network behaviour is exercised manually and via fixtures).

> **Update (2026-10-23, Phases 6–7).** The rows above are the 2026-10-19
> audit snapshot. Since then: `pytest` is **292 passed**, `mypy` covers **38
> files**, and the one FAIL row — **fresh-venv wheel install (audit G7)** — is
> **FIXED**: `data/catalog` ships inside the wheel and resolves
> package-relative, so `tools status/search/show` + `catalog validate` all
> exit 0 in a clean venv (`PHASE_07_REPORT_TESTING.md`). TUI truthfulness
> fixed in `PHASE_06_REPORT_TUI.md`. Nothing above was rewritten — it records
> what was true at audit time.

## Codebase size (measured)

| Area | Files | Lines |
|---|---|---|
| `src/tracefield/` | 34 | 6,591 |
| `cli/main.py` | 1 | 1,682 |
| `tui/app.py` | 1 | 291 |
| `tests/` | 15 (incl. conftest) | ~2,509 |
| `data/catalog/tools.jsonl` | 1 (2,264 records) | — |
| Strategy docs | 5 (+ 4 review streams) | — |
| Community/CI docs | CONTRIBUTING, SECURITY, CODE_OF_CONDUCT, CHANGELOG, CI workflow, 4 issue templates + PR template | — |
| OOVS mapping | `docs/oovs/OOVS_MAPPING.md` | — |
| Synthetic demo | `docs/demo/run_synthetic_demo.sh` + recorded session `DEMO_SESSION.txt` (captured 2026-10-19 UTC, header reads 2026-10-20 because the machine clock is +03:00 — timezone artifact, not a date claim) | — |
| Post-build audit | `docs/strategy/POST_BUILD_AUDIT.md` + `TUI_INTERACTION_SPEC.md` (2026-10-19) | — |

Git state: **4 commits on `main`** (`fd6eec4` initial build, `86a67cc` path
scrub + GitHub hardening, `cabcfa8` dependency/report fixes, `e964409` HTML
report), tracking `origin/main`, working tree clean. GitHub repo public with
secret scanning, push protection, Dependabot, CodeQL; CI green on `e964409`.

## Catalogue (tiered counts, from `tracefield tools status`)

```
catalogue records: 2264
  by integration state:  indexed 2254, verified 10
  by entry type:         website 1904, cli_tool 256, api_service 64,
                         reference 19, dataset 13, library 8
  by license (top):      UNKNOWN 2257, GPL-3.0 4, MIT 3
```

Counts are factual; no entry is claimed healthy without a recorded successful
health check. `verified` is deliberately small — each verification is a real
licence/identity check, not a checkbox.

## Implemented (P0 complete)

**Case & evidence core** — case lifecycle (`case create/list/show`,
`case-delete --yes`); content-addressed immutable evidence (SHA-256, `0o400`,
streamed copy); hash-chained `analysis_events`; `evidence verify`;
`case-verify` (manifest re-hash); `case-export` (redact-then-manifest).

**Analytic engine** — sources, claims, observations, assertions, relations
(`add`/`list`/`review`); origin clustering (origin-r3 containment, k=3/4/5,
`related_text` advisory edges); contradiction candidates (dates, digests,
quantities — severity always `candidate`); `analyze claim` decision table
(pinned by tests, see DECISIONS D4); `report` (JSON/Markdown) with caveats,
rule versions, `generated_at`.

**Field tools** — `hash`, `inspect [--deep]` (exiftool/ffprobe backends with
honest UNAVAILABLE states), `ocr` (tesseract wrapper), `fetch --fetch`
(doubly-opt-in, IP-pinned, SSRF-guarded), `username check` (curated providers,
soft-404 markers, 1 req/s, no HTTP-200-as-match).

**Registry** — inert catalogue (JSONL, project-authored descriptions,
attribution), `tools search/show/status`, `catalog validate/sync`.

**Security** — SSRF deny-list + connection pinning; terminal-injection
sanitization + rich-markup escape at every render site; redaction (`_kv`
patterns, `&`-safe, JSON-aware); at-rest `0700` dirs / `0600` DB; strict
case-ID validation; cross-case provenance trigger.

**Structured logging** — JSONL audit log at `<data_root>/logs/tracefield.jsonl`
(`0700` dir, `0600` file); every CLI invocation logs a `command` event with
redacted argv, failures log `fail` with the exit code, and a top-level
catch-all logs `unhandled` instead of dumping a raw traceback (opt-in detail
via `TRACEFIELD_DEBUG=1`); field caps + ANSI sanitization so logs stay
machine-parseable and terminal-safe; provenance of exit codes preserved.

**CLI/TUI** — full command surface (see `tracefield --help`: doctor, init,
hash, inspect, ocr, report, case-export, case-verify, case-delete, tui, case,
source, claim, evidence, observation, relation, analyze, tools, catalog,
username); deterministic exit codes 0/1/2/3/4/5; `--json` on every data
command; Textual TUI with keyboard workflow (headless-tested) and DB cleanup
on shutdown.

## Known debt (documented, not blocking P0)

1. `catalog`/`providers` SQLite tables exist at schema v1 but are unwired
   (JSONL is the single representation) — must be wired or dropped before
   schema v2 (DECISIONS D7).
2. Relation endpoint validation is app-level only; no DB-level FK on
   `from_id`/`to_id` (RISK A1/R-A1-5).
3. Report lacks author identity and a corrections section (RISK C1/R-C1-2).
4. Event digest does not yet include `tool_fingerprint`
   (`occurred_at` **is** included — `core/provenance.py`; the earlier claim
   that it was missing was stale). Deferred to schema v2 to avoid breaking
   existing chains.
5. ~~**P0 (confirmed):** wheel packaging of `data/` is broken~~ — **RESOLVED
   (Phase 7).** The wheel target now force-includes `data/catalog` inside the
   package, and the catalogue resolves package-relative (repo fallback intact);
   fresh-venv `tools status/search/show` + `catalog validate` all exit 0
   (audit gate G7 closed; `PHASE_07_REPORT_TESTING.md`).
6. No health-check job for catalogue rows (`last_checked` schema-only).
7. No perceptual hashing for image duplicate analysis.
8. ~~TUI has no case selector; no async worker offload~~ — **RESOLVED (Phase
   6).** Active-case model + `c` case picker shipped; case-scoped views render
   one case only; cooperative `Ctrl+C` cancel with real-count milestones.
   Docstring/keymap mismatches and false data labelling remediated
   (`PHASE_06_REPORT_TUI.md`; audit T1–T10 closed).
9. Malformed User-Agent string in `fetch.py` (cosmetic; needs real contact
   URL before public release).
10. Redirect hops in `fetch.py` are policy-validated but not IP-pinned
    (validate-then-connect window on hop 2+; first hop is pinned) — audit F1.
11. `run_backend` docstring claims an allowlist that the code does not enforce
    (only `shutil.which`; call sites are all literal today) — audit F2.
12. `migrate()` silently accepts a newer-schema DB (empty upgrade range
    instead of refusing) — audit F3.
13. Fault-tolerance coverage gaps: SQLite busy/corrupt/full/write-permission,
    export interruption, cancellation semantics untested — audit §6.

## Explicit non-claims

- No certification, including OWASP OOVS, is claimed. `docs/oovs/OOVS_MAPPING.md`
  is a maintainer self-assessment against OOVS v0.1.0 with per-requirement
  statuses (7 scoped PASS, 1 FAIL on correction propagation, 2 NOT_ASSESSED);
  the official OOVS acceptance tests were not executed.
- No catalogue entry is described as installed, healthy, or integrated unless
  the tiered counts say so.
- Review streams in `docs/strategy/` were role-based analytical subagent
  perspectives, not interviews with real people; they must never be described
  as practicing analysts.
- No performance benchmarks are published; none have been run beyond a
  startup smoke timing recorded below.

## Startup timing (informal, this machine, 2026-10-16)

`tracefield --help` wall-clock: 275 ms median of 3 warm runs (262/275/279 ms,
2026-10-16, this machine; venv import of Typer + Rich dominates). Not a
published benchmark; recorded only so future regressions have a baseline.
