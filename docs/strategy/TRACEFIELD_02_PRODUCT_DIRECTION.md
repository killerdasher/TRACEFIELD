# TRACEFIELD 0.2 — From Tool Output to Verified Intelligence

> **Product direction proposal**, 2026-11-06.
> Prepared by the loop-engine workflow (`--mode deep --max-iterations 3`) on a
> clean checkout of `main` @ `dbdbfd6` (working tree has zero uncommitted
> changes; nothing in this repository was modified by this phase — this
> document is a new file under `docs/strategy/`).
>
> **Method.** Every baseline claim below comes from commands actually executed
> in this session against the real repository (verification log: §14). Claims
> taken from project documents are labelled with their document and date.
> Claims about competitors are taken from `docs/strategy/COMPETITOR_MATRIX.md`
> / `RESEARCH_REGISTER.md` and are **dated primary-source facts**, not current
> values (their own refresh rule applies before quoting in any release note).
>
> **Scope of this document.** Strategy and planning only. It does not
> implement anything, does not change the architecture, adds no dependencies,
> and does not touch the README or other product documents.
>
> **ERRATUM 2026-11-06** (correction from the canonical strategy pass in
> `TRACEFIELD_STRATEGIC_FORESIGHT.md`, same date): this document's Sherlock
> ingest plan targeted `--json` output. A live fetch of the Sherlock README
> on 2026-11-06 shows `--json` is an **input** flag ("Load data from a JSON
> file"); the output options are `--csv`, `--xlsx`, `--txt` (plus the default
> per-username text file). B-01 re-targets accordingly: verify a real,
> version-pinned **`--csv`** output sample first (`--txt` fallback; `--xlsx`
> avoided — not worth a dependency). Verify-before-plan is reaffirmed: one
> skipped format check is what produced this wrong plan.
>
> **AMENDMENTS 2026-11-06, PASS 1** (independent iteration-2 red-team review;
> conflicts resolved in favour of the canonical
> `TRACEFIELD_STRATEGIC_FORESIGHT.md`). Applied in place below: (1) Sherlock
> ingest format re-targeted `--json` → `--csv` (`--txt` fallback) — §7.2 row,
> B-01 row, R-1, §20 question 2 (a final-review pass 2 extended the retarget
> to IS-1/IS-2/§6.1/§6.2/U-1/§7.3 gate 1, which PASS 1 had missed); (2) B-01/B-02
> boundary fixed: B-01 closes at fixture + schema-doc state; parser/skew
> tests land with B-02 against that fixture (the earlier wording required a
> parser to exist for B-01 to close); (3) AC-02 corrected — a Sherlock CSV is
> not expected to carry in-file tool-name/version metadata; name = detection,
> version = declared if present else `unknown` (R-SEC-4), with the
> operator-recorded version+date pinning the fixture doc; (4) AC-06 narrowed
> to J6–J7 — the `s` search palette (J8) is deferred out of 0.2 into the
> canonical H2; (5) B-07 (Maigret) made an explicit 0.2 *stretch* item, not a
> release blocker; (6) §13.2 CLI command count corrected to 46 (was "~37").
>
> **AMENDMENTS 2026-11-06, PASS 2** (independent iteration-3 final review —
> PASS 1 fixed the named findings, not yet every contract they governed):
> retarget completed to the surviving Sherlock-format spots — IS-1 (CSV
> first), §6.1 flow (`--file out.csv`; preflight wording corrected),
> IS-2/AC-02 alignment (name via detection, version if-present-else-
> `unknown`), §6.2 parser name (`sherlock_csv.py`), U-1 (saved CSV);
> R-SEC-3 now refuses only *declared-but-unmappable* identity — absent
> metadata is recorded `unknown` and imports; §6.1 preflight bullet and
> B-02's five refusals re-enumerated accordingly (oversize, unmappable
> format, declared-but-unsupported major version, cross-case attempt, zero
> rows) plus one positive absent-version-imports-as-`unknown` test; B-02
> suite now names the zero-egress (R-SEC-6, no fetch on import) and
> R-SEC-5 echo-sanitation tests, which AC-03 and R-9 cite; §7.3 gate 1's
> skew-test wording moved to B-02; §8.2 Search row and §8.4 J8 row marked
> deferred to the canonical H2; B-08 timeline deferred to the canonical H2;
> convergence note scoped to the ingest-data-dependent items (B-02/B-03/
> B-04/B-07); demo wording corrected to 13 numbered banners (0–12);
> retention label split; `inspect.py:159`→`:160`; Sherlock star count
> dated.

---

## 1. Executive product decision

**Decision.** TRACEFIELD 0.2 commits to **Direction B — the evidence-centric
investigation and provenance workbench — with the interoperability path
(Direction D) absorbed as its ingestion/integration layer**. Direction A
(large OSINT collection platform) is **rejected as a primary direction**, and
Direction C (autonomous AI-driven OSINT investigator) is **rejected outright
for 0.2** with its useful residue (machine-assisted *drafting* behind analyst
review) postponed as a research item.

**One-line thesis for 0.2.** The repository already proves the full evidence
vertical slice — case → evidence → claims → review → report → export →
independent verification (run end-to-end in this session, §14). What separates
"a workbench that stores evidence beautifully" from "a workbench that turns
analysts' actual tool runs into verified intelligence" is one missing layer:
**typed, provenance-preserving ingestion of external tool output into the case
pipeline.** 0.2 builds exactly that layer, for the first one or two upstream
tool formats, end to end.

**Why this decision, in evidence terms:**

1. The collectors own collection. Sherlock (97.7k stars on the 2026-11-06
   fetch — starred counts move; MIT, v0.16.2),
   Maigret (39,220 stars, MIT, v0.6.6), SpiderFoot (23,615 stars, MIT) are
   dated-verified facts in `COMPETITOR_MATRIX.md` §"Verified matrix"
   (2026-10-19 refresh). Rebuilding their decade of collector engineering is
   `COMPETITOR_MATRIX.md`'s explicit "already done by" trap, and
   `RESEARCH_REGISTER.md` §Refresh 2026-10-19 records a compliance boundary
   against Maigret-style bypass features ("no CAPTCHA/anti-bot evasion, ever",
   `FINAL_BUILD_SPEC.md` §7 / D17).
2. The complementary layer is **already credible here**: this session's live
   run of `docs/demo/run_synthetic_demo.sh` exercised case+scope, four
   sources with declared provenance, hash-addressed evidence, origin
   clustering that downgraded apparent independence, contradiction
   candidates, deterministic assessment (`assess-r2`), a reproducibility
   double-check, hash-chained events, report render with the operator's
   author identity, and an export manifest that caught one tampered byte —
   all through the real CLI (§14, demo rc=0, tamper detection exit 1 as
   designed).
3. The missing wrapper is measured, not inferred: `grep` over the CLI surface
   shows **no case-data import or search command** (the only `search` is
   `tools search`, catalogue-only), and `src/tracefield/registry/importers.py`
   is documented as *"Catalogue importers: parse public source lists into
   normalized records"* — i.e. it populates the tool registry, not cases.
   Practitioner pain zones recorded in `RESEARCH_REGISTER.md` §Practitioner
   evidence (Bellingcat 2022 survey, `[V]`: scattered tool outputs, volume
   overload) map directly onto ingest+review.
4. Direction A fails the project's own honesty rules (`RISK_REGISTER.md`
   B1/R1 "feature-inflation trap"; B2 "800+ verified entries is not credible
   at alpha"; real counts from this session's `tools status`: **2,254
   indexed / 10 verified / 0 integrated**, 2,257 licences `UNKNOWN`).
   Direction C collides with the product's determinism pillar —
   `tests/e2e/test_demo_case.py:378` pins *"assessment must be reproducible"*
   and `src/tracefield/core/analysis.py` documents "deterministic,
   explainable assessment" — and with the no-unverified-claims posture
   (`20_ROLE_REVIEW.md` §Explicit non-claims). An LLM-driven investigator
   would put unreviewable probability language inside a product whose entire
   differentiation is refusing it.
5. 0.2 stays small and testable (§5): one import command family, one or two
   upstream formats, zero new dependencies (stdlib JSON parsing), zero new
   DB tables (existing `sources`/`evidence`/`observations` carry ingested
   data), and the remainder of the workflow unchanged because it is already
   shipped and pinned (`tests/e2e/test_demo_case.py`, 332-test suite, CI
   `40860607568` success on `dbdbfd6`).

### 1.1 Direction comparison (the required explicit table)

Evidence sources: `COMPETITOR_MATRIX.md`, `RESEARCH_REGISTER.md`,
`20_ROLE_REVIEW.md`, and this session's own measurements; feasibility column
anchors to what the code already contains (§2.2), not opinions.

