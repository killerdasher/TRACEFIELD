# TRACEFIELD — Post-Build Audit

> Audit date: **2026-10-19/20** (UTC 2026-10-19, local +03:00), on the clean
> 4-commit checkout `fd6eec4 → 86a67cc → cabcfa8 → e964409`, branch `main`,
> no uncommitted changes at phase start. This document records what was
> inspected, how, and what was found. It changes no product code. Companion
> deliverables: `TUI_INTERACTION_SPEC.md` (interaction remediation spec) and
> `FINAL_BUILD_SPEC.md` (consolidated priorities/milestones).

## 1. Method and scope

| Phase | What was done | How |
|---|---|---|
| Baseline inventory | Confirmed commits, clean tree, doc set, absence of prior spec/audit files | git, file inventory |
| Behavioural audit | TUI exercised headlessly against a fresh workspace with 2 synthetic cases (probe script, temp home) | Textual `run_test()` pilot |
| Code reading | Security-critical paths re-read line-level: fetch, backend runner, digest, migration, catalogue path, report | Direct source reading |
| Release gates | Full gate re-run incl. **fresh-venv wheel install** | ruff/mypy/pytest/catalog/pip-audit/`python -m build` + clean venv |
| Local tool search | Desktop dirs scanned for OSINT tool candidates (read-only) | filesystem search |
| Research refresh | Practitioner survey re-fetched; Sherlock/Maigret/SpiderFoot re-verified | primary sources, dated in `RESEARCH_REGISTER.md` |

