# Security Policy

## Reporting a vulnerability

Please report security issues **privately**. Do not open a public GitHub issue
for vulnerabilities that could put people or data at risk.

- Preferred: GitHub Security Advisories ("Report a vulnerability") on this
  repository.
- Alternative: contact the maintainer via the email on the GitHub profile,
  with the subject line `[TRACEFIELD security]`.

Include: affected version/commit, reproduction steps, impact, and any known
workarounds. You will get an acknowledgement when the maintainer is available;
there is **no published response SLA** — this is a small project and a fake
SLA would be dishonest. You will be credited in the changelog unless you ask
not to be.

## Scope notes for this project

TRACEFIELD is a local-first tool: your case data stays on your machine. That
shapes the threat model:

**In scope**

- Path traversal or arbitrary file read/write via crafted case IDs, evidence
  filenames, or export paths.
- SSRF bypasses: any URL that makes `tracefield source add --fetch` (or the
  username checker) connect to loopback, private, link-local, multicast, or
  cloud-metadata addresses, including via DNS rebinding or redirects.
- Terminal escape/ANSI injection that can hide or forge output when rendering
  untrusted source text, filenames, or tool output.
- Secret leakage: redaction bypasses, evidence/export paths that write secrets
  un-redacted, or environment-variable values appearing in logs/reports.
- Integrity failures: cases where `evidence verify` or `case-verify` reports
  OK for tampered bytes, or where the event hash chain verifies after a row
  was modified.
- Dependency vulnerabilities with a demonstrated path to any of the above.

**Out of scope (by design — not bugs)**

- The event hash chain is tamper-*evident* within this store's threat model
  only; a sufficiently privileged operator who rewrites every row can defeat
  it. This is documented in the code ("Not a blockchain").
- SHA-256 evidence digests prove byte-level integrity, not truthfulness,
  authorship, or authenticity of content.
- Third-party tools and providers reachable through opt-in network features
  (their own vulnerabilities belong with their maintainers).
- Findings that require physical or root access to the machine already
  holding the case database.
- Denial of service against yourself (e.g., attaching a pathological file to
  your own case).

## Hardening facts maintainers should keep true

- Network is off by default; `TRACEFIELD_ALLOW_NETWORK=1` plus an explicit
  `--fetch`/check flag are both required, and the SSRF policy is re-evaluated
  per request and per redirect.
- At rest: data directories `0700`, database `0600`, evidence copies `0400`.
- All external strings are sanitized before terminal rendering; JSON output
  is escaped by `json.dumps`.
- Catalogue content is inert data; nothing in `registry/` may import or
  execute catalogue-supplied content.
- CI runs the security regression suite (`pytest -m security`) and
  `pip-audit --strict`; a red gate is a signal, not noise.

## Supported versions

Only the latest release on `main` receives security fixes. There are no
long-term support branches at this stage of the project.
