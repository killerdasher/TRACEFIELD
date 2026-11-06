# TRACEFIELD — Strategic Foresight & Evolution Architecture (canonical)

> **Canonical long-term strategy.** 2026-11-06. Prepared by the loop-engine
> workflow (`--mode deep --max-iterations 3`) on a clean checkout of `main` @
> `dbdbfd6` (tree clean except this session's own strategy documents — see §0).
>
> **Document hierarchy (single source of truth for its horizon).** This is THE
> canonical product/long-term strategy document. Subordinate, non-duplicating
> companions:
> - `docs/strategy/TRACEFIELD_02_PRODUCT_DIRECTION.md` — the 0.2 release plan
>   (scope IS-1…IS-6, non-goals NG-1…NG-10, verification log §14). Not
>   superseded; re-anchored to this document; erratum applied (below).
> - `docs/strategy/DECISIONS.md` — decision log with alternatives (D1–D23).
> - `docs/strategy/FINAL_BUILD_SPEC.md` — build spec + release-gate checklist
>   §6 and standing boundaries §7.
> - `docs/strategy/COMPETITOR_MATRIX.md` + `RESEARCH_REGISTER.md` — dated
>   external facts; this document never re-quotes them wholesale.
> - `docs/strategy/RISK_REGISTER.md` — risk statuses carried as its own record.
> This document ADDs new evidence and decisions; where it restates a prior
> decision it cites the decision ID, not the text.
>
> **Erratum 2026-11-06 (applied to the companion 0.2 doc).** The 0.2 doc said
> Sherlock's first import format is `--json`. A live fetch of the Sherlock
> README on 2026-11-06 shows `--json` is an **input** flag ("Load data from a
> JSON file"); the *output* options are `--csv`, `--xlsx`, `--txt` (plus the
> default per-username text file). B-01 therefore re-targets: verify a real
> version-pinned **`--csv`** output sample first (`--txt` fallback; `--xlsx`
> avoided). A dated erratum note was added to the companion document.
>
> **Method.** Evidence labels used exactly as defined: VERIFIED /
> IMPLEMENTED BUT NOT VERIFIED / EXPERIMENTAL / PLANNED / NOT PRESENT /
> SUSPECTED / BLOCKED. Session battery (2026-11-06, this session): full test
> suite, lint/type, catalogue, stale-listing, live demo re-run, CI state,
> anchor re-checks (§2.1). External research was done by direct primary-source
> fetches; the search-engine integration returned HTTP 402 that day, so the
> *breadth* of the ecosystem scan is BLOCKED and that limitation is recorded
> (§5, §22) — dated primary web sources + the project's own dated register
> carry the load instead.

---

## Contents

1. Executive strategic decision · 2. Evidence-based current state · 3. Product
identity and North Star · 4. Target users and workflows · 5. OSINT landscape &
competitors · 6. Differentiation thesis & falsification · 7. Nine research-cell
findings and disagreements · 8. Foresight scenarios · 9. Architecture
assessment · 10. Target architecture & evolution principles · 11. Security,
privacy, reliability · 12. Analyst experience & interface · 13. Controlled
self-evolution model · 14. Strategic pillars · 15. Anti-roadmap · 16.
Prioritized roadmap · 17. Risks, assumptions, unresolved questions · 18.
Measurable acceptance criteria · 19. Solo-maintainer R&D operating model · 20.
External specialist review brief · 21. The single next implementation task ·
22. Source register.

---

## §1. Executive strategic decision

**Decision.** TRACEFIELD evolves along the direction set in the companion 0.2
document (Direction B — the evidence-centric investigation and provenance
workbench — with interoperability absorbed as an ingestion layer) and, over
the long term, deliberately becomes the **analyst-judgment and integrity layer
between the collectors the analyst already uses and the report the analyst
must defend**. It does NOT become: a collector, a browse-time capture tool, a
team/collaboration cloud, a leak corpus platform, or an autonomous agent.

**What changes versus the 0.2 doc's framing, forced by fresh evidence.**
Two primary-source fetches (2026-11-06) narrow the differentiation claims and
upgrade the roadmap:

1. **Hunchly** (commercial, Maltego Technologies) already owns
   *browse-time capture with hashes and an audit trail*, on local storage — so
   "we hash evidence" must never be marketed as novel. TRACEFIELD's field
   remains: tool-output ingestion, analyst-judgment structure
   (review-gated independence/contradictions), deterministic assessment, and
   correction continuity — none of which its fetched descriptions claim.
2. **Atlos** (open-source, self-hostable) owns *collaborative investigation
   tracking with built-in archival* — and its own FAQ disclaims "suitable for
   legal or forensic evidence". TRACEFIELD stays single-operator local-first;
   no team/server mode (anti-roadmap AR-8).
3. **Sherlock's output reality** (above erratum) confirms the B-01
   format-verification gate is not bureaucracy: upstream CLI contract reading
   from memory/wildest assumption already produced one wrong format plan.

**North-horizon posture (6/12/24 months).** Short term: land the 0.2 slice so
the wedge ("external tool output in") exists at all. Medium: close the
analyst-workflow gaps that cost real time (search, timeline, licence honesty
in the catalogue). Long: conditional bridges only on demonstrated demand
(read-only C2PA manifest reading via a future adapter; PROV-JSON mapping only
if a recipient asks). Every long-term item is reversible and evidence-gated
(§16).

---

## §2. Evidence-based current state (this session, 2026-11-06)

### 2.1 Fresh verification battery (all run in this session)

| Check | Command (abbrev.) | Result | Status |
|---|---|---|---|
| Test suite | `pytest -m "not network"` | **332 tests, full dots, rc=0**, 0 skipped ⇒ the integrated exiftool E2E ran; suite = 284 `def test` occurrences → 332 collected items (parametrization) | VERIFIED |
| Lint / format | `ruff check src tests` / `ruff format --check` | "All checks passed!" / "61 files already formatted" | VERIFIED |
| Types | `mypy src` (strict) | "Success: no issues found in 38 source files" | VERIFIED |
| Catalogue | `catalog validate` / `tools status` | 2,264 valid; tiered 2,254 indexed / 10 verified / **0 integrated**; licences: UNKNOWN 2,257 | VERIFIED |
| Freshness honesty | `catalog stale` | prints "stale listing is not a health verdict; verification is operator-manual (never contacts upstream)" | VERIFIED |
| Flagship workflow | `bash docs/demo/run_synthetic_demo.sh` (fresh workdir) | **rc=0**, stages 0–12 (doctor prelude + 12 numbered steps), "manifest verified — all digests match", tamper step present (expected failure) — re-run after battery's demo step hit MY scripting bug (`$$PWD` env mangling → rc 127; product untouched; stray log cleaned from repo root, tree re-verified clean) | VERIFIED |
| CI / CodeQL | `gh run list --limit 5` | CI `40860607568` + CodeQL `40860607746` success on HEAD `dbdbfd6` (2026-10-29); scheduled CodeQL `41457478434` (2026-11-02); Dependabot success (2026-11-02). Lineage note (added 2026-11-06): the HEAD commit *message*'s recorded runs (`40860162983/40860162798`) belong to the previous commit's push (CI `40860162983` visible in the same list, 2026-10-29T10:46Z) — no contradiction | VERIFIED |
| Solution anchors | `sed`/`grep` probes | `ReviewState` @ `domain.py:42`; `verify_manifest` @ `export.py:208`; exit codes 0/1/2/3/4/5 @ `cli/main.py:63-68`; `SCHEMA_VERSION=2` tripwire @ `database.py:20` | VERIFIED |
| Code size | `wc -l` (fresh) | `src/tracefield` 10,326 lines; `cli/main.py` 2,423; `tui/app.py` 674 + `tui/views.py` 707; `domain.py` 285 (13 typed records); `adapters.py` 354 | VERIFIED |
| Runtime deps | `pyproject.toml` | exactly 6: `typer, click, rich, textual, pydantic, httpx` (pinned ranges) | VERIFIED |

**BLOCKED in this session:** a *broad* current-market scan (search API
HTTP 402, 2026-11-06). Mitigation: five direct primary-source fetches
(§22) + all dated internal-register facts. No freshness claim is made beyond
those fetches' access dates.

### 2.2 Capability classification (labels per Part IX)

| Capability | Label | Anchor |
|---|---|---|
| Case lifecycle, scope ledger, evidence (SHA-256, 0o400, streamed), event chain, evidence verify | VERIFIED (suite + live demo) | `cli/main.py:353/389/456`; D20; `test_scope_ledger` |
| Origin clustering (origin-r3, ordered k=3/4/5 containment, Unicode-safe) | VERIFIED | `core/origins.py`; D3; analytical fixture tests |
| Contradiction candidates (dates/digests/quantities, always `candidate`) | VERIFIED | `core/contradictions.py` |
| Deterministic assessment `assess-r2`; reproducibility double-check | VERIFIED (live demo; pin test exists) | `core/analysis.py:19`; `tests/e2e/test_demo_case.py:378` |
| Analyst review gates (unreviewed output ≠ evidence) | VERIFIED | `ReviewState` `domain.py:42`; D4 table |
| Report identity / corrections / dissemination register / author identity | VERIFIED (suite; author identity live in demo) | D21/D23; `TestReportRegister` `test_cli.py:398`; `report-correct` `main.py:2010`, `report-history` `main.py:2051` |
| Export redact-then-manifest; case-verify; tamper detection | VERIFIED (live) | `export.py:208`; `case-verify` `main.py:2148` |
| Adapter boundary D19: one integrated adapter (exiftool, E2E), 2 spec-only | VERIFIED (integrated path ran, 0 skips) | `adapters.py:152/168/192`; `run_backend` allowlist `inspect.py:160` |
| Scope-gated fetch; per-hop re-pinned redirects; SSRF deny list | VERIFIED (security suite green today) | `fetch.py:74-120`; `tests/security/test_security.py:90` |
| Username checks (curated, soft-404 rules, 1 req/s, env-gated) | VERIFIED fixtures / IMPLEMENTED BUT NOT VERIFIED against live class of providers (network-marked tests never run) | `fieldtools/username.py` |
| TUI (6 workspaces, truthful keymap parity, filters, cancel, themes) | VERIFIED (28 journey tests in today's suite) | `tui/app.py`; `tests/tui/test_journeys.py` |
| Planner (proposal-only, deterministic) | VERIFIED (advisory by design — proposal-only; 9 capabilities; determinism test-pinned per D18) | `planner.py` |
| ffprobe/tesseract adapters | EXPERIMENTAL | `integration_state = spec-only` (D19) |
| **Case-data import of external tool output** | **NOT PRESENT** | no ingest path; `registry/importers.py` is catalogue-only |
| Cross-record case search; timeline view | NOT PRESENT | no command/view exists |
| Fault-tolerance handling (corrupt/truncated DB, locks, read-only, interrupted export) | VERIFIED (8 named tests in today's suite) | `tests/integration/test_fault_tolerance.py:73-182` |
| Perceptual hashing (image duplicates) | PLANNED (FS-25) — catalogue records the gap honestly | `RISK_REGISTER` C4/R-C4-3 Open |
| Retention/erasure workflow | IMPLEMENTED for the field (`Case.retention_policy` @ `domain.py`; no command/tests — full workflow PLANNED) | — |
| Cross-platform behaviour (macOS/Windows) | IMPLEMENTED BUT NOT VERIFIED — CI matrix is 3×Python on **ubuntu only** (`.github/workflows/ci.yml:44`); `0o400`/`0700` semantics on Windows are SUSPECTED to degrade to best-effort | — |
| Unwired `catalog`/`providers` SQLite tables | CONFIRMED DEBT (tables exist @ `database.py:153/192`; zero usage found in `repositories.py` 2026-11-06) with SUSPECTED impact only (no runtime cost measured) | D7 said "wire or drop before schema v2" — the deadline passed; carried into v2 |
| E2E reproducibility flake | SUSPECTED (1 failure @ `test_demo_case.py:378` observed 2026-11-06, unreproduced in 8 further runs; root cause unproven) | Companion doc §14 V3 |
| Broad market adoption of the product | SUSPECTED — untested assumption; no demand data beyond the dated 2022 survey | §4 |

---

## §3. Product identity and North Star

**Identity (one sentence).** TRACEFIELD is a local-first, terminal-first OSINT
workbench that turns an investigator's collected artifacts, tool outputs, and
manual findings into hash-bound, review-gated, correction-carrying evidence —
and exports bundles whose integrity anyone can re-verify without TRACEFIELD.

**Core problem it solves.** After collection, everything the analyst produced
scatters across terminal scrolls, screenshots, and tab-copies with no shared
integrity or judgment structure; conclusions then rest on unevidenced
confidence. TRACEFIELD gives that forgotten middle — between collection and
the report — an integrity contract, a review discipline, and a correction
trail.

**What it deliberately does NOT solve** (each with its owner, from §5):
online collection breadth (Sherlock/Maigret/SpiderFoot); browse-time capture
(Hunchly); team-scale collaboration and shared tracking (Atlos); leak/document
corpora at organizational scale (Aleph); metadata depth (ExifTool); evasion
(truthful refusal, D17); autonomous judgment (its own rules); probability
scores of truth (its own rules).

**North Star.** *"External tool output in → independently verifiable
intelligence out, in one sitting."* Practical, measurable demonstrations:

1. **Pass-through proof:** every release's synthetic demo (or a real-case
   equivalent) must complete the full path — ingest → triage → review →
   assessment → report — and end with `manifest verified` (today: VERIFIED
   sans ingest; ingest is the 0.2 addition).
2. **Stranger-verifiability:** a third party re-checks an export with plain
   `sha256sum` against `manifest.json` and gets byte-equality for every file
   (live-verified format today: per-file `files[].sha256` +
   `evidence/<storage_ref>` paths), and a deliberate tamper flips the verdict
   (demo step 12, exit 1).
3. **Correction survival:** any correction made after a report shipped appears
   in all subsequent renders of that lineage (D21); nobody can silently
   rewrite a distributed conclusion.

These three are the product's definition of "working"; everything in §14–§16
must advance at least one of them.

---

## §4. Target users and their real workflows

### 4.1 Segments and the evidence for caring about them

| Segment | Work they try to do | Where it fails today | Fit with TRACEFIELD |
|---|---|---|---|
| S1 — Individual OSINT researchers / independent investigators | Run Sherlock/Maigret/Nuclei-type sweeps, triage results, keep receipts, compose defensible writeups | Results land as TXT/CSV files and terminal scroll; no integrity, no review structure, correction means retyping everything | **Primary.** Local-first + terminal match their habits; the 0.2 ingest wedge speaks their exact pain |
| S2 — Verification-minded journalists / fact-checkers | Verify claims with evidence trails a reader/editor can audit; publish, then correct responsibly when facts change | Corrections across renditions; recipients holding stale versions; "how do I prove the trail" | **Primary.** Corrections/dissemination register + stranger-verifiable export are aimed exactly here |
| S3 — Digital investigators / DFIR practitioners | Hash-bound exhibits, tool-output provenance, court-grade care | Require more formal chain-of-custody than any FOSS here yet offers; Hunchly targets this commercially | Secondary. U-4 style export is honest about not being a legal-grade product; do not court-certify |
| S4 — Corporate risk / due-diligence analysts | Tool-supported checks on entities, with auditable method | Same scatter pain; often buy tools (Peeler-type, Kyubi-type) — no demand data for a FOSS CLI | Secondary; same unproven-adoption assumption as S3 (SUSPECTED) |
| S5 — Academics / trainers | Teach method with reproducible synthetic cases | Need no-real-data setups; honesty as curriculum value | Secondary; the synthetic demo doubles as teaching material |

Evidence basis: practitioner pains (finding tools difficult >83%, scattered
formats, volume overload, 49/525 naming verification as the biggest
challenge) — Bellingcat 2022 survey `[V]`, fetched 2026-10-19 (2022
self-reported data — dated, not current market size). The *existence of
paying substitutes* (Hunchly across law-enforcement/journalism/PI/HR verticals
`[V 2026-11-06]`; Atlos serving large team investigations `[V 2026-11-06]`)
shows the workflow's value is real, and shows who is already serving whom —
which is exactly TRACEFIELD's whitespace argument in §5.

### 4.2 The strongest initial segment, and the honest gap in the reasoning

**S1+S2 veterans who are terminal-comfortable and solo/small.** Why them:
(a) their pain is the documented scatter/verification problem; (b) Hunchly
(Audience: professionals, commercial, browser-centric) and Atlos
(teams/large-scale) do not target the solo CLI operator; (c) they already
produce the artifacts 0.2 ingests.

**The untested assumption, named:** their *willingness* to install and keep a
FOSS pipeline in this exact shape is SUSPECTED — no survey of THIS product
exists. Falsifiable smallest experiment: distribute the live verified demo +
review brief (§20) to a pool of 2–5 practitioners (≥3 sent in week 1,
H0-5); adoption signal = one real workflow
attempt with feedback, not a like. No fake pipeline expectations before that
signal lands.

### 4.3 What makes them distrust — and what TRACEFIELD already does about it

Distrust triggers (survey + project's own rules): marketing counts, unverifiable
health claims, black-box scoring, silent rewriting, evasion features. The
product's structural answers already VERIFIED: tiered catalogue counts, refusal
to claim health, no percentages, append-only corrections, never-empty caveats,
honest `author not set`. §14 Pillars protect exactly these.

---

## §5. OSINT landscape and competitor analysis (as of the access dates)

### 5.1 Substitutes by layer, with dates and what they establish

| Layer | Player / evidence | What their fetched material establishes | Consequence for TRACEFIELD |
|---|---|---|---|
| Collection — usernames | **Sherlock** — GH page fetched 2026-11-06: **97.7k stars**, MIT, v0.16.x, `--csv/--xlsx/--txt/--dump-response` outputs, `--ignore-exclusions` FP warning | Username hunting is commoditized and enormous; output contract exists but is *documented text/CSV, not JSON* | Never compete; ingest instead. B-01 format = CSV |
| Collection — usernames/dossiers | **Maigret** 39,220★, v0.6.6 `[V 2026-10-19]`; 5,203 enabled sites; **bypass features out of scope (D17)**; optional `--ai` external API | Dossier value; the ecosystem is dabbling in AI | Second ingest target; ignore never-use bypass fields |
| Collection — automation | **SpiderFoot** 23,615★ `[V 2026-10-19]`, upstream push 2026-04-13, maintenance contested (issue #1911), active forks (health `[U]`) | Automation breadth exists; maintenance-risk lesson for anything with many moving parts | Postpone beyond 0.2; keep catalogue row factual |
| Capture — browse-time | **Hunchly** (`hunch.ly`, fetched 2026-11-06): auto URL+timestamp+**hashes**, full-page captures, tags/search, "court-ready packages", audit trail; local-storage option; Maltego Technologies ©2026; used in 84 countries | The capture+hash+audit layer for browsing is **solved commercially** and professionally respected (Bellingcat founder quote on their page) | AR-1: never build browse capture. Differentiate on judgment layer; state this in docs |
| Team workflow / tracking / archival | **Atlos** (atlos.org, fetched 2026-11-06): open source + self-hostable; tracks **every change**; built-in archival (photos/videos/webpages); safety features; private-by-default workspaces; CSV import/export; project API; FAQ: archival **"not suitable for legal or forensic evidence"**; independent audit summer 2023 | The collaborative tracking+archive space for large investigations is taken; team features are server-shaped | AR-8: no team/server mode. The single-operator local-first lane stays open |
| Corpora / entity relationships | **Aleph** (docs.alephdata.org, fetched 2026-11-06): OCCRP platform; secure leak uploads; OCR-searchable; network diagrams; timelines; hundreds of datasets for name comparison | Big-org data-platform needs are served | Not a lane for a single-op tool; possible future *recipient* of exports (API import as conditional H3) |
| Harvester UIs | theHarvester + HarvestView review UI, GPL-2.0 `[V 2026-10-16]`; holehe GPL-3.0, quiet >2 yrs | Even collectors are adding kept-history UIs — the direction (capture→review) is real; their licensing shapes bundling rules (D7 licence hazards) | Catalogue rows only; no bundling of GPL without process |
| Metadata | **ExifTool** `[V 2026-10-16]` (the one integrated adapter) | Depth of metadata reading is owned upstream | Keep as the execute-path reference; do not grow its scope |
| Tool discovery | Bellingcat toolkit (337 pages, no repo-root licence), Awesome OSINT (CC BY-SA 4.0), OSINT Framework (MIT) `[V 2026-10-16]` | Human-curated breadth is owned by them | TRACEFIELD wins on *machine-checkable tiers*, not breadth (B1/R2 position, kept) |
| Provenance standards | **C2PA** spec 2.3; steering (11 members on the fetched page): Adobe, Amazon, BBC, Google, Meta, Microsoft, **OpenAI**, Publicis, Sony, TikTok, Truepic; page updated 2026-01-08 (fetched 2026-11-06) | Content-provenance standardization is a serious industry effort aimed at content authenticity, not investigation-case integrity | Read-only C2PA manifest *reading* is a conditional H3 adapter candidate — never a fork of their brand or messenger problems; our own exported-case manifest remains independent |

### 5.2 Commoditized, strong, fragmented

- **Already commoditized** (never re-sell as features): username enumeration;
  page hashing at capture; metadata reading; OCR wrapping; link lists; SQLite
  storage; JSON output; redaction of secrets (`COMPETITOR_MATRIX.md` "NOT
  novel" list, reinforced by today's fetches).
- **Strong elsewhere:** collection breadth; cluster-scale archival; team UX;
  court-package assembly (commercial).
- **Still fragmented (the tracked whitespace):** a cross-tool
  *verification + judgment* layer for the solo operator that (i) imports
  heterogeneous tool outputs with provenance, (ii) structures
  independence/contradiction reasoning, (iii) carries corrections with the
  lineage, (iv) verifies integrity without the tool itself. No fetched
  substitute claims all four; most fetched substitutes claim none of them.
  Basis note (added by the iteration-2 review): these are single-page checks
  per player (§22) plus dated internal registers — a market-wide absence
  claim is NOT made; before building anything beyond 0.2, the §8.2 triggers
  re-check *capability*, not copy.

### 5.3 BLOCKED / limits of this research pass

Breadth scans (fresh surveys, "OSINT trends 2026" articles, adoption stats)
were BLOCKED (search integration HTTP 402, 2026-11-06). Claims in this §5 are
staked ONLY on the five dated primary fetches and dated internal registers.
No adoption/steady-growth figures are asserted anywhere in this document.

---

## §6. Differentiation thesis and falsification

### 6.1 Candidate-by-candidate existence check

| Differentiator candidate | Exists elsewhere? (checked sources, §5) | TRACEFIELD's actual difference | Would analysts feel it? | Reproducible by a competitor? |
|---|---|---|---|---|
| Evidence *hashing* | **Yes** — Hunchly hashes every captured page; Atlos tracks every change | Tool-output-centric, offline, content-addressed copies + chain + export manifest | The raw hash is table stakes; packing it *for tool outputs* not held by them | Trivially copied (do not market it) |
| Case export verifiable **without the tool** | Not found in fetched docs of substitutes (Hunchly audit trail promotes reading *inside* Hunchly; Atlos disclaims forensic-grade) | `manifest.json` + plain `sha256sum` path, redact-then-manifest, SENSITIVE_METADATA keys-not-values, SENSITIVE redaction never rewrites originals | Yes — the export is a *verification contract*, today VERIFIED live (tamper exit 1) | Requires adopting the whole contract; medium |
| Independence/contradiction structure with review gates | Not found in fetched substitutes (Aleph shows relationships viz; Atlos tracks changes; Hunchly tags) | origin-r3 clustering that **downgrades apparent independence**, decision table `assess-r2`, candidates always `candidate` | Yes — "independence NOT established" wording is the rare anti-overclaim feature | Copyable conceptually; the discipline (review-gated, deterministic, caveat-carrying) is the hill |
| Deterministic, reproducible assessment | Not found; Maigret ships `--ai` (opposite direction) | no clock/RNG/network in rules (D18 pattern), reproducibility pin test | Yes for anyone burned by tool nondeterminism | Small script could copy; the *pin test + table* discipline is the moat-lite |
| Correction continuity across renditions + dissemination register | Not found as first-class lineage-carrying corrections in fetched substitutes | `report_id`/revision/supersedes; corrections append-only and travel forward; recipients recorded (D21) | Yes — S2 core workflow | Documentable; adjusting per-release reports is where realism lives |
| Honest machine-checkable tool tiers | Not found beyond editorial lists (Bellingcat/Awesome/OSINT-FW) | `indexed/verified/integrated(0)/healthy(unreachable)` + per-entry `last_checked`; `catalog stale` refuses verdicts | Trust asset, not a feature boast | Copying the *text* is easy; keeping counts honest under churn is the ongoing cost |
| FOSS + local-first + no telemetry + no SLA honesty | Partial: Atlos OSS but server-shaped; Hunchly commercial/licensed | Apache-2.0, single-process, 0600/0700 at-rest, exactly 6 runtime deps | Yes for target segment | Licensing/culture choice, not code |

### 6.2 The falsification exercise ("assume a competitor copies the visible features")

If tomorrow a product copies: CSV import with provenance, caveats, review
states, even manifest exports — what survives?

1. **The combination under one operator discipline.** The value is not any
   single mechanism; it is that ingestion → triage → independence →
   contradictions → correction register → verified export compose *without
   contradiction* and that every honesty rule kept that way through growth
   (the same discipline the maintainers demonstrated across Phases 1–12).
2. **The maintenance asymmetry.** Honesty decays — a fork that adds features
   faster than pinned verification will drift into claims the tests can't
   defend. The economic moat is that the product *refuses* much of what a
   growth-focused fork would monetize.
3. **The integrity chain semantics.** Events are append-only with
   hash-chained prev-digests, delivered with refusal to break chains by
   design (`tool_fingerprint` binding is a *decided*, not accidental,
   omission, FS-24). Reworking chains compatibly is non-trivial to bolt on.
4. **Nothing else claimed. Manifest + workflow labels if copied are just
   features.** The thesis survives only as *practiced* discipline plus the
   wedge (tool-output ingestion) which nobody in the checked set is building
   toward solo-browser-free operators.

Honest verdict: **defensible on combination + discipline, NOT on any single
technique.** Confidence: HIGH for no-single-mechanism uniqueness; MEDIUM for
sustained-discipline advantage (depends on the one maintainer).

---

## §7. Nine research-cell findings and their disagreements

Condensed outputs; full elaborations are the sections above/below.

- **CELL 01 Product intelligence** — problem space documented (§4); user
  segments and prior-work evidence reconciled with the dated survey;
  strongest initial segment S1+S2 terminal-comfortable solo/small;
  demand-level confidence LOW/MEDIUM (2022 data, no fresh survey) —
  experiment-first posture.
- **CELL 02 Ecosystem** — five-layer map ≈ §5; commoditization and whitespace
  paragraphs; provenance-standards signal (C2PA); BLOCKED breadth scan
  recorded; trend statements all carry access dates.
- **CELL 03 Differentiation** — §6 includes falsification; uniqueness reduced
  to combination + discipline; explicit "never market hashing/capture" rule
  reinforced by Hunchly's existence.
- **CELL 04 Architecture** — §9: strengths VERIFIED (typed core, fail-closed,
  additive discipline, real fault-tolerance suite, exit-code contract); debts:
  CLI monolith (2,423 L), unwired tables (D7 deadline missed), no ingest,
  render-path sync queries, no cross-platform exercise, no benches.
- **CELL 05 Security** — §11: no open CRITICAL/HIGH; security surface mapped;
  residual set (A2/R-A2-3, C1/R-C1-4, C1/R-C1-5 `tool_fingerprint`, catalogue
  UNKNOWN licences) carried with owner actions; ingestion future-surface
  requirements R-SEC-1..8 referenced (companion doc); nothing invented; no
  claim of invulnerability anywhere.
- **CELL 06 Analyst UX** — §12: terminal-first retained as a **hypothesis
  being re-tested** (D13 explicitly kept it visible); friction list anchored
  (import absent, search absent, timeline absent); restraint rules to keep.
- **CELL 07 Quality/reliability** — §11.3 + §18: current gates measured green;
  gaps named (cross-platform, property/fuzz-for-parsers post-0.2,
  doc-implementation consistency checker absent, benches absent; flake).
  Coverage % NOT treated as a goal; behavior-gated criteria instead.
- **CELL 08 Foresight** — §8: four scenarios with triggers and confidence;
  pre-mortem; success path; reversible-decision taxonomy.
- **CELL 09 Red team** — §6.2 + §15 + §17; the strongest objections are
  surfaced and answered; a genuinely independent subagent review pass ran
 against this document's draft (§20 lists what changed as a result).

**Disagreements recorded (and how they resolved):**

1. **UX wants search+timeline now; Red team says 0.2 stays minimal.** Kept
   Red team's sequencing (ingest first — it feeds search/timeline with real
   content), BUT the canonical doc elevates search+timeline into a named H2
   commitment rather than a someday line, so they don't evaporate.
2. **Ecosystem says provenance standards are coming (C2PA); Red team says
   don't chase standards.** Resolution: keep our own manifest sovereign
   (AR-6); add a *read-only* C2PA bridge only as a future adapter candidate
   triggered by a real recipient need (H3, §8 trigger list).
3. **Product cells enthusiasm vs demand evidence thin.** Resolution: split
   confidence honestly (execution HIGH, adoption MEDIUM/LOW); no growth
   targets; adoption measured by §4.2's experiment only.
4. **Architecture cell wants the unwired tables dropped; tamer voices say
   don't touch schema during 0.2.** Resolution: drop decision recorded for
   the schema-v3 window with a required test; no write actions in 0.2.
5. **Sherlock as first target (all cells agreed) but format choice now
   disagreed with the 0.2 doc.** Live README fetch wins: CSV-first. (This is
   why the doc-hierarchy rule lets this document correct a companion.)

---

## §8. Strategic foresight scenarios (conditional, no fake probabilities)

### 8.1 Scenario table

| Scenario | What changes | Becomes more valuable | Becomes commoditized | New risks | TRACEFIELD preparation | Confidence |
|---|---|---|---|---|---|---|
| **A. BASELINE** — current trends continue | Collectors keep evolving; capture stays commercial; FOSS floors stay quiet | Integrity chain, corrections discipline; the wedge (ingest) | Username sweeps; lists | Drift/rot in maintained parts; catalogue rot | Land 0.2; keep suite/pins; catalogue `verified` slice grows within creator capacity | HIGH (lowest-variance) |
| **B. ACCELERATED (AI + synthetic content)** | Inference-heavy content floods verification workflows; C2PA-style provenance moves to journalism tooling; `--ai`-style analytics become default features of rivals | **Human-auditable reasoning structure + review gates** (the product refuses to become a black box — this is the moment that refusal pays); provenance fields in exports | "Assisted EVERYTHING" features; raw scraping | Clients/customer pressure to "add AI"; provenance-forking temptation | Never at autonomy (AR-4/AR-5); planner stays proposal-only; H3 conditional C2PA-read bridge; keep all AI-adjacent fields as *data labels*, never judgments | MEDIUM (direction evidence exists — C2PA steering incl. OpenAI/BBC, Maigret `--ai`; the workload trend is framed in §5, sources dated) |
| **C. CONSTRAINED (solo capacity, debt, legal/infra limits)** | Maintainer time shrinks; upstreams break formats; host restrictions tighten | Small, additive, test-pinned codebase; docs-as-memory; zero-dep discipline | Anything requiring ops/telemetry; big integrations | Ghost project perception; patch stranding | H0 stabilization items first; ≤2 integrations until 0.2 dogfoods; partner lightness (no SLA stated honestly) | MEDIUM-HIGH (real risk; history shows discipline held so far) |
| **D. DISRUPTIVE (consolidation / paradigm shift)** | Maltego/Hunchly absorbs more of the capture+case space; or platform consolidation forces "ecosystem" behaviour; or a collector vanishes or changes all behaviour | Cross-tool neutrality + export portability; being the *compliant boring layer* everyone can leave | Not much more of what we do — validation instead | Losing upstream (e.g., Sherlock output change), forced format work; lock-in pressure from partners | B-01 fixture+version-registered parser as the pattern; reversible architecture (§10) | LOW-MEDIUM (trigger-conditioned) |

### 8.2 Leading indicators / triggers (observable, not oracular)

- Sherlock/Maigret output shape changes on new releases (watch releases;
  fixture-rotation policy B-01).
- C2PA/@content-credentials adoption appearing in journalism or collector
  tooling (any major collector shipping C2PA manifests → H3 bridge becomes
  candidate).
- Hunchly/Atlos publishing a solo-tier/CLI story (would erode S1 whitespace →
  re-run differentiation falsification §6); generalized: ANY standalone
  independent-verification layer appearing in the collection space erodes the
  export-contract whitespace → re-run §6 too.
- At least 2 independent practitioner responses to the review brief (supply
  of real demand evidence).
- Dependabot opening range-wide bumps (dependency discipline watch).
- Pydantic/Textual major leaps (the only 2 surfaces with real breakage
  potential in the 6-dep set).

### 8.3 Pre-mortem (assume failure to gain adoption after 2 years)

Most plausible reasons, in order: **1)** the wedge never became credible —
import stayed manual and the "why install this?" collapsed (early warning:
months pass without B-01/B-02); **2)** zero distribution — an honest product
with no demo GIF/video/practitioner voices starves (warning: review brief
used 0 times); **3)** single-maintainer pauses (warning: CHANGELOG quiet >1
quarter); **4)** catalogue honesty can't scale — 2,257 UNKNOWN licences lets
critics dismiss the trust story (warning: any "why are your rows UNKNOWN?"
encounter unanswered); **5)** terminal-only reaches the surveyed
one-quarter-holdout too slowly and partners (Hunchly users) never try it;
**6)** a flaky suite or a red CI run during a hiring/window kills first
impressions (warning: any flake left un-diagnosed). Decisions that would have
prevented it in hindsight: B-01 done *first*; review brief shipped with every
release; `verified` tier grown steadily (cli_tool slice first); explicit
"what this is not" messaging from day one; flake instrumented immediately.

