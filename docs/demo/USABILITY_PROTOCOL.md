# First-run usability test protocol (three independent users)

Status: **protocol defined; first-run dry-run results recorded below (AI
testers, 2026-11-14); human tester results still do not exist.** The two
runs below were executed by independent fresh-context AI agents using only
the README and `--help` (no source, no coaching) — a genuine unaided
first-run proxy, but not human evidence. When three human testers have run
this protocol, record results here or in a dated successor note with each
tester's raw task log attached.

## Dry-run results (2 independent fresh-context AI testers, 2026-11-14)

Both testers completed every task **unaided** (Tester A: manual path —
case → attach → claim → relation → analyze → report → export → verify →
tamper; Tester B: ingest path — case-import of the committed Sherlock
fixture → status → promote → claim → analyze → report, plus deliberate
duplicate and garbage-import probes). Both verdicts: a competent new user
can complete evidence-to-report unaided.

Defects found by the runs and fixed in the same session (each pinned by
regression tests in `tests/integration/test_tester_findings.py` and
`tests/integration/test_fetch_persistence.py`):

1. `source add --fetch` recorded the fetched body's sha256 but never
   stored the bytes — the digest was unverifiable (found by a real online
   case, not by the testers; HIGH). Fixed: fetches now attach
   content-addressed evidence automatically.
2. `relation add --type supports --from <claim_id>` was accepted, making a
   claim corroborate itself under assess-r2 (README's old example taught
   the shape). Fixed: refused with an actionable message; README teaches
   source → claim; endpoints must now exist in the case.
3. `source add` duplicated a locator silently. Fixed: loud warning naming
   the existing source id.
4. `doctor` flagged the unset report author without a remedy. Fixed: names
   `TRACEFIELD_REPORT_AUTHOR` / `report_author` config key.
5. case-verify tamper message now shows manifest vs observed digests.

Known-but-accepted friction (documented, not defects): duplicate
case-import is additive by design with a clear inline note; `--case` must
be repeated per command (no active-case concept by design); promote's
provenance string could be more key=value-structured.

## Purpose

Establish whether a new user can complete the evidence-to-report workflow
**without coaching**, using only the repository's own materials (README,
`--help`, command `--help`). This measures onboarding reality, not feature
eligibility.

## Tester requirements

Three testers, each independently, on their own machine, in one session of
≤ 45 minutes per person:

- has not previously used or read TRACEFIELD's docs,
- is comfortable with a terminal,
- has Python ≥ 3.11 installed,
- is told only: *"Try to produce an evidence-backed report for a synthetic
  claim, then export and verify it. Think aloud. Do not ask anyone anything
  until you are truly stuck."*

Suggested tester mix: one OSINT-practitioner background, one
developer/generalist, one digital-forensics or journalism background.

## Tasks (each tester, same order)

1. Install from `README.md` ("Try it — five minutes, no network") into a
   scratch virtualenv. Record: time, all friction points, docs consulted.
2. Create a synthetic case with a declared purpose/scope you invent, next
   to a scratch `TRACEFIELD_HOME`. Record: flags guessed vs looked up.
3. Register one source (URL, no fetch). Add one claim. Attach one local
   synthetic file as evidence (create a small text file). Record:
   command-discovery path (browse `--help`? README? guess?).
4. Relate claim ↔ evidence `supports`, review the relation `confirmed`,
   then run `analyze claim`. Record: whether the outcome label and caveats
   were understood without explanation; quote the tester's read of
   `SUPPORTED_BUT_UNCONFIRMED`.
5. If stuck: follow the README's ingest section instead — import the
   committed Sherlock fixture (`tests/fixtures/ingest/…`) via
   `case-import`, promote one observation. Record: was the promote/refusal
   messaging clear?
6. Generate a Markdown report and export the case; run `case-verify` on
   the export; then append one byte to an exported file and re-verify.
   Record: expectation vs actual result, whether the manifest math was
   understood.
7. Answer (out loud, recorded verbatim by the runner):
   - What does this tool do, in your own words?
   - What would you use it for in your own work?
   - Anything you expected that was missing?
   - Anything that felt over-claimed or dishonest?

## Recorded per task

- Elapsed time; commands attempted (raw transcript, sanitized); docs
  consulted; moments of confusion (verbatim quote); whether the step
  completed unaided.

## Scoring

- Task success rate (unaided / aided-by-docs / stuck).
- Median time per task.
- Themes from think-aloud quotes, one line each.

Tester notes are sanitized per the bug-report rule: no real personal data,
no real case content — every dark file path, name, or credential must be
removed before sharing any transcript anywhere.
