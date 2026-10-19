# TEAM D — Rapid access, integration, protection

> Simulated role-based review conducted by independent review subagents on 2026-10-16. These are role perspectives, not interviews with real people. External facts were verified via live web checks on this date where marked.

**Review target:** repository working tree at the project root (version `0.1.0`, Python 3.13 venv present).
**Method:** static reading of every file named below, plus black-box runs of the installed `tracefield` console script against a scratch `TRACEFIELD_HOME`, plus live HTTP GETs to the public pages named in D2/D3 (all dated **2026-10-16**). Anything not observed or not sourced is marked **unknown**.
**Cross-cutting observation (applies to all five roles):** `tests/` is **empty** (0 test files) even though `pyproject.toml` defines pytest markers including `security` and `network`, and `filterwarnings = ["error"]`. Every acceptance criterion below is therefore currently unenforced.

---

## D1. Fast Field Utilities Engineer

### 1.1 What actually exists

| Capability | Entry point | Notes |
|---|---|---|
| `hash` | `cli/main.py:638-647` → `fieldtools/inspect.py:335-352` | streams, `--json` |
| `inspect` (+`--deep`) | `cli/main.py:650-661` → `inspect.py:295-332` | magic-byte type, sha256/sha512/md5, fs times, optional exiftool/ffprobe |
| `ocr` | `cli/main.py:664-672` → `fieldtools/ocr.py:39-63` | Tesseract only; honest `UNAVAILABLE` (exit 5) |
| `username check` | **does not exist** | advertised by TUI at `tui/app.py:213`; setting `username_check_enabled` (`config/settings.py:44,71-72`) is parsed and never read by any code path |
| `tools search` | **does not exist** | advertised by TUI at `tui/app.py:256` and `tui/app.py:268` |

Measured: `tracefield username check alice` → `No such command 'username'` (exit 2); `tracefield tools search exiftool` → `No such command 'tools'` (exit 2). Both verified 2026-10-16.

### 1.2 Output-consistency (`--json` parity) audit — measured

| Command | `--json`? | Parity defect observed |
|---|---|---|
| `doctor` | **no** — `emit({...}, False, render)` hardcodes `False` (`cli/main.py:200`) | scripts cannot parse doctor |
| `init` | no (`cli/main.py:205-217`) | — |
| `case create/list/show`, `source add/list`, `claim add/list`, `evidence attach/list/verify` | yes | errors always human-only: `fail()` (`cli/main.py:86-88`) prints red text, never JSON |
| `hash` | yes | **error path emits no JSON**: `hash README.md -a notahash --json` → `error: unsupported hash algorithm: notahash`, exit 1, zero JSON (`inspect.py:338-342`) |
| `inspect` | yes | directory input → raw `IsADirectoryError` traceback, exit 1 (observed on `inspect /tmp`) |
| `ocr` | yes | **exit-code parity broken**: `ocr README.md --json` → JSON with `"status": "UNAVAILABLE"` and **exit 0**; human mode exits **5** (`ocr.py:51-57`). Scripts that gate on exit codes silently treat "no backend" as success |
| `report` | `--format json` only (`cli/main.py:683-685`) | different flag name than every other command; no `--json` alias |
| `case-export`, `case-delete` | no | — |
| usage errors | — | `tracefield inspect /nonexistent` and `tracefield case show nosuch` both exit **2**; `EXIT_NOT_FOUND = 2` (`cli/main.py:48`) collides with Click/Typer's usage-error code 2. "bad invocation" and "case missing" are indistinguishable to scripts |

Also observed: `evidence attach <directory>` — `dir_okay=True` (`cli/main.py:516`) — reaches `hash_file` on a directory and dies with a raw `IsADirectoryError` traceback (exit 1).

### 1.3 Correctness/gap findings inside the utilities

1. **Triple full-file read per `inspect`.** `inspect_file` calls `hash_file` once for sha256, once for sha512, once for md5 (`inspect.py:252-257`) — three complete I/O passes. A single-pass multi-hash (`hashlib` objects created up front) is strictly better and trivial.
2. **JSON detection is both weak and contains dead code.** `inspect.py:76-83`: `json.loads(head.decode(...) + "0" * 0)` — the `+ "0"*0` is a no-op; only the first 512 bytes are parsed, so any JSON document whose first value exceeds 512 bytes (almost all API payloads) fails the probe and falls through to `text/plain`. The comment says "conservative", but the net effect is that `application/json` is almost never reported.
3. **`BM` magic is over-broad.** `inspect.py:32` maps any file starting with `BM` to `image/bmp`; countless non-images (e.g. files whose first two bytes are the ASCII letters `BM`, some text/binary formats) misreport. No secondary validation (e.g. DIB header size at offset 14).
4. **Empty file → `text/plain`.** `_looks_like_text` returns `True` for empty input (`inspect.py:91-92`); observed: 0-byte file reports `detected_media_type: text/plain`. Arguably should be `application/octet-stream` or an explicit `empty` marker.
5. **Tesseract argv lacks `--`.** `ocr.py:22` builds `["tesseract", str(path), "stdout", "-l", lang]` with no `--` before the path, unlike the exiftool/ffprobe calls which correctly use `--` (`inspect.py:168`, `inspect.py:191`). A file whose name begins with `-` (e.g. `-c`, `--version`, or a crafted tessedit option string) is parsed by Tesseract as flags. `lang` is also unvalidated at the function boundary (`ocr.py:17`), though not yet exposed as a CLI flag.
6. **OCR text is redacted but never sanitized for the terminal.** `ocr.py:36` returns `redact_secrets(out)` and `ocr.py:62` prints it raw. Control characters (including form feed `0x0c`, which Tesseract does emit between pages) and Rich markup (`[bold]...`) in OCR output reach the terminal/render pipeline unfiltered.
7. **`ocr_pdf_first_page_placeholder` is dead code** (`ocr.py:66-75`) — no caller anywhere (`grep` over `src/` returns only the definition). PDF OCR is honestly absent, which is fine, but the placeholder should either be wired to a CLI message or removed.
8. **Rich markup injection in the displayed filename.** `inspect.py:302` does `console.print(f"[bold]{result['filename']}[/bold]")` with no `rich.markup.escape`. Observed: a file literally named `x[bold red]INJECTED.txt` renders as `xINJECTED.txt` — the tool **misreports the filename of record in human output** (JSON output is unaffected). For a provenance tool this is a falsification bug, not cosmetic.
9. **GPS warning is `--deep`-only.** `find_gps` runs only under `deep=True` (`inspect.py:259-275`). A plain `inspect` on an image never surfaces the "SENSITIVE: GPS present" warning; the export path strips GPS on export only (`reporting/export.py:35-47`, gated by `strip_precise_gps_on_export` which is set in `Settings` but **never read** — `settings.py:49`).

### 1.4 Named gaps (from the role brief)

- **Perceptual duplicates: absent.** No pHash/dHash/aHash anywhere; `hash` offers md5/sha256/sha512 only (byte-identical). Near-duplicate image triage (the single most common field need after "is this the same file") has no path.
- **Archive listing: absent.** Magic bytes recognise zip/rar/7z/gz/bz2/xz (`inspect.py:41-46`) but nothing lists contents. There is no `zipfile`/`tarfile` usage, no entry count, no compression-ratio check (which matters for the archive-bomb question in D4), no nested-type summary.
- **PDF metadata: backend-only.** PDFs get metadata only via `exiftool --deep` when installed; there is no stdlib fallback for the PDF `Info` dictionary, `%PDF-ID`, XMP block, or page count. With exiftool missing (observed on this machine: `doctor` reports `missing`), `inspect --deep --json` on a PDF yields `embedded_metadata: null` with no explanation inside the JSON beyond `backends.exiftool: unavailable`.

### 1.5 Proposed implementation order

