# TRACEFIELD — Competitor Matrix

> All rows verified against primary sources (GitHub REST API, raw LICENSE/README
> files, product sites) on **2026-10-16** by the competitive-intelligence review
> stream (Team B, `teams/team_b_adoption.md` §B1.2). Stars and `pushed_at` are
> point-in-time snapshots; treat them as dated facts, not current values.
> `[V]` = verified from a primary source on the check date. `[U]` = unverified.
> **Refresh 2026-10-19 (post-build audit):** Sherlock / Maigret / SpiderFoot
> rows re-verified via GitHub pages + release data (see `RESEARCH_REGISTER.md`
> §Refresh 2026-10-19); other rows unchanged from 2026-10-16.

## Verified matrix

| Tool | License (as verified) | Last activity (`pushed_at`) | Stars @ 2026-10-16 | Free / keyless | Key capabilities (verified only) |
|---|---|---|---|---|---|
| **Sherlock** (`sherlock-project/sherlock`) | MIT (LICENSE text verified) `[V]` | 2026-10-19 (page fetch) `[V]` | ~94k (93,916 GitHub page @ 2026-10-19) `[V]` | Free; keyless per README `[U]` (keys not stated) | Username hunting across "400+ social networks" (site claim); pipx/docker/dnf install; v0.16.2 (2026-09-08); README warns broken third-party ParrotOS/Ubuntu packages; `--ignore-exclusions` may raise false positives `[V]` |
| **Maigret** (`soxoj/maigret`) | MIT ("Copyright (c) 2020-2026 Soxoj") `[V]` | 2026-10-14T16:10:52Z (API, 2026-10-16); release v0.6.6 2026-09-18 `[V]` | 39,220 `[V]` @ 2026-10-19 | Free; README: "No API keys required" `[V]` | Dossier-by-username, 5,900 sites claimed / 5,203 enabled (0.6.6); DB auto-update every 24 h (offline fallback); optional `--ai` external API; **"partially bypasses" blocks/CAPTCHA + FlareSolverr support — evasion features TRACEFIELD must not integrate** `[V]` |
| **SpiderFoot** (`smicallef/spiderfoot`) | MIT `[V]` | upstream 2026-04-13T19:43:06Z (API, 2026-10-16) `[V]` | 23,543 (2026-10-16) → 23,615 (2026-10-19) `[V]` | Free self-hosted; some modules need API keys; HX is paid cloud | Web UI + CLI, "over 200 modules", YAML correlation (37 rules), SQLite, CSV/JSON/GEXF export, TOR; **maintenance contested**: issue #1911 "Project Dead?" (2025-01), docs-vendor-marketing complaints, external PRs still landing 2026-10; active forks `poppopjmp/spiderfoot` (Mirage rewrite) and `Jaheay/spiderfoot` `[V]` (fork health `[U]`) |
| **theHarvester** (`laramies/theHarvester`) | GPL-2.0 `[V]` | 2026-10-14T05:13:58Z | 17,981 | Free; some passive sources keyless `[V]` | Emails/subdomains/hosts/IPs/ASNs harvest; CLI + HarvestView evidence-review UI + local REST API; requires Python 3.14 + `uv` |
| **holehe** (`megadose/holehe`) | GPL-3.0 `[V]` | 2024-09-10T20:24:32Z | 15,219 | Free | Email→registered-sites check; quiet >2 years at check date |
| **ExifTool** (exiftool.org; mirror `exiftool/exiftool`) | Upstream: Artistic/GPL dual ("same terms as Perl itself"); GitHub mirror detected GPL-3.0 — **discrepancy recorded** `[V]` | mirror 2026-05-27; upstream release 13.59 (2026-05-27) | 5,169 (mirror) | Free, keyless, offline | Metadata read/write for a very large format set, `-json`, geolocation DB, MD5/SHA256/SHA512 of image data, C2PA/JUMBF read |
| **OSINT Framework** (`lockfale/OSINT-Framework`) | MIT ("Copyright (c) 2017 Justin Nordine") `[V]` | 2026-10-10T14:48:55Z | 12,292 | Free web index, keyless | D3 tree of free OSINT resources; OPSEC notes; community ratings; dead-link/paywall reporting |
| **Bellingcat Online Investigation Toolkit** (`bellingcat/toolkit`) | **No license file at repo root** → redistribution terms `[U]` | 2026-10-08T05:36:45Z | 682 | Free to read; per-tool cost field | 337 tool pages + 59 category pages `[V]`; staff-checked; explicit no-endorsement disclaimer |
| **Awesome OSINT** (`jivoi/awesome-osint`) | GitHub API: NOASSERTION; `LICENSE.txt`: **CC BY-SA 4.0** `[V]` | 2026-10-15T06:51:52Z | 30,275 | Free list, keyless | Curated markdown list: 1,527 list items, 1,473 http(s) links, 1,437 unique raw URLs `[V]` |
| **WhatsMyName** (`WebBreacher/WhatsMyName`) | CC BY-SA 4.0 ("Copyright (C) 2015-2026 Micah Hoffman") `[V]` | 2026-10-15T14:55:30Z | 2,952 | Free | Curated site list + detection patterns for username enumeration |
| **IntelX** (intelx.io) | `[U]` | `[U]` | n/a | `[U]` | Site reachable (HTTP 200); everything else unverified in this pass |
| **namechk.com** | `[U]` | `[U]` | n/a | `[U]` | HTTP 403 to automated fetch; third-party mirror `GONZOsint/Namechk` (616 stars, last push 2021-03-23) of unknown relationship |

## Capability overlap (implemented TRACEFIELD surface only)

