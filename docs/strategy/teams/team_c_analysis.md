# TEAM C — Analytical Practice Review of TRACEFIELD (v0.1.0)

> Simulated role-based review conducted by independent review subagents on 2026-10-16. Role perspectives grounded in publicly available methods — not interviews with real analysts.

## Scope and method

Files read in full (review build of 2026-10-16):

- `src/tracefield/core/domain.py`, `core/analysis.py`, `core/origins.py`, `core/contradictions.py`, `core/provenance.py`
- `src/tracefield/reporting/build.py`, `reporting/export.py`
- `src/tracefield/cli/main.py`, `src/tracefield/tui/app.py`
- `src/tracefield/fieldtools/inspect.py`, `fieldtools/ocr.py`, `fieldtools/fetch.py`, `fieldtools/username.py`
- `src/tracefield/security/redact.py`, `security/sanitize.py`, `security/urls.py`
- `src/tracefield/config/settings.py`, `storage/database.py`, `storage/repositories.py`, `registry/catalog.py`
- `README.md`, `pyproject.toml`; `docs/` and `tests/` are empty in this snapshot

Empirical checks were run against the project's own `.venv` interpreter on 2026-10-16 (`sys.path` → `src`). Every claim below marked **[R-check]** was executed, not inferred. Line numbers refer to the files as read on 2026-10-16. No repository files were modified by this review; scratch fixtures were written only to `/tmp/opencode/`.

Web sources for C3 (and privacy notes in C5) were retrieved via web search on 2026-10-16 and are listed with URLs and access date at the end. Anything not confirmed from a retrieved page is marked **unknown**.

---

## 0. Cross-cutting P0 finding (affects all five roles): the analytic core is unreachable from the shipped interface

Before role-specific findings, one structural fact dominates every other observation. The domain model, the assessment engine, the origin-clustering engine, and the contradiction detector all exist and are importable — but **no CLI command, TUI action, or repository call path in the application ever creates the records they consume, and several of them are never invoked at all.** Verified by exhaustive grep over `src/tracefield/` on 2026-10-16:

| Capability | Code exists | Called from application code? | Consequence |
|---|---|---|---|
| Create a `Relation` (supports/contradicts/corroborates) | `RelationRepo.add` (`storage/repositories.py:345`) | **No** — the only reference is its own definition | A case built with the CLI can never leave `UNASSESSED`; `assess_claim` has nothing to read |
| Confirm/reject a relation (`ReviewState.CONFIRMED`) | `RelationRepo.set_review_state` (`storage/repositories.py:374`) | **No** | `CORROBORATED_WITH_LIMITATIONS`, `SUPPORTED_BUT_UNCONFIRMED`, `CONTESTED`, `CONTRADICTED_BY_AVAILABLE_EVIDENCE` are all unreachable via the product (they require `CONFIRMED` relations, `core/analysis.py:46-51`) |
| Run origin clustering | `find_origin_edges` / `cluster_from_edges` (`core/origins.py:62,95`) | **No** — only `ClusterRepo.list_for_case` is read in `reporting/build.py:35` | `origin_clusters` is always `0` in reports; the anti-syndication machinery never runs |
| Run contradiction detection | `find_contradictions` (`core/contradictions.py:50`) | **No** | Structured conflict detection is dead code |
| Record a tool return as an `Observation` | `ObservationRepo` (`storage/repositories.py:299`) | **No** — never instantiated | `inspect`/`ocr`/`fetch` outputs are printed and lost; the report cannot cite a single tool observation |
| Create an `Assertion` (analyst conclusion) | `AssertionRepo.add` (`storage/repositories.py:385`) | **No** | Reports have a counts field for assertions and never render any (`reporting/build.py:34,52`) |
| Verify the tamper-evidence chain | `EventRepo.verify_chain` (`storage/repositories.py:522`) | **No** | The hash chain is written but no shipped command can check it |
| Set claim status to `RETRACTED` | `Claim.status` field exists (`core/domain.py:36-39`) | **No** update command exists | The corrections workflow advertised by the domain model cannot be performed |

The TUI compounds this by advertising commands that do not exist: `tui/app.py:213` lists `tracefield username check <name>` and `tui/app.py:268` tells users to run `tracefield tools search <query>` — neither is registered in `cli/main.py` (command surface is `doctor`, `init`, `case`, `source`, `claim`, `evidence`, `hash`, `inspect`, `ocr`, `report`, `case-export`, `case-delete`, `tui`). `cli/main.py:3-5` claims "Every advertised command has a real implementation." **[R-check: command registry read in full]**

**Effect on report defensibility:** every case report produced by the shipped product today reads `UNASSESSED` with the caveat "No supporting or contradicting relations recorded" (`core/analysis.py:132-134`) regardless of how much work the analyst did, because the work surface (`source add`, `claim add`, `evidence attach`) never creates relations. An analyst following the README five-minute workflow (`README.md:26-34`) gets a report that structurally cannot distinguish a well-sourced claim from an empty one.

---

## C1. OSINT Verification / Investigative Journalism Analyst

**Mandate simulated:** claim decomposition, source attribution, origin tracking, media verification, alternative hypotheses, chronology, corrections, report defensibility. Review of the *actual implemented workflow*: `case create` → `source add [--fetch]` → `claim add` → `evidence attach` → `report` / `case-export`.

### C1.1 Workflow review (what the analyst can actually do)

Strengths worth keeping, from an analyst's standpoint:

- Conservative outcome vocabulary (`core/domain.py:73-81`) with explicit "workflow state, not probability" framing repeated in the report footer (`reporting/build.py:182-184`) and global caveats (`reporting/build.py:66-75`). This is genuinely better practice than numeric "confidence scores."
- `Source.published_at` vs `first_seen_at` vs `collected_at` are three distinct fields (`core/domain.py:121-123`) — correct chronology semantics; most tools collapse them.
- Evidence is content-addressed and re-hashable (`core/provenance.py:62-65,133-137`), and `evidence verify` actually re-hashes (`cli/main.py:597-630`). The manifest caveat correctly states hashes prove byte integrity, not truth (`core/provenance.py:177-181`).
- Fetch failures preserve the declared URL plus an error note instead of fabricating a snapshot (`cli/main.py:369-376`). Honest failure is the right default for collection records.
- `OriginCluster` is modelled as a hypothesis with `review_state=unreviewed` (`core/origins.py:136-137`) — the right epistemics, even though the pipeline that would produce clusters is never executed (section 0).

Deficiencies that break the analyst loop:

1. **No claim decomposition support.** A `Claim` is free text with `claim_type`, `temporal_scope`, `spatial_scope` (`core/domain.py:172-183`) but nothing requires or assists splitting a compound claim, and the assessment engine treats the whole claim atomically. Compound claims are the classic source of unfalsifiable "mostly true" judgments.
2. **No alternative-hypothesis artifact.** There is no entity for competing explanations; `Assertion` (`core/domain.py:157-169`) could serve but is unreachable (section 0) and has no `hypothesis` kind. `assess_claim` never asks "what else would explain this evidence?"
3. **No origin tracking for *claims*.** `Claim.origin: str = "analyst"` (`core/domain.py:179`) is a free-text string with no link to the source that first asserted it. "Who said it first" — the single most load-bearing question in a verification report — is not modelled.
4. **Corrections/retractions are unimplementable.** `ClaimStatus.RETRACTED` exists; there is no command to set it, no report section for corrections, and `assess_claim` does not inspect `claim.status` at all (`core/analysis.py:22-140` never reads `.status`). A retracted claim would still be assessed and rendered.
5. **Chronology is not rendered.** Sources carry three timestamps and evidence carries `captured_at`, but `render_markdown` produces no timeline section (`reporting/build.py:103-132` lists sources and evidence as unordered blocks — sorted only by `first_seen_at`/`captured_at` in the repo, `storage/repositories.py:212,250`).
6. **The report has no generation metadata.** `build_case_payload` (`reporting/build.py:29-76`) contains no `generated_at`, no tool version, no analyst/owner identity (`Case.owner_label` exists at `core/domain.py:107` but is never rendered or settable from the CLI). A report that cannot say *when, by which tool version, by whom* is hard to defend in an editorial or legal review.
7. **Fetched pages are not snapshotted.** `fetch_source` computes the body's SHA-256 and stores the digest in the `limitations` free-text field (`fieldtools/fetch.py:98-102`) but discards the bytes (`fieldtools/fetch.py:105-107`). A digest of bytes nobody kept is not verifiable later, and `limitations` is being overloaded as a metadata sink (title, final URL, status, content-type, digest all concatenated at `fieldtools/fetch.py:98-109`).
8. **Contradiction detection is format-naive and never wired in.** Even if wired, [R-check] the date rule flags *the same date written in two formats* as a contradiction (`2024-01-02` vs `01/02/2024` → one candidate, `core/contradictions.py:36-43,56-72`), while a *shared* date in two excerpts suppresses all date conflicts between them (`dates_a & dates_b` non-empty → no candidate). The quantity aspect promised by the docstring (`core/contradictions.py:3,27`) has no rule; `_NUM_RE` (`core/contradictions.py:20`) is unused.

### C1.2 Risks

