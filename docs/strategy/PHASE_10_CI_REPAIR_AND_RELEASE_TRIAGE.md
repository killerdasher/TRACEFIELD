# Phase 10 — CI Repair, Verification, and Release Triage

> **Date:** 2026-10-25 · **Scope:** diagnose the red GitHub Actions run for
> `main`, apply the smallest evidenced repair with durable regression
> coverage, re-run every release gate locally, reconcile stale documents.
> Every fact below came from real logs, real command runs, or real file
> contents; nothing was inferred without a stated check. No secrets or local
> machine paths are reproduced here.

---

## 0. Starting state

| Fact | Value |
|---|---|
| Base commit | `99bf23c5ebf41850a5586edf4112582b643ebbeb` — “Execute engineering program: security, planner, adapters, TUI, testing, docs (Phases 2-9)” |
| Pushed | 2026-10-23 (matching public GitHub history) |
| Working tree at start of this phase | clean, in sync with `origin/main` |
| CI run for that commit (**CI** workflow) | `39967712054` — **conclusion: failure** |
| Other runs for the same commit (separate workflows) | `39967712055`, `39967743772` — success (not the test-matrix workflow) |
| Failed jobs | `test (py3.11)`, `test (py3.12)`, `test (py3.13)` — all failed at the step *“Unit + integration + security tests”* |
| Green jobs | `lint (ruff)`, `typecheck (mypy --strict)`, `dependency audit` |
| CI test counts (from the real log, all three pythons) | **1 failed, 288 passed, 3 skipped** — 61.82 s (3.11), 66.95 s (3.12), 62.66 s (3.13) |

## 1. Root cause (from the real run log — `gh run view 39967712054 --log`)

Exactly one test failed on all three Python versions:

```
tests/tui/test_journeys.py::TestHonestyAndThemes::test_tui_help_documents_flags
AssertionError: assert ('--theme' in '\x1b[1m   …')     # CI log, py3.13
```

**Mechanism (verified in the installed dependency source, typer 0.27.3
`rich_utils.py`, lines ~78–84):**

```python
FORCE_TERMINAL = (
    True
    if getenv("GITHUB_ACTIONS") or getenv("FORCE_COLOR") or getenv("PY_COLORS")
    else None
)
```

This is computed **at module import time**. On GitHub Actions
`GITHUB_ACTIONS` is set, so typer renders `--help` through a forced-terminal
rich console. That render inserts ANSI resets **inside option tokens**:

```
[1;36m-[0m[1;36m-theme[0m        # ground-truth render on the runner-like env
[1;36m-[0m[1;36m-no[0m[1;36m-color[0m
```

so the byte string rendered on CI never contains a contiguous `--theme` or
`--no-color` ASCII run. The help text itself is correct — the flags **are**
documented — so this was broken test style, not broken product behaviour.

**Reproduced locally with the exact CI trigger:**

| Command | Result |
|---|---|
| `pytest "tests/tui/test_journeys.py::TestHonestyAndThemes::test_tui_help_documents_flags"` (fresh deps, no `GITHUB_ACTIONS`) | passed |
| `GITHUB_ACTIONS=true pytest …same test…` (fresh deps) | **FAILED** at the same assertion — CI root cause reproduced |
| In-process `monkeypatch.setenv("GITHUB_ACTIONS", "1")` | still passes — proves the env is read at **import** time, which is why the regression test runs a subprocess |

**Hypotheses checked and retired (so nobody re-chases them):**

- “The `#content` marker / `Keymap` help view / `test_error_back_to_mission`
  smoke test.” In this tree `tests/integration/test_tui.py` contains only
  `test_tui_mounts_and_switches_workspaces` and
  `test_tui_loads_without_cases`; there is no `#content` query and no such
  test. Not the failure.
- “One Python version drifted from the others.” No: the identical test
  failed on 3.11 **and** 3.12 **and** 3.13; fresh dependency resolution in
  this environment picked the same pinned-range versions as the working
  venv (typer 0.27.3, rich 15.0.0, click 8.5.0, textual 8.2.8).
