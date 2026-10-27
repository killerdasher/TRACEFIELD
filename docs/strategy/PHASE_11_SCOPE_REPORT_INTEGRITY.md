# Phase 11 — Scope Ledger, Report Identity, and DB Integrity

> **Date:** 2026-10-27 · **Scope:** the non-user-gated remainder of the
> roadmap: scope/authorization enforcement (OOVS-01), report identity /
> corrections / dissemination controls (OOVS-09 mechanism), DB-level
> referential integrity, the assertion creation path, the FS-20 catalogue
> decision, and the User-Agent contact route. Every fact below came from
> real command runs or real file contents; nothing is inferred without a
> stated check. No secrets or local machine paths are reproduced here.

---

## 0. Starting state

| Fact | Value |
|---|---|
| Base commit | `0883d44` — "Phase 10: deterministic mid-flight cancel in J5 tests (final deflake)" |
| CI at base | CodeQL + test workflows green on the exact pushed commit (Phase 10 report) |
| Local gates at start | 5 prior commits on `main`, suite at 309 tests (3.13), docs not yet reconciled |

## 1. What shipped (five implementation commits)

| Commit | Content | Map |
|---|---|---|
| `9a81c2b` | **Schema v2** — additive-only migration: `case_reports` (identity: revision/supersedes/superseded_by), `report_corrections`, `dissemination` tables + `trg_relations_integrity_{ins,upd}` / `trg_assertions_integrity_{ins,upd}` triggers; `SCHEMA_VERSION 1→2` with the existing tripwire asserted at 2 | FS-19, A1/R-A1-5, A4/R-A4-5 |
| `ac1b707` | **Report identity + dissemination** — `ReportRepo` (register/lineage/corrections/shipments), report schema v3 (document block carries real `report_id/revision/supersedes` + lineage corrections; unregistered payloads read `revision: "unregistered"` honestly), `build_report(register=)` + `build_registered_report`, single-registered-payload `export_case` + `--recipient` shipment register, CLI `report --register/--no-register` (default register), `report-correct`, `report-history`, `case-export --recipient` | FS-17 (machinery), OOVS-09 |
| `84ec255` | **Scope authorization ledger** — `case authorize --scope --authorized-by [--revoke]` (hash-chained `scope.authorize`/`scope.revoke` events), `case scope` read view, `source add --fetch` gate (exit 4 unless the latest decision is an active grant) + soft host advisory, `EventRepo.latest_action` | OOVS-01, C3/R-C3-1 |
| `1c977e0` | **Assertion creation path** — `assertion add/list/review` over `AssertionRepo` (+`get`/`set_review_state`), same-case `--claim`/`--evidence` validation, hash-chained `assertion.add` event | A4/R-A4-5 |
| `3f17c8c` | **Catalog staleness decision + UA** — `catalog stale [--max-age-days N]` read-only freshness listing (`checked_age_days`; unknown dates reported, never guessed; "not a health verdict" wording), User-Agent in `username.py` set to the project's repo contact route | FS-20 decided, C3/R-C3-5 |

Net: 13 files, +1,834/−37 (code+tests) across the five commits.

## 2. Design decisions (full text in `DECISIONS.md` D20–D22)

- **D20** — authorization is a ledger of hash-chained events (latest decision
  wins); enforcement sits at the fetch boundary; scope-text matching is a
  soft advisory, never claimed semantic; username checks deliberately stay
  env-gated (not case collection).
- **D21** — one registered revision per rendered document (export renders
  both formats from ONE identity); corrections append and travel forward
  with the lineage; shipments recorded, not automated; OOVS-09 verdict held
  until the author string exists.
- **D22** — no automated catalogue health job; `catalog stale` is a
  freshness listing; unknown freshness is reported; columns retained.

## 3. Migration safety evidence

- Additive-only: v1 tables/columns untouched; `test_migration_from_v1_database`
  constructs a real v1 database with data, re-opens (auto-migrates), asserts
  data survival + trigger installation.
- Idempotent: `migrate()` reruns cleanly (`CREATE TABLE/TRIGGER IF NOT EXISTS`).
- Trigger semantics were **empirically probed before writing** (standalone
  sqlite probe): evaluator short-circuits `json_valid(...) AND NOT
  EXISTS(json_each(...))`, so invalid JSON is refused without error-in-error;
  all guard paths raise the intended `IntegrityError` messages (cross-case,
  invented, dangling, non-text element, invalid JSON, mixed).
- Guards cover **new writes only**; pre-v2 rows are not retro-validated —
  stated in the migration script itself, not hidden.

## 4. Verification gates (all on the HEAD commit, measured locally)