| TRACEFIELD implemented capability | Already done by | What they have that we do not | What we have that they do not (as verified) |
|---|---|---|---|
| `hash` / `inspect [--deep]` (signature, hashes, exiftool/ffprobe backends) | ExifTool (far deeper), ffprobe, `file(1)`, `sha256sum` | Thousands of tags, write support, geotagging, diffing | Honest backend status strings + explicit "metadata does not prove authenticity" caveat in the same output; hash bound to a case, re-verifiable via `evidence verify` |
| `ocr <image>` (local tesseract wrapper) | Any tesseract wrapper | Real OCR quality engineering (deskew, languages, psm) | Provenance binding: OCR result stored with `source_sha256` and method `"tesseract-local"` |
| Case lifecycle + claims + evidence with SHA-256 + hash-chained events | SpiderFoot (SQLite scan store), theHarvester (HarvestView run history), Atlos (Bellingcat category listing) | Mature collectors with a decade of modules; investigator UX | Collection opt-in; every stored artifact carries integrity data and a `prev_digest` chain; "hashes prove bytes, not truth" stated in the product |
| Case export + integrity manifest + redaction | SpiderFoot export; archiving pipelines (Auto Archiver, Archive.today) | Dedicated archiving | Manifest is a verification contract (`verify_manifest` re-hashes exported bytes); default redaction; GPS-bearing files listed in `SENSITIVE_METADATA.txt` without rewriting binaries |
| Tool catalogue with health/tier states | OSINT Framework (OPSEC notes, community ratings, dead-link reports), Bellingcat (337 staff-checked pages), Awesome OSINT (1.4k links) | Human editorial processes TRACEFIELD cannot match at alpha | Machine-checkable **tiered** states distinguishing listed/verified/integrated/healthy, with per-entry `last_checked` |
| Conservative username checks (opt-in, curated providers, no HTTP-200-as-match) | Sherlock (94k stars), Maigret, WhatsMyName, holehe | 10–1000× more sites; years of false-positive engineering | Deliberate smallness: soft-404 marker rules, 1 req/s politeness, backoff on 429/403/5xx, "existence of a public handle is NOT identity attribution" |
| `doctor` (local-only environment check, never network) | — (not standard in checked tools) | — | Genuine small differentiator; kept network-free |
| `tui` (Textual) | SpiderFoot web UI, theHarvester HarvestView | Mature GUIs | Optional layer; every feature also has a CLI path |

## Explicitly NOT novel — never market these as innovations

Content hashing; EXIF/ffprobe metadata reading; tesseract OCR wrapping; "a big
list of OSINT tools"; username enumeration; case folders; read-only
content-addressed evidence copies (git and other CAS designs predate this
project); SQLite storage; JSON output; redaction of secrets.

## Defensible (as implemented today)

A single local-first CLI in which (a) network is off by default with a
dedicated exit code, (b) every finding is re-verifiable from the case
directory without the tool, (c) catalogue claims are tiered and dated, and
(d) output routinely states what a number does *not* prove.

## Differentiation thesis (verbatim-usable)

> TRACEFIELD is not a collector and not another list. It is the **provenance
> and continuity layer between collection and the report**: you keep using
> Sherlock, Maigret, SpiderFoot, ExifTool and the Bellingcat toolkit —
> TRACEFIELD stores what they produced as hash-addressed, re-verifiable
> evidence under a scoped case, records the chain of actions, refuses to
> grade truth as a probability, and exports a bundle whose integrity anyone
> can re-check with `sha256sum`. Its catalogue's honesty is that it counts
> what it has *not* verified.

Positioning corollaries:

1. **Complement, don't compete.** Sherlock/Maigret/SpiderFoot are upstream
   collectors; the catalogue ships "how to pipe their output into a TRACEFIELD
   case", it does not re-implement them.
2. **The catalogue is a trust artefact, not a feature checklist.** OSINT
   Framework and Bellingcat win on breadth and editorial quality; TRACEFIELD
   can only win on machine-checkable honesty (dated checks, state tiers, licence
   provenance).
3. **Zero-claims beats feature-claims at alpha.** Any "more powerful than X"
   claim is falsifiable by a five-minute trial; the honest pitch is the
   case/evidence/provenance contract.

## Catalogue scale reality (measured 2026-10-16)

| Source | Raw rows | Unique after normalization |
|---|---|---|
| Awesome OSINT | 1,473 http(s) links | 1,430 |
| OSINT Framework (`arf.json`) | 1,168 leaves | 1,090 |
| Bellingcat toolkit | 337 tool dirs | 278 |
| **Union (deduped)** | 2,798 raw | **2,523** |

Therefore: 800+ deduplicated *candidate* records is achievable; 800+
*verified + installable + integrated + healthy* is not credible at alpha. The
launch metric must be tiered counts, never a single padded number.

## Licence hazards (why rows are links + project-authored prose)

| Source | Verified licence | We may | We must not |
|---|---|---|---|
| OSINT Framework | MIT `[V]` | Reuse with attribution | Imply endorsement |
| Awesome OSINT | CC BY-SA 4.0 `[V]` | Link; write our own factual summaries | Copy list prose/structure into a share-alike-free dataset |
| Bellingcat toolkit | No license file `[V]` | Link; cite names | Copy descriptions/CSV/images; treat the public CSV as redistribution-cleared |
| WhatsMyName | CC BY-SA 4.0 `[V]` | Link; attribute Micah Hoffman | Wholesale import of detection-pattern JSON into a differently-licensed dataset |
| Upstream tools | GPL-2.0/3.0/MIT mixed `[V]` | List, link, describe factually | Bundle GPL code into TRACEFIELD (Apache-2.0) without a separate process |