### 8.4 Success-path analysis (assume respected tool among serious practitioners)

What must have been true: (i) the 0.2 wedge shipped and flows in real
provider outputs via pinned fixtures; (ii) at least one practitioner-used
workflow existed with continuous feedback feeding the backlog; (iii) a public explainer
essay teaches the verify workflow (the export
contract is *explained*, not hidden); (iv) releases come with watched-gate
evidence every time (habit, not exception); (v) "verified" catalogue slice
covers the cli_tool tier in earnest; (vi) the anti-roadmap kept the tool
small. Technically: schema maturity (no breaky migrations), render-path
worker fix measured, benches for ingest at real sizes (10k+ rows), and the
two primary flows (import→assess; export→verify) never regressed once.

---

## §9. Current architecture assessment (no redesign proposed)

### 9.1 Shape, VERIFIED fresh (2026-11-06)

Single local process; SQLite with equality triggers and identity chain; typed
pydantic records; Typer CLI (12 sub-apps, 46 commands, exit codes
`0/1/2/3/4/5`), Textual TUI over the same repos (every TUI path has a CLI
path); adapters behind one typed boundary D19; security module
(`urls/redact/sanitize`); planner proposal-only. 10,326 src lines; the 6
runtime deps harmonized in pinned ranges; no network caller outside the two
doubly-opt-in surfaces; event chain shared by scope ledger + report
corrections + imports. This codebase is **unusually disciplined for its
size**, and its debt is documented, not hidden.