| Direction | Practical value | Differentiation | Feasibility vs today's code | Security / maintenance cost | User-demand evidence available? | Evidence-based verdict |
|---|---|---|---|---|---|---|
| **A — large collection platform** | Competes head-on with mature collectors (Sherlock/Maigret/SpiderFoot rows all active, dated-verified) | Low — "Explicitly NOT novel" list covers collection and the catalogue list itself; catalogue counts are not a capability (2,254/2,264 merely `indexed`) | Would start from near-zero code reuse (collectors inside TRACEFIELD = new engine + new evasion/liability surface) | Highest: per-request URLs, credentials, CAPTCHA-adjacent behaviours project policy forbids (D17), catalogue licence grind on top (2,257 `UNKNOWN`) | Strong public demand for *capability*, but not for *this team* to rebuild it — `POST_BUILD_AUDIT.md` local-tool analysis + matrix shows saturated niche | **Reject as primary**. Its only load-bearing role is upstream: collectors whose *outputs* TRACEFIELD ingests |
| **B — evidence-centric investigation & provenance workbench** | Solves the post-collection gap: integrity, review, correction, export, independent verification — the survey's verification-is-challenge pain point (`RESEARCH_REGISTER.md`) | High and *implemented*: lineage, correction history, deterministic assessment, manifest-verified exports (§4.1) | Highest — the full vertical slice already exists and is test-pinned (§2.2 matrix, §2.3 baseline); 0.2 is one addition (ingest) not a re-architecture | Contained to new untrusted-input parsing (§9 planned); per-format cost is small (stdlib parsers) | Direct: survey verification/scattered-outputs pain `[V]` (dated), plus the repository's own operators' workflows reading as U-1…U-5 | **Recommended primary** — it is both the most differentiated and the shortest continuation of what shipped |
| **C — autonomous AI investigator** | Speculative; would need autonomy the product explicitly refuses (review-gated labels, deterministic rules) | Marketing-side "hot", but it would destroy the differential honesty that survives a five-minute trial (`COMPETITOR_MATRIX.md` corollary 3); un-reviewable outputs violate OOVS-mapping posture | Low: requires LLM stack (new heavy dependencies), prompt-attack surface, and undoing the determinism pins (`test_demo_case.py:378`) | Highest liability class: real surveillance consequences of wrong "autonomous findings" — plus a threat model the project has no budget to meet | No demand evidence in the repo beyond hype-adjacent passages; project docs deliberately avoid claiming it | **Reject for 0.2**. Residue worth keeping as user-gated research: machine-assisted *drafting* behind analyst review, parked as B-10 |
| **D — interoperability platform (connect tools ↔ structured investigations)** | Real but narrow if made the product itself: connectors without the analyst workflow reproduce the "tool-output graveyard" | Medium as a *layer*, low as the product (the workbench is what makes connector rows valuable) | Medium-high as a *layer* (§5–§7 design reuses `adapters.py` discipline, `sources`/`evidence`/`observations`); high as a standalone (mapping standards, D14 boundary against STIX/TAXII/CASE-UCO) | Layer-form is the cheapest of the four to secure; standalone would import untrusted bags of formats with no review target | Indirect (the survey's "One tool for all" quote is about workflow, not interfaces) | **Adopt as the ingestion/integration layer inside B (0.2's IS-1…IS-6); postpone its standards-facing remainder** |