| Gate | Result |
|---|---|
| `pytest -m "not network"` (3.11) | **321 passed / 0 failed / 0 skipped** |
| `pytest -m "not network"` (3.12) | **321 passed / 0 failed / 0 skipped** |
| `pytest -m "not network"` (3.13) | **321 passed / 0 failed / 0 skipped** (one unrelated TUI journey flaked once in a full run; ×3 isolated reruns + a full-suite rerun both clean) |
| `ruff format` | clean |
| `ruff check` | clean (includes ruff-found fixes: F821 type annotation import, RUF043 regex escapes) |
| `mypy src` (strict) | clean, 38 files |

Test-count math: 315 (schema v2 + identity + scope ledger) + 3 assertion + 3
`catalog stale`/catalogue = **321**. Notable new pinned behaviour: a
repo-level roundtrip fixture that used **invented ids** was replaced by a
real-id one — the old fixture is no longer storable at the DB layer, by design.

## 5. Behaviour change of record (operator-visible)

`source add --fetch` now **requires** a recorded scope grant:

```
$ TRACEFIELD_ALLOW_NETWORK=1 tracefield source add <url> --case <c> --fetch
fetching is blocked: no active scope authorization for this case. Record the
collection grant with: tracefield case authorize <c> --scope "<collect scope
text>" --authorized-by "<name>" (see: tracefield case scope)   # exit 4
```

Existing workflows without `--fetch` are unchanged. The SSRF/self-test suite
was updated to grant first — the SSRF coverage itself is unchanged.

## 6. Document reconciliation (this phase)

- `RISK_REGISTER.md`: C3/R-C3-1 Fixed; A1/R-A1-5 Fixed; A4/R-A4-5 Fixed;
  C1/R-C1-2 partially (machinery shipped, author string open);
  C3/R-C3-5 Fixed (+stale description corrected); A3/R-A3-4 Accepted
  (decided, D22); C1/R-C1-5 wording de-drifted; Emerging table marked
  audit-time with pointer.
- `OOVS_MAPPING.md`: header (schema v2, report v3, re-verified 2026-10-27,
  321 tests); `-01` NOT_ASSESSED → **PASS (scoped)** with ledger/gate test
  evidence; `-09` mechanism documented, **verdict held FAIL** (author
  string + not-run acceptance tests; counts now 8 PASS / 1 FAIL /
  1 NOT_ASSESSED).
- `FINAL_BUILD_SPEC.md`: M1 correction (FS-18 landed via repo route),
  M2 substantially shipped (FS-19/FS-20 + FS-17 machinery; author string
  and FS-23 open), M3 partially advanced (first additive schema-v2 step;
  FS-24's remaining scope still open), §3 footnote, §8 decision list.
- `DECISIONS.md`: D20, D21, D22 appended.
- `CHANGELOG.md`: Phase 11 Added/Fixed entries.
- `README.md`: feature-matrix rows, network-gate wording, non-guarantee
  line de-staled (scope ledger now exists; it records authority, it does
  not grant it).
- `IMPLEMENTATION_STATUS.md`: Phase 11 update block with measured gates.

## 7. Explicitly NOT done in this phase (user-gated)

1. **FS-17 author identity string** — reports honestly print `author not
   set`; the register/correction/dissemination machinery is complete.
2. **OOVS-09 re-verdict** — held `FAIL` per mapping policy until (1) and a
   re-verification against the requirement's own tests.
3. **FS-26/FS-27 comparison URLs** (`WIX/Eagle` licence + git pin, "200+
   tools" repo) — P3, awaiting inputs.
4. **Publish timing** (v0.1.0 wheel) and OOVS publication timing.
5. FS-23 (licence fields for 2,257 `UNKNOWN` rows) and FS-24's remaining
   scope (`tool_fingerprint` digest binding; `catalog`/`providers` table
   wire-or-drop) — open, not user-gated.

## 8. Watched CI verification

| Workflow | Run | Commit | Result |
|---|---|---|---|
| CI (`test py3.11/3.12/3.13`, `lint`, `typecheck`, `dependency audit`) | `40531044503` | `7958fa3` | **success** — **321 passed** on all three pythons, 0 skipped (exiftool installed in CI) |
| CodeQL | `40531045015` | `7958fa3` | **success** |
| CI (`…`, incl. the verification-note commits) | `40531708504` | `8bbb279` | **success** |
| CodeQL | `40531708391` | `8bbb279` | **success** |

Policy unchanged from Phase 10: no "CI green" statement without a passing
Actions run for that exact commit. Every row above was watched to completion;
Actions history on `main` shows a green run for each pushed commit,
including the final note commit's own run (quoted in the Phase 11 closing
report).

## 9. Honesty notes

- The `catalog stale` listing does **not** imply any catalogue row was
  contacted or verified this phase — it is computed from shipped dates.
- The scope gate changed CLI behaviour; every existing `--fetch` test was
  updated to record a grant first rather than weakening the gate or the
  SSRF tests.
- The Phase 11 commits were pushed to `origin/main` after the local gates
  above; both Actions runs were watched to completion for the pushed commit
  (CI `40531044503`, CodeQL `40531045015` — see §8).
