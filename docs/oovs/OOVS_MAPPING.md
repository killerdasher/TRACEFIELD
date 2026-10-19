# TRACEFIELD ↔ OWASP OOVS mapping (self-assessment)

**Standard:** OWASP Open Source Intelligence Verification Standard (OOVS),
version **v0.1.0** (release: <https://github.com/OWASP/OWASP-Open-Source-Intelligence-Standard/releases/v0.1.0>).
Normative text: [`oovs/v0.1/standard.md`](https://github.com/OWASP/OWASP-Open-Source-Intelligence-Standard/blob/main/oovs/v0.1/standard.md);
structured requirements: [`requirements.json`](https://github.com/OWASP/OWASP-Open-Source-Intelligence-Standard/blob/main/oovs/v0.1/requirements.json);
acceptance tests: [`tests.json`](https://github.com/OWASP/OWASP-Open-Source-Intelligence-Standard/blob/main/oovs/v0.1/tests.json).

**Assessed product:** TRACEFIELD 0.1.0 (pre-first-release), data schema v1.
**Assessment date:** 2026-10-19.
**Rule versions in scope:** `assess-r2` (claim assessment), `contra-r2`
(contradiction detection), `origin-r3` (origin clustering), report schema v1.
**Assessment type:** maintainer self-assessment against the OOVS requirement
objectives, evidenced by source and the automated test suite (203 tests passing
at assessment time: `tests/unit`, `tests/integration`, `tests/security`,
`tests/e2e/test_demo_case.py`).

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
| `OOVS-v0.1.0-01` | Authorised purpose and proportionality | `NOT_ASSESSED` |
| `OOVS-v0.1.0-02` | Collection boundary and data minimisation | `PASS` (scoped) |
| `OOVS-v0.1.0-03` | Source provenance and integrity | `PASS` (scoped) |
| `OOVS-v0.1.0-04` | Source and claim assessment | `PASS` (scoped) |
| `OOVS-v0.1.0-05` | Corroboration and confidence | `PASS` (scoped) |
| `OOVS-v0.1.0-06` | Analytic transparency and reproducibility | `PASS` (scoped) |
| `OOVS-v0.1.0-07` | Rights, privacy, and safeguarding | `PASS` (scoped) |
| `OOVS-v0.1.0-08` | AI and automation assurance | `PASS` (scoped) |
| `OOVS-v0.1.0-09` | Dissemination and action controls | `FAIL` |
| `OOVS-v0.1.0-10` | Governance, audit, and improvement | `NOT_ASSESSED` |

7 `PASS` (each scoped), 1 `FAIL`, 2 `NOT_ASSESSED`, 0 `NOT_APPLICABLE`.

## Requirement detail

### `OOVS-v0.1.0-01` — Authorised purpose and proportionality — `NOT_ASSESSED`

**What the product has:** `case create` records a declared purpose and scope
(`src/tracefield/cli/main.py:306-307`); collection commands operate only on the
case the operator selected; there is no bulk-collection mode anywhere in the
CLI.

**Why not `PASS`:** recording a purpose is necessary but not sufficient —
nothing in the workflow *gates* collection on the declared scope (no scope
ledger, no proportionality check before a fetch or username query, no
authorization record beyond free-text fields). The official acceptance test was
not run.

**Gap to close:** enforce scope at collection time (reject or warn when a
command targets material outside the declared scope) and record an
authorization decision object, then re-map.

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
  the tool does not auto-harvest, but it also does not refuse over-collection
  against the declared scope (see `-01`).

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

**What the product has:**
- Caveats and limitations travel with the report to the point of action
  (global + per-source + per-assessment caveats).
- Redaction of secrets in exports; post-redaction integrity manifest so a
  recipient can verify their copy (`src/tracefield/reporting/export.py`).
- Reports state provenance of the report itself (generated-by, rule versions,
  schema version) and non-guarantees.

**Why `FAIL`:** the requirement's correction obligation — a correction reaching
everyone who received the product — has **no mechanism** in TRACEFIELD today.
There is no release/recipient register, no re-issue workflow, no "this report
was superseded" marker carried forward, and no way to notify prior recipients.
The first half (caveats travel) is implemented; the second half (corrections
propagate) is absent. This is the clearest unmet requirement.

**Gap to close:** report revision IDs + a supersession record on cases, and an
export manifest that lists which recipients/exports were issued which revision.

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
