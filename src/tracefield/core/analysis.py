"""Explainable assessment engine.

Implements the multi-dimensional assessment vector from the master brief.
No black-box "truth scores". Outcome labels are conservative workflow
states with documented criteria, not probabilities.
"""

from __future__ import annotations

from tracefield.core.domain import (
    AssessmentVector,
    Claim,
    OutcomeLabel,
    Relation,
    RelationType,
    ReviewState,
)

RULE_VERSION = "assess-r2"


def assess_claim(
    claim: Claim,
    relations: list[Relation],
    *,
    origin_clusters: int = 0,
    clustered_origin_ids: set[str] | None = None,
) -> AssessmentVector:
    """Deterministic, explainable assessment of a claim.

    Criteria (documented, testable; rule version recorded in output):

    - No relations at all => UNASSESSED.
    - Confirmed CONTRADICTS and no confirmed SUPPORTS =>
      CONTRADICTED_BY_AVAILABLE_EVIDENCE (a statement about available
      evidence, not proof of falsity).
    - Confirmed CONTRADICTS and confirmed SUPPORTS => CONTESTED (analyst
      must resolve).
    - Confirmed SUPPORTS/CORROBORATES from >=2 distinct origins, where
      those origins are NOT members of the same confirmed origin cluster,
      and at least one relation is a CORROBORATES edge =>
      CORROBORATED_WITH_LIMITATIONS. If the origins appear in any origin
      cluster (even unconfirmed), the label is downgraded to
      SUPPORTED_BUT_UNCONFIRMED with an explicit caveat — clustering is a
      hypothesis, but it is enough to break the independence claim.
    - Confirmed SUPPORTS but <2 independent origins, or no corroboration
      edge => SUPPORTED_BUT_UNCONFIRMED.
    - Only unreviewed relations => INSUFFICIENT_EVIDENCE (unreviewed
      machine suggestions are not evidence).

    Provenance completeness now measures whether supporting relations carry
    an explicit ``rationale`` AND ``evidence_ids`` (real lineage), not just
    free-text presence.
    """
    clustered = clustered_origin_ids or set()
    supports = [
        r for r in relations if r.relation in (RelationType.SUPPORTS, RelationType.CORROBORATES)
    ]
    contradicts = [r for r in relations if r.relation == RelationType.CONTRADICTS]
    confirmed_supports = [r for r in supports if r.review_state == ReviewState.CONFIRMED]
    confirmed_contradicts = [r for r in contradicts if r.review_state == ReviewState.CONFIRMED]
    unreviewed_supports = [r for r in supports if r.review_state == ReviewState.UNREVIEWED]

    distinct_origins = {r.from_id for r in confirmed_supports}
    origins_in_clusters = distinct_origins & clustered
    independent_origins = distinct_origins - clustered

    v = AssessmentVector(
        claim_id=claim.id,
        supporting_count=len(supports),
        contradicting_count=len(contradicts),
        rule_version=RULE_VERSION,
    )

    # Provenance completeness: lineage must be explicit (rationale + evidence).
    if confirmed_supports:
        fully_linked = sum(1 for r in confirmed_supports if r.rationale and r.evidence_ids)
        v.provenance_completeness = (
            "complete"
            if fully_linked == len(confirmed_supports)
            else "partial"
            if fully_linked
            else "absent"
        )
    elif supports:
        v.provenance_completeness = "partial"
    else:
        v.provenance_completeness = "absent"

    v.evidence_directness = (
        "linked"
        if confirmed_supports and all(r.evidence_ids for r in confirmed_supports)
        else "unlinked"
        if confirmed_supports
        else "none"
    )
    if origins_in_clusters:
        v.independence = (
            f"{len(distinct_origins)} confirmed origin(s), "
            f"{len(origins_in_clusters)} in origin cluster(s) — independence "
            "NOT established"
        )
    else:
        v.independence = (
            f"{len(distinct_origins)} confirmed origin(s), none clustered"
            if confirmed_supports
            else "none confirmed"
        )
    v.source_transparency = "partial" if any(r.rationale for r in supports) else "unknown"
    v.temporal_fit = "unknown"
    v.missing_information = (
        "no relations recorded" if not supports and not contradicts else "see caveats"
    )
    v.reproducibility = f"deterministic rules {RULE_VERSION}"

    has_corroboration = any(r.relation == RelationType.CORROBORATES for r in confirmed_supports)

    if confirmed_contradicts and not confirmed_supports:
        v.outcome = OutcomeLabel.CONTRADICTED_BY_AVAILABLE_EVIDENCE
        v.caveats.append(
            "Confirmed contradiction(s) exist with no confirmed supporting "
            "relation. This reflects available evidence only; it is not "
            "proof of falsity."
        )
    elif confirmed_contradicts and confirmed_supports:
        v.outcome = OutcomeLabel.CONTESTED
        v.caveats.append(
            "Both confirmed support and confirmed contradiction are present; "
            "an analyst must resolve the conflict."
        )
    elif len(independent_origins) >= 2 and has_corroboration and not origins_in_clusters:
        v.outcome = OutcomeLabel.CORROBORATED_WITH_LIMITATIONS
        v.caveats.append(
            f"{len(independent_origins)} confirmed independent origins with "
            "at least one corroboration relation. Independence rests on the "
            "absence of origin-cluster membership; confirm clustering "
            "review state before relying on this label."
        )
    elif confirmed_supports:
        v.outcome = OutcomeLabel.SUPPORTED_BUT_UNCONFIRMED
        if origins_in_clusters:
            v.caveats.append(
                f"{len(origins_in_clusters)} of {len(distinct_origins)} "
                "confirmed origins appear in an origin cluster; apparent "
                "independence may be overstated (copies, syndication, or "
                "common sourcing)."
            )
        else:
            v.caveats.append(
                "At least one confirmed supporting relation, but fewer than "
                "two confirmed independent origins or no corroboration edge."
            )
    elif unreviewed_supports:
        v.outcome = OutcomeLabel.INSUFFICIENT_EVIDENCE
        v.caveats.append(
            "Supporting relations exist but none are analyst-confirmed. "
            "Unreviewed machine suggestions are not evidence."
        )
    else:
        v.outcome = OutcomeLabel.UNASSESSED
        v.caveats.append("No supporting or contradicting relations recorded.")

    if origin_clusters and v.outcome in (
        OutcomeLabel.CORROBORATED_WITH_LIMITATIONS,
        OutcomeLabel.SUPPORTED_BUT_UNCONFIRMED,
    ):
        v.caveats.append(
            f"{origin_clusters} origin cluster(s) exist in this case; "
            "review their state before treating any origin as independent."
        )
    v.caveats.append(
        "Missing data is not evidence of absence. These labels are workflow "
        "states with documented criteria, not probabilities of truth."
    )
    return v
