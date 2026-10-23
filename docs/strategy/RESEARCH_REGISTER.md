# TRACEFIELD — Research Register

> Every external fact used by this project, with its source, verification date,
> and confidence. Facts marked `[V]` were fetched from a primary source on the
> stated date. Facts marked `[U]` are unverified and must not be relied on.
> Internal facts (code behaviour) are verified by the test suite, not listed
> here.

## Standards and specifications

| Fact | Source | Verified | Confidence |
|---|---|---|---|
| PROV-DM is a W3C Recommendation; `wasDerivedFrom`, `wasGeneratedBy`, `used`, `alternateOf` are its core relations | https://www.w3.org/TR/prov-dm/ (fetched during Team A review) | 2026-10-16 | `[V]` |
| TRACEFIELD's `Source`/`Observation`/`EvidenceItem`/`AnalysisEvent`/`Relation.DERIVED_FROM` map cleanly onto PROV-DM concepts; the mapping is documented in this register and `DECISIONS.md`, not implemented as PROV-XML/JSON | Internal design decision | 2026-10-16 | `[V]` |
| OWASP OOVS v0.1.0 exists with machine-readable requirements; we reference it by stable identifier only, no text copying (CC BY-SA 4.0 obligations) | OWASP OOVS repository (per master brief §14) | Not re-fetched this session | `[U]` — mapping doc must re-verify version at publication |
| NO_COLOR informal standard: tools should disable ANSI colour when env `NO_COLOR` is set; Rich ≥11.2.0 respects it | https://no-color.org/ | 2026-10-16 | `[V]` |
| SQLite busy timeout (`sqlite3_busy_timeout` / `PRAGMA busy_timeout`) is the documented contention control | https://www.sqlite.org/c3ref/busy_timeout.html | 2026-10-16 | `[V]` |
| Textual provides `App.run_test()` headless pilot testing | https://textual.textualize.io/guide/testing/ | 2026-10-16 | `[V]` |

## Practitioner evidence

| Fact | Source | Verified | Confidence |
|---|---|---|---|
| Bellingcat survey (2022-08-12): 525 respondents; **>83% find finding the right tools difficult or time-consuming**; only ~24% regularly use GitHub-hosted tools; "only a quarter of our respondents knew how to use the command line"; 49/525 named source/verification as their biggest challenge; recurring pains: information scattered across formats ("One tool for all would be great"), overloaded by volume, distrust of marketing language, want to be told when a tool stops working | https://www.bellingcat.com/resources/2022/08/12/these-are-the-tools-open-source-researchers-say-they-need/ (article text fetched in full) | 2026-10-19 | `[V]` (page fetched; figures read directly from article text — treat as 2022 self-reported survey, not current market data) |

Implication for positioning (used in `POST_BUILD_AUDIT.md` / `FINAL_BUILD_SPEC.md`):
honest capability statements, visible staleness, and a case-first workflow are
directly supported by this survey; a terminal-only product consciously reaches
the technically comfortable minority (the CLI is optional-but-primary here).

## Competitor / ecosystem facts

All rows in `COMPETITOR_MATRIX.md` were verified 2026-10-16 via GitHub REST API
repo metadata (license, `pushed_at`, stars, archived flags), raw LICENSE/README
files, and product sites. Summary of the verification session:

- Sherlock: MIT, pushed 2026-10-16T05:17:06Z, 94,272 stars `[V]`
- Maigret: MIT, pushed 2026-10-14T16:10:52Z, 39,142 stars; "No API keys required" `[V]`
- SpiderFoot: MIT, pushed 2026-04-13T19:43:06Z, 23,543 stars; "200+ modules" `[V]`
- theHarvester: GPL-2.0, pushed 2026-10-14T05:13:58Z, 17,981 stars; requires Python 3.14 + `uv` `[V]`
- holehe: GPL-3.0, pushed 2024-09-10T20:24:32Z, 15,219 stars `[V]`
- ExifTool: upstream Artistic/GPL dual; GitHub mirror reports GPL-3.0 — discrepancy recorded `[V]`
- OSINT Framework: MIT, pushed 2026-10-10T14:48:55Z, 12,292 stars; has OPSEC notes + dead-link reporting `[V]`
- Bellingcat toolkit: no license file at repo root `[V]`; 337 tool pages counted `[V]`
- Awesome OSINT: LICENSE.txt = CC BY-SA 4.0 (API says NOASSERTION) `[V]`; 1,473 http links counted `[V]`
- WhatsMyName: CC BY-SA 4.0 `[V]`
- IntelX, namechk.com: unverified `[U]` (403 to automated fetch / not checked)

## Catalogue ingestion facts

Measured 2026-10-16 (method: fetch, extract, normalize `scheme-stripped,
lowercase host (www. removed) + path (trailing slash removed)`):

| Source | Raw | Unique | Notes |
|---|---|---|---|
| Awesome OSINT README | 1,527 list items; 1,473 http(s) links | 1,430 | Includes articles/datasets/services — not 1,430 tools |
| OSINT Framework `arf.json` | 1,168 leaves under 248 categories | 1,090 | 1 leaf had no URL |
| Bellingcat `gitbook/tools/*/README.md` | 337 tool dirs; URL parsed in 333 | 278 | 4 READMEs had no parseable URL |
| **Union** | 2,798 | **2,523** | Overlaps: A∩O 200, A∩B 59, O∩B 50, all three 34 |

Consequence: the shipped catalogue (2,264 records at last `catalog validate`)
is a subset of the 2,523 candidate union; counts are reported tiered, never as
a single padded headline.

## Attribution carried in the shipped artefacts

