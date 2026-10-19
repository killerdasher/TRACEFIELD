# TEAM A — Engineering & Architecture Review

> Simulated role-based review conducted by independent review subagents on 2026-10-16. These are role perspectives, not interviews with real people.

**Unit under review:** TRACEFIELD v0.1.0 (repository root), ~4,356 lines of Python under `src/tracefield/`, no tests, no CI workflow files, no docs, no catalogue data.

**Method.** Every claim below is grounded in code that was read line-by-line and/or exercised on this machine on 2026-10-16. Commands executed during this review (against a scratch `TRACEFIELD_HOME=/tmp/opencode/tfhome*`):

```
tracefield --help / init / doctor / case create|list|show / case-delete
tracefield source add (with and without --fetch)
tracefield claim add|list / evidence attach|list|verify
tracefield report -f json|markdown / case-export / tui
ruff check .            -> 31 errors (14 × F401 unused imports)
mypy (project config)   -> 24 errors in 10 files, strict = true
pytest                  -> "no tests ran in 0.00s" (tests/ is empty)
```

Observed failures reproduced during review (details in role sections): `evidence attach <directory>` → raw `IsADirectoryError` traceback, exit 1; `case-export` on a case containing redaction-triggering evidence → raw `PermissionError` traceback, exit 1, partial bundle left on disk; `tracefield tools status` and `tracefield username check` → `No such command`, exit 2; evidence attached to case B using a `Source` belonging to case A → accepted.

**External references used (all fetched 2026-10-16):**

- W3C Recommendation, *PROV-DM: The PROV Data Model*, https://www.w3.org/TR/prov-dm/
- Textual docs, *Testing*, https://textual.textualize.io/guide/testing/
- NO_COLOR informal standard, https://no-color.org/ (page last updated 2026-01… shown as 2026-10-12 on page)
- SQLite C interface, *Set A Busy Timeout* (`sqlite3_busy_timeout` / `PRAGMA busy_timeout`), https://www.sqlite.org/c3ref/busy_timeout.html

Nothing in this review is sourced from community consensus, benchmark numbers, or blog posts. Where I could not verify something, it is listed as an **Open question**.

---

## Architecture snapshot (as-built)

```mermaid
flowchart TB
  subgraph outer["Outermost — I/O & presentation"]
    CLI["cli/main.py<br/>typer app, 782 lines"]
    TUI["tui/app.py<br/>Textual app, 274 lines"]
  end
  subgraph mid["Middle — services"]
    RP["reporting/{build,export}.py"]
    FT["fieldtools/{inspect,ocr,fetch,username}.py"]
    PR["core/provenance.py<br/>(CaseWorkspace, IntegrityManifest)"]
  end
  subgraph inner["Inner — state & policy"]
    ST["storage/{database,repositories}.py"]
    AN["core/analysis.py"]
    OR["core/origins.py"]
    CT["core/contradictions.py"]
  end
  subgraph leaf["Leaves — no project deps"]
    DOM["core/domain.py"]
    SEC["security/{urls,sanitize,redact}.py"]
    REG["registry/catalog.py"]
    CFG["config/settings.py"]
  end
  CLI --> RP & FT & PR & ST & DOM & SEC
  TUI --> ST & DOM & SEC & REG & CFG
  RP --> AN & ST & PR & SEC
  FT --> SEC & DOM & PR & CFG
  PR --> DOM & ST
  AN & OR & CT --> DOM
  ST --> DOM
  REG --> DOM
```

Dependency-direction rule that *should* hold and currently does not: **arrows must point toward `core/domain.py`.** `core/provenance.py:15-22` imports `storage.database` and `storage.repositories`, so `core` depends upward on `storage` while `storage/repositories.py:12-28` depends downward on `core/domain` — a package-level inversion living inside a package whose own docstring (`core/domain.py:4-5`) promises purity.

As-built data flow for the one end-to-end path that works:

```
CLI source add ──► SourceRepo.add ──► analysis_events (hash-chained, manual)
CLI evidence attach ──► CaseWorkspace.attach_file ──► fs copy + chmod 0400
                                          └──► EvidenceRepo.add ──► analysis_events
CLI report ──► build_case_payload ──► assess_claim(relations=∅ always) ──► UNASSESSED
```

The dotted arrows are the ones that do not exist yet but the whole design depends on: `relation add`, `assertion add`, `observation add`, `cluster run`, `contradict scan`, `events verify`.

---

# A1. Principal Systems Architect

## A1.1 Findings

1. **The domain model is the strongest part of the codebase.** `core/domain.py:102-248` defines `Case`, `Source`, `EvidenceItem`, `Observation`, `Assertion`, `Claim`, `Relation`, `OriginCluster`, `AnalysisEvent`, `AssessmentVector` with stable prefixed IDs (`new_id`, domain.py:21-22), UTC-`Z` timestamps (`utcnow`, domain.py:17-18), and `StrEnum`s for every closed vocabulary. `Observation` (raw, uninterpreted) vs `Assertion` (evidence-linked interpretation) vs `Claim` (the proposition under test) is a genuinely correct three-way split, and `AssessmentVector` is explicitly documented as "never a single truth score" (domain.py:232-233).

2. **`Relation` has no evidence link — the central architectural gap.** `Relation` (domain.py:195-204) carries `from_id`, `to_id`, `relation`, `rationale`, `method`, `review_state` — but no `evidence_ids`. `Assertion` *does* have `evidence_ids: list[str]` (domain.py:168), and `Observation` has `evidence_id` (domain.py:149), yet neither is ever written by any code path (see A4). Consequence: the claim→evidence chain that the product's entire pitch rests on cannot be represented in the schema that ships.

3. **`Relation.from_id`/`to_id` are untyped polymorphic strings.** No FK (storage/database.py:112-113), no entity-type discriminator, no validation that both ends exist or belong to `case_id`. `core/analysis.py:57` then computes `distinct_origins = {r.from_id for r in confirmed_supports}` — i.e. it treats the *relation source* as an "origin", but nothing documents whether `SUPPORTS` flows evidence→claim or claim→claim. `reporting/build.py:40` selects relations with `r.from_id == claim.id or r.to_id == claim.id`, which is direction-agnostic, so a relation where the claim is the *supporter* would still be counted as support for itself. This is a semantic ambiguity that will silently corrupt assessments once relations exist.

4. **Six of ten domain entities are unreachable.** `ObservationRepo.add` (repositories.py:303), `AssertionRepo.add` (repositories.py:385), `RelationRepo.add` (repositories.py:345), `ClusterRepo.add` (repositories.py:430), `find_origin_edges`/`cluster_from_edges` (origins.py:62, 95), and `find_contradictions` (contradictions.py:50) have **zero callers** in `src/tracefield/`. Verified by grep. The `observations`, `assertions`, `relations`, `origin_clusters`, `catalog`, and `providers` tables (database.py:83-197) are created and then never inserted into.

5. **Storage abstraction is concrete, not abstract.** `CaseWorkspace.__init__(root, db: Database)` (provenance.py:49) and every repository take the concrete `Database` class. There is no protocol/interface, so an in-memory store for tests, an encrypted store, or a Postgres store would each require editing `core`, `storage`, `reporting`, `cli`, and `tui`.

6. **Schema versioning has two sources of truth.** `SCHEMA_VERSION` lives in both `src/tracefield/__init__.py:4` (=1) and `storage/database.py:15` (=1). `IntegrityManifest` reads it from the package root (provenance.py:189) while `Database.migrate()` reads its own. They will diverge.

7. **The catalog DB tables duplicate the JSONL catalogue and neither is wired to anything.** `catalog` (database.py:147-181) and `providers` (database.py:186-197) mirror `CatalogEntry` fields 1:1, but `registry/catalog.py` persists to JSONL only (`Catalog.save`, catalog.py:142-149), and no repository reads or writes those tables. Meanwhile `tui/app.py:192-195` constructs the catalogue path as `Path(tracefield.__file__).parent.parent.parent / "data" / "catalog" / "tools.jsonl"` — a source-tree-relative path that is wrong for any wheel install and that does not exist in this repo (`data/` is empty).

8. **Configuration is env-only by design, but the type system advertises otherwise.** `Settings.config_path` (settings.py:42) and `default_config_path()` (settings.py:27-34) exist, are never read, and `load_settings()` (settings.py:64-73) documents this as intentional for P0. Meanwhile `pyproject.toml` has no config-file dependency and no `tomllib` usage. Dead API surface.

9. **Extension points: none.** No `[project.entry-points]` in `pyproject.toml` beyond `[project.scripts]`. There is no `ToolAdapter` protocol, no discovery hook, no plugin directory. The three ad-hoc "connector" shapes that exist (`run_backend` argv allowlist, `ProviderRule` dataclass, `fetch_source`) share no interface (see A3).

10. **The event hash chain is well-designed and then abandoned.** `compute_event_digest` (repositories.py:538-547) + `EventRepo.verify_chain` (repositories.py:522-535) is a clean, honestly-threat-modelled tamper-evidence chain ("Not a blockchain" — good). But `verify_chain` has no caller, no CLI command, and no report section. The TUI "Runs" view (`tui/app.py:216-231`) shows digests but never verifies them.