- **R-C1-1 (High).** Every shipped report renders `UNASSESSED` for all claims (section 0). An editor or court reviewer seeing a professional-looking report whose assessments are uniformly empty will either distrust the tool or, worse, distrust the analyst's competence.
- **R-C1-2 (High).** Report defensibility gaps: no `generated_at`, no tool version, no author, no corrections section, no assertions rendered (`reporting/build.py:79-185`), no publisher/visibility for sources (the fields exist at `core/domain.py:118,125`; the renderer omits them at `reporting/build.py:107-118`, and no CLI command can set them).
- **R-C1-3 (Medium).** Overloaded `limitations` string on `Source` (`fieldtools/fetch.py:98-109`) mixes collection metadata with honest-limitation notes. When an analyst later reads "fetch failed: HTTP 404" next to "title=…; final_url=…; sha256=…", the field has lost its meaning as a caveats channel.
- **R-C1-4 (Medium).** Local-file sources store absolute paths (`cli/main.py:536`) and evidence attach records the absolute original path in the event log (`core/provenance.py:100` → `inputs=[str(src)]`). Reports render source locators verbatim (`reporting/build.py:109`), so a report published externally leaks analyst filesystem structure and usernames.
- **R-C1-5 (Medium).** Tamper-evidence chain omits `occurred_at` and `tool_fingerprint` from the digest (`storage/repositories.py:538-547` hashes only action/inputs/outputs/prev). Rewriting timestamps or tool versions does not break `verify_chain` (`storage/repositories.py:522-535`). `case-delete` appends no event (`cli/main.py:746-751`), so destructive actions are the one thing the chain never records.
- **R-C1-6 (Low).** `reporting/build.py:40` attributes *any* relation touching a claim (`from_id == claim.id or to_id == claim.id`) to that claim, so a claim-to-claim relation (e.g., `B derived_from A`) is double-counted into both claims' assessments.

### C1.3 Concrete failure modes

- **FM-C1-1.** Analyst spends a day on a case: 12 sources, 4 claims, 9 evidence files; runs `tracefield report case`. Output: 4 × `UNASSESSED`, each with "No supporting or contradicting relations recorded" and "Supporting relations: 0; contradicting: 0" (`reporting/build.py:146-150`), even though the analyst attached and verified evidence for each claim. No command exists to record *why* the evidence supports the claim. [R-check: no `RelationRepo.add` call site in the tree]
- **FM-C1-2.** [R-check] With relations present but only `REJECTED` ones, `assess_claim` returns `UNASSESSED` with the caveat "No supporting or contradicting relations recorded" **while `contradicting_count=1`** — the report simultaneously asserts zero contradicting relations and prints "contradicting: 1". Rejected relations fall through every branch (`core/analysis.py:93-134`) yet are still counted (`core/analysis.py:61-62`).

### C1.4 Challenged assumption

**Challenged:** the README's claim that "findings rarely survive the trip from collection to report with intact provenance" is *solved* by TRACEFIELD (`README.md:10-14`). **Counter:** provenance of *bytes* is solved (content-addressing, manifests, event chain); provenance of *conclusions* is not — the chain from `EvidenceItem` → `Relation` → `AssessmentVector` → rendered sentence is broken at the first hop (no relations can be created), and the report cannot even state its own generation time. Byte provenance without conclusion provenance produces what forensic reviewers call "integrity theatre": everything hash-checks, nothing is argued.

### C1.5 Recommendations

1. **P0 — ship the review surface.** `tracefield relation add --from <source> --to <claim> --type supports|contradicts|corroborates --rationale "…"` and `tracefield relation review <id> --confirm|--reject`. Without these the assessment engine is decorative.
2. **P0 — render analyst conclusions.** Add an "Analyst assertions" section to `render_markdown`; add `generated_at`, `tracefield_version`, and `Case.owner_label` to the payload header (`reporting/build.py:45-76`).
3. **P1 — claim decomposition.** Add `Claim.parent_id` (or `derived_from` enforcement) and render the claim tree; require each leaf claim to be a single checkable proposition before assessment.
4. **P1 — corrections.** `tracefield claim retract <id> --reason "…"` writing an `AnalysisEvent` with action `claim.retract`, plus a report "Corrections and retractions" section that lists superseded assessments with timestamps.
5. **P1 — snapshot or stop hashing.** Either store the fetched body as evidence (`ws.attach_bytes`, `core/provenance.py:103-131`) behind an explicit `--save-snapshot` flag, or drop the body digest from `limitations` and record it as a proper `Observation.raw_ref`. Split `limitations` into structured fields (`final_url`, `http_status`, `content_type`, `title`) plus a real `limitations` string.
6. **P1 — timeline section.** Render a merged, sortable chronology of `published_at`/`first_seen_at`/`collected_at`/`captured_at` in report output.
7. **P2 — fix `assess_claim` counting.** Exclude `REJECTED` relations from `supporting_count`/`contradicting_count`; either give rejected-only cases their own outcome or a distinct caveat. Align the docstring with behavior (see AC-C2-3).
8. **P2 — redact analyst-local paths** in rendered reports by default (replace absolute local paths with `<local-path>` unless `--include-paths`).

### C1.6 Open questions

- Q-C1-1. Should `CORROBORATES` be an analyst-only relation, or may a machine method propose it? Today `Relation.method` defaults to `"analyst"` (`core/domain.py:202`) with no distinction enforced.
- Q-C1-2. What is the intended difference between `Assertion` (evidence-linked interpretation) and `Relation` (evidence-linked link)? Both are described as interpretation layers; without guidance analysts will double-book.
- Q-C1-3. Is a retraction supposed to mutate the old assessment or append a superseding one? Append-only is defensible; the schema currently supports neither.
- Q-C1-4. Who is the report *for* — internal newsroom, public publication, or court disclosure? Redaction and path-leakage requirements differ; the product currently guesses.

### C1.7 Testable acceptance criteria

- **AC-C1-1.** Given a case with one source and one claim, when the analyst runs `relation add` + `relation review --confirm`, then `tracefield report` shows `SUPPORTED_BUT_UNCONFIRMED` (1 origin) and never `UNASSESSED`. Test: end-to-end CLI test in `tests/`.
- **AC-C1-2.** Given only `REJECTED` relations on a claim, then `supporting_count`/`contradicting_count` both render `0` **or** the report prints an explicit "N rejected relations excluded" line; the caveat "No … contradicting relations recorded" may never appear together with a non-zero contradicting count. Test: unit test on `assess_claim` + snapshot test on `render_markdown`.
- **AC-C1-3.** Every rendered report contains `generated_at` (UTC ISO-8601 `Z`), tool version, and case owner label. Test: report builder unit test.
- **AC-C1-4.** `tracefield claim retract <id>` sets status, appends an event, and the next report lists the claim under "Corrections and retractions". Test: CLI + report test.
- **AC-C1-5.** A report rendered from a case containing an absolute path locator never contains `/home/` or the analyst username unless `--include-paths` is passed. Test: security regression test (marker exists in `pyproject.toml`).
- **AC-C1-6.** `find_contradictions("…2024-01-02…", "…01/02/2024…")` returns **zero** candidates after dates are normalized to one canonical form; and two excerpts sharing a publication date but disagreeing on an event date produce exactly one candidate. Test: unit tests on `core/contradictions.py`.

---

## C2. Source Evaluation & Corroboration Analyst

**Mandate simulated:** independence assessment, common-origin detection, primary vs secondary evidence, source bias/interest, temporal relevance, confidence wording. Focus files: `core/origins.py` (Jaccard 5-gram clustering) and `core/analysis.py` (`assess_claim`).

### C2.1 Corroboration rubric (recommended, mapped to current code)

| Grade | Definition | Independent signals TRACEFIELD should require | Current state |
|---|---|---|---|
| **G0 Unassessed** | No reviewed evidence | — | Only grade reachable today via CLI |
| **G1 Single-source** | One origin, primary or secondary | 1 confirmed origin | Reachable only after relations exist (`SUPPORTED_BUT_UNCONFIRMED`, `core/analysis.py:120-125`) |
| **G2 Dependent multi-reporting** | ≥2 sources that share an origin (syndication, wire copy, mutual citation) | ≥1 confirmed origin cluster covering ≥1 supporting source, analyst-confirmed | Clusters never computed; `origin_clusters` is a *count* that only adds a caveat (`core/analysis.py:115-119`) |
| **G3 Independent corroboration** | ≥2 sources with demonstrated independence: different publishers, no shared upstream, no cross-citation, different collection times, ideally primary vs secondary | ≥2 confirmed origins **not** in the same confirmed cluster + ≥1 `CORROBORATES` + publisher/ownership check + temporal spread | `CORROBORATED_WITH_LIMITATIONS` requires only "≥2 distinct `from_id`s" (`core/analysis.py:57,106-109`) — no cluster, publisher, or time check |
| **G4 Primary anchoring** | G3 plus ≥1 primary record (document, dataset, first-hand) | `SourceType` + `access_method` + evidence-linked excerpt | `SourceType` exists (`core/domain.py:49-56`) but is never consulted by `assess_claim` |

