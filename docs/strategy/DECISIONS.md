# TRACEFIELD — Decision Log

> Arbitration record for disagreements raised in the 20-role review
> (`20_ROLE_REVIEW.md`, `teams/team_*.md`) and the engineering choices made
> during implementation. Each decision states the alternatives considered and
> the reason the chosen option won. Decisions are dated 2026-10-16 unless noted.

## D1 — Project license: Apache-2.0 (code) / CC BY-SA 4.0 attribution (catalogue data)

Alternatives: MIT; GPL-3.0; dual license.

Apache-2.0 chosen for the code because it is the brief's default candidate, it
carries an explicit patent grant, and there is no conflicting upstream code in
the repository (the repo is greenfield; all bundled data carries its own
licence file and attribution in `data/catalog/source-manifest.json`). The
catalogue/data licence is treated **separately**: Awesome OSINT rows are CC
BY-SA 4.0 and are used with attribution; descriptions are project-authored
factual prose, never paraphrases of CC BY-SA or unlicensed source text.
Bellingcat toolkit content is link-only (no repo-root license file exists).

## D2 — Stack: Python ≥3.11 (CI matrix 3.11/3.12/3.13), Typer + Rich + Textual + Pydantic + SQLite + HTTPX

Alternatives: Click directly; Textual-only UI; PostgreSQL; httpx vs aiohttp.

Typer chosen over raw Click for the typed-parameter ergonomics (note: Typer
0.27.x vendors its own click fork — command bodies raise `SystemExit`, not
`typer.Exit`). Textual chosen for the TUI because it is pure Python, testable
headless via `run_test()`, and shares Rich's rendering model. SQLite chosen for
the local-first single-file store. HTTPX chosen for its request-hook and
transport-pinning APIs needed by the SSRF guard.

## D3 — Origin clustering algorithm: origin-r3 containment

Alternatives: single fixed Jaccard on word 5-grams at 0.8 (the original);
MinHash/LSH; entity/number-overlap merge channel.

The review (C2) proved the original representation wrong in both directions:
frozenset shingles discarded word order (reversed text = 1.0) and the
normalizer deleted non-Latin text. origin-r3 uses **max containment over
ordered k=3,4,5 shingles**: `NEAR_DUP_THRESHOLD = 0.8` merges (containment ≥
0.8), `RELATED_FLOOR = 0.5` emits advisory `related_text` edges that do **not**
merge. Containment (not Jaccard) is required because syndicated copies embed
the original plus a kicker — Jaccard dilutes, containment catches. Unicode
tokenization keeps Cyrillic/Arabic verbatim copies at 1.0.

**Numeric/entity channel is deliberately NOT a merge blocker.** Figure
divergence (two→three) on otherwise-contained text keeps a high containment
score and remains a *contradiction candidate* for analyst review, not an
origin-merge veto. Rationale: syndicated wire copy legitimately updates
figures after first publication; blocking merges on numbers would fragment one
origin into several and re-introduce the independence overcounting the whole
mechanism exists to prevent. Cross-cutting numeric conflicts belong to
`core/contradictions.py` (which flags differing number sets with severity
`candidate`, always requiring review). Consistent with review item 12, which
recorded only the ordered-shingle and Unicode fixes.

## D4 — Assessment decision table (assess_claim)

Alternatives: score-based confidence; auto-demote on unreviewed support;
treat rationale as provenance.

The table is now explicit and pinned by tests:

| Situation | Outcome |
|---|---|
| Confirmed CONTRADICTS, no confirmed SUPPORTS | `CONTRADICTED_BY_AVAILABLE_EVIDENCE` + "not proof of falsity" caveat |
| Confirmed CONTRADICTS + confirmed SUPPORTS | `CONTESTED` (analyst must resolve) |
| ≥2 confirmed independent origins + corroboration + none clustered | `CORROBORATED_WITH_LIMITATIONS` (independence caveat) |
| Confirmed supports but <2 independent or no corroboration | `SUPPORTED_BUT_UNCONFIRMED` (+ cluster-overstatement caveat when applicable) |
| Only unreviewed supports | `INSUFFICIENT_EVIDENCE` ("Unreviewed machine suggestions are not evidence") |
| Nothing | `UNASSESSED` |