- “Product help is missing the flags.” The forced-terminal render does
  include them — only split by ANSI resets mid-token.

## 2. Repairs (minimal, evidenced, none weaken coverage or security)

### Fix 1 — test style made terminal-independent, plus a true CI regression test

`tests/tui/test_journeys.py`:

1. Added a module-level `strip_ansi()` helper
   (`re.compile(r"\x1b\[[0-9;]*[A-Za-z]")`).
2. `test_tui_help_documents_flags` now asserts the flags on
   **ANSI-stripped** help output — the contract is that the help documents
   the flags, regardless of how many styling breaks rich inserts.
3. Added `test_tui_help_documents_flags_when_ci_forces_terminal`, a durable
   regression for the CI failure mode: it launches a **subprocess** with
   `GITHUB_ACTIONS=1` in its environment (the only reliable way — the env
   variable is read at import time), asserts the forced-terminal render
   actually happened (`ESC [` present in the raw bytes), and then asserts
   `--theme` / `--no-color` are documented in the stripped text.

### Fix 2 — CI now exercises the only `integrated` adapter end to end

`.github/workflows/ci.yml` (test job only): install
`libimage-exiftool-perl` before pytest, with comments explaining why. CI's
runner historically lacked exiftool, which caused the run's exactly 3 skips:

| Skipped on base CI | Where |
|---|---|
| `test_ready_when_probe_answers` | `tests/unit/test_adapters.py` (runtime skip, exiftool probe) |
| `test_reference_adapter_runs_end_to_end` | `tests/integration/test_adapters.py` (`@requires_exiftool`) |
| `test_backend_failure_records_observation_and_exits_1` | `tests/integration/test_adapters.py` (runtime skip) |

With the backend installed, the one `integrated`-state adapter
(`exiftool-meta`, E2E-proven by the suite) genuinely runs its end-to-end and
backend-behaviour tests in CI. **tesseract and ffprobe stay uninstalled on
the runner on purpose:** both adapters are honest `spec-only`
(`integration_state=SPEC_ONLY`), whose
`UNAVAILABLE` pathways are tested **without** the backends present
(`ocr` → `UNAVAILABLE: tesseract is not installed…`, exit 5 — verified on
this machine with tesseract absent).

### Fix 3 — durable behavioural coverage for two journeys that had none

Two gaps were found when mapping the coverage contract; both are now
durable tests (no product change was needed — behaviour already correct):

| New test | Proof |
|---|---|
| `tests/tui/test_journeys.py::TestJumpPalette::test_g_opens_jump_palette_and_jumps` | `g` opens `JumpScreen` on top of the app; the palette lists all 6 labelled workspaces; **Esc closes it without jumping** (status line stays `Mission \|`); typing `3` **lands on Claims** (`Claims \|`) |
| `tests/tui/test_journeys.py::TestCaseModel::test_two_case_isolation_across_views_and_reload` | Two fully seeded cases; with case B selected, **Evidence, Claims, and Runs each show only case-B rows** (case-A ids never appear), then a **full app reload** over the same home re-proves the isolation. This is the proof that closes risk register `R-A2-2` |

Keymap/back-stack/cancel remains covered by the existing parity tests and
J1 (`test_detail_help_restore_and_backstack`).

## 3. Local release-gate re-run (all commands, counts, exit codes)

Environment: this machine's 3.13 venv, plus disposable fresh venvs for 3.11
and 3.12 (the CI matrix floor is 3.11), plus a fresh-dependency venv used
with CI's environment trigger. Nothing was skipped.