Bias/interest and temporal relevance are not modelled at all: `Source.publisher` and `Source.visibility` (`core/domain.py:118,125`) are unsettable from the CLI and unread by the engine; `Source.published_at` is unread by `temporal_fit`, which is hard-coded `"unknown"` (`core/analysis.py:86`).

### C2.2 How naive source counting is defeated in the current code

All of the following were executed against the shipped modules on 2026-10-16.

**Adversary A — 20 syndicated verbatim copies + 1 reworded original.**
[R-check] 20 `DocInput`s sharing one sentence with 20 different URLs produced 190 pairwise `near_duplicate_text>=0.8` edges (all 20 collapse into one cluster — good), while the *reworded* restatement of the same story scored **0.0** Jaccard and remained a singleton. In `assess_claim`, singleton = "distinct origin": if an analyst confirmed one support relation per URL, `distinct_origins` = 21 (`core/analysis.py:57`). The clustering, even if it were wired into the pipeline, **cannot see the paraphrase**, and nothing in `assess_claim` consumes cluster membership — `origin_clusters=len(clusters)` is passed as a scalar (`reporting/build.py:42`) and used only to append a warning *after* the corroborated outcome has already been chosen (`core/analysis.py:110-119`). Outcome: `CORROBORATED_WITH_LIMITATIONS` on what is one journalistic origin plus one rewrite.

**Adversary B — paraphrasing that evades the 0.8 Jaccard threshold.**
[R-check] Original vs. light paraphrase (same entities, same numbers, different syntax) → Jaccard **0.0**. The 5-gram word-set representation (`core/origins.py:29-33`) has no stemming, no entity/number channel, no MinHash/containment fallback. Any deliberate or even editorially normal rewrite defeats near-duplicate detection entirely. The signal is effectively "near-verbatim copy detector," mislabelled as origin detector.

**Adversary C — word-reordered text scores as a perfect copy (false common origin).**
[R-check] A sentence and its exact reversal produce Jaccard **1.0**; two short texts that merely share a word pool ("alice was here" / "here was alice") also produce 1.0. Root cause: shingles are `frozenset` of window words (`core/origins.py:33`), discarding order *within* the 5-word window. Ordered `tuple` shingles would fix this. False common-origin edges matter because they *merge independent sources*, which in a future wired pipeline would wrongly demote genuine G3 corroboration to G2.

**Adversary D — non-Latin sources are unclusterable.**
[R-check] `_WORD_RE = [a-z0-9]{4,}` (`core/origins.py:22`) with `.lower()`; a Russian-language text normalizes to `""`, `word_shingles` returns `set()`, and `jaccard` returns `0.0` for empty sets (`core/origins.py:37-38`). Twenty verbatim Cyrillic/Arabic/Chinese syndications produce zero edges. This is a systematic blind spot for exactly the cross-language laundering that origin analysis exists to catch.

**Adversary E — two URLs, one publisher.**
`distinct_origins` counts `Relation.from_id` strings (`core/analysis.py:57`). Nothing validates that `from_id` is a `Source` (the `relations` table has no foreign keys on `from_id`/`to_id`, `storage/database.py:111-113`), nothing joins to `Source.publisher`, and no ownership/canonical-domain table exists. Two properties of the same outlet (`news.example.com` and `cdn-syndication.example.com`) count as two origins; two different mastheads owned by the same parent company count as two origins.

**Adversary F — self-corroboration and relation spam.**
[R-check] Duplicating `SUPPORTS` relations from the same `from_id` inflates `supporting_count` (4 relations from 2 sources → `supporting_count=4`), because `supporting_count=len(supports)` includes unreviewed, rejected, and duplicate relations (`core/analysis.py:41-44,61-62`). One source emitting both a `SUPPORTS` and a `CORROBORATES` relation contributes to the corroboration requirement's "any `CORROBORATES` present" clause (`core/analysis.py:106-108`) without any second source being needed for that half of the test.

**Adversary G — cross-citation conflates "cites" with "is".**
[R-check] Page B citing page A's URL produces an edge `b_url_cited_by_a` with score 1.0 (`core/origins.py:78-83`) and the two are clustered as one origin. For *independence* purposes that is defensible (a citing source is dependent), but the cluster then contains the *origin* and the *dependent copy* indistinguishably — the analyst loses the direction the evidence actually supports, and `cluster_from_edges` performs single-linkage union-find (`core/origins.py:95-118`) so a chain of citations can merge an entire beat into one blob. Substring matching also risks false edges (A's URL appearing as a prefix inside a longer URL in B's text).

### C2.3 Risks

- **R-C2-1 (Critical).** `CORROBORATED_WITH_LIMITATIONS` is awarded on distinct `from_id` count alone. Combined with unreachable clustering (section 0), the product's highest corroboration grade is structurally unable to detect syndication.
- **R-C2-2 (High).** `evidence_directness` and `temporal_fit` are hard-coded `"unknown"` (`core/analysis.py:77,86`); `independence` is a stringified count (`core/analysis.py:78-82`). The "multi-dimensional assessment vector" (`core/domain.py:232-248`) varies in practice on 3 of 9 fields. Marketing the vector as explainable multi-dimensional assessment overstates it.
- **R-C2-3 (High).** Near-duplicate detection fails in both directions (paraphrase → 0.0; reversal → 1.0) and is monolingual-Latin-only.
- **R-C2-4 (Medium).** Docstring/behavior mismatch: the docstring promises `CONTRADICTED_BY_AVAILABLE_EVIDENCE` "when supporting evidence is zero" (`core/analysis.py:34-35`), but the code triggers on *zero confirmed* supports (`core/analysis.py:93-99`). [R-check] One unreviewed `SUPPORTS` + one confirmed `CONTRADICTS` → `CONTRADICTED_BY_AVAILABLE_EVIDENCE`. The machine is asserting a contradiction while unexamined support sits in the case.
- **R-C2-5 (Medium).** Confidence wording in reports leans on the outcome token alone; `caveats` are appended but `render_markdown` prints them as flat bullets (`reporting/build.py:152-153`) with no per-caveat severity, and the crucial "origin independence is itself a hypothesis" caveat (`core/analysis.py:110-114`) is only reachable in the already-corroborated branch.

### C2.4 Concrete failure modes

- **FM-C2-1.** Wire story published by Agency X at 06:00; 20 outlets carry verbatim copies; one outlet rewords it. Analyst confirms supports for 21 URLs (or, in a future wired build, the tool proposes them). Report: `CORROBORATED_WITH_LIMITATIONS`, "21 confirmed origin(s)". True origin count: 1. Published externally, this converts a single-source rumour into an apparent multi-source fact.
- **FM-C2-2.** [R-check] Two independent investigations both cite the original report's URL in their text (good practice!). Edge `a_url_cited_by_b` merges them with the original into one cluster. The demotion the tool *would* apply (if clusters were consulted) would punish two genuinely independent teams for correct citation practice — unless citation direction is preserved and interpreted, which it is not.

### C2.5 Challenged assumption

**Challenged:** "Jaccard on word 5-grams at 0.8 is a sufficient near-duplicate signal for origin clustering" (`core/origins.py:6`, default at `:65`). **Counter from the checks above:** the threshold is simultaneously too high (paraphrases score 0.0), the representation is wrong in both directions (order discarded inside windows → reversal = 1.0), and the normalizer deletes every non-ASCII source from consideration. Public methods literature on near-duplicate news detection (MinHash/LSH over shingles, containment for nested documents, language-specific tokenizers, entity/number overlap as a separate channel) indicates a single fixed 0.8 Jaccard on ordered-word frozensets is not a defensible basis for a corroboration decision that may be published.

### C2.6 Recommendations