Review C2's objection is honoured: unreviewed support can no longer be
silently outranked by a confirmed contradiction into a "contradicted" label —
the contradiction branch now requires **confirmed** contradict relations.
`provenance_completeness` is computed from `Relation.evidence_ids` + rationale
(both required for "complete"), never from rationale text alone; the review's
recommendation to rename rationale-only scoring was implemented by measuring
both (`rationale and evidence_ids`).

## D5 — GPS / sensitive metadata on export: list, never silently rewrite

Alternatives: strip GPS from binary originals on export (the dead
`strip_precise_gps_on_export` setting); rewrite images; do nothing.

Export never silently rewrites binary originals (that would falsify the
evidence object and break re-verification of what the analyst actually
stored). Instead the export contains `SENSITIVE_METADATA.txt` listing **key
names, not values**, for GPS-bearing files, and the export README states that
the operator is responsible for handling before distribution. The dead setting
was removed; behaviour is documented honestly rather than advertised.

## D6 — Exit-code contract

`0` ok, `1` error, `2` not found, `3` usage, `4` network blocked, `5`
unavailable. Verified by shell probes: username-check without opt-in → 4;
`--fetch` against loopback/metadata → 4 even with `TRACEFIELD_ALLOW_NETWORK=1`
(the SSRF guard is per-request, not a global override); delete without `--yes`
on an existing case → 3; delete of a missing case → 2 (resolve-first, then
usage). Typer's own unknown-command usage error is mapped to 3 so 2 stays
reserved for genuine entity-not-found.

## D7 — Catalogue data representation: JSONL is the shipped artefact; DB tables remain unwired (accepted debt)

Review A1 recommended deleting the `catalog`/`providers` SQLite tables or
wiring them. Decision: **defer**. The JSONL file + `importlib`-free
`_default_catalog_path()` is the single wired path; `Catalog.validate()` runs
in CI over the real 2,264-record dataset. The unused tables stay at
`SCHEMA_VERSION = 1` to avoid a migration this early; they are recorded as
known debt in `IMPLEMENTATION_STATUS.md` and must be wired or dropped before
schema v2.

## D8 — TUI lifecycle: override private `_shutdown` to close the DB

Textual's `run_test()` teardown calls `app._shutdown()` directly (not the
`ExitApp` message), so a public `on_exit_app` hook alone leaks the sqlite
connection (GC-time `ResourceWarning` fails the `filterwarnings = ["error"]`
suite). Decision: override `_shutdown` with `try/finally` around
`super()._shutdown()`. Accepted risk: if a future Textual renames the private
method, the override silently stops firing and the test suite surfaces the
leak as a warning — an acceptable tripwire versus threading cleanup through
every exit path.

## D9 — Test async strategy: `asyncio.run()` around `app.run_test()`, no pytest-asyncio

Alternatives: add pytest-asyncio; anyio plugin (anyio is already present as a
Textual dependency).

The TUI smoke tests drive `app.run_test()` (an async context manager) from
sync test functions via a small `asyncio.run(scenario())` helper. This adds no
dependency and keeps `pytest` configuration identical across suites.

## D10 — Ruff B008 ignore (Typer parameter idiom)

Typer's `typer.Option(False, "--json", ...)` idiom is flagged by flake8-bugbear
B008 (function call in default arg). Decision: ignore B008 project-wide with a
comment; this is the documented Typer style and fighting it would mean boxing
every parameter.

## D11 — Terminal safety: escape at the display boundary, store verbatim

Case titles and other analyst strings are stored **verbatim** (including
control characters) — the database is not a rendering surface. Every render
site passes strings through `s()` = rich-markup escape + ANSI/OSC sanitization;
`report` output is printed with `markup=False, highlight=False`. JSON output
uses `json.dumps` escaping. Tests pin both properties: raw bytes survive
round-trip through storage/JSON, and `[bold` markers appear literally in table
output (markup not interpreted).

