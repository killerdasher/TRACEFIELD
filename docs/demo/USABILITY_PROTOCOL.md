# First-run usability test protocol (three independent users)

Status: **protocol only — not yet executed. Nobody has completed this
test.** No usability claims exist for TRACEFIELD; when this protocol has
been run, results are recorded here or in a dated successor note with each
tester's raw task log attached.

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
