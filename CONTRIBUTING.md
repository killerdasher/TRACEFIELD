# Contributing to TRACEFIELD

Thanks for considering a contribution. TRACEFIELD is a local-first OSINT
field workbench: the project's value is **evidence provenance and honest
claims**, so contributions are held to a higher honesty bar than feature
count.

## Development setup

```bash
git clone <repo-url> && cd TRACEFIELD
python3.13 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest -m "not network"        # full suite, no live network
.venv/bin/ruff check src tests && .venv/bin/ruff format src tests
.venv/bin/mypy src                       # strict; must stay clean
TRACEFIELD_HOME=/tmp/tf-dev .venv/bin/tracefield doctor
```

Never point a dev install at a real investigation's `TRACEFIELD_HOME`. Use a
scratch directory. Tests already isolate themselves via the `tf_home` fixture.

## The gates every PR must pass

- `pytest -m "not network"` — all green (`filterwarnings = ["error"]`; a
  ResourceWarning fails the build on purpose).
- `ruff check src tests` and `ruff format --check src tests`.
- `mypy src` (strict).
- `tracefield catalog validate` if you touched `data/catalog/`.
- No new network calls in tests. Live-network behaviour is `pytest.mark.network`
  and is opt-in only.

## Catalogue contributions

The catalogue is **inert data, never code**. A catalogue row may not import,
execute, or reference executable content — this invariant is enforced by
`registry/catalog.py` and its tests, and by review.

Rules for adding or editing rows in `data/catalog/tools.jsonl`:

1. **Descriptions are project-authored.** Do not copy or paraphrase prose from
   CC BY-SA sources (Awesome OSINT, WhatsMyName) or unlicensed sources
   (Bellingcat toolkit). Write one or two factual sentences yourself.
2. **Attribution is mandatory.** Every row carries `source_list` and
   `attribution`. A `license_id` of `NOASSERTION`/`UNKNOWN` may never be
   translated into "permissive".
3. **Licence review is recorded, not assumed.** `license_review_state` stays
   `unverified` until someone has read the actual licence file; record the
   URL and date in `license_source`.
4. **Key requirements are names only.** `key_env_vars` stores variable names;
   values never appear anywhere in the repo.
5. **Tiered honesty.** `integration_state=integrated` requires an adapter
   manifest reference; `verification_state=verified` requires a dated check.
   Do not inflate states.
6. Run `tracefield catalog validate` — it must print `catalogue OK`.

## Adapter / integration proposals

Open an "adapter proposal" issue before writing code. Minimum contract:

- A `ToolAdapter`-shaped surface: declared capabilities, credential
  requirements (names), network policy, `health()`, and a `run()` that returns
  a result object with status + caveats.
- Adapters never write to the case store directly; they return observation
  payloads and the caller decides persistence.
- Failure taxonomy is fixed: `ok`, `UNAVAILABLE`, `RATE_LIMITED`, `BLOCKED`,
  `TIMEOUT`, `PROVIDER_ERROR`, `POLICY_REFUSED`. Do not invent new top-level
  statuses without a discussion issue.
- Rate limits and politeness: respect 429/403 with backoff; never circumvent
  a block; default to ≤1 request/second for profile checks.

## Code conventions

- Python ≥3.11 target (`target-version = "py311"`), strict typing, no
  `Any` leakage in public signatures.
- Deterministic exit codes: 0 ok, 1 error, 2 not found, 3 usage, 4 network
  blocked, 5 unavailable. Never reuse a code for a different meaning.
- Every user-facing string that can contain external or analyst-supplied text
  passes through `s()` / `sanitize_for_terminal` before rendering.
- Network is opt-in and fails closed. New network paths must route through
  `validate_fetch_url` and the connection-pinning pattern in
  `fieldtools/fetch.py`.
- No command may be advertised in help text, TUI strings, or README without a
  working implementation.

## License and privacy policy for contributions

- Contributions are accepted under Apache-2.0 (the project license). By
  submitting a PR you agree your work is licensed as such.
- Do not commit real investigation data, credentials, personal data, or
  anything you are not authorized to share. Test fixtures must be synthetic.
- Do not commit secrets; CI runs secret scanning where the platform provides
  it.

## Commit / PR hygiene

- Small, reviewable PRs; one concern each.
- Bug reports: use the bug template; include the exact command, exit code,
  and output (sanitized).
- TUI changes: include a terminal recording or before/after description.
- Analytic changes (assessment rules, clustering, contradictions): include a
  test that pins the new behaviour and update `RULE_VERSION` if semantics
  change.

## Code of conduct

Participation is governed by [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
