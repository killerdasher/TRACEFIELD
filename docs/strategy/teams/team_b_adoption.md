# TEAM B — Differentiation, Adoption, GitHub

> Simulated role-based review conducted by independent review subagents on 2026-10-16. These are role perspectives, not interviews with real people. External facts were verified via live web checks on this date where marked.

**Scope of this file.** Team B covers competitive position, catalogue/ecosystem strategy, developer
experience and docs, terminal brand systems, and maintainer/community sustainability. Team B does
**not** review algorithm internals, storage schema, or security exploit surface (Teams A/C/D).

**How to read claims.**
- `[V]` = verified by me on 2026-10-16 (HTTP fetch or local command execution). URL + method in the
  Verification Log (Appendix A).
- `[U]` = unknown / could not be verified in this pass. Never treat `[U]` as "no".
- Star counts are GitHub REST API `stargazers_count` observed 2026-10-16 ~19:02–19:05 UTC; they change
  continuously and must never be re-quoted without a re-check date.
- Last-activity values are GitHub API `pushed_at` (last push recorded for the repository), not release
  dates, unless stated otherwise.

**Local baseline used throughout** (verified by reading the working tree at
`/home/dasher/Desktop/github/TRACEFIELD` and executing the installed CLI into a scratch data root
`TRACEFIELD_HOME=/tmp/opencode/tfhome`):
- Implemented commands (read from `src/tracefield/cli/main.py` and confirmed in `tracefield --help`):
  `doctor`, `init`, `hash`, `inspect`, `ocr`, `report`, `case-export`, `case-delete`, `tui`,
  `case create|list|show`, `source add|list`, `claim add|list`, `evidence attach|list|verify`.
- `tools status` is advertised in `README.md` as "(planned)"; it does **not** exist in the CLI, and
  `data/catalog/tools.jsonl` does not exist (`data/` is empty). `[V]`