Constraints honoured: **no commits, pushes, or destructive git**; no product
build-execution prompt produced; no live probing of third-party targets
(WIX's test suite was therefore **not** run); no broad rewrites.

## 2. Current-state matrix

| Area | State | Evidence | Verdict |
|---|---|---|---|
| Case/evidence core | Lifecycle, content-addressed immutable evidence, hash-chained events, verify/export | 207-test suite green | **Healthy** |
| Analytic engine | Sources/claims/observations/relations, origin-r3, contradictions, assess decision table, JSON/MD report | integration tests green | **Healthy** |
| Field tools | hash/inspect/ocr/fetch/username check, honest UNAVAILABLE states | integration + security tests green | **Healthy** (OCR untestable on this host: tesseract absent) |
| Registry | Inert JSONL catalogue, tiered counts, validate/sync (offline importers only) | `catalog validate` 2,264 OK | **Healthy in-repo**, broken from wheel (§4 G7) |
| Security | SSRF deny-list + first-hop pinning, redaction, sanitization, 0700/0600, cross-case trigger | security tests green; §5 findings | **Healthy with 3 gaps** (§5) |
| Logging | JSONL audit log, redacted argv, fail/unhandled events | prior-phase commit `cabcfa8` era | **Healthy** |
| CLI | 21 commands, exit codes 0/1/2/3/4/5, `--json` everywhere | `--help` inventory re-run | **Healthy** |
| HTML report | `render --format html`, escaped, self-contained, no JS | prior phase | **Healthy**; author/revision absent (§5 F5) |
| TUI | Mounts, switches, quits | headless probe | **Advertises behaviour it does not implement; mixes cases** (§3) |
| Packaging | Wheel builds; `data/` not shipped | fresh-venv install | **FAIL** (§4 G7) |

## 3. TUI behavioural findings (all confirmed by probe, not by reading alone)

Probe: fresh `TRACEFIELD_HOME`, 2 cases created via CLI, TUI driven key-by-key.

| # | Observation | Evidence |
|---|---|---|
| T1 | `?` help **overwrites `#content`**; status bar still says the previous workspace (e.g. "workspace: Claims" while help is shown) | probe |
| T2 | `g` does **not** open a palette/jump list — only the status line "go to: press 1-6, or ? for help" | probe |
| T3 | `/` does **not** filter — status shows "search: use the CLI…" | probe |
| T4 | **Tab and Enter do nothing**, yet the module docstring (`tui/app.py:7-8`) advertises "Tab next panel / Enter inspect selected"; `BINDINGS` (app.py:99-110) contains neither | probe + source |
| T5 | `Esc` always jumps to workspace 0 (Mission); no back-stack | probe |
| T6 | Evidence/Claims/Runs views **list rows from all cases** (`lists_cases: 2` in a 2-case workspace); no active-case concept; no case selector (`c` is a no-op) | probe |
| T7 | Subtitle "(synthetic/demo data only in this view)" is false — views render live DB rows | probe + source |
| T8 | No progress/cancellation model; `Ctrl+C` advertised as "cancel current operation first" in docstring but no cancel binding/action exists | probe + source |
| T9 | Hard-coded hex colours in CSS; no theme tokens | source |
| T10 | `tests/integration/test_tui.py` is smoke-only (mount/switch/help/esc/quit) — none of T1–T8 can regress-detect | test file |

**Consequence:** RISK `A2/R-A2-1` ("TUI keymap advertised unbound keys",
previously marked *Fixed*) is **wrong as of this checkout** and is re-opened in
`RISK_REGISTER.md`. The remediation spec (workspaces, keymap, journeys,
progress/cancel, active-case model) is `TUI_INTERACTION_SPEC.md`.

## 4. Release-gate matrix

| # | Gate | Result |
|---|---|---|
| G1 | `pytest` (strict markers, `filterwarnings=error`) | **PASS** — 207 passed (85 unit / 98 integration / 23 security / 1 e2e), exit 0 |
| G2 | `ruff check src tests` | **PASS** (clean) |
| G3 | `ruff format --check` | **PASS** (49 files) |
| G4 | `mypy src` (strict) | **PASS** (no issues, 34 files) |
| G5 | `tracefield catalog validate` | **PASS** — 2,264 records valid |
| G6 | `pip-audit --strict` (requirements minus the editable self-line) | **PASS** — no advisories |
| G7 | **Fresh-venv wheel install smoke** (`python -m build --wheel`, install into clean venv) | **FAIL** — `doctor`/`case`/`evidence`/`report` work; `tools status` → **exit 2**, `error: catalogue data not found at <venv>/lib/python3.13/data/catalog/tools.jsonl` |
| G8 | CI on `e964409` | **PASS** (6 jobs, from prior phase; not re-run this phase — no pushes) |
| G9 | Network-marked tests | **NOT_RUN by design** — zero tests carry the `network` marker |
| G10 | OCR backend | **NOT_RUN** — tesseract absent; UNAVAILABLE path covered by tests |
| G11 | Git state | Clean at start; **unchanged** (this phase made no commits) |

**G7 root cause (two lines of evidence):** `pyproject.toml` wheel target sets
`packages = ["src/tracefield"]` only, so `data/` is never packaged; and
`cli/main.py:1186` resolves the catalogue as
`Path(_tf.__file__).parent.parent.parent / "data" / "catalog" / "tools.jsonl"`
which only works from a source checkout. This confirms known debt #5 as a
**P0 packaging defect**, not an untested theoretical risk.

## 5. Security review findings (line-level re-read)

| ID | Finding | Where | Severity |
|---|---|---|---|
| F1 | Redirect hops are policy-validated in the request hook but **not IP-pinned**: hook runs `validate_fetch_url` (DNS resolved at validation), then httpx connects with fresh resolution — a validate-then-connect window on hop 2+ (first hop is pinned). The inline comment claims the gap is closed; it is only closed for the first hop | `fieldtools/fetch.py:82-108` | Medium |
| F2 | `run_backend` docstring says "Run an **allowlisted** local utility" but the code only does `shutil.which(argv[0])` — no allowlist enforced inside the runner (all current call sites are literal `exiftool`/`ffprobe`/`tesseract`, so today's exposure is nil; the docstring overclaims and the defence-in-depth is absent) | `fieldtools/inspect.py:132-145` | Medium |
| F3 | `migrate()` runs `range(version + 1, SCHEMA_VERSION + 1)` — a **newer** schema DB is silently accepted (empty range), not refused with a clear error | `storage/database.py:254-263` | Medium |
| F4 | `compute_event_digest` **does** bind `occurred_at` (debt #4's first half was stale) but still omits `tool_fingerprint` | `core/provenance.py:41-51` | Low (schema v2) |
| F5 | Report still carries no author identity, revision, or supersession block → OOVS `-09` FAIL and RISK `C1/R-C1-2` stand unchanged | `reporting/` | High (release claim) |
| F6 | Redaction/URL-policy/trust_env/shell-less-subprocess posture re-verified **healthy** (patterns, CGNAT/`fec0::/10`/metadata-host denials, `trust_env=False`, `--` before paths, sanitized env) | `security/`, `fieldtools/` | — |

## 6. Fault-tolerance and cross-case coverage inventory

**Present:** backend missing/UNAVAILABLE; HTTP 403/429/5xx classification;
OCR unavailable; cross-case provenance trigger + cross-case attach refusal (2
tests).

**Absent (tested nowhere):** SQLite busy/locked, corrupt DB, disk-full or
write-permission loss, **newer-schema refusal (F3)**, export interruption
mid-copy, in-app operation cancellation. Seed items for `FINAL_BUILD_SPEC.md`
P1.

## 7. Local tool search (desktop, read-only)

| Candidate | What it is | Integration verdict |
|---|---|---|
| `~/Desktop/dashey` | Project self-named **"WIX — Web Intelligence & Attack-Surface Reasoning Engine"** v0.1.0, Apache-2.0, hatchling, 64 test files/502 tests, SECURITY/HARDENING/Makefile | **Blocked** — not a git repository (no commit to pin); active web-recon suite, so its tests were **not run** this phase (would probe third-party targets, prohibited) |
| `~/Desktop/eagle` | "Eagle — Federal-Grade Cybersecurity Pentesting Platform" v1.0.0, setup.py, 29 test files | **Blocked** — **no LICENSE file found** → licence unknown |
| `pythonlab/`, `OMEGA7_REPORTS/` | Loose scripts / report text files | Not tool repos; not integration candidates |
| SyncFlow (github `syncflow PRJ`, `my app/syncflow`) | The user's app-sync workflow | Not OSINT; out of scope |
| "200+ OSINT tools" repo | Referenced by the penultimate research prompt | **Unresolved** — no URL/name in prompts, checkout (grep: 0 matches) or context; logged as open question (user input required), not guessed |

## 8. Documentation inconsistencies found (to be corrected in this phase)

| File | Issue | Fix |
|---|---|---|
| `IMPLEMENTATION_STATUS.md` | Header says "2026-10-16, pre-first-commit"; git-state block claims "no commits yet" while 4 commits exist | Corrected in this phase |
| `IMPLEMENTATION_STATUS.md` debt #4 | Claims `occurred_at` not in digest — stale (F4) | Corrected |
| `IMPLEMENTATION_STATUS.md` debt #5 | "wheel packaging not yet exercised" — now exercised and FAILING | Corrected |
| `OOVS_MAPPING.md:14` | "203 tests" — actual 207 | Corrected |
| `DEMO_SESSION.txt` header | "2026-10-20 00:54+03:00" is a local-timezone artifact of a 2026-10-19 UTC capture | Annotated, not rewritten |
| RISK `A2/R-A2-1` | Marked Fixed — demonstrably untrue in this checkout (T4) | Re-opened |
| RISK `C1/R-C1-5` | Implies `occurred_at` unbound — only `tool_fingerprint` remains | Corrected |

## 9. Explicit non-actions

No product code was modified; no commits/pushes; no new framework; no
planner/plugin work; no live-target testing; no official OOVS acceptance tests
executed (self-assessment remains self-assessment); this document is not a
certification or a release authorization.
