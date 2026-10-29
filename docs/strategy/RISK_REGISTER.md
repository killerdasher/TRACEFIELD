# TRACEFIELD — Risk Register

> Consolidated from the 20-role review (Teams A–D); status refreshed after the
> **2026-10-19 post-build audit** (`POST_BUILD_AUDIT.md`). Status values:
> **Fixed** (code + test), **Mitigated** (partial mitigation shipped, residual
> risk documented), **Accepted** (consciously carried with a rationale),
> **Open** (not yet addressed). Severity is the review's original rating.
>
> Phase 11 refresh (2026-10-27): C3/R-C3-1, A1/R-A1-5, A4/R-A4-5, C3/R-C3-5,
> and FS-20-related A3/R-A3-4 updated with dated evidence; C1/R-C1-2 partially
> addressed (corrections/identity shipped; author string still user-gated).
> Phase 12 continuation (2026-10-29): C1/R-C1-2 → Fixed — the author identity
> landed (config-file mechanism + maintainer-confirmed string), completing FS-17.

## Critical / High

| ID | Risk | Sev | Status | Residual / notes |
|---|---|---|---|---|
| A4/R-A4-1 | Claim→evidence link missing; every report `UNASSESSED` | Critical | **Fixed** | `Relation.evidence_ids` + `relation add/review` + `analyze claim` wired; fixture tests pin outcomes |
| C2/R-C2-1 | Corroboration awarded on `from_id` count alone; clustering unwired | Critical | **Fixed** | origin-r3 clustering wired; `CORROBORATED_WITH_LIMITATIONS` requires no clustered origins + corroboration edge |
| A3/R-A3-2, C3/R-C3-2 | DNS-rebinding TOCTOU defeats SSRF guard | High | **Fixed** | Connection pinning to pre-validated IPs; Host/SNI preserved; redirect re-validation |
| A1/R-A1-1 | `provenance_completeness` measured rationale text, not evidence | High | **Fixed** | Computed from `rationale AND evidence_ids`; rationale-only scores "partial"/"absent" |
| A4/R-A4-2 | Export crashed on redaction (`PermissionError`), manifest mismatch | High | **Fixed** | Copy writable → redact → manifest over final bytes; CLI e2e test covers it |
| D4/R (orig #4) | Redaction corruption (`[REDACTED]word`), cookie partials, token leaks | High | **Fixed** | `_kv`/`_cookie_kv` rewrite; `&`-safe query parsing; expanded patterns; security tests |
| D4/R (orig #1) | SSRF guard incomplete (CGNAT, IMDS-style, IPv6 site-local) | High | **Fixed** | Explicit deny list incl. `fec0::/10`; unit-tested against measured Python quirks |
| A2/R-A2-1 | TUI keymap advertised unbound keys (Tab/Enter/g) | High | **Fixed (Phase 6, 2026-10-23)** | `BINDINGS`/docstring/parity now agree; keymap-parity test asserts bidirectional mapping; `/` filters with counts, `g` opens a real jump palette, `Esc` pops a bounded back-stack, Ctrl+C cancel implemented + recorded in Runs. Spec: `TUI_INTERACTION_SPEC.md` TS-2/TS-3; journeys J1–J5 green. Behavioral proof added Phase 10: `TestJumpPalette::test_g_opens_jump_palette_and_jumps` (`g` opens the palette listing all 6 labelled workspaces; Esc cancels without jumping; typing an entry lands the workspace) |
| A5/R (orig #16) | Unhandled tracebacks; usage errors collided with NOT_FOUND | High | **Fixed** | Top-level exception mapping (usage=3, not-found=2); `dir_okay=False` on attach |
| B3/R (orig #3) | Export corrupted its own evidence (0o400 rewrite) | High | **Fixed** | See A4/R-A4-2 |
| C1/R-C1-1 | All reports `UNASSESSED`; empty assessments look professional | High | **Fixed** | Relations CLI + analysis wiring; report renders real outcomes + per-claim caveats |
| C3/R-C3-1 | No authorization/scope gate before network actions | High | **Fixed (Phase 11, 2026-10-27)** | `case authorize --scope --authorized-by [--revoke]` records scope decisions as hash-chained analysis events; `case scope` exposes the ledger; `source add --fetch` fails (exit 4, actionable hint) unless the **latest** decision is an active grant; URL host absent from the recorded scope text draws a soft advisory. Residual: scope text is free-form, so matching is textual, not semantic; username checks stay env-gated (D20). Tests: `TestScopeLedger` incl. revoke-reblocks and a DNS-decoy fetch proving the ledger gate is separate from URL policy |
| C4/R-C4-1 | GPS coordinates leak into terminal scrollback via warning text | High | **Fixed** | Inspect warning shows key names, not values; export lists GPS-bearing files by name only |
| C4/R-C4-2 | Silent redaction produces text that looks verbatim but is not | High | **Mitigated** | Redaction reports rule IDs and counts; report caveats state redaction was applied; residual: operator must read the export README |
| D2/R (orig #5) | Terminal injection (ANSI/OSC) via locators/filenames | High | **Fixed** | `s()` escape at every render site; CLI injection tests |
| D2/R (orig #7) | Path traversal via crafted case IDs | High | **Fixed** | Strict case-ID shape validation before any path join; traversal tests |

## Medium

| ID | Risk | Sev | Status | Residual / notes |
|---|---|---|---|---|
| A1/R-A1-2 | core↔storage layering inversion | Medium | **Fixed** | `CaseWorkspace` moved to `storage/workspace.py`; core imports pure |
| A1/R-A1-3 | Two `SCHEMA_VERSION` sources of truth | Medium | **Fixed** | Single definition in `tracefield/__init__.py`; `database.py` imports it |
| A1/R-A1-4 | Catalogue path breaks under wheel install | High (was Medium) | **Fixed (Phase 7, 2026-10-23)** | `data/catalog` now force-included inside the wheel (`pyproject.toml`); path resolves package-relative with repo fallback. Fresh-venv install: `tools status/search/show` + `catalog validate` all exit 0; audit G7 resolved |
| A1/R-A1-5 | Untyped `Relation` endpoints allow cross-case edges | Medium | **Fixed (Phase 11, 2026-10-27)** | Schema-v2 DB triggers (`trg_relations_integrity_{ins,upd}`) refuse missing/cross-case endpoints at write time (UPDATE covered too), plus a same-case JSON guard on `evidence_ids`; app-level checks unchanged. Raw-SQL tamper tests pin every refusal shape. Note: triggers guard NEW writes only — pre-v2 rows are not retro-validated (documented in the migration) |
| A2/R-A2-2 | TUI `self.cases[0]`-style view scoping | Medium | **Fixed (Phase 10, 2026-10-25)** | Views scope rows to the active case, and the case picker never auto-selects with >1 case. Durable proof: `tests/tui/test_journeys.py::TestCaseModel::test_two_case_isolation_across_views_and_reload` (Evidence/Claims/Runs each show only case-B rows after selection, navigation, and a full app reload; case-A rows never leak) + `test_two_cases_never_guess_and_picker_works` (no auto-pick + Evidence isolation). Spec: `TUI_INTERACTION_SPEC.md` TS-1 / P-TS-4 |
| A2/R-A2-3 | Synchronous repo queries hitch in render path | Medium | **Open** | No worker offload yet; acceptable at current data volumes |
| A2/R-A2-4 | TUI never closed DB (WAL linger) | Low | **Fixed** | `_shutdown` override closes connection (see DECISIONS D8) |
| A3/R-A3-3 | `_is_blocked_ip` enumerated checks missed ranges | Medium | **Fixed** | Explicit deny list; measured Python `is_global` quirks documented |
| A3/R-A3-4 | Catalogue staleness has no enforcement | Medium | **Accepted (decided, Phase 11, 2026-10-27)** | Decision D22: **no automated health job** — upstream re-verification is operator-manual; `catalog stale [--max-age-days N]` shipped as a read-only freshness listing (overdue + unparseable dates reported as unknown, never guessed; explicit "not a health verdict" wording; no network, no writes). `last_checked`/`health_result` columns retained in schema v2 for that workflow |
| A3/R-A3-5 | `Catalog.load` silently collapses duplicate IDs | Medium | **Fixed** | Duplicates retained and reported by `validate()` |
| A4/R-A4-4 | Whole-case cluster count fired caveats on every claim | Medium | **Fixed** | Per-claim cluster membership computed from supporting origins |
| A4/R-A4-5 | Assertion `evidence_ids` TEXT column, no dangling check | Medium | **Fixed (Phase 11, 2026-10-27)** | `assertion add/list/review` CLI wired over `AssertionRepo` (previously creation was impossible); assertions gain the same schema-v2 DB guard (`trg_assertions_integrity_{ins,upd}`): `claim_id` same-case, `evidence_ids` JSON same-case |
| A4/R-A4-6 | `attach_file` read whole file into memory | Medium | **Fixed** | Streamed copy (`shutil.copyfileobj`); clustering size guard with explicit skip |
| C1/R-C1-2 | Report defensibility gaps (no generated_at/version/author) | Medium | **Fixed (Phase 12, 2026-10-29)** | FS-17 complete: reports carry a durable report_id/revision/supersession register + lineage corrections (Phase 11) **and** the operator's author identity (config file `report_author` / `TRACEFIELD_REPORT_AUTHOR`; fail-closed config loading, doctor-visible). The maintainer's environment is configured; other operators keep the honest `author not set` fallback until they set their own — per D23, no tool-level default exists |
| C1/R-C1-4 | Absolute paths leak filesystem structure in reports | Medium | **Mitigated** | Report renders source locators through `s()`; path redaction beyond that is **open** |
| C1/R-C1-5 | Event digest omits `tool_fingerprint`; `case-delete` appends no event | Medium | **Mitigated** | Delete appends an event; `occurred_at` **is** bound (audit F4; earlier note was stale); `tool_fingerprint` remains unbound (FS-24, P3 — not part of the Phase 11 schema v2, which was additive tables+triggers to avoid breaking existing chains) |
| C2/R-C2-3 | Near-dup detection failed both directions; Latin-only | Medium | **Fixed** | origin-r3 containment + Unicode tokenization; fixtures pin both |
| C2/R-C2-4 | Contradiction asserted while unreviewed support sat in case | Medium | **Fixed** | Decision table requires *confirmed* contradict for CONTRADICTED (D4) |
| C3/R-C3-3 | `username.py` skipped URL policy validation on redirects | Medium | **Fixed** | Redirect targets re-enter policy validation |
| C3/R-C3-5 | User-Agent in `username.py` lacked a real contact route | Low | **Fixed (Phase 11, 2026-10-27)** | UA now carries the project's own contact route (`tracefield/0.1 (+https://github.com/killerdasher/TRACEFIELD)`), matching `fetch.py`. (The 2026-10-19 description cited the malformed `(+https://)` form, which only the username path ever had.) If a different contact address is later preferred, it is a one-line change |
| C4/R-C4-3 | No perceptual hashing (image duplicate analysis absent) | Medium | **Open** | Planned post-P0; catalogue already records the capability gap honestly |
| C4/R-C4-4 | Signature table false positives can mislabel exhibits | Low | **Mitigated** | Signature table emits "weak/ambiguous" markers; caveat text present |

## Low / Accepted

| ID | Risk | Sev | Status | Notes |
|---|---|---|---|---|
| D8-adj | TUI `_shutdown` is a private-API override | Low | **Accepted** | Tripwire = test warning if Textual renames it (DECISIONS D8) |
| C1/R-C1-3 | `limitations` field overloaded (collection metadata + caveats) | Medium | **Accepted** | Field split deferred; fetch output separates metadata from limitations in practice |
| A1 open | `Observation` per-run vs per-fetch semantics | — | **Accepted** | Per-artefact semantics documented in docstring; revisit with adapter contract |
| B1/R1 | Feature-inflation trap ("OSINT platform" framing) | — | **Accepted** | Positioning fixed in README: complement, not compete |
| B1/R2 | Catalogue licence contamination (CC BY-SA / unlicensed) | — | **Mitigated** | Descriptions project-authored; source-manifest attribution; Bellingcat link-only |
| B1/R5 | Star-count envy (Sherlock 94k) | — | **Accepted** | No star comparisons in any project doc |

## Emerging (this implementation pass)

> Rows below record the **audit-time state (2026-10-19)** and are re-visited in
> the phase reports; several were already fixed in Phases 6–10 (see
> `FINAL_BUILD_SPEC.md` milestone statuses). Phase 11 (2026-10-27) addressed
> the rows the detailed tables above now mark as dated.

| Risk | Sev | Status | Notes |
|---|---|---|---|
| `pip-audit` in CI fails on a transitive CVE with no upstream fix | Medium | **Accepted** | CI job is non-`continue-on-error`; a red audit is a real signal, not noise |
| Catalogue data ships 2,264 records but README/docs may say a different number | Low | **Fixed** | Counts generated from `catalog validate`; docs use the validated number |
| TUI test surface is smoke-level only | Medium | **Accepted → Spec'd** | Deep journeys now specified as TS-6/TS-7 test requirements in `TUI_INTERACTION_SPEC.md`; implementation is P1 |
| Wheel/sdist cannot run catalogue commands (fresh-install broken) | High | **Open (P0)** | Audit G7; blocks any release artifact claim; fix = package `data/` + importlib.resources-style path |
| Redirect hop validate-then-connect TOCTOU (hop 2+ not IP-pinned) | Medium | **Open** | Audit F1; inline comment overstates coverage; fix = per-hop pinning or single-hop redirect refusal |
| `run_backend` allowlist claimed but unenforced | Medium | **Open** | Audit F2; literal call sites today make exposure nil; fix = enforced `{"exiftool","ffprobe","tesseract"}` set + docstring accuracy |
| Newer-schema DB silently accepted by `migrate()` | Medium | **Open** | Audit F3; fix = refuse with exit code + message when `db_version > SCHEMA_VERSION` |
| TUI renders "synthetic/demo data" label over live rows | Medium | **Open** | Audit T7; honesty-boundary violation; fix per TS-4 |
| SQLite corrupt/busy/full, export interruption, cancel paths untested | Medium | **Open** | Audit §6; seed P1 tests in `FINAL_BUILD_SPEC.md` |
