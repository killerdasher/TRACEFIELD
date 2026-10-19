# TRACEFIELD — 20-Role Review (Synthesis)

> **Provenance of this document:** The 20 role perspectives below were
> conducted by **four independent review subagents** (Teams A–D, five roles
> each) operating in parallel on 2026-10-16, plus a final arbitration pass by
> the principal engineer. These are **role-based analytical perspectives**, not
> interviews with real people, and not a claim that practicing intelligence
> professionals were hired. Full per-team findings: `teams/team_a_engineering.md`,
> `teams/team_b_adoption.md`, `teams/team_c_analysis.md`,
> `teams/team_d_field_security.md`.

## Method

Each reviewer received the same brief: ground every finding in the actual
repository state or a dated external source, produce risks, recommendations,
open questions, testable acceptance criteria, at least one challenged
assumption, and at least one failure mode. External facts were verified via
live web checks on 2026-10-16 where marked; unverifiable claims are marked
`unknown`. Disagreements were resolved in `DECISIONS.md`.

## Highest-severity findings (arbitrated)

| # | Finding | Source roles | Resolution |
|---|---------|--------------|------------|
| 1 | **SSRF guard incomplete**: `is_private`-based check allowed CGNAT `100.64/10`, IMDS-style `100.100.100.200`, and IPv6 site-local; DNS-rebinding TOCTOU between resolve and connect | D4, C5, A1 | Fixed: `is_global` policy + connection pinning to pre-validated IPs with Host/SNI preserved |
| 2 | **Analytic core unreachable**: no command created or confirmed `Relation`s; every report rendered `UNASSESSED` | A4, C1, C2 | Fixed: `relation add/review`, `analyze claim` commands; `Relation.evidence_ids` added |
| 3 | **Export corrupted its own evidence**: redaction wrote to `0o400` copies → `PermissionError`, partial exports, manifest built before redaction → digest mismatch | B3, C5, D4 | Fixed: exports copy writable, redact, then build manifest over final bytes |
| 4 | **Redaction corruption**: `password: hunter2` → `password: [REDACTED]word`; cookies partially redacted; `access_token`/`sig`/`key` leaked | C5, D4 | Fixed: rewritten patterns with non-capturing groups + expanded coverage |
| 5 | **Terminal injection**: raw locators/limitations/filenames could inject ANSI/OSC; Rich markup in filenames swallowed text | D4, A2 | Fixed: sanitize all untrusted strings at every render site |
| 6 | **Cross-case provenance leak**: evidence could reference a source from another case; deleting the source's case orphaned the evidence | A1, C5 | Fixed: DB trigger + app-level check enforce `evidence.case_id == source.case_id` |
| 7 | **Path traversal**: case IDs with `../` could place case dirs outside the data root and `rmtree` them | D4 | Fixed: strict case-ID shape validation before any path join |
| 8 | **Data at rest world-readable**: DB `0644`, dirs `0755` | C5 | Fixed: `0700` dirs, `0600` DB |
| 9 | **Unbounded memory**: `read_bytes()` on attach; O(n²) clustering with no guard | D4, A5 | Fixed: streamed copy; clustering size guard with explicit skip |
| 10 | **Zero tests / empty CI** despite advertised gates | A5, B3, D4 | Fixed: full unit/integration/security/analytical fixture suite + CI workflow |
| 11 | **Advertised-but-missing commands** (`tools search/status`, `username check`) | B3, A2 | Fixed: implemented for real; no command is advertised without an implementation |
| 12 | **Near-duplicate clustering defects**: frozenset shingles discarded word order (reversed text = 1.0); non-Latin text normalized to empty | C2 | Fixed: ordered shingles; Unicode-aware tokenization |
| 13 | **Contradiction rules**: identical dates in different formats flagged; shared dates masked real conflicts; never wired | C2, C1 | Fixed: normalized comparison, wired as candidates requiring review |
| 14 | **GPS handling**: dead `strip_precise_gps_on_export` setting; export promised stripping it never performed | C5, C4 | Fixed: export emits `SENSITIVE_METADATA.txt` (key names, not values) listing GPS-bearing files; binary originals never silently rewritten; setting removed and behavior documented honestly |
| 15 | **Layering inversion**: `core/provenance.py` imported `storage` | A1 | Fixed: `CaseWorkspace` moved to `storage/workspace.py`; core stays pure |
| 16 | **Unhandled tracebacks** on directory attach, usage errors collided with NOT_FOUND exit code | A5, B3 | Fixed: top-level exception mapping (usage=3, not-found=2); `dir_okay=False` |

## Challenged assumptions (kept visible)

- **A1/B1 challenged:** "a terminal workbench is differentiated" — accepted only
  as a *hypothesis*; Sherlock/Maigret/SpiderFoot dominate username/automation;
  TRACEFIELD's differentiator is evidence provenance + honest catalogue health
  states, which competitors lack. Verified competitor facts in
  `COMPETITOR_MATRIX.md`.
- **B2 challenged:** "800+ entries are achievable" — measured 2,523 unique
  normalized URLs across three public indexes (raw 2,798), so 800+ *candidate*
  rows is real; 800+ *verified/installable/integrated* is not, and the product
  must report tiered counts, never a single padded number.
- **C2 challenged:** "≥2 distinct `from_id`s = independence" — rejected;
  independence requires origin-cluster awareness and analyst confirmation.
- **D2 challenged:** "HTTP 200 means profile exists" — rejected in the design;
  per-provider soft-404 markers required.
- **C5 challenged:** "local-only means safe" — rejected; at-rest permissions
  and export redaction are real privacy surfaces.

## Explicit non-claims

- No certification (including OWASP OOVS) is claimed. Any OOVS mapping is a
  self-assessment with stated scope.
- No claim that catalogue entries are installed, healthy, or integrated unless
  the tiered counts say so.
- Review streams were subagents, not humans; simulated reviewers must never be
  described as real analysts.