## A1.2 Risks

- **R-A1-1 (High).** Shipping the assessment engine over an entity (`Relation`) that cannot reference evidence produces reports whose "provenance_completeness" is computed from the presence of free-text `rationale` (`analysis.py:67-75`), not from evidence linkage. An analyst will read "complete" as "evidence-backed". That is a category error baked into the schema.
- **R-A1-2 (High).** The core↔storage inversion means any storage-backend work forces edits in `core/`, which will trigger import cycles or force a big-bang refactor at the worst possible time (when evidence volume makes a real backend necessary).
- **R-A1-3 (Medium).** Two `SCHEMA_VERSION` constants + `migrate()` reading a `meta` row before `meta` exists (database.py:225-234 handles this, but only for the empty-DB case) means a v2 migration can be applied to a manifest that still says v1, breaking export verification silently.
- **R-A1-4 (Medium).** Catalogue path derived from `tracefield.__file__` breaks under `pip install`, Nix, or any relocatable install — the TUI Arsenal workspace will render "catalogue data not loaded" for most users while the README (`README.md:72`) tells them to run a command that does not exist.
- **R-A1-5 (Medium).** Untyped `Relation` endpoints allow `case-A claim → case-B claim` edges, mirroring the cross-case `Source` reference that was reproduced in testing (see A4/A5). The schema cannot express the invariant "everything in a case stays in the case".

## A1.3 Recommendations

1. **Add `evidence_ids: list[str]` to `Relation`** (domain.py:195-204) plus a DB column and repo round-trip, and make `assess_claim` consume it for `provenance_completeness` and `evidence_directness` instead of inspecting `rationale`. Keep `rationale` as human text, not as a provenance proxy.
2. **Define and enforce the relation direction contract** in `core/domain.py` as a docstring + a `RelationDirection` note, and change `reporting/build.py:40` to select only `r.to_id == claim.id` for support/contradiction edges (claim is always the object).
3. **Introduce `storage.protocols.Repository` / `storage.protocols.UnitOfWork`** (typing.Protocol, runtime-checkable) and move `CaseWorkspace` to depend on the protocol. This is a small change today (one call site shape) and a large one later.
4. **Split `core/` into `core/` (pure: domain, analysis, origins, contradictions) and `services/` (provenance workspace, anything touching storage).** `core/domain.py`'s own docstring already promises this; honour it.
5. **Delete `catalog`/`providers` tables from `_MIGRATION_1` now, or wire them.** A schema with two representations of the same data and zero writers is pure migration debt. My preference: keep JSONL as the shipped artefact, add a single `catalog_snapshot` table only if search performance demands it.
6. **Single-source `SCHEMA_VERSION`:** `storage/database.py` should import from `tracefield.__init__`, or vice-versa — pick one direction and add an import-linter contract (see A5) so it cannot regress.
7. **Expose the event chain:** add `tracefield case-verify <case>` that runs `EventRepo.verify_chain` *and* re-hashes evidence, and include the result in `report.md` as a top-line "store integrity" row. A tamper-evidence chain nobody can invoke is theatre.
8. **Staged plan:**
   - **S0 (correctness now):** fix the two reproduced tracebacks (A5), add `Relation.evidence_ids`, add `relation add`/`events verify` CLI, delete unused imports, make `ruff`/`mypy` gate CI.
   - **S1 (coherence):** core/storage split + Protocol; wire `Observation`/`Assertion` creation into `evidence attach` and `claim add`; add catalogue data + `tools` CLI; kill the `Path(__file__)` lookup.
   - **S2 (capability):** plugin entry points, `origin cluster run`, `contradict scan`, report sections for observations/assertions, retention/GDPR erasure workflow.
   - **S3 (scale):** streaming origins clustering, FTS index over excerpts, optional encrypted store.

## A1.4 Open questions

- Is `Observation` meant to be per-tool-run (one row per provider) or per-fetch (one row per HTTP exchange)? The schema (`raw_ref`) suggests per-artefact, the docstring ("a direct tool return") suggests per-run.
- Should `AssessmentVector` be persisted (it is computed on demand in `build_case_payload` and never stored), or is on-demand recomputation the intended reproducibility story? Recomputation is fine *if* `rule_version` is recorded on the assessment *and* the rule set is archived.
- Who owns `OriginCluster.member_ids` semantics after an analyst edits membership — is the edited cluster a new entity with `DERIVED_FROM` to the original, or a mutation? Nothing in the schema records an edit history for clusters.
- Is a case title intended to be a user-facing stable key (`CaseRepo.resolve` prefers ID then title, repositories.py:161-163)? If so it needs uniqueness enforcement *and* a rename story; today `get_by_title` does `ORDER BY created_at DESC LIMIT 1` on duplicates, which is a silent ambiguity.

## A1.5 Testable acceptance criteria

- **AC-A1-1.** `import-linter` contract passes: `tracefield.core.domain`, `tracefield.core.analysis`, `tracefield.core.origins`, `tracefield.core.contradictions`, `tracefield.registry`, `tracefield.security` import nothing from `tracefield.storage`, `tracefield.cli`, `tracefield.tui`, `tracefield.reporting`.
- **AC-A1-2.** A relation created with `evidence_ids=["ev_x"]` round-trips through `RelationRepo` and appears in `report --format json`; deleting `ev_x` does not cascade (evidence is referenced by value in the link, and the report emits a dangling-reference caveat).
- **AC-A1-3.** `assess_claim` on a claim whose only supporting relation has the claim as `from_id` does **not** count that relation as self-support (direction contract enforced).
- **AC-A1-4.** Creating a `Relation` whose `from_id`/`to_id` are not resolvable entities in the same `case_id` raises `ValueError` before the row is written.
- **AC-A1-5.** `tracefield events verify <case>` returns exit 0 on an untouched store and non-zero after any single-byte mutation of an `analysis_events` row.
- **AC-A1-6.** Building a wheel (`python -m build`) and installing into a clean venv still lets the TUI Arsenal workspace find the catalogue (no `Path(__file__)`-relative source-tree lookup).
- **AC-A1-7.** `grep -rn "SCHEMA_VERSION" src/` returns exactly one definition.

## A1.6 Challenged assumption

> *"All persistent entities use stable string IDs… These models are pure data: they never import storage, network, or TUI code."* (`core/domain.py:3-5`)

The purity claim holds for `domain.py` itself but is false for the `core` package: `core/provenance.py:15-22` imports `storage.database` and `storage.repositories` and is the module that actually implements the headline "immutable, content-addressed evidence" behaviour. So the property the architecture review would want to guarantee — "domain rules are testable without a database" — is true for `analysis.py`/`origins.py`/`contradictions.py` and false for the one core module users touch most. The assumption should be restated as a *rule with an enforcement mechanism*, not a comment.

## A1.7 Concrete failure mode

**Cross-case provenance leak (reproduced 2026-10-16).** `evidence attach` accepts a `--source` ID belonging to a *different* case:

```
$ tracefield source add https://a.example/ --case c1 --json   -> src_f6553f2c95c646cb
$ tracefield evidence attach f1.txt --case c2 --source src_f6553f2c95c646cb --json
{"id": "ev_…", "case_id": "case_dfb36b4753d249cb",
 "source_id": "src_f6553f2c95c646cb", …}
```

There is a foreign key on `evidence.source_id` (database.py:54) but it only checks that the source *row exists*, not that `sources.case_id == evidence.case_id`. Then `case-delete --yes` on case c1 cascades `DELETE` on `sources` (database.py:38), which cascades to `evidence` (database.py:54) and removes the evidence row **from case c2** while leaving the orphaned `0o400` bytes on disk under case c2's directory. Result: case c2's binary evidence survives with no database record, and case c2's integrity manifest silently reports fewer files than the directory contains.

---

# A2. Terminal UX / TUI Engineer

## A2.1 Findings

1. **The keymap is documented in a docstring that the code does not honour.** `tui/app.py:4-13` promises `Tab` next panel, `Enter` inspect selected, `q` "confirms if a view is dirty-safe to leave", `Ctrl+C` "cancel current operation first". Actual bindings (tui/app.py:91-103): `q`, `?`, `g`, `1`-`6`, `/`, `escape`. `Tab`, `Enter`, and a `Ctrl+C` cancel-then-exit sequence are unbound. `q` is `action_quit` with no dirty check. The docstring is a promise to users that is false on day one.

2. **`/` does not search.** `action_focus_search` (tui/app.py:266-270) writes "search is available in the CLI: tracefield tools search" into the status bar. That referenced command does not exist (see A3). `DataTable` and `Input` are imported (tui/app.py:21) and unused — Ruff confirms two `F401`s. The CSS block styles `DataTable` (tui/app.py:86-88) for a widget that is never instantiated.

3. **`g` (go-to) is a no-op** that prints a reminder (tui/app.py:245-249); there is no picker, no palette. Textual ships a command palette; it is not enabled.

4. **`Esc` is documented as "cancel / back" but jumps to workspace 1**, discarding the user's position (`action_back` → `_set_ws(0)`, tui/app.py:263-264). Pressing `?` then `Esc` from the Claims workspace loses the Claims context.