- Repo hygiene as of review time: `git log` fails ("your current branch 'main' does not have any
  commits yet"), `tests/` is empty, `.github/workflows/` is empty, `docs/` was empty before this file,
  and `CONTRIBUTING.md` / `SECURITY.md` — both linked from `README.md` — are absent. `[V]`

---

## B1. Competitive Intelligence Reviewer

### B1.1 Method

Live GitHub REST API repo metadata (license, `pushed_at`, stars, archived, open issues), raw LICENSE
and README files, plus the product sites for the two non-code indexes. Everything in the matrix is a
direct quote-level fact from those sources. Where GitHub's license detection and the actual license
text disagree, both are recorded — that disagreement is itself a catalogue-quality lesson for B2.

### B1.2 Dated competitor matrix (all rows checked 2026-10-16)

| Tool | License (SPDX, as verified) | Last activity (`pushed_at`) | Stars @ 2026-10-16 | Free / keyless status | Key capabilities (verified only) |
|---|---|---|---|---|---|
| **Sherlock** (`sherlock-project/sherlock`) | MIT (LICENSE file text verified) | 2026-10-16T05:17:06Z | 94,272 | Free & open-source; API-key requirements not stated in README → keyless **[U]** | Username hunting across "400+ social networks" (site claim quoted in repo docs); install via pipx/docker/dnf; README warns third-party ParrotOS/Ubuntu 24.04 packages "appear to be broken" |
| **Maigret** (`soxoj/maigret`) | MIT (LICENSE: "Copyright (c) 2020-2026 Soxoj") | 2026-10-14T16:10:52Z | 39,142 | Free; README states **"No API keys required"** | Dossier-by-username across a large site set, page-data collection, readthedocs docs, PyPI distribution, sponsor/ads sections for commercial OSINT platforms |
| **SpiderFoot** (`smicallef/spiderfoot`) | MIT (LICENSE verified) | 2026-04-13T19:43:06Z | 23,543 | Free self-hosted; **some modules need API keys** (README lists "API key export/import"); SpiderFoot HX is the paid cloud | Web UI **and** CLI, "over 200 modules", YAML correlation engine with 37 predefined rules, SQLite backend, CSV/JSON/GEXF export, TOR integration, can shell out to DNSTwist/WhatWeb/Nmap/CMSeeK |
| **theHarvester** (`laramies/theHarvester`) | GPL-2.0 (LICENSE: "Version 2, June 1991") | 2026-10-14T05:13:58Z | 17,981 | Free; README: some "P0 passive sources … need no API key" | Harvests emails/subdomains/hosts/IPs/ASNs from search engines, CT logs, DNS datasets, code repos, TI platforms; CLI + **HarvestView** local run-history/evidence-review UI + local REST API; **requires Python 3.14 + `uv`** |
| **holehe** (`megadose/holehe`) | GPL-3.0 (LICENSE.md verified) | 2024-09-10T20:24:32Z | 15,219 | Free | Checks which sites an email address is registered on; last push is >2 years before this review (maintenance status: quiet) |
| **ExifTool** (exiftool.org; GitHub mirror `exiftool/exiftool`) | Upstream site: "same terms as **Perl itself**" (Artistic/GPL dual). GitHub API on the mirror: GPL-3.0. **Discrepancy recorded** | Mirror `pushed_at` 2026-05-27T16:45:01Z; upstream release **13.59 (May 27, 2026)** | 5,169 (mirror) | Free, keyless, offline | Reads/writes/edits metadata for a very large format set, JSON output (`-json`), geolocation DB, metadata diff, **generates MD5/SHA256/SHA512 of image data**, C2PA/JUMBF read |
| **OSINT Framework** (`lockfale/OSINT-Framework`; site osintframework.com) | MIT (LICENSE: "Copyright (c) 2017 Justin Nordine") | 2026-10-10T14:48:55Z | 12,292 | Free web index, keyless | D3 tree of free OSINT resources; site features **OPSEC notes, community star ratings, and dead-link/paywall/incorrect-info reporting**; legend marks install-locally (`T`), Google dork (`D`), registration (`R`), manual URL (`M`) |
| **Bellingcat Online Investigation Toolkit** (`bellingcat/toolkit`; site bellingcat.com/toolkit → bellingcat.gitbook.io/toolkit) | **No license file detected at repo root** → redistribution terms `[U]` | 2026-10-08T05:36:45Z | 682 | Free to read; per-tool cost field exists (Free / Partially Free / Paid) | GitBook-sourced tool reviews; **337 tool pages, 59 category pages** `[V]`; CSV download offered; "Bellingcat staff checks each toolkit entry before it goes online"; explicit disclaimer: "Inclusion in the toolkit does not imply that Bellingcat endorses or recommends a specific tool" |
| **Awesome OSINT** (`jivoi/awesome-osint`) | GitHub API: **NOASSERTION**; repo `LICENSE.txt` text: **CC BY-SA 4.0**. Both verified — the API answer alone is misleading | 2026-10-15T06:51:52Z | 30,275 | Free list, keyless | Curated markdown list: **1,527 list items, 1,473 http(s) links, 1,437 unique raw URLs, 78 headings** `[V]`; 0 open issues at check time |
| **WhatsMyName** (`WebBreacher/WhatsMyName`) | GitHub API: NOASSERTION; `LICENSE.md` text: **CC BY-SA 4.0**, "Copyright (C) 2015-2026 Micah Hoffman" | 2026-10-15T14:55:30Z | 2,952 | Free | Curated site list + detection patterns for username enumeration; web app whatsmyname.app returned **HTTP 403 to my automated fetch** (bot filtering; human reachability `[U]`) |
| **IntelX** (intelx.io) | `[U]` (not verified) | `[U]` | n/a (not a repo I verified) | `[U]` | Site reachable (HTTP 200). Everything else `[U]` in this pass |
| **namechk.com** | `[U]` | `[U]` | n/a | `[U]` | Site returned **HTTP 403** to automated fetch. A third-party mirror `GONZOsint/Namechk` exists: 616 stars, last push 2021-03-23, license `[U]` — relationship to the live site `[U]` |

### B1.3 Capability overlap with TRACEFIELD's **implemented** surface

Only implemented commands are compared (planned features are marked as such). "Overlap" means the
competitor already does the thing; it is not a criticism, it is a warning against claiming novelty.

| TRACEFIELD implemented capability | Already done by | What they have that we do not | What we have that they do not (as far as this pass verified) |
|---|---|---|---|
| `hash <file>` (sha256 default; sha256+sha512 in `inspect`) | ExifTool (MD5/SHA256/SHA512 of image data, verified feature list); coreutils `sha256sum` | ExifTool's hashes are per-image-data semantics, not just file bytes | Hash recorded as an **evidence record bound to a case**, re-verifiable via `evidence verify` |
| `inspect [--deep]` (signature, hashes, mtime, exiftool/ffprobe backends) | ExifTool (far deeper), ffprobe, `file(1)` | Thousands of tags, write support, geotagging, diffing | Honest backend status strings + explicit caveat text ("metadata does not prove authenticity") in the same output |
| `ocr <image>` (local tesseract wrapper) | Any tesseract wrapper; Bellingcat lists verification tooling | Real OCR quality engineering (deskew, languages, psm) | Provenance binding: OCR result stored with `source_sha256` and method `"tesseract-local"` |
| Case lifecycle + claims + evidence with SHA-256 + event digests | SpiderFoot (SQLite scan store, CSV/JSON/GEXF export), theHarvester (HarvestView local run history + "normalized evidence model" + retained findings on partial failure), commercial platforms (Bellingcat's Data Org & Analysis category lists **Atlos**) | Mature collectors with a decade of modules; existing investigator UX | A CLI where **collection is opt-in and every stored artifact carries integrity data and a chain of `prev_digest` events**; "hashes prove bytes, not truth" stated in the product, not a blog post |
| Case export + integrity manifest + redaction | SpiderFoot export (CSV/JSON/GEXF); Bellingcat's toolkit points to archiving tools (Auto Archiver, Archive.today) | Dedicated archiving pipelines | Manifest is a verification contract (`verify_manifest` re-hashes), plus default redaction and GPS-stripping flags |
| Tool catalogue with health states (`indexed/verified/integrated/healthy/stale/unavailable/unverified`) | OSINT Framework (OPSEC notes, community ratings, dead-link reports), Bellingcat (337 reviewed tools, cost + difficulty fields, staff checks), Awesome OSINT (1.4k links) | Human editorial processes TRACEFIELD cannot match at alpha; Bellingcat explicitly refuses unsolicited tool suggestions | Machine-checkable **tiered** states that distinguish *listed* from *verified* from *integrated* from *healthy*, with per-entry `last_checked` |
| Conservative username checks (`fieldtools/username.py`, opt-in, curated providers, no HTTP-200-as-match) | Sherlock (94k stars), Maigret ("No API keys required", huge site set), WhatsMyName, holehe (email-based) | 10–1000× more sites; false-positive engineering over years | Deliberate smallness: soft-404 marker rules, 1 req/s politeness, backoff on 429/403/5xx, and "existence of a public handle is NOT identity attribution" |
| `doctor` (local-only environment check, never network) | — (not a standard feature of the tools I checked) | — | This is a genuine small differentiator; keep it network-free |
| `tui` (Textual) | SpiderFoot web UI, theHarvester HarvestView | Mature GUIs | Optional layer; every feature also has a CLI path |

**Explicitly NOT novel — never market these as innovations:** content hashing, EXIF/ffprobe metadata
reading, tesseract OCR wrapping, "a big list of OSINT tools", username enumeration, case folders,
read-only evidence copies (content-addressed stores are an old pattern: git and other CAS designs),
SQLite storage, JSON output, redaction of secrets.

**Defensible (as implemented today, and only if the bugs in B3 are fixed):** a single local-first CLI
in which (a) network is off by default with a dedicated exit code, (b) every finding is re-verifiable
from the case directory without the tool, (c) catalogue claims are tiered and dated, and (d) output
routinely states what a number does *not* prove.

### B1.4 Differentiation thesis (one paragraph, usable verbatim in the README)

> TRACEFIELD is not a collector and not another list. It is the **provenance and continuity layer
> between collection and the report**: you keep using Sherlock, Maigret, SpiderFoot, ExifTool and the
> Bellingcat toolkit — TRACEFIELD stores what they produced as hash-addressed, re-verifiable evidence
> under a scoped case, records the chain of actions, refuses to grade truth as a probability, and
> exports a bundle whose integrity anyone can re-check with `sha256sum`. Its catalogue's honesty is
> that it counts what it has *not* verified.

Positioning corollaries:
1. **Complement, don't compete.** Sherlock/Maigret/SpiderFoot are upstream collectors; the catalogue
   should ship "how to pipe their output into a TRACEFIELD case", not re-implement them.
2. **The catalogue is a trust artefact, not a feature checklist.** OSINT Framework and Bellingcat win
   on breadth and editorial quality; TRACEFIELD can only win on machine-checkable honesty (dated
   checks, state tiers, licence provenance).
3. **Zero-claims beats feature-claims at alpha.** With no tests, no CI, no commits and a reproducible
   `case-export` crash (B3), any "more powerful than X" claim is currently falsifiable by a five-minute
   trial.

### B1.5 Risks
- **R1 — Feature-inflation trap:** SpiderFoot ships 200+ modules and Sherlock 400+ sites; any
  "OSINT platform" framing invites a capability comparison TRACEFIELD loses by 2–3 orders of
  magnitude.
- **R2 — Catalogue licence contamination:** Awesome OSINT and WhatsMyName are CC BY-SA 4.0; Bellingcat
  has no detected license. Copying descriptions/rows creates ShareAlike and unknown-terms exposure.
- **R3 — Wrapper-of-wrappers:** `inspect --deep` is a subprocess call to exiftool/ffprobe; users who
  discover that may ask why they need TRACEFIELD at all. The answer must be "case + provenance", not
  "prettier output".
- **R4 — Competitor quiet periods misread as abandonment:** holehe's last push is 2024-09-10 and
  SpiderFoot's 2026-04-13; "we're more alive" is a weak claim (ExifTool's mirror also went quiet
  after its May 2026 release) and invites uncharitable responses if TRACEFIELD itself goes quiet.
- **R5 — Star-count envy:** Sherlock at 94,272 stars sets an unwinnable metric (see B5 for the
  no-gaming stance).

### B1.6 Recommendations
- Publish `docs/strategy/competitors.md` generated from a script that records, per row: source URL,
  SPDX id *and* license-file hash, `pushed_at`, stars, `checked_at`. Regeneration must fail loudly
  rather than emit stale numbers.
- Rewrite the README "Why" section using the thesis in B1.4; add a "What this is not" section listing
  the non-novel items verbatim from B1.3.
- Add three "collector handshake" examples: Sherlock/Maigret text output → `source add` +
  `evidence attach`; `exiftool -json` output attached as evidence; Bellingcat toolkit row → catalogue
  entry link (link only, no prose).
- Track Bellingcat's `last-synced.json` and OSINT Framework's `arf.json` as ingestion inputs (both are
  machine-readable, which neither list's licence fully promises for redistribution — link/metadata
  only, see B2).

### B1.7 Open questions
- Q1: Is the target user an OSINT generalist (Bellingcat audience) or a security-assessment workflow
  (theHarvester/SpiderFoot audience)? The README's "field workbench" wording suggests the former,
  `pyproject` classifiers ("Topic :: Security") suggest the latter.
- Q2: Will the catalogue ever include commercial/registered services (IntelX, namechk)? Every such row
  raises pricing/ToS fields that need maintenance nobody has budgeted.
- Q3: Should TRACEFIELD declare a "supported upstreams" shortlist (e.g. 20 tools whose output formats
  it understands), or stay purely link-based?

### B1.8 Testable acceptance criteria
- **AC-B1-1:** `docs/strategy/competitors.md` contains ≥ the 11 rows in B1.2, each with a source URL,
  `checked_at` ≤ 30 days old, and license recorded as *both* SPDX and license-file hash; a check
  fails CI if any row's `checked_at` is stale.
- **AC-B1-2:** No marketing file (README, docs/index, release notes) contains a novelty claim for
  hashing, metadata reading, OCR, tool lists, or username checks; a grep-based test enforces a
  denylist of phrasings ("first", "only", "unique") against those feature nouns.
- **AC-B1-3:** Every competitor row marked `[U]` in B1.2 is either resolved or re-labelled `[U]` with a
  dated re-check attempt logged; zero silent guesses.
- **AC-B1-4:** A documented "collector handshake" exists for at least two third-party tools and is
  exercised by an integration test using recorded fixtures (no live network).

### B1.9 Challenged assumption
> "TRACEFIELD's honesty about catalogue health states is a novel differentiator."

Challenged with evidence: OSINT Framework already crowdsources dead-link/paywall reports and shows
community ratings (site UI, verified); Bellingcat staff-checks 337 tool pages and carries cost and
difficulty fields (verified); theHarvester now ships a local evidence-review UI with a "normalized
evidence model" and preserves findings when sources fail (verified from its README). Honest catalogue
practice is **necessary but not sufficient** differentiation — the defensible core is the
case/evidence/provenance contract, not the catalogue.

### B1.10 Failure mode
> **"Catalogue-driven launch."** TRACEFIELD ships 800+ rows, gets a burst of traffic from people
> searching for OSINT tool lists, and converts none of them, because the rows are links (which
> OSINT Framework already does better) while the actual differentiator — case export with a
> re-checkable manifest — still crashes with a raw traceback (verified in B3). Result: the project is
> filed mentally as "another awesome-list with a CLI", and later marketing cannot correct it.

---

## B2. Ecosystem & Catalogue Curator

### B2.1 What the three public indexes actually contain (measured, not guessed)

Method (reproducible, 2026-10-16): fetch each source, extract candidate entries, normalize URLs as
`scheme-stripped, lowercase host (www. removed) + path (trailing slash removed)`, keep fragments/queries
out.

| Source | Raw rows measured | Unique after normalization | Notes |
|---|---|---|---|
| Awesome OSINT (`jivoi/awesome-osint` README.md) | 1,527 markdown list items; 1,473 http(s) links | 1,430 | Includes articles, datasets, services, and non-tool links — **not** 1,430 tools |
| OSINT Framework (`osintframework.com/arf.json`) | 1,168 leaf nodes under 248 category nodes | 1,090 | 1 leaf had no URL; 1,342 unique node names |
| Bellingcat toolkit (`bellingcat/toolkit`, `gitbook/tools/*/README.md`) | 337 tool directories; URL section parsed in 333 | 278 | 4 READMEs had no parseable URL line; some rows are web services |
| **Sum of uniques (raw rows across sources)** | **2,798** | — | |
| **Union (deduped)** | — | **2,523** | Overlaps: Awesome∩Framework 200, Awesome∩Bellingcat 59, Framework∩Bellingcat 50, all three 34 |

Consequences for an "800+ catalogue" claim:
- 800+ **deduplicated candidate records** is comfortably achievable (2,523 candidate URLs). `[V]`
- 800+ **verified + installable + integrated + healthy** is not credible at alpha: each verification
  step is manual-ish (upstream identity, license text, installability), and the honest installable
  subset of OSINT links is a small fraction of a list that is dominated by websites and datasets.
- Therefore the **launch metric must be tiered counts, never a single number** (see B2.3).

### B2.2 Licence and attribution rules (the hard part)

| Source | Verified licence | What we may do | What we must not do |
|---|---|---|---|
| OSINT Framework | MIT `[V]` | Reuse with attribution (copyright Justin Nordine 2017) | Imply endorsement; ship MIT obligations unmet |
| Awesome OSINT | CC BY-SA 4.0 in `LICENSE.txt` (API says NOASSERTION) `[V]` | Link to entries; write our **own** factual summaries | Copy list prose/structure into a share-alike-free dataset; rely on the GitHub API badge alone |
| Bellingcat toolkit | **No license file at repo root** `[V]` | Link to pages; cite names | Copy descriptions, CSV contents, or images; treat the public CSV download as redistribution-cleared |
| WhatsMyName | CC BY-SA 4.0 `[V]` | Link; attribute Micah Hoffman | Wholesale import of its detection-pattern JSON into a differently-licensed dataset |
| Upstream tools themselves | GPL-2.0/3.0/MIT mixed (B1.2) `[V]` | List, link, describe factually | Bundle GPL code into TRACEFIELD (Apache-2.0) without a separate process |

Rules to encode in `data/catalog/source-manifest.json` (README already promises this file; it does not
exist yet):
1. Every entry records `source_list` (which indexes it came from), `attribution` (upstream project +
   copyright holder where known), and `license_source` (URL + SHA-256 of the license file we read, and
   the date we read it). A `license_id` of `NOASSERTION` may never be translated into "permissive".
2. Descriptions are project-authored, ≤ 2 sentences, factual, and **never** derived by paraphrase from
   CC BY-SA or unlensed sources. `CatalogEntry.description` already documents this intent; enforce it
   with a review checklist item, not vibes.
3. Where our licence review is incomplete, `license_review_state` stays `unverified` and
   `validation()` already rejects the contradiction "license UNKNOWN + review verified" — keep that
   guard and add a test for it.
4. Entries whose upstream requires circumvention, paid-only access without a free tier, or whose ToS
   forbids automated access are catalogue-eligible but must carry `data_exposure_warning` and
   `passive_active` fields; they are never "integrated".
5. Snapshot discipline: catalogue snapshots are dated artefacts (`catalogue-2026.10.16.jsonl`) with a
   manifest of source commits (`git rev-parse` of each index) so any row can be traced to a byte-exact
   input.

### B2.3 Tiered counts (the only counts we may publish)

Map directly onto the existing `IntegrationState` enum in `src/tracefield/registry/catalog.py`:

| Tier | Definition (publishable wording) | Counting rule |
|---|---|---|
| `raw_rows` | Rows ingested from source indexes | Every parsed candidate, before dedupe |
| `deduped` | Unique canonical entities after URL/name normalization + `duplicate_group` assignment | One per `id`; losers recorded in the group, not deleted |
| `verified` | Upstream identity + license text + last-activity checked by a human or scripted fetch with evidence stored | `verification_state=verified` **and** `last_checked` ≤ 90 days |
| `installable` | A documented install path exists (PyPI/npm/apt/brew/binary) and was executed successfully on a reference machine | Not derivable from metadata alone; needs a recorded test |
| `integrated` | A runnable adapter exists **inside** TRACEFIELD | Note: `catalog.validate()` currently flags any `integration_state=integrated` entry as a problem — the state is unreachable by design until adapter manifests exist. Either add an `adapter_manifest` field or delete the state; do not leave a dead enum value |
| `healthy` | Adapter (or, for index-only rows, an `upstream_url` reachability probe) passed a check in the last N days | `health_checked_at` + `health_result`; overdue ⇒ `stale` |

`tracefield tools status` (planned) must print all six numbers with the above captions and must refuse
to print a single "total tools" headline without the tiers.

### B2.4 Eligibility rules for inclusion
Include a candidate only if **all** hold:
- It has a resolvable upstream URL (repo or official site) — already enforced by `validate()`.
- It is plausibly usable by an investigator without credentials we cannot hold (else: eligible only
  with `key_required=yes` and a data-exposure warning).
- It is not purely a course, newsletter, or consulting landing page (categories `reference` and
  `workflow` exist precisely for those — count them separately from tools).
- It has a licence we can name or explicitly `UNKNOWN` with `license_review_state` honest.

Exclude (record in a `rejected.jsonl` with reason, never silently drop):
- Closed-source "free trial" lead-generation pages.
- Tools whose primary purpose is circumvention of platform protections.
- Duplicate vanity domains of a canonical repo (record as `duplicate_group`, not new entities).

### B2.5 Catalogue quality score (per entry, 0–100, components published)

| Component | Weight | Measured by |
|---|---|---|
| Licence identified + review state verified (with file hash) | 20 | `license_id != UNKNOWN` and `license_review_state=verified` |
| Upstream activity fresh (≤ 12 months since `pushed_at`/release) | 15 | dated check |
| Install path proven on a reference machine | 20 | recorded test run |
| Provenance fields complete (source_list, attribution, terms_url where relevant, checked_at) | 15 | schema lint |
| Health check fresh (≤ 30 days) | 15 | `health_checked_at` |
| Limitations/description quality (≤ 2 factual sentences, no marketing adjectives, no copied prose) | 10 | review checklist |
| Not stale/unavailable (state penalty) | 5 | state machine |

Aggregate catalogue score = weighted mean over **verified** entries only; always published next to the
tier counts. A high score on 40 entries must never be presented as a score on 900.

### B2.6 Risks
- **R1 — The 800 number becomes the goal** (Goodhart): counts inflate via websites/datasets while
  installable tools stagnate.
- **R2 — Licence exposure from unlensed sources** (Bellingcat) and ShareAlike propagation (Awesome
  OSINT, WhatsMyName).
- **R3 — Maintenance debt:** every row with `last_checked` older than 90 days silently lies. A list of
  900 rows with no refresh pipeline is worse than a list of 60 that is true.
- **R4 — Attribution rot:** upstream projects rename, transfer ownership, or relicense (ExifTool's own
  GitHub-vs-Perl-license ambiguity is a live example). `[V]`
- **R5 — Scope collision with B1's "catalogue is not the differentiator"** — spending the alpha's
  entire budget on rows nobody can verify.

### B2.7 Recommendations
- Build the ingestion pipeline **before** the data: one script per source, one normalizer, one
  `rejected.jsonl`, deterministic IDs (`slug of canonical host+path`), and a snapshot manifest.
- Start with 60–100 **high-trust** rows (the B1.2 competitors plus their direct dependencies), each
  fully verified, and publish tiered counts honestly ("412 indexed, 96 verified, 12 installable-tested,
  0 integrated") instead of a headline number.
- Add `license_file_sha256` and `source_commit` fields to the schema (bump `schema_version` to 2) so
  B2.5 can be computed mechanically.
- Use OSINT Framework's `arf.json` and Bellingcat's per-tool `README.md`/`tool.json` as **link**
  sources only; use each tool's own repo for facts.

### B2.8 Open questions
- Q1: Who signs off licence review for the 100th entry — and is that person named in the manifest?
- Q2: Do we accept entries we cannot install (commercial web tools), or is "catalogue = things that
  can run from a terminal" a hard eligibility line?
- Q3: How are corrections from upstream maintainers handled when they ask to be *removed*?

### B2.9 Testable acceptance criteria
- **AC-B2-1:** `tracefield tools status --json` emits `raw_rows`, `deduped`, `verified`,
  `installable`, `integrated`, `healthy`, each an integer ≥ 0, and the schema includes `generated_at`
  and per-source commit hashes.
- **AC-B2-2:** Ingesting the three sources in B2.1 twice in a row produces byte-identical JSONL
  (determinism test) and yields ≥ 2,000 deduped rows (reproduces my measurement).
- **AC-B2-3:** `validate()` fails if any entry has `license_id == "UNKNOWN"` with
  `license_review_state == "verified"`, if `duplicate_group` is empty on a name collision, or if
  `integration_state == "integrated"` without an adapter manifest reference.
- **AC-B2-4:** A licence-lint test asserts no `description` field shares a 12-gram with any fetched
  Awesome OSINT/Bellingcat prose (simplest possible copying detector).
- **AC-B2-5:** Any published catalogue number in README/docs is emitted by `tools status`, not typed
  by hand; a docs test greps for bare large numbers.

### B2.10 Challenged assumption
> "We can ship a deduplicated 800+ catalogue at launch with quality."

Measured reality: the three indexes yield 2,523 deduped URLs, but "URL" ≠ "tool", and verification is
the bottleneck. A defensible alpha catalogue is ~50–150 fully verified rows with tiered counts; the
800+ number should be presented, if at all, as "candidate records awaiting verification" — a backlog
metric, not an achievement.

### B2.11 Failure mode
> **"Row-laundering."** A contributor imports 300 rows from an index, the descriptions are subtly
> paraphrased CC BY-SA prose, `license_review_state` is bulk-set to `verified`, the README headline
> becomes "800+ tools", and two months later an upstream relicenses or a rights-holder notices.
> TRACEFIELD's entire differentiation (honesty) is then spent on a compliance problem.

---

## B3. Developer Experience & Docs Reviewer

### B3.1 What a new user actually experiences today (all verified by execution, 2026-10-16)

Environment: `.venv` in the repo, Python 3.13.5, exiftool and ffprobe present, **tesseract absent**,
`TRACEFIELD_HOME` pointed at a scratch directory.

| Step | Command | Result |
|---|---|---|
| Install (dev) | `python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'` | Works (pre-existing venv verified runnable) |
| Help | `tracefield --help` | Lists 13 commands; `--install-completion` / `--show-completion` present `[V]` |
| Diagnostics | `tracefield doctor` | Table: python 3.13.5, version 0.1.0, database ok, exiftool/ffprobe present, tesseract missing, network blocked, telemetry none `[V]` |
| Machine output | `tracefield doctor --json` | **FAILS**: "No such option: --json", exit 2 — but README says "add `--json` to most commands" `[V]` |
| Case | `case create/list/show` | Works; `case list --json` emits JSON `[V]` |
| Inspect | `tracefield inspect ./fixture.txt --deep` | 0.64 s; prints sha256/sha512/md5, size, mtime, exiftool JSON, caveats. **Also emits `warning: ffprobe: … Invalid data found` for a plain text file** (noisy but honest) `[V]` |
| Hash | `tracefield hash ./fixture.txt --json` | Clean JSON `[V]` |
| OCR | `tracefield ocr ./fixture.txt` | `UNAVAILABLE: tesseract is not installed…`, exit 5 `[V]` (matches README's exit-code table) |
| Network guard | `source add https://example.com --case demo --fetch` | Exit 4 with the opt-in message `[V]` |
| Not found | `case show nope` | Exit 2 `[V]` (matches README) |
| Usage error | `tracefield inspect` (missing arg), `tracefield badcmd` | **Exit 2**, but README documents usage errors as exit **3** `[V]` |
| Export | `case-export demo --output DIR` | **Reproducible crash**: raw Python traceback, `PermissionError` writing `…/evidence/evidence/<sha>`, exit 1; `manifest.json` written but `report.md`/`report.json` **missing** in the crashed run `[V]` |

Root cause of the export crash (diagnosed by reading `src/tracefield/reporting/export.py:39-47` and
reproducing): `copytree` preserves the immutable 0400 mode of stored evidence; the redaction pass then
calls `write_text` on any text-decodable evidence file whose content matches a secret pattern
(reproduced with a fixture containing `token=supersecret…`, which becomes `token=[REDACTED]`).
Opening a 0400 file for writing raises `PermissionError`, which escapes uncaught. This is both a crash
and a latent integrity bug (if the write succeeded, exported bytes would diverge from the manifest).

### B3.2 Diagnostics, completion, examples — current state
- Diagnostics: `doctor` is good and honest; it is **missing `--json`** (every other command family has
  it) and does not report the catalogue data directory or schema version.
- Completion: Click/Typer shell completion works out of the box (`--show-completion` emitted a zsh
  function `[V]`) — undocumented in the README.
- Examples: README has a five-minute block; it currently ends with `case-export`, i.e. the step that
  crashes (B3.1).
- Contributor instructions: README links `CONTRIBUTING.md` and `SECURITY.md`; **both files do not
  exist** `[V]`. There are no tests and no CI workflow files `[V]`.

### B3.3 Proposed README outline (keep it shorter than the code)
1. One-sentence definition + status badge (alpha, Python ≥3.11, Apache-2.0).
2. "What this is not" (from B1.3 — 5 bullets).
3. Install: `pipx install tracefield` (target), `pip install -e '.[dev]'` (dev), plus optional
   backends table (exiftool / ffprobe / tesseract) with the exact distro commands.
4. Five-minute first case — **every command pasted from an executed transcript**, exit codes shown.
5. Command surface table (already good) + "most commands accept `--json`" *after* doctor/report get it.
6. Exit-code contract (single source of truth; see B3.5).
7. Privacy defaults (network off, telemetry-free, redaction) — already strong.
8. Honest catalogue counts (`tools status`, tier captions).
9. Limitations (keep verbatim; it is the best-written section in the repo).
10. Contributing / Security / Changelog links (only after the files exist).

### B3.4 Documentation acceptance tests (executable, CI-enforced)
- **DT-1 install:** clean container → install → `tracefield --version` prints `0.1.0`, exit 0.
- **DT-2 first result:** `tracefield hash README.md --json` parses with a JSON parser and returns a
  64-hex digest; total elapsed < 10 s.
- **DT-3 doctor contract:** `doctor --json` exits 0 and emits `{"checks": [...]}` (currently fails).
- **DT-4 exit codes:** scripted assertion of {missing arg ⇒ 3, unknown command ⇒ 3, unknown option ⇒ 3,
  not-found ⇒ 2, network-blocked ⇒ 4, backend-missing ⇒ 5, success ⇒ 0} (currently 3 of 6 fail).
- **DT-5 export round-trip:** create case → attach two fixtures (one containing `token=…`) →
  `case-export` → exit 0 → `report.md` exists → re-hash of exported evidence matches manifest →
  exported file containing the token is redacted **and** digest bookkeeping stays consistent (this
  test currently fails by design; it is the regression test for the B3.1 bug).
- **DT-6 docs snippets:** every fenced bash block in README/docs is extracted and executed in a
  scratch `TRACEFIELD_HOME`; any block that exits non-zero fails CI.
- **DT-7 link check:** no README link may 404 (catches the missing CONTRIBUTING/SECURITY today).
- **DT-8 no-color:** `NO_COLOR=1 tracefield doctor | grep -c $'\033\['` is 0.
- **DT-9 narrow terminal:** `COLUMNS=40 tracefield evidence list --case X` contains no truncated
  digest shorter than 32 hex chars and no line ending mid-token.

### B3.5 Risks
- **R1 — Documented-path breakage** (highest): the README's own five-minute recipe ends in a traceback.
  First-run failure is the single strongest predictor of zero retention for a CLI.
- **R2 — Exit-code contract drift:** scripts cannot rely on documented codes; `2` currently means both
  "not found" and "usage error".
- **R3 — Tracebacks as UX:** uncaught exceptions leak paths and internals; for an OSINT tool whose
  users paste terminal output into tickets, that is also an OPSEC leak.
- **R4 — Optional-backend fog:** users who skip `doctor` discover tesseract/ffprobe absence at the
  moment of need (exit 5 is honest, but the message lacks install commands per platform).
- **R5 — No tests, no CI:** nothing prevents the next refactor from breaking the five-minute path
  again.

### B3.6 Recommendations
- Fix the export crash first (redact into a temp file and replace, or redact a copy with the manifest
  updated to the redacted digest; never mutate the immutable store). Then re-run DT-5.
- Add `--json` to `doctor`, `report`, and `case-export`; make `--json` a documented **matrix** in the
  README rather than "most commands".
- Make Click usage errors exit 3 (custom `ClickException`/`Abort` handling in `main()`), keeping 2 for
  not-found, or change the README — but pick one and test it.
- Add per-platform install hints to the exit-5 message (`apt install tesseract-ocr`, `brew install
  tesseract`, etc.).
- Document `--install-completion` in the README (it already works).
- Land `tests/` with at least DT-2/DT-4/DT-5/DT-8/DT-9 and one GitHub Actions workflow before any
  public announcement.

### B3.7 Open questions
- Q1: Is `pipx` the blessed install path (recommended) or is source-install the only story for now?
- Q2: Should the TUI be advertised in the README at alpha, given every feature has a CLI path?
- Q3: Do we guarantee JSON output stability (schema) in 0.x, or is JSON also "unstable until 1.0"?

### B3.8 Testable acceptance criteria
- **AC-B3-1:** DT-1…DT-9 all pass in CI on Linux (macOS optional) for every PR.
- **AC-B3-2:** `tracefield --help` command list == the set of commands in the README table (parsed
  comparison test).
- **AC-B3-3:** No command emits a Python traceback for any input exercised by the test suite
  (fail-on-`Traceback` in output).
- **AC-B3-4:** `case-export` is atomic: either all of {manifest, report.md, report.json,
  EXPORT_README.txt, evidence/} exist with exit 0, or the output directory is removed and exit ≠ 0.
- **AC-B3-5:** README links to CONTRIBUTING.md and SECURITY.md resolve (files exist).

### B3.9 Challenged assumption
> "The README's five-minute first case works today."

Falsified on 2026-10-16: install→help→doctor→case→inspect→hash all work, but `doctor --json` errors
(exit 2), usage errors return 2 instead of the documented 3, and `case-export` — the final step of the
published recipe — raises an uncaught `PermissionError` with a raw traceback. The five-minute path
should be treated as a **test fixture**, not prose.

### B3.10 Failure mode
> **"Screenshot-driven docs."** Docs are written from the intended behaviour, the export crash is
> known only to people who ran it, and the first external user's paste of a traceback becomes the
> project's public first impression on a forum — after which no amount of "honest catalogue" messaging
> recovers credibility.

---

## B4. Terminal Brand & Visual Systems Reviewer

### B4.1 Current rendering behaviour (verified by execution, 2026-10-16)

| Condition | Observed |
|---|---|
| Default terminal | Rich box-drawing tables (heavy borders), green/red/yellow status words in `doctor`, dim hashes in `ocr` |
| `NO_COLOR=1` | No ANSI SGR sequences emitted `[V]` — good — but **UTF-8 box-drawing characters remain** (fails on ASCII/cp437 locales and some CI logs) |
| `TERM=dumb` | Still renders full box tables `[V]` |
| `COLUMNS=40` | Tables reflow with ellipsis truncation (`sha2…`, `sour…`) `[V]`; `case show` wraps mid-token (`records: … 3` / `evidence`) `[V]` |
| Piping | Tables still drawn when stdout is not a TTY (piped `case list` still contains box glyphs) `[V]` |

Risk: truncated hashes in narrow terminals are a **provenance hazard** — a user copying `fe482b5e…`
cannot verify anything.

### B4.2 Design tokens (proposal, not a mandate)

One accent, four status colours, one dim, one rule. Foreground-only — **never emit background colours**
(so screenshots, `script(1)` capture, and light-bg terminals degrade gracefully).

| Token | Hex (truecolor) | ANSI-256 fallback | ANSI-16 | Usage |
|---|---|---|---|---|
| `tf.text` | `#D6DCE5` | 253 | 7 (white) | Primary output |
| `tf.dim` | `#7D8799` | 244 | 8 (bright black) | Labels, timestamps, caveats |
| `tf.accent` | `#4FB6C6` (signal cyan) | 44 | 6 (cyan) | **Identity only**: case IDs, section headers, prompt. Never status |
| `tf.ok` | `#4CAF7D` | 72 | 2 (green) | `ok`, `intact`, `verified` |
| `tf.warn` | `#D9A140` | 179 | 3 (yellow) | `missing`, `stale`, `caution` |
| `tf.error` | `#E2574C` | 167 | 1 (red) | `fail`, `unavailable`, blocked network |
| `tf.rule` | `#2A3140` | 236 | 8 | Table borders in full-colour mode |
| `tf.plain` | — | — | — | ASCII mode: no colour, no Unicode |

Rules:
- Hashes/digests are **never** colour-coded (colour implies meaning; digests have none).
- Assessment labels (`UNASSESSED`, etc.) render in `tf.dim`, not `tf.warn` — they are workflow states,
  not warnings; this matches the product's own stated limitation.
- Accent budget: at most one accent-coloured element per screenful of CLI output.

### B4.3 Sample terminal output sketch (`tracefield evidence verify --case demo`)

```text
evidence — demo                                    case_5663cfa0  [accent]

  OK  ev_1c42766a  90c7d0e42b15590b4f127c0f159b7935a49c24c29d53c0adad3284e29261628b
  OK  ev_a45e7d4a  c950f5400d310751dc2d4545a2c87c908a473525aa389a821155f0e3f19e9dd9
  OK  ev_be08b4f3  fe482b5e524c67728f4f2b4f430cd10d9a25659641f995ae537b282ccd181e0b

  3 files checked · all intact          [dim: digests prove bytes, not truth[/dim]]
  hint: --json for machine-readable results
```

Reduced-colour (NO_COLOR / `TRACEFIELD_COLOR=off`) variant — same information, no SGR, ASCII only when
`TRACEFIELD_UNICODE=0`:

```text
evidence - demo                                    case_5663cfa0
  OK  ev_1c42766a  90c7d0e42b15590b4f127c0f159b7935a49c24c29d53c0adad3284e29261628b
  OK  ev_a45e7d4a  c950f5400d310751dc2d4545a2c87c908a473525aa389a821155f0e3f19e9dd9
  OK  ev_be08b4f3  fe482b5e524c67728f4f2b4f430cd10d9a25659641f995ae537b282ccd181e0b
  3 files checked; all intact
```

### B4.4 Small-terminal rules
- `< 60` columns: no tables; key/value lines; digests always printed in full on their own line
  (never wrapped mid-token, never shortened below 32 hex chars).
- `60–100`: tables allowed with truncated digests **only if** a `full digest: …` line or a `--json`
  hint follows.
- `> 100`: full tables.
- Any TTY width below 40: refuse tables entirely and print a `compact` layout.
- Non-TTY stdout (pipes, CI): no tables by default; either plain lines or an error telling the user to
  pass `--json`. Never box-drawing characters into a pipe without `--json`.

### B4.5 References (broad inspiration only; assets are not copied)
- Wave Terminal docs (`https://docs.waveterm.dev/`, HTTP 200 on 2026-10-16) — useful only as a
  reference for how a modern terminal product documents panes/widgets; TRACEFIELD's CLI must not
  depend on a specific terminal emulator.
- Omarchy (`https://omarchy.com/` and `https://omarchy.com/docs`, HTTP 200 on 2026-10-16) — broad
  reference for opinionated dark-first defaults; no theme assets, fonts, or config files are taken.
- Explicitly not borrowed: any colourway, logo, screenshot, font, or config file from either project.

### B4.6 Risks
- **R1 — Colour as meaning:** if status colours are reused for assessment labels, users read
  "yellow" as "probably fake", contradicting the product's own "labels are not probabilities" rule.
- **R2 — Unicode-only output:** box drawing breaks in ASCII locales; some users pipe output into
  systems that mangle UTF-8.
- **R3 — Truecolor assumptions:** many corporate terminals are 16-colour; hard-coded 24-bit hex
  degrades to invisible or ugly without fallbacks.
- **R4 — Truncated digests** (observed today) undermine the core promise of verifiability.
- **R5 — Brand creep:** adding a logo/banner to a security tool invites "marketing" criticism; the
  aesthetic should read as instrumentation, not product placement.

### B4.7 Recommendations
- Implement tokens as a single module (`render/theme.py`) consumed by every Rich console; add
  `TRACEFIELD_COLOR=auto|always|off` and `TRACEFIELD_UNICODE=0|1` env knobs alongside `NO_COLOR`.
- Switch default table box to a light rule set; reserve heavy borders for the TUI only.
- Print full digests at any width in `evidence verify`, `evidence list`, and `case-export` summaries.
- Make non-TTY output plain by default (Rich `Console(no_color=True, force_terminal=False)` already
  helps; verify with DT-8/DT-9).

### B4.8 Open questions
- Q1: Is signal cyan the right single accent (instrument/field vibe) or should the accent be the
  terminal default foreground to minimise footprint?
- Q2: Do we ship a documented `TRACEFIELD_THEME=tui|plain` split, or one theme with modes?
- Q3: Should the TUI (Textual) reuse the same token table 1:1, or is a separate TUI palette acceptable?

### B4.9 Testable acceptance criteria
- **AC-B4-1:** With `NO_COLOR=1`, no command emits ESC bytes (test greps for `\x1b[`).
- **AC-B4-2:** With `TRACEFIELD_UNICODE=0`, no command emits any codepoint above U+007E in output.
- **AC-B4-3:** With `COLUMNS=40`, every digest printed is either ≥ 32 hex chars or explicitly labelled
  truncated with a `--json` hint; no line ends mid-token.
- **AC-B4-4:** Piping any command's human output to `cat` produces no box-drawing characters unless the
  user forced colour.
- **AC-B4-5:** A token table test asserts exactly one accent colour is used per rendered screen and
  that assessment labels resolve to `tf.dim`.

### B4.10 Challenged assumption
> "A dark palette plus one accent is sufficient brand work for a terminal tool."

Challenged by measurements: today's output already loses information at `COLUMNS=40` (truncated
digests) and still emits Unicode box drawing under `NO_COLOR=1` and `TERM=dumb`. Brand work for a
terminal product is mostly **degradation behaviour** (narrow, dumb, piped, non-UTF8), not the happy-path
colour scheme.

### B4.11 Failure mode
> **"Pretty in my terminal, garbage in the ticket."** A user pastes `evidence list` output from a
> 60-column terminal into an issue: digests are elided to `fe482b5e…`, box characters render as mojibake,
> and the one thing TRACEFIELD promised — independently checkable integrity — cannot be checked by the
> reviewer. The brand promise is broken by its own rendering.

---

## B5. Open-Source Maintainer & Community Reviewer

### B5.1 Current governance surface (verified 2026-10-16)

| Artifact | State |
|---|---|
| `LICENSE` | Apache-2.0 present `[V]` |
| `README.md` | Present; links `CONTRIBUTING.md` and `SECURITY.md` **which do not exist** `[V]` |
| `CONTRIBUTING.md` | Missing `[V]` |
| `SECURITY.md` | Missing `[V]` |
| `.github/workflows/` | Empty `[V]` |
| `tests/` | Empty `[V]` |
| Git history | No commits on `main`; all files untracked `[V]` |
| Version | `0.1.0`, Development Status :: 3 - Alpha `[V]` |
| Changelog | Missing `[V]` |
| Issue templates / labels / roadmap | None `[V]` |

### B5.2 CONTRIBUTING design (to be written before the first external contributor)
- **Scope boundary section first:** "TRACEFIELD stores and verifies findings; it does not try to be
  the collector." A triage question on every feature request: *"Does this add provenance/verification,
  or does it collect new data?"* — collector features are answered with a catalogue link, politely and
  consistently (label `wont-collect`).
- **Catalogue contributions** require: upstream URL, license file URL + SPDX, last-activity date,
  evidence of install (command + output), and a signed-off statement that the description is original
  prose (B2's copying detector enforces this mechanically). Unsolicited "please add my tool" PRs
  without verification data are closed with a template reply — a policy Bellingcat already practises
  publicly ("Please do not suggest tools that should be added to the toolkit", toolkit README,
  verified).
- **Code contributions:** `ruff` + `mypy --strict` + pytest gates (config already exists in
  `pyproject.toml`), `pre-commit` optional, "no new runtime dependencies without an issue".
- **Evidence-handling contributions** carry a higher bar: any change touching
  `core/provenance.py`, `reporting/export.py`, or `security/*` requires a test that demonstrates the
  integrity property, plus a second reviewer.

### B5.3 Issue templates and labels
- Templates: `bug.yml` (version, OS, `doctor --json` output, reproduction, whether data contains real
  case material — with a warning never to paste real subjects), `catalogue.yml` (entry id, upstream
  URL, what changed, evidence), `feature.yml` (collector-vs-provenance triage question), `docs.yml`.
- Labels: `cli`, `tui`, `provenance`, `catalogue`, `dx`, `docs`, `security`, `needs-verification`,
  `wont-collect`, `good-first-issue` (reserved for docs/tests only in 0.x), `blocked-upstream`.
- Roadmap labels: `roadmap/0.2`, `roadmap/0.3` with a single `ROADMAP.md` that states *exit criteria*,
  not feature lists ("0.2 = DT-1…DT-9 green + 50 fully verified catalogue rows").

### B5.4 Security reporting
- `SECURITY.md` with: supported versions (`0.1.x` — "latest only"), private reporting channel (GitHub
  private vulnerability reporting, or an email), expected response window (e.g. ack ≤ 5 days), and an
  explicit note that **real case data must never be attached to public issues**.
- Because TRACEFIELD handles investigative material, add a short "what we do not want in reports"
  section (no live targets, no personal data of third parties).

### B5.5 Version and changelog policy
- Code: SemVer/PEP 440, 0.x = no API stability promise, but **exit codes and JSON keys are treated as
  API** once documented (that is why B3's contract matters).
- Catalogue data: independent calendar versioning (`catalogue-2026.10.16`) with its own manifest of
  source commits; a code release must not silently ship different data.
- Schema: `CatalogEntry.schema_version` already exists; publish a migration note when bumping.
- `CHANGELOG.md` in Keep-a-Changelog form, generated per release; include "known limitations" section
  (the project's strongest rhetorical asset).

### B5.6 Workload controls and sustainable adoption
- **Ingest automation, human review:** bots may open catalogue PRs; humans approve verification state.
  Cap new-entry PRs at a reviewable batch (e.g. 25) with dedupe evidence attached.
- **Staleness:** an automated monthly job marks entries `stale` when `last_checked` > 90 days and
  opens an issue per batch, not per row.
- **No star-gaming:** no "★ 1k stars by Friday" targets, no bought coverage, no follow-for-follow
  outreach, no misleading comparisons with Sherlock's 94,272 stars `[V]`. Metrics that matter:
  verified rows, healthy checks, export round-trips performed, bug reports with reproducers, and
  number of contributors whose patches included tests.
- **Sustainable pace:** single-maintainer alpha should pre-commit to response SLAs it can keep (e.g.
  "issues triaged weekly, no promise of feature work") rather than over-promising and going silent —
  a known failure pattern in OSINT tooling (see quiet periods in B1.2: holehe last push 2024-09-10).
- **Announce last, ship first:** do not publish the repository publicly before the first commit, tests,
  CI, CONTRIBUTING, SECURITY, and the export bug fix exist. Right now there is literally nothing to
  clone (`git log` fails) `[V]`.

### B5.7 Risks
- **R1 — Broken links at launch** (README → missing CONTRIBUTING/SECURITY) signals unmaintained.
- **R2 — Catalogue PR flood** consuming all maintainer time with low-value "add my tool" requests.
- **R3 — Evidence-handling regressions** from well-meaning contributors who do not understand
  integrity semantics (mitigated by the higher review bar in B5.2).
- **R4 — Trust incident:** if a real investigation's data ever lands in a public issue, the project's
  privacy posture is finished regardless of code quality.
- **R5 — Metrics distortion:** chasing stars or "800+ tools" headlines (B2) crowds out verification
  work.

### B5.8 Recommendations
- Land, in this order, before any announcement: (1) export crash fix + DT-5, (2) exit-code contract
  fix, (3) tests + CI, (4) CONTRIBUTING.md + SECURITY.md + CODE_OF_CONDUCT, (5) CHANGELOG + ROADMAP,
  (6) first tagged release `v0.1.0`.
- Add GitHub private vulnerability reporting and branch protection requiring CI green.
- Publish `ROADMAP.md` with exit criteria and a "non-goals" section (collectors, cloud sync, chatbot).
- Adopt a maintainer-duties doc: review cadence, what gets declined by default, and how catalogue
  entries graduate between states.

### B5.9 Open questions
- Q1: Single maintainer or small core team at launch? (Determines SLA realism.)
- Q2: Is there an appetite for a `catalogue-*` data-only release cadence separate from code?
- Q3: Do we accept DCO sign-off now (cheap while contributors ≈ 0) or later (painful)?

### B5.10 Testable acceptance criteria
- **AC-B5-1:** `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, `CHANGELOG.md`, `ROADMAP.md`
  exist; every README/docs link resolves (DT-7).
- **AC-B5-2:** ≥ 3 issue templates and ≥ 10 labels exist in `.github/`, including `wont-collect` and
  `needs-verification`.
- **AC-B5-3:** A CI workflow runs ruff, mypy strict, and pytest on every PR; branch protection requires
  it.
- **AC-B5-4:** A tagged release exists whose CHANGELOG lists known limitations and whose artifacts
  install via `pipx` in a clean container (DT-1).
- **AC-B5-5:** Written policy forbids publishing catalogue counts without tier captions and forbids
  star-count targets; enforcement is a docs lint (B2 AC-B2-5) plus a maintainer checklist.

### B5.11 Challenged assumption
> "Open-sourcing the alpha will attract contributors and adoption."

Falsified-by-inspection today: there are no commits, no tests, no CI, no CONTRIBUTING/SECURITY, and
the published five-minute path crashes (B3). An alpha in that state attracts issue reports it cannot
service and erodes trust with exactly the audience (investigators) that punishes unreliability hardest.
Adoption sequencing should be: releasable artefact → verifiable claims → then audience.

### B5.12 Failure mode
> **"The catalogue PR swamp."** The repo goes public with "800+ tools" in the headline; within weeks
> most incoming PRs are drive-by "add my tool" submissions with no licence, no install evidence, and
> duplicate URLs. The maintainer spends evenings deduplicating instead of fixing provenance bugs; the
> few genuine bug reports (like the export crash) rot unanswered; the project quietly joins the long
> list of half-maintained OSINT utilities — the very failure mode TRACEFIELD's honesty pitch claims to
> reject.

---

## Appendix A — Verification log (all accessed 2026-10-16, UTC)

GitHub REST API (`https://api.github.com/repos/<owner>/<repo>`), observed 19:02–19:05 UTC:
- `smicallef/spiderfoot` → MIT, pushed 2026-04-13T19:43:06Z, 23,543 stars, open issues 345
- `jivoi/awesome-osint` → NOASSERTION (API), pushed 2026-10-15T06:51:52Z, 30,275 stars
- `lanmaster53/recon-ng` → GPL-3.0, pushed 2026-10-05T14:10:08Z, 5,994 stars
- `soxoj/maigret` → MIT, pushed 2026-10-14T16:10:52Z, 39,142 stars
- `sherlock-project/sherlock` → MIT, pushed 2026-10-16T05:17:06Z, 94,272 stars
- `exiftool/exiftool` → GPL-3.0, pushed 2026-05-27T16:45:01Z, 5,169 stars
- `laramies/theHarvester` → GPL-2.0, pushed 2026-10-14T05:13:58Z, 17,981 stars
- `megadose/holehe` → GPL-3.0, pushed 2024-09-10T20:24:32Z, 15,219 stars
- `lockfale/OSINT-Framework` → MIT, pushed 2026-10-10T14:48:55Z, 12,292 stars
- `bellingcat/toolkit` → no license detected, pushed 2026-10-08T05:36:45Z, 682 stars
- `WebBreacher/WhatsMyName` → NOASSERTION (API), pushed 2026-10-15T14:55:30Z, 2,952 stars

License texts and docs fetched (raw.githubusercontent.com / product sites):
- `jivoi/awesome-osint/master/LICENSE.txt` → CC BY-SA 4.0 text
- `WebBreacher/WhatsMyName/main/LICENSE.md` → CC BY-SA 4.0, Micah Hoffman
- `smicallef/spiderfoot/master/LICENSE` → MIT (Steve Micallef); `README.md` → features list incl. "200+ modules", "API key export/import", SpiderFoot HX commercial
- `soxoj/maigret/main/LICENSE` → MIT 2020-2026 Soxoj; `README.md` → "No API keys required"
- `lanmaster53/recon-ng/master/LICENSE` → GPL-3.0; `README.md` → modular recon framework, "free software"
- `laramies/theHarvester/master/LICENSE` → GPL-2.0; `README.md` → Python 3.14 + uv, HarvestView, REST API, "P0 passive sources … no API key"
- `megadose/holehe/master/LICENSE.md` → GPL-3.0
- `sherlock-project/sherlock/master/LICENSE` → MIT; `docs/README.md` → "400+ social networks", install table, broken third-party packages warning
- `exiftool.org/` → release 13.59 (May 27, 2026), features incl. MD5/SHA256/SHA512 of image data, JSON output; License section: "same terms as Perl itself"
- `osintframework.com/` → UI features (OPSEC notes, community rating, dead-link report), link to `github.com/lockfale/osint-framework`; `LICENSE` raw → MIT (Justin Nordine); `arf.json` → 1,168 leaves / 248 categories / 1,090 unique normalized URLs
- `www.bellingcat.com/toolkit` → redirects to `bellingcat.gitbook.io/toolkit` (HTTP 200); toolkit README quotes: staff checks entries, CSV download, "Inclusion … does not imply … endorses"; repo tree → 337 tool dirs, 59 category pages, no LICENSE file
- `docs.waveterm.dev/` → HTTP 200; `omarchy.com/` and `omarchy.com/docs` → HTTP 200
- `intelx.io` → HTTP 200 (details not verified); `namechk.com` and `whatsmyname.app` → HTTP 403 to automated fetch

Local execution evidence (`.venv/bin/tracefield`, `TRACEFIELD_HOME=/tmp/opencode/tfhome`):
- `doctor`, `case create/list/show`, `source add`, `claim add`, `evidence attach/list/verify`, `hash`,
  `inspect --deep` (0.64 s), `report`, `tui` present in `--help`
- `doctor --json` → exit 2 "No such option: --json"; `case show nope` → exit 2; `inspect` (no arg) and
  `badcmd` → exit 2; `source add … --fetch` (no opt-in) → exit 4; `ocr` without tesseract → exit 5
- `case-export` → exit 1, raw traceback, `PermissionError` at
  `reporting/export.py:47` writing `…/evidence/evidence/<sha>` (reproduced twice; caused by redaction
  of a 0400 immutable evidence copy containing `token=…`)
- `NO_COLOR=1` → no SGR escapes but UTF-8 box glyphs remain; `COLUMNS=40` → truncated digests and a
  mid-token wrap in `case show`; `--show-completion` emits a zsh completion function

## Appendix B — Explicit "unknown" register
- Sherlock / recon-ng / IntelX / namechk.com API-key requirements: not verified → `[U]`
- Bellingcat toolkit redistribution terms: no license file found → `[U]`
- Whether `exiftool/exiftool` on GitHub is the canonical upstream or a mirror → `[U]` (upstream site
  points at SourceForge for downloads)
- Live reachability of `whatsmyname.app` and `namechk.com` for humans (403 to my fetcher) → `[U]`
- Any claim about community consensus, sentiment, or benchmark performance: **none is made anywhere in
  this document**; nothing of that kind was verified, so nothing of that kind is asserted.