| Artefact | Attribution |
|---|---|
| `data/catalog/tools.jsonl` | CC BY-SA 4.0 attribution to `jivoi/awesome-osint`; OSINT Framework rows from `lockfale/OSINT-Framework` (MIT); descriptions are project-authored |
| `data/catalog/source-manifest.json` | Records source lists, retrieval dates, and licence-review state per source |

## Environment facts (this build machine)

| Fact | Value | Verified |
|---|---|---|
| OS | Parrot Security 7.4 | 2026-10-16 |
| Python | 3.13.5 (venv `.venv/`) | 2026-10-16 |
| `exiftool` / `ffprobe` | installed | 2026-10-16 |
| `tesseract` | NOT installed (OCR reports UNAVAILABLE) | 2026-10-16 |
| Python `is_global` quirks (3.13.5) | `224.0.0.1` multicast → `is_global=True`; `ff02::1` → True; `fec0::1` site-local → True; CGNAT `100.64.0.1` → False | 2026-10-16, measured in REPL |

The last row is why `security/urls.py` uses an explicit deny list (deny
multicast/unspecified/loopback/link-local/reserved/private/`fec0::/10`) rather
than trusting `is_global` alone.

### Refresh 2026-10-19 (post-build audit; web search + GitHub pages, fetched 2026-10-19)

- Sherlock: ~94k stars (93,916–94,448 across sources), MIT, "400+ social
  networks", latest release **v0.16.2 (2026-09-08)**, last push 2026-10-19,
  actively maintained; README warns third-party ParrotOS/Ubuntu 24.04 packages
  are broken; `--ignore-exclusions` "may return more false positives" `[V]`
- Maigret: 39,220 stars, MIT, **v0.6.6 (2026-09-18)**; 5,900 sites claimed /
  **5,203 enabled** in 0.6.6 changelog; auto-updates site DB from GitHub every
  24 h (falls back offline); optional `--ai` profiling calls an external
  OpenAI-compatible API; README claims it "detects and partially bypasses
  blocks, censorship and CAPTCHA" and supports FlareSolverr (Cloudflare
  bypass); ongoing false-positive fixes (CJK regex, HackerNews, Rajce) `[V]`
- SpiderFoot: 23,615 stars, MIT; upstream `pushed_at` 2026-04-13; maintenance
  publicly contested — open issue #1911 "Project Dead?" (2025-01) and claims
  docs moved behind vendor marketing; external PRs still landing (2026-10-16);
  active forks exist (`poppopjmp/spiderfoot` "Codename Mirage", 201 stars,
  rewritten stack; `Jaheay/spiderfoot`) `[V]` (fork health `[U]`)
- Practitioner-survey page (Bellingcat 2022, above) re-fetched and quotes
  re-read 2026-10-19 `[V]`

Compliance consequence (recorded as a spec boundary, not a competitor jab):
TRACEFIELD must **not** integrate CAPTCHA/Cloudflare-bypass or similar
evasion behaviours (out of scope per master brief); Maigret's bypass features
are noted only to keep the catalogue's descriptions factual.

## External reference verification (2026-10-19, all fetched from primary source)

| Source | Date/version on page | Relevance | Limitation |
|---|---|---|---|
| github.com/OWASP/OWASP-Open-Source-Intelligence-Standard (+ releases) `[V]` | Only release = **v0.1.0** (tag `v0.1.0`, commit `6810c83`); release body says "released 2026-08-05", GitHub publish timestamp **2026-08-10 14:49** | Ten requirements + one acceptance test each, machine-readable requirements/tests JSON; CC BY-SA 4.0 (no text copying) | Two plausible dates — record both; re-verify tag at publication |
| w3.org/TR/prov-primer/ `[V]` | W3C Working Group Note, **2013-04-30** (latest published version) | PROV vocabulary behind D14 conceptual mapping | Note, not a Recommendation (its siblings PROV-DM/O are Recs of same date) |
| OWASP Secrets Management Cheat Sheet `[V]` | undated living doc | Applies to future collection-credential handling | No date to pin |
| OWASP SSRF Prevention Cheat Sheet `[V]` | undated living doc | Validate-then-connect + deny-list posture matches our F1 fix direction (disable/validate redirects, pin after resolve) | No date to pin |
| scorecard.dev (OpenSSF Scorecard) `[V]` | "launched November 2020"; 18 checks | Dependency/repo hygiene signal for vetting | Moving target, no version on page |
| GitHub Docs "About READMEs" `[V]` | undated | README placement/precedence conventions | Undated |
| clig.dev (CLI Guidelines) `[V]` | undated living guide | Exit codes, stdout/stderr split, `--json`, no prompt on non-TTY — TRACEFIELD conforms today | Undated |

## Open external questions (must re-verify before any release claim)

- OWASP OOVS current version/tag at the time the mapping doc is published
  (2026-10-19: still v0.1.0 only release; date ambiguity 08-05 body vs 08-10 publish).
- Competitor stars/`pushed_at` drift (any release notes must re-run the matrix
  script rather than copy these numbers).
- Bellingcat toolkit licensing (still no repo-root license file as of
  2026-10-16; do not assume redistribution rights).
- Whether Python ≥3.14 changes `ip.is_global` semantics (re-run the quirk
  measurements on each Python minor before widening the support matrix).
- **Unresolved lead (2026-10-19):** the penultimate research prompt references
  "a GitHub repository containing 200+ OSINT tools" chosen by the user, but no
  URL/name appears in either prompt, anywhere in the checkout (grep: no
  matches), or in local context. Per that prompt's own rule ("do not guess"),
  this is logged as an unresolved question: **the user must supply the URL**
  before it can be inspected and entered into `COMPETITOR_MATRIX.md`.