### 9.2 Weaknesses and debts (labels)

- ARC1 — **CLI monolith**: one 2,423-line main.py weaving 12 sub-apps.
  Impact: merge conflicts, review radius. Severity MEDIUM, non-blocking.
  Fix strategy: **split-at-touch** per command family (no pre-emptive
  refactor; churn is the real risk being managed).
- ARC2 — **Unwired `catalog`/`providers` tables** (database.py:153/192;
  unused in repositories.py; D7's "wire-or-drop before v2" deadline
  missed). Severity LOW-MEDIUM. Fix: DROP in the schema-v3 window with a
  migration test; schema-v2 already retains the JSONL as truth (D22).
- ARC3 — **No ingest path** (the wedge gap; NOT PRESENT). Addressed by 0.2
  IS row set.
- ARC4 — **Render-path synchronous queries** (A2/R-A2-3 Open, Medium).
  With realistic case sizes (large evidence lists) the TUI may hitch. Mitigation:
  Textual worker offload exists in the framework (the import machinery will
  need it anyway); the H0-3 measured repro decides with a number; the
  worker-offload implementation stays gated in H2 (B-09).
- ARC5 — **No cross-platform exercise** (above): only-ubuntu CI; SUSPECTED
  Windows chmod/traversal variances. Fix: add macOS job (cheap) in H2;
  Windows only on demonstrated user demand (avoid masking real platform
  differences with false claims).
