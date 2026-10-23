# TRACEFIELD — TUI Interaction Specification

> Spec for remediating the confirmed TUI findings of `POST_BUILD_AUDIT.md`
> (T1–T10). Requirement IDs `TS-xx` are referenced from
> `FINAL_BUILD_SPEC.md`. This is a specification only — no UI framework change
> (Textual stays), no implementation in this phase. Standing rule from the
> product brief: **the TUI is optional; every feature here also has a CLI
> path**, and the status/help text must never advertise behaviour the build
> does not implement.

## 1. Design principles

1. **Truthful chrome (P-TS-1).** Every key shown in the docstring, footer,
   help view, or status line exists in `BINDINGS` **and** performs what the
   label says. A key that is unbound is not mentioned anywhere.
2. **Truthful data labelling (P-TS-2).** Views say what they render: live
   workspace data, demo fixtures, or empty state — never a "synthetic" label
   over live rows (audit T7).
3. **Execution feels alive without lying (P-TS-3).** Long operations show
   progress the moment it is real (start/row-count/finish), fail visibly with
   the exit-code meaning, and never spin fake timers.
4. **Case is the unit of view (P-TS-4).** No view ever mixes rows from
   different cases (audit T6).
5. **Progressive disclosure (P-TS-5).** Default screens show status + next
   actions; detail is one keystroke away; help is contextual and reversible.
6. **No manipulation (P-TS-6).** No manufactured urgency, no confetti, no
   success colour on uncertain results; state text carries meaning, colour is
   redundant reinforcement only.

## 2. Workspace model

Six workspaces (unchanged names), each with one primary pane + status line:

| # | Workspace | Purpose | Primary content |
|---|---|---|---|
| 0 | **Mission** | Case orientation: purpose/scope, counts, recent events, integrity state | case header, tiered counts, last events, `case-verify` result badge |
| 1 | **Evidence** | The case's evidence items | list (case-scoped), detail pane with hash/verifier state |
| 2 | **Claims** | Claims, relations, assessment outcomes | list (case-scoped), detail with decision table outcome + caveats |
| 3 | **Arsenal** | Catalogue search/browse | tiered counts, per-entry state ("listed/verified" never "healthy") |
| 4 | **Field** | Field utilities (hash/inspect/ocr/fetch/username) | inputs + results bound to active case |
| 5 | **Runs** | Analysis & event history | hash-chained events, analyze runs, log references |

**Active case (TS-1):** exactly one case is *active* in the session. Rules:

- Mission shows the active case; every case-scoped view renders **only**
  active-case rows and shows `case: <id>` in the status line at all times.
- A **case picker** (`c`) lists cases (id, name, counts); Enter sets active,
  Esc cancels. On launch with exactly one case it is auto-selected; with
  zero, Mission offers `case create` guidance; with 2+, Mission shows
  "select a case: c" until chosen (no silent `cases[0]`).
- Switching cases preserves per-workspace scroll position per case.

## 3. Interaction grammar (the contract)

| Key | Action | Notes |
|---|---|---|
| `1`–`6` | Jump to workspace n | Direct, always |
| `g` | **Jump palette**: mini-prompt listing the six workspaces with numbers; type number or arrows+Enter; Esc closes | Replaces today's status-only hint (T2) |
| `Tab` | Move focus to next pane **if and only if** the workspace has >1 pane; otherwise no-op **and not documented in that workspace's footer** | Fixes T4: footer is built from live bindings, so a mono-pane view never advertises Tab |
| `Enter` | Inspect/activate selected row (detail pane or drill-down) | Bound only in views with rows; footer reflects it |
| `/` | **Filter the current list** with incremental match + match count (`3/57`); empty result shows "no match" state, not silence | Fixes T3 |
| `?` | **Help overlay** rendered above content (modal), workspace-context section first; any of `?`/`Esc` closes and restores the exact prior pane | Fixes T1: content is never destroyed; status stays truthful |
| `Esc` | Pop back: overlay → detail → previous workspace (back-stack, max depth recorded) | Fixes T5: no forced jump to Mission |
| `c` | Case picker (TS-1) | |
| `q` | Quit; prompts only when an operation is in flight | Docstring must match actual behaviour |
| `Ctrl+C` | **Cancel the in-flight operation first** (TS-3); second press within the quit-confirm window exits | Fixes T8: implemented, not just documented |