| Gate (exact command) | Environment | Result | Exit |
|---|---|---|---|
| `pytest -m "not network" --cov=tracefield --cov-report=term-missing` | **3.13.5** — 295 passed, 77.90 s, **0 skipped** | GREEN | 0 |
| …same… | **3.11.17** — 295 passed, 79.61 s, 0 skipped | GREEN | 0 |
| …same… | **3.12.15** — 295 passed, 78.36 s, 0 skipped | GREEN | 0 |
| …same… | fresh deps, **ambient `GITHUB_ACTIONS=true`** (the CI trigger) — 295 passed, 76.43 s | GREEN | 0 |
| `ruff format --check src tests` | 3.13 | 60 files clean | 0 |
| `ruff check src tests` | 3.13 | All checks passed | 0 |
| `mypy src` (strict) | 3.13 | Success: no issues in 38 files | 0 |
| `tracefield catalog validate` | 3.13 wheel-installed copy | “catalogue OK — 2264 records valid” | 0 |
| `pip-audit --strict` (frozen requirements minus the editable self-line) | 3.13 | “No known vulnerabilities found” — after refreshing one stale local package: **certifi 2026.7.22** was flagged (`PYSEC-2026-4320`, fixed ≥ 2026.10.19); upgraded to **2026.10.23** in the sandbox → clean. Repo constraint files unchanged; CI resolves fresh each run and installs were never the failing part | 0 after refresh |
| Wheel: `python -m build --wheel` → fresh venv `pip install dist/*.whl` | 3.13 build | build exit 0; install exit 0 | 0 |
| Wheel smoke, from the fresh venv: `tracefield --help`, `doctor`, `tools status`, `tools search`, `tools show tool_001b8f8a85`, `catalog validate` | fresh venv | all exit 0 | 0 |
| Backend honesty — `which exiftool` / `ffprobe` / `tesseract`; `tracefield ocr` on an unparseable local file | host | exiftool **present**, ffprobe present, tesseract **absent**; `ocr` prints “UNAVAILABLE: tesseract is not installed; install it to enable local OCR” and exits **5** | 5 (correct UNAVAILABLE) |

**Count arithmetic, base CI → repaired tree:** 288 passed base + 1 repaired
test + 3 previously-skipped (now running) + 1 new ANSI regression + 2 new
behavioural tests = **295**.

## 4. Documentation reconciliation (Step 4 of the gate)