1. **P0 — make clusters affect outcomes.** Replace the scalar `origin_clusters: int` parameter (`core/analysis.py:26`) with the actual cluster membership set; a claim whose supporting origins all fall inside one *analyst-confirmed* cluster may not reach `CORROBORATED_WITH_LIMITATIONS` (it should render as `G2` per the rubric).
2. **P0 — wire clustering into a command** (`tracefield origins compute --case …`) and persist `DocInput` provenance (which source's excerpt produced each doc).
3. **P1 — fix the shingle representation:** ordered tuples, Unicode-aware tokenization, plus (a) containment/Jaccard on 3–5-grams, (b) an entity/number overlap channel (dates, quantities, named entities must match for a near-dup edge), (c) a low-threshold "related text" edge distinct from "near-duplicate" so analysts see both.
4. **P1 — publisher/ownership dimension:** populate `Source.publisher` from the CLI, add an optional `ownership_group` field, and count origins by publisher-group, not by URL or `from_id`.
5. **P1 — dedupe relations:** `assess_claim` should count distinct `(from_id)` for independence and distinct `(from_id, relation)` for support strength, excluding `REJECTED` and capping duplicates.
6. **P2 — cross-citation edges should be directional** (`B depends_on A`), never unioned symmetrically; keep the citing source out of the origin set for A.
7. **P2 — surface bias/interest:** add `Source.limitations`-style structured fields `interest` (who benefits) and `independence_notes`; have `render_markdown` print them next to each source.

### C2.7 Open questions

- Q-C2-1. Should analyst-*unconfirmed* clusters demote an outcome, or only annotate? Demotion risks the tool overruling the analyst; annotation risks the caveat being ignored (it already is — see R-C2-1).
- Q-C2-2. What is the intended semantic of `Relation.CORROBORATES` vs `SUPPORTS`? They are treated identically for counting (`core/analysis.py:41-44`), differing only in that one `CORROBORATES` unlocks the top grade.
- Q-C2-3. Is cross-language origin analysis in scope? If yes, the normalizer must be replaced; if no, the limitation must be stated in report caveats.

### C2.8 Testable acceptance criteria

- **AC-C2-1.** Given 20 verbatim copies and 1 paraphrase of one wire story with confirmed supports on each, the computed outcome is not `CORROBORATED_WITH_LIMITATIONS` unless the paraphrase is linked by an analyst-confirmed edge; the report must display "20 sources, 1 detected origin cluster, 1 unlinked source". Test: fixture set `syndication-20-plus-paraphrase` (see C4 fixtures).
- **AC-C2-2.** A document and its word-reversed version produce Jaccard < 0.8 (target: < 0.3) and no `near_duplicate_text` edge. Test: unit test on `word_shingles`/`jaccard`.
- **AC-C2-3.** With one unreviewed `SUPPORTS` and one confirmed `CONTRADICTS`, the outcome is never `CONTRADICTED_BY_AVAILABLE_EVIDENCE`; a new label (e.g., `CONTESTED_WITH_UNREVIEWED_SUPPORT`) or `CONTESTED` is used. Test: unit test pinning the decision table in `core/analysis.py`.
- **AC-C2-4.** Duplicate identical relations from the same `from_id` count once toward `supporting_count`. Test: unit test.
- **AC-C2-5.** Non-Latin (Cyrillic, Arabic, Chinese) near-verbatim copies produce at least one near-duplicate edge at the default threshold. Test: fixture-driven unit test.
- **AC-C2-6.** `assess_claim` never emits `CORROBORATED_WITH_LIMITATIONS` when all supporting origins belong to one confirmed `OriginCluster`. Test: unit test with injected clusters (requires R-C2-1 refactor).

---

## C3. Cyber Threat Intelligence Analyst

**Mandate simulated:** safe public-source workflows for domains, IPs, certificates, URLs, hashes, and threat reports; passive-lookup vs active-testing boundaries; scope/authorization gates. Provider documentation was checked on 2026-10-16 (URLs in the sources section; items I could not confirm from a retrieved page are marked **unknown**).

### C3.1 Passive vs active classification (as TRACEFIELD implements it today)

| TRACEFIELD capability | Classification | Notes |
|---|---|---|
| `tracefield source add <url>` (no `--fetch`) | Passive bookkeeping | Records a locator; no network (`cli/main.py:338-355`) |
| `tracefield source add --fetch` | **Active contact with the target** | Direct GET from the analyst's machine to the target (`fieldtools/fetch.py:51`). The target's server logs the analyst's IP/UA. Network is opt-in (`config/settings.py:43`) and SSRF-guarded (`security/urls.py`), but *target observability* is not addressed anywhere |
| `check_username` (unreachable from CLI) | Active contact with third-party platforms | Hits github/gitlab/reddit/HN/keybase (`fieldtools/username.py:45-83`); follows redirects **without re-validating them** (`fieldtools/username.py:206-212` — no `validate_fetch_url`, unlike `fetch.py:23-25`). Inconsistent with the project's own SSRF policy |
| CTI provider lookups (RDAP/CT/urlscan-search/etc.) | Passive **from the target's** perspective, but **reveals analyst interest to the provider** | See shortlist below |

Two policy gaps that matter more than any single provider choice:

1. **No scope/authorization gate.** `Settings.scope` is a free-text field on `Case` (`core/domain.py:106`) and nothing checks it before `--fetch`. There is no `--i-am-authorized` style attestation, no allowlist of in-scope domains, no blocking of "target of active abuse" fetches. For a tool that will point at hostile infrastructure, the absence of an explicit authorization record is a governance defect, not a legal technicality.
2. **DNS rebinding / TOCTOU in fetch validation.** `validate_fetch_url` resolves the host and checks addresses (`security/urls.py:83-87`), then httpx resolves *again* at connect time. A low-TTL name that resolves publicly on the first lookup and to `127.0.0.1`/`169.254.169.254` on the second defeats the guard. The redirect hook (`fieldtools/fetch.py:23-25`) re-runs the same non-pinning validation. This is the classic SSRF bypass pattern; the code claims "Fails closed" (`security/urls.py:6`) which is true only against static hostile DNS, not rebinding.

Positive notes: scheme allowlist, credential-in-URL rejection, blocked metadata hostnames, `.local`/`.internal` suffix rejection (`security/urls.py:69-87`); `trust_env=False` on httpx clients so ambient proxy env vars cannot reroute collection (`fieldtools/fetch.py:45`, `fieldtools/username.py:211`); explicit refusal to retry/circumvent 429/403 (`fieldtools/fetch.py:58-62`, `fieldtools/username.py:110-125`).

### C3.2 Safe-provider shortlist for a future `tracefield ct` module

Every row: retrieved 2026-10-16 via web search; re-verify terms before integration (ToS change frequently).

| # | Provider | Use | Class | Access model | Terms / exposure caveats |
|---|---|---|---|---|---|
| 1 | **RDAP (IANA bootstrap + per-TLD servers; convenience: rdap.org, lookup.icann.org)** | Domain registration data: registrar, dates, nameservers, status codes | Passive | Free, no key for registry queries; rdap.org rate-limits ~10 req/10 s (Cloudflare) per its docs | Registrant PII is routinely redacted for unauthenticated queries (RFC 9537 defines explicit redaction signalling); nonpublic data goes through RDRS, not scraping. ICANN lookup ToU: lawful purposes only. Querying a registrar's RDAP directly means *the registry/registrar sees the query* — rdap.org's client pages exist specifically to minimize that; direct client→registry is privacy-preferable. URLs: `https://rdap.org/`, `https://lookup.icann.org/`, `https://www.iana.org/assignments/rdap-dns/rdap-dns.xhtml` (bootstrap), `https://www.rfc-editor.org/rfc/rfc9537` |
| 2 | **crt.sh (Sectigo)** | Certificate Transparency search: SANs, issuance history, cert fingerprints | Passive | Free web UI; programmatic access via their documented query interface — rate limits and bulk-use policy **unknown**, do not scrape aggressively | CT data is public by design (browser-trusted logs since 2018). Subdomain discovery via CT is standard practice. Treat newly-issued certs for a monitored domain as a *security signal*, not an accusation. URL: `https://crt.sh/` |
| 3 | **SSLMate Cert Spotter API** | CT issuance lookup/monitoring by domain | Passive | API key; paid tiers for volume (pricing page observed: hobbyist tier exists) | Same CT-public-data posture; check `https://sslmate.com/certspotter/api/docs-v1` (exact current terms **unknown** — page not retrieved) |
| 4 | **urlscan.io Search API** | Historical passive-DNS-like view: who contacted this domain/IP, past screenshots, related scans | Passive (search) | API key for meaningful quotas; unauthenticated search is limited | **Do not confuse with urlscan Scan API.** Submitting a URL for *scanning* is an active action: urlscan's browser fetches the target from urlscan infrastructure, and `visibility` defaults to `public` (docs) with an `overrideSafety` flag that disables PII reclassification — i.e., submitting URLs can leak investigation targets and personal data to the public internet. ToS require backoff and prohibit circumvention. URLs: `https://docs.urlscan.io/apis/urlscan-openapi/scanning`, `https://api.urlscan.io/docs/search`, `https://api.urlscan.io/terms` |
| 5 | **Censys Search API** | Hosts, certificates, web properties from Internet-wide scans | Passive (querying their corpus) | Account + API key; tiered endpoints (free tier: host/certificate/web-property lookups only); API calls consume credits | Censys's own scanning is active against the whole IPv4 space, but *your* query is passive. ToS: no crawling of the web UI (API only), no redistribution of Censys Data without consent (researcher terms allow inclusion in reports/publications); free/research accounts non-commercial only. URLs: `https://docs.censys.com/reference/get-started`, `https://censys.com/terms-and-conditions`, `https://about.censys.io/` |
| 6 | **Shodan** | Service/banner exposure data | Passive (querying their corpus) | Account; research/academic tiers with affiliation requirements | ToS observed prohibit automated access outside their API and robots.txt compliance; academic access requires institutional email and is non-commercial. URLs: `https://static.shodan.io/legal/terms.html` |
| 7 | **VirusTotal (file/URL *report* lookup by hash)** | Hash reputation, historical sightings | Passive **if you only GET reports by hash** | API key; public API ~4 req/min (historical; current limits **unknown**) | **Never upload samples** in an OSINT workflow: submission shares the sample with partners and the community (site consent text: "sharing of your Sample submission with the security community"), which for evidence-file uploads means disclosing case material to third parties — including potentially the subject of investigation. URL lookups similarly share the URL. Prefer hash-only GETs. URLs: `https://docs.virustotal.com/docs/how-it-works`, `https://developers.virustotal.com/v3.0/reference` |
| 8 | **DNS resolver lookups (system resolver / DoH of operator's choice)** | Current A/AAAA/NS/MX/TXT | Passive from target's view (resolver sees query) | None | Resolver choice leaks target-of-interest to whoever operates the resolver; prefer a resolver with a stated no-log policy — specific policy claims **unknown/unverified** here |

Explicitly out of scope for passive CTI (must not be added without an authorization gate): port scanning, vulnerability probing, credential testing, brute-force paths, CAPTCHA/anti-bot circumvention, and anything that interacts with the target beyond a single GET of a public page. TRACEFIELD's own fetch is a single bounded GET — acceptable for public pages *of in-scope targets*, and it already refuses to retry 403/429 (`fieldtools/fetch.py:58-62`), which is the right posture.

### C3.3 Risks

- **R-C3-1 (High).** No authorization/scope gate before network actions (§C3.1). An analyst under time pressure will point `--fetch` at whatever domain appears in a tip, including targets they have no permission to touch (employer rules, national law, platform ToS).
- **R-C3-2 (High).** DNS rebinding TOCTOU defeats the SSRF guard (§C3.1); the metadata-endpoint blocklist (`security/urls.py:16-23`) is defeated the same way. Cloud metadata IPs are additionally covered by the private-range check (`security/urls.py:32-40`) only if the *second* resolution returns them.
- **R-C3-3 (Medium).** `username.py` skips URL policy validation entirely on both initial request and redirects (`fieldtools/username.py:216-247`), inconsistent with `fetch.py`. If a provider redirects to an internal address, httpx follows it.
- **R-C3-4 (Medium).** No provider-integration layer exists yet, so the ToS/rate-limit posture of any future provider module is currently *unimplementable*: there is no per-provider rate limiter, no API-key storage design, and no "provider refused" state machine beyond the inline 429/403 handling in the two network modules. (`registry/catalog.py` models `rate_limits`/`terms_url` as inert metadata at `:77-79`, which is good, but nothing consumes it.)
- **R-C3-5 (Low).** `User-Agent` construction in `fetch.py:37` produces `tracefield/0.1 (+https://)` — malformed, no contact URL. Providers' ToS and abuse desks expect a reachable contact; a missing contact invites blocks and looks like a scraper.

### C3.4 Concrete failure modes

- **FM-C3-1.** Analyst fetches a phishing-kit mirror domain discovered in a tip. The domain's DNS returns a public A record to `validate_fetch_url`, then `127.0.0.1` to httpx. The GET hits the analyst's own machine (or a cloud metadata endpoint if the analyst runs in a cloud VM), and the fetch result is recorded as a legitimate source with `http=200`. [Design-level; not executed against live infrastructure]
- **FM-C3-2.** Analyst runs `check_username` for a person of interest across five providers with redirects enabled; one provider 302s to an unvalidated host. Even without malice, five providers × 1 s sleeps × unvalidated redirects is a policy inconsistency that a security review will flag as SSRF.

### C3.5 Challenged assumption

**Challenged:** "network fetches are opt-in ⇒ the network surface is safe by default" (`config/settings.py:43`, `README.md:60-62`). **Counter:** the default is safe for *unwitting* users; it does nothing for *deliberate* users, who are the entire user base of an OSINT workbench. Safety for deliberate users comes from scope gates, per-target authorization records, provider ToS metadata enforced in code, and passive-first defaults for CTI object types (domain/IP/cert/hash should default to RDAP/CT/report lookups, never to direct contact).

### C3.6 Recommendations

1. **P0 — scope gate.** Require `Case.scope` to be non-empty before any network command; add `tracefield scope add <domain>` allowlist and refuse `--fetch` for out-of-scope hosts with a distinct exit code.
2. **P0 — pin IPs on fetch.** Resolve once, validate, then connect to the validated IP with correct TLS SNI/Host (httpx supports `transport` with a custom resolver mapping). Re-validate every redirect hop against the same pinned policy.
3. **P1 — apply `validate_fetch_url` in `username.py`** (initial URL and each redirect), exactly as `fetch.py` does.
4. **P1 — CTI module order:** RDAP → CT (crt.sh/Cert Spotter) → passive search APIs (urlscan search, Censys) → hash reputation (VT GET-only). Direct target contact last, behind the scope gate, with a mandatory `--acknowledge-contact` flag.
5. **P1 — provider registry enforcement.** Read `terms_url`/`rate_limits`/`data_exposure_warning` from the catalogue and require an analyst to record `terms_reviewed_at` before first use of a provider module; refuse to run otherwise.
6. **P2 — fix the UA string** to `tracefield/0.1 (https://github.com/killerdasher/TRACEFIELD; research OSINT workbench)`.
7. **P2 — network action journal.** Every outbound request should append an `AnalysisEvent` (action `net.fetch`, inputs `[url]`, outputs `[status]`) so the case records that contact was made — this is also a C1 provenance requirement.

### C3.7 Open questions

- Q-C3-1. Should TRACEFIELD ever integrate a URL *scanner* (urlscan submit, VT URL submit) given the public-visibility defaults? My position: no for the free tiers; only against providers offering private/unlisted scans, with the exposure warning printed at submission time.
- Q-C3-2. Is there a jurisdiction boundary (users in EU/UK vs US) that should shape RDAP/PII handling guidance shipped in the docs?
- Q-C3-3. Should hash lookups be allowed for *evidence* hashes (case files) at all, given that a hit can leak the existence of a file to a third party? (See C5 risk register.)

### C3.8 Testable acceptance criteria

- **AC-C3-1.** `--fetch` on a host not in the case scope list fails with a documented exit code and no outbound connection (test: mock transport asserting zero requests).
- **AC-C3-2.** A test double DNS that answers `public-ip` on first resolution and `127.0.0.1` on second produces a policy refusal, not a request (test: fake resolver injected into the fetch path).
- **AC-C3-3.** `username` checks refuse any URL failing `validate_fetch_url`, including mid-redirect (test: httpx mock asserting the hook fires per hop).
- **AC-C3-4.** Any future provider module refuses to run without a recorded `terms_reviewed_at` for that provider (test: unit test over the catalogue).
- **AC-C3-5.** Every outbound request appends an `AnalysisEvent` with `action="net.fetch"`; `tracefield report` counts them. Test: integration test.

---

## C4. Image/Video/Document Forensics Analyst

**Mandate simulated:** metadata extraction, stream inspection, OCR limitations, perceptual duplicates, file signatures, timestamps, GPS sensitivity, evidentiary limitations. Files: `fieldtools/inspect.py`, `fieldtools/ocr.py` (plus the evidence path in `core/provenance.py` that consumes them).

### C4.1 Assessment of the current field tools

What is done well:

- Content-signature detection instead of extension trust (`fieldtools/inspect.py:57-87`) — right instinct.
- Explicit two-level honesty: `--deep` asks for optional backends and reports `UNAVAILABLE` rather than faking (`fieldtools/inspect.py:259-290`); `doctor` surfaces the same (`cli/main.py:154-167`).
- `run_backend` uses argv arrays, no shell, sanitized env, timeout, and output caps (`fieldtools/inspect.py:136-160`). Solid.
- Caveats embedded in results (`fieldtools/inspect.py:244-250`) correctly state that metadata can be stripped/fabricated and that filesystem times are local-filesystem facts.
- OCR output is labelled machine-derived with a re-check warning (`fieldtools/ocr.py:45-48`), and PDF OCR honestly reports unimplemented (`fieldtools/ocr.py:66-75`).

Gaps and defects (all [R-check] executed unless noted):

1. **Signature false positives.** `_MAGIC` contains `(b"BM", "image/bmp")` (`fieldtools/inspect.py:32`); any text file beginning with the letters BM is classified `image/bmp` before the text heuristic can run. [R-check] A two-line text note starting "BM" → `image/bmp`. No extension-vs-content mismatch warning is emitted when they disagree (`inspect_file` reports both fields at `:236-237` but never compares them).
2. **JSON detection inconsistent.** [R-check] A short `{"a":1}` → `application/json`; a >512-byte pretty JSON file → `text/plain` (the head window at `:78-83` can't parse a truncated object). The `+ "0" * 0` no-op at `:78` is a code smell indicating this path was not fixture-tested.
3. **Timestamp semantics under-specified.** `_fs_times` reports `ctime` (`fieldtools/inspect.py:129`) — on Linux this is *inode change* time, not creation; the generic caveat (`:248-249`) does not say so. Analysts routinely misread ctime as creation time.
4. **GPS warning leaks the coordinates it warns about.** [R-check] `find_gps` (`fieldtools/inspect.py:222-228`) matches any key containing `gps` plus a `location` substring; the SENSITIVE warning then **embeds up to five raw `key=value` pairs** (`fieldtools/inspect.py:270-275`). `inspect --deep photo.jpg 2>&1 | tee log.txt` writes precise coordinates into a file that will later be shared. The JSON output path (`:299-300`) prints full `embedded_metadata` including GPS with no redaction option.
5. **Personal-data (non-GPS) metadata is unflagged.** `EXIF:Artist`, `XMP:Creator`, `MakerNote`, device serials, and faces-adjacent fields are not detected; the only sensitive-class detection is GPS + secret-shaped strings (`redact_secrets_json`, `fieldtools/inspect.py:205-212`). [R-check] `EXIF:Artist="Jane Doe"` passes through untouched.
6. **Silent redaction alters evidentiary values without disclosure.** Both `exiftool_metadata` and `ffprobe_streams` pipe results through `redact_secrets_json` (`fieldtools/inspect.py:182,200`), and OCR text through `redact_secrets` (`fieldtools/ocr.py:36`), but **none of the outputs record that redaction occurred or how many values changed.** An analyst quoting OCR'd text of a leaked-credentials document would quote `[REDACTED]` as if it were the pixels. (The redactor itself is also buggy — see C5 [R-check] `password:` mangling.)
7. **OCR has no confidence channel.** `ocr_image` returns raw text only (`fieldtools/ocr.py:21-36`); Tesseract's TSV/`tsv` config exposes per-word confidence that is discarded. Since `contradictions.py` extracts dates and hashes from *text*, an OCR misread (`2024-01-02` → `2024-l0-02`) can silently suppress or fabricate a structured contradiction, and nothing in the pipeline marks that text as OCR-derived. (Contradiction detection is currently unwired — section 0 — so this is a latent, not active, defect.)
8. **No perceptual hashing.** `inspect_file` computes sha256/sha512/md5 (`fieldtools/inspect.py:252-257`) — byte-level only. There is no pHash/dHash/aHash, so a re-encoded, re-compressed, or screenshot-of-a-screen image is an unrelated object for the tool, even though perceptual duplicates are the bread and butter of image verification. The word "perceptual" appears nowhere in the codebase.
9. **No stream-level tamper signals.** `ffprobe_streams` output is stored raw (`fieldtools/inspect.py:279-288`); nothing flags duration/codec inconsistencies, multiple audio tracks, or MP4 `moov` relocation, and the dead `_MAGIC` entry for MP4 (`:48`, exact `\x00\x00\x00\x1cftyp`) is superseded by the `ftyp` check at `:62-66`.
10. **Argument-injection hygiene is inconsistent.** `exiftool`/`ffprobe` calls pass `--` before the path (`fieldtools/inspect.py:168,190-191`); `tesseract` does not (`fieldtools/ocr.py:22`). A file named like an option (`-c`, `--psm`) or a Tesseract *config word* (`digits`, `hocr`) can change tool behavior. Severity is low (path is positional argument #1) but the project's own convention is `--`.
11. **Whole-file reads in the evidence path.** `CaseWorkspace.attach_file` uses `src.read_bytes()` (`core/provenance.py:86`) after hashing in chunks (`:28-34`) — a multi-GB video will be buffered entirely in RAM while `hash_file` was carefully streamed. Inconsistent and a field-laptop failure waiting to happen.
12. **Evidentiary linkage gap.** Neither `inspect` nor `ocr` writes an `Observation` or an event (`core/provenance.py:139-154` is only called from attach paths). A screenshot of the inspect output is currently the only way to bind tool results to a case — which is exactly the manual step this tool exists to eliminate.

### C4.2 Field-tool gap spec (prioritized)

| ID | Gap | Priority | Target module |
|---|---|---|---|
| G-C4-1 | GPS/PII values must not be echoed in warnings or JSON by default; print `GPSLatitude=[present]` and require `--show-gps` | P0 | `inspect.py` |
| G-C4-2 | Disclose redaction: every redacting transform returns `(value, n_redacted)`; results carry `redactions_applied: int` | P0 | `inspect.py`, `ocr.py` |
| G-C4-3 | Extension-vs-detected-type mismatch warning | P1 | `inspect.py` |
| G-C4-4 | Timestamp labels: `ctime (inode change, not creation)`, `birthtime (where supported)` | P1 | `inspect.py` |
| G-C4-5 | Perceptual hash (pHash, 64-bit) for images; store beside byte hashes; surface `similar_to` suggestions | P1 | new `fieldtools/perceptual.py` |
| G-C4-6 | OCR confidence: emit TSV parse with mean/median word confidence; attach `derived_from_ocr: true` to any downstream text | P1 | `ocr.py` |
| G-C4-7 | PII field detection beyond GPS (Artist/Creator/Owner/serial/email regex) with the same warning channel | P1 | `inspect.py` |
| G-C4-8 | `--` before path for tesseract (verify Tesseract ≥5 accepts it; if not, reject paths starting with `-`) | P2 | `ocr.py` |
| G-C4-9 | Stream chunked copy in `attach_file` (mirror `hash_file` streaming) | P2 | `provenance.py` |
| G-C4-10 | Persist `inspect`/`ocr` results as `Observation` rows + `AnalysisEvent`s when `--case` is supplied | P2 | `cli/main.py`, `fieldtools/*` |

### C4.3 Fixture set specification (for the currently empty `tests/`)

All fixtures synthetic; no real personal data; ship under `tests/fixtures/fieldtools/`.

| Fixture | Construction | Expected assertions |
|---|---|---|
| `png_1x1.png` | Minimal valid PNG | `detect_media_type` → `image/png`; sha256 matches golden value |
| `png_with_gps.jpg` | JPEG built with piexif: GPS IFD `GPSLatitude=51.5074N`, `GPSLongitude=0.1278W`, `EXIF:Artist=Synthetic Analyst` | `find_gps` finds ≥2 keys; **warning text does not contain `51.5074`** (G-C4-1); JSON mode redacts GPS values; Artist flagged under G-C4-7 |
| `text_starting_BM.txt` | ASCII text beginning `BM notes…` | `detect_media_type` ≠ `image/bmp` (regression for FM-C4-1) |
| `json_short.json` / `json_long.json` | Same schema, 20 B vs 64 kB | Both → `application/json` |
| `docx_minimal.docx` | ZIP with `[Content_Types].xml` | → `application/zip` **and** a `possible_docx_container` note (today: silent `application/zip`; add note under G-C4-3) |
| `pdf_two_page.pdf` | Two blank pages with embedded text | `ocr` → status `UNAVAILABLE` with the honest PDF message (`fieldtools/ocr.py:66-75`) |
| `image_reencode_a.png` / `image_reencode_b.jpg` | Same synthetic image, re-encoded | Byte hashes differ; pHash distance ≤ threshold (G-C4-5) |
| `image_screenshot_of_a.png` | `image_reencode_a` rendered at 50% scale to a new raster | pHash distance ≤ threshold; documents the intended tolerance |
| `mp4_two_streams.mp4` | ffmpeg-generated clip, one video + one audio | `ffprobe_streams` returns 2 streams; status `ok` |
| `ocr_confident.png` / `ocr_noisy.png` | Rendered 24 pt text vs same text at 6 pt with noise | Confidence channel separates them (G-C4-6); noisy case mean confidence below documented threshold |
| `ocr_digits_confusable.png` | Rendered `2024-01-02` in a font where `1`/`l` confuse at low res | Downstream `find_contradictions` on OCR text must be suppressed when `derived_from_ocr` and confidence < threshold (documents the latent defect in §C4.1-7) |
| `secret_bearing_metadata.json` | exiftool JSON with `Comment: api_key=…`, `password: hunter2`, `Cookie: a=b; c=d` | Redaction count reported (G-C4-2); **no `[REDACTED]word` mangling** (regression, see C5 FM-C5-2); both cookies redacted |
| `zip_bomb_small.zip` | Highly compressible zip, decompressed size > 1 GB | `detect_media_type` safe; `attach_file` refuses or streams with size guard (documents G-C4-9) |
| `unicode_filenames/` | Files with RTL/CJK/emoji names | `sanitize_for_terminal` output renders without escape/overturn (`security/sanitize.py:21-31`) |

### C4.4 Risks

- **R-C4-1 (High).** GPS coordinates leak into terminal scrollback and logs via the warning text itself (`fieldtools/inspect.py:270-275`) — the exact class of accident that turns an OSINT case file into a personal-safety incident (see C5).
- **R-C4-2 (High).** Silent redaction + no confidence channels means the tool can produce *text that looks verbatim but is not* — the worst failure mode for an evidentiary workbench.
- **R-C4-3 (Medium).** No perceptual hashing ⇒ image duplicate analysis, one of the two or three highest-value forensic field operations, is simply absent.
- **R-C4-4 (Medium).** Signature table false positives (`BM`) with no mismatch warning can mislabel exhibit types in a report.
- **R-C4-5 (Low).** Tool outputs are ephemeral (no `Observation`), so field findings cannot be cited with provenance.

### C4.5 Challenged assumption

**Challenged:** "Content-signature type detection … never executes file content" (`fieldtools/inspect.py:57-58,232`) is presented as sufficient safety for untrusted exhibits. **Counter:** the real forensic risk in this module is not code execution — it is *mislabelling* (BM/JSON cases above) and *silent transformation* (redaction of metadata/OCR text without disclosure). A tool that never executes content but quietly edits values still fails the evidentiary standard, because the analyst's quote stops matching the exhibit.

### C4.6 Recommendations

Implement the gap spec in G-C4-1…G-C4-10, in that order; adopt the fixture set as the acceptance suite for `fieldtools/`; add a golden-file test for `inspect --deep --json` with the GPS fixture asserting **no coordinate substrings** anywhere in the output.

### C4.7 Open questions

- Q-C4-1. Should `inspect --deep` ever persist its JSON into the case store automatically, or only via explicit `evidence attach`? (My position: explicit, with an `--attach` flag that writes an `Observation` + event.)
- Q-C4-2. What pHash library is acceptable dependency-wise given the project currently has five runtime deps (`pyproject.toml`)? A pure-Python pHash on small images may be acceptable; a numpy/opencv dependency likely is not.
- Q-C4-3. Is video frame extraction in scope for P1? (It would require ffmpeg *decoding*, not just probing — an active parsing step on hostile input with a much larger attack surface.)

### C4.8 Testable acceptance criteria

- **AC-C4-1.** `inspect --deep --json` on `png_with_gps.jpg` produces output containing no `51.5074`/`0.1278` substrings; coordinates appear only under an explicit `--show-gps` flag. Test: security regression test.
- **AC-C4-2.** Every redacting path reports `redactions_applied ≥ 1` when it changed anything; OCR output carries `redactions_applied` and `derived_from_ocr: true`. Test: unit tests on `ocr_image` and `exiftool_metadata`.
- **AC-C4-3.** `text_starting_BM.txt` is not classified as `image/bmp`; a `.jpg` that is actually a PNG produces a `type_mismatch` warning. Test: fixture tests.
- **AC-C4-4.** `ctime` is rendered with its Linux semantics in human output. Test: string assertion.
- **AC-C4-5.** `image_reencode_b.jpg` is reported as perceptually similar to `image_reencode_a.png` at the documented threshold; a visually unrelated image is not. Test: fixture test.
- **AC-C4-6.** A file named `-c` or `digits` cannot alter tesseract's argument parsing. Test: CLI test asserting ERROR (not unexpected success) and no option injection.

---

## C5. Privacy, Rights & Responsible Research Reviewer

**Mandate simulated:** proportionality, personal-data minimization, retention/deletion, sensitive GPS exposure, third-party leakage, legal/ethical disclaimers, misuse risk. Files: `config/settings.py`, `security/redact.py`, `reporting/export.py`, plus the storage/CLI surfaces they govern.

### C5.1 Privacy defaults assessment

| Control | Declared | Implemented? | Evidence |
|---|---|---|---|
| Network off by default | `Settings.allow_network=False` (`config/settings.py:43`) | **Yes** — enforced in `source add --fetch` with exit code 4 (`cli/main.py:360-365`) | Good |
| Username checks opt-in | `username_check_enabled=False` (`config/settings.py:44`) | **No consumer** — `check_username` has no CLI command; the flag is read and never used | Dead control |
| Redact exports | `redact_exports=True` (`config/settings.py:48`) | **No** — the flag is never read; redaction is controlled only by the CLI `--redact/--no-redact` option (`reporting/export.py:24`, `cli/main.py:708-710`) | Dead setting |
| Strip precise GPS on export | `strip_precise_gps_on_export=True` (`config/settings.py:49`) | **No — not implemented anywhere.** The only GPS code in the tree is detection (`fieldtools/inspect.py:215-228`). `export_case`'s comment claims "Redact GPS-bearing metadata files" (`reporting/export.py:38`) but the loop applies `redact_secrets`, which matches token/cookie/API-key shapes only (`security/redact.py:12-32`). [R-check] JPEG EXIF GPS is untouched; and binary images are skipped entirely by the UTF-8 decode (`reporting/export.py:41-44`) | **Critical gap** |
| CLI help promise | `--redact` help: "Redact secrets and precise GPS." (`cli/main.py:709`) | **False advertising** — precise GPS is never redacted on any path | Critical |
| Immutable evidence | `chmod 0o400` (`core/provenance.py:87,117`) | Partial — mode is set on create; export copies preserve mode, but see FM-C5-1 for in-place mutation | Mixed |
| Data-at-rest protection | — | **None.** [R-check] SQLite creates `tracefield.sqlite3` with mode `0644` and `mkdir` uses default umask → directories `0755` (`config/settings.py:59-61`, `core/provenance.py:57-60`). On a shared machine, every other local user can read case titles, source locators, claim text, and evidence metadata; evidence *bytes* are 0o400 but the DB is not | High |
| Retention | `Case.retention_policy` ("default"), `EvidenceItem.retention_status` ("retained") (`core/domain.py:109,141`) | **No enforcement, no purge job, no expiry check, no CLI to change either field.** "Retention" is two unchanging strings | Medium |
| Deletion | `case-delete --yes` cascades rows (`storage/repositories.py:173-175` + FK cascade, `storage/database.py:211`) and `rmtree`s the case dir (`cli/main.py:746-751`) | Yes for live data; the CLI correctly warns exports survive (`cli/main.py:755-758`). No WAL/backup purging; no secure-erase (acceptable if documented) | Adequate with caveats |
| Third-party leakage on fetch | Fetch is direct, single-GET, `trust_env=False` | Yes; but the fetched page's *content* is discarded while its digest lands in `limitations` (`fieldtools/fetch.py:98-107`), which is then exported in reports — low risk | Adequate |
| Report redaction | — | **Inconsistent.** `case-export --redact` redacts; `tracefield report -o out.md` never redacts (`cli/main.py:694-696` → `build_report` has no redaction). Same case, two commands, different leakage | Medium |

### C5.2 Risks (risk register)

| ID | Risk | Likelihood | Impact | Notes |
|---|---|---|---|---|
| **RK-1** | Precise GPS from field photos leaks into exports and (via inspect warnings/JSON) into terminal logs | High | High — physical safety of subjects/analysts | `strip_precise_gps_on_export` is a placebo; `--redact` help lies |
| **RK-2** | Redaction *edits exported evidence bytes in place*, breaking the content-addressed integrity guarantee | Medium | High — evidentiary credibility | See FM-C5-1 |
| **RK-3** | World-readable case DB (`0644`) on shared hosts | Medium | Medium | No `umask`/`chmod` in `ensure_dirs` |
| **RK-4** | Redaction bugs silently corrupt or partially redact text: `password: hunter2` → `password: [REDACTED]word`; `Cookie: a=b; c=d` leaves `c=d`; `access_token=`, `?sig=`, `?key=` untouched | High (all [R-check]) | Medium | Wrong redaction is worse than none: it *looks* safe |
| **RK-5** | Absolute local paths in reports/events reveal usernames and investigation folder structure | High | Low-Medium | `cli/main.py:536`, `core/provenance.py:100` |
| **RK-6** | No retention enforcement ⇒ indefinite accumulation of personal data in case stores | High | Medium | Also a legal-posture problem for GDPR-style storage limitation |
| **RK-7** | `privacy_label` exists (`core/domain.py:140`) but no CLI sets it, no report renders it, no export filters on it | High | Medium | Personal/sensitive data is never *marked*, so proportionality review is impossible |
| **RK-8** | Third-party disclosure via future CTI integrations (VT/urlscan sharing submissions) | Medium (future) | High | See C3 shortlist caveats; needs a standing warning in docs |
| **RK-9** | Misuse: the toolchain (username existence checks, photo GPS, syndication analysis) is coherent for accountability journalism and equally coherent for stalking/doxxing | Medium | High | No misuse deterrents beyond text caveats (`fieldtools/username.py:266-274` — good text, no structural friction beyond opt-in and no bulk mode) |
| **RK-10** | `case-export` with `dirs_exist_ok=True` (`reporting/export.py:30`) merges into an existing directory, potentially mixing two cases' evidence in one "bundle" | Low | Medium | Cross-case contamination of an export is an integrity and a privacy event |

### C5.3 Concrete failure modes

- **FM-C5-1.** Analyst exports a case containing one text evidence file that mentions `api_key=…`. `export_case` builds `manifest.json` from stored digests (`reporting/export.py:31`), **then** rewrites that evidence file in place with `redact_secrets` (`reporting/export.py:39-47`). The exported file's bytes no longer match its manifest entry or its content-addressed filename (`evidence/<sha2>/<sha256>`). Anyone running `verify_manifest` (`reporting/export.py:65-82`) gets "digest mismatch" on a file TRACEFIELD itself modified — and the export README simultaneously claims evidence copies are "immutable" (`reporting/export.py:55`). Either verification fails (integrity theatre) or analysts learn to ignore verification failures (worse).
- **FM-C5-2.** [R-check] `redact_secrets("password: hunter2")` → `"password: [REDACTED]word"` (group-index bug at `security/redact.py:39-40`: pattern 6 has two groups, so `\g<2>` re-appends the literal `word`). The same loop leaves `access_token=SECRETTOKEN123` and `?sig=abcd` in cleartext, and only the first cookie of a multi-cookie header. An analyst who tests redaction once on `password:` will *believe* redaction works, and it will still miss the token forms that actually appear in URL parameters.
- **FM-C5-3.** Field analyst photographs a site visit with a phone that geotags images; attaches 40 photos via `evidence attach` (privacy_label stays `"unknown"`, RK-7); runs `case-export` with default `--redact`; sends the bundle to an editor. Precise coordinates of a sensitive location travel to a third party, and the CLI told the analyst GPS was redacted (`cli/main.py:709`).

### C5.4 Challenged assumption

**Challenged:** "Defaults are privacy-preserving" (`config/settings.py:39`). **Counter:** the *network* defaults are genuinely conservative; the *data-at-rest* and *export* defaults are not. A default that creates a world-readable database, ships two never-read privacy settings, and advertises GPS redaction it does not perform is not privacy-preserving — it is privacy-theatrical. The distinction matters because users calibrate trust to the settings panel they can see, not to the code they cannot.

### C5.5 Recommendations

1. **P0 — make GPS stripping real.** Implement coordinate stripping for (a) exported text/JSON evidence, (b) image binaries via metadata rewrite (exiftool `-all:all=` or GPS-only removal) into a *derived* redacted copy — never mutating the original hash-named object (see RK-2). Until then, change the `--redact` help text and `Settings` docstring to say precisely what is and is not redacted.
2. **P0 — never mutate exported evidence.** Redaction must write `evidence_redacted/<sha2>/<sha256>` (new digests, new manifest section) or be dropped for binaries entirely.
3. **P0 — fix `redact_secrets`:** correct the `\g<2>` bug, cover `access_token`/`sig`/`key`/`auth` URL parameters, multi-cookie values, and add a self-test command (`tracefield doctor --redact-selftest`) so analysts can verify the redactor.
4. **P0 — file modes.** `ensure_dirs` → `mkdir(mode=0o700)`; after `Database` creation, `chmod 0o600` on the DB file (and WAL/SHM siblings). Document multi-user threat model.
5. **P1 — wire the dead settings or delete them.** `redact_exports` and `strip_precise_gps_on_export` must be read by `export_case`, or removed to avoid a false sense of control. Same for `username_check_enabled` once the CLI command exists.
6. **P1 — make `privacy_label` operational:** `evidence attach --privacy public|sensitive|personal|unknown`; report renders the label per evidence item; `case-export` refuses `personal`-labelled items unless `--include-personal` is passed, and prints a count of what was withheld.
7. **P1 — retention that does something:** `tracefield case purge --older-than 90d` honouring `retention_policy`; a doctor check warning about cases older than the policy; document that deletion is not secure erase.
8. **P1 — consistent redaction surface:** `report` should accept `--redact` (default on when writing to a file, off on a TTY) or document the asymmetry with `case-export`.
9. **P2 — path minimization:** store case-local relative references in events; render `<local-path>` in reports by default (aligns with AC-C1-5).
10. **P2 — misuse friction, proportionality, and rights:** ship a `docs/ethics.md` covering: purpose limitation (the case `purpose` field should be mandatory before collection), a do-not-use list (stalking, targeting of private individuals' home locations, unverified accusation), subject-access/correction handling (the retraction workflow from C1 doubles as a correction mechanism), and a standing warning that GPS and username-existence data are safety-sensitive. Add a first-run line: "Do not use TRACEFIELD to track people who are not part of a documented public-interest investigation."
11. **P2 — export hygiene:** refuse `output` directories that already exist and are non-empty (or require `--force`), and refuse output paths inside `data_root`/`cases_root`.

### C5.6 Open questions

- Q-C5-1. Is TRACEFIELD intended for individual journalists, newsroom teams, or NGO investigators? Multi-user deployments make RK-3 (world-readable DB) and RK-10 (export mixing) materially worse.
- Q-C5-2. Should precise GPS be *stored at all* by default, with a "coarsen to city/region on attach" option, rather than being handled only at export time? (My position: yes — minimization at collection beats redaction at egress.)
- Q-C5-3. What is the intended answer to a subject-access request against a case store? Today: impossible to service systematically (no search-by-subject field exists).

### C5.7 Testable acceptance criteria

- **AC-C5-1.** A case exported with default flags contains zero occurrences of any GPS coordinate present in the source evidence (binary and text), and `verify_manifest` passes on the export afterwards. Test: end-to-end export test with the `png_with_gps.jpg` fixture + a text evidence fixture containing coordinates.
- **AC-C5-2.** No export path ever modifies a file under the original `evidence/<sha2>/<sha256>` tree; redacted derivatives live in a separate subtree with their own manifest entries. Test: file-mtime/digest assertions before and after export.
- **AC-C5-3.** `redact_secrets` self-test vector set passes: `password: x`, `passwd=`, `?access_token=`, `?sig=`, `Cookie: a=1; b=2`, JWT, AWS key, `scheme://user:pass@host`, and **no** `word` suffix artifacts. Test: unit test table.
- **AC-C5-4.** Fresh `tracefield init` produces data root `0700` and DB `0600`; `doctor` reports the current modes and flags world-readable ones. Test: filesystem-mode test (security marker).
- **AC-C5-5.** `evidence attach --privacy personal` on a case, then `case-export` without `--include-personal`, excludes that evidence binary and its excerpt from the bundle and reports "withheld N personal-labelled items". Test: CLI integration test.
- **AC-C5-6.** `tracefield report -o file` applies the same redaction defaults as `case-export --redact`. Test: parity test on both outputs with a secret-bearing claim text.
- **AC-C5-7.** Settings self-consistency: no privacy-related field in `Settings` is unread at runtime (grep-based lint test in CI).

---

## Consolidated priorities for the maintainers

| Priority | Item | Roles |
|---|---|---|
| **P0** | Ship the relation/review/cluster/observation commands so the assessment engine is reachable at all (section 0) | C1, C2 |
| **P0** | Make origin clusters affect `assess_claim` outcomes (replace scalar `origin_clusters`) | C2 |
| **P0** | Implement or honestly de-advertise GPS stripping on export; stop mutating exported evidence | C5, C4 |
| **P0** | Fix `redact_secrets` group bug + URL-parameter coverage; disclose redaction in all outputs | C5, C4 |
| **P0** | Tighten data-at-rest file modes (DB 0600, dirs 0700) | C5 |
| **P0** | Scope/authorization gate + DNS-pinning for network paths | C3 |
| **P1** | Fix shingle representation (ordered, Unicode-aware) and add entity/number channel | C2 |
| **P1** | Report metadata: generated_at, version, author, assertions section, corrections section, timeline | C1 |
| **P1** | Perceptual hashing + OCR confidence + redaction disclosure in field tools | C4 |
| **P1** | Operationalize `privacy_label` and retention; consistent redaction between `report` and `case-export` | C5 |
| **P2** | Fix TUI-advertised nonexistent commands; UA string; path minimization; export hygiene; ethics doc | All |

## Web sources consulted (retrieved 2026-10-16 via web search; re-verify before integration)

1. urlscan.io scanning API (visibility defaults, `overrideSafety`): https://docs.urlscan.io/apis/urlscan-openapi/scanning — accessed 2026-10-16
2. urlscan.io Search API reference: https://api.urlscan.io/docs/search and https://docs.urlscan.io/apis/urlscan-openapi/search — accessed 2026-10-16
3. urlscan.io Terms of Service (rate limits, no-circumvention): https://api.urlscan.io/terms — accessed 2026-10-16
4. RDAP bootstrap registry (IANA): https://www.iana.org/assignments/rdap-dns/rdap-dns.xhtml (linked from ICANN RDAP Technical Implementation Guide, https://itp.cdn.icann.org/en/files/registry-operators/rdap-technical-implementation-guide-21feb24-en.pdf) — accessed 2026-10-16
5. rdap.org bootstrap service (rate limit and privacy notes): https://rdap.org/ — accessed 2026-10-16
6. ICANN registration data lookup tool (RDAP + WHOIS failover terms): https://lookup.icann.org/ — accessed 2026-10-16
7. RFC 9537, Redacted Fields in RDAP Responses: https://www.rfc-editor.org/rfc/rfc9537 — accessed 2026-10-16
8. crt.sh Certificate Search: https://crt.sh/ — accessed 2026-10-16
9. SSLMate Cert Spotter (CT monitoring + search API): https://sslmate.com/certspotter and https://sslmate.com/ct_search_api — accessed 2026-10-16
10. Censys API docs (tiers, credits): https://docs.censys.com/reference/get-started — accessed 2026-10-16
11. Censys Terms and Conditions: https://censys.com/terms-and-conditions — accessed 2026-10-16
12. Censys scanning/data-collection description: https://about.censys.io/ — accessed 2026-10-16
13. Shodan Terms of Service: https://static.shodan.io/legal/terms.html — accessed 2026-10-16
14. VirusTotal "How it works" (sharing of submissions): https://docs.virustotal.com/docs/how-it-works — accessed 2026-10-16
15. VirusTotal API v3 overview (report-by-hash vs upload): https://developers.virustotal.com/v3.0/reference — accessed 2026-10-16

Anything referenced above that was **not** confirmed from a retrieved page (current exact rate limits for crt.sh, Cert Spotter API pricing/quotas, VirusTotal's current public-API limits, resolver no-log claims) is marked **unknown** and must be re-verified at integration time.

## Standing disclaimer

This document is a role-simulated analytical review produced by independent review subagents. The "analyst" perspectives (investigative journalism, source evaluation, CTI, digital forensics, privacy review) are lenses derived from publicly available methods, checklists, and standards — they are not interviews with, or endorsements by, real intelligence professionals, newsrooms, or legal counsel. Nothing here is legal advice; jurisdiction-specific obligations (data protection, archive law, platform ToS) must be assessed for the actual deployment context.