- ARC6 — **No performance baselines** besides one 2026-10-16 startup smoke.
  Not blocking; H2 micro-benches will cover import/cluster/verify at sizes
  the happy path meets (10k rows / 5k files — sizes harmonized with §16/§18).
- ARC7 — **E2E reproducibility flake** observed once (2026-11-06), 8 clean
  runs after. Owner: B-05.
- ARC8 — **Documentation-practice consistency check** relies on human
  discipline (K1/K2 class issues recurred historically in this repo's own
  strategy docs). H2: a small doc-consistency checker (grep-pinned claims vs
  generated counts) as a *read-only* lint script; NEVER networked.

### 9.3 Options where a real decision existed (Stage 2, deep)

- **Ingest as separate `ingest/` package vs adapters extension.** Selected:
  separate package. Reason: adapter boundary D19 = *execute* contract (binaries,
  allowlist, probes); ingest = *parse saved untrusted bytes* — different
  threat class, different test strategy (no binaries, no PATH). Migration
  cost: zero (new code); risk: none to existing pinnings.
- **Promote-at-import vs promote-on-review for imported rows.** Selected:
  rows arrive only as `Observation`, promotions via explicit analyst command
  (mirrors existing review-state semantics).
- **`catalog stale` automation?** Revisited and re-confirmed D22 read-only
  (no health job; no network). No change.