5. **Workspace views hardcode `self.cases[0]`.** Evidence, Claims, and Runs render only the *first* case in the list (tui/app.py:167, 182, 220) with no case selector and no indication that the view is scoped. `Mission` (tui/app.py:151-160) iterates all cases but calls `SourceRepo`/`ClaimRepo`/`EvidenceRepo` three times per case, synchronously, inside the render path.

6. **The subtitle lies.** `tui/app.py:132-136` renders "(synthetic/demo data only in this view)" while the view is reading the live SQLite database.

7. **Accessibility: colour is the only channel for the active-workspace indicator, and it is hard-coded.** `#sidebar .ws-item.-active { color: #c4b5fd; text-style: bold; }` (tui/app.py:60-62). Bold is present (good — that part survives `NO_COLOR` semantics per no-color.org FAQ), but the CSS is a fixed hex palette with no theme hook and no dark/light awareness. `Screen { background: #101014 }` is forced regardless of the user's terminal.

8. **CLI non-TTY behaviour is decent but not complete.** With stdout piped, Rich drops ANSI but still emits Unicode box-drawing (`M-bM-^TM-^O` etc. observed in `tracefield case list | cat -v`). On an ASCII-only terminal (`LANG=C`, `TERM=vt100`) that is mojibake. `NO_COLOR=1` is respected (verified: no ESC sequences when piped) — consistent with Rich ≥11.2.0 per no-color.org's library table, and the project pins `rich>=13.9,<16`.

9. **Error output is correctly directed to stderr and sanitized** — `fail()` uses `err_console = Console(stderr=True)` and wraps the message in `sanitize_for_terminal` (cli/main.py:86-88). This is better than most CLIs.

10. **`--json` is honoured on most commands but not on `report`/`case-export`/`doctor`/`init`/`tui`.** `doctor` builds a `checks` payload and then calls `emit(..., False, render)` with `as_json` hard-coded `False` (cli/main.py:200) — the flag is not even a parameter. `report --format json` is the machine path, fine, but `doctor` has no machine path at all, which makes it un-automatable for the deployment/health use case it exists for.

11. **Exit-code contract is good and mostly honoured:** 0/1/2/3/4/5 documented in `README.md:54-56` and defined at cli/main.py:46-51. Two observed exceptions: Typer's own "No such command" usage error exits **2**, colliding with `EXIT_NOT_FOUND`; and raw unhandled exceptions exit **1** after printing a full traceback (`pretty_exceptions_enable=False`, cli/main.py:58 — a deliberate choice that currently makes bugs look like crashes, which they are).

## A2.2 Risks

- **R-A2-1 (High).** A keyboard-first product whose documented keymap is aspirational will lose its target user in the first session. Every unbound key silently falls through to "do nothing", which reads as "the app is broken".
- **R-A2-2 (Medium).** `self.cases[0]` scoping means an analyst with three open cases will read case-2 evidence while believing they are looking at case 1. For an evidence product this is the worst class of UI bug: a *misleading* view, not a missing one.
- **R-A2-3 (Medium).** Synchronous repo queries inside `_render_ws` on every workspace switch (3 queries × N cases) will hitch on a case directory with thousands of sources; there is no worker, no loading state, no `run_worker`.
- **R-A2-4 (Low-Medium).** The TUI opens `Database(self.settings.db_path)` in `on_mount` (tui/app.py:115) and never closes it. WAL files linger; a second concurrent CLI write during a long TUI session depends on SQLite's default busy handling (no `busy_timeout` set — see A5).
- **R-A2-5 (Low).** Fixed-width sidebar `width: 24` (tui/app.py:51) leaves 56 columns at 80×24 and 16 columns at 40×12. Verified that the app *mounts* and keypresses work at 40×12 via `app.run_test(size=(40,12))`, but nothing adapts the layout.

## A2.3 Recommendations

1. **Make the docstring a contract or delete it.** Ship `Tab`/`Enter`/`ctrl+c` behaviours or remove them from the header comment and the in-app help (tui/app.py:251-261) in the same PR.
2. **Add a case selector as the first-class object.** `c` opens a `Select`/`OptionList` of cases; the selected case ID is app state; every workspace renders it. Never index `self.cases[0]` implicitly — if the list is empty, render an explicit empty state.
3. **Implement `/` as an in-app filter over the current list** using the already-imported `Input`, or remove the binding. If it stays CLI-only, the status message must not reference a command that does not exist.
4. **Move all rendering off the message-pump thread:** wrap repo calls in `@work(exclusive=True, thread=True)` and render a `LoadingIndicator` meanwhile.
5. **Adopt a theme indirection:** define CSS variables (`$accent`, `$bg-panel`) and provide a default dark theme plus a `--theme light` flag; never hard-code hex in selectors. Verify `NO_COLOR` behaviour explicitly with a pilot test rather than assuming.
6. **Add `--json` to `doctor`** (the payload structure already exists) and to `init`.
7. **Separate "unknown command" from "not found":** install a Typer/Click callback so unknown subcommands exit `EXIT_USAGE` (3), preserving 2 for genuine entity-not-found.
8. **Catch-all exception handler at the CLI boundary** that emits `error: <sanitized message>` on stderr and exit 1, with the traceback available behind `--debug`. Today `pretty_exceptions_enable=False` gives users the worst of both worlds.
9. **Wire the command palette** (`CommandPalette` is built into Textual ≥0.x and the project pins `textual>=8.2,<9`) so `g` becomes real and the keymap has one discoverable entry point.

## A2.4 Open questions

- Does the project intend the TUI to be a *viewer* (read-only, CLI is the writer) or a *workbench*? The docstring says "every feature here also has a CLI path", which implies parity, but the code is a viewer. Pick one and write it into `README.md`.
- Is there an intended resolution for `Esc` semantics in a three-level model (help → workspace → list item)? Today there are only two levels.
- Should `q` in a dirty view prompt, and if so, what is the Textual idiom the project wants (`ExitModal`)?
- What is the intended behaviour when the DB is corrupt or the schema version is newer than the binary? `Database.migrate()` will `KeyError` on an unknown target (database.py:236) — is a friendly "upgrade required" message in scope?

## A2.5 Testable acceptance criteria

- **AC-A2-1.** A `pytest-asyncio` pilot test presses every binding listed in the in-app help and asserts a state change for each. The test suite fails if the help text and `BINDINGS` drift apart (generate one from the other).
- **AC-A2-2.** `async with app.run_test(size=(40, 12))` mounts, switches all six workspaces, opens help, and returns; the sidebar selection is still recoverable after `escape` from help (Esc restores prior workspace).
- **AC-A2-3.** With two cases each having one distinct source, selecting case 2 and pressing `2` renders case 2's source and *not* case 1's. Asserted by string equality on the rendered `#content`.
- **AC-A2-4.** `tracefield doctor --json` emits a parseable JSON object on stdout with keys `checks`, `name`, `status`, `detail`; human output is byte-identical to today's table when `--json` is absent.
- **AC-A2-5.** `tracefield badcmd` exits 3; `tracefield case show nope` exits 2.
- **AC-A2-6.** `tracefield case list | cat -v` under `LANG=C` produces no bytes ≥ 0x80 when `RICH_ASCII=1` or an equivalent `--ascii` flag is set.
- **AC-A2-7.** No unhandled exception escapes the CLI: a test monkeypatches `CaseRepo.list` to raise `RuntimeError("boom")` and asserts stderr contains `error: boom`, no `Traceback`, exit code 1.

## A2.6 Challenged assumption

> *"Keyboard-first, JSON-capable, deterministic exit codes, no network by default. Every advertised command has a real implementation."* (`cli/main.py:2-4`)

Verified false on both halves. The TUI advertises `tracefield tools search` and `tracefield username check` (tui/app.py:256, 213); neither exists. `README.md:72` advertises `tracefield tools status (planned)` — labelled planned, which is honest, but the TUI strings are not. And "every advertised command has a real implementation" is contradicted by the keymap itself (Tab/Enter/g). The assumption should be replaced with a CI check that greps every string literal matching `tracefield [a-z-]+` in `src/` and asserts it is a registered Typer command.

## A2.7 Concrete failure mode

**Analyst reads the wrong case's evidence.** Case A ("Acme leak") and Case B ("Vendor review") both exist. `TracefieldApp.cases` is ordered by `created_at DESC` (repositories.py:158), so case B — the one created later — is `cases[0]`. The analyst presses `2` for Evidence, sees a list of `SRC`/`EV` rows, and starts annotating what they believe is case A's evidence. Nothing in the UI names the case being rendered in the Evidence, Claims, or Runs workspaces (`tui/app.py:164-186, 216-231` produce only a heading like "[Evidence and source list]"). The analyst's notes reference evidence IDs that are real but belong to the other investigation. This is not a crash; it is a silent correctness failure in a tool whose value proposition is "every conclusion traces back to its source".

---

# A3. Connector & Registry Engineer

## A3.1 Findings

