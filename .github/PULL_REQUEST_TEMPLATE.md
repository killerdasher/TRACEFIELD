## Summary

<!-- What does this PR change, and why? Link the issue if there is one. -->

## Type of change

- [ ] Bug fix
- [ ] New feature
- [ ] Catalogue data update
- [ ] Documentation
- [ ] Refactor / internal quality
- [ ] Security fix (link the advisory; do not disclose details publicly)

## Gates

- [ ] `pytest -m "not network"` passes locally
- [ ] `ruff check src tests` and `ruff format --check src tests` pass
- [ ] `mypy src` passes (strict)
- [ ] `tracefield catalog validate` passes (if `data/catalog/` changed)

## Claim-honesty checklist

- [ ] No new advertised capability lacks an implementation (help text, TUI strings, README)
- [ ] New caveats/limitations are stated in the output where the claim appears
- [ ] If assessment semantics changed, `RULE_VERSION` was bumped and tests pin the new decision table
- [ ] No novelty/marketing claims for hashing, metadata reading, OCR, tool lists, or username checks

## Data & privacy

- [ ] No real investigation data, personal data, credentials, or secrets are included
- [ ] Fixtures are synthetic
- [ ] New/changed files respect at-rest permission expectations (`0700` dirs, `0600` db, `0400` evidence)

## Licensing

- [ ] New code is Apache-2.0-compatible
- [ ] No prose copied from CC BY-SA (Awesome OSINT, WhatsMyName) or unlicensed (Bellingcat) sources
- [ ] Third-party attribution recorded where applicable

## TUI changes

- [ ] Terminal recording or before/after description attached
- [ ] Keymap docstring / in-app help updated in the same PR

## Test plan

<!-- How were the changes verified? Note any behaviours deliberately NOT covered. -->