- **eviction of the flake.** Options: chase root-cause vs instrument-and-doc.
  Selected: B-05 dual-track with a hard rule — never leave silent.

---

## §10. Target architecture and evolution principles

**Remains (no rewrite; evidence: everything above VERIFIED on the current
shape):** single local process; SQLite at SCHEMA_VERSION 2 with
additive-migration discipline + tripwire assert (database.py:20); typed
records; one integrity primitive (append-only hash-chained `analysis_events`,
reused by scope/corrections/imports); D19 adapter boundary; CLI as the
contract, TUI as a layer over it; exit-code contract; zero default network.

**Improvements (all additive; none change behaviour of shipped flows):**
1. `src/tracefield/ingest/` for saved-output parsing (0.2) with
   per-format, per-major-version parsers; table-driven; size-capped; typed
   refusals (Reason codes, exit 3); no network in the module (test-pinned).
2. Split-at-touch CLI module organization, one sub-app family per file, to
   unwind the monolith gradually without churn.
3. Fault-tolerance suite extension patterned on test_fault_tolerance.py for
   new surfaces (ingest interruption mid-write test required by AC).
4. Read-only views layer (search, timeline) over existing repos — NO new
   tables (H2).
5. Worker-offload for any op that can exceed ~a UI-frame's price (B-09),
   measured, not dogma.

**Removal / simplification:** the two unwired tables (schema-v3 window);
repeat review of `_is_blocked_ip` list vs new Python versions (each Python
bump = re-run the quirk fixtures); retire the "unwired deadline" debt row
when dropped. No removable core.

**Principles (guardrails for every future change):** additive-first;
fail-closed at every trust boundary; honest labels in output; typed +
versioned everywhere inputs are untrusted; one integration at a time with
real fixtures; simplicity over frameworks; every claim printed by the tool
must be checkable today (no "verifying..." placeholders (truthful progress
only)).

---

## §11. Security, privacy, and reliability requirements

### 11.1 Standing invariants (all current-status VERIFIED — do not regress)

Re-classified from decisions/tests, keep as PR checklist: SSRF deny list +
per-hop re-pin (`fetch.py:74-120`; `tests/security/test_security.py:90`);
backend allowlist exact-match (`inspect.py:160`; covered among the 22 tests
in `tests/security/test_security.py`); terminal
escape at every render site (D11; raw storage); path-traversal defences
(strict case-ID shapes; tests); redact-then-manifest (D5; export corrupts
neither originals nor manifest integrity — VERIFIED live); 0700 dirs / 0600
at-rest perms (0700 dirs / 0600 DB; permission
tests cover both); cross-case DB triggers (Phase 11);
dissemination register metadata; no telemetry; `--fetch`/`username` are the
only egresses, privilege-denied by default; scope-gate before any case
collection (D20); no SLA claims (SECURITY.md).

### 11.2 Threat model notes (situation-anchored, no theater)

Primary attacker classes: (a) crafted case/evidence names and exported-bundle
content (exemplified: OSC/ANSI, path shapes, XML-ish payloads) — covered by render-site
sanitation + strict IDs + export validation; (b) remote endpoints during
doubly-opt-in fetch (SSRF/redirect/rebinding) — covered; (c) local
machines/other local users (perms 0600/0700, sql triggers); (d) future
ingest (BIGGEST untested surface in 0.2; parser-hardening requirements
R-SEC-1..8 by reference: see companion doc §9); (e) supply chain (6 pinned
deps; Dependabot; pip-audit gate; CodeQL). NOT SCOPE: kernel-hardening,
host-forensics, network-TLS-everywhere claims nobody asked for. The **SUSPECTED**
residuals stay in the risk register with owners (A2-3, C1-4, C1-5).

### 11.3 Reliability/quality requirements

Measured green in this session's battery (§2.1): 332/0/0; mypy strict 38
files; catalogue gate. NOT re-claimed as measured today: the wheel+fresh-venv
install smoke and the pip-audit gate — last run in the 2026-11-06 morning
companion session (its §14 verification log); 8 named
fault-tolerance tests (corrupt/truncated DB, second-writer, busy→exit 5,
read-only root/db, lock-during-report, interrupted-export preservation). Standards:
coverage % is not a target; every FAILED check is fixed or user-accepted
(never silent); watched-run policy for CI claims; the reproducibility pin
(test_demo_case.py:378) must never be removed to make a flake go away —
instrumentation (B-05) first.

---

## §12. Analyst experience and interface direction

**Direction (restrained, terminal-first, honest):** keep the 6-workspace
Textual TUI as an *optional* surface over the CLI contract; every UI affordance
must remain CLI-reachable (parity test exists); truthful chrome stays the law
(TS-2). What changes (in H1/H2): the TUI gains the import/triage overlay plus
a last-import block on Mission (0.2, J6–J7 spec in companion doc — J8 search
deferred to H2); H2 adds a
case-wide jump-to-record palette (`s`) and a read-only chronological strip built
purely on existing timestamps (spec'd, no new tables); H3-conditioned: any
canvas/graph only with demonstrated demand.

**Human-friction priorities (analytic order):** 1) ingestion (today: manual
transcription of every row — the wedge); 2) retrieval (no cross-record search
today; grep-the-JSONL is the only workaround — poor); 3) orientation over
time (timestamps exist per record; no assembled view); 4) risk-of-misread
controls (already strong; keep caveating wording current); 5) long-running ops
(worker offload when measurements justify).

**Explicit non-goals retained:** no web dashboard absent ≥3 independent
practitioner requests tied to real workflows (otherwise the surveyed
terminal-quarter is honest to decline; the review brief experiments this);
no onboarding wizard; no theming sprawl (theme tokens stay in
`tui/state.py` palette); no TUI-only feature ever.

---

## §13. Controlled self-evolution model

**Two capacities, deliberately separated:**

### 13.A In-product self-diagnostics (what the product reports about itself)
All shipped (VERIFIED): `doctor` (local env, honest `UNAVAILABLE`),
`tools status` (tiered counts + no health fabrication), `catalog stale`
(read-only freshness listing, refuses health verdicts by wording),
`catalog validate` (CI gate), `evidence verify`, `analyze events`
(chain closure check), `case scope` (ledger), `case-verify` (bundle),
`report-history` (who got what), exit codes machine-parseable, JSON on every
data command. **Proposed additions (all read-only, H2, NOT PRESENT yet):**
- `tools integrations` — one command enumerating the ADAPTERS registry +
  fixture-version registry so the honest integration surface is queryable
  (not scattered across docs);
- doc-consistency checker (§9 ARC8) — grep-pinned factual claims (counts,
  versions) vs generated truths; run in CI, zero network;
- micro-benchmark scripts + a recorded baseline table (§9 ARC6).
None of these mutate state; all feed §13.B decisions.

### 13.B The dev-process loop (OpenCode + LOOP, single maintainer)

