# TRACEFIELD ↔ OWASP OOVS mapping (self-assessment)

**Standard:** OWASP Open Source Intelligence Verification Standard (OOVS),
version **v0.1.0** (release: <https://github.com/OWASP/OWASP-Open-Source-Intelligence-Standard/releases/v0.1.0>).
Normative text: [`oovs/v0.1/standard.md`](https://github.com/OWASP/OWASP-Open-Source-Intelligence-Standard/blob/main/oovs/v0.1/standard.md);
structured requirements: [`requirements.json`](https://github.com/OWASP/OWASP-Open-Source-Intelligence-Standard/blob/main/oovs/v0.1/requirements.json);
acceptance tests: [`tests.json`](https://github.com/OWASP/OWASP-Open-Source-Intelligence-Standard/blob/main/oovs/v0.1/tests.json).

**Assessed product:** TRACEFIELD 0.1.0 (pre-first-release), data schema v2
(additive migration from v1, 2026-10-27).
**Assessment date:** 2026-10-19.
**Re-verified:** 2026-10-27 after Phase 11 (scope/authorization ledger, report
identity/corrections/dissemination register, schema-v2 DB integrity triggers,
assertion CLI, catalogue freshness listing) — 321 tests passing
(`pytest -m "not network"`, 3.13; re-run on 3.11/3.12 before push).
**Rule versions in scope:** `assess-r2` (claim assessment), `contra-r2`
(contradiction detection), `origin-r3` (origin clustering), report schema v3
(v2 was additive to assessed v1: added generated_at/tool/document
dissemination block, 2026-10-19; v3 is additive to v2: the document block
gains durable report identity — report_id/revision/supersedes — and
correction records, 2026-10-27; v1/v2 fields unchanged).
**Assessment type:** maintainer self-assessment against the OOVS requirement
objectives, evidenced by source and the automated test suite (207 tests passing
at assessment time, re-verified 2026-10-19: `tests/unit`, `tests/integration`,
`tests/security`, `tests/e2e/test_demo_case.py`; the earlier draft cited 203).

## This document is not a certification

OOVS is a voluntary standard. This mapping is TRACEFIELD's own self-assessment.
It is **not** an OWASP assessment, certification, accreditation, or endorsement;
it does not determine legal compliance or evidentiary admissibility, and it does
not claim any government, agency, court, or vendor approval. The OOVS official
acceptance-test procedures (`tests.json`) were **not executed** by us; where the
evidence to judge was insufficient, the status is `NOT_ASSESSED` rather than a
guess. Requirement identifiers are cited in the form
`OWASP OOVS v0.1.0, OOVS-v0.1.0-NN` and linked upstream; normative wording is
not reproduced here (the standard is CC BY-SA 4.0 —
<https://creativecommons.org/licenses/by-sa/4.0/>).

## Status definitions

| Status | Meaning |
|---|---|
| `PASS` | Within the stated scope, available evidence satisfies the requirement's objective. Scope limits are listed with each entry. |
| `FAIL` | A known gap against the objective; the required mechanism does not exist in the product today. |
| `NOT_ASSESSED` | Evidence genuinely insufficient to judge (no mechanism to examine, or the official test was not run and the product cannot yet claim the capability). |
| `NOT_APPLICABLE` | The requirement is not engaged by this product or workflow, with reason. |

## Summary

| ID | Requirement | Status |
|---|---|---|
| `OOVS-v0.1.0-01` | Authorised purpose and proportionality | `PASS` (scoped) |
| `OOVS-v0.1.0-02` | Collection boundary and data minimisation | `PASS` (scoped) |
| `OOVS-v0.1.0-03` | Source provenance and integrity | `PASS` (scoped) |
| `OOVS-v0.1.0-04` | Source and claim assessment | `PASS` (scoped) |
| `OOVS-v0.1.0-05` | Corroboration and confidence | `PASS` (scoped) |
| `OOVS-v0.1.0-06` | Analytic transparency and reproducibility | `PASS` (scoped) |
| `OOVS-v0.1.0-07` | Rights, privacy, and safeguarding | `PASS` (scoped) |
| `OOVS-v0.1.0-08` | AI and automation assurance | `PASS` (scoped) |
| `OOVS-v0.1.0-09` | Dissemination and action controls | `FAIL` |
| `OOVS-v0.1.0-10` | Governance, audit, and improvement | `NOT_ASSESSED` |

8 `PASS` (each scoped), 1 `FAIL`, 1 `NOT_ASSESSED`, 0 `NOT_APPLICABLE`.

## Requirement detail

### `OOVS-v0.1.0-01` — Authorised purpose and proportionality — `PASS` (scoped)

**Evidence (re-mapped 2026-10-27 after Phase 11):**
- `case create` records a declared purpose and scope
  (`src/tracefield/cli/main.py`); collection commands operate only on the
  case the operator selected; there is no bulk-collection mode anywhere in
  the CLI.
- **Scope/authorization ledger**: `case authorize <case> --scope "<text>"
  --authorized-by "<name>"` records a collection-authority decision
  (optionally `--revoke` to withdraw) as a **hash-chained analysis event**
  (`scope.authorize`/`scope.revoke` in `analysis_events`; tamper-evident by
  the same chain `case verify` checks). `case scope <case>` is the read
  view (declared scope, ledger entries, active or not).
- **Enforcement**: `source add --fetch` fails closed (exit 4, with an
  actionable `case authorize` hint) unless the **latest** recorded decision
  for that case is an active grant — the global
  `TRACEFIELD_ALLOW_NETWORK=1` opt-in alone is not collection authority.
  A later revoke blocks again. Tests: `tests/integration/test_cli.py::TestScopeLedger`
  (gate blocks with hint; grant-then-fetch passes the ledger and fails on
  the URL policy instead — via an intentionally unresolvable `.invalid`
  host, so no network is contacted; revoke re-blocks; host advisory;
  grant validation; ledger read view).

**Scope limits / honest caveats:**
- Authorization is recorded as *who decided what collection* — it does not
  make an operation lawful, and the tool cannot verify a legal authority
  (operator responsibility, stated in README non-guarantees).
- The recorded scope text is free-form; the host-vs-scope check (`source
  add --fetch`) is a **soft advisory** when a target host is not mentioned,
  not a semantic proportionality check. There is no proportionality scoring.
- Username checks (`username check`) deliberately stay env-gated only
  (`TRACEFIELD_USERNAME_CHECK`, decision D20): they are public-profile
  existence probes against a curated allowlist, not case collection;
  proportionality for them is procedural.
- The official acceptance test was not run.

### `OOVS-v0.1.0-02` — Collection boundary and data minimisation — `PASS` (scoped)

**Evidence:**
- Network is off by default (`allow_network = False`, `username_check_enabled = False`,
  `src/tracefield/config/settings.py:44-45`); enabling requires an explicit
  opt-in (`TRACEFIELD_ALLOW_NETWORK=1`, shown by `about`, still validated
  per-URL) — fail-closed network policy with exit code 4.
- Per-URL SSRF policy: private ranges, link-local, metadata endpoints blocked
  (`src/tracefield/security/urls.py`; `tests/security/`).
- Fetches have byte caps and timeouts; no bulk or crawl mode exists.
- No telemetry: stated in `about` (`src/tracefield/cli/main.py:254`) and the
  module docstring of `settings.py`; enforced by the security test suite
  (network tests are marker-gated `network` and assert no outbound calls on the
  default path).
- Username checks use a curated per-service allowlist and never treat HTTP 200
  alone as a match (`src/tracefield/fieldtools/username.py:7,34`).

**Scope limits / honest caveats:**
- `retention_policy` is a recorded field with a default
  (`src/tracefield/storage/database.py:32`) but there is **no automated
  retention/erasure job**; deletion is operator-driven (`case delete`,
  `src/tracefield/cli/main.py:1582`).
- Data minimisation depends on the operator attaching only what the case needs;
  the tool does not auto-harvest; scope enforcement is the Phase 11
  authorization ledger plus a soft host advisory (`-01`), not a semantic
  refusal of over-collection.

### `OOVS-v0.1.0-03` — Source provenance and integrity — `PASS` (scoped)

**Evidence:**
- Every evidence object stores a SHA-256 digest
  (`src/tracefield/storage/database.py:57`), indexed for duplicate detection.
- Originals are written once and chmod'd read-only (`0400`); case dirs are
  `0700` (`src/tracefield/storage/workspace.py:56,99`).
- Provenance fields (locator, first seen, collected-at, method, operator) are
  part of the source record; syndicated/derived sources link `derived_from` so
  copies stay distinguishable from originals.
- Analysis actions append to a hash-chained event log (`prev_digest`/`digest`)
  with `verify_chain` (`src/tracefield/storage/repositories.py:521`) and
  `case verify` checks record integrity end-to-end (e2e test tampers a record
  and expects exit 1).
- Structured logs are `0600` in a `0700` directory
  (`src/tracefield/config/logging.py:93,162`).

**Scope limits:** the chain is **tamper-evident, not tamper-proof** — a
sufficiently privileged operator who rewrites every row defeats it (documented
in `verify_chain`'s docstring). SHA-256 proves byte integrity, not truth,
authorship, or authenticity (stated in every report's global caveats).

### `OOVS-v0.1.0-04` — Source and claim assessment — `PASS` (scoped)

**Evidence:**
- Strict separation of Observation / Assertion / Claim
  (`src/tracefield/core/domain.py`); observations are never auto-interpreted
  as findings.
- Soft-404 handling per service: HTTP 200 alone never confirms a profile
  (`src/tracefield/fieldtools/username.py`), with per-service notes recorded.
- Assessment decision table (`assess-r2`, `src/tracefield/core/analysis.py:19`)
  is deterministic, pinned by unit tests, and always emits
  `severity=candidate`-class labels requiring analyst review —
  "Unreviewed machine suggestions are not evidence" is emitted as an explicit
  caveat in the output itself.
- Contradiction detection (`contra-r2`) also reports only as candidates;
  findings carry signal sources so `analyze events` explains why.

**Scope limits:** `temporal_fit` is currently always `unknown`; source-quality
weighting is structural (tiered), not a scored credibility model.

### `OOVS-v0.1.0-05` — Corroboration and confidence — `PASS` (scoped)

**Evidence:**
- Independence is counted by **distinct origins**, not mentions: origin
  clustering (`origin-r3`, `src/tracefield/core/origins.py`) merges syndicated
  copies; `analyze origins` prints the caveat that copies in one cluster must
  not be counted as independent (`src/tracefield/cli/main.py:1063`).
- Clusters are explicitly hypotheses unless analyst-confirmed (report global
  caveat, `src/tracefield/reporting/build.py`).
- Confidence labels are workflow states with documented criteria, explicitly
  **not** probabilities of truth (global caveat); rule versions travel with
  every assessment.
- Relation review states (`unreviewed` → `confirmed`/`rejected`) gate what
  counts as corroboration (decision table).

**Scope limits:** clustering is advisory — an analyst can override it, and the
override must be justified via annotation (the annotation exists; enforcement
is procedural, not technical).

### `OOVS-v0.1.0-06` — Analytic transparency and reproducibility — `PASS` (scoped)

**Evidence:**
- Every assessment records `rule_version`; contradiction analysis records
  `contra-r2`; clustering records `algorithm_version`.
- Rules are deterministic and unit-pinned; the e2e test runs the same analysis
  twice and asserts byte-identical JSON.
- Reports (Markdown + JSON) carry method, limitations, global caveats, and
  per-assessment caveats; exports verify via a post-redaction SHA-256 manifest.
- Machine vs analyst output stays distinguishable (reports say so; OCR/inspect
  output is labeled machine-derived).

**Scope limits:** a report records rule *versions* but does not archive the
rule *text* itself — the text lives in the versioned source repository. A
report generated from modified code with stale version strings would not be
detected (process gap, not a code gap).

### `OOVS-v0.1.0-07` — Rights, privacy, and safeguarding — `PASS` (scoped)

**Evidence:**
- Local-first, permissioned storage (`0700`/`0600`); no telemetry; no cloud
  sync.
- Secret redaction (`src/tracefield/security/redact.py:38`) applied to logs and
  exports; terminal-escape sanitization prevents control-character smuggling.
- Exports emit `SENSITIVE_METADATA.txt` listing files with embedded metadata
  (GPS, EXIF, device identifiers) **without rewriting them** — rewriting would
  invalidate the digests the manifest asserts; the advisory tells the operator
  what to scrub before sharing.
- `case delete` removes records and stored binaries with traversal defenses,
  and honestly notes it cannot erase copies the operator already exported.
- Handling caveats travel with the report.

**Scope limits:** GPS/metadata scrubbing is advisory, not enforced; there is no
access control beyond the filesystem (no per-user auth); no DPIA-style workflow
exists (see `-01`).

### `OOVS-v0.1.0-08` — AI and automation assurance — `PASS` (scoped)

**Evidence:**
- The product contains **no AI/LLM components**: no model calls, no generated
  analysis. All automation is deterministic, versioned rules (`assess-r2`,
  `contra-r2`, `origin-r3`) with test-pinned behaviour.
- Automated suggestions never auto-promote: relations start `unreviewed`;
  assessments are candidates; a named analyst must review and confirm
  (`relation review --state confirmed`), keeping a person answerable for the
  judgment.
- External machine-derived output (OCR, inspect) is labeled as such at the
  point of output and marked `UNAVAILABLE`/`ERROR` honestly when the tool is
  missing (`src/tracefield/fieldtools/ocr.py:49`).

**Scope limits:** the AI-specific clauses are not engaged because no AI
components exist; this status covers the automation half only. If generative AI
is ever added, this entry must be re-assessed before release.

### `OOVS-v0.1.0-09` — Dissemination and action controls — `FAIL`

**What the product has (mechanism shipped Phase 11, 2026-10-27; verdict held
— see below):**
- Caveats and limitations travel with the report to the point of action
  (global + per-source + per-assessment caveats).
- Redaction of secrets in exports; post-redaction integrity manifest so a
  recipient can verify their copy (`src/tracefield/reporting/export.py`).
- Reports state provenance of the report itself (generated-by, rule versions,
  schema version) and non-guarantees.
- **Report identity register** (data schema v2): every rendered report gets a
  durable `report_id` + revision; revision N supersedes N-1 with the chain
  (`supersedes`/`superseded_by`) recorded. Corrections are appended, never
  silently rewritten, are addressed at a specific report id (`report-correct`),
  and travel **forward with the lineage** — a re-render carries every
  correction against the report and its ancestors (`report schema v3`).
- **Dissemination register**: `case-export --recipient <name>` records which
  report revision shipped to which recipient and when; `report-history`
  displays the chain (revisions, corrections, recorded shipments). Exports
  name their exact report id/revision in `EXPORT_README.txt`.

**Why the verdict stays `FAIL` (held, not promoted):**
1. **Correction reachability is not closed-loop**: the register makes "who
   received which revision" answerable, but notifying prior recipients of a
   correction remains an operator action — nothing in the tool automatically
   reaches or confirms any recipient.
2. **No author identity is configured**: the dissemination document must say
   who asserts it; reports currently state `author not set` plainly (FS-17
   author string is user-gated). A self-assessment cannot claim this
   control while its identity half is an empty string.
3. The official acceptance test was not run.

**Gap to close (in order):** set the author identity string (user decision),
re-verify the register against the requirement's own tests, then re-verdict.
Per mapping policy below, promotion from `FAIL` also requires a test that
would fail if the mechanism regressed — the Phase 11 identity/correction
tests provide exactly that tripwire; items 1–2 above are what the verdict
rests on.

### `OOVS-v0.1.0-10` — Governance, audit, and improvement — `NOT_ASSESSED`

**What the product has:**
- In-product audit trail: hash-chained analysis events (`verify_chain`) plus
  structured JSONL logs with redaction (`src/tracefield/config/logging.py`),
  `0600`-protected.
- Project hygiene already in place: `SECURITY.md`, `CONTRIBUTING.md`,
  `CODE_OF_CONDUCT.md`, `CHANGELOG.md`, issue/PR templates, CI (lint, type
  check, tests on 3.11–3.13, catalogue validation, dependency audit).

**Why not `PASS`:** there is no release governance yet — no signed tags, no
versioned upgrade/migration policy, no maintainer plurality — because the
project has not had its first commit or release. The official acceptance test
was not run. The in-product audit half is strong; the project-governance half
cannot be claimed until a release process exists.

**Gap to close:** first release with tag + checksums, documented schema
migration policy, then re-map.

## Maintenance

- Re-map whenever the OOVS version changes (identifiers embed the version:
  `OOVS-v0.1.0-NN`) or when a listed rule version changes (`assess-r2`,
  `contra-r2`, `origin-r3`).
- Every status change must cite the evidence (file/test) that justified it.
- Statuses may never be promoted from `FAIL`/`NOT_ASSESSED` to `PASS` without a
  test that would fail if the mechanism regressed.
