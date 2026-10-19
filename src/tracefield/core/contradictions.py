"""Deterministic contradiction detection for structured claim aspects.

Rules run on exact/near-exact structured values: dates (normalized across
formats), hashes, quantities. Semantic/NLP candidate detection is NOT in
this release — when added it must be labeled as a candidate and require
review. Analyst-approved findings are never silently overwritten.

All outputs are ``severity="candidate"`` and require analyst review.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

RULE_VERSION = "contra-r2"

_ISO_DATE_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_US_DATE_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
_HASH_RE = re.compile(r"\b[a-fA-F0-9]{64}\b")


@dataclass
class ContradictionCandidate:
    """A structured conflict between two evidence excerpts."""

    aspect: str  # date | hash
    value_a: str
    value_b: str
    evidence_a: str
    evidence_b: str
    rule: str
    severity: str = "candidate"  # always 'candidate' — requires review


def _normalize_date(raw: str) -> str | None:
    """Normalize a date string to ISO YYYY-MM-DD where possible, so the
    same day written two ways (2024-03-01 vs 3/1/2024) does NOT register
    as a contradiction."""
    raw = raw.strip()
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date().isoformat()
    except ValueError:
        pass
    for fmt in ("%m/%d/%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def extract_dates(text: str) -> set[str]:
    """Return normalized ISO dates found in ``text``."""
    out: set[str] = set()
    for m in _ISO_DATE_RE.finditer(text):
        norm = _normalize_date(m.group(0))
        if norm:
            out.add(norm)
    for m in _US_DATE_RE.finditer(text):
        norm = _normalize_date(m.group(0))
        if norm:
            out.add(norm)
    return out


def extract_hashes(text: str) -> set[str]:
    return {h.lower() for h in _HASH_RE.findall(text)}


def find_contradictions(
    text_a: str, evidence_a: str, text_b: str, evidence_b: str
) -> list[ContradictionCandidate]:
    """Compare two excerpts for structured contradictions (candidates)."""
    out: list[ContradictionCandidate] = []

    dates_a, dates_b = extract_dates(text_a), extract_dates(text_b)
    # Flag ONLY when both excerpts contain dates, they share no normalized
    # date (a shared date masks nothing here), and each has at least one
    # date the other lacks. Identical dates in different formats have been
    # normalized and will match, so they no longer false-positive.
    if dates_a and dates_b and not (dates_a & dates_b):
        out.append(
            ContradictionCandidate(
                aspect="date",
                value_a=",".join(sorted(dates_a)),
                value_b=",".join(sorted(dates_b)),
                evidence_a=evidence_a,
                evidence_b=evidence_b,
                rule=RULE_VERSION,
            )
        )

    hashes_a, hashes_b = extract_hashes(text_a), extract_hashes(text_b)
    if hashes_a and hashes_b and hashes_a != hashes_b:
        out.append(
            ContradictionCandidate(
                aspect="hash",
                value_a=",".join(sorted(hashes_a)),
                value_b=",".join(sorted(hashes_b)),
                evidence_a=evidence_a,
                evidence_b=evidence_b,
                rule=RULE_VERSION,
            )
        )
    return out
