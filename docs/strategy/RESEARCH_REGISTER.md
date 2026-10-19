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

## Open external questions (must re-verify before any release claim)

- OWASP OOVS current version/tag at the time the mapping doc is published.
- Competitor stars/`pushed_at` drift (any release notes must re-run the matrix
  script rather than copy these numbers).
- Bellingcat toolkit licensing (still no repo-root license file as of
  2026-10-16; do not assume redistribution rights).
- Whether Python ≥3.14 changes `ip.is_global` semantics (re-run the quirk
  measurements on each Python minor before widening the support matrix).