1. **The registry is genuinely inert, and that is the right design.** `registry/catalog.py:3-4` states "A registry entry is DATA, never executable code. Nothing in this module loads, imports, or executes catalogue content." The implementation matches: `json.loads` → `CatalogEntry.model_validate` (catalog.py:132-133), no `eval`, no `exec`, no `importlib`, no `pickle`, no `subprocess` with catalogue-supplied argv. `Catalog.validate()` (catalog.py:221-251) adds lint rules including "license marked verified but is UNKNOWN" and "integration_state=integrated but no adapter manifest reference" — the last of which is exactly the guard that keeps an inert record from being mistaken for a working connector.

2. **Metadata schema is unusually complete for an alpha.** `CatalogEntry` (catalog.py:54-92) carries `license_id`/`license_source`/`license_review_state`, `pricing_class`, `key_required`/`key_env_vars` (names only, never values — catalog.py:75), `auth_method`, `rate_limits`, `terms_url`, `network_required`, `data_exposure_warning`, `passive_active`, `maintenance_status`, `verification_state`, `integration_state`, `first_seen`/`last_checked`/`health_checked_at`/`health_result`, `duplicate_group`, `source_list`, `attribution`. The `IntegrationState` ladder (`indexed → verified → integrated → healthy/stale/unavailable/unverified`, catalog.py:37-44) with `counts()` reporting "Truthful tiered counts. Indexed ≠ integrated ≠ healthy" (catalog.py:203) is the correct anti-inflation mechanism.

3. **There is no adapter contract.** Three disjoint connector shapes exist and share nothing:
   - local binary: `run_backend(argv, timeout_s, max_output)` (fieldtools/inspect.py:136-160) — argv allowlist, no shell, `FileNotFoundError` → UNAVAILABLE, scrubbed `env={"PATH":…, "LC_ALL":"C"}`.
   - HTTP profile check: `ProviderRule` frozen dataclass + `check_username` (fieldtools/username.py:26-83, 188-276) — soft-404 markers, `presence_on_200` flag, per-rule `notes`, 1 s `MIN_INTERVAL_S`, 10 s timeout, `trust_env=False`.
   - HTTP page fetch: `fetch_source` (fieldtools/fetch.py:28-110) — SSRF guard, redirect re-validation, byte cap, timeout, size-limited title scrape.

   All three encode "how to talk to a thing", "what failure looks like", and "what we must never claim" — but as three unrelated conventions.

4. **Capability discovery does not exist.** `Catalog.search()` (catalog.py:154-190) filters on stored metadata (type, category, license, key_required, integration_state, network_required, substring over name/description/aliases/categories/capabilities). There is no `capabilities` vocabulary, no synonym map, no ranked relevance — plain substring. Fine for a few hundred records; the mechanism is not the problem, the absence of a shipped dataset is.

5. **The catalogue data does not exist.** `data/` is empty. `tui/app.py:192-196` looks for `data/catalog/tools.jsonl` relative to the *source tree* and renders "catalogue data not loaded" otherwise. `README.md:89-90` references `data/catalog/source-manifest.json`, also absent.

6. **Credential requirements are declared, not enforced — correctly.** `key_env_vars` stores names only (catalog.py:75) and `Catalog.validate()` rejects entries containing `=` or longer than 100 chars (catalog.py:248-250). No code path reads those env vars, because no adapter exists. This is the right shape for an inert catalogue.

7. **Rate limits and timeouts live in three uncoordinated places.** `Settings.max_fetch_timeout_s=15.0`, `max_fetch_bytes=10 MiB`, `max_redirects=5` (settings.py:45-47); `REQUEST_TIMEOUT_S=10.0`, `MIN_INTERVAL_S=1.0`, `max_body=500_000` (username.py:21-22, 192); `run_backend(timeout_s=30|60, max_output=2_000_000|5_000_000)` (inspect.py:137, 168, 190; ocr.py:24). The catalogue's `rate_limits` free-text field is never consulted by any of them.

8. **Health-check lifecycle is a schema without a job.** `health_checked_at`/`health_result` (catalog.py:87-88, database.py:175-176) and `IntegrationState.STALE` ("health check overdue", catalog.py:42) are defined; nothing ever sets them. `doctor` (cli/main.py:125-202) checks *local* binaries only and explicitly never touches the network — correct for `doctor`, but it means there is no health-check entry point at all.

9. **Network is doubly opt-in and fails closed.** `Settings.allow_network=False` (settings.py:43); `source add --fetch` refuses with `EXIT_NETWORK_BLOCKED=4` unless `TRACEFIELD_ALLOW_NETWORK=1` (cli/main.py:360-365, reproduced: exit 4). `validate_fetch_url` (security/urls.py:61-88) rejects non-http(s), embedded credentials, blocked metadata hostnames, `.local`/`.internal`, and any resolved address that is private/loopback/link-local/multicast/reserved/unspecified. Redirect targets are re-validated by an httpx request hook (fetch.py:23-25, 46).

10. **`check_username` is the best-behaved connector in the repo** and should be the template for the contract: curated allowlist, no bulk mode, `validate_username` regex gate (username.py:99-105), 404 → `NOT_FOUND_VERIFIED`, soft-404 markers → `NOT_FOUND_VERIFIED`, markers present → `CONFIRMED_PUBLIC_PROFILE`, no markers + `presence_on_200` → `LIKELY_MATCH` (never confirmed), 429 → `RATE_LIMITED` with "not retried", 403 → `BLOCKED` with "not circumvented", and three standing caveats about identity attribution (username.py:266-274). **But it has no CLI command** — `check_username` has zero callers.

## A3.2 Risks

- **R-A3-1 (High).** Three ad-hoc connector shapes will accrete into N shapes. Each new one will re-invent failure taxonomy, timeout defaults, and caveat text, and the honesty guarantees that make `check_username` good will not propagate.
- **R-A3-2 (High).** SSRF guard has a DNS-rebinding TOCTOU window: `validate_fetch_url` resolves the host (urls.py:43-58) and then httpx resolves *again* at connect time. A name that returns a public A record to the validator and `169.254.169.254` to the connector defeats the check. The code's own docstring says "DNS is resolved and every redirect target must be re-validated" — re-validation is present, rebinding protection is not.
- **R-A3-3 (Medium).** `_is_blocked_ip` (urls.py:32-40) enumerates `is_private/is_loopback/is_link_local/is_multicast/is_reserved/is_unspecified` instead of testing `not ip.is_global`. Measured on this machine (Python 3.13.5): `100.64.0.1` (CGNAT) → all six `False`, so **allowed**; `fec0::1` (deprecated site-local) → `is_global=True`, so allowed even under the recommended check. CGNAT is not a cloud-metadata path, but the enumerated-allowlist approach is structurally wrong and will keep missing ranges.
- **R-A3-4 (Medium).** Catalogue staleness has no enforcement. `last_checked` and `health_result` will rot the moment a dataset ships, and `IntegrationState.STALE` has no transition function.
- **R-A3-5 (Medium).** `Catalog.load` overwrites on duplicate `id` silently (`self.entries[entry.id] = entry`, catalog.py:137) while `validate()` separately reports "duplicate id" — but `validate()` iterates a dict that already collapsed the duplicate, so the duplicate is *undetectable* post-load. The lint reports a problem it structurally cannot see.

## A3.3 Recommendations

1. **Define `ToolAdapter` as a Protocol and make the three existing shapes implement it.** Minimum surface:
   ```
   name: str
   version: str
   capabilities: frozenset[str]
   credential_requirements: list[EnvVarRequirement]   # names + presence check
   network_policy: Literal["none","opt-in","always"]
   health() -> HealthResult
   run(request, *, budget: Budget, cancel: CancellationToken) -> ToolResult
   ```
   with `ToolResult` carrying `status ∈ {ok, UNAVAILABLE, RATE_LIMITED, BLOCKED, TIMEOUT, PROVIDER_ERROR, POLICY_REFUSED}`, `observed_at`, `evidence_ref`, `caveats: list[str]`, and a hard rule that **no adapter may ever write to the case store directly** — it returns an `Observation` payload and the caller (CLI/TUI) decides whether to persist.
2. **Pin the connection to the validated IP.** Resolve once, check the policy, then connect to the literal address with the original `Host` header (httpx supports this via a custom transport). This closes R-A3-2 without giving up the redirect hook.
3. **Switch `_is_blocked_ip` to `not ip.is_global`** with an explicit allowlist for the handful of `is_global=False`-but-harmless ranges if any are needed, and add unit tests for `100.64.0.1`, `192.0.2.1`, `fec0::1`, `::ffff:10.0.0.1`.
4. **Single rate-limit/time-budget authority:** move all timeouts and byte caps into `Settings` (or a `Budget` value object built from it), and have adapters accept a `Budget` rather than defining their own constants.
5. **Ship the catalogue as a versioned artefact** (`data/catalog/tools.jsonl` + `source-manifest.json`), load it via `importlib.resources` (the unused import at database.py:12 is a hint someone already intended this), and add `tracefield tools status|search|show` with the *tiered* counts that `Catalog.counts()` already returns.
6. **Fix `Catalog.load` duplicate handling:** keep duplicates in a `self.duplicates: list[tuple[str, int]]` so `validate()` can report line numbers.
7. **Make health checks an explicit, network-opt-in command** (`tracefield tools health [--all]`), never a background job, never on startup, and record `health_checked_at`/`health_result` with the same `analysis_events` chain used elsewhere.
8. **Add `--dry-run` to every network-touching command** that prints the exact URLs that would be contacted, the resolved IPs, and the policy decision, without opening a socket. This is the single best trust-building feature for the target user.