## D12 — SSRF guard: explicit deny list + connection pinning

Python 3.13's `ip.is_global` returns True for multicast (`224.0.0.1`,
`ff02::1`) and deprecated site-local (`fec0::1`) — measured on this machine —
so `_is_blocked_ip` uses an explicit deny list (multicast, unspecified,
loopback, link-local, reserved, private, `fec0::/10`) instead of trusting
`is_global` alone. Fetches are connection-pinned: resolve once, validate, then
connect to the literal IP with Host/SNI preserved, closing the DNS-rebinding
TOCTOU the review flagged. Redirect targets re-enter the same validation.

## D13 — Assumptions the review challenged and we kept visible

- "A terminal workbench is differentiated" — kept as a *hypothesis*; the
  defensible core is the case/evidence/provenance contract, not the catalogue
  (see `COMPETITOR_MATRIX.md` §B1.9).
- "≥2 distinct `from_id`s = independence" — rejected; independence requires
  origin-cluster awareness plus analyst confirmation.
- "HTTP 200 means profile exists" — rejected; per-provider soft-404 markers
  required; `presence_on_200` yields at most `LIKELY_MATCH`.
- "Local-only means safe" — rejected; at-rest permissions (dirs `0700`, DB
  `0600`) and export redaction are real privacy surfaces.
- `Typing :: Typed` classifier — kept only because mypy strict is now green
  (34 files); it was removed from consideration until then.

## D14 — Provenance model: PROV-DM-aligned concepts, no PROV serializer; no STIX/TAXII/CASE-UCO at P0

Per brief §14, W3C PROV was reviewed (`RESEARCH_REGISTER.md`, fetched
2026-10-16). TRACEFIELD's records map onto PROV-DM concepts without shipping a
PROV encoding: `EvidenceItem` ≈ Entity (`wasGeneratedBy` a collection
activity), `AnalysisEvent` ≈ Activity with per-hop digests, operator ≈ Agent,
`Relation.DERIVED_FROM` ≈ `wasDerivedFrom`, syndicated copies ≈ `alternateOf`
handled by origin clustering. The mapping stays conceptual — a PROV-XML/JSON
serializer is deferred until an exchange use case demands it (schema v2
backlog). STIX/TAXII and CASE/UCO were considered and **rejected for P0**: no
concrete interoperability consumer exists in scope, and the dependency/mapping
cost would buy no analyst capability. Revisit when an export target requests
one of them.

## D15 — Packaging: catalogue data ships inside the wheel (P0, from audit G7)