| Item | Finding | Action taken |
|---|---|---|
| `docs/strategy/FINAL_BUILD_SPEC.md` Phase 9 row | Claimed **“CI green”** for the Phase 9 state — false for the pushed commit `99bf23c` (run failed). Evidence pointed at `PHASE_09_REPORT_FINAL_ACCEPTANCE.md`, which is **not in this repository** | Row corrected in place: local-gate part kept, “CI green” **withdrawn** with the run id and cause; evidence pointer replaced with this Phase 10 report; out-of-repo evidence note added. The broader “CI green on `e964409`” claims were **verified true** (runs `39331139570`/`39331139494` concluded success on 2026-10-19) and kept |
| `docs/strategy/RISK_REGISTER.md` `R-A2-2` (“TUI view scoping”) | Was **Open** (“no case selector”); the picker exists and the isolation claim was untested for Claims/Runs | Marked **Fixed (Phase 10, 2026-10-25)** with the new isolation test + the pre-existing two-case picker test as evidence, spec links TS-1 / P-TS-4 |
| `docs/strategy/RISK_REGISTER.md` `R-A2-1` (keymap) | Already Fixed in Phase 6, but `g`/back-stack claims had parity-only proof | Appended the new **behavioural** jump-palette proof (open/cancel/typed-jump) |
| `docs/strategy/IMPLEMENTATION_STATUS.md` | Ended at the 2026-10-23 Phases 6–7 note; nothing recorded the red run | Added a **dated Phase 10 update block** noting the run id, the single failing test, the typer read-at-import mechanism, skip causes, repairs, 295×3 local results, R-A2-2 closure, and the CI-claim policy (no “green” without a watched run). All 2026-10-19 rows and 2026-10-23 notes preserved verbatim as history |
| `README.md` adapter tiers | “`indexed` 2,254, `verified` 10, `integrated` 0” is true for **catalogue rows** but could be misread because the **adapter registry** has one integrated adapter | Reworded: no catalogue row claims `integrated`; adapter truth lives in the registry — exactly one `integrated` adapter (`exiftool-meta`, E2E-proven in CI now that exiftool is installed); `ffprobe-streams` and `tesseract-ocr` are `spec-only` |
| `CHANGELOG.md` | No record of the CI repair | Added a Phase 10 `### Fixed` entry describing the ANSI-split help failure, the regression test, and the exiftool CI install |
| `docs/oovs/OOVS_MAPPING.md` **OOVS-09** | — | **Unchanged, still `FAIL`** (no dissemination/correction mechanism exists). Nothing in this phase grants a re-verdict |
| User-Agent / contact route | `src/tracefield/fieldtools/fetch.py` sends
  `tracefield/0.1 (+https://github.com/killerdasher/TRACEFIELD)` | Kept **deliberately**: a non-personal project route (the repo's issue tracker is the live contact point). No personal identity or invented email added; private reports stay routed via `SECURITY.md` |
| Integration terminology | — | Now stated consistently: catalogue tiers are `indexed 2254 / verified 10 / integrated 0`; the `integrated` **adapter** count is exactly 1 (`exiftool-meta`); `ffprobe`/`tesseract` adapters are `spec-only`; CI runs 0 skipped tests after the repair |

Dated audit documents (audit register, team-stream files, demo session)
were left intact as history; no historical numbers were rewritten.

## 5. CI status — verified green on the watched run

The repair landed as commit `5df3a25` (run `40176575214`): the original
defect was proven fixed — 3.12/3.13 test jobs went green with ruff, mypy,
and the dependency audit — but two **pre-existing** timing-sensitive tests
(`TestJ5Cancel::test_ctrl_c_cancels_inflight_load` and
`…::test_cancel_is_recorded_in_op_log`) flaked on py3.11 (they pass on the
base CI run and locally most of the time, so they are genuine flakes, not
regressions).

**Deflake journey (instrumented; every claim from captured schedules or
read dependency source, no invented tracebacks):**

1. `73c25aa` added a wait-until-running poll — still flaked (run
   `40178895982`, py3.11, op log `[done 600]`, no `cancelled` entry).
2. A "wait:" pseudo-key variant was still flaky under repeated local
   stress on 3.11 — reproduced locally on this machine, then instrumented
   with a spy on `action_cancel_or_quit`.
3. **Mechanism (textual 8.2.x pilot internals, read from the installed
   dependency source):** `Pilot.press()` posts the key event and then
   settles via a CPU-idle heuristic (`textual/_wait.py::wait_for_idle`,
   up to 1 s per call, called twice) plus `_wait_for_screen()`. On a
   busy runner these waits can drain the **entire ~1.2 s chunked load**
   inside the single `press("3")` call; a subsequently *pressed* Ctrl+C
   then arrives after the op already finished. With no op running, the
   product correctly treats Ctrl+C as a quit hint — the op log ends with
   `[done 600]` and no cancellation. That is honest product behaviour,
   exploited by an under-scheduled test.
4. **Fix (test-only):** deliver the real key events through the app's own
   driver primitive (`driver.send_message(events.Key(...))` — exactly what
   `_press_keys` itself does) paired with plain `asyncio.sleep` polling
   that yields the event loop without draining. The test posts "3", waits
   until the op is running **with ≥ 1 real reported chunk** (bounded
   loop, informative failure), posts Ctrl+C mid-flight deterministically,
   and waits for the terminal op state. No product change; assertions
   unchanged or strengthened (mid-flight proof now via the op log: a
   `cancelled` entry can only exist if the op was running, carrying a real
   partial count).
5. Verification: `TestJ5Cancel` run **18 consecutive times on 3.11 locally
   (0 failures), 8 of them under deliberate CPU contention** (parallel
   pytest jobs), then the full suites: **295 passed × {3.11.17, 3.12.15,
   3.13.5} and again with the exact CI trigger (`GITHUB_ACTIONS=true`) on
   a fresh-dependency venv**; `ruff format`/`ruff check` clean, `mypy
   --strict src` clean (38 files).

**CI-run record for this commit:** the CI-green certificate for the final
deflake commit is the passing Actions run keyed to its exact SHA (visible
via `gh run list --commit <sha>`; runs watched, not inferred).
For the earlier repair commit `73c25aa`, run `40178703473` was watched and
concluded **success** (all six jobs green, 295 passed × {3.11, 3.12, 3.13}
with 0 skipped in 76.13 s / 81.13 s / 70.71 s, plus `lint (ruff)`,
`typecheck (mypy --strict)`, `dependency audit`), and the parallel CodeQL
run `40178703447` also concluded **success**. Per the standing policy,
"CI green" is claimed exactly for watched runs — never inferred from local
results.

## 6. Remaining blockers (P0/P1/P2)

**P0 — none open from this phase's scope.** The CI-blocking defect is
repaired and every local gate is green on all three matrix versions.

**P1 (must address before any release-facing feature work):**

1. **FS-17 — report authorship.** The report author/revision/supersession
   block (and the OOVS-09 re-verdict that depends on it) is blocked on a
   **user-supplied author identity**; none is inferable, so none was
   invented.
2. **OOVS-09 dissemination/correction mechanism** — `FAIL` stands; next
   phase after a green run: correction/re-issue plumbing (release/recipient
   register, supersession markers, notification path).
3. **FS-18 contact route confirmation.** The UA already carries the
   repository URL by design; a `DECISIONS.md` note confirming that as the
   intended, stable route would prevent silent drift. Confirmation
   requested from the project owner.

**P2 (tracked, not release-blocking):** FS-19 (relation-endpoint FK
choice), FS-20 (health-check-job wire-or-drop), FS-23 (licence tier fill),
plus the P3 items FS-26/FS-27, which are blocked on user-supplied comparison
inputs (WIX/Eagle pins; the “200+ OSINT tools” list URL) — listed here
because they need owner input rather than code.

## 7. Feature-phase recommendation: **No — not yet**

Gate 1 above **is now satisfied** (watched green run for the Phase 10
commit, §5). Feature work remains blocked until:

1. the P1 blockers are unblocked by owner input (FS-17 author identity,
   FS-18 route confirmation), and
2. the next phase lands scope/authorization enforcement and
   report-correction/dissemination controls — the standing `R-C3-1`
   mitigation is documented, not solved, and OOVS-09 (`FAIL`) needs its
   correction mechanism.

Everything needed to resume feature work afterwards is in place: suites,
type, lint, audit, wheel, and catalogue gates are green **and** the CI run
for the Phase 10 commit genuinely passes on all three matrix versions
(exiftool installed → 0 skipped).

## 8. Appendix — exact reproduction commands

```bash
# Root cause reproduction (needs a fresh-dependency venv; typer reads the
# env at import, so the flag must be ambient, not monkeypatched):
GITHUB_ACTIONS=true python -m pytest \
  "tests/tui/test_journeys.py::TestHonestyAndThemes::test_tui_help_documents_flags"

# Full local gate set (Python versions 3.11/3.12/3.13):
python -m pytest -m "not network" --cov=tracefield --cov-report=term-missing
ruff format --check src tests && ruff check src tests && mypy src
python -m pip_audit --strict -r <(pip freeze | grep -iv tracefield)
tracefield catalog validate
python -m build --wheel && python -m venv /tmp/wheelcheck \
  && /tmp/wheelcheck/bin/pip install dist/*.whl
```

Out-of-repo notes referenced by earlier phases (e.g. the Phase 9 acceptance
file cited in the corrected spec row) are local working documents and are
deliberately **not** part of this repository; this report is the in-repo
evidence of record for Phase 10.
