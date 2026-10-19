"""Source-origin clustering: transparent signals, explainable edges.

Signals (each is an explainable edge, never a hidden heuristic):
- exact duplicate content digests
- near-duplicate via CONTAINMENT over ordered word k-grams (k=3,4,5)
- advisory related-text edges in a lower band (visible, never merged)
- explicit cross-citation (URL A appears in B's text or vice versa)

Containment (|A inter B| / min(|A|,|B|)) rather than plain Jaccard:
- tolerates light edits (a one-word change must not defeat detection)
- handles nested documents (a paragraph quoted inside a larger article)
- max over k=3..5 so both short and long overlaps are seen

Ordered tuples, not frozensets: a reversed or shuffled text scores ~0
(the AC-C2-2 reversal target). Unicode-aware tokenization: non-Latin
scripts must not normalize to the empty string (AC-C2-5).

Numeric/entity channel (deliberate, documented): differing quantities do
NOT block a merge. Near-identical prose carrying an updated figure is the
classic syndication-update pattern ("12 dead" -> "14 dead"); treating it
as independent origins would over-count corroboration. Figure conflicts
belong to the contradiction engine, not the origin engine.

Clusters are HYPOTHESES: confidence_label starts at "hypothesis" and
review_state at "unreviewed". Analysts confirm or reject edges.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from tracefield.core.domain import OriginCluster, ReviewState, new_id, utcnow

ALGORITHM_VERSION = "origin-r3"

# Unicode letters+digits, length >= 4. \w with re.UNICODE covers non-Latin
# scripts; excluding underscore avoids snake_case artifacts.
_WORD_RE = re.compile(r"[^\W_]{4,}", re.UNICODE)

MAX_DOCS_GUARD = 200  # O(n^2) pairwise; skip and report rather than hang

K_VALUES = (3, 4, 5)
NEAR_DUP_THRESHOLD = 0.8  # merges clusters
RELATED_FLOOR = 0.5  # advisory only; below this, no edge at all

# Only these signals merge documents into one cluster. Advisory
# "related_text" edges are deliberately excluded: relatedness must never
# silently downgrade an independence assessment.
MERGING_SIGNALS = (
    "exact_duplicate_digest",
    "a_url_cited_by_b",
    "b_url_cited_by_a",
    "near_duplicate_text",
)


def normalize_text(text: str) -> str:
    return " ".join(_WORD_RE.findall(text.lower()))


def word_shingles(text: str, k: int = 5) -> set[tuple[str, ...]]:
    """ORDERED k-grams: a set of tuples, preserving word order so reversed
    or shuffled text does not falsely match (a frozenset would drop order)."""
    words = normalize_text(text).split()
    if len(words) < k:
        return {tuple(words)} if words else set()
    return {tuple(words[i : i + k]) for i in range(len(words) - k + 1)}


def word_shingles_multi_k(text: str) -> dict[int, set[tuple[str, ...]]]:
    return {k: word_shingles(text, k) for k in K_VALUES}


def jaccard(a: set[tuple[str, ...]], b: set[tuple[str, ...]]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def containment(a: set[tuple[str, ...]], b: set[tuple[str, ...]]) -> float:
    """|A ∩ B| / min(|A|,|B|) — symmetric, nested-document friendly."""
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def containment_score(
    sa: dict[int, set[tuple[str, ...]]],
    sb: dict[int, set[tuple[str, ...]]],
) -> float:
    """Max containment across k=3..5."""
    return max(containment(sa[k], sb[k]) for k in K_VALUES)


@dataclass
class DocInput:
    """A document/source snippet to cluster."""

    doc_id: str
    url: str
    text: str
    sha256: str = ""


@dataclass
class Edge:
    a: str
    b: str
    signal: str
    score: float


def find_origin_edges(
    docs: list[DocInput],
    *,
    near_dup_threshold: float = NEAR_DUP_THRESHOLD,
    related_floor: float = RELATED_FLOOR,
) -> tuple[list[Edge], str]:
    """Pairwise explainable edges. Returns (edges, note). O(n^2) — guarded
    for case-sized inputs; oversized inputs are skipped with a note rather
    than hanging the UI.

    Edge bands (by containment over ordered k=3..5 grams):
    - score >= near_dup_threshold -> near_duplicate_text (merges)
    - related_floor <= score < threshold -> related_text (advisory only)
    - below related_floor -> no edge
    """
    if len(docs) > MAX_DOCS_GUARD:
        return [], (
            f"skipped: {len(docs)} documents exceeds clustering guard "
            f"({MAX_DOCS_GUARD}); cluster manually or split the case"
        )
    edges: list[Edge] = []
    shingle_map = {d.doc_id: word_shingles_multi_k(d.text) for d in docs}
    for i, a in enumerate(docs):
        for b in docs[i + 1 :]:
            if a.sha256 and a.sha256 == b.sha256:
                edges.append(Edge(a.doc_id, b.doc_id, "exact_duplicate_digest", 1.0))
                continue
            if a.url and a.url in b.text:
                edges.append(Edge(a.doc_id, b.doc_id, "a_url_cited_by_b", 1.0))
                continue
            if b.url and b.url in a.text:
                edges.append(Edge(b.doc_id, a.doc_id, "b_url_cited_by_a", 1.0))
                continue
            score = containment_score(shingle_map[a.doc_id], shingle_map[b.doc_id])
            if score >= near_dup_threshold:
                edges.append(
                    Edge(
                        a.doc_id,
                        b.doc_id,
                        f"near_duplicate_text>={near_dup_threshold}",
                        round(score, 3),
                    )
                )
            elif score >= related_floor:
                edges.append(
                    Edge(
                        a.doc_id,
                        b.doc_id,
                        f"related_text<{near_dup_threshold}",
                        round(score, 3),
                    )
                )
    return edges, ""


def cluster_from_edges(
    case_id: str, docs: list[DocInput], edges: list[Edge]
) -> list[OriginCluster]:
    """Union-find over MERGING edges only; each connected component becomes
    a cluster with explainable indicators. Advisory related_text edges are
    never unioned (they would falsely collapse independent sources).
    Singletons are not clustered."""
    parent: dict[str, str] = {d.doc_id: d.doc_id for d in docs}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: str, y: str) -> None:
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[ry] = rx

    merging = [e for e in edges if e.signal.startswith(MERGING_SIGNALS)]
    for e in merging:
        if e.a in parent and e.b in parent:
            union(e.a, e.b)

    groups: dict[str, list[str]] = {}
    for d in docs:
        groups.setdefault(find(d.doc_id), []).append(d.doc_id)

    clusters: list[OriginCluster] = []
    for members in groups.values():
        if len(members) < 2:
            continue
        member_set = set(members)
        indicators: list[str] = []
        for e in merging:
            if e.a in member_set and e.b in member_set:
                indicators.append(f"{e.a}~{e.b}: {e.signal} ({e.score})")
        clusters.append(
            OriginCluster(
                id=new_id("ocl"),
                case_id=case_id,
                member_ids=sorted(members),
                indicators=indicators,
                algorithm_version=ALGORITHM_VERSION,
                confidence_label="hypothesis",
                review_state=ReviewState.UNREVIEWED,
                created_at=utcnow(),
            )
        )
    return clusters