**TS-2 keymap parity test:** a test parses the module docstring's key table
and asserts key-for-key equality with `BINDINGS`-derived keys, and asserts
each footer entry maps to an existing binding. Any future drift fails CI.

## 4. Progress and cancellation model (TS-3)

Applies to any operation >300 ms (repo queries, analyze, exports, fetch,
username runs via CLI shim):

- **States:** `idle → running(<label>, <started_at>) → done(count, elapsed) |
  failed(<exit code meaning>) | cancelled(by user)`.
- Progress renders as discrete milestones (rows read, files copied, providers
  checked) — **only from real reported counts**; if a backend cannot report
  progress, the UI shows elapsed time + label, never a synthetic bar.
- `Ctrl+C` requests cooperative cancel; the operation finalises its state
  (partial results marked `cancelled`, no half-written artefacts; export
  interruption leaves the prior intact bundle + a `failed` event).
- Every terminal state appears in the Runs workspace and the audit log.

## 5. Honest status and labelling rules (TS-4)

- Status line format: `<workspace> | case: <id> | <op-state>` — always
  consistent with the visible content (audit T1's status mismatch).
- Subtitle shows the data source truthfully: "live workspace data" or the
  demo marker **only when `TRACEFIELD_DEMO_FIXTURES=1`** (audit T7).
- Catalogue/arsenal entries render tiered states verbatim (`indexed`,
  `verified`); "verified" tooltip states what was checked and when.
- UNAVAILABLE/absent backends (tesseract, exiftool) show their reason string
  as-is — same vocabulary as CLI.

## 6. Theming (TS-5)

- Colours move from CSS hex literals to semantic tokens
  (`--fg`, `--bg`, `--accent`, `--ok`, `--warn`, `--err`, `--muted`) with a
  light/dark pair; default follows terminal background detection, `--theme`
  flag overrides.
- `NO_COLOR`/`--no-color` degrade to text-only state labels (no
  colour-only signalling — already a stated StatusBar rule, now enforced).
- All text passes through the existing `sanitize_for_terminal` boundary
  before render (unchanged; D11).

## 7. Core journeys with acceptance assertions (TS-6)

| ID | Journey | Must hold |
|---|---|---|
| J1 | Open app → select case → browse Evidence → open detail → Esc → `?` → Esc | Rows only from active case; after `?`+close, prior detail/scroll state is byte-identical; status never contradicts content |
| J2 | Field: hash a file → attach to case → Claims: create claim → relate evidence → assess | Each step shows start/done state; result identical to the same CLI sequence (cross-checked by test) |
| J3 | Arsenal: filter "exif" → open entry → note tier | Filter count accurate; tier text matches `tools show --json` |
| J4 | Runs: view analyze run → inspect event chain | Events render in chain order with digest prefix; a tampered event shows a verification failure state |
| J5 | Cancel: start a heavy list render → Ctrl+C | State `cancelled` within 500 ms; no partial rows left visible; Runs records the cancel |

## 8. Stateful and performance requirements (TS-7)

- **Stateful tests:** journeys J1–J5 implemented with
  `App.run_test()` pilots over a seeded 2-case workspace; assertions include
  case-scoping (`lists_cases` invariant = 1 rendered case), help-overlay
  restore, back-stack order, keymap parity (TS-2), cancel semantics.
- **Performance acceptance (informal, this machine, recorded as baseline not
  benchmark):** workspace switch ≤100 ms at 5k evidence rows; list filter
  ≤150 ms at 5k rows; no render-path query over 50 ms without worker
  offload — which becomes the trigger to implement the existing open risk
  `A2/R-A2-3` (async worker offload) rather than an unconditional rewrite.

## 9. Non-goals

No new UI framework; no plugin system; no web UI; no mouse-first redesign;
no feature that exists only in the TUI; no claim that the TUI replaces the
CLI's scripting/automation surface.