**What this document is not:** a roadmap for shipping more integrated tools
(§7 explains its gate: real-format verification precedes ambition), not a UI
rewrite (`TUI_INTERACTION_SPEC.md`'s remediated model is the base), and not a
release claim (nothing in OOVS or publication terms changes here).

---

## 2. Current state, verified and classified

### 2.1 Classification vocabulary

- **VERIFIED** — executed/passed in this session (§14 log cites the command).
- **IMPLEMENTED** — shipped in code, covered by the run suite and/or CI
  (332 / 0 / 0 × {3.11, 3.12, 3.13}, watched run `40860607568`, 2026-10-29);
  inspected this session at source level but not individually re-exercised.
- **EXPERIMENTAL** — present and typed, but explicitly not exercised
  end-to-end by the project's own tests, or shipped as by-design advisory.
- **PLANNED** — named in product docs only (README/`FINAL_BUILD_SPEC.md`);
  no implementation behind it.
- **NOT PRESENT** — no code, no spec, no test.

### 2.2 Capability matrix

| Capability | Class | Evidence |
|---|---|---|
| Case lifecycle + recorded scope authorization | VERIFIED | Demo steps 1 + scope text in output; `case create/authorize/scope` (`src/tracefield/cli/main.py:353/389/456`); scope ledger gate pinned by `TestScopeLedger` (risk register C3/R-C3-1 row, Fixed 2026-10-27) |
| Evidence attach: SHA-256, immutable `0o400` content-addressed copies | VERIFIED | Demo step 3; `evidence attach/verify`; streamed copy (`src/tracefield/storage/repositories.py` per A4/R-A4-6); cross-case guards (risk row A1/R-A1-5) |
| Hash-chained analysis events + chain verification | VERIFIED | Demo step 9; `EventRepo` + `compute_event_digest` (`src/tracefield/core/provenance.py`); `analyze events` output in demo log |
| Origin clustering (origin-r3, ordered k=3/4/5 shingles) | VERIFIED | Demo step 6: two syndicated sources clustered, "skipped 2 source(s)" note, cluster `hypothesis`/`unreviewed` states; `src/tracefield/core/origins.py`; advisory `related_text` edges; + `tests/integration/test_analytical_fixtures.py` |
| Contradiction candidates (dates/hashes/quantities), always `candidate` until reviewed | VERIFIED | Demo step 7: date pair (2026-03-01, 2026-03-15) candidates all severity `candidate`; `src/tracefield/core/contradictions.py` |
| Deterministic claim assessment, decision table, rule version `assess-r2` | VERIFIED | Demo step 8: `SUPPORTED_BUT_UNCONFIRMED` → `CONTESTED` on confirmed contradiction; independence downgrade wording "independence NOT established"; `src/tracefield/core/analysis.py:19`; pinned by `tests/e2e/test_demo_case.py:366-399` |
| Analyst review gate (unreviewed machine suggestions are never evidence) | VERIFIED | Demo flows and assessment caveats; `ReviewState`/`Relation.review_state` (`src/tracefield/core/domain.py:42,186-207`) |
| Reports Markdown/JSON/HTML: caveats, rule versions, escapes, self-contained HTML | VERIFIED | Demo step 10 (HTML written); XSS pins (`tests/unit/test_security_and_core.py` render tests); `src/tracefield/reporting/build.py` |
| Report identity: report_id/revision/supersedes + corrections carried forward | VERIFIED (suite) | `TestReportRegister` (`tests/integration/test_cli.py:398`), `TestReportAuthor` (`tests/integration/test_cli.py:759`), `TestReportAndExport` (`tests/integration/test_storage_and_report.py:384`); commands `report-correct` / `report-history` (`cli/main.py:2010/2051`) |
| Dissemination register + operator author identity | VERIFIED (demo logged) | Demo report shows `**Author:** killerdasher — github.com/killerdasher/TRACEFIELD` (from this operator's `config.toml`, D23); recipient register in export README; scaled claim = per-operator (unset installs say `author not set`) |
| Export + integrity manifest + independent verification | VERIFIED | Demo steps 11–12: `manifest verified — all digests match`; tampered byte → exit 1; `src/tracefield/reporting/export.py:208` (`verify_manifest`), `case-verify` (`cli/main.py:2148`) |
| Adapters (typed boundary): exiftool-meta **integrated**, ffprobe/tesseract spec-only | VERIFIED (integrated path; spec-only = EXPERIMENTAL by design) | `src/tracefield/adapters.py` (D19); E2E ran today with the real exiftool binary (zero test skips); `tests/unit/test_adapters.py:49` ("only reference adapter claims integrated") |
| Scope-before-fetch gate (doubly opt-in network) | IMPLEMENTED | `source add --fetch` requires active grant (exit 4); per-hop redirect re-pin (`src/tracefield/fieldtools/fetch.py:74-120`; `tests/security/test_security.py:90` `test_redirect_hop_is_revalidated_and_repinned`) |
| Username checks (soft-404 rules, 1 req/s, env-gated) | IMPLEMENTED | `src/tracefield/fieldtools/username.py`; provider failure ≠ negative result (`tests/security/test_security.py:261`) |
| Field tools `hash/inspect/ocr` with honest UNAVAILABLE states | IMPLEMENTED | `src/tracefield/fieldtools/inspect.py` (backend allowlist fail-closed at `run_backend`, `inspect.py:160`: `raise ValueError("backend not allowlisted …")` — audit F2 confirmed fixed); OCR untestable on hosts without tesseract (UNAVAILABLE path covered) |
| Adapters `ffprobe-streams` / `tesseract-ocr` | EXPERIMENTAL (typed, non-E2E) | `src/tracefield/adapters.py:168-205` — the project's own `integration_state = spec-only` vocabulary: typed specs exist, the adapter path is *not* exercised end-to-end by the suite; UNAVAILABLE paths tested without the binaries |
| TUI (Textual): 6 workspaces, truthful keymap, `/` filter, `g` palette, back-stack, case picker, cancel | IMPLEMENTED | `src/tracefield/tui/app.py` docstring + `tests/tui/test_journeys.py` (keymap parity `test_docstring_table_matches_live_bindings`, case isolation `test_two_case_isolation_across_views_and_reload`, etc.); T1–T8 remediation per `FINAL_BUILD_SPEC.md` M0/M1 GREEN |
| Catalogue (inert, tiered, dated): 2,264 records | VERIFIED | `tools status` run today: 2,254 indexed / 10 verified, 2,257 licences UNKNOWN; `catalog validate` → "catalogue OK — 2264 records valid"; freshness: `catalog stale` (D22) |
| Planner (guided suggestion) | IMPLEMENTED (advisory) | `src/tracefield/planner.py` (9 capabilities); suggestions only, no automation |
| **Case-data import of external tool output** | **NOT PRESENT** | Only `source add` (manual locator) / `evidence attach` (manual file) / `observation add` (manual free-text) exist; `registry/importers.py` imports *catalogue* records; no command parses a Sherlock/Maigret/SpiderFoot/Nmap-style output into case records |
| Timeline / chronological case view | NOT PRESENT | No `timeline` surface in CLI or TUI (`grep` over `cli/main.py` and `tui/views.py` returns nothing); timestamps exist per-record but are not assembled |
| Cross-record case search | NOT PRESENT | CLI: only `tools_search` (catalogue). TUI: per-list `/` filter only (no cross-workspace/case query) |
| Perceptual hashing / cross-media duplicate detection | PLANNED | README "planned"; `FINAL_BUILD_SPEC.md` FS-25 (P3) |
| Retention / erasure workflow | IMPLEMENTED for the field; workflow PLANNED (amended 2026-11-06, matching the canonical split label) | README "planned"; `Case.retention_policy` field exists (`core/domain.py:109`), no workflow behind it |
| PROV-JSON/STIX/CASE-UCO interchange export | NOT PRESENT (and by design deferred) | D14 keeps PROV conceptual; `FINAL_BUILD_SPEC.md` §7 standing boundary |

### 2.3 Baseline measured in this session (not inferred)

| Check | Command | Result |
|---|---|---|
| Test suite | `.venv/bin/python -m pytest -m "not network" -q` | **PASS** — 332 tests, all dots, rc=0 (3 consecutive full-suite runs; 5/5 solo-file runs of the e2e demo). First invocation of the day produced **1 failure in `tests/e2e/test_demo_case.py::test_synthetic_demo_end_to_end` at line 378 ("assessment must be reproducible") that did not reproduce in 8 further runs** — recorded as suspected flake (§12 R-4) — see K3/B-05 |
| Lint/type | `ruff check src tests` / `ruff format --check` / `mypy src` | **PASS ×3** — "All checks passed!", "61 files already formatted", "Success: no issues found in 38 source files" |
| Catalogue | `catalog validate` / `tools status` | **PASS** — 2,264 valid; tiered counts as above |
| Demo + export/verify | `bash docs/demo/run_synthetic_demo.sh` | **PASS** — rc=0 through all 13 numbered banners (0. doctor + steps 1–12); export manifest verified; deliberate tamper detected (exit 1) |
| CI (GitHub, fresh `gh run list`, 2026-11-06) | `gh run list --limit 6` | **PASS** — CI `40860607568` success + CodeQL `40860607746` success on HEAD `dbdbfd6` (2026-10-29); scheduled CodeQL `41457478434` success (2026-11-02); Dependabot updates success (2026-11-02). No new push-triggered runs since. HEAD unchanged: `git log` shows `dbdbfd6` tip, ahead=0/behind=0 |
| Static-anomaly checks inspected (fixed-in-code audit items) | source reads | **PASS** — per-hop redirect re-pin (`fetch.py:74-120`), `run_backend` fail-closed allowlist (`inspect.py:148-159`), newer-schema refusal (`database.py:460-467` raises `SchemaVersionError`) |
| pip-audit + fresh-venv wheel smoke | background in this session | see §14 for final states; both were green on the identical tree one week earlier (`docs/strategy/PHASE_12_REPORT_AUTHOR.md` §3, 2026-10-29) |

### 2.4 Documentation-vs-code contradictions found in this run

| # | Finding | Verdict |
|---|---|---|
| K1 | `POST_BUILD_AUDIT.md` §4 G7 says fresh-venv wheel smoke **FAIL** and §3 T-table lists T1–T8 violations; `FINAL_BUILD_SPEC.md` milestones mark these **GREEN (Phases 6–8)**. Re-checked in code this session: the wheel ships `data/` (risk row A1/R-A1-4 documents the Phase 7 fix + fresh-venv pass), and TUI bindings/docstring agree (keymap-parity test exists and passed today). | Both are **historical point-in-time records**. No product change needed; the newer milestone status supersedes the audit snapshot. This document refreshes the state snapshot to 2026-11-06 (§2.2/§2.3) |
| K2 | `RISK_REGISTER.md` §"Emerging (this implementation pass)" rows FR-1/F3/T7/cancellation look **Open**, but the section's own header says rows are "audit-time state (2026-10-19)" and that Phase 6–10 work superseded them. Code today carries the fixes (§2.3). | Same class as K1: snapshot rows, not live status. The only risk rows genuinely open today: A2/R-A2-3 (render-path worker offload), C4/R-C4-3 (pHash), C1/R-C1-4 (path redaction residual), plus user-gated FS-26/27 |
| K3 | This session's one-off e2e reproducibility failure (§2.3) is a **new finding not yet recorded anywhere** in the repository. Its verification evidence lives in `/tmp/opencode/looprepro/` only. | Recorded here (§12 R-4) for the backlog; reproduction/instrumentation is backlog P1 (B-05) |
| K4 | `docs/strategy/DECISIONS.md` D14 ("PROV stays conceptual, no STIX/TAXII/CASE-UCO") constrains several tempting 0.2 phrases; nothing in `COMPETITOR_MATRIX.md`'s differentiation section contradicts it. No conflict found in the direction chosen. | Consistent |

---

## 3. Target users and practical use cases

**Who this is actually for** (honest lens, per the project's own evidence):

1. **Technically comfortable investigators** — the terminal is a tool, not a
   barrier; they already run Sherlock/Maigret/ExifTool in their own
   environment and need the *workbench* around those runs.
2. **Verification-minded journalists / fact-checkers / OSINT analysts** who
   must show *why* they believe something: they need evidence, not vibes —
   and they need to correct published conclusions without losing history.
3. **Single-operator / small-team workflows** — this tool is
   deliberately local-first; it is not a shared cloud case system, and 0.2
   does not change that (data stays `0700`-scoped on their machine,
   and `src/tracefield/config/settings.py:78` `ensure_dirs()` enforce it).

**Who it is explicitly not targeting at 0.2** (stated, not apologized):
GUI-native users who won't leave a browser — `RESEARCH_REGISTER.md` quotes
the Bellingcat 2022 survey's "only a quarter of respondents knew how to use
the command line" `[V]`; this product consciously reaches the technically
comfortable minority and states the trade-off honestly rather than promising
a web dashboard (§8, TUI-16).

**Practical use cases the 0.2 slice must serve end to end** (all already
possible, all easier once ingestion exists):

- **U-1 — Social-account inventory from an operator's Sherlock/Maigret run.**
  Operator runs the tool themselves (this product never executes it in 0.2 —
  §7), imports the saved CSV (Sherlock; Maigret dossier-JSON later), triages
  which found handles are worth adding
  as `Source`s of the case, and relates them to claims.
- **U-2 — Media/document triage on existing exiftool integration.** The one
  `integrated` adapter already proves the execute-path; ingestion joins it
  with review and reporting (same records, same caveats).
- **U-3 — Claim work-down memo**: assess claims against evidence with
  independence analysis, then `report --format markdown/html` with the
  analyst's identity, caveats, and corrections lineage.
- **U-4 — Evidentiary packet**: `case-export --recipient` a redacted,
  manifest-bound bundle a third party can verify independently — the
  sha256-based manifest re-checks with plain `sha256sum` (per
  `COMPETITOR_MATRIX.md`: "re-verifiable from the case directory without the
  tool"), or with `case-verify` when TRACEFIELD is available — plus a
  traceable shipment record.
- **U-5 — Recipient correction follow-up**: analyst receives pushback from a
  recipient → `report-correct` appends a correction → re-render carries the
  correction forward; the register answers "who received which revision".

---

## 4. Product differentiation thesis

### 4.1 What is genuinely available as a differentiator

Capabilities from the task's list, mapped to reality:

| Differentiator candidate | State | Honest assessment |
|---|---|---|
| **Evidence lineage** | Present, strong | Every record carries integrity data (`sha256` evidence copies, `prev` digest chain on `analysis_events`, `evidence verify`, DB triggers for same-case endpoints). NOT LOCKED: `tool_fingerprint` still unbound in digests (FS-24, P3) |
| **Reproducible case exports** | Present, strong | Redaction, manifest-over-final-bytes, recipient register; independently verify-able (`case-verify` after one tampered byte → exit 1 in the live demo). Distinct from archiving — the manifest is a *verification contract* |
| **Report correction history** | Present (v3, Phase 11/12) | `report_id`/revision/supersedes chain; corrections appended, never rewritten, travel with lineage; register plus operator-driven notification (not automated) |
| **Source independence analysis** | **Partial — biggest honest 0.2 differentiator upside** | Origin clustering exists per case; **independence downgrade wording is pinned by tests** ("2 of 3 confirmed origins appear in an origin cluster; apparent independence may be overstated…"). But it is *text-similarity-based*; nothing clusters across fetches-metadata/multiplicity, and ingestion doesn't yet record "these N rows came from one tool run" as a *provenance signal among sources* — 0.2 closes precisely that gap (§5, §6) |
| **Claim-evidence graphs** | Partial (data model solid; view missing) | `relations` with `evidence_ids` exist end-to-end and the TUI lists them; no graph view, no cross-case visual. Restrained 0.2: no new viewer; improve *completeness* (imported rows arrive as linked triples) rather than a graph UI |
| **Temporal intelligence** | Partial, honest upside | Per-record timestamps exist (first_seen/collected/published distinction in `Source`; `returned_at` in `Observation`); contradiction candidates already compare dates. NOT PRESENT: timeline view and time-windowed selection. Restrained 0.2: add a read-only chronological view in TUI + CLI, not a time machine |
| **Contradiction review** | Present | Wired candidate severity + `analyst must resolve` semantics (live demo step 7–8) |

### 4.2 What must NOT be marketed as innovation

Verbatim rule from `COMPETITOR_MATRIX.md` §"Explicitly NOT novel — never
market these as innovations": content hashing; EXIF/ffprobe metadata reading;
tesseract OCR wrapping; "a big list of OSINT tools"; username enumeration;
case folders; content-addressed storage; SQLite; JSON output; redaction of
secrets. **Catalogue size is a count, not a capability** (§2.2: 2,254 of
2,264 rows are merely `indexed`; 0 integrated *catalogue rows* — and the
integration truth that does exist lives in the adapter registry, exactly one
`integrated` adapter).

### 4.3 The thesis, in one paragraph

> Competitors store tool output; after that, an analyst's file hygiene and
> memory are the only evidence system. TRACEFIELD's claim is the layer
> **between collection and the report**
> (positioning corollary 1, `COMPETITOR_MATRIX.md`), wired from the case's
> recorded scope, through hash-addressed evidence, analyst-reviewed
> independence logic, correction-history reporting, into exports whose
> integrity anyone can re-check without this tool. Its catalogue's honesty
> is that it counts what it has *not* verified. Every boundary it refuses
> (probability language, evasion, marketing numbers, auto-attribution) is a
> boundary the domain has repeatedly been burned by, recorded in
> `20_ROLE_REVIEW.md`'s challenged assumptions.

---

## 5. TRACEFIELD 0.2 scope and explicit non-goals

### 5.1 The 0.2 vertical slice

> **Smallest coherent, testable slice: "external tool output in, verified
> intelligence out".** One ingestion command family that maps an upstream
> tool's saved output into the case pipeline *with full provenance*, one or
> two upstream formats verified from real upstream sources, and the existing
> horizontal workflow left unchanged (it is already proven).

**In scope (IS-1 … IS-6):**

| ID | Item | Already-exists anchor |
|---|---|---|
| IS-1 | `case-import` command family (see §6/§7 for the priority order) reading an operator-supplied **saved output file** (CSV first — amended 2026-11-06; Maigret dossier-JSON second), storing the original file verbatim as content-addressed evidence | `evidence attach` mechanics (`repositories.py` attach path), byte-identical storage, `0o400` |
| IS-2 | Typed, version-aware normalization of rows into `Observation`s (raw verbatim + typed view) with tool name via detection and version declared-in-file if present, else `unknown` (amended 2026-11-06, aligned with AC-02 — a CSV header carries no tool metadata), `acquisition_method="tool-import"`; **fail-closed on declared-but-unmapped format/major version only** | `Observation.tool_name/tool_version/raw_ref` exist (`core/domain.py:144-155`); honest-error pattern matches `catalog validate` |
| IS-3 | Analyst triage surface: per-row review into (a) **promote** a row to a case `Source` (explicit command, never auto), (b) dismiss with recorded reason, (c) defer. Rows arrive **unreviewed** and are never evidence until review | `Source` has no auto-creation path today; review-state vocabulary (`ReviewState`) already exists and is used on `Relation`/`OriginCluster` — reuse in the same semantics, no schema change |
| IS-4 | Origin/independence integration: imported rows participate in existing `analyze origins` and `analyze claim` caveats verbatim; per-run provenance becomes a part-of-origin-cluster signal candidate | `ClusterRepo` + cluster wording (`origins.py`, analysis caveats); new signal only *adds candidate edges* in the existing `hypothesis → review` flow, never auto-confirms |
| IS-5 | Temporal context: `first_seen_at` aligned to the tool run; contradiction candidates already process dates (no new logic needed to benefit) | `Source.published_at/first_seen_at/collected_at` (`core/domain.py:114-127`) |
| IS-6 | TUI + CLI surface with full parity, honest states, no auto-labels; background job treatment following TS-3 | §8 spec; existing cancel/progress model |

**Explicit non-goals (NG-1 … NG-10), each with the reason:**

| ID | Non-goal | Reason |
|---|---|---|
| NG-1 | **No tool execution added in 0.2 beyond today's list** — no Sherlock/Maigret/SpiderFoot *runner* | Run/execute semantics already exist for exiftool only after its E2E test (`adapters.py` D19). Running network tools would need `needs_network=True` specs + full telemetry; the same value arrives with import (operator runs their tool) at a fraction of the risk |
| NG-2 | **No auto-claim synthesis** (machine-generated claims from imported data) | Assessment honesty: "labels are workflow states, not probabilities of truth" — auto-claims would inflate INSUFFICIENT_EVIDENCE into confident text; claims stay analyst-authored |
| NG-3 | **No LLM / autonomous AI investigator** in 0.2 | Collides with determinism and evidence-reviewability (§1.4); research item parked (§10 B-10) with an explicit analyst-review lid |
| NG-4 | **No new dependencies** — parsing via stdlib `json`/`csv` only | Project dependency discipline (CONTRIBUTING; minimal-deps rule); any future dependency must go through its own justification process |
| NG-5 | **No web UI / dashboard** | §8, TUI-16; evidence today does not demand it |
| NG-6 | **No STIX/TAXII/CASE-UCO/PROV-JSON export** | D14 standing boundary (conceptual mapping only) |
| NG-7 | **No graph viewer / force-directed canvas** | Fake maturity: the *data* exists in TUI listings; a viewer adds several hundred UI-quality risk for one case in a hundred; revisit only with analyst demand evidence |
| NG-8 | **No app-level auto-correction of upstream data** (not even obvious-ish typos) | Adapters never assert conclusions (D19); corrections belong in *this* product's correction register, tied to reports — not silently rewriting the record |
| NG-9 | **No bulk mode / parallel fetching** in ingestion. | "`no bulk mode`" is a standing product rule (`doctor` output, username checks); ingestion likewise must cap size + rate |
| NG-10 | **No automated recipient notification** of report corrections | Stated scope limit of OOVS-09 promotion (`docs/oovs/OOVS_MAPPING.md`); remains operator-executed |

### 5.2 Why this slice is "smallest coherent"

One import family touches: provenance preservation (evidence store), typed
normalization (observation store), review (analyst gates), source-independence
(clustering), temporality (timestamps), reporting/export/verification (the
TUI/CLI surfaces) — i.e. every layer needed for "from tool output to verified
intelligence", with **zero new architectural layers** and a testable
acceptance list (§11). Dropping any one of IS-1…IS-6 breaks coherence: import
without triage recreates the unreviewed-data problem; triage without
provenance recreates the headerless-paste problem; provenance without
independence signals exploits syndication holes; any of it without report/
export changes nothing the analyst can hand to anyone else.

---

## 6. Data flow and architecture proposal

### 6.1 Flow (0.2 target, no redesign — additive on the shipped pipeline)

```
operator tool run (their machine, their burden of scope)
        │  saved output file (CSV / other formats later)
        ▼
tracefield case-import <case> --file out.csv --tool sherlock   (IS-1)
        │  1. fail-closed preflight:
        │     - file exists within size cap (max_fetch_bytes-style),
        │     - format detected; declared-but-unmappable version → refuse
        │       with exit 3 (usage); ABSENT version ⇒ recorded `unknown`,
        │       not a refusal (R-SEC-4; amended 2026-11-06); the
        │       NOT_FOUND(2) / NETWORK(4) exit meanings stay untouched
        │  2. raw-first: file copied verbatim → EvidenceItem
        │     (sha256, 0o400, acquisition_method="tool-import")
        │  3. typed rows: per record → Observation(tool_name/tool_version,
        │     raw_ref → row JSON, returned_at = recorded run/analysis time)
        │  4. import event appended, hash-chained (compute_event_digest)
        ▼
triage (analyst, IS-3): promote → Source | dismiss(reason) | defer
        │  (promote records the row's origin tool+version+ran_at honestly; it
        │  stays inside the same case; `relation add --from source --to claim`
        │  afterwards flows through the EXISTING review/confirm workflow)
        ▼
existing horizontal slice (all pinned by today's tests)
        analyze origins → analyze claim (assess-r2) → analyze contradictions
        → report (md/json/html) → report-correct/history
        → case-export --recipient → case-verify (independent)
```

### 6.2 Proposed module boundaries (naming, not prescription)

| New/changed surface | Purpose | Respects |
|---|---|---|
| `src/tracefield/ingest/` (new package, mirrors `registry/` style) | format-version probe (`detect_format` returns a typed spec or a typed refusal), row mapping to `Observation`, no business rules inside parsers | `importers.py` doc rule: "UNTRUSTED DATA — validated by pydantic and never modifies application behavior or executes code" |
| `src/tracefield/ingest/sherlock_csv.py` (amended 2026-11-06 from `sherlock_json.py`), `maigret_json.py` (0.2 targets; add only after upstream format verification per §7) | one parser per format+major version, table-driven | adapter spec style of `adapters.py` (typed, fail-closed) |
| `cli/main.py` `case-import` / `case-import status` / `source promote` typer commands | the analyst-facing flow | existing exit-code contract 0/1/2/3/4/5 |
| `tui/views.py` review-queue overlay | §8 spec | truthful-chrome rules (TS-2) |
| **No DB migration**: `sources`, `evidence`, `observations`, `relations` suffice; provenance strings on rows (`collection_agent`, `raw_ref`, `acquisition_method`) carry import identity | zero schema-version bump | additive-only migration discipline from Phase 11 |

### 6.3 What deliberately does NOT change

Schema version (`v2` stays), exit-code contract, URL policy, adapters
registry (D19), scope-gate rules, `analyze` decision table, report/export
rendering, the OOVS mapping, security posture. Anything beyond ingest is out
of scope by §5.

---

## 7. Integration and adapter priorities

### 7.1 The existing contract (`src/tracefield/adapters.py`)

D19's four pillars hold today (verified by reading code, not just docs):
**typed** (`AdapterSpec` frozen dataclass, fail-closed against
`ALLOWED_BACKENDS = {exiftool, ffprobe, tesseract}` at construction *and* at
call time — `inspect.py:160` raise confirmed), **honest lifecycle**
(`integration_state = integrated` iff E2E-exercised by our suite; health is
only "version probe answered right now", never "healthy"), **proposal-free,
local-only** (user-invoked; future network specs need `TRACEFIELD_ALLOW_NETWORK`
+ explicit per-call opt-in), **raw first** (`AdapterResult` uninterpreted,
provenance block, "interpretation stays a reviewable claim layer").

**Import vs execute — the 0.2 distinction.**
- *Execute* path (exists, one integrated adapter): TRACEFIELD invokes the
  binary on a local file. High control, high risk per new backend (arg
  injection, output caps, licence of bundled binary, version skew), and it
  makes TRACEFIELD responsible for the tool's network behaviour — the reason
  Sherlock-type tools don't fit that path at 0.2 (NG-1).
- *Ingest* path (0.2's addition): TRACEFIELD parses a **saved output file the
  operator already produced**. TRACEFIELD never touches the network on the
  operator's behalf for it, the operator keeps full control of scope/legality,
  and provenance still lands in the case (which tool, which version, when).
  This is the correct boundary for username/OSINT-collection outputs whose
  *collection* is legitimately the operator's responsibility.
- A catalogue entry remains exactly what `COMPETITOR_MATRIX.md` says: a link,
  not an integration. Integration truth lives in the `ADAPTERS` registry +
  `integration_state`, and 0.2 adds an analogous typed registry entry only
  for *formats*, after they verify E2E.

### 7.2 Candidate integrations (verified upstream facts only)

| Upstream | Licence (verified, dated) | Output format (verified facts) | Integration verdict for 0.2 |
|---|---|---|---|
| **Sherlock** (`sherlock-project/sherlock`, v0.16.2 2026-09-08) | MIT `[V]` (LICENSE text, 2026-10-19) | CLI with `--csv`/`--txt`/`--xlsx` documented output and `--json` as an input flag (amended 2026-11-06; header erratum); README warns about broken third-party packages and `--ignore-exclusions` false positives — **must be reflected as a caveat on import, not silently normalized** | **FIRST candidate (import)** — CSV/TXT, single flat site-status records, MIT, high analyst value for U-1; no network provenance required by TRACEFIELD |
| **Maigret** (`soxoj/maigret`, v0.6.6 2026-09-18) | MIT `[V]` | JSON dossier per username; auto-updating site DB embedded in output; **README advertises CAPTCHA/Cloudflare-bypass features — out of scope for TRACEFIELD** (RESEARCH_REGISTER compliance note; D17) | **Second candidate (import)** — only the dossier-JSON content is normalized; bypass-related fields are ignored-with-record, never used; value: the 5,203-enabled-sites corpus overlaps Sherlock's website reach |
| ExifTool (already integrated) | Artistic/GPL dual upstream; GitHub mirror GPL-3.0 — discrepancy recorded `[V]` | multiple formats+`-json` | execute path exists; no new work |
| SpiderFoot (`smicallef/spiderfoot`, MIT, maintenance contested) | MIT `[V]` | "200+ modules", SQLite scan store, CSV/JSON/GEXF exports | **Postponed beyond 0.2** — import formats are heavier (correlation graphs), maintenance contested, modules vary; do not hinge the vertical slice on it |
| holehe / theHarvester | GPL-3.0 / GPL-2.0 `[V]` | JSON/CLI outputs | Later import-only candidates; parsing a *saved* output file is not code distribution, so the licence of the upstream binary is not a blocker — recorded attribution stays attached to imported rows |

### 7.3 Verification gates before any implementation may claim an integration

1. **Format verification from primary source** (task-required, deliberately
   not done inside this planning session to keep the loop read-only):
   fetch/obtain a version-pinned actual sample of the tool's `--csv`
   output (fallback: `--txt`; amended 2026-11-06 per the header erratum),
   record its schema at field level, and pin the sample as a committed
   fixture. Gate: fixture + field-level schema doc + rotation policy are
   committed and the full suite stays green; parser and version-skew tests
   land with B-02 against that fixture (boundary amended 2026-11-06).
2. **Licence review**: MIT is clean for parsing saved files — the
   ingestion-relevant hazards are upstream disclaimer strings and
   cross-source attribution (the `data/catalog/source-manifest.json`
   pattern), which the import records per row.
3. **`integration_state` honesty**: verdict `import-integrated` only after
   the E2E ingest test runs against the stored real-sample fixture;
   `spec-only` until then (wording choice left to the implementer; the
   honest vocabulary obligation comes from `adapters.py`).
4. **No network of any kind inside ingest tests** — the fixture is the
   sample file; zero live probes (standing `NETWORK`-marker rule).

**Priority call:** Sherlock first (flat, single-output, MIT, widest reach),
Maigret second (dossier normalization; careful with bypass metadata
recording). Nothing else before 0.2 ships its first integration — the point
is the layer, not a connector count (mirrors the rule that catalogue count ≢ capability).

---

## 8. TUI design specification (restrained evolution)

### 8.1 Principles carried forward (unchanged)

The remediated TUI (`src/tracefield/tui/app.py` + `tui/views.py`, pinned by
`tests/tui/test_journeys.py`) already enforces: truthful chrome
(keymap-parity test), truth-in-data-labelling, progress that only reports
real counts, case as unit of view, progressive disclosure, no manipulation,
and the every-feature-has-a-CLI-path rule. 0.2 **adds no new framework and no
keyboard re-learning**; the whole evolution lives inside the existing
six-workspace model.

### 8.2 Where the ingestion and review work lands

| Task-requirement surface | 0.2 treatment |
|---|---|
| Navigation | Unchanged: `1`–`6` jump, `g` palette, `c` case picker, `Esc` back-stack (all test-pinned). 7th workspace deliberately **not** added; ingestion surfaces inside existing workspaces |
| Case overview (Mission) | Shows `last import` block (tool, version, row counts, evidence hash) once any import exists; `case-import status`-equivalent data |
| Evidence inspector | Existing detail pane gains the imported file's format/version/version-skew states (raw verbatim always inspectable) — the pane already shows hash/verifier state |
| Claims/relationships | Unchanged; promoted sources appear as ordinary case sources — **visible honesty, not a special class** |
| Timeline (new, read-only) | `Mission` gains a toggle-free chronological strip: sources+evidence+observations+analyst events interleaved by timestamp; pure view of existing data; no auto-statistics |
| Search (small, honest) | **AMENDED 2026-11-06 — deferred to the canonical H2** (canonical `case search` + case-wide jump-to-record palette row); 0.2 keeps the per-list `/` filter; exact-prefix/bounded matching only, no fuzzy matching |
| Keyboard interaction | All new keys follow TS-2 parity: not advertised until bound; `?` overlay updated by the same tests |
| Background jobs | Batch import/triage-wrap/verify reuse TS-3 states (running/count/finish/cancelled); **implementation takes the trigger path** of accepted risk A2/R-A2-3 (worker offload) at batch sizes, not a rewrite |
| Cancellation | Ctrl+C cooperative cancel already modeled (TS-3); import adds `cancelled → no partial rows` (import is itemized; the event list records what was applied) |
| Reports view | Reuse `Runs`/existing report surfaces; no report-authoring UI invented in 0.2 |

### 8.3 TUI design rules specific to 0.2

1. **TUI-1 (truthful effects):** an imported batch shows "imported N rows → M
   observations + file hash" states only — never spins while waiting on a
   parse, never implies network activity.
2. **TUI-2 (Honesty):** the "ingested" label never hides source-promotion
   review requirements; rows show `[unreviewed]` till triaged, consistent
   with the machine-suggestions-are-not-evidence rule.
3. **TUI-3 (Parity):** every TUI ingest action has an exact CLI counterpart
   (J6 cross-check vs CLI in journeys test, mirroring J2's existing pattern).
4. **TUI-4 (No-onboarding):** no wizard mode; the palette/overlays suffice;
   first-run guidance stays the Mission empty-state text (honest, short).
5. **TUI-5 (Theming):** new states use the existing theme tokens
   (`tui/state.py` `build_themes`), never raw hex; `NO_COLOR` degrades
   (already test-pinned: `test_status_words_survive_no_color`).
6. **TUI-16 / NG-5:** no web dashboard until analyst evidence demands one
   (none exists in the current records); terminal-first is a design
   decision, not a milestone gap.

### 8.4 New journeys (fresh acceptance assertions, same style as TS-6)

| ID | Journey | Must hold |
|---|---|---|
| J6 | Import a saved Sherlock-style fixture → Mission shows last-import block → Evidence: raw file present + hash → triage overlay: promote 2, dismiss 1 with reason → claims view lists the 2 as sources → report includes them | Every triage state recorded; dismiss-without-reason refused; numbers never inflated; no rows from cases other than active case |
| J7 | Import one large fixture (many rows) → Ctrl+C mid-run on the TUI side → op state `cancelled` within the TS-3 window; events/journal entries completed before the cancel are retained and labeled as such, none beyond the last completed unit; Runs records the cancel | Itemized-by-event retention only; partial progress never claims completion; no bulk/parallel fetching introduced to do it |
| J8 | **AMENDED 2026-11-06 — deferred out of 0.2 to the canonical H2** (search palette; row kept for spec continuity). Same fixture rows → `s` search by locator prefix → jump → detail hint that origin cluster exists → `analyze claim` caveat visible | Search never invents rows; count shown |

---

## 9. Security and privacy requirements (0.2)

All current boundaries are inherited unchanged (SSRF deny-list + per-hop
pinning; fail-closed backend allowlist; terminal sanitation; redaction
redact-then-manifest; `0600` DB / `0700` dirs; scope-gate-before-fetch;
"no evasion, ever" D17). Ingestion is 0.2's biggest new attack surface and
gets its own required set:

| ID | Requirement | Anchors to existing mechanism |
|---|---|---|
| R-SEC-1 | **Untrusted-file parser hygiene**: parse via stdlib deterministic `json` into pydantic-typed shapes; no eval, no code interpretation, no recursive regex, no zip-deep semantics; bound row count + field sizes | mirrors `importers.py` doc rule "never modifies application behavior or executes code" + `run_backend` output caps |
| R-SEC-2 | **Size caps**: ingest file size limit enforced **before** parse (default aligned with `max_fetch_bytes` setting = 10 MB; refuse larger with exit 3 + explicit message); also cap evidence copy memory (already streamed, keep it that way) | `Settings.max_fetch_bytes`; A4/R-A4-6 streamed copy |
| R-SEC-3 | **Fail-closed unknown data**: *declared-but-unmapped* `format`/`version`/`tool` identity — refuse the whole file, exit 3, error names what was unmappable; never partially imported. **Absent** tool/version metadata is not a refusal case: it is recorded `unknown` and imports (R-SEC-4; amended 2026-11-06 — a CSV header carries column names, not tool metadata). Unknown *extra fields* inside a known, type-safe shape are not a refusal case: they are accepted but recorded as an import flag in the Observation's summary, never silently dropped | "hard fail instead of half-truth" project posture; `SchemaVersionError` style |
| R-SEC-4 | **Provenance cannot be forged upward**: rows arrive as Observations with `returned_at` = the run's own declared metadata only if present; the *file's* sha256 and the tool name/version are recorded from what the file actually declares; absent tool/version metadata is recorded as unknown, never guessed — nothing ever claims the tool returned what the file does not show | adapters' `provenance()` honesty; observation wording in `observation add` ("raw return — not a verified fact until reviewed") |
| R-SEC-5 | **Secrets at rest**: imported raw outputs may contain cookies/tokens; they stay in the immutable content-addressed copy and are never echoed unredacted into TUI/excerpts; redaction happens only at export (post-redaction manifest, per C4/R-C4-2) and reports carry the redaction caveat — the raw record itself is never silently rewritten at import | `security/redact.py` at export + report caveats; `sanitize_for_terminal` at TUI/CLI render |
| R-SEC-6 | **No URL fetch on import**: URLs found inside tool output are recorded as candidate sources only; `source add --fetch` semantics (opt-in + scope grant + URL policy) stay their own action | fetch gate (C3/R-C3-1 promotion) + `validate_fetch_url` |
| R-SEC-7 | **Cross-case isolation preserved**: imports operate only on the named case; no TUI view mixes cases (already test-pinned); no promotion to a source outside the case exists | DB triggers + app-level checks (`A1/R-A1-5`) |
| R-SEC-8 | **Review actions are auditable and case-scoped**: promote/dismiss/defer are recorded as hash-chained events under the same case-scope enforcement; promote is analyst-triggered (no network, no rate-limit dependency); dismiss without a recorded reason is refused | scope+event discipline of Phase 11 |

**Privacy review of the slice specifically:** no new data leaves the
machine (local file handling only); no network on import; no automatic PII
enrichment; source privacy labels stay operator-controlled (set/edited by
the operator, never inferred by the tool). The biggest **privacy** risk in
this slice is operator over-expectation that "imported" ⇒ "verified" —
addressed by §8 TUI-2 and §10's acceptance gaps, not by automation.

---

## 10. Prioritized implementation backlog (0.2)

Acceptance criteria are test statements a future phase actually runs; any
item whose acceptance is unverifiable in code is `NOT PRESENT` until it is.

| ID | Pri | Item | Acceptance (testable) |
|---|---|---|---|
| B-01 | P0 | Format verification gate for **Sherlock**: obtain/record one version-pinned real Sherlock `--csv` sample (`--txt` fallback; operator-supplied fixture; no live run required by TRACEFIELD), document the schema at field level in a doc file, pin it as a fixture (amended 2026-11-06) | **B-01 closes at fixture + schema-doc + rotation-policy state** (parser tests cannot precede the ingest package — iteration-2 review); `tests/unit/test_ingest_sherlock.py` lands with **B-02** against this fixture: a mutated fixture (unknown extra field) is *accepted-but-flagged* only if the field is additive and typed-map-safe — otherwise refused; all per R-SEC-3 — **SHIPPED 2026-11-07** (`d5d126e`, fixture + `docs/ingest/SHERLOCK_CSV_SCHEMA.md`; trap verified live: `--csv` is a boolean flag) |
| B-02 | P0 | `src/tracefield/ingest/` package with `detect_format` + `sherlock_csv` mapping (amended 2026-11-06 from `sherlock_json`) to Observations, raw-first Evidence storage, import event append, fail-closed pre-conditions (R-SEC-1..4) | Suite: 1 fixture-load test, 5 refusal tests (oversize, unmappable format, declared-but-unsupported major version, cross-case attempt, zero rows refusal — re-enumerated 2026-11-06) + 1 positive test that *absent version* imports recorded as `unknown`, 1 hash-chain-closure test, 1 cross-case-refusal test, plus the zero-egress pin (import performs no fetch/write — R-SEC-6) and the R-SEC-5 terminal-echo sanitation test — **SHIPPED 2026-11-07** (`fd63412` Phase 16; 23 ingest tests; extra columns accepted-but-flagged per R-SEC-3 amendment) |
| B-03 | P0 | `case-import` + `case-import status` + `source promote/dismiss` CLI commands with exit-code contract and `--json` parity | `tests/integration/test_cli.py::TestIngest`: (a) `promote` without review of a *dismissed-by-reason* record is refused; (b) promote lands a `Source` row with recorded provenance and adds an event; (c) `dismiss` without reason → exit 3; (d) final `analyze claim` output changes exactly when the analyst builds a new relation through the existing flow (baseline equality check, per `test_demo_case.py:378` pattern) — **SHIPPED 2026-11-07** (`fd63412` Phase 16; grammar `case-import --file <path>` per D27; also carries `source defer`; no `--tool-version` flag per D28) |
| B-04 | P0 | Sherlock E2E integration: real end-to-end demo addition (fixture-based) — import, triage, relate one claim, assess, report, export, verify | `tests/e2e/test_ingest_demo.py` (mirrors `test_demo_case.py` honesty): manifest verifiable after import event; report contains the promoted sources' provenance strings; tampered byte detection still passes — **SHIPPED 2026-11-08** (`5e948bd` Phase 17; E2E also caught and fixed a promote off-by-one in `raw_ref` record addressing) |
| B-05 | P1 | Flake instrumentation + test isolation hardening: the session's one-off reproducibility failure (§2.3) gets reproduced/diagnosed or instrumented with a documented attempts loop | Either root cause fixed with a targeted test, or a documented no-repro note with the attempt count N and the test left intact — never left silent; outcome recorded in `RISK_REGISTER.md` — **SHIPPED (instrumented) 2026-11-07** (`9069a13` Phase 14, decision D26: 18 consecutive clean runs; re-open on ≥2 hits per 50 runs) |
| B-06 | P1 | TUI: triage overlay + Mission last-import block + Journeys J6–J7 (amended 2026-11-06: the `s` search palette + J8 deferred out of 0.2 — canonical H2 row instead) | `tests/tui/test_journeys.py` additions; keymap-parity test updated with any new bindings; no-key-without-action assertions stay green — **SHIPPED 2026-11-08** (`48f8991` Phase 18; mission `t`/`i` bindings; J7 goes through the real submit path with committed-batch cancellation per D28; honest-partial labelling `incomplete=cancelled rows_written=<N>`) |
| B-07 | P1 | **Maigret** format verification + dossier parser (post-Sherlock; **STRETCH inside 0.2** — do not block the release on it, amended 2026-11-06), bypass-field handling per RESEARCH_REGISTER compliance note (ignore with recorded reason, never used) | Same gates as B-01/B-02; parser fixture named for Maigret 0.6.x; correlation fields normalize at candidate severity only |
| B-08 | P2 | Temporal read-only timeline work — **deferred to the canonical H2 horizon** (amended 2026-11-06; canonical §16 governs; not part of the 0.2 release scope): Mission strip + `timeline` CLI read command for re-assembly of existing timestamps, no new logic | Snapshot-vs-count assertion; lazy rendering off the render path (A2/R-A2-3 measured in canonical H0-3); zero new state mutation |
| B-09 | P2 | A2/R-A2-3 trigger resolution: move heavy import + verify + export off the UI thread into Textual workers per TS-3 (achieves worker offload without rewriting architecture) | Cancel-state within 500 ms preserved at J7; no direct DB call in `compose()` path at import batch sizes (static test) |
| B-10 | P2 | Research bookmark (no implementation): LLM-assisted *draft* suggestions behind explicit analyst review — research the cost of preventing suggestion text from appearing to *be* assessment | One-pager in `docs/strategy/` with a threat analysis against R-SEC-4 / the probability-language rule; a DECISIONS.md entry deciding for or against ever doing it |
| B-11 | P3 | Carry-over never-blocking items preserved as-is: FS-23 (licence-UNKNOWN grind, cli_tool tier first), FS-24 remainder (`tool_fingerprint` binding decision), FS-25 (pHash), C1/R-C1-4 path redaction residual | untouched priorities; any 0.2 work around them must not silently drop or re-scope them (`FINAL_BUILD_SPEC.md` M2/M3 discipline) |

---

## 11. Testable acceptance criteria for 0.2

"0.2 is done" means all of AC-01…AC-11 pass, not none-but-some:

- **AC-01** — `pytest -m "not network"` returns 0 failures with suite size
  ≥ 332 + the new suites (baseline recorded per §14); CI (test job ×3
  Pythons) stays green on the 0.2 commit.
- **AC-02** — A real-sample Sherlock fixture (committed with upstream
  version + date) imports through the shipped CLI, zero errors, zero
  invented fields; tool name via detection, version recorded as declared in
  the file if present, else `unknown` (R-SEC-4 — never guessed; a Sherlock
  CSV is not expected to carry version metadata; the operator-recorded
  version+date pin the fixture doc — amended 2026-11-06), and the raw
  file stored hash-identical to the fixture bytes.
- **AC-03** — Import obeys R-SEC-1..8; refusals produce exit 3 + explicit
  messages; **zero partial imports** occur in the 5 refusal tests; the
  zero-egress pin (import performs no fetch) and the R-SEC-5
  echo-sanitation tests pass — both named in B-02's suite (amended
  2026-11-06).
- **AC-04** — Analyst triage states (promote/dismiss/defer) captured as
  hash-chained events; dismissed row cannot be promoted without a reason;
  no auto-claim synthesis anywhere (no code path writes a `claim` without a
  user action).
- **AC-05** — With two promoted sources, `analyze claim` output changes via
  the *existing* decision-table semantics only, and matches the
  predetermined case (determinism as today).
- **AC-06** — TUI journeys J6–J7 are implemented as pilot tests (J8 search
  deferred out of 0.2 — moved to the canonical doc's H2, amended
  2026-11-06); the
  keymap-parity test (`test_docstring_table_matches_live_bindings`) remains
  green; no new key is advertised without an action.
- **AC-07** — CLI parity: every ingest action works end-to-end via CLI alone;
  a scripted headless run of the B-04 E2E via `pytest` matches the TUI
  equivalents (J6's cross-check).
- **AC-08** — The e2e demo script (`docs/demo/run_synthetic_demo.sh`) keeps
  passing end-to-end pre- and post-merge; the demo gains an ingest step in
  0.2 (fixture-based), and its report includes the ingested sources'
  provenance strings.
- **AC-09** — `case-verify` after a `--recipient` export of an ingested
  case verifies clean; after a deliberate tamper, exits 1.
- **AC-10** — No new runtime dependency appears in `pyproject.toml`
  (maintaining NG-4); no new DB migration is required for ingest.
- **AC-11** — Documentation updates needed for behavior changes land in this
  same release cycle: `CHANGELOG.md` section, README capability matrix only
  for the new ingest row, `docs/demo/` re-record; **none of the existing
  claims go stale** (`FINAL_BUILD_SPEC.md` §6 release-gate documentation
  check stays valid).

---

## 12. Risks, dependencies, unresolved decisions

| ID | Risk / dependency / decision | Impact | Mitigation / status |
|---|---|---|---|
| R-1 | **Upstream format drift**: Sherlock/Maigret can change CSV/JSON-dossier shapes across minor versions (amended 2026-11-06: Sherlock's first import format is CSV; Maigret already carries an auto-updating site DB) | Parser silently under-reads (worse than refusing) | Version-pinned fixture + schema documented per version; fail-closed unknown versions (R-SEC-3); version-skew test in acceptance; a drift-logging note in CHANGELOG whenever a parser is revised |
| R-2 | **Task-required format verification is NOT DONE inside this session** (no network in this loop; fixture must come from real upstream sample) | Ingest cannot be speced below field level until it is | B-01 makes it P0; nothing gets "integrated" without a real-sample fixture passed through E2E |
| R-3 | **Single-maintainer bus factor** (implicit throughout; explicit in SECURITY.md "no published response SLA") | Acknowledgement and fix latency depend on one person's availability | 0.2 keeps changes additive; parser count (≤2) and module count deliberately small |
| R-4 | **The e2e reproducibility flake** (§2.3): appeared once in today's first full run, absent from 8 further runs; root cause unproven; suspected ordering/interference or hidden state | Tests can carry future regressions inside noise; future assessment-flow changes could break invisibly | B-05 P1; until resolved, green claims keep the project's watched-run discipline (`FINAL_BUILD_SPEC.md` §6) |
| R-5 | **The Bellingcat 2022 survey data is dated** (2022, self-reported, `[V]`) — fine for honesty of positioning, not for user-demand quantification in 2026 | If quoted externally, it must be re-fetched and dated | Recycling rule already used by `RESEARCH_REGISTER.md`; external review brief §13 states it as a limitation, not demand proof |
| R-6 | **Redaction residual** (C4/R-C4-2): the residual is the documented "text looks verbatim but is not" semantics, which depend on the recipient reading the export README | Someone skims and misses that redaction happened | 0.2 does not worsen it (import does not redact; the export path is unchanged); §9 R-SEC-5 keeps honesty first; report caveats for ingested-data cases re-checked at acceptance |
| R-7 | **Maintenance coupling**: B-04's E2E pins the ingest→assess flow via public CLI outputs; any `analyze` decision-table change must update both the flow pin and the fixture | Maintenance cost accumulation | The pin targets observable CLI behavior (per `test_demo_case.py:378` pattern), so decision-table changes ship together with their acceptance updates |
| R-8 | **Catalogue licence deficit adjacency**: 2,257 `UNKNOWN` licences (FS-23) sit next to 0.2's integration work; a reader could conflate "catalogue row exists" with "imported/verified" | Positioning confusion, planning drift | NG/boundary restated: ingestion claims no catalogue integration; FS-23 stays a separate autonomous grind (B-11) |
| R-9 | **Exit-code boundary**: `exit 4` exists for "network BLOCKED"; an import flow that auto-fetched a URL would be both a security and an honesty failure | NG/R-SEC-6 weakened by accident | No code path connects import review to networked fetch; the zero-egress pin in B-02's suite covers it (named in AC-03 — amended 2026-11-06) |
| R-10 | **Unresolved decision (user input):** whether `integration_state` gains a tier for import-only adapters (`import-integrated`) — vocabulary change; also whether `catalogue` rows should reflect it | Naming/UX clarity for the honest-lifecycle rule | Decision left to the 0.2 implementer + maintainer; today's rule (`integrated` = E2E by our suite) is never loosened |

---

## 13. External specialist review brief

*Ready to share with an experienced OSINT analyst / verification
specialist. Facts below this line are all anchored in the repository state
as inspected on 2026-11-06, and in actually-run outputs (§14). The brief
avoids marketing language, per the project's own honesty rules.*

### 13.1 Product purpose

A **terminal-first, local, evidence-centric OSINT investigation workbench**:
it records case scope, holds analyst-supplied/collected artifacts as
hash-addressed evidence, keeps raw tool returns separate from interpretive
claims, requires explicit analyst review, generates reports that carry their
own author identity and correction lineage, and produces exports whose
integrity a stranger can re-verify without TRACEFIELD. It deliberately does
not: collect on its own (beyond two doubly-opt-in functions), automate
identity attribution, express probabilities, or provide evasion features
(D17).

### 13.2 Architecture in one table

| Layer | Where | Notes |
|---|---|---|
| Core domain | `src/tracefield/core/domain.py` (285 lines; 13 typed records) | Case/Source/EvidenceItem/Observation/Assertion/Claim/Relation/OriginCluster/AnalysisEvent/CaseReport/ReportCorrection/Dissemination/AssessmentVector |
| Deterministic rules | `src/tracefield/core/analysis.py` (`assess_claim`), `origins.py`, `contradictions.py` | recorded `RULE_VERSION = assess-r2`; clustering is hypothesis, review required |
| Support | `src/tracefield/storage/database.py` (SQLite, schema v2, integrity triggers), `repositories.py`, `workspace.py` | `migrate()` refuses a newer schema with a clear error; `0600` DB / `0700` dirs |
| Adapters | `src/tracefield/adapters.py` + `fieldtools/inspect.py` | exiftool integrated E2E; ffprobe/tesseract spec-only; fail-closed backend allowlist; raw-first |
| Security | `src/tracefield/security/{urls,redact,sanitize}.py` + `fieldtools/fetch.py` | SSRF deny-list + per-hop re-pin; redact-then-manifest exports; terminal sanitation |
| CLI | `src/tracefield/cli/main.py` (2,423 lines; 12 sub-apps; 46 commands — amended 2026-11-06, was "~37"; exit codes 0/1/2/3/4/5) | `--json` everywhere; case/scope/claims/relations/assertions/analyze/report/correct/export/verify |
| TUI | `src/tracefield/tui/{app,views,state}.py` (Textual) | 6 workspaces; truthful keymap (TS-2 parity test); active-case-only model; no feature is TUI-only |
| Registry | `src/tracefield/registry/{catalog,importers}.py` | 2,264 inert tool records (tiered); importers are catalogue-only |

### 13.3 Verified capabilities (anchored to commands actually run)

- End-to-end synthetic case demo (13 numbered banners: doctor prelude + steps 1–12) through the real CLI: passive,
  scope → sources → hash-bound evidence → observation → claim+relations →
  clustering (2 sources fused) → contradiction candidates → analyst-confirm
  → `SUPPORTED_BUT_UNCONFIRMED` → double-run reproducibility → confirm
  contradiction → `CONTESTED` → event chain verify → reports →
  privacy-aware export with SENSITIVE_METADATA listing key names only →
  `case-verify` clean → tampered byte caught (`case-verify` exit 1).
- 332-test suite green (`pytest -m "not network"`), ruff/mypy strict clean,
  catalogue 2,264 valid, CI+CodeQL success on the same commit (§2.3).
- Determinism and honesty are enforced, not claimed: reproducibility pin
  (`test_demo_case.py:378`), label-is-not-truth caveat in every `analyze
  claim` render, `tools status` prints tiered counts and prints the refusal
  to claim health, report prints "hashes prove bytes, not truth" style
  caveats.

### 13.4 Known limitations (honest set, current as of 2026-11-06)

1. **No case-data import**: there is no path from a Sherlock/Maigret/other
   tool's output file into case records — the analyst manually transcribes
   (`source add`, `evidence attach`, `observation add`). The 0.2 direction
   exists precisely to close this (§5/§6/§7).
2. **Independence analysis is text-based only** (origin-r3 containment);
   metadata/clustering signals across non-text evidence (like image
   duplicates) are absent (pHash planned-only).
3. **One integrated adapter** (exiftool). ffprobe/tesseract are typed but
   not exercised end-to-end (`spec-only`). A catalogue of 2,264 records is
   a registry, not an integration list (0 integrated rows in `tools
   status`; integration truth lives in the adapter registry).
4. **No timeline view, no cross-record search** (§2.2 NOT PRESENT rows).
5. **Licence completeness deficit in the catalogue** — 2,257 of 2,264 rows
   say `UNKNOWN` (FS-23 grind accepted and open).
6. **Report-defensibility residuals**: absolute paths may leak filesystem
   structure in `s()`-escaped locator text (C1/R-C1-4 residual); recipient
   notification of corrections remains operator-executed (OOVS-09 scope
   limit); `tool_fingerprint` not yet bound into digest chains (FS-24).
7. **Terminal-scoped user base** — CLI is primary; interface minorities
   outside terminal users are consciously not served at 0.2.
8. **Single-maintainer project**, no response SLA (SECURITY.md says so).

### 13.5 Threat model and trust boundaries

- **Local-first data model**: all state on the operator's machine, `0700`
  dirs / `0600` DB; SQLite triggers enforce same-case relational integrity;
  no server component exists at all.
- **Network surface (doubly opt-in)**: fetch (`TRACEFIELD_ALLOW_NETWORK=1` +
  `--fetch` + recorded scope grant) and username checks (env-gated). URL
  policy revalidates per hop and connects only to pre-validated pinned IPs
  (DNS-rebinding TOCTOU closed, `fetch.py:74-120` + redirect test).
  Politeness rules (1 req/s, backoff on 429/403/5xx) and soft-404 marker
  rules prevent "HTTP 200 = profile exists" claims.
- **Untrusted data paths**: catalogue lists (parsed inert, described by
  this project — copying other lists' prose is forbidden); tool raw returns
  (verbatim, never executed); terminal/session text (ANSI/OSC sanitized at
  every render site; CI-level tests pin the trick we already caught, e.g.
  OSC-clipboard injection defusing).
- **Integrity boundaries**: `analysis_events` hash chain (`prev_digest`),
  evidence SHA-256, case-export manifest over final bytes, cross-case
  guard, refusal of newer DB schemas than the build understands.
- **Authorship/misattribution boundary**: `report_author` is per-operator
  config; the tool never invents an author and refuses ambiguity
  (`author not set` fallback), meaning a report without a configured author
  is honest about being unattributed.
- **AI/automation boundary (as designed)**: no autonomous agent operates on
  a case; every machine suggestion arrives at candidate/unreviewed
  severity, and the standing product rule: the number/probability
  framing is refused deliberately, because assessment labels are workflow
  states with documented criteria, not degrees of truth.

### 13.6 Reproducible synthetic demo (self-contained, no network, no real persons)

```bash
# From a TRACEFIELD checkout with the Python project installed:
bash docs/demo/run_synthetic_demo.sh
# Signals to look for (all were observed 2026-11-06):
#   - "manifest verified — all digests match"
#   - case-verify exit code after tamper: 1 (1 = detected, as designed)
#   - report block: Author: killerdasher — github.com/killerdasher/TRACEFIELD
```

It is fully synthetic (fictional company, locally generated fixtures,
`.example` domains), mirrors `tests/e2e/test_demo_case.py` (which asserts
 the same behaviors), and induces a deliberate tamper to prove detection.

### 13.7 Five technical questions for an experienced analyst

1. **Does the independence downgrade match your workflow?** `analyze claim`
   downgrades `CORROBORATED_WITH_LIMITATIONS` to
   `SUPPORTED_BUT_UNCONFIRMED` purely on text-similarity clustering of
   sources, and says so ("independence NOT established"). Is this the right
   conservative default, or would an analyst-facing per-cluster justification
   review (which does exist today at candidate severity) need to flow
   further up into report language?
2. **Which tool outputs do you actually bring into a workbench first, and
   in what format?** (Sherlock CSV is the first planned import format —
   amended 2026-11-06;
   Maigret dossier second; do you have real saved outputs, and would
   per-row provenance (tool+version+time+raw row link) be sufficient, or
   would you need the full raw dossier attached and searchable?)
3. **Is claim-level assessment-as-state (workflow labels, no probabilities)
   defensible in your environment?** The product refuses probability
   sizing deliberately. Where does that help regimes that require clarity
   (see `20_ROLE_REVIEW.md` for why), and where does it cause friction for
   you (e.g., judicial or editorial contexts)? Be specific about report
   block you'd want added/removed.
4. **Does the export package satisfy your chain-of-custody test?**
   `case-export --recipient` records which revision shipped to whom and
   `case-verify` re-hashes the bundle independently. Given the SENSITIVE_
   METADATA advisory file (key names only; GPS coordinates never copied),
   what's the weakest point an opposing party would attack at (e.g., can
   they claim post-redaction manifest work-around), and what would
   make *you* accept the manifest as proof the recipient can reproduce the
   case bytes?
5. **What should ingestion do when an upstream tool's row is *wrong* about
   a site's existence** (e.g., Sherlock's `--ignore-exclusions` false
   positives, Maigret's soft-404 mistrials)? Is a per-row
   `dismiss(reason)` enough at triage time, or would you need an
   upstream-quality signal on the row itself (source claim vs row claim,
   i.e., layered disagreement)?

### 13.8 Highest-risk weaknesses that need independent review

1. **Ingestion is the risk we ask the reviewer to look at first** — none
   exists yet, and 0.2's design (§6/§9) is unverified against a real analyst
   workflow (their review could change the triage model before anything is
   built; that is a *good* outcome, not a failure).
2. **Redaction residual risk** (C4/R-C4-2): redaction exists, but its
   "looks verbatim but isn't" semantics depend on reading the export README.
   An adversarial reviewer should evaluate whether the current marker
   system (rule IDs + report caveats) suffices for a recipient who never
   reads READMEs.
3. **Independence-downgrade dependence on text clustering**: origin-r3's
   containment scores can both under-cluster (poorly warmed text) and
   over-cluster (derivative but distinct sources); the review-gate is
   analyst-confirmed states only, which is honest but human-bounded.
4. **Digest-chain forward-compatibility**: `tool_fingerprint` is not bound
   into event digests (FS-24); upgrading chains later has a known compat
   decision recorded as BLOCKED-until-decided (chain rehash+reverify would
   be a breaking artifact change). Reviewers should pressure-test the
   "decision later" posture.
5. **Test-suite noise**: §2.3's one-time non-reproducible failure in the
   E2E reproducibility assertion — simplest possible explanation is
   environmental/ordering interference; unproven. A fresh reviewer's
   environment (non-Ubuntu, different disk, running different subsets of
   the suite) is the most likely place to wake it again. Treat repeated flakes as the
   suite's primary health signal.

---

## 14. Verification log (this session, 2026-11-06)

| # | Command (abbreviated) | Result | Evidence kept |
|---|---|---|---|
| V1 | `git status --porcelain` / `git log --oneline -3` / rev-list sync | clean tree at `dbdbfd6`, ahead=0/behind=0 | output above |
| V2 | `gh run list --limit 6` | CI `40860607568` + CodeQL `40860607746` success on HEAD (2026-10-29); scheduled CodeQL `41457478434` success (2026-11-02); Dependabot success (2026-11-02) | output above |
| V3 | `pytest -m "not network"` (3 full-suite runs + 5 solo-file runs) | 1 initial failure in `test_demo_case.py:378` then 0 failures ×3 suites (332 tests each, no skips ⇒ exiftool E2E exercised); root cause unproven → R-4/B-05 | `/tmp/opencode/looprepro/full[1-3].log` |
| V4 | `pytest tests/e2e/test_demo_case.py` solo ×5 | PASS ×5 | same dir |
| V5 | `ruff check src tests` / `ruff format --check` / `mypy src` | "All checks passed!"; "61 files already formatted"; "Success: no issues found in 38 source files" | output above |
| V6 | `tracefield catalog validate` / `tracefield tools status` | "catalogue OK — 2264 records valid"; tiered counts 2,254 indexed/10 verified; licences UNKNOWN 2,257 | output above |
| V7 | `bash docs/demo/run_synthetic_demo.sh` (with `TRACEFIELD_BIN` = repo venv binary, fresh workdir) | rc=0; all 13 numbered banners (0–12); "manifest verified — all digests match"; tamper test exit 1 as designed | `/tmp/opencode/looprepro/demo.log` |
| V8 | Source-level re-reads: `adapters.py`, `fetch.py` per-hop pin, `inspect.py:148-159` allowlist, `database.py:452-467` schema refusal, `analysis.py` determinism doc, `reporting/{build,export}.py`, `tui/app.py`, `fieldtools/username.py`, security modules | matches documented claims; POST_BUILD_AUDIT statuses are point-in-time (K1/K2) | reads above |
| V9 | pip-audit + fresh-venv wheel smoke (background in this session) | **PASS** — pip-audit rc=0 "No known vulnerabilities found"; wheel built `tracefield-0.1.0-py3-none-any.whl`; fresh-venv install: `tools status` / `catalog validate` / `doctor` all `ok` | `/tmp/opencode/looprepro/{pip-audit,wheel}.log` |
| V10 | No uncommitted changes introduced; the only file created by this phase is this document under `docs/strategy/` | preserves the "do not implement" boundary | `git status` re-check before convergence |

> Loop-convergence note: this document is the deliverable of a planning-only
> loop (`--mode deep`, 3 iterations). It introduces no code, no tests, no
> dependency changes and no releases. Every "VERIFIED" above was executed in
> this session; anything else is labelled with the project document and its
> date. The recommended first implementation task is **B-01** (Sherlock
> format verification via a real pinned sample), because every
> ingest-data-dependent 0.2 item (B-02/B-03/B-04/B-07) depends on a verified
> format (scoping corrected 2026-11-06; release-mechanics items — TUI
> overlay mechanics, timeline (deferred), worker offload, research bookmarks,
> the release checklist — do not wait on it).