## A3.4 Open questions

- Should `passive_active` be a closed enum (`passive|active|mixed|unknown`) rather than free text? The current string will fragment the moment a second curator touches the data.
- Is `duplicate_group` meant to be a grouping key for *the same tool under different names*, or for *different tools that do the same job*? The `validate()` rule (catalog.py:232-237) only enforces the former.
- Who is allowed to flip `verification_state`/`license_review_state`, and is that flip itself supposed to be an `analysis_events` row? Nothing records catalogue edits today.
- Is the curated provider list in `username.py` meant to eventually *come from* the catalogue (`capabilities` includes `username_check`), or stay a hard-coded safety allowlist? These pull in opposite directions — the former is extensible, the latter is auditable.

## A3.5 Testable acceptance criteria

- **AC-A3-1.** A fuzz/property test feeds 200 malformed JSONL lines (bad UTF-8, nested objects, 10 MB strings, `__proto__`-style keys, deeply nested arrays) to `Catalog.load`; it never raises, and `import_errors` length equals the number of rejected lines.
- **AC-A3-2.** A unit test asserts that no module under `tracefield.registry` imports `subprocess`, `importlib`, `eval`, `exec`, `pickle`, or `marshal` (`grep`-based gate in CI, or `import-linter` forbid rules).
- **AC-A3-3.** `validate_fetch_url` rejects: `http://127.0.0.1/`, `http://10.0.0.1/`, `http://100.64.0.1/`, `http://[::ffff:127.0.0.1]/`, `http://169.254.169.254/`, `http://metadata.google.internal/`, `https://user:pass@host/`, `ftp://host/`, and a hostname whose first resolution is public but second is `127.0.0.1` (rebinding test with a stub resolver).
- **AC-A3-4.** `check_username` with an injected `httpx.MockTransport` returning (a) 404, (b) 200 with a not-found marker, (c) 200 with a found marker, (d) 200 with neither, (e) 429, (f) 403, produces exactly the six documented `UsernameResultState` values and never `CONFIRMED_PUBLIC_PROFILE` for (d).
- **AC-A3-5.** `Catalog.counts()` over a fixture with 10 `indexed`, 3 `verified`, 1 `integrated`, 1 `healthy` reports all four buckets separately; a UI string asserting "N tools" must reference `by_integration_state`, never `total_records` alone.
- **AC-A3-6.** Every string matching `tracefield [a-z][a-z-]+` anywhere in `src/` resolves to a registered Typer command (a test that walks the Typer app object).
- **AC-A3-7.** An adapter given a `Budget(timeout=0.001)` against a stub that sleeps 1 s returns `TIMEOUT` within 50 ms wall-clock and performs at most one request.

## A3.6 Challenged assumption

> *"Catalogue records are inert data, never code. Indexed ≠ installed ≠ integrated ≠ healthy."* (`README.md:73-74`, enforced by `Catalog.validate`, catalog.py:243-247)

I support the assumption and think it is the best idea in the project. I challenge the *sufficiency* of the enforcement: the invariant is held by a `validate()` function that nothing calls. There is no `tracefield tools lint`, no CI step, no pre-commit hook, and no shipped data to lint. An invariant enforced only by an unused function is a comment. Until `Catalog.validate()` is on a CI path over real data, the claim "inert catalogue" is aspirational in exactly the same way the TUI keymap is.

## A3.7 Concrete failure mode

**A user follows the README and gets exit 2.** `README.md:72` says: *"Run `tracefield tools status` (planned) or inspect `data/catalog/tools.jsonl`."* Reproduced 2026-10-16:

```
$ tracefield tools status
Error: No such command 'tools'.
$ echo $?
2
```

and the file path does not exist (`data/` is empty). The word "planned" is doing honest work, but a user following the five-minute path at `README.md:26-34` who then continues into the "Honest catalogue counts" section hits a dead end, and — worse — the exit code 2 is the same code the tool uses for `case not found`, so a script that retries on `EXIT_NOT_FOUND` will retry a usage error forever. The TUI compounds it: pressing `/` prints "search is available in the CLI: tracefield tools search", which is the same non-existent command, unlabelled as planned (tui/app.py:266-270).

---

# A4. Evidence / Provenance / Quantitative Analysis Engineer

## A4.1 Findings

1. **Content-addressed immutable evidence is implemented correctly.** `CaseWorkspace.attach_file`/`attach_bytes` (provenance.py:67-131) hash with streamed SHA-256, write to `<case>/evidence/<sha[:2]>/<sha>`, `chmod 0o400`, dedupe on existence, then record an `EvidenceItem` and append a hash-chained `AnalysisEvent`. `verify_evidence` (provenance.py:133-137) re-hashes and compares. Verified live: `evidence verify --case demo` → `OK ev_be08b4f3ee354ed3 … 1 files checked; all intact`, exit 0. The docstring's framing — *"SHA-256 proves byte-level integrity of the stored object, not truthfulness, authorship, or authenticity"* (provenance.py:4-5) and the identical caveat baked into `IntegrityManifest.to_json` (provenance.py:177-181) — is exactly right and should be preserved verbatim through any refactor.

2. **The claim→evidence link does not exist in the shipped schema.** `Relation` has no `evidence_ids` (domain.py:195-204). `Assertion.evidence_ids` exists (domain.py:168) but no code ever creates an `Assertion`. `Observation.evidence_id` exists (domain.py:149) but no code ever creates an `Observation`. So the only machine-computable path from a claim to a byte is: claim → (relation, which cannot be created) → evidence. Verified: a freshly created case with one source, one evidence item and one claim reports `"outcome": "UNASSESSED"` with `"supporting_count": 0, "contradicting_count": 0`.

3. **`provenance_completeness` measures the wrong thing.** `analysis.py:67-75` sets it to `complete` when every confirmed supporting relation has a non-empty `rationale` string. `rationale` is free text; it is not an evidence link. A relation with `rationale="I saw this on a forum"` and no evidence gets "complete". The field is named for a property it does not measure.

4. **`evidence_directness` and `temporal_fit` are hard-coded `"unknown"`** (analysis.py:77, 86). Honest, but they are reported in the assessment vector and in the Markdown report, so a reader sees eight dimensions of which four are permanently unpopulated. That reads as a fuller assessment than it is.

