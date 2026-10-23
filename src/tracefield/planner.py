"""Deterministic, explainable mission planner — offline, no model, no network.

Given a bounded research question, ``build_plan`` proposes several
defensible investigation paths built from a **fixed, versioned capability
table** plus optional suggestions from the inert catalogue. Design contract
(decision D18):

- **Deterministic**: same question + same catalogue → byte-identical plan.
  No clock, no RNG, no network influences the output.
- **Explainable**: every step states which question terms matched and why;
  every path carries its multi-criteria score breakdown. Scores are
  integer tuples for ordering — **never** probabilities of truth.
- **Proposal only**: the planner executes nothing. Every network-touching
  step is marked as requiring the existing double opt-in; the user runs
  each command themselves. A plan is a map, not a mission.
- **Honest about gaps**: terms no capability matches are reported as
  unresolved instead of being force-fit into a step.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

PLANNER_VERSION = "plan-r1"

# Fixed workflow policy: a non-empty path always ends with a close-out step.
_CLOSE_OUT = "close-out"

_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "can",
        "check",
        "did",
        "do",
        "does",
        "find",
        "for",
        "from",
        "get",
        "how",
        "i",
        "in",
        "is",
        "it",
        "look",
        "me",
        "my",
        "of",
        "on",
        "or",
        "please",
        "research",
        "that",
        "the",
        "this",
        "to",
        "was",
        "we",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
        "with",
        "would",
        "you",
    }
)


@dataclass(frozen=True)
class Capability:
    """A built-in TRACEFIELD capability the planner can propose."""

    id: str
    keywords: frozenset[str]
    goal: str
    command: str
    input_needed: str  # file | url | username | case
    needs_network: bool = False


# The single source of truth for planning knowledge. Ordered by fixed
# workflow phase (integrity → examination → collection → analysis → close).
_CAPABILITIES: tuple[Capability, ...] = (
    Capability(
        id="hash-verify",
        keywords=frozenset(
            {"hash", "sha256", "checksum", "digest", "integrity", "verify", "reverify"}
        ),
        goal="Establish/verify byte-level integrity hashes",
        command="tracefield hash <file>  |  tracefield evidence verify <evidence>",
        input_needed="file",
    ),
    Capability(
        id="metadata-inspect",
        keywords=frozenset(
            {
                "metadata",
                "exif",
                "gps",
                "geolocation",
                "camera",
                "properties",
                "media",
                "video",
                "audio",
                "image",
            }
        ),
        goal="Extract local file metadata (exiftool/ffprobe, honest UNAVAILABLE)",
        command="tracefield inspect <file> [--deep]",
        input_needed="file",
    ),
    Capability(
        id="ocr-extract",
        keywords=frozenset({"ocr", "tesseract", "screenshot", "scanned", "text-from-image"}),
        goal="Extract text from images via local tesseract",
        command="tracefield ocr <image>",
        input_needed="file",
    ),
    Capability(
        id="web-fetch",
        keywords=frozenset(
            {"url", "website", "web", "page", "article", "snapshot", "archive", "link"}
        ),
        goal="Capture a bounded public-source snapshot (SSRF-guarded)",
        command="TRACEFIELD_ALLOW_NETWORK=1 tracefield source add <url> --fetch",
        input_needed="url",
        needs_network=True,
    ),
    Capability(
        id="username-check",
        keywords=frozenset({"username", "handle", "account", "profile", "social", "alias", "nick"}),
        goal="Conservative public-profile existence check (curated providers)",
        command="TRACEFIELD_ALLOW_NETWORK=1 tracefield username check <handle>",
        input_needed="username",
        needs_network=True,
    ),
    Capability(
        id="origin-analysis",
        keywords=frozenset(
            {
                "origin",
                "copied",
                "copy",
                "syndicated",
                "syndication",
                "repost",
                "duplicate",
                "near-duplicate",
                "plagiarism",
                "republished",
            }
        ),
        goal="Cluster likely republications; repetition ≠ corroboration",
        command="tracefield analyze origins <case>",
        input_needed="case",
    ),
    Capability(
        id="contradiction-scan",
        keywords=frozenset(
            {
                "contradiction",
                "conflict",
                "inconsistent",
                "discrepancy",
                "timeline",
                "dates",
                "dispute",
            }
        ),
        goal="Surface contradiction candidates (always reviewable, never verdicts)",
        command="tracefield analyze contradictions <case>",
        input_needed="case",
    ),
    Capability(
        id="claim-assessment",
        keywords=frozenset(
            {"claim", "assess", "confidence", "corroboration", "support", "evidence", "conclusion"}
        ),
        goal="Assess a claim via the versioned decision table",
        command="tracefield analyze claim <claim>",
        input_needed="case",
    ),
    Capability(
        id="report",
        keywords=frozenset({"report", "export", "summary", "handoff", "share", "bundle"}),
        goal="Produce caveated report / verifiable export bundle",
        command="tracefield report <case> --format json  |  tracefield case-export <case>",
        input_needed="case",
    ),
)

_NETWORK_NOTE = "requires TRACEFIELD_ALLOW_NETWORK=1 plus an explicit per-operation opt-in"


def _tokenize(question: str) -> list[str]:
    raw = [
        t
        for t in "".join(ch.lower() if ch.isalnum() else " " for ch in question).split()
        if t and t not in _STOPWORDS and len(t) > 1
    ]
    seen: set[str] = set()
    ordered: list[str] = []
    for t in raw:
        if t not in seen:
            seen.add(t)
            ordered.append(t)
    return ordered


def _matched_capabilities(terms: list[str]) -> tuple[list[Capability], dict[str, list[str]]]:
    """Return (capabilities with ≥1 keyword hit, term→keywords matched)."""
    hits: dict[str, list[str]] = {}
    picked: list[Capability] = []
    for cap in _CAPABILITIES:  # fixed order = deterministic
        matched = sorted(t for t in terms if t in cap.keywords)
        if matched:
            picked.append(cap)
            hits[cap.id] = matched
    return picked, hits


def _step(cap: Capability, matched: list[str], hits: dict[str, list[str]]) -> dict[str, Any]:
    return {
        "capability": cap.id,
        "goal": cap.goal,
        "command": cap.command,
        "input_needed": cap.input_needed,
        "needs_network": cap.needs_network,
        "risk_note": _NETWORK_NOTE if cap.needs_network else "local-only; no network",
        "matched_terms": matched,
        "why": f"question terms matched capability keywords: {', '.join(matched)}",
        "covered_terms": len(matched),
    }


def _close_out_step() -> dict[str, Any]:
    return {
        "capability": _CLOSE_OUT,
        "goal": "Record the result in a caveated report (fixed workflow policy)",
        "command": "tracefield report <case> --format markdown",
        "input_needed": "case",
        "needs_network": False,
        "risk_note": "local-only; no network",
        "matched_terms": [],
        "why": "workflow policy: every non-empty path ends with a reportable close-out",
        "covered_terms": 0,
    }


def _path(pid: str, steps: list[dict[str, Any]], covered: int, rationale: str) -> dict[str, Any]:
    """Assemble a path with its documented multi-criteria score.

    Score tuple = (coverage higher-better, -steps higher-better,
    -network higher-better), ordered lexicographically; ties break on path id
    (string order). This is an integer ranking device, **not** a
    probability.
    """
    network_steps = sum(1 for s in steps if s["needs_network"])
    score = [covered, -len(steps), -network_steps]
    return {
        "id": pid,
        "rationale": rationale,
        "criteria": {
            "covered_terms": covered,
            "step_count": len(steps),
            "network_steps": network_steps,
        },
        "score": score,
        "steps": steps,
    }


def _catalogue_suggestions(
    question: str, catalog_path: Path | None, limit: int = 5
) -> dict[str, Any]:
    """Inert catalogue matches, clearly marked as suggestions requiring
    manual use — the planner never executes or integrates them."""
    if catalog_path is None or not catalog_path.exists():
        return {
            "available": False,
            "note": "catalogue file unavailable; suggestions omitted",
            "suggestions": [],
        }
    from tracefield.registry.catalog import Catalog

    catalog = Catalog(catalog_path)
    matches = catalog.search(question, limit=limit)
    return {
        "available": True,
        "note": "inert catalogue data; entries are listings, not verified integrations",
        "suggestions": [
            {
                "id": e.id,
                "name": e.canonical_name,
                "entry_type": e.entry_type.value,
                "integration_state": e.integration_state.value,
                "license_id": e.license_id,
                "upstream_url": e.upstream_url,
            }
            for e in matches
        ],
    }


def build_plan(question: str, *, catalog_path: Path | None = None) -> dict[str, Any]:
    """Build a deterministic, explainable plan for ``question`` (offline)."""
    terms = _tokenize(question)
    caps, hits = _matched_capabilities(terms)

    covered = set()
    for matched in hits.values():
        covered.update(matched)

    offline_steps = [_step(c, hits[c.id], hits) for c in caps if not c.needs_network]
    if offline_steps:
        offline_steps.append(_close_out_step())
    network_steps = [_step(c, hits[c.id], hits) for c in caps]
    if network_steps:
        network_steps.append(_close_out_step())

    paths = [
        _path(
            "offline-first",
            offline_steps,
            len(covered),
            "local-only capabilities; nothing leaves this machine",
        ),
        _path(
            "bounded-network",
            network_steps,
            len(covered),
            "includes opt-in collection steps; every network step states its opt-in",
        ),
    ]
    # Deterministic ranking: score tuple, then id — no randomness anywhere.
    paths.sort(key=lambda p: (tuple(p["score"]), p["id"]), reverse=True)

    return {
        "planner_version": PLANNER_VERSION,
        "question": question,
        "terms": terms,
        "unresolved_terms": [t for t in terms if t not in covered],
        "paths": paths,
        "catalogue_suggestions": _catalogue_suggestions(question, catalog_path),
        "global_caveats": [
            "A plan is a proposal: TRACEFIELD executes nothing from it; "
            "you run each command yourself.",
            "Scores are deterministic multi-criteria orderings "
            "(coverage, steps, network), not probabilities of truth.",
            "Catalogue suggestions are inert listings; 'indexed' is not "
            "'verified', 'healthy', or 'integrated'.",
            "Unresolved terms mean no local capability matched — the plan "
            "does not invent coverage it does not have.",
        ],
    }


__all__ = ["PLANNER_VERSION", "build_plan"]