The fresh-venv install test (2026-10-19) proved the wheel cannot serve
catalogue commands: `data/` is excluded by the wheel target and
`cli/main.py:1186` assumes a source checkout. Decision: **`data/catalog/` is
part of the distribution** — wheel target gains a force-include of the
catalogue into the package, and path resolution becomes package-relative with
the current repo-relative lookup retained as fallback for editable installs.
Failure mode when data is genuinely absent keeps exit `2` (not found) with
the existing explicit message. Source-tree behaviour and the 2,264-record
validation gate are unchanged. (Debt #5 promoted to P0.)

## D16 — Redirects: every `--fetch` hop gets first-hop-grade treatment (from audit F1)

The first hop is IP-pinned; redirect hops are only policy-validated inside
the request hook, leaving a validate-then-connect DNS-rebinding window. The
inline comment claiming full coverage is wrong and must be corrected with the
fix. Decision: handle redirects **manually up to `max_redirects`**, re-running
`validate_host` + connection pinning (and Host/SNI preservation) per hop —
same guarantees as hop 1 — rather than letting `httpx` reconnect on fresh
DNS. If a hop cannot be pinned, fail closed with exit `4` (network blocked).

## D17 — Scope boundary: no evasion features, ever (from audit §5 / research refresh)

Research refresh (2026-10-19) recorded that Maigret offers CAPTCHA/anti-bot
"partial bypass" and FlareSolverr integration. Decision: TRACEFIELD **never**
integrates CAPTCHA-solving, Cloudflare/bot-evasion, or similar bypass
behaviours — collection stays on plainly reachable public endpoints under the
doubly-opt-in network model (brief: no captcha evasion). Catalogue
descriptions may state such features factually for other tools, with no
endorsement and no wiring. Also recorded: `run_backend` gains an enforced
literal allowlist (`exiftool`, `ffprobe`, `tesseract`) matching its existing
docstring, and `migrate()` must refuse a newer-schema DB with exit `5`
(unavailable) instead of silently succeeding (audits F2, F3).

## D18 — Mission planner: deterministic table-driven ranking, no model, proposal-only

The planner (`src/tracefield/planner.py`, `plan-r1`) is a fixed, versioned
capability table (9 built-in capabilities) plus optional inert-catalogue
suggestions. Design commitments, all test-pinned:

- **Determinism**: iteration order is fixed (capability tuple order, sorted
  matched terms, lexicographic tie-break); no clock, RNG, or network can
  influence output. Same question ⇒ byte-identical plan (`TEST-VERIFIED`).
- **Ranking**: integer score tuple `(coverage, -steps, -network)` compared
  lexicographically. Explicitly **not** a probability of anything — the
  no-percentages rule (constitution §5) applies to plans too.
- **Multi-path**: `offline-first` (local-only) vs `bounded-network`
  (includes opt-in collection; every network step states its opt-in). Paths
  are policy variants of the same coverage, not competing forecasts.
- **Proposal-only**: the planner module imports no `httpx`/`socket`/
  `subprocess` (test-pinned); it never executes a step. Approval-before-
  external-action is preserved structurally: the only executor remains the
  user running the printed command.
- **Honest gaps**: unmatched question terms are reported as
  `unresolved_terms`; an all-gibberish question yields zero-step paths
  rather than invented work.

## D19 — Adapter ecosystem: one typed boundary, one verified adapter, honest states

`src/tracefield/adapters.py` is the single sanctioned path from TRACEFIELD
to an external backend. Design commitments, test-pinned:

- **Typed, declared, never discovered**: every backend is an `AdapterSpec`
  (frozen dataclass) whose `backend` literal must be in the Phase-2
  allowlist — enforced at construction AND re-checked at call time. The
  registry is a code-review artefact, not a runtime scan.
- **One reference adapter, no bulk claims**: exactly `exiftool-meta` may
  claim `integrated` (it is exercised end-to-end by our suite);
  `ffprobe-streams` and `tesseract-ocr` are typed `spec-only` — the
  boundary exists, the integration is not verified here. Catalogue
  `HEALTHY` remains unreachable from the adapter layer: we persist no
  dated health checks, so the vocabulary offers only factual `ready`
  (version probe answered *now*), `missing-backend`, `disabled`, `blocked`.
- **Kill switch + network posture**: `TRACEFIELD_ADAPTERS=0` disables all
  adapters (maps to exit `5` unavailable); every shipped spec is
  local-only, and a future network spec must set `needs_network=True`,
  which then requires BOTH `TRACEFIELD_ALLOW_NETWORK=1` and a per-call
  opt-in — mirroring the fetch policy (D17).
- **Raw first**: `adapters run` stores the tool's raw return verbatim in
  the case workspace (`observations/<obs_id>.json`, 0600) and records an
  Observation referencing it; interpretation stays a reviewable layer.
  Reports now carry `observations` (schema v2, additive) so raw returns
  surface without being promoted to findings.

## D20 — Scope authorization is a ledger, enforced at the fetch gate

`case authorize <case> --scope "<text>" --authorized-by "<name>"` (optionally
`--revoke`) records collection-authority decisions as **hash-chained
analysis_events** (`scope.authorize` / `scope.revoke`) — the same
tamper-evident chain `case verify` checks. No separate authorization table:
a decision is an event, sharing one integrity mechanism.

- **Latest decision wins**: `case scope` (read view: declared scope, ledger
  entries, active or not) and the gate both read the most recent
  scope event. A later revoke blocks; the ledger cannot hold two
  simultaneous states.
- **Enforcement is at the collection boundary**: `source add --fetch` exits
  `4` (network-blocked) with an actionable `case authorize` hint unless the
  latest decision is an active grant. The existing global
  `TRACEFIELD_ALLOW_NETWORK=1` opt-in remains, but is no longer collection
  authority by itself: it enables the network stack; the ledger authorizes
  the collection.
- **Soft host advisory, not semantic matching**: scope text is free-form,
  so when a fetch target's host is not mentioned in any recorded grant text,
  the CLI prints a warning that names the host and tells the operator to
  confirm — it does not refuse. Claims of semantic scope enforcement stay
  out of the product.
- **Username checks deliberately stay env-gated** (`TRACEFIELD_USERNAME_CHECK`)
  and are NOT behind the case ledger: `username check` is a public-profile
  existence probe run against a curated allowlist, not case collection of
  material; folding it into per-case authorization would blur what the
  ledger warrants. Recorded here so the asymmetry is a decision, not an
  oversight. Rationale and residual limits are stated in OOVS `-01` scope notes.

## D21 — Report identity: one registered revision per rendered document

Data schema v2 (additive-only migration: `case_reports`, `report_corrections`,
`dissemination` + DB integrity triggers; no column or data changes) carries
the dissemination-control machinery (OOVS-09):

- **One identity per document**: `ReportRepo.register()` mints revision N and
  links it (supersedes N-1, superseded_by back-filled). `case-export` builds
  **one registered payload and renders `report.json` + `report.md` from that
  same identity** — registering per format would mint two revisions for one
  shipped document, a false trail. `report` (CLI) registers by default;
  `--no-register` stays available and unregistered payloads honestly read
  `revision: "unregistered"` / empty `report_id` rather than faking one.
- **Corrections are appended, never rewritten**, addressed at a specific
  report id, and travel **forward with the lineage** (`corrections_for_chain`
  includes corrections against ancestors): a re-render never silently drops a
  known error. Each correction also appends a hash-chained
  `report.correction` event.
- **Shipments are recorded, not automated**: `case-export --recipient`
  writes a dissemination row (report id, recipient, time) and the export
  README names the exact revision and the duty to notify prior recipients after
  a correction. Nothing sends anything; the register makes the notification
  traceable (`report-history`).
- **Verdict discipline**: OOVS-09 stays `FAIL` until the author identity
  string exists (user decision, FS-17) — mechanism shipped, verdict held,
  per the mapping's promotion policy.

## D22 — Catalogue verification is operator-manual; freshness listing, not a health job

FS-20 asked for a health-check job wired to `last_checked` **or** the columns
dropped before schema v2. Decision: **neither automated checking nor dropping**
— the catalogue is inert data, and a shipped "health" label is exactly the
kind of unverifiable claim the project refuses to make. Instead:

- `catalog stale [--max-age-days N]` lists entries whose `last_checked`
  predates the cutoff, plus entries with unparseable or missing dates,
  reported as `unknown` — unknown freshness is **reported, never guessed**.
- The command states plainly that a stale listing is **not a health verdict**
  and never contacts upstream. Writes are zero.
- Schema v2 retains `last_checked`/`health_result` as inert columns for the
  operator-manual workflow; `health_result` remains unclaimed by the tool.
- Consequence accepted: no automated staleness detection beyond the listing.
  Risk-register row A3/R-A3-4 carries the residual as **Accepted (decided)**.

## D23 — The report author is the operator (FS-17 closed), identity never automated

FS-17 required a real author identity before the dissemination document
block could claim authorship. Resolved 2026-10-29:

- **The maintainer supplied and confirmed the string** —
  `killerdasher — github.com/killerdasher/TRACEFIELD` — after being asked
  explicitly what reports should carry. It was not invented, not defaulted,
  and not taken from git metadata: authorship is a claim, and only the
  author can make it.
- **Per-operator, never tool-level**: the identity lives in the operator's
  config file (`~/.config/tracefield/config.toml`, `report_author` key;
  `TRACEFIELD_REPORT_AUTHOR` env var wins). This project deliberately
  refuses a shipped default author: anyone else's install would then stamp
  the maintainer's identity onto reports about their evidence — a false
  attribution, the exact failure mode the honesty rules exist to prevent.
  Unconfigured operators get `author not set` — an unattributed report is
  honest about being unattributed.
- **Config loading is validated and fail-closed** (accepted-key allowlist,
  valid-TOML required; violations ignore the whole file and surface in
  `doctor`). A typo must never silently half-apply an identity, and never
  crash reporting.
- **OOVS-09 re-verdict**: with (a) the register/corrections/recipient
  machinery (D21), (b) the configured + confirmed author, and (c)
  regression-pinning tests for all of it, the self-assessment promotes
  OOVS-09 to `PASS (scoped)` with explicit limits — recipient *notification*
  of a correction stays a human workflow the tool supports but does not
  automate, and official acceptance tests remain unrun.

## D24 — Unwired `catalog`/`providers` SQLite tables: DROP at schema v3 (H0-2)

Alternatives: wire them as a mirror of the JSONL catalogue; keep them
indefinitely. Chosen 2026-11-07: **drop**. Evidence: the tables exist at
`src/tracefield/storage/database.py` (`catalog`/`providers`, created since
the first schema) with zero reads/writes anywhere in `repositories.py`;
the D7 "wire or drop before schema v2" deadline passed; the JSONL catalogue
remains the single source of truth (`docs/strategy/DECISIONS.md` D22's
operator-manual verification stays authoritative). Wiring a second
representation of the same data would double the drift surface for zero
analyst value — the honesty rules forbid carrying a table whose contents
nobody maintains. **Implementation contract:** the DROP happens in the
schema-v3 migration window with a migration test asserting (a) tables
absent after migrate, (b) the tripwire assert (`SCHEMA_VERSION`) updated in
the same change, (c) downgrade not supported (documented, one-way). No
drop occurs during v2.x releases.

## D25 — Worker offload (A2/R-A2-3): measured — the DB query is NOT the bottleneck (H0-3)

Measured 2026-11-07, on this machine, one synthetic case with 10,000
evidence rows (fresh data root):

| Probe | Result |
|---|---|
| `EvidenceRepo.add` ×10,000 | 0.358 s total |
| `list_for_case()` (query + typed construction, 10k) | **94.2 ms** (second run: 82.5 ms) |
| `json.dumps` of all 10k typed records | 42.9 ms (4.14 MB) |
| Plain-text render, 10k lines | 2.3 ms |
| Full CLI `evidence list --case …` table render | **≈5.2 s wall** (JSON variant ≈6.3 s) |

Conclusion: the A2/R-A2-3 hypothesis ("render-path synchronous queries may
hitch the TUI") is **refuted at the DB layer** — a 10k-row query costs
<100 ms. The dominating cost is *rich-table rendering* (~5 s at 10k rows),
which is where Textual worker offload (B-09) must act, together with ingest
batch processing. Decision: keep repository calls on the calling thread;
B-09 is re-scoped to "workers for rendering + import batches", and the
R-A2-3 residual is re-rated **Measured (query benign; render offload
pending)** rather than Open-without-evidence. Re-measure if a real case
exceeds 50k rows.

## D26 — The one-off e2e reproducibility flake: instrumented, never silenced (B-05)

The failure observed 2026-11-06 (assessment-reproducibility assert,
`tests/e2e/test_demo_case.py:378` region) is handled by policy, not by a
guess: 10 additional full runs of that e2e file on 2026-11-07 were all
clean (cumulative 18 clean runs after the single observed failure; root
cause unproven). Rules adopted: the pin test is never removed or weakened
to make it pass; if it recurs ≥2 times within any 50-run window, a timing
instrument is added and the diagnosis re-opened; B-05 stays listed in RISK
_REGISTER until two consecutive release batteries (plus these 18 runs)
show no recurrence. Anti-goal: chasing a 1-in-19 phantom to extinction.

## D27 — `case-import` grammar: `--file` option, not a bare positional

Chosen 2026-11-08 during B-03: the import file is passed as
`tracefield case-import --file <path>`, while status stays a plain
subcommand (`case-import status`). Cause: Click/Typer dispatches group
callbacks with a declared positional BEFORE subcommand resolution, so a
bare-path grammar made the literal string `status` parse as a filename
("File 'status' does not exist"). Renaming the subcommand or swallowing it
with `exists=False` heuristics were the rejected alternatives — both trade
ambiguity for grammar fidelity. The `--file` option keeps both the
`case-import` name and an unambiguous `status`; the command's help text
records the reason.

## D28 — Batched import + honest cancellation (J7): committed batches are
retained; a partial import is never claimed complete

Chosen 2026-11-08, shipped with B-06. `run_import` decomposes into
`prepare_import` (fail-closed pre-conditions + raw-first 0o400 copy) →
`write_rows_batch` (per-batch commit points) → `finish_import_event`. When
the TUI-side import op is cancelled (or a worker errors) between batches,
already-committed rows are RETAINED — deleting live data on cancel was the
rejected alternative, since committed rows are real observations of real
rows the operator saw — and the chain event records
`incomplete=<cancelled|error> rows_written=<N>` in its inputs, plus the
report row-gap consequences stay visible in `case-import status`. A
complete import carries NO such marker. Related invariants pinned by
tests: the analysis event chain closes across cancelled imports
(hash-chain-closure test); dismissed observations cannot be promoted again
without a fresh recorded decision (R-SEC-8); the blank-reason dismissal is
refused (exit 3) rather than recorded; and an operator-supplied
`--tool-version` flag was deliberately NOT added — version provenance comes
from the file's own declaration only, absent versions import as
`unknown` (R-SEC-4, closing the forged-provenance surface).

## D29 — Dismissal is terminal in 0.2; the refusal message says so honestly

Chosen 2026-11-08, closing fresh-context adversarial review M-1. The
`candidate.dismiss` action permanently closes an observation from promotion:
there is no re-consider event type in this build (`candidate.restore` was the
considered alternative and is deferred — a new event type needs its own
design cycle, not a side-effect of a message change). The dismissal refusal
now states this plainly ("that dismissal is terminal in this build (D29…
promotion stays refused for the life of this observation") instead of the
former text that promised a "fresh analyst decision" re-consider path that
did not exist. Related honest-display fix: the triage overlay shows a
dismissed observation as dismissed regardless of a later defer — what the
UI displays must match what the state machine enforces.

## D30 — Promotion records the URL provenance deliberately; boundary made
explicit, persistence made self-grounding, re-imports never silent

Chosen 2026-11-08, closing review findings m-6/m-7/m-10. Three related
facts made explicit rather than implicit:

1. **URL persistence is deliberate.** Promoting an observation copies the
row's `url_user` into the Source locator and the `candidate.promote` event
inputs, because the provenance must survive even if the observation is later
pruned from the working set. This is a recorded reference, never a fetch
(R-SEC-6 holds — the closed-input subset of `tracefield.ingest` has no
network imports). Boundary: R-SEC-5's "secrets never echoed" applies to the
IMPORT path — summaries/excerpts/terminal during ingest; a deliberate
post-review provenance copy into the hash-chained ledger is the analyst's
recorded judgment line, visible in `source list` and Runs by design.
Operators handling credential-bearing URLs should dismiss instead of promote.

2. **The Source row grounds itself.** `limitations` now carries the FULL
file sha256, `row_record=<n>` and the observation's `raw_ref` (the former
12-char sha truncation could not be re-grounded without the original
observation row).

3. **Re-imports are additive and named.** Re-importing byte-identical bytes
imports again (there is no deduplication of live data by design), and the
result now names the earlier evidence (`duplicate_of` in the payload, a
"[yellow]note[/yellow]" line in the CLI render) — the "10 captured rows"
story can surface as 20/30 counts, visibly and deliberately, never silently.
Residual (accepted): `case-import status` counts observations by tool name,
so manually created observations with `--tool sherlock` join the ingest
totals; counts are case-scoped and tool-labelled, not import-scoped.