1. **P0 — contract fixes (no new features):** (a) make every command emit JSON on error and unify exit codes (`EXIT_USAGE=3` must not be shadowed by Click's 2 — set `app = typer.Typer(...)` and catch `click.UsageError` in `run()`); (b) fix `ocr --json` exit parity (`ocr.py:51-57` — decide: JSON emitted **and** nonzero exit); (c) reject directories explicitly (`dir_okay=False`) for `hash`/`inspect`/`ocr`, and add the missing `--` before the Tesseract path; (d) `rich.markup.escape` every attacker-influenced string before `console.print`.
2. **P1 — high-value local additions:** archive inventory (`zipfile`/`tarfile` stdlib now, `7z l`/`unrar l` via the existing `run_backend` allowlist), native PDF Info/XMP fallback, single-pass multi-hash, optional `--limit`/TSV output for scripting.
3. **P2 — perceptual hashes:** optional extra (`imagehash` + `Pillow`), `inspect --phash`, output must carry the caveat "similarity score, not identity" and a threshold default that errs toward "no match".
4. **P3 — batch mode:** `inspect --dir`/`hash --dir` with explicit `--max-files`, streaming NDJSON (one object per line) rather than a pretty-printed array, and a progress line only when stderr is a TTY.

### 1.6 Risks

- Shipping `username` as a library-only feature while the TUI advertises a command that does not exist will burn trust on first contact (verified failure above).
- Exit-code collision (2 = both usage error and NOT_FOUND) makes TRACEFIELD unusable as a reliable pipeline citizen — the README promises "deterministic exit codes".
- Markup/escape injection means human output can be *wrong*, which for an evidence tool is worse than crashing.

### 1.7 Recommendations

- Adopt a single `emit_result(payload, ok, exit_code, as_json)` helper used by all commands; forbid ad-hoc `console.print` of untrusted strings (lint rule / `ruff` plugin).
- Add `EXIT_CONTRACT.md`-style table to the README and a test that asserts every command's `(stdout schema, exit code)` for success, not-found, unavailable, and usage-error.
- Expose `--lang` for OCR only after validating against `^[a-z0-9_+-]{1,32}$` and passing `--` before the path.

### 1.8 Open questions

- Should `inspect` default to `--deep` when the backends are installed, or stay opt-in? (Field speed vs. accidental metadata exfil into notes.)
- Is md5 retained purely as an "identification aid" (`inspect.py:257`)? If yes, document that it is emitted for cross-dataset matching and never for integrity.
- Who owns the `username` CLI: this role (surface) or D2 (semantics)? It currently belongs to neither.

### 1.9 Testable acceptance criteria

1. `tracefield ocr <img> --json` with no Tesseract returns exit 5 **and** a JSON object with `status=UNAVAILABLE`.
2. `tracefield hash <file> -a bogus --json` emits a JSON error object (not bare text).
3. `tracefield case show missing --json` exits 3 (usage) or a dedicated code, never 2; `case show` of a missing-but-valid-ref exits 2 only.
4. `inspect` on a directory exits with a clean one-line error, no traceback.
5. A file named `x[bold red]y.txt` is displayed (human mode) with the literal brackets.
6. `inspect` on a 1 GiB file performs exactly one read pass (assert via mocked `Path.open` call count).
7. `archive inventory` on a 3-entry zip reports 3 entries, total uncompressed size, and total compressed size without extracting.

### 1.10 Challenged assumption

*"The field utilities are basically JSON-parity-complete."* **Disproved.** Six of thirteen user-facing commands have no `--json`; every error path is human-only; `ocr --json` silently reports exit 0 for UNAVAILABLE; `doctor` is hardwired to `False` at `cli/main.py:200`.

### 1.11 Concrete failure mode

An analyst scripts `tracefield ocr shot.png --json > out.json && jq -r .text >> notes.md` on a machine without Tesseract: the command exits 0, `out.json` contains `"status":"UNAVAILABLE"` with no `text` key, `jq -r .text` yields empty, and the notes silently omit that OCR never ran — months later the omission is indistinguishable from "the image had no text".

---

## D2. Public Username Search / Identity-Correlation Engineer

### 2.1 Design summary under review

`fieldtools/username.py` (276 lines): one username per invocation, five curated providers (`username.py:45-83`), state machine `UsernameResultState` (`core/domain.py:84-94`), classification in `_classify` (`username.py:108-185`), fixed 1.0 s inter-request sleep (`username.py:22,229,240,247`), `trust_env=False` (`username.py:211`), caveats block (`username.py:266-274`). **There is no CLI command** (see D1 §1.1), so today the only caller is a Python REPL — and `username_check_enabled` (`settings.py:44`) is never checked.

### 2.2 Per-provider verification-state review (live checks 2026-10-16)

| Provider | Rule as coded | Live observation today | State mapping works? | Confidence |
|---|---|---|---|---|
| **github** (`username.py:46-52`) | 404 status ⇒ `NOT_FOUND_VERIFIED`; 200 + `'"profile"'`/`'itemprop="additionalName"'` ⇒ `CONFIRMED` | Missing user `https://github.com/zzztracefieldnonexistent987654` → **HTTP 404** (verified). Real profile `https://github.com/torvalds` → 200, **both markers present** in the 213 KB HTML (verified) | Yes, today | **Medium-high for existence, zero for identity.** Both markers are single points of failure in a large SPA payload; failure mode is fail-safe (falls to `LIKELY_MATCH`), which is acceptable |
| **gitlab** (`username.py:53-59`) | 404 ⇒ not-found; 200 + `gitlab-activity`/`js-user-profile` ⇒ confirmed | Missing user returned **HTTP 403** to this client (verified) — i.e. the rule never gets to test its markers; result would be `BLOCKED` | Mapping is correct, but the provider is **effectively non-functional unauthenticated** from many networks | **Low / unknown.** Markers untested |
| **reddit** (`username.py:60-68`) | `about.json`; requires `"kind": "t2"`; `presence_on_200=False` | `https://www.reddit.com/user/zzz.../about.json` → **HTTP 403** (verified). Official Reddit help states traffic "not using OAuth or login credentials will be blocked" ([Reddit Data API Wiki](https://support.reddithelp.com/hc/en-us/articles/16160319875092-Reddit-Data-API-Wiki), accessed 2026-10-16) | Correctly yields `BLOCKED`; but the provider should be labelled OAuth-only or removed | **Low.** The `kind=t2` design is sound; the transport is dead |
| **hackernews** (`username.py:69-75`) | soft-404 marker `"No such user."`; found markers `"user:"`,`"created:"` | `https://news.ycombinator.com/user?id=zzz...` → **200 with body "No such user."** (verified) — exactly as documented | Yes | **Medium.** See false-positive hazard below: the marker is attacker-settable (a real user's About text) |
| **keybase** (`username.py:76-82`) | not-found markers `("404", "Sorry, we can't find")`; found `('"basics"', "keybase.io/")` | `https://keybase.io/zzz...` → **HTTP 404** (verified), so status path saves it | Partially | **Low.** The soft-404 marker `"404"` is catastrophically generic: any 200 page containing the substring "404" (JS chunk names, build hashes, footer links) is classified `NOT_FOUND_VERIFIED` for a **real** profile |

### 2.3 False-positive and soft-404 handling

**Strengths.** 429 → `RATE_LIMITED`, 401/403 → `BLOCKED`, 5xx → `PROVIDER_ERROR`, 404 → `NOT_FOUND_VERIFIED`, all with explicit `limitations` strings (`username.py:110-141`); soft-404 markers are checked **before** found markers (`username.py:143-151`), which is the correct precedence; `presence_on_200=False` for reddit forces a marker (`username.py:66`).

**Defects.**

1. **Substring matching on attacker-controlled bodies.** `marker.lower() in body.lower()` (`username.py:144,152`) means a *page owner* can flip the result. Concrete: an HN user whose About field literally contains `No such user.` is reported `NOT_FOUND_VERIFIED`. A Keybase profile whose HTML contains `404` anywhere is reported `NOT_FOUND_VERIFIED`. These are false negatives on real people — the worst direction for an OSINT tool that others will treat as "cleared".
2. **"Invalid for this platform" is conflated with "confirmed absent".** `_USERNAME_RE` (`username.py:85`) allows dots and a 39-char cap for all providers. GitHub usernames cannot contain dots (platform rule, not re-verified today — **unknown**), so `foo.bar` yields GitHub 404 → `NOT_FOUND_VERIFIED`. That is an overclaim: the correct state is "this identifier is not even valid here". Recommend a `NOT_APPLICABLE`/`INVALID_FOR_PLATFORM` state, or per-provider regex.
3. **`url` field construction.** `_classify` builds `rule.url_template.format(username="")` (`username.py:109`) and relies on the caller to overwrite it (`username.py:244`). Fragile but currently correct; a future early-return path would publish a URL with an empty username.
4. **Final-URL is recorded but never inspected** (`username.py:245`). A 200 that redirected to a login/interstitial page (common for bot challenges) is still classified as a profile when markers accidentally match. Recommend: `CONFIRMED` only if `final_url` host still matches the provider's expected host.

### 2.4 Rate limiting

- Fixed 1.0 s sleep, no jitter, no `Retry-After` handling, no per-provider cooldown state, no daily budget, no shared limiter between invocations (each call builds a fresh `httpx.Client`, `username.py:206-212`).
- Worst case for one username: 5 providers × (10 s timeout + 1 s sleep) ≈ **55 s** of blocking with no progress output and no cancellation path other than SIGINT (which will surface as a traceback — no handler).
- Politeness gap: `USER_AGENT = "tracefield/0.1 (public-profile existence check; contact: local)"` (`username.py:23`) has no contactable identity; the Internet Archive explicitly requires descriptive, versioned, contactable UAs for automated access ([archive.org/developers/bots.html](https://archive.org/developers/bots.html), accessed 2026-10-16) — other providers increasingly expect the same.
- **No caching**: identical lookups re-hit providers, wasteful and needlessly distinctive.

### 2.5 Identity-overclaiming prevention

Genuinely good: `check_username` docstring ("Never claims two accounts belong to the same person", `username.py:196-199`), and the three caveats (`username.py:266-274`) are the right words. **But**: five `CONFIRMED_PUBLIC_PROFILE` rows side by side is, psychologically, a correlation table. There is no field that says "these results are independent existence checks with no linkage asserted", and nothing in the output schema prevents a future caller from computing an aggregate "identity score". Recommendation: add an explicit `"linkage": "none-asserted"` member to the payload and a lint-level rule in code review that forbids any aggregate verdict.

### 2.6 Non-bulk default assessment

The *stated* constraint ("One username per interactive invocation by default; no bulk mode", `username.py:4`) is **not enforced anywhere**: `check_username` accepts a single string, but nothing stops a loop; there is no per-process request counter, no refusal path, and (because the CLI command doesn't exist) no interactive gate at all. As shipped, the "non-bulk" property is a comment. Enforcement options: module-level token bucket (e.g. max 20 provider-requests/hour default), hard `MAX_PROVIDER_REQUESTS_PER_RUN`, and an explicit `TRACEFIELD_ALLOW_BULK=1` opt-out that is never set by default.

### 2.7 Risks

- Markers rot silently; `checked_at` is mentioned in a comment (`username.py:44`) but **does not exist in the output schema** (`username.py:252-275`) — stale rules are indistinguishable from verified-today rules.
- Reddit/GitLab BLOCKED-from-many-networks means the curated set degrades to "GitHub + HN" in practice, while the output still looks comprehensive.
- Unbounded body read (below) makes each provider request a memory-exposure vector.

### 2.8 Recommendations

1. Replace keybase's `"404"` marker with something structural (or drop keybase); anchor HN's marker to the page's `<body>`-level rendering, or switch HN to the official Firebase endpoint `hacker-news.firebaseio.com/v0/user/<id>.json` (existence = non-null; **endpoint behaviour not re-verified today — unknown**).
2. Switch GitHub/GitLab to official APIs: GitHub REST `GET /users/{username}` (60 req/h unauthenticated per IP — [GitHub REST rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api), accessed 2026-10-16); GitLab `GET /api/v4/users?username=` (GitLab.com allows 500 unauth req/min per IP — [GitLab.com rate limits](https://docs.gitlab.com/user/gitlab_com/rate_limits/), accessed 2026-10-16). Official APIs return 404 vs 200 structurally — no marker guessing.
3. Add `checked_at` and `rule_version` to every `ProviderResult`.
4. Validate `final_url` host against the provider's expected host before `CONFIRMED`.
5. Enforce the non-bulk constraint with a real counter (see §2.6).
6. Handle `Retry-After`, add ±0.3 s jitter, and stream with `client.stream(...)` + a hard read cap (see D4 V3).

### 2.9 Open questions

- Is HTML-marker scraping defensible under provider terms at all, given that GitHub's Acceptable Use Policies explicitly define and restrict scraping ([GitHub Acceptable Use Policies §7](https://docs.github.com/en/site-policy/acceptable-use-policies/github-acceptable-use-policies), accessed 2026-10-16), while GitHub ToS (effective 2026-04-27) push data collection to the API ([GitHub ToS](https://docs.github.com/en/site-policy/github-terms/github-terms-of-service), accessed 2026-10-16)?
- Should `BLOCKED` be terminal for a provider for the rest of the session (recommended) rather than retried on the next invocation?
- Do we want an explicit `SUSPENDED/DELETED` distinction where the platform exposes it (GitHub returns 404 for both never-existed and deleted — **unknown** whether any distinguishing signal exists)?

### 2.10 Testable acceptance criteria

1. Fixture HTML for each provider (existing/absent/ad-challenge) produces the expected state; markers are never re-downloaded in tests (network marker: opt-in only).
2. A HN user whose About contains `No such user.` is **not** classified `NOT_FOUND_VERIFIED`.
3. A Keybase-like 200 body containing the substring `404` is **not** classified `NOT_FOUND_VERIFIED`.
4. `foo.bar` (invalid on GitHub) returns `NOT_APPLICABLE`-class state for GitHub, not `NOT_FOUND_VERIFIED`.
5. `check_username` aborts after N provider requests per process with an explicit `LIMIT_REACHED` state.
6. Every result carries `checked_at`, `rule_version`, and `final_url`-host match boolean.
7. Two `CONFIRMED` rows plus any aggregation attempt must be impossible from the returned schema alone (no aggregate field; `linkage` present).

### 2.11 Challenged assumption

*"HTTP 200 + found_markers ⇒ CONFIRMED_PUBLIC_PROFILE is reliable because markers were hand-verified."* **Challenged on two axes:** (a) the keybase rule as written inverts the guarantee (generic `"404"` substring wins over any found marker), and (b) even for GitHub — where I verified both markers live today — a single SPA re-render converts every `CONFIRMED` into `LIKELY_MATCH` with no alarm, because there is no `checked_at` to age the rule.

### 2.12 Concrete failure mode

An analyst runs a username check on `target_hobby`, gets `CONFIRMED_PUBLIC_PROFILE` on GitHub (real account) and `NOT_FOUND_VERIFIED` on Keybase — except the Keybase profile exists; its current HTML contains the literal string `404` inside a JS bundle. The report states "no Keybase presence", the analyst closes that avenue, and the actual Proton/Keybase-verified identity is never pursued. False negative caused by an unanchored substring marker.

---

## D3. Public API & Provider Reliability Engineer

### 3.1 Provider matrix

Every row was checked against the listed source on **2026-10-16**. "Free" is only asserted where a dated official (or clearly-labelled secondary) source says so. Unverified numbers are **unknown**, never guessed.

| Provider | Intended use | Access method | Auth | Cost / free tier (source, 2026-10-16) | Rate limits (source, 2026-10-16) | Terms / policy notes | Deprecation risk | Uncertainty |
|---|---|---|---|---|---|---|---|---|
| **urlscan.io** | passive URL/domain scan history, screenshots | REST: `GET /api/v1/search`, result API ([docs](https://docs.urlscan.io/apis/urlscan-openapi)) | Optional API key; unauthenticated requests are rate-scoped to `ip-address` ([rate limits doc](https://docs.urlscan.io/pages/api-rate-limits)) | Quota model per action (search, scan submit, etc.); **exact free-tier numeric quotas: unknown** (docs say "check your personal quotas" via `GET /api/v1/quotas`) | Per-action, per-minute/hour/day fixed windows; only HTTP-200 counts against quota; HTTP 429 on exceed; `X-Rate-Limit-*` headers returned ([source](https://docs.urlscan.io/pages/api-rate-limits)) | [Terms](https://urlscan.io/terms/); submitting scans of third-party URLs has policy implications — read-only search is the safe field mode | Low-moderate: actively maintained docs (result API page dated 2026-06-12) | Free-tier numbers unknown; do not quote a number in-product |
| **Internet Archive / Wayback CDX** | capture history, snapshot availability | `GET https://web.archive.org/cdx/search/cdx?url=...` ([CDX server README](https://github.com/internetarchive/wayback/blob/master/wayback-cdx-server/README.md)); Availability API `GET https://archive.org/wayback/available?url=` ([IA API page](https://archive.org/help/wayback_api.php)) | None for read | No published price; IA developer portal requires descriptive UA for automated access ([bots page](https://archive.org/developers/bots.html)) | **Official page publishes no number**: "respect 429 / Retry-After, add delays, limit concurrency" ([bots page §Rate Limiting](https://archive.org/developers/bots.html)) — numeric limit **unknown**. Community reports vary (≈60/min CDX average claimed in a 2023 project issue; treat as **unverified anecdote**) | IA asks for identifiable bots; bulk harvesting policies apply ([bots page](https://archive.org/developers/bots.html)) | Low: CDX documented as BETA for years; IA has litigation/financial pressure (**speculative**) | Numeric limits unknown; keep default client ≤0.5 req/s and honor Retry-After |
| **RDAP** (registry lookups) | domain/IP/ASN registration data | HTTPS JSON per [RFC 9082 (STD 95)](https://www.rfc-editor.org/info/rfc9082) / [RFC 9083 (STD 95)](https://www.rfc-editor.org/rfc/rfc9083.html); bootstrap per [RFC 7484](https://www.rfc-editor.org/rfc/rfc7484.txt) (**obsoleted by RFC 9224** — datatracker status line, accessed 2026-10-16) | None for standard queries; some registries add rate limits | No universal cost model; **per-registry: unknown** | Per-operator, **unknown** generically | gTLD operators are contractually required to offer RDAP (ICANN policy — **not re-verified today, unknown**) | Low: IETF standards-track; bootstrap registry churn is the real maintenance cost | Must implement per-registry timeouts and treat 429/503 as back-off signals |
| **crt.sh (Certificate Transparency)** | subdomain/cert discovery | Unofficial JSON (`https://crt.sh/?q=example.com&output=json`) and a public PostgreSQL listener on :5432 | None | Free to query; **no official SLA** | **Per-IP 5 requests/minute on :443 and 5 concurrent Postgres connections**, stated by crt.sh's operator Rob Stradling on 2023-06-09 ([crtsh Google Group](https://groups.google.com/g/crtsh/c/QXQFoy331pE)); earlier 2020 statement said 60/min ([thread](https://groups.google.com/g/crtsh/c/NZJntKrBdmg)). **Current 2026 value: unknown — re-check before shipping** | No published ToS; the JSON endpoint is explicitly unofficial (community clients document breakage risk, e.g. [certgraph docs](https://pkg.go.dev/github.com/lanrat/certgraph/driver/crtsh)) | Moderate: endpoint is unofficial and reverse-engineered per community docs; operator has warned limits may be lowered further | High uncertainty — treat as best-effort, ≤1 req every 15 s, never in a loop |
| **VirusTotal (Public API)** | hash/URL/domain reputation | REST v3 (`docs.virustotal.com`), API key header | Free API key via community account | **Public API is free**: 500 requests/day, 4 requests/minute; must not be used in commercial products/services; must not be used in business workflows that don't contribute files; no multi-accounting ([Public vs Premium API](https://docs.virustotal.com/reference/public-vs-premium-api), accessed 2026-10-16) | 4/min, 500/day as above; HTTP 204 signals quota exhaustion ([v2 error reference](https://docs.virustotal.com/v2.0/reference/api-responses)) | Non-commercial restriction is explicit — an OSINT tool must surface this to users | Low: v3 is default, v2 "will not be deprorecated" per docs wording (accessed 2026-10-16) | Well-sourced; still re-check at each release |
| **Shodan (free API plan)** | host/banner lookup | REST `api.shodan.io` ([API reference](https://developer.shodan.io/api)) | API key, free with account ([requirements](https://developer.shodan.io/api/requirements); [billing FAQ](https://account.shodan.io/billing): "All Shodan accounts come with a free API plan") | "Free API plan" confirmed; **query-credit allotment for the free plan: unknown** from official pages checked (Membership tier documented at 100 credits/month in [help docs](https://help.shodan.io/guides/how-to-download-data-with-api)); scan credits require a paid plan ([API docs](https://developer.shodan.io/api)) | Not stated numerically on pages checked — **unknown**; search with filters consumes credits ([API reference](https://developer.shodan.io/api)) | Commercial data; redistribution restricted (**policy text not re-verified today — unknown**) | Low-moderate | Never advertise "free Shodan searches" in-product without the credit caveat |
| **GitHub REST** (for identity checks) | profile existence, repo metadata | `GET https://api.github.com/users/{username}` | Optional token | Public data readable unauthenticated; free tier = the 60/hr unauth limit | **60 req/hour unauthenticated per IP**; 5,000/hr with PAT ([official](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api), accessed 2026-10-16) | ToS §H API Terms govern; scraping defined/limited by AUP §7 (both accessed 2026-10-16) | Low | — |
| **GitLab REST** (for identity checks) | username → user object | `GET /api/v4/users?username=` | None needed for public | Public read | **500 unauthenticated req/min per IP**; authenticated API 2,000/min per user ([GitLab.com rate limits](https://docs.gitlab.com/user/gitlab_com/rate_limits/), accessed 2026-10-16) | Standard GitLab ToS (**not re-verified today**) | Low | — |
| **HTTP Archive** | web-technology research | Google BigQuery public dataset (`httparchive.*`) | Google account; billing setup | "First 1 TB per month free" is a **BigQuery platform** fact ([Google Cloud public datasets](https://docs.cloud.google.com/bigquery/docs/public-data)), not an HTTP Archive grant; dataset is petabyte-scale and cost-control guides exist ([getting started](https://httparchive.org/docs/guides/getting-started), [minimizing costs](https://httparchive.org/docs/guides/minimizing-costs)) — all accessed 2026-10-16 | BigQuery quotas apply; **not suitable for a field CLI** | Open-source project; attribution requested | Low | Out of scope for field use; list as research-only |
| **MDN** | documentation | N/A — no data API relevant to field collection | — | — | — | — | — | **Not applicable / unknown**; excluded from integration plans |

### 3.2 Reliability & integration guidance

1. **Prefer APIs over page-scraping for every row where an API exists** (GitHub, GitLab, Reddit-with-OAuth, HN-with-Firebase). Marker scraping (D2) is the highest-churn, highest-false-positive integration class in this matrix.
2. **Provider client shape:** every client must (a) send a descriptive, versioned, contactable User-Agent (IA makes this explicit policy); (b) honor `Retry-After`; (c) treat 429 as *expected*, not exceptional, with exponential backoff + jitter; (d) cap concurrency at 1 for field default; (e) record `checked_at` + `X-Rate-Limit-Remaining` (where provided) into provenance `limitations`.
3. **Key handling:** keys are env-only today (`settings.py:64-72` reads `TRACEFIELD_*` env vars; no config file yet). Never write keys into case DBs, exports, or reports. `catalog.py` already stores `key_env_vars` as *names only* with a validator rejecting `=` (`registry/catalog.py:248-250`) — keep that invariant.
4. **Data-exposure warning field** exists (`catalog.py:80`) but the catalogue is empty (see D4 V13), so no provider currently carries an in-product exposure warning. When populated, urlscan (public scan submissions) and Shodan (banner data) must be flagged passive-with-caveat.
5. **Deprecation watch-list (quarterly re-check):** urlscan free-tier quota values; crt.sh per-IP limit statement (last dated 2023); Reddit unauthenticated JSON endpoints (officially blocked per Reddit help wiki); Shodan free-plan credits; RDAP bootstrap RFC transition (7484 → 9224).

### 3.3 Risks

- Any in-product string like "free provider" without a dated source will eventually be wrong and will push users into ToS violations (VT non-commercial clause is the sharpest edge).
- crt.sh's 5 req/min (2023 statement) means a naive "scan all subdomains" feature will hammer a community resource — this needs a hard client-side limiter, not just documentation.
- Wayback has no published numeric limit; a well-meaning user can still get IP-throttled.

### 3.4 Recommendations

- Land the matrix above as a machine-readable catalogue (`data/catalog/tools.jsonl` — currently **missing entirely**, see D4 V13) with `last_checked` dates, and refuse to render any entry older than 90 days without an "STALE" label (the `IntegrationState.STALE` enum already exists, `catalog.py:42`).
- Build provider adapters as thin wrappers that emit a standard envelope: `{provider, endpoint, auth_required, quota_hint, checked_at, raw_sha256}` so provenance is uniform.
- Ship a `tracefield doctor --providers` (network opt-in) that hits the *quota* endpoints (urlscan `/api/v1/quotas`, VT, Shodan `/api-info`) and reports remaining budget.

### 3.5 Open questions

- Do we accept HTTP Archive as "research-only documentation" only, or is any field integration contemplated? (Recommendation: documentation only.)
- Should RDAP bootstrap be vendored (IANA JSON snapshots, refreshed weekly) to avoid a network dependency at first run?
- Is a ToS-compliance review by counsel required before enabling urlscan scan *submission* (as opposed to search)?

### 3.6 Testable acceptance criteria

1. No catalogue entry may set `pricing_class=FREE`/`FREE_TIER` without a non-empty `source_list` URL and a `last_checked` within 90 days (lint in `Catalog.validate()`).
2. Every provider client passes a stub-server test asserting: descriptive UA, `Retry-After` honored, 429 → backoff, no more than 1 in-flight request.
3. `catalog validate` fails the build if `rate_limits` is empty for any `api_service` entry.
4. A recorded fixture test per provider for the 200/404/429 shapes observed on 2026-10-16.

### 3.7 Challenged assumption

*"These integrations are 'free' and stable enough to build on."* Only two rows are fully sourced-and-dated today (VirusTotal public API 500/day & 4/min; GitHub 60/hr unauth). IA publishes no number, crt.sh's number is a 2023 community post, Shodan free-tier credits are unknown from official pages, and urlscan's free quotas are per-account and undisclosed. Anything else in a pitch deck is a guess.

### 3.8 Concrete failure mode

A user enables a future "enumerate all subdomains via crt.sh" feature; the first run fires 30 queries in 10 seconds against a service operator-limited to ~5 req/min per IP (2023 statement). The user gets HTTP 502s (documented as common under load by the operator), interprets them as "no certificates", and records a false negative in a case — while degrading a shared community resource.

---

## D4. Application Security / Supply-Chain Reviewer

### 4.1 Threat model

**Assets.** (1) Case evidence + database at `~/.local/share/tracefield` (or `TRACEFIELD_HOME`); (2) operator's terminal display integrity (analysts paste hostile strings by trade); (3) operator's network position (SSRF can reach things the operator's browser cannot); (4) any provider API keys introduced later (env-only today); (5) reputation of outputs (this is an evidence tool — forged display == corrupted record).

**Actors.** (A) Hostile content: filenames, HTML titles, provider bodies, EXIF strings, OCR text; (B) hostile network: redirectors, DNS rebinding, malicious providers; (C) hostile case files: a shared/imported SQLite DB or evidence directory from a third party; (D) local multi-user host: another user racing the evidence directory; (E) supply chain: PyPI deps and build backend.

**Boundaries that must hold.** No request to a non-public address under any input; no attacker-controlled bytes altering what the analyst believes the tool printed; no mutation of evidence bytes after `chmod 0o400`; no code execution from catalogue data.

### 4.2 Concrete vulnerabilities and gaps (ranked)

**V1 — SSRF guard bypass: CGNAT / cloud-metadata-adjacent ranges / IPv6 site-local (HIGH).**
`_is_blocked_ip` (`security/urls.py:32-40`) checks private/loopback/link-local/multicast/reserved/unspecified. On Python 3.13 (measured 2026-10-16):
- `100.64.0.1` (RFC 6598 CGNAT) → `is_private=False`, `is_global=False` → **ALLOWED**
- `100.100.100.200` (Alibaba/Tencent-style instance-metadata address, inside 100.64/10) → **ALLOWED** (`http://100.100.100.200/latest/meta-data/` passes `validate_fetch_url` — verified)
- `fec0::/10` deprecated site-local → **ALLOWED** (`http://[fec0::1]/` passes — verified)
Correctly blocked (verified): `127.0.0.1`, `::1`, `0.0.0.0`, `169.254.169.254`, `metadata.google.internal`, `fd00::1`, decimal/hex IPv4 obfuscation (`http://2130706433/`, `http://0x7f000001/`), userinfo tricks (`http://example.com@127.0.0.1/`).
**Fix:** invert the predicate — require `ipaddress.ip_address(...).is_global` (which is False for CGNAT, benchmarking, documentation, site-local, etc.) and *then* keep the explicit denylist; add the measured addresses as regression fixtures.

**V2 — DNS rebinding TOCTOU (HIGH).**
`validate_fetch_url` resolves via `socket.getaddrinfo` (`urls.py:49`), then httpx resolves **again** at connect time (`fetch.py:39-51`); every redirect re-enters the same split (`fetch.py:23-26`). An attacker-controlled name with a short-TTL record can answer the validator with a public IP and the connector with `127.0.0.1`. No pinning, no single-resolution transport.
**Fix:** resolve once; connect to the pinned IP with the original Host/SNI (httpx `extensions={"sni_hostname": host}` + a custom transport mounting the IP), and re-run the check inside the transport for every hop.

**V3 — `check_username` has no URL policy, no redirect re-validation, unbounded body read (HIGH).**
`username.py:206-247`: the client follows redirects (`follow_redirects=True, max_redirects=3`) with **no** call to `validate_fetch_url`, so a 302 from any provider (or a compromised/open-redirector on its domain) sends the tool to `http://169.254.169.254/` or an internal admin panel from the operator's network position. Separately, `body = resp.text[:max_body]` (`username.py:242`) reads the **entire** response into memory first; `max_body=500_000` only truncates afterwards — a hostile endpoint can return gigabytes.
**Fix:** stream with `client.stream(...)`, read at most `max_body+1` bytes, and re-validate every redirect target with the same policy as `fetch.py`.

**V4 — Terminal escape + Rich-markup injection in human output (HIGH for an evidence tool).**
Observed 2026-10-16:
- `source add --case c $'https://evil.example/\x1b[31mFAKE-RED\x1b[0m\n  injected-row-looking-line'` → the ESC sequences are printed **raw** to the terminal (`cli/main.py:398` prints `s['locator']` with no sanitize), and the embedded newline produces a second forged output line.
- Same record in `source list` renders a **two-line table cell**, i.e. a forged extra row (`cli/main.py:433` sanitizes controls but `sanitize_for_terminal` deliberately keeps `\n`/`\t`, `security/sanitize.py:24-28`).
- `inspect` on a file named `x[bold red]INJECTED.txt` displays `xINJECTED.txt` — Rich markup swallowed (`inspect.py:302`; no `rich.markup.escape` anywhere in the codebase).
- Remote HTML `<title>` is extracted (`fetch.py:113-129`), **prepended to `limitations` after redaction** (`fetch.py:98-109`), stored in the DB, then printed raw at `cli/main.py:401` — a remote page title can inject escapes/markup into the analyst's terminal on `source add` (network opt-in required, but that is the whole point of `--fetch`).
**Fix:** one `rich_safe(text)` helper = `sanitize_for_terminal` (with an option to strip `\n` in single-line contexts) + `rich.markup.escape`; use it in every `console.print` of untrusted data; never print `limitations`/`locator`/`title` raw.

**V5 — Default `case-export --redact` crashes; latent evidence-mutation bug (HIGH functional / MEDIUM integrity).**
Observed 2026-10-16: attaching a text file containing `password=Sup3rSecret!` then running `tracefield case-export` (redact defaults **True**, `cli/main.py:708-710`) dies with a raw `PermissionError` traceback at `reporting/export.py:47`. Root cause chain: evidence is `chmod 0o400` (`provenance.py:87`) → `shutil.copytree` preserves the mode (`export.py:30`) → the redaction loop calls `write_text` on the read-only copy. The export directory is left **partial** (evidence + manifest, no reports). If the copy were ever writable (root, umask change, manual chmod), the same code path would **rewrite evidence bytes after the manifest was built from the DB digests** (`provenance.py:187-203`), silently invalidating `verify_manifest` for those files.
**Fix:** redact into *new* files (`*.redacted`) beside the immutable copies, or redact at report-generation time only; never mutate the evidence tree; wrap export in error handling that cleans up partial output.

**V6 — Subprocess hardening gaps (MEDIUM).**
`run_backend` (`inspect.py:136-160`) is argv-only, no shell — good — and exiftool/ffprobe correctly pass `--` before the path (`inspect.py:168,191`). But: (a) the child env inherits ambient `PATH` (`inspect.py:154`), so a hostile `PATH` (or a `PATH` containing `.`) redirects `exiftool`/`ffprobe`/`tesseract` to attacker binaries via `shutil.which` (`inspect.py:145`); (b) the Tesseract invocation omits `--` (`ocr.py:22`), so dash-prefixed filenames become flags; (c) timeouts return `(124, "", "timeout")` but do not kill a grandchildren-spawning backend (exiftool can spawn helpers) — `subprocess.run(timeout=)` kills only the direct child.

**V7 — Unbounded memory on evidence ingest (MEDIUM).**
`attach_file` does `dest.write_bytes(src.read_bytes())` (`provenance.py:86`) *after* already streaming the hash — measured ≈336 MB peak RSS for a 300 MB file (2026-10-16), i.e. the whole file in RAM, read twice. Combined with no size cap, a 5 GB evidence file is a self-DoS.

**V8 — Path traversal via DB-sourced identifiers (MEDIUM, hostile-case-file threat).**
`case_dir = self.root / case_id` (`provenance.py:57-60`) and `path = self.case_dir(case_id) / ev.storage_ref` (`provenance.py:134`) perform no containment check; `case_delete` does `shutil.rmtree(settings.cases_root / case_obj.id)` (`cli/main.py:748-751`); export verification joins `export_dir / "evidence" / entry["storage_ref"]` (`export.py:75`). IDs are locally generated (`domain.py:21-22`, `case_<uuid16>`), so today's CLI cannot produce a traversal — but a **shared/imported case DB** can, and the tool's whole premise is exchanging case material. One `../../..` in `case.id` or `storage_ref` yields arbitrary directory delete (rmtree) or arbitrary file read (verify/hash).
**Fix:** after joining, assert `resolved.is_relative_to(root.resolve())` in `case_dir`, `evidence_path`, `verify_evidence`, `case_delete`, and `verify_manifest`.

**V9 — Redaction engine: corruption bug + coverage gaps (MEDIUM).**
Measured 2026-10-16 against `redact_secrets`:
- `password=Sup3rSecret!` → `password=[REDACTED]word` — the optional group `(word)?` is re-emitted (`redact.py:21,39-40`), corrupting output.
- `api_key: 'tok_...'` → `api_key: [REDACTED]'` (stray quote).
- **Misses:** `sk-…` (OpenAI-style), `AIza…` (Google), `xox[baprs]-…` (Slack), PEM private-key blocks, `X-Amz-Signature`/presigned query params. (JWT and `Authorization: Bearer` *do* work — verified.)
- Reports rendered to stdout (`tracefield report`, `cli/main.py:699`) are **not** redacted at all; only exports are (`export.py:35-37`).
- `source.limitations = f"fetch failed: {exc}"` (`cli/main.py:372`) is stored unredacted.

**V10 — Fetch layer positives (for balance) and residual issues.**
Positives: scheme allowlist + credentialed-URL rejection (`urls.py:69-74`); redirect re-validation via event hook (`fetch.py:23-26,46`); size cap checked *before* buffering the offending chunk (`fetch.py:72-79`); httpx sends `Accept-Encoding: gzip, deflate` and decodes (verified), so the cap applies to **decompressed** bytes; `trust_env=False` blocks ambient proxies/env credentials (`fetch.py:45`); 429/403 refused without retry/circumvention (`fetch.py:58-62`); TLS verification on by default. Residual: User-Agent is malformed — `f"tracefield/0.1 (+{url.split('/')[0]}//)"` yields `tracefield/0.1 (+https://)` (`fetch.py:37`) — and carries no contact string; no explicit `verify=True` pin (an `SSL_CERT_FILE` env change silently re-roots trust even with `trust_env=False`).

**V11 — No crash-free SIGINT path (LOW-MEDIUM).**
No `try/except KeyboardInterrupt` anywhere in the CLI; `pretty_exceptions_enable=False` (`cli/main.py:58`) means SIGINT during a long hash/attach surfaces a raw traceback (not directly observed; by inspection). Exit code would be 1 (or 130 if Python's default propagates) — undocumented either way.

**V12 — Supply chain (MEDIUM).**
`pyproject.toml` pins *ranges* only (`typer>=0.15,<0.28`, `rich>=13.9,<16`, `textual>=8.2,<9`, `pydantic>=2.10,<3`, `httpx>=0.28,<1`); no lockfile, no hashes, no SBOM, no provenance/attestations, no Dependabot/renovate config visible. Build backend `hatchling>=1.25`. Textual is a large dependency pulled in for an optional TUI — correctly lazy-imported (`cli/main.py:771`), but still a supply-chain surface. `filterwarnings=["error"]` and `ruff`/`mypy --strict` configured are genuine positives.

**V13 — Catalogue/data integrity (LOW, but trust-adjacent).**
`registry/catalog.py` is genuinely inert (pydantic validation, `json.loads` only, no `eval`/`exec`/import of content — verified by reading all 251 lines); the `key_env_vars` validator (`catalog.py:248-250`) is a nice touch. Two real problems: (a) `data/catalog/` **does not exist** (`data/` is empty), so the TUI Arsenal workspace always renders "catalogue data not loaded" (`tui/app.py:196-206`); (b) the wheel packages only `src/tracefield` (`pyproject.toml` `[tool.hatch.build.targets.wheel]`), so even if `data/catalog/tools.jsonl` were created it would not ship in an installed package — the TUI's path walk (`tui/app.py:192-195`) works only in an editable checkout.

**V14 — SQLite/OS-level (LOW, unreviewed depth).** `Database` file permissions, WAL mode, and `PRAGMA` hardening were not in this role's file list; flagging as an open question (below). Default `ensure_dirs` uses umask-default `mkdir` (`settings.py:59-61`) — on a shared host, case data may be world-readable.

### 4.3 Abuse cases (concrete)

1. Analyst fetches a hostile URL with `--fetch`; page title contains OSC-52 clipboard-write + fake "[green]verified[/green]" lines → analyst's terminal applies them (V4).
2. Attacker registers `evl-tmp.github.io` page that 302s to `http://100.100.100.200/latest/meta-data/` → any redirect-following fetcher in the operator's cloud VM leaks instance credentials (V1 + V2 + V3).
3. Third party shares a case DB whose `case.id = "../../.ssh"`; analyst runs `case-delete --yes` → `rmtree` traverses out of the data root (V8).
4. Attacker emails a "photo" whose filename is `-c` + option soup → Tesseract interprets flags instead of a filename (V6b).
5. Analyst exports a case containing a screenshot whose EXIF has `password=` in a comment field → export crashes mid-way; the analyst ships the partial bundle without reports (V5).

### 4.4 Security regression test list (to be added to `tests/`, which is currently empty)

1. `validate_fetch_url` allow/deny table including: `100.64.0.1`, `100.100.100.200`, `fec0::1`, `::ffff:127.0.0.1`, `192.0.2.1`, `169.254.169.254`, `metadata.google.internal`, `foo.internal`, `http://0x7f000001/`, `http://2130706433/`, userinfo URLs, `file:`, `ftp:`.
2. Rebinding simulation: stub DNS returning public then loopback; assert fetch aborts (requires pinned-transport implementation).
3. Redirect-hook test: 302 → `http://127.0.0.1/` raises `UrlPolicyError`.
4. Size-cap test: server streams gzip-compressed 100 MB → `FetchError` at `max_fetch_bytes`, peak RSS bounded.
5. `check_username` with a provider that 302s to a private IP → refused; body larger than `max_body` → truncated, memory bounded.
6. Terminal-injection corpus (ESC, CSI, OSC-52, `\n` row forgery, Rich markup, bidi override U+202E, combining marks, wide CJK) through `sanitize_for_terminal`, `source list`, `inspect`, `ocr` output — assert no raw ESC bytes and no markup interpretation.
7. Export: case with secret-looking text → export completes, manifest verifies, evidence bytes unchanged; export failure leaves no partial directory.
8. Traversal corpus: `case.id` and `storage_ref` values with `../` → refused everywhere (`case_dir`, `verify_evidence`, `case_delete`, `verify_manifest`).
9. `redact_secrets` golden tests for: `password=`, `pass=`, `api_key:`, URL creds, Bearer, JWT, AWS AKIA, `ghp_`, plus negatives (prose containing the word "token").
10. Subprocess: `run_backend` refuses to run when `PATH` is hostile; `ocr` on a file named `-l` behaves as a filename.
11. `evidence attach` of a 0-byte file, a symlink to `/etc/hosts`, a FIFO, and a directory → defined errors, no hang, no traceback.
12. Concurrent double-attach of the same bytes → single content-addressed object, `chmod 0o400` holds.

### 4.5 Remediation checklist (ordered)

- [ ] V1: switch to `is_global` + explicit denylist; add the 12-row regression table.
- [ ] V2: pinned-IP transport with SNI/Host preservation; re-validate inside transport.
- [ ] V3: URL-policy + streaming + read cap in `check_username`.
- [ ] V4: `rich_safe()` helper; apply to every untrusted string; strip `\n` in table cells; redact-then-sanitize titles (not prepend-after-redact).
- [ ] V5: never mutate export evidence; write redacted derivatives separately; make export atomic.
- [ ] V6: pin backend paths (`/usr/bin:/usr/local/bin` only), add `--` before Tesseract path, `start_new_session=True` + kill process group on timeout.
- [ ] V7: chunked copy for `attach_file`; optional `--max-evidence-bytes`.
- [ ] V8: `is_relative_to` containment asserts at all five join sites.
- [ ] V9: fix `password` group re-emission; add sk-/AIza/xox/PEM/presigned-signature patterns; redact report stdout paths too.
- [ ] V12: produce a lockfile with hashes; add SBOM generation to CI; pin `hatchling` exactly.
- [ ] V13: commit `data/catalog/tools.jsonl` **inside the package** (`src/tracefield/data/...`) so wheels ship it; keep the inert-loader guarantee.
- [ ] V11: wrap `run()` in `except KeyboardInterrupt: sys.exit(130)`.

### 4.6 Open questions

- Should `TRACEFIELD_HOME` directories be created `0o700` explicitly (multi-user host threat D)?
- Are case DBs ever expected to be exchanged between analysts? If yes, V8 moves from MEDIUM to HIGH and needs signing, not just containment.
- Do we want an optional `--allow-private` (lab use) that is **off** by default and loudly announced, or is hard-refusal non-negotiable? (Recommendation: hard refusal; use a real proxy for lab work.)

### 4.7 Testable acceptance criteria

1. No URL in the allow/deny corpus of §4.4-1 misclassifies; CGNAT/metadata/site-local are denied.
2. Under the rebinding stub, zero requests reach the loopback target.
3. `grep -r "console.print" src/tracefield` shows no direct print of `locator|limitations|title|text|exc` without `sanitize_for_terminal`+`escape` (enforced by a test that AST-scans the CLI module).
4. Export of a case with secret-like evidence text completes with exit 0, `verify_manifest` passes, and evidence bytes are byte-identical to the case store.
5. `rmtree`/hash/verify with `../`-laden identifiers raise `ValueError` and touch nothing outside the data root.
6. Peak RSS for `evidence attach` of a 300 MB file < 64 MB (chunked copy).
7. Corpus test: no raw `0x1b` byte ever reaches stdout/stderr from any command given hostile inputs.

### 4.8 Challenged assumption

*"The SSRF guard fails closed."* **Disproved empirically (2026-10-16):** `http://100.100.100.200/latest/meta-data/`, `http://100.64.0.1/x`, and `http://[fec0::1]/` all pass `validate_fetch_url`. The guard is a denylist of what Python happens to call "private", not a positive allowlist of the public internet.

### 4.9 Concrete failure mode

An analyst on a cloud VM fetches a URL that an attacker later re-points (short TTL) to `169.254.169.254`. The validator's `getaddrinfo` sees the public answer; httpx's connect-time resolution sees the link-local answer; the tool happily streams instance metadata into the case's `limitations` field and, with `--fetch`, into the case record — from a tool whose README promises "SSRF-guarded" fetching.

---

## D5. Terminal Performance & Workflow Ergonomics

### 5.1 What the CLI imports eagerly (measured 2026-10-16, this machine, warm page cache)

| Command | Wall time | Notes |
|---|---|---|
| `tracefield --version` | **0.242 s** | |
| `tracefield --help` | **0.303 s** | Typer builds the full command tree |
| `tracefield doctor` | 0.241 s | |
| `tracefield case list --json` | 0.256 s | includes DB open |
| `tracefield hash README.md` | 0.235 s | |
| `import tracefield.cli.main` | 179–189 ms | of which **pydantic ≈ 96 ms** (via `core/domain.py`), typer ≈ 36 ms, rich.console ≈ 21 ms |
| `import httpx` | 111 ms | **not** on the local-command import path (verified via `-X importtime`) |
| `import textual` | 152 ms | **not** imported unless `tracefield tui` (`cli/main.py:771` lazy import) |

Eager chain: `typer`, `rich`, `pydantic` (through `core/domain.py:…` model imports at `cli/main.py:22-41`), `sqlite3` via `storage`. Positives: fieldtools are lazily imported per-command (`cli/main.py:645,659,670,358`); textual is lazy. Costs: ~90 ms of pydantic for even `--version`; `--version` could be 20 ms with a stdlib-only version callback.

**Side effect worth flagging:** every DB-touching command calls `open_db → settings.ensure_dirs()` (`cli/main.py:91-93`), so `tracefield case list` **creates** `~/.local/share/tracefield/{,cases}` on first run — a read-only-looking command mutates the filesystem.

### 5.2 Performance budgets (proposed, testable)

| Interaction | Budget | Current | Gap |
|---|---|---|---|
| `--version` cold | ≤ 80 ms | 242 ms | 3× over — defer pydantic/typer import behind the version callback |
| any local command cold | ≤ 350 ms p95 | ~250 ms | OK on this box; add CI benchmark on a constrained runner |
| `tracefield tui` first frame | ≤ 1.5 s | unmeasured (needs a pty harness) | **unknown** |
| `hash` throughput | ≥ 200 MB/s | 300 MB attach measured ~336 MB RSS + double read (D4 V7) | fix ingest path |
| 10k-row `source list --json` render | ≤ 1 s | unmeasured; no pagination exists | add `--limit`/streaming |
| TUI workspace switch on 5k-record case | ≤ 100 ms | unmeasured; `_render_ws` builds one giant string (`tui/app.py:141-231`) with N+1 queries (`app.py:152-154`) | switch to the already-imported `DataTable` with windowing |
| Idle CPU in TUI | < 2 % | `Header(show_clock=True)` (`app.py:121`) forces 1 Hz redraw | make clock opt-in |

### 5.3 Large result sets

- CLI lists (`case/source/claim/evidence list`) load **everything** into memory and print a Rich table with no `--limit`, no paging, no `--ids-only` (`cli/main.py:258-284,408-441,473-506,560-594`). A case with 50k sources produces a multi-MB table render and blocks the terminal for seconds.
- JSON mode pretty-prints via `console.print_json` (`cli/main.py:81`) — fine for `json.load`, hostile to streaming/`jq -c` on huge payloads; consider NDJSON for list commands.
- TUI renders lists as one `Static` string join (`app.py:164-186`) rather than the imported-but-unused `DataTable` (`app.py:21`) — no virtualization, full rebuild per keystroke-triggered workspace switch.

### 5.4 Cancellation

- CLI: no signal handling; long ops are `hash` (I/O bound) and `source add --fetch` (up to `max_fetch_timeout_s=15 s` × redirects). SIGINT will raise through to a traceback (no handler installed anywhere in `src/`). Exit code for interrupt is undocumented.
- TUI: the module docstring promises "`Ctrl+C` cancel current operation first; second press exits" (`tui/app.py:13`) but **no Ctrl+C binding exists** in `BINDINGS` (`app.py:91-103`); Textual's default quits immediately, contradicting the documented two-stage behavior. Similarly documented-but-unbound: `Enter`/`Tab` (`app.py:8-9`).
- `action_back` (Esc) does not go "back" — it resets to workspace 0 (`app.py:263-264`); `action_goto` and `action_focus_search` only set a status message telling the user to use the CLI (`app.py:245-270`) while the keymap docstring promises `/` filters the current list (`app.py:5`).

### 5.5 Copy / export ergonomics

- No clipboard integration at all (no `pyperclip`/OSC-52); the only "export" is `case-export` (whole bundle) and `--json` re-runs.
- Flag-name drift: `report --format json` vs everything else's `--json` (`cli/main.py:683`); `case-export`/`case-delete` have no JSON mode at all, so monitoring scripts cannot wrap them.
- No `--quiet`/`--plain` mode; `--json` output is indented (good for humans, wasteful for pipes).
- No progress feedback for hashing/attaching multi-hundred-MB evidence — the CLI is silent for seconds (verified: 300 MB attach with no output until completion).

### 5.6 Low-resolution terminals & color behavior (verified)

- Rich strips ANSI automatically when stdout is not a TTY (observed: piped `hash`/`case list` output contains zero escape bytes) and honors `NO_COLOR` (`rich/console.py:728` in the pinned rich). Textual honors `NO_COLOR` too (`textual/app.py:614-615` in the pinned textual) — verified by source inspection of the installed packages, 2026-10-16.
- Non-TTY width falls back to 80 columns, so wide tables wrap into noise (observed with `source list` piped).
- TUI CSS hardcodes truecolor hex values (`#101014`, `#c4b5fd`, `tui/app.py:46-89`); behavior on 8-bit/16-color terminals is **unknown** (Textual downgrades, but the sidebar contrast strategy was not verified on a low-color terminal).
- `sanitize_for_terminal` truncates by code points, not display width (`sanitize.py:29-30`), so a string of combining marks or wide CJK can be cut mid-grapheme and misalign tables (cosmetic, but this tool's tables are read as records).

### 5.7 Shortcut list (as implemented, as documented)

| Key | Documented (`app.py` docstring) | Actually bound (`app.py:91-103`) | Behavior |
|---|---|---|---|
| `q` | quit | yes | quits, no dirty-check despite docstring's "confirms if a view is dirty-safe" (`app.py:10`) |
| `?` | help | yes | static help text; help text itself advertises `tracefield tools search`, a nonexistent command (`app.py:256,268`) |
| `g` | "go to workspace" | yes (stub) | status message only |
| `1`–`6` | jump to workspace | yes | works |
| `/` | search/filter | yes (stub) | status message only, tells user to use CLI |
| `Esc` | cancel/back | yes | resets to workspace 0 |
| `Tab`, `Enter`, `Ctrl+C` | documented | **not bound** | default Textual behavior |

### 5.8 Risks

- Sub-300 ms cold starts are the difference between "field tool" and "not worth typing" — the current 240 ms baseline is acceptable but fragile (pydantic import growth is the risk).
- Stub keys are worse than absent keys: an analyst in a hurry presses `/`, sees a status message, and believes search ran.
- Unpaginated tables will eventually hang a terminal on a real case (an OSINT case with thousands of sources is normal, not exotic).

### 5.9 Recommendations

- Make `--version` stdlib-only (module-level `__version__` read without importing the Typer app tree); measure in CI.
- Add `--limit N` (default e.g. 200) to every list command plus `--all` to opt out; emit a `truncated: true` field in JSON.
- Implement real `/` filtering against the already-loaded list, or remove the binding and the docstring promise.
- Implement two-stage Ctrl+C (cancel current op → second press quits) or fix the docstring.
- Add `case-export`/`case-delete`/`report` `--json` results for wrapper scripts; standardize on `--json` everywhere.
- Add a spinner/progress only when stderr is a TTY (never in `--json` mode).
- Print to a pager? No — stay pipe-friendly; instead add `--plain` (no table borders) for low-res terminals.

### 5.10 Open questions

- Is the TUI ever expected to run over SSH on a 80×24 session? If yes, the fixed 24-column sidebar + padding needs a responsive breakpoint.
- Should `case list` really create the data directory, or should only `init`/`case create` do so?
- Do we want OSC-52 clipboard support (works over SSH, opt-in via env var) instead of a pyperclip dependency?

### 5.11 Testable acceptance criteria

1. `tracefield --version` completes in ≤ 80 ms on the CI runner (benchmark in `tests/` marked `slow`).
2. `tracefield case list --json | jq length` on a 50k-source case returns within budget and reports `truncated` unless `--all`.
3. `tracefield source list --json` emits zero ANSI bytes when piped; with `NO_COLOR=1` in a pty, human mode emits zero color bytes.
4. TUI: pressing `/` either filters or the binding does not exist (no status-only stub); `Ctrl+C` semantics match the documented behavior exactly.
5. TUI with a 5,000-source case switches workspaces in ≤ 100 ms (profile `_render_ws`).
6. Every command documented in `--help` exists; a test asserts `set(documented commands) == set(app.registered_commands)`.
7. `tracefield inspect` on a grapheme-heavy filename (combining marks, CJK, RTL) renders a table whose columns stay aligned (width-aware truncation).

### 5.12 Challenged assumption

*"The TUI is a thin, honest veneer over a complete CLI."* **Disproved twice:** the TUI advertises `tracefield username check` and `tracefield tools search` (`tui/app.py:213,256,268`) — both commands **do not exist** (verified: exit 2, "No such command"); and three documented keys (`/`, `g`, `Ctrl+C` two-stage) are stubs or unbound. A veneer that lies about the underlying surface is an ergonomic defect, not a polish issue.

### 5.13 Concrete failure mode

An analyst in a live field session, on a slow link, hits `/` to filter a 3,000-row source table, sees nothing happen except a status line, assumes the tool is broken, switches to raw `curl` for the rest of the case — and every subsequent observation is collected outside TRACEFIELD's provenance chain, defeating the product's entire reason to exist.
