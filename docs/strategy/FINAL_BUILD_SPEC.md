# TRACEFIELD — Final Build Specification

> Consolidated output of the post-build audit phase, 2026-10-19/20, on the
> clean 4-commit checkout at `e964409`. This document freezes **what exists,
> what is wrong, what happens next and in what order**. It is a specification,
> not an execution prompt: it authorises no build, no commits, no pushes, and
> no implementation in this phase. Sources and their dates are listed in §9;
> deliverables written this phase in §10.

## 1. Product state at freeze (evidence, not aspiration)

| Dimension | State |
|---|---|
| Repository | `main` @ `e964409`, 4 commits, clean; public GitHub with secret scanning, push protection, Dependabot, CodeQL; CI green |
| Gates | pytest **292 pass** (Phase 7), ruff clean, mypy strict clean (38 files), catalogue **2,264 valid**, pip-audit clean |
| Broken gate (audit G7) | **FIXED (Phase 7).** Fresh-venv wheel install now packages `data/catalog` inside the wheel (FS-01) and resolves it package-relative (FS-02); `tools status/search/show` + `catalog validate` all exit 0 in a clean venv (FS-03) |
| Healthy | case/evidence core, analytic engine, field tools, security posture (with 3 gaps), logging, CLI exit-code contract, HTML report |
| **Final release-gate re-run (Phase 9, 2026-10-23)** | **G1–G11 local gates green** — pytest 292, ruff check clean, ruff format 60 files clean, mypy strict clean (38 files), catalogue 2,264 valid, pip-audit no advisories, **fresh-venv wheel install** catalogue commands exit 0, 0 network-marked tests, OCR UNAVAILABLE-path covered, git clean-before-commit. **Correction (Phase 10, 2026-10-25):** the "CI-green" item in this row was wrong for the pushed commit `99bf23c` — GitHub Actions run 39967712054 failed all three Python test jobs (one test broken by typer's CI-forced-terminal help rendering; 3 backend-gated tests skipped). CI was repaired and re-gated in Phase 10; see the in-repo report `PHASE_10_CI_REPAIR_AND_RELEASE_TRIAGE.md` — the Phase 9 evidence file `PHASE_09_REPORT_FINAL_ACCEPTANCE.md` is a local working note, not part of this repository |
| Not healthy (audit-time) | TUI truthfulness + doc drift + packaging G7 — **all FIXED in Phases 6–7**: keymap/parity, real back-stack, active-case model + picker, per-hop pinning, backend allowlist, newer-schema refusal, FS-15 fault-tolerance suite |
| Not assessed | Official OOVS acceptance tests; live-network tests (zero exist by design); OCR backend (tesseract absent on this host) |

## 2. Priority model

- **P0 — honesty & artifact correctness.** Must be done before *any*
  release artifact is published or *any* release claim is made. A shipped
  wheel/TUI/doc that misstates its own behaviour violates the product thesis.
- **P1 — robustness & completeness.** Before v0.1.1: failure modes,
  cancellation, case workflow completeness, security hardening residuals.
- **P2 — craft & defensibility.** Before an OOVS-reassessment attempt or
  wider publication: theming, report dissemination fields, catalogue health,
  performance triggers.
- **P3 — research & expansion.** Needs external input or schema v2; never
  blocks the above.

## 3. Requirements (FS-IDs, each traceable to audit evidence)

| ID | Requirement (condensed) | Trace | Pri |
|---|---|---|---|
| FS-01 | Catalogue `data/` ships **inside** the wheel; wheel target includes it | G7, D15 | P0 |
| FS-02 | Catalogue path resolves package-relative (fallback to repo-relative); absent data → exit 2, explicit message | G7, `cli/main.py:1186` | P0 |
| FS-03 | Fresh-venv install: `tools status/search/show`, `catalog validate` all exit 0 | G7 | P0 |
| FS-04 | TUI keymap parity: docstring/footer/help advertise **only** bound keys; Tab/Enter documented iff the workspace has multi-pane/rows | T4, TS-2 | P0 |
| FS-05 | `/` filters the current list with match counts; `g` opens a real jump palette; `Esc` pops a back-stack (never forced jump) | T2/T3/T5, §3 spec | P0 |
| FS-06 | Active-case model: all case-scoped views render one case only; `c` picker; status always shows `case: <id>` | T6, TS-1 | P0 |
| FS-07 | Truthful labelling: "synthetic/demo" marker only under demo fixtures; status line never contradicts visible content | T1/T7, TS-4 | P0 |
| FS-08 | Document corrections land (status git-state, OOVS 207, debt #4/#5, risk re-opens) | audit §8, done this phase | P0 |
| FS-09 | All existing gates stay green in CI and locally; fresh-venv gate added to CI-equivalent checklist | G1–G7 | P0 |
| FS-10 | Help = overlay that restores exact prior state; `?`/`Esc` close | T1, J1 | P1 |
| FS-11 | Progress & cancellation: real-count milestones, cooperative `Ctrl+C`, `cancelled` states recorded in Runs + audit log; export interruption leaves intact prior bundle | T8, TS-3, J5 | P1 |
| FS-12 | `--fetch` redirects handled manually: per-hop `validate_host` + IP pinning + Host/SNI; unpinnable hop fails closed (exit 4) | F1, D16 | P1 |
| FS-13 | `run_backend` enforces literal allowlist (`exiftool`, `ffprobe`, `tesseract`); docstring and code agree | F2, D17 | P1 |
| FS-14 | `migrate()` refuses `db_version > SCHEMA_VERSION` with a clear message and exit 5 | F3, D17 | P1 |
| FS-15 | Fault-tolerance tests: SQLite busy/corrupt/newer-schema, write-permission loss, export interruption, cancellation | audit §6 | P1 |
| FS-16 | TUI journey tests J1–J5 + keymap-parity test (stateful, 2-case seeded workspace) | TS-6/TS-7 | P1 |
| FS-17 | Report gains author identity, revision, supersession/corrections block → basis for re-mapping OOVS-09 | F5, C1/R-C1-2 | P1* |
| FS-18 | User-Agent carries a real contact URL | debt #9 | P1 |
| FS-19 | DB-level FK enforcement on relation endpoints (or documented single-choice) | A1/R-A1-5 | P2 |
| FS-20 | Catalogue health-check job wired to `last_checked` **or** schema columns dropped before v2 | A3/R-A3-4, D7 | P2 |
| FS-21 | Semantic theme tokens (light/dark), `NO_COLOR` degrades to text-only states | TS-5 | P2 |
| FS-22 | Render-path performance triggers worker offload (≤50 ms rule) with recorded baseline | TS-7, A2/R-A2-3 | P2 |
| FS-23 | Licence fields filled for the `cli_tool` catalogue tier (2,257 `UNKNOWN` overall; tier-first) | tools status counts | P2 |
| FS-24 | Schema v2: bind `tool_fingerprint` in digests; wire-or-drop `catalog`/`providers` tables | F4, D7 | P3 |
| FS-25 | Perceptual hashing for image duplicates | debt #7 | P3 |
| FS-26 | WIX/Eagle comparison inputs (git pin; license file) once unblocked | audit §7 | P3 |
| FS-27 | "200+ OSINT tools" repo comparison once the user supplies the URL | register open question | P3 |

\* FS-17 needed a user-supplied author identity before it could complete (§8).
**RESOLVED (Phase 12, 2026-10-29):** the maintainer supplied the identity and
confirmed its use on reports; FS-17 is complete. The FS-11…FS-17 machinery:
report identity register + corrections + recipient register (Phase 11) and
the operator-config-file author mechanism (Phase 12) both shipped and are
test-pinned; the maintainer's environment carries the confirmed string while
other installs keep the honest `author not set` fallback (D23).

## 4. Milestones

| Milestone | Contains | Exit gate (all must pass) | Status (2026-10-23) |
|---|---|---|---|
| **M0 — Honest artifact** | FS-01…FS-09 | G1–G7 all green **including fresh-venv wheel install**; TUI probe rerun shows zero docstring/bindings drift; docs contain no stale claims (audit §8 list empty) | **GREEN** — pytest 292/ruff/mypy clean; G7 fixed + fresh-venv catalogue commands exit 0; TUI keymap-parity + drift fixes landed; §8 doc corrections landed (Phases 6–8) |
| **M1 — Complete & cancellable** | FS-10…FS-16, FS-18 | J1–J5 journeys green; fault-tolerance suite green; redirect-pinning test against a local two-hop server green; migrate-refusal test green; all prior gates | **GREEN** — J1–J5 + FS-15 suite + redirect re-pin + migrate-refusal all green (Phases 6–7). **Correction (Phase 11, 2026-10-27):** FS-18 landed — the `username.py` User-Agent now carries the project's own contact route (`+https://github.com/killerdasher/TRACEFIELD`, matching `fetch.py`); no user input was required (the repo URL is the project's canonical address); a different contact route remains a one-line swap if the user prefers |
| **M2 — Defensible dissemination** | FS-17, FS-19…FS-23 | Report renders author/revision/corrections (fixture test); OOVS mapping updated with `-09` re-verdict; theme/NO_COLOR tests; catalogue health or D7 drop decided | **SHIPPED except FS-23 (2026-10-29)** — FS-19 done (Phase 11, DB integrity triggers); FS-20 decided + shipped (`catalog stale`, D22); **FS-17 DONE (Phase 12, 2026-10-29)** — author identity + register + corrections + recipient register all test-pinned, and **OOVS-09 re-verdicted `PASS (scoped)`** in the mapping (promotion policy satisfied: mechanism + configured author + regression-pinning tests); FS-21/FS-22 landed (Phase 6); **only FS-23 (catalogue licence fields, tier-first) remains open in this milestone** |
| **M3 — Expansion** | FS-24…FS-27 | schema v2 migration + chain-compat note; pHash fixture test; comparison rows appended to `COMPETITOR_MATRIX.md` with dated sources | **OPEN, partially advanced (Phase 11, 2026-10-27)** — a first additive schema-v2 step landed (report-identity/correction/dissemination registers + DB integrity triggers, additive-only migration from v1 with idempotent + data-survival tests); FS-24's remaining scope (**bind `tool_fingerprint` in digests; wire-or-drop the existing `catalog`/`providers` tables**) is still open; FS-25 pHash, FS-26/FS-27 comparison inputs still open (FS-26/27 user-gated) |

Sequencing rule: no milestone opens until the previous one's exit gate is
green. M0 is the only milestone on the path to any published artifact.

## 5. Test-suite additions required (roll-up)

1. TUI: keymap-parity (FS-04), case-scoping invariant (FS-06), overlay
   restore (FS-10), cancel semantics (FS-11), J1–J5 (FS-16).
2. Storage: busy/locked DB, corrupt header, read-only data dir, newer-schema
   refusal (FS-14/FS-15).
3. Packaging: automated fresh-venv install smoke exercising FS-03 (scripted,
   runs in release checklist).
4. Network edge: localhost-only redirect chain proving per-hop pinning and
   block-on-unpinnable (FS-12); no third-party probing (unchanged rule).
5. Export: simulated interruption leaves prior bundle + `failed` event
   (FS-11/FS-15).

Zero network-marked tests remain the default; localhost servers count as
integration, not `network`.

## 6. Release-gate checklist (the standing definition of "green")

`pytest` (all markers intended for CI) · `ruff check` · `ruff format --check`
· `mypy src` · `catalog validate` (2,264+ valid) · `pip-audit --strict`
(filtered) · **fresh-venv wheel install smoke** · CI green on the release
commit · demo session re-recorded if UI-visible behaviour changed ·
`RESEARCH_REGISTER.md` dates re-checked for any figure quoted in release
notes. Anything not run is reported as `NOT_RUN`, never omitted.

## 7. Standing product boundaries (carry into every future prompt)

Textual stays; CLI remains the primary, scriptable surface; network doubly
opt-in with per-request SSRF policy; **no CAPTCHA/anti-bot evasion, ever**
(D17); no feature is TUI-only; no star-count comparisons; catalogue claims
stay tiered and dated; "hashes prove bytes, not truth" stays in outputs;
PROV stays conceptual, no STIX/TAXII/CASE-UCO (D14); OOVS mapping remains a
self-assessment until official tests are run.

## 8. Open decisions requiring the user

1. **URL of the "200+ OSINT tools" GitHub repository** (P3 input; not guessed).
2. **Report author identity string** — **RESOLVED (2026-10-29)**: the
   maintainer supplied and confirmed `killerdasher —
   github.com/killerdasher/TRACEFIELD`, persisted per-operator in
   `~/.config/tracefield/config.toml` (env var overrides; no tool-level
   default so other operators' reports stay honestly unattributed, D23).
   FS-17 completed; OOVS-09 re-verdicted `PASS (scoped)`.
3. **User-Agent contact route** — **satisfied in Phase 11 by the project's own
   repo URL** (`github.com/killerdasher/TRACEFIELD`); if a distinct contact
   address (email/domain) is ever preferred, swapping it is a one-line change.
4. **Eagle licence** (no LICENSE file) and **WIX git history** (not a repo) —
   unblock FS-26; also confirm whether either should be probed at all.
5. **Publish timing**: whether M0's fixed wheel is published as v0.1.0 or
   held — decision made only after M0's exit gate is green (not this phase).
6. **OOVS publication timing** — mapping must re-verify upstream version
   immediately before any publication that cites it.

## 9. Research used this phase (dates in `RESEARCH_REGISTER.md`)

- Bellingcat practitioner survey, 2022-08-12 (fetched 2026-10-19): 525
  respondents, >83% tool-discovery difficulty, ~24% regular GitHub-tool use,
  verification as top challenge — supports honesty-first positioning.
- Sherlock (github.com/sherlock-project/Sherlock, fetched 2026-10-19):
  ~94k stars, MIT, v0.16.2 (2026-09-08), active; broken distro packages noted.
- Maigret (github.com/soxoj/maigret, fetched 2026-10-19): 39,220 stars, MIT,
  v0.6.6 (2026-09-18), 5,203 enabled sites; CAPTCHA/Cloudflare-bypass features
  recorded as **out of scope for TRACEFIELD** (D17).
- SpiderFoot (github.com/smicallef/spiderfoot, fetched 2026-10-19): 23,615
  stars, MIT, maintenance contested (issue #1911), active forks exist —
  refreshes the matrix's maintenance column.
- Prior-session sources (2026-10-16) unchanged: GitHub API metadata for
  theHarvester/holehe/OSINT Framework/Awesome OSINT/WhatsMyName/Bellingcat
  toolkit, licence texts, W3C PROV-DM, SQLite, Textual testing docs, NO_COLOR.

## 10. Deliverables written this phase

| File | Content |
|---|---|
| `docs/strategy/POST_BUILD_AUDIT.md` | Inspection method, current-state matrix, TUI evidence (T1–T10), release-gate matrix (G1–G11), security findings (F1–F6), fault-tolerance inventory, local-tool search verdicts, doc-inconsistency list |
| `docs/strategy/TUI_INTERACTION_SPEC.md` | Principles, workspace/active-case model, interaction grammar, progress/cancel model, honest-status rules, theming, journeys J1–J5, stateful/performance requirements (TS-1…TS-7) |
| `docs/strategy/RESEARCH_REGISTER.md` | Practitioner-evidence section + 2026-10-19 competitor refresh + unresolved "200+ tools" question |
| `docs/strategy/COMPETITOR_MATRIX.md` | Sherlock/Maigret/SpiderFoot rows refreshed (dated), evasion-feature boundary noted |
| `docs/strategy/IMPLEMENTATION_STATUS.md` | Corrections: git state, gates incl. wheel FAIL, debt #4/#5, new debts 10–13 |
| `docs/oovs/OOVS_MAPPING.md` | Test count 203 → 207 with re-verification date |
| `docs/strategy/RISK_REGISTER.md` | A2/R-A2-1 re-opened, A2/R-A2-2 re-opened, A1/R-A1-4 → Open P0, C1/R-C1-5 corrected, 7 new audit risks |
| `docs/strategy/DECISIONS.md` | D15 (packaging), D16 (per-hop pinning), D17 (no-evasion boundary + allowlist + migrate refusal) |
| **`docs/strategy/FINAL_BUILD_SPEC.md`** | This document |

## 11. Explicit non-goals of this phase (as executed)

No product code changed; no commits/pushes/tags; no release published; no
new UI framework; no planner/plugin work; no build-execution prompt; no
live third-party probing; no OOVS certification claim; no fabricated test or
gate results.