Cycle (recurring; each step's artifact named so the work survives gaps):

| Step | What happens | Artifact written/updated | Automatable? |
|---|---|---|---|
| DISCOVER | Sweep: own friction (_FLAGGED in work sessions), user reports (issue template), ecosystem signals (release notes of upstreams, C2PA news) | `RESEARCH_REGISTER.md` entry (URL, date, verdict) | grep-based sweeps + manual reading; CLI-local only |
| RESEARCH | Primary sources only; falsify what you think you know (the Sherlock `--json` erratum is the in-house example) | same register | webfetch; search when available |
| FORM HYPOTHESIS | "X will improve Y for Z users" with accept criteria | strategy backlog row (this doc §16) | — |
| EVALUATE | Cost/risk/confidence; anti-roadmap check (§15); dependency check (6-dep budget) | same row + DECISIONS entry if a boundary is crossed | — |
| DESIGN | Minimal slice; schemas; threat pass (trust boundaries); test list | companion release plan (e.g., 0.2 doc) | — |
| IMPLEMENT | LOOP iterations; follow loop-engine safety rules (git status first; additive; fail-closed) | code + tests + docs | loop-engine run |
| TEST | Full battery (§2.1 commands scripted); toolkit: ruff/mypy/pytest/pip-audit/wheel/fresh-venv/demo | battery log; release-claim note | FULLY automatable (this session's battery IS the template) |
| ADVERSARIAL REVIEW | Independent subagent red-team (fresh-context) + self-review; severity-ordered fixes | review note in phase doc | subagent (1 per substantive change) |
| MEASURE | Acceptance criteria checked against evidence, not vibes | updated IMPLEMENTATION_STATUS-style notes | partial |
| DECIDE | Ship / hold / park; anti-bloat test (net-commands +; review radius; honesty still keepable?) | DECISIONS.md entry; CHANGELOG | human only |

**Human-only gates (never automated):** direction/pillar changes; security
verdicts; licence interpretations; dependency additions; upstream fixture
re-record decisions; releases/pushes; any interaction with production
bug-reports from real users. **Automatable safely:** gates listed in §2.1,
catalogue validation, stale listing, doc-consistency lint, backend probe
checks, demo script. **Hard prohibition:** no autonomous mutation of the
repository by any process; no telemetry; LOOP agents get scoped, reviewed
writer permissions only, and every loop ends in human review before push.

---

## §14. Strategic pillars (max 4)

Each pillar: purpose → analyst value → differentiation → required
capabilities → cost → security implications → acceptance criteria →
confidence → falsifiable if.

### P-1 — Verifiable integrity end-to-end (the chain holds)
- **Purpose:** every artifact from import to export is bound by one integrity
  primitive (content-addressed storage + event chain + export manifest).
- **Analyst value:** they can PROVE the case bytes and detect tampering, in
  court, in edit rooms, and in arguments, without trusting the tool's screen.
- **Differentiation:** stranger-verifiable export (§6 row 2). Hunchly/Atlos
  verified equivalents promote in-tool audit instead.
- **Required:** existing chain + manifest; 0.2 adds ingest-file binding.
- **Cost:** near-zero incremental (existing system); maintenance = chain
  event tests.
- **Security:** redaction never rewrites originals; manifest covers final
  bytes (D5/D21).
- **AC:** AC-09 of companion doc + demo step-12 passing every release.
- **Confidence:** HIGH (built & live-verified).
- **Falsifiable if:** any external re-check of an export fails, or tamper
  detection misses.

### P-2 — Analyst-controlled truth (review > approval)
- **Purpose:** the tool structures reasoning (independence, contradictions,
  assessment) but never completes it; labels are workflow states, not truth
  scores; corrections are append-only and travel.
- **Value:** defensible conclusions; the last writer of meaning stays human.
- **Differentiation:** the only checked substitute set that carries this
  reasoning structure with refusal to score probability (§6 rows 3–5).
- **Required:** origin-r3 + decision table + ReviewState gates; 0.2 triage.
- **Cost:** cognitive design cost per new surface (kept small deliberately).
- **Security:** gate at collection boundary; no unreviewed promotion.
- **AC:** no-automation pins (AC-04/AC-05 companion doc); caveat wording
  tests.
- **Confidence:** HIGH (verified); adoption tied to S1/S2 goodwill.
- **Falsifiable if:** any output ever auto-promotes unreviewed content into
  evidence, or a correction vanishes from a subsequent render.

### P-3 — Honest ingestion & interop (earn the integrating role)
- **Purpose:** be the reliable downstream of collectors by parsing their real
  saved outputs with provenance, version honesty, and refusal-on-drift.
- **Value:** kills the manual transcription wedge; tool metadata (name,
  version, run time) becomes structured provenance; row-level history.
- **Differentiation:** none of the checked substitutes ingests collector
  outputs from a *workbench* perspective (they ingest their own/format or
  none). Sherlock-first; each integration gated (B-01 pattern).
- **Required:** ingest/ package; fixture-per-version registry; allowlist-style
  refusal table; CSV first (stdlib).
- **Cost:** per format: fixture procurement + schema doc + parser + skew
  tests; deliberately ≤2 for 0.2.
- **Security:** R-SEC-1..8; size caps; no URL auto-fetch; secrets-at-rest
  rules (companion doc §9).
- **AC:** AC-02/AC-03/AC-07 companion; zero-network ingest tests.
- **Confidence:** HIGH on mechanism; MEDIUM on demand until review brief
  returns.
- **Falsifiable if:** a real Sherlock CSV (or later Maigret) fails to import
  byte-faithfully, or any test reaches network.

### P-4 — Local-first, consentful operation (the machine is theirs)
- **Purpose:** the analyst's data stays on their machine; network exists only
  as two doubly-opt-in surfaces; no telemetry ever; export/redaction still
  under their control.
- **Value:** legal/ethical stance usable inside organizations; threat model
  small; no cloud surprise.
- **Differentiation:** fidelity to a costly stance (vs Atlos server-shaped,
  vs Hunchly licensed/clouds) at equal honesty.
- **Required:** current drills; scope ledger; env gates; at-rest perms.
- **Cost:** ongoing (every new surface re-audited; egress list audit).
- **Security:** keeps the attack surface minimal (§11.2).
- **AC:** zero-egress test suite green; egress-codes contract intact;
  SECURITY.md honesty unchanged.
- **Confidence:** HIGH.
- **Falsifiable if:** any new egress appears outside the two surfaces, or
  any file-permission or redaction regression.

---

## §15. The deliberate anti-roadmap (what we refuse, and why it protects)

| ID | Refuse to build | Why it protects |
|---|---|---|
| AR-1 | Browse-time capture (screenshots/plugin/tunnel) — **Hunchly owns it** (fetched evidence) | avoids direct war with a respected commercial incumbent on their ground; our ingest wedge serves the complementary flow |
| AR-2 | Any new collector / more collection surfaces | Sherlock 97.7k★, Maigret, SpiderFoot maintain a 10-year moat in a commoditized layer; refs B1/R1 feature-inflation trap |
| AR-3 | Team/server/cloud mode | Atlos owns collaborative tracking; server-mode changes our threat model and honesty claims; solo-local is the unserved lane |
| AR-4 | Autonomous AI investigator / auto-claims | kills determinism + reviewability; wrecking-iron evidence: D4/D18; OOVS posture; Maigret's `--ai` is the cautionary mirror, not a target |
| AR-5 | Any LLM writer/summarizer in the report/verdict path | unreviewable probability-adjacent language inside a product whose differentiation is refusing it; a corrections-*drafting* assistant (H3 row 4) requires an explicit DECISIONS amendment of this row citing the B-10 threat analysis — never a silent relaxation; parked B-10 research bookmark (human-only gate) |
| AR-6 | STIX/TAXII/CASE-UCO export; PROV serializer | D14; no concrete consumer exists; revisit ONLY on a named recipient communicate requirement |
| AR-7 | Web dashboard | absent practitioner evidence (§12 trigger); terminal-first is a design stance with a review mechanism (D13), not a milestone delay |
| AR-8 | Multi-repo split / product spin-off | violates single-product identity; internal boundaries suffice; revisit only with hard technical necessity (none demonstrated) |
| AR-9 | Graph canvas / force-directed viewer | visual richness ≠ analytical value; data exists in listings; revisit only with demand |
| AR-10 | Probability scores / confidence percentages anywhere | violates the honesty vocabulary; D4 wording is pinned by tests |
| AR-11 | Auto-correcting upstream data / silent normalization | provenance cannot be quietly improved; correction belongs to the corrections register |
| AR-12 | New runtime dependencies without a concrete need | 6-dep budget is auditable and has held; each addition must pass `EVALUATE`+`DECIDE` with a named user value |
| AR-13 | Telemetry, phone-home, update pings | incompatible with identity; violations would be fatal trust breaches |
| AR-14 | Evasion features (CAPTCHA/bot-blocks), forever | D17; boundary is also a legal stance, recorded |
| AR-15 | "Health"/certification claims (catalogue HEALTHY, OOVS badges, SLAs) | no basis on hand; honest states instead (D19/D22) |
| AR-16 | Racing feature parity with Hunchly's court-packaging UX | different trust target (forensic packaging vs operational workflow); stay the boring verifiable file-set |

---

## §16. Prioritized roadmap (four horizons)

Ordering rule: analyst value × differentiation × feasibility ÷ security +
survival impact; reversible decisions preferred; 2 items running max (solo
capacity). Gate: FULL battery green at each landing.

### H0 — Immediate stabilization (≈0–4 weeks serialized per the §19 cadence —
one landing per working block; before any 0.2 feature)
| Item | Why now | Owner note |
|---|---|---|
| H0-5: Ship the §20 review brief to ≥3 practitioner candidates in week 1; log responses as they arrive | the cheapest decision-relevant evidence available, and it exists now; pre-mortem warning #2 (§8.3) is "brief used 0 times", and the strategy claims an experiment-first posture (§4.2, §7) — shipping it late would contradict that claim | zero build cost; overlaps all other H0 items; responses analyzed at the H2 checkpoint below |
| B-05 Flake diagnostic (dual-track: reproduce/instrument → decide, time-boxed — no open-ended root-cause chase) | reliability floor; if it recurs during 0.2 it poisons every claim | document in RISK_REGISTER when resolved |
| H0-2: Unwired-table decision memo (drop in v3; date the migration test) | debt D7 already missed a deadline; zero-risk on decision now | DECISIONS entry |
| H0-3: Worker-offload decision (A2/R-A2-3) with a measured case-size repro (10k evidence rows) | decide with a number, not a feeling; feeds B-09 design | |
| H0-4: ERRATA sync (companion 0.2 doc — Sherlock CSV; this doc) | docs stay authoritative (Part I) | done in this session, completed by the PASS-2 amendments |

(H0-1 is deliberately absent: its scope was folded into B-05 and H0-2 at
planning time; the recorded IDs preserve that numbering.)

### H1 — Next 90 days (the 0.2 release)
| Item | Evidence anchor | Notes |
|---|---|---|
| **B-01 Sherlock format verification — `--csv` first** | live README fetch 2026-11-06 (§22) | version+date pinned fixture; schema doc; rotation policy; `--txt` fallback recorded too; no network during tests; parser/skew pins land with B-02 |
| B-02 ingest package (preflight, raw-first storage, typed rows, event append) | 0.2 IS-1/IS-2 | AC-02/AC-03 |
| B-03 `case-import` + `case-import status` + `source promote/dismiss` CLI | 0.2 IS-3 | exit-code contract |
| B-04 ingest E2E (fixture → triage → claim → report → export → verify) | 0.2 B-04 | AC-08/AC-09 extension |
| B-06 TUI triage overlay + last-import block | 0.2 §8 | J6–J7 (J8 = search palette → H2 row below) |
| B-07 Maigret verification+parser (second; bypass fields ignored-with-record) | §5 row 2 | 0.2 *stretch*, not a release blocker: only after B-04 ships AND calendar allows; otherwise the first H2 item (feasibility cut adopted from the iteration-2 review, §20) |
| Release: watched CI, CHANGELOG, docs rows | FINAL_BUILD_SPEC §6 checklist | no global config changes |

### H2 — 3–12 months (breadth of the same identity)
| Item | Reason | Trigger/outcome |
|---|---|---|
| Timeline (read-only strip + CLI `timeline`) | orientation cost (Cell 6) | H1 first; view-only |
| Case-wide jump-to-record palette (`s` + CLI `case search`; J8 moved here from 0.2) | retrieval cost | exact-prefix/bounded; no magic |
| Catalogue licence grind — cli_tool slice (256 rows as of 2026-11-06) | trust asset with the biggest number of truths per hour | FS-23 |
| macOS CI job; Windows *assessment only* (measure 0o400/0700 + traversal behaviour via a candidate env-matrix run) | portability honesty | SUSPECTED→confirmed measurements; no support claim, no Windows CI (ARC5) |
| Doc-consistency checker in CI | recurring K-class docs drift | read-only; no network; the concrete checks are enumerated at §18 H2(d) |
| Micro-bench: import 10k-row fixture; cluster 1k sources; verify 5k-file bundle | ARC6 | baseline recorded, regression-gated |
| `tools integrations` command (13.A) | queryable honesty | read-only |
| FS-24 decision: bind `tool_fingerprint` into event digests (breaking-chain decision recorded) | integrity completeness | one-time migration w/ explicit costs |
| Review brief analysis checkpoint (initial send moved forward to H0-5) | demand falsification vs SUSPECTED | maintainer-controlled outcomes only: brief shipped + N attempts + responses logged; the response count drives the §4.2 decision gate — it is a decision trigger, not a pass/fail AC |

### H3 — Conditional long-term opportunities (12–24 months; all evidence-gated)
| Candidate | Gate to enter |
|---|---|
| C2PA read-only manifest reading (adapter) | a real recipient/collector need documented |
| PROV-JSON bridge (export) | named consumer (D14 revisit condition) |
| pHash cross-media duplicates (FS-25) | after benches prove analytic value at real sizes |
| Partial workflow automation of corrections *drafting* (assistant-level, human-gated) | S1/S2 actual workflows demand it AND an explicit DECISIONS amendment of AR-5 citing the B-10 threat analysis; never in verdicts |
| Aleph import adapter (export→corpus) | a named newsroom partnership/user; not speculative |
| Windows support | demonstrated users; measured variance (ARC5) |

### Priority statement
**Highest priority next task: B-01, re-targeted to Sherlock `--csv`.** The
argument is not preference — it is control dependence: without a
version-pinned REAL upstream artifact, the ingest-data-dependent H1 items
(B-02/B-03/B-04/B-07) have untestable acceptance by construction (B-06's
overlay mechanics and the release checklist do not wait on it), and today's
erratum (would-be `--json` claim
wrong) demonstrates that skipping this gate manufactures wrong plans in
advance. Evidence: §22 S1. Expected value: unblocks the wedge fully. Cost:
hours of fixture work, minutes of schema doc. Risk: shutdown-format-change
later (drift watch policy listed §8.2). Confidence HIGH. Falsifiable: any
real CSV that defies the documented schema kills the plan, so B-01 records
field-level reality rather than assumption.

---

## §17. Risks, assumptions, dependencies, unresolved questions

| ID | Risk/assumption | Basis | Handling |
|---|---|---|---|
| R-1 | Upstream format drift breaks parsers silently | Sherlock CSV/TXT may change across releases | fixtured per version; schema docs; refusal-on-unknown; fixture-rotation policy |
| R-2 | Demand hypothesis untested (survey 2022; Hunchly/Atlos signal ≠ our demand) | §4.2 | review brief experiment; measure, don't motivate |
| R-3 | Single-maintainer bus factor; pauses | HISTORY + SECURITY.md no-SLA | additive small steps; docs-as-memory; ≤2 parallel problems |
| R-4 | E2E reproducibility flake (observed once) | observed 2026-11-06 | B-05; never silently removed |
| R-5 | Catalogue UNKNOWN licences (2,257/2,264) undermine trust story | tools status | FS-23 grind; honesty about progress over numbers |
| R-6 | Competitive pressure into our lane (Hunchly adding CLI-style ingest; Atlos solo) | §5 | re-run §6 falsification on signal; keep wedge narrow & deep |
| R-7 | Dependency ecosystem surprises (Textual/Pydantic majors) | pinned ranges today | range discipline; quirk fixture re-runs on py bumps |
| R-8 | Redaction/limits residual (C1/R-C1-4, C4/R-C4-2) | risk register | keep owner notes; never silently widen redaction |
| R-9 | Unwired tables (D7 tardiness) become a v3-force | confirmed unused | H0-2 decision memo; aimed drop with test |
| R-10 | Import terminology/`integration_state` vocabulary unclear | companion R-10 | maintainer decision before B-03 |
| R-11 | No SLA; slower fixes than users expect | SECURITY.md | honesty repeated in place of promises |

**Dependencies (runtime, pinned)**: typer/click/rich/textual/pydantic/httpx.
**Upstream deps for plan**: Sherlock (MIT ✓) and later Maigret (MIT ✓)
format stabilities; availability of an ACTUAL saved output file for
record-keeping (operator-supplied fixture; no live collection in this task).
**Unresolved (explicitly)**: drop-vs-wire tables (H0-2 memo); OOV/`import-integrated`
vocabulary (R-10); FS-26/27 user-gated items (untouched); review brief
answers pending; breadth-of-market numbers BLOCKED (search API 402) —
schedule a narrower re-scan when available.

---

## §18. Measurable acceptance criteria

Global (every release): full battery green (§2.1 commands); watched CI+CodeQL
on the released commit; no silent weakening of any §11 invariant; docs
rows truthful (FINAL_BUILD_SPEC §6 discipline).

H1 (=0.2 companion AC-01…AC-11, by reference; the load-bearing ones restated):
AC-02 real CSV fixture imports byte-faithfully (tool name via detection;
version = declared in the file if present, else `unknown` per R-SEC-4 — a
Sherlock CSV is not expected to carry version metadata; the
operator-recorded version+date is pinned in the B-01 fixture doc instead);
AC-03 zero partial imports on the 5 preflight-refusal tests;
AC-05 assessment changes only via decision table; AC-08/AC-09 demo+verify
unchanged after ingest; AC-10 zero new runtime deps; AC-11 documentation rows
land same-release.

H2 (new): (a) timeline & jump-to-record parity: every TUI result has a CLI twin,
tested; both read-only (zero mutations in view paths — test); (b) catalogue:
cli_tool tier licence coverage recorded with a dated delta (not a padded
count); (c) macOS job green; (d) doc-consistency checker runs in CI with its
checks enumerated so "catches drift" is testable: every printed count equals
the count generated from the catalogue dataset; every `file.py:line` anchor
cited in strategy docs exists at that exact line; every decision-ID citation
exists in `DECISIONS.md` (the historic K1/K2 class becomes this checklist);
(e) micro-bench baselines recorded (import
10k rows; cluster 1k sources; verify 5k files) and regression alarms set;
(f) review brief shipped to ≥3 candidates in week 1 (H0-5) with attempts and
responses logged — the response count drives the §4.2 decision gate (a
decision trigger on parties the maintainer does not control), while the
maintainer-controlled pass/fail set is: send completed, log complete.

H3 (conditional items): each outcome documented in DECISIONS with the exact
trigger evidence that admitted it (no drifting entries).

---

## §19. Solo-maintainer R&D operating model (OpenCode + LOOP)

**Cadence (minimum viable weekly; stretch at release windows).** Rough cycle
per §13.B with this practical shape: pick ≤1 horizon item + ≤1 maintenance
item per working block; run LOOP (≤3 iterations) per item; battery + red
team per substantial change; commit only if gates green; checkpoint docs. A
"week" that produces: one landed horizon item, one doc/spec entry, and an
honest BATTERY log, is a successful week — throughput optimism is the
engineer's enemy under solo conditions.

**How opportunities are discovered without burnout:** friction queue (your
own weekly use of TUI/CLI); upstream release notes of the 6 pinned deps +
2 integration targets; issue templates; §8.2 indicator review monthly. STOP:
if a discovery does not map to one of the 4 pillars, park it (named) in
RESEARCH_REGISTER and move on (no side quests).

**Valuable feature vs distraction test (3 questions, in order):** Does it
advance any North Star demonstrable? Does it fit a pillar AC without a new
boundary? Can it ship post-battery in ≤… days with fixtures/test? Any NO =>
park it, named, in this doc's parking list (NOT silently dropped).

**Preventing architecture decay:** split-at-touch policy (§9); every new
surface must include its fault-tolerance + parity tests; the tripwire-assert
schema pattern continues; refactors allowed ONLY when touching that area for
other reasons (churn control).

**Technical debt prioritization:** debt matrix = (user-visible failure %
today) × (blast radius on honesty claims). Current top-3: D7 tables (already
tardy), flake B-05, A2/R-A2-3 measure-first. Everything else queue.

**Adversarial review protocol:** fresh-context subagent with a rubric:
contradiction hunt (docs-vs-code), unverified-claim hunt, honesty-leak hunt
(any improvement to claims vs evidence), attack the weakest §11 boundary,
attack the newest surface every time. Iterate until zero HIGH findings, cap
2 rounds (anti-litigation).

**Preserving knowledge:** DECISIONS.md (why), IMPLEMENTATION_STATUS-style
snapshots (what state), RESEARCH_REGISTER (evidence trail), phase reports
(how happened); the repo docs double as onboarding for any future
collaborator within an afternoon.

**Documentation authority rule:** companion/one canonical strategy doc per
horizon class; edits in place with dated update notes (like IMPLEMENTATION
STATUS does); never competing word docs on the same subject.

**Release preparation:** FINAL_BUILD_SPEC §6 checklist + §18 battery + demo
re-run + review-brief ping to practitioners + CHANGELOG wording pass (claims
≤ evidence).

**Objectivity:** batteries and watched gates only; scope releases to what
the gates say; never count skipped tests as coverage; flake policy as per
B-05.

---

## §20. External specialist review brief (updated for this horizon)

*Shareable alone or with the companion doc; demo runs offline, synthetic
data only. Reviewers are asked to attack, not applaud.*

- **Prompt-to-reviewer:** "Run `bash docs/demo/run_synthetic_demo.sh` on a
  checkout. Then attempt these tasks and tell us where the tool fell short:
  recreate this flow with the actual records of one of your own closed
  checks; ingest your own saved tool output (today this requires manual row
  copying — tell us how much time that costs you); re-verify an export bundle
  with `sha256sum` only; fabricate a correction trail; lie with the
  probability claims you wish we had (so we can hear it)."
- **Focused questions (replaces the long list from the companion doc for this
  horizon, which remain valid there):** Q1 what evidence fields would make
  your tool-export pipeline trust this bundle MORE (specific, countable)?
  Q2 given your real Sherlock/CSV (or Maigret) saved outputs, which two
  columns are the FIRST you'd want structured, and do our CSV/TXT plan and
  provenance fields match your habit? Q3 where would a *deterministic*
  assessment vocabulary slow your editorial/legal workflow down (the
  probability refusal is a stance, pick it apart)? Q4 red-team the export
  verification: what does a smart adversary do to a bundle that `sha256sum`
  would NOT catch? Q5 judging §5's verified facts: do you use Indo-Pacific
  products (Hunchly/Atlos/Aleph) with which this tool coexists rather than
  competes; where precisely would you switch between them?

**Iteration-2 red-team record (2026-11-06; independent fresh-context
subagent review of this document, ≈20 factual claims spot-checked against
the repo and re-fetched pages).** Findings and dispositions:
- **H-1** (B-01's DoD secretly fused B-02's parser tests) → §21 rewritten:
  B-01 closes at fixture + schema-doc + rotation-policy state; parser/skew
  tests are B-02's AC-02/AC-03.
- **H-2** (search placement contradicted between the H1 "J6–J8" note and the
  H2 search row) → J8 explicitly moved to H2 here, and the same amendment
  applied into the companion doc (AC-06 → J6–J7).
- **H-3** (AC-02 demanded in-file tool-name/version metadata a Sherlock CSV
  cannot carry, contradicting the doc's own R-SEC-4 "never guessed") →
  AC-02 reworded; version evidence comes from operator-recorded fixture
  provenance.
- **H-4** (AR-5 categorical vs H3 corrections-drafting candidate) → AR-5
  reworded to the report/verdict path; any relaxation requires an explicit
  DECISIONS amendment citing B-10.
- **H-5** (the review brief — the cheapest demand evidence — was scheduled
  after the build it de-risks) → new H0-5 ships the brief in week 1; the
  H2 row became the analysis checkpoint.
- **MEDIUMs applied:** command count 46 (was ~37; both docs); `40`→6 deps
  typo; security-test citation rewritten (22 in the dedicated module);
  planner label EXPERIMENTAL→VERIFIED (advisory, per D18); wheel/pip-audit
  provenance re-attributed honestly (not re-claimed as today's battery);
  companion-body `--json` drift repaired in place; CI run-ID lineage
  explained (both ID sets are real — different commits); H0 serialized to
  ≈4 weeks at the §19 cadence; H2(d)/(f) criteria made testable and
  maintainer-controlled; §5.2 whitespace claims bounded to their
  single-page basis; §8.2 trigger generalized to any standalone
  verification layer.
- **LOWs applied:** `analysis.py:19` anchor (was :22); 13-banner demo
  wording; §22 S1 flag list; retention-row label split; C2PA steering
  list completed (Publicis); H2 Windows row narrowed to assessment-only;
  search surface renamed uniformly ("case-wide jump-to-record palette").
- **Feasibility verdict (reviewer): FEASIBLE WITH CUTS** → cuts adopted:
  B-07 → stretch item, J8 → H2, B-05 time-boxed. The reviewer's
  single-most-important weakness (front-loading code over both the
  format-unknown and the demand-unknown) is neutralized by H0-5 + the
  B-01-first ordering.

---

## §21. The single recommended next implementation task

**B-01 — Sherlock format verification, re-targeted `--csv` (then `--txt`),
version-pinned real-sample fixture + field-level schema doc + rotation
policy.** Steps: (1) obtain/record a real `--csv` output from an operator's
normal Sherlock run searching a username the operator owns or lawfully
tests (with the Sherlock version + date recorded); (2) document field-level schema and per-field
provenance in a fixture doc; (3) commit the fixture under
`tests/fixtures/ingest/` together with its provenance note; (4) record the
schema doc's shelf-life policy (rotation on upstream release). Parser and
skew tests are NOT part of B-01: the parser-fixture tests
(unknown-version/major-field/mutated-fixture refusals) belong to B-02's
AC-02/AC-03 against this fixture. B-01 is closed when the fixture, schema
doc, and rotation policy land with the full suite still green — nothing else
claims the 0.2 wedge until that state exists (amended by the iteration-2
review: the earlier wording secretly fused B-01 with B-02, since parser
tests cannot precede the ingest package).

Why first, precisely: every ingest-data-dependent H1 acceptance criterion
(B-02–B-04, B-07) has B-01 as a strict prerequisite; the leverage argument
(§16), plus the erratum already produced by skipping an equivalent
verification once, makes this the single highest-leverage hour of engineering
in the roadmap. Command-level completion test: `pytest tests/ -m "not
network"` stays fully green AND the demo keeps passing at the moment the
fixture+docs land — that state is B-01 closed; evidence labels updated in
the same commit. No parser exists yet, by design; B-02's tests will pin
AC-02/AC-03 against this fixture.

---

## §22. Source register

Session battery commands (2026-11-06, this session): `git status/list`,
`pytest -m "not network"`, `ruff check/format`, `mypy src`, `tools status`,
`catalog validate`, `catalog stale`, demo script run + validate log, `gh run
list`, anchor greps — as enumerated in §2.1 with results.

### External primary sources (fetched by this session)

| # | Source (URL) | Accessed | Establishes (exactly) |
|---|---|---|---|
| S1 | https://github.com/sherlock-project/sherlock | 2026-11-06 | 97.7k stars; MIT; `--csv/--xlsx/--txt/--dump-response` output options and `--json` as an input flag ("Load data from a JSON file"); v0.16.x in help text; broken third-party package warning |
| S2 | https://www.atlos.org | 2026-11-06 | OSS + self-hostable collaborative investigation platform; change tracking; built-in archival; private-by-default workspaces; CSV import/export; project API; senior-AI-audit 2023; FAQ: archiving "not suitable for legal or forensic evidence" |
| S3 | https://www.hunch.ly | 2026-11-06 | Commercial capture product (Maltego Technologies ©2026): hashes+timestamps of visited pages, full-page captures, tagging/search, court-ready reports, audit trail; local or Kasm-workspace cloud storage; 84 countries |
| S4 | https://docs.alephdata.org | 2026-11-06 | OCCRP Aleph: leak/document uploads, OCR+searchable, network diagrams, timelines, hundreds of datasets |
| S5 | https://c2pa.org | 2026-11-06 | C2PA content-provenance standard (spec 2.3 linked); steering group — 11 members on the fetched page: Adobe, Amazon, BBC, Google, Meta, Microsoft, OpenAI, Publicis, Sony, TikTok, Truepic; page updated 2026-01-08 |

### Register-recorded facts (no re-fetch this session; dated entries)

- Bellingcat 2022 survey (registration of practitioner pains) — `[V
  2026-10-19]`, URL + quotes in `RESEARCH_REGISTER.md`.
- Maigret/SpiderFoot/theHarvester/holehe/ExifTool rows — `[V 2026-10-16]` /
  `[V 2026-10-19]`, `COMPETITOR_MATRIX.md`.
- W3C PROV-DM fetch — `[V 2026-10-16]`, same register.
- Demo recorded session (2026-10-19) and OOVS mapping — `docs/demo/`,
  `docs/oovs/`.

### BLOCKED / unavailable this session

- Broad ecosystem scan via search engine (HTTP 402 on 2026-11-06);
  `about.atlos.org` transport error (resolved via `www.atlos.org`);
  Sherlock raw-README CDN misses on `main`/`master` (resolved via the
  repository page render, S1). No further gaps were papered over: any
  freshness claim beyond §5's access dates is NOT made.
