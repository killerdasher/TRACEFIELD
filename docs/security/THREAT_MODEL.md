# TRACEFIELD — Threat Model

> Maintained since the security/privacy/trust phase of the staged build
> program (2026-10-19/20). This is a working engineering document, not a
> certification. It names what we defend, against whom, with which control,
> and — importantly — what we deliberately do **not** defend against. Every
> control cited is enforced by code and pinned by at least one test.

## 1. Assets worth protecting

| Asset | Why it matters |
|---|---|
| Evidence bytes (`<data>/cases/<id>/…`, mode `0400`) | The exhibits themselves; loss or alteration destroys the case |
| Hash chain (`analysis_events.prev_digest` → `digest`) | The re-verifiability guarantee; breaking it breaks trust in every finding |
| Case database (`tracefield.db`, `0600`) | Claims, sources, relations, assessment outcomes |
| Operator privacy (identity, intents, credentials) | OSINT targets can be hostile; the tool must not expose the investigator |
| Structured audit log (`logs/tracefield.jsonl`, `0600`) | Non-repudiation of what the tool was asked to do |

## 2. Adversaries and what they can do

| Adversary | Capability assumed | Primary controls |
|---|---|---|
| **Malicious remote content** (a hostile web page/API) | Returns arbitrary bytes, redirects, headers, terminal escape sequences | SSRF policy + per-hop IP pinning (`fetch.py`); size caps; timeouts; `s()` terminal-escape sanitization at every render site; HTML `escape(quote=True)` in reports |
| **DNS rebinding** (public-at-validate, private-at-connect) | Controls DNS answers between validation and connect | Connection is pinned to the IP validated in the same call that connects (`_pinned_url_and_extensions`), for **every** redirect hop (audit F1 fix); Host/SNI preserved |
| **Prompt/label injection embedded in sources** | Places instruction-like text in scraped data, filenames, metadata | All external content is treated as untrusted data; nothing in a source can trigger an action or override policy; redaction before log/error/export |
| **Path traversal via case IDs / filenames** | Supplies `../`, absolute paths, non-hex IDs | Strict `validate_case_id` before any path join; `dir_okay=False` on attach; workspace path pinned under root (test) |
| **Local unprivileged user on a shared host** | Can read world-readable files | At-rest modes `0700`/`0600`/`0400`; no world-readable scratch |
| **Arbitrary-command execution via tool wrappers** | Controls a string that reaches a subprocess | `run_backend` enforces a literal allowlist (`exiftool`, `ffprobe`, `tesseract`) **before** PATH lookup (audit F2 fix); argv arrays only, never a shell; stripped env (`PATH`, `LC_ALL=C`) |
| **Credential leakage** | Harvests anything the tool echoes or logs | Redaction of auth/cookie/api-key/token/password/bearer in logs, errors, and exports |

## 3. Trust boundaries

1. **Network is OFF by default.** A case fetch requires *all three* of
   `TRACEFIELD_ALLOW_NETWORK=1`, a per-operation `--fetch`, and an **active
   recorded scope-authorization grant for the case** (`case authorize`;
   latest decision wins — a later `--revoke` blocks again). The SSRF guard
   is per-request and is *not* defeated by any of those opt-ins — a
   `--fetch` against loopback/metadata still exits 4. `username check` is
   a separate, case-less network path gated only by
   `TRACEFIELD_USERNAME_CHECK=1` (curated providers, 1 req/s, no bulk
   mode); it is not ledger-gated because it is not tied to a case.
2. **Subprocess boundary.** Only three allowlisted local utilities may run;
   they never receive a shell, never inherit ambient env, and their output is
   size-capped and treated as untrusted text.
3. **Persistence boundary.** Everything written to disk is content-addressed
   and hash-chained; `evidence verify` / `case-verify` re-hash from bytes so
   integrity never depends on the database being intact.

## 4. Explicitly out of scope (stated so no reader over-trusts us)

- **Not an anonymity system.** TRACEFIELD does not proxy, rotate identities,
  or defeat fingerprinting; using it does not make an operator untraceable.
- **No CAPTCHA / anti-bot / Cloudflare evasion, ever** (decision D17). If a
  provider blocks us (403/429), we report "refused access; not retrying, not
  circumventing" and stop.
- **Truth and authorship.** A SHA-256 proves *bytes are unchanged since
  hashing*; it does not prove a claim is true, who authored it, or when it was
  originally published. This sentence is a standing commitment of this
  project, not a disclaimer.
- **No retention/erasure guarantees yet.** We can delete a case's files; we
  cannot claim erasure from backups we do not control. Honest deletion
  semantics are planned, not shipped.
- **Authorization is recorded *and* enforced — as described, and nothing
  more.** The scope ledger (Phase 11) makes a case fetch require an active
  recorded grant (OOVS-01 self-assessment: `PASS (scoped)`, pinned by
  CLI tests: no-grant blocks exit 4, grant passes the gate, revoke
  blocks again). It *records who authorized what collection*; it cannot
  verify legal authority, the scope text is free-form, and the
  host-mentioned-in-scope check is a soft advisory, not semantic parsing.
  A recorded entry is a decision trail, not proof that every future
  operation is lawful or in-scope.

## 5. Residual risks accepted (with rationale)

| Risk | Why accepted |
|---|---|
| SQLite busy/corrupt under concurrent writers | Single-operator local tool; busy_timeout=5000; deeper fault-tolerance covered by the testing phase's fault-injection tests |
| Catalogue is inert data, not scanned code | By design (`Catalog` never executes records); `catalog validate` parses defensively |
| Dependency supply chain | `pip-audit --strict` in CI is non-`continue-on-error`; a red gate blocks release, it is not ignored |

## 6. Review cadence

Re-read this model whenever a new network path, subprocess, or export surface
is added. The controls named here are pinned by `tests/security/`; a control
without a test is treated as absent.