5. **`RelationType.DERIVED_FROM` mirrors W3C PROV `wasDerivedFrom`, and the mapping is not written down.** The domain vocabulary lines up well with PROV-DM (W3C Recommendation, https://www.w3.org/TR/prov-dm/, accessed 2026-10-16): `Source` ≈ Entity + Attribution; `Observation` ≈ Activity + Usage; `EvidenceItem` ≈ generated Entity; `Assertion`/`Claim` ≈ Entity with Attribution to an Agent; `AnalysisEvent` ≈ Activity with `wasGeneratedBy`; `Relation.DERIVED_FROM` ≈ `wasDerivedFrom`; `OriginCluster` ≈ an `alternateOf`/`specializationOf` hypothesis. Nothing in the repo states this mapping, which means the vocabulary can drift from the standard without anyone noticing.

6. **The event hash chain is honest about its threat model.** `EventRepo.verify_chain` docstring (repositories.py:523-525): *"Tamper-evident within this store's threat model only — a sufficiently privileged operator who rewrites every row can defeat it. Not a blockchain."* `IntegrityManifest` caveat (provenance.py:177-181) is equally precise. Two of the best-written sentences in the codebase. **But `verify_chain` has no caller.**

7. **Origin clustering is well-specified and completely unwired.** `find_origin_edges` (origins.py:62-92) implements three explainable signals (exact digest, URL cross-citation, Jaccard on word 5-grams ≥ 0.8), each emitted as an `Edge(a, b, signal, score)` with a human-readable signal string. `cluster_from_edges` (origins.py:95-141) does union-find, skips singletons, stores per-edge indicators as `"a~b: signal (score)"`, and defaults `confidence_label="hypothesis"`, `review_state=UNREVIEWED`. This is exactly the right design for "don't let syndicated copies count as independent sources". **Zero callers.** Nothing populates `OriginCluster`.

8. **Contradiction detection is deterministic, conservative, and unwired.** `find_contradictions` (contradictions.py:50-86) flags date sets that are disjoint *and* non-empty on both sides, and 64-hex digests that differ. `ContradictionCandidate.severity` is hard-coded `"candidate"` with the comment "always 'candidate' — requires review". `_NUM_RE` is defined (contradictions.py:20) and never used — quantity contradiction detection is advertised in the aspect comment (`date | hash | quantity`, contradictions.py:27) but not implemented. **Zero callers.**

9. **Report caveats cannot be stripped by accident, which is good, but they are also not per-finding.** `build_case_payload` attaches `global_caveats` (build.py:66-75) and `render_markdown` puts them in a blockquote section at the top (build.py:97-101) *and* per-assessment caveats inline (build.py:152-153). Good. What is missing: every claim's Markdown section does not carry a "no evidence is linked to this claim" marker when `supporting_count == 0`, so an exported report with 30 claims and 0 relations looks structurally like a report where the analysis simply hasn't rendered.

10. **Export redaction breaks the integrity manifest (reproduced).** `export_case` order is: `copytree` → `IntegrityManifest.build` → reports → redaction loop that rewrites exported evidence files (export.py:26-49). Two consequences, both verified: (a) any evidence file matching a secret pattern raises an uncaught `PermissionError` because the copy is `0o400` and `write_text` is outside the `try/except` (export.py:41-47); (b) even if the write succeeded, the manifest digests were computed from the *original* bytes, so `verify_manifest` would report a mismatch on every redacted file.

## A4.2 Risks

- **R-A4-1 (Critical).** The product's core promise — "traces every conclusion back to its sources" (README.md:12-13) — is not satisfiable with the shipped schema and command surface. Everything downstream (`assess_claim`, origin clusters, contradiction candidates, the report) is built on top of a link type that cannot be created.
- **R-A4-2 (High).** A case-export that contains a secret-shaped byte string crashes with a traceback *after* writing `manifest.json` and before writing `report.md`/`report.json`/`EXPORT_README.txt`. The user gets a directory that looks like an export, contains a manifest that verifies nothing useful, and has no report. In a real investigation this is a data-loss-adjacent event.
- **R-A4-3 (High).** `provenance_completeness="complete"` on rationale-only relations is a mislabel that will be read as "evidence-backed" by downstream consumers and by any report reader who skims.
- **R-A4-4 (Medium).** `origin_clusters=len(clusters)` is passed to `assess_claim` as a whole-case count (build.py:42), and the resulting caveat says "if any contain these origins". Once clustering is wired, this will fire on every claim in a case that has any cluster at all — noise, not signal.
- **R-A4-5 (Medium).** `evidence_ids` on `Assertion` is `json.dumps` in a TEXT column with no FK and no dangling-reference check (repositories.py:398). Once assertions exist, a deleted evidence row leaves a silent hole in the assertion's provenance.
- **R-A4-6 (Medium).** `attach_file` copies the whole source file into memory (`src.read_bytes()`, provenance.py:86) before writing. A multi-GB exhibit will OOM rather than fail cleanly.

## A4.3 Recommendations

1. **Add the evidence link to `Relation` first** (`evidence_ids: list[str]`), then build `relation add` CLI, then wire `assess_claim` to use it for `provenance_completeness` and `evidence_directness`. Do not ship more assessment dimensions until the input exists.
2. **Split export into two phases with an explicit contract:** (a) copy evidence to a temp dir, (b) redact *there*, (c) re-hash the redacted bytes, (d) write a manifest whose digests are of the *exported* bytes, and record `"redaction_applied": true` plus the redaction rule IDs in the manifest. Redacted and unredacted exports are then both verifiable, and the difference is documented rather than accidental.
3. **Wrap the whole redaction loop in `try/except OSError`, chmod the export copies to `0o600` before rewriting, and never mutate the source case store.** Also move `report.md`/`report.json`/`EXPORT_README.txt` writes *before* the redaction pass, or write the manifest last, so a crash cannot leave a manifest without a report.
4. **Replace `rationale`-based provenance scoring** with an explicit `evidence_ids`-based one, and rename the current heuristic to `rationale_coverage` so the name matches the measurement.
5. **Write down the PROV-DM mapping** in `docs/provenance-model.md` as a table (`TRACEFIELD entity → PROV-DM type/relation → note`), and state explicitly which PROV-DM relations we deliberately do *not* implement (`wasInvalidatedBy`, `wasStartedBy`/`wasEndedBy`, bundles). This costs an afternoon and prevents vocabulary drift for a decade.
6. **Implement `quantity` contradictions or delete the aspect string.** A documented-but-unimplemented aspect in a dataclass comment is the same failure as the keymap docstring.
7. **Stream large attachments:** hash in chunks (already done), then `shutil.copyfileobj` instead of `read_bytes`.
8. **Make the report emit a per-claim "evidence linkage" row** that is one of `none | unreviewed | analyst-confirmed`, computed from `evidence_ids`, so a reader can see at a glance which claims have a chain.
9. **Persist `AssessmentVector`** as a table keyed by `(claim_id, rule_version, computed_at)`, and have the report state which persisted assessment it printed, so re-running with a new `RULE_VERSION` does not silently rewrite history.

## A4.4 Open questions

- Is `AnalysisEvent` meant to be the *only* audit trail, or should every mutation (including `claim add`, `case-delete`) append one? Today `source.add` and `evidence.attach` append; `claim add`, `case create`, `case-delete`, `report`, `case-export` do not.
- Should `AnalysisEvent.inputs` contain raw locators (it does: `inputs=[locator]`, cli/main.py:389) given that locators can carry query-string tokens? `redact_secrets` is not applied to that path.
- Who is the "agent" in PROV terms for an analyst-confirmed relation — `Relation.attribution` does not exist; `Assertion.attribution` does. Should relations get attribution too?
- Is `retention_status` on `EvidenceItem` (domain.py:141) meant to drive an erasure job? Nothing reads it, and `case-delete` deletes everything regardless.
- Should origin clusters be re-derived when a new source is added, or only on explicit request? Immutability of prior clusters vs. staleness of the set are in tension.

## A4.5 Testable acceptance criteria

- **AC-A4-1.** A golden-fixture case (fixed timestamps, fixed IDs, 3 sources, 2 of which are byte-identical) produces a byte-identical `report --format json`. The fixture is committed; the test fails on any change to `RULE_VERSION` output.
- **AC-A4-2.** `assess_claim` returns `CORROBORATED_WITH_LIMITATIONS` only when ≥2 *distinct* confirmed supporting relations exist **and** at least one has non-empty `evidence_ids`; a relation with a rationale but no evidence contributes to `rationale_coverage` only.
- **AC-A4-3.** `find_origin_edges` on two docs with identical `sha256` emits exactly one edge with `signal="exact_duplicate_digest"`, `score=1.0`; on two docs sharing a URL emits `signal="a_url_cited_by_b"`; a third doc with no overlap emits nothing. Deterministic across runs (sorted output).
- **AC-A4-4.** `cluster_from_edges` never emits a cluster with fewer than 2 members, and every `indicators` entry round-trips through `ClusterRepo` without loss.
- **AC-A4-5.** Export of a case containing `token=supersecretvalue1234567890` in evidence bytes completes with exit 0, writes all five artefacts, `verify_manifest` on the export directory returns `(True, [])`, and the exported evidence file contains `[REDACTED]` and a *different* digest than the source store.
- **AC-A4-6.** `EventRepo.verify_chain` returns `(False, …)` after any single-byte UPDATE of an `analysis_events.digest`; `(True, "ok (N events)")` after a fresh 100-event run.
- **AC-A4-7.** `find_contradictions("X on 2024-01-01", "ev_a", "X on 2024-02-01", "ev_b")` returns one candidate with `aspect="date"` and `severity="candidate"`; `find_contradictions("X on 2024-01-01", "ev_a", "Y", "ev_b")` returns zero.
- **AC-A4-8.** Attaching a 64 MiB file completes with peak RSS < 2× file size (streaming copy).

## A4.6 Challenged assumption

> *"Originals are immutable. Derived artifacts are separate files with their own digests."* (`core/provenance.py:3-4`)

True for the case store, and verified (`chmod 0o400`, content-addressed names, dedupe). **False for exports.** `export_case` writes a copy, then *rewrites* that copy during redaction (export.py:39-47) — a derived artefact being mutated in place, after its digest has been recorded in a manifest. The immutability invariant is therefore not transitive to the one artefact that leaves the machine. Since the export is the thing handed to counsel, a journalist, or a regulator, the invariant must hold there at least as strictly as in the store. I challenge the design decision to reuse the case-store layout (`evidence/evidence/<hash>`) for exports at all: exports should be produced by a separate builder with their own digest computation, not by `copytree` + in-place rewrite.

## A4.7 Concrete failure mode

**A case export containing a credential-shaped string crashes and leaves a half-written bundle (reproduced 2026-10-16).**

```
$ printf 'token=supersecretvalue1234567890\nplain body\n' > ev2.txt
$ tracefield evidence attach ev2.txt --case demo --json   # ok
$ tracefield case-export demo --output ./exp2
Traceback (most recent call last):
  … export_case …
  meta_file.write_text(cleaned, encoding="utf-8")
PermissionError: [Errno 13] Permission denied:
  './exp2/evidence/evidence/c9/c950f5400d310751dc2d4545a2c87c908…'
```

Exit code 1, raw traceback (because `pretty_exceptions_enable=False`). The directory `exp2/` exists and contains `manifest.json` and `EXPORT_README.txt`'s sibling `manifest.json` — but **no** `report.md`, **no** `report.json`, and the evidence file is untouched, i.e. **the credential is present in plaintext in the export**. A user who checks for the report, doesn't find it, and assumes the export failed has just been handed an export directory containing an unredacted secret. Two bugs compose into a privacy incident: the `write_text` outside `try/except OSError` (export.py:41-47), and writing the manifest before the redaction pass (export.py:31-32).

---

# A5. QA / Performance / Portability Engineer

## A5.1 Findings

1. **There are zero tests.** `tests/` is empty; `pytest` reports *"no tests ran in 0.00s"* in 0.00s. `pyproject.toml` has a well-considered pytest config (`testpaths`, `--strict-markers`, markers for `slow`/`network`/`integration`/`security`, `filterwarnings = ["error"]`) and a dev extra with `pytest`, `pytest-cov`, `pytest-mock`, `ruff`, `mypy` — but no `pytest-asyncio`, which Textual's own testing guide (https://textual.textualize.io/guide/testing/, accessed 2026-10-16) states is required to drive `App.run_test()`. Verified absent from `.venv`.

2. **The static gates are red.** `ruff check .` → **31 errors**, 23 auto-fixable, including 14 `F401` unused imports (`time`, `PrivacyLabel`, `ReviewState`, `IntegrityManifest`, `hash_file`, `EventRepo`, `RelationRepo` in cli/main.py alone — which is how you can tell the relation/event-verify features were started and abandoned). `mypy` with the project's own `strict = true` config → **24 errors in 10 files**, including real ones: `cli/main.py:100` `Incompatible return value type (got "Case | None", expected "Case")` (because `fail()` is annotated `-> None` instead of `NoReturn`), `cli/main.py:546` `Item "None" of "Source | None" has no attribute "id"`, `tui/app.py:201` `"int" has no attribute "items"`, `registry/catalog.py:215-217` dict-item mismatches. There is no CI workflow (`.github/workflows/` is empty).

3. **Unhandled exceptions escape as raw tracebacks.** Reproduced twice: `evidence attach <directory>` → `IsADirectoryError`, exit 1; `case-export` with redaction-triggering evidence → `PermissionError`, exit 1. `pretty_exceptions_enable=False` (cli/main.py:58) is the right instinct — the traceback is not user-friendly — but there is no replacement handler.

4. **`dir_okay=True` on `evidence attach`** (cli/main.py:516) invites the directory case and then crashes. Typer's `exists=True, readable=True` are honoured; `file_okay` is not restricted.

5. **Concurrency is unguarded at the SQLite layer.** `sqlite3.connect(..., check_same_thread=False)` with a single shared connection, `PRAGMA journal_mode = WAL`, `PRAGMA foreign_keys = ON` (database.py:209-212) — and **no `PRAGMA busy_timeout`** and no `sqlite3_busy_timeout` call (https://www.sqlite.org/c3ref/busy_timeout.html, accessed 2026-10-16). WAL allows concurrent readers with one writer, but a writer that collides with another writer gets `SQLITE_BUSY` immediately. Ten parallel `claim add` processes succeeded in a smoke test, which is evidence of *not yet stressed*, not of correctness: every repo method commits immediately (e.g. repositories.py:143, 203, 241), so a 100-op batch is 100 separate write transactions.

6. **Cancellation does not exist.** No `signal` handling, no `KeyboardInterrupt` handler, no `CancellationToken` type. `httpx` calls use a `timeout=` but Ctrl-C during a long `inspect` of a large file or a 10 MiB fetch will raise `KeyboardInterrupt` out through Typer and print a traceback. `subprocess.run(timeout=…)` in `run_backend` (inspect.py:148-157) returns `124` on timeout but the parent process cannot be told to stop early.

7. **Performance hot spots, measured by reading (no benchmark numbers are claimed):**
   - `find_origin_edges` is O(n²) pairwise with a full shingle set per doc (origins.py:67-89). Fine for tens of docs; 10k docs is 50M comparisons.
   - `cluster_from_edges` re-scans the full edge list once per cluster (origins.py:126-128) — O(clusters × edges).
   - `_render_ws` in the TUI issues 3 queries per case on every workspace switch (tui/app.py:152-154), synchronously, on the message-pump thread.
   - `attach_file` does `src.read_bytes()` (provenance.py:86) — O(file) memory.
   - `build_case_payload` loads all sources/claims/evidence/relations/assertions/clusters/events into memory and `json.dumps` the lot (build.py:29-43, 190-191). A 50k-evidence case will produce a multi-hundred-MB JSON string.
   - `IntegrityManifest.build` stats every evidence file (provenance.py:192-203); `evidence verify` re-hashes every file. Both are linear and unavoidable, but neither reports progress.

8. **Offline behaviour is genuinely good.** `doctor` never networks (cli/main.py:126). Network is off by default and `source add` without `--fetch` does not resolve DNS (cli/main.py:343). `validate_fetch_url` is only reached on `--fetch`. `fetch.py` and `username.py` both set `trust_env=False`, which correctly ignores ambient `HTTP_PROXY`. Verified: `source add https://example.com/x --case c1` with no network opt-in completed instantly with no DNS lookups attempted.

9. **Linux-first portability is coherent.** `requires-python = ">=3.11"`, classifiers list `POSIX :: Linux` and 3.11/3.12/3.13. `shutil.which` gating for `exiftool`/`ffprobe`/`tesseract` with an honest `UNAVAILABLE` + exit 5 contract (inspect.py:145-146, ocr.py:28-30, cli/main.py:154-167). `run_backend` sets `LC_ALL=C` and a minimal `env` (inspect.py:154) — good for reproducibility of subprocess output. `os.stat` `st_birthtime` is correctly guarded behind `hasattr` (inspect.py:131-133). Case-insensitive-filesystem and `0o400` semantics are not addressed anywhere (macOS/Windows are not in the classifiers, so this is consistent, but it should be stated).

10. **Determinism: mostly good, one gap.** IDs are UUID4-based (`new_id`, domain.py:21-22) and timestamps are wall-clock `utcnow()` (domain.py:17-18), so no output is byte-reproducible across runs without a fixture-injection seam. `compute_event_digest` sorts keys (repositories.py:543-546) and `IntegrityManifest.to_json` uses `sort_keys=True, indent=2` (provenance.py:172-185) — those two are deterministic given the same inputs. `assess_claim` is a pure function of `(claim, relations, origin_clusters)` — fully deterministic, and `RULE_VERSION = "assess-r1"` is recorded on every vector (analysis.py:19, 62). Same for `ALGORITHM_VERSION = "origin-r1"` (origins.py:20) and `RULE_VERSION = "contra-r1"` (contradictions.py:14). This is a strong foundation that is being squandered by the absence of tests.

11. **Secret handling in tests is a live risk.** `filterwarnings = ["error"]` is good. The `network` marker is declared (pyproject.toml) and correctly opt-in. But there is no `respx`/`pytest-httpx` in dev deps; `httpx.MockTransport` is built in and is the right tool.

## A5.2 Risks

- **R-A5-1 (Critical).** Zero tests plus red lint/type gates plus empty CI means every one of the bugs in this review — the two tracebacks, the cross-case source reference, the export/manifest mismatch, the unused-import signal of abandoned features — can ship silently.
- **R-A5-2 (High).** No `busy_timeout` + immediate-commit-per-row + a long-lived TUI process holding a connection means a user running `tracefield tui` and a shell script writing in a loop will eventually hit an unhandled `sqlite3.OperationalError: database is locked`, surfacing as a traceback.
- **R-A5-3 (High).** `attach_file`'s `read_bytes()` means an analyst attaching a 4 GB video gets an OOM kill, not an error, and the `AnalysisEvent` for the attach is never appended — leaving a partially-written state that `verify` will not catch (no row, no file, consistent).
- **R-A5-4 (Medium).** No cancellation path means a Ctrl-C during `case-export` of a large case can leave a partial export directory with a valid-looking `manifest.json` (see A4).
- **R-A5-5 (Medium).** `filterwarnings = ["error"]` is a good default but will make the first third-party deprecation warning (Rich, Typer, Textual, httpx all move fast) a hard test failure. Needs a targeted `filterwarnings` allowlist or a scheduled job that runs with warnings-as-errors separately from the always-on gate.
- **R-A5-6 (Medium).** The O(n²) origin clustering will be the first wall. Without a size guard or a documented limit, the first user with 2k sources will experience a multi-minute hang with no progress output and no way to cancel.

## A5.3 Recommendations

1. **Land a minimal test harness before any new feature.** Priority order: (a) `security/urls.py` unit tests (pure, no I/O), (b) `core/analysis.py` golden vectors, (c) `core/origins.py` fixtures, (d) `core/provenance.py` against a `tmp_path` case root, (e) CLI end-to-end via `typer.testing.CliRunner`, (f) TUI pilot tests. Add `pytest-asyncio` and `pytest-textual-snapshot` to the dev extra.
2. **Add `PRAGMA busy_timeout=5000`** immediately after `journal_mode = WAL` (database.py:212), and wrap repo writes so `sqlite3.OperationalError` maps to a clean `EXIT_ERROR` with a retry hint.
3. **Introduce a `Clock`/`IdFactory` seam.** `utcnow()` and `new_id()` should be injectable (module-level function with a settable default, or a contextvar) so golden-file tests are possible. This is a ~20-line change and it unlocks byte-exact report tests.
4. **Add a CLI boundary exception handler** (see A2 rec #8) and set `file_okay=True, dir_okay=False` on `evidence attach`.
5. **Stream copies:** replace `src.read_bytes()` with a chunked `shutil.copyfileobj` to a temp file in the destination directory, then `os.replace`, then `chmod`.
6. **Make cancellation real:** catch `KeyboardInterrupt` at the CLI boundary → exit 130 (conventional) with a sanitized message; pass a `cancel_event` into `fetch_source`/`check_username` checked between providers.
7. **Profile before optimising, but write the budget now:** propose `evidence verify` ≤ 200 MB/s throughput on local disk, `report` on a 1k-claim case ≤ 2 s, `tui` workspace switch ≤ 100 ms at 1k sources, `origin cluster run` ≤ 5 s at 500 docs (and a documented hard cap above that). These are *budgets to be validated*, not measured results — no numbers are claimed here.
8. **Add CI:** `.github/workflows/ci.yml` running `ruff check`, `ruff format --check`, `mypy`, `pytest -m "not network"`, plus a `pytest -m network` scheduled job that is allowed to fail. Today `.github/workflows/` is empty while `pyproject.toml` already declares the markers.
9. **Gate the "inert catalogue" invariant in CI** (A3's import-linter rule) — it is cheap and it protects the project's most defensible design decision.
10. **Portability note in README:** state Linux-only, state `0o400` assumption, state that case-insensitive filesystems are untested, and state that `st_birthtime` is used when present.

## A5.4 Open questions

- Is `filterwarnings = ["error"]` intended to apply to third-party deprecations, or only to the project's own warnings? The answer determines whether CI needs an allowlist.
- Should `slow`-marked tests run in CI at all, or only on a schedule? The marker exists and nothing uses it.
- What is the intended max case size? No documented limit anywhere; it determines whether O(n²) clustering is a P0 or P2 risk.
- Is there an intended reproducibility story (fixed seed / injected clock) for releases, or is determinism only required within a single rule version?
- Should `case-delete` be recoverable (soft delete + retention window)? `EvidenceItem.retention_status` exists and is unread.

## A5.5 Testable acceptance criteria

- **AC-A5-1.** `pytest` collects ≥ 150 tests; `pytest -m "not network"` passes offline with network namespace unavailable (run in a container with `--network none`).
- **AC-A5-2.** `ruff check .` and `mypy` both exit 0 on `main`, enforced in CI on every PR.
- **AC-A5-3.** A `CliRunner` test drives the full five-minute path from README (`doctor → case create → source add → evidence attach → claim add → report → case-export`) and asserts exit 0 at each step plus a successful `verify_manifest` on the export.
- **AC-A5-4.** `validate_fetch_url` unit suite (≥ 25 cases) covers every blocked class and every allowed class; runs with no sockets opened (monkeypatch `socket.getaddrinfo`).
- **AC-A5-5.** Two `Database` instances on the same file, each opening a transaction and writing, both complete within `busy_timeout` without raising.
- **AC-A5-6.** `evidence attach` of a 512 MiB temp file completes with peak RSS < 1.2× the chunk size (1 MiB), not 512 MiB.
- **AC-A5-7.** A TUI pilot test at `size=(40, 12)` and `size=(200, 60)` mounts, switches all workspaces, and exits 0; a snapshot test (`pytest-textual-snapshot`) guards the Mission workspace.
- **AC-A5-8.** `find_origin_edges` over a 500-doc fixture completes in < 5 s on the CI runner; a 2,001st doc triggers a documented size-guard error rather than hanging.
- **AC-A5-9.** A golden `report --format json` for a fixed fixture is byte-identical across two runs on two different machines, given injected clock and IDs.
- **AC-A5-10.** `SIGINT` during a 10 s `fetch_source` results in exit 130 within 1 s, no traceback on stdout, and no partial `Source` row with `access_method=fetched`.

## A5.6 Challenged assumption

> *"Development Status :: 3 - Alpha"* and *"Typing :: Typed"* in `pyproject.toml` classifiers, with `strict = true` mypy and `filterwarnings = ["error"]` in config.

The *configuration* asserts a level of rigour the *repository* does not meet: mypy strict fails with 24 errors, ruff fails with 31, and there are no tests. A classifier is a promise to downstream users and to contributors running `pip install tracefield` that the type information is sound. Right now `mypy` in CI (once CI exists) would be red on day one. I challenge the decision to declare `Typing :: Typed` before `mypy` is green — the honest sequencing is: fix the 24 errors (most are mechanical: `NoReturn` on `fail()`, `dict[str, Any]` annotations, deleting unused imports), *then* add the classifier. Shipping a red strict-mypy config with a Typed classifier trains contributors to ignore the type checker, which is far more expensive than the fix.

## A5.7 Concrete failure mode

**An analyst attaches a directory and gets a stack trace instead of a diagnosis (reproduced 2026-10-16).**

```
$ tracefield evidence attach /tmp/opencode/adir --case demo
Traceback (most recent call last):
  … inspect.detect_media_type …
    with p.open("rb") as f:
  File "…/pathlib/_local.py", line 539, in open
    return io.open(self, mode, buffering, encoding, errors, newline)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
IsADirectoryError: [Errno 21] Is a directory: '/tmp/opencode/adir'
$ echo $?
1
```

`cli/main.py:516` declares `dir_okay=True`, so Typer accepts the argument; `detect_media_type` then opens it as a file. `pretty_exceptions_enable=False` was set precisely to suppress this kind of output, but no replacement handler exists, so the user gets the raw Python traceback with filesystem paths. The same pattern will recur for: a symlink loop, a file deleted between Typer's `exists=True` check and the read (TOCTOU), a permission-denied file, and a named pipe (`exists=True` passes, `open("rb")` blocks forever with no timeout and no cancellation — a trivial local denial-of-service against your own tool). Four distinct failure classes, one missing `try/except OSError` at the CLI boundary and one wrong Typer flag.

---

# Cross-cutting conflicts

These are places where two roles' recommendations pull in opposite directions, or where one role's finding invalidates another role's assumption.

1. **Export redaction: A2/A4 want it; A1's immutability invariant forbids it as written.** A4 recommends recomputing the manifest over redacted bytes; A1's staged plan (S0) wants `case-export` to stay a pure copy. *Resolution proposal:* exports become a distinct artefact type with their own digests and an explicit `redaction_applied` flag — not a mutated copy of the case store. That satisfies both, but it is a schema change (manifest needs a `digest_kind ∈ {source, exported}` field) and should land in S0, not S1, because it is a privacy bug today.

2. **Catalogue storage: A1 wants the `catalog`/`providers` tables deleted; A3 wants a versioned shipped dataset that search can query.** *Resolution proposal:* keep JSONL as the source of truth and the shipped artefact; add a single derived, rebuildable `catalog_cache` table populated by an explicit `tracefield tools sync` command, never by import side effects. Delete `providers` (it is a subset of `CatalogEntry` and has no consumer).

3. **`check_username` placement: A3 wants it generalised into the `ToolAdapter` contract; A4 wants it kept hard-coded as an auditable safety allowlist.** These are in genuine tension — extensibility vs. auditability for a feature whose failure mode is misattributing identity to a real person. *Resolution proposal:* keep the provider list as reviewed Python code (auditable, diffable, testable) but make the *rule shape* implement `ToolAdapter`, so the contract is shared and the data is not. Do not move provider rules into JSONL.

4. **Relation direction semantics: A1 wants `claim` to always be the object; A4's `assess_claim` currently counts `r.from_id` as an origin.** Directly contradictory readings of the same dataclass. *Resolution proposal:* settle it in the `Relation` docstring in the same PR that adds `evidence_ids`, and change `distinct_origins` to be computed from the *evidence's* source, not from `from_id`. A5 should lock this with a golden test before either is merged.

5. **TUI scope: A2 recommends real write capability (case selector, in-app search, workers); A1's S1/S2 staging has the TUI as a viewer until S2.** *Resolution proposal:* the case selector is not a feature, it is a correctness fix for R-A2-2, and belongs in S0. Everything else (search, workers, palette) can wait for S2.

6. **Determinism vs. usability: A4/A5 want an injectable clock and ID factory; A1's domain module is deliberately free of injection machinery.** *Resolution proposal:* keep `utcnow()`/`new_id()` as module-level functions but route them through a single `_clock`/`_ids` indirection that defaults to the real implementations. No DI framework, no behavioural change, tests become possible.

7. **`doctor` machine output: A2 wants `--json`; A5 wants `doctor` to stay a zero-network, zero-side-effect probe.** Not actually in conflict — `--json` is output formatting only — but worth stating because a plausible "improvement" (making `doctor` also check catalogue health, A3 rec #7) would violate A5's constraint. *Resolution proposal:* `doctor` stays local-only forever; catalogue health is a separate `tools health` command that is network-opt-in.

---

*End of TEAM A review. Prepared for the 2026-10-16 TRACEFIELD multi-role review.*
