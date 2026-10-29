# Phase 12 — Report Author Identity (FS-17 closed)

> **Date:** 2026-10-29 · **Scope:** the single remaining FS-17 decision —
> the operator's report author identity — and the mechanism that makes it
> per-operator, validated, and honest; then the OOVS-09 re-verdict
> (`FAIL` → `PASS (scoped)` under the mapping's own promotion policy).
> Every fact below came from real command runs or real file contents.
> The author identity string was chosen and confirmed by the maintainer;
> nothing here invents, defaults, or guesses an identity.

---

## 0. Starting state

| Fact | Value |
|---|---|
| Base commit | `598fb09` — Phase 11 final (CI `40532658970` + CodeQL `40532658805` both success on that exact commit) |
| Open spec decision | FS-17 author identity string (FINAL_BUILD_SPEC §8 item 2) — the only remaining user-gated item besides FS-26/27 URLs and publish timing |
| OOVS-09 | `FAIL` (held: mechanism shipped Phase 11; identity missing) |

## 1. The decision (maintainer-confirmed, 2026-10-29)

| Item | Value |
|---|---|
| Author string | `killerdasher — github.com/killerdasher/TRACEFIELD` |
| Persistence | per-operator config file (`~/.config/tracefield/config.toml`, `report_author` key); `TRACEFIELD_REPORT_AUTHOR` env var keeps precedence |
| Explicitly rejected alternative | baking the string into the tool's default — that would stamp the maintainer's identity on reports by any other operator (false attribution); rejected in D23 |

The maintainer's environment is configured (file written `0600`; `tracefield
doctor` shows `config: ok — report author (config file): …` from a real run).

## 2. What shipped (commit `9c28ff3` …)

- **Config-file loader** (`config/settings.py`): stdlib `tomllib`; a
  documented accepted-key allowlist (`report_author` only in this
  iteration); any invalid TOML, unknown key, or non-string value ignores
  the WHOLE file and records `Settings.config_error` for `doctor` —
  fail-closed, never partially applied, never swallowed. Authored config
  errors must not half-apply an identity or crash reporting.
- **`doctor`**: a `config` row reporting file state + the effective author
  and its source ("config file" / "env (TRACEFIELD_REPORT_AUTHOR)"),
  `missing` when fully unset with the honest fallback spelled out.
- **Semantics (D23)**: `report_author` is a per-OPERATOR identity. No
  tool-level default exists. Unconfigured operators get `author not set` —
  an unattributed report is honest about being unattributed.
- **Test isolation**: `tf_home` now points `TRACEFIELD_CONFIG` at a
  per-test path, so the maintainer's real config can never leak into a
  test run; the pre-existing `author not set` pins thereby remain valid
  *unset*-state pins, not accidents of environment.

## 3. Gates (measured locally, on the HEAD commit)

| Gate | Result |
|---|---|
| `pytest -m "not network"` (3.13) | **332 passed / 0 failed / 0 skipped** (11 new: 7 unit loader-contract, 3 e2e author-in-report, 1 doctor rows) |
| `ruff format` / `ruff check` | clean |
| `mypy src` (strict) | clean, 38 files |
| `pip-audit --strict` | clean |
| fresh-venv wheel smoke | `tools status` / `catalog validate` / `doctor` exit 0 from a wheel install |
| Pushed-commit CI | run `40860162983` **success — 332 passed on all three pythons, 0 skipped** (watched) |
| Pushed-commit CodeQL | run `40860162798` **success** (watched) |

## 4. OOVS-09 re-verdict (`FAIL` → `PASS (scoped)`)

The mapping's own policy says a `FAIL` may be promoted only when the
mechanism exists, the identity half is real, and a regression-pinning test
set covers it. As of this phase all three hold:

1. **Mechanism** (Phase 11): report identity register with supersedes
   chain; corrections appended never rewritten and carried forward with the
   lineage; recipient register + `report-history`; exports name the exact
   revision (`TestReportIdentity`, `TestReportRegister`).
2. **Identity** (this phase): the report document block carries the
   operating analyst's identity, actually configured and confirmed in the
   maintainer's environment (`TestReportAuthor` e2e).
3. **Regression travelwires**: broken-config path, env-override
   precedence, and unregistered-state authorship are all pinned.

**Scope limits stated with the verdict:** recipient *notification* of a
correction is operator-executed (the register makes it traceable; nothing
sends anything); the official OOVS acceptance tests (`tests.json`) remain
unrun; the author-identity half is claimed from a verified configuration
(a fresh install prints `author not set` until its own operator decides).

Summary line: **9 `PASS` (each scoped), 0 `FAIL`, 1 `NOT_ASSESSED`**
(`-10` still not assessable: no release governance yet).

## 5. Explicitly NOT done in this phase

- FS-23 (catalogue licence fields, tier-first) — open, non-user-gated.
- FS-24 remainder (`tool_fingerprint` digest binding; `catalog`/`providers`
  wire-or-drop) — open, P3, needs a chain-compatibility decision.
- FS-25 (perceptual hashing) — P3.
- FS-26/FS-27 comparison URLs + publish/OOVS publication timing — user-gated.

## 6. Honesty notes

- The author string appears in this repo's docs exactly as the maintainer
  confirmed it; it is also now in the *operator's* local config, not in
  the product — installed copies have no author set.
- The re-verdict does not claim certification, and the mapping keeps its
  "not an OWASP assessment" paragraph; it is a self-assessment with stated
  limits.
- CI claim policy unchanged: run IDs recorded only for runs watched to
  completion for the exact commit.
