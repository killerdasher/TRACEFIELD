# TRACEFIELD — External Specialist Review Brief

> **Shareable verbatim.** Last updated 2026-11-07. Distilled from the
> canonical strategy (`docs/strategy/TRACEFIELD_STRATEGIC_FORESIGHT.md`
> §20). The demo runs fully offline on synthetic data only — no real
> persons, no live collection, no telemetry.

## Who we are asking

Practitioners who do Investigate-and-report work: independent OSINT
researchers, verification journalists/fact-checkers, digital investigators.
Terminal comfort is a plus but not required for the questions below.

## What we are not asking for

No data about real people, no case files with personal data, no networked
setup. If you want to test with real material, use redacted/synthetic
content.

## Try it in five minutes (no install beyond `pip install -e .`)

```bash
bash docs/demo/run_synthetic_demo.sh
```

That walks the full pipeline: case → evidence (hash-bound, 0o400) → claims
→ review-gated analysis → report → export bundle you can re-verify with
plain `sha256sum` — and then a deliberate tamper that the verification must
catch.

## The tasks — tell us where the tool fell short

1. Recreate the demo flow with the *shape* of one of your own closed
   investigations (synthetic or redacted data). What's missing to make it
   yours?
2. Ingest your own saved tool output. Today this requires manual row
   copying — tell us how much time that costs you, and which tool's saved
   file you'd hand the importer first.
3. Re-verify an export bundle with `sha256sum` only. Did the instructions
   hold up? Where did you get stuck?
4. Fabricate a correction trail (report, correct, re-ship, re-verify).
   Anything that let history disappear?
5. Lie with the probability claims you *wish* the tool had — we chose
   refusal (workflow labels, no percentages). Pick the refusal apart.

## Focused questions

- **Q1.** What evidence fields in an export bundle would make you trust it
  *more* — be specific and countable?
- **Q2.** Given your real Sherlock/CSV (or Maigret) saved outputs, which two
  columns would you structure first, and do the plan's provenance fields
  (tool, version, run time, per-row raw link) match your habit?
- **Q3.** Where would a *deterministic* assessment vocabulary (no
  probability scores) slow your editorial or legal workflow down?
- **Q4.** Red-team the export verification: what does a smart adversary do
  to a bundle that `sha256sum` would NOT catch?
- **Q5.** Judging by capability (not marketing): where does this workbench
  sit between the tools you already pay for — and where exactly would you
  switch between them?

## What we promise in return

Honesty: every claim in the docs is checkable; no telemetry ever; no data
leaves the machine except your own exports. Your answers feed the public
backlog (`docs/strategy/`), credited or anonymous as you prefer.

*Responses: open an issue titled `review-brief` or answer inline. We log
attempt- and response-counts either way — non-responses count too.*
