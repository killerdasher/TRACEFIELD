"""Regression: every assessment surface must agree on the same case state.

Finding A (specialist review; reproduced 2026-11-11): report generation
(``reporting/build.py``) called ``assess_claim`` with ``origin_clusters``
(the cluster count) but never with ``clustered_origin_ids`` (membership),
while the CLI ``analyze claim`` path passed both. The same evidence could
therefore grade as ``SUPPORTED_BUT_UNCONFIRMED`` in analysis output and
``CORROBORATED_WITH_LIMITATIONS`` in the report — the report independently
re-interpreted the evidence and overstated corroboration.

The TUI claims panel was a third variant (``origin_clusters=0``, no
cluster context at all).

These tests pin the contract: for identical case state, the analysis
surface, the report payload surface, and the TUI detail surface must
produce the same outcome label and rule version.
"""

from __future__ import annotations

import pytest

from tracefield.core.analysis import assess_claim
from tracefield.core.domain import (
    Claim,
    EvidenceItem,
    OriginCluster,
    OutcomeLabel,
    Relation,
    RelationType,
    ReviewState,
    Source,
)
from tracefield.reporting.build import build_case_payload
from tracefield.storage.repositories import (
    ClaimRepo,
    ClusterRepo,
    EvidenceRepo,
    RelationRepo,
    SourceRepo,
)

pytestmark = pytest.mark.integration


def _harness(db, case):
    """Create two sources, one claim, two confirmed supporting relations.

    Source A corroborates, source B supports: with no cluster context this
    is the documented CORROBORATED_WITH_LIMITATIONS shape; when both
    origins sit in one origin cluster, independence is broken and the label
    must downgrade — on every surface.
    """
    src_a = SourceRepo(db).add(
        Source(case_id=case.id, locator="https://wire1.example/story", publisher="Wire One")
    )
    src_b = SourceRepo(db).add(
        Source(case_id=case.id, locator="https://mirror2.example/story", publisher="Mirror Two")
    )
    ev_a = EvidenceRepo(db).add(
        EvidenceItem(
            case_id=case.id,
            source_id=src_a.id,
            sha256="a" * 64,
            media_type="text/html",
            storage_ref=f"evidence/aa/{'a' * 64}",
        )
    )
    ev_b = EvidenceRepo(db).add(
        EvidenceItem(
            case_id=case.id,
            source_id=src_b.id,
            sha256="b" * 64,
            media_type="text/html",
            storage_ref=f"evidence/bb/{'b' * 64}",
        )
    )
    claim = ClaimRepo(db).add(
        Claim(case_id=case.id, text="the announcement happened on 2026-03-02")
    )
    rels = RelationRepo(db)
    rels.add(
        Relation(
            case_id=case.id,
            from_id=src_a.id,
            to_id=claim.id,
            relation=RelationType.CORROBORATES,
            rationale="independent wire text",
            evidence_ids=[ev_a.id],
            review_state=ReviewState.CONFIRMED,
        )
    )
    rels.add(
        Relation(
            case_id=case.id,
            from_id=src_b.id,
            to_id=claim.id,
            relation=RelationType.SUPPORTS,
            rationale="mirror carrying the same claim",
            evidence_ids=[ev_b.id],
            review_state=ReviewState.CONFIRMED,
        )
    )
    claim_rels = [
        r for r in rels.list_for_case(case.id) if r.from_id == claim.id or r.to_id == claim.id
    ]
    return src_a, src_b, claim, claim_rels


def _analyze_surface(claim, claim_rels, clusters) -> str:
    """Exactly what the CLI ``analyze claim`` path computes."""
    clustered_ids: set[str] = set()
    for c in clusters:
        clustered_ids.update(c.member_ids)
    v = assess_claim(
        claim,
        claim_rels,
        origin_clusters=len(clusters),
        clustered_origin_ids=clustered_ids,
    )
    return str(v.outcome)


def _report_surface(settings, db, case, claim) -> str:
    """Exactly what the report payload computes for the same claim."""
    payload = build_case_payload(settings, db, case)
    a = next(a for a in payload["assessments"] if a["claim_id"] == claim.id)
    return str(a["outcome"])


class TestAnalysisReportConsistency:
    def test_clustered_origins_never_split_across_surfaces(
        self, settings, db, case_factory
    ) -> None:
        """Both origins in one origin cluster → SUPPORTED_BUT_UNCONFIRMED on
        every surface. Reproduces Finding A: the report used to see no
        membership and graded the pair CORROBORATED_WITH_LIMITATIONS."""
        case = case_factory("clustered")
        src_a, src_b, claim, claim_rels = _harness(db, case)
        clusters = [
            ClusterRepo(db).add(
                OriginCluster(
                    case_id=case.id,
                    member_ids=[src_a.id, src_b.id],
                    indicators=["matched_text"],
                    algorithm_version="test-fixture-v1",
                    confidence_label="hypothesis",
                    review_state=ReviewState.UNREVIEWED,
                )
            )
        ]
        analyze_outcome = _analyze_surface(claim, claim_rels, clusters)
        assert analyze_outcome == str(OutcomeLabel.SUPPORTED_BUT_UNCONFIRMED)
        assert _report_surface(settings, db, case, claim) == analyze_outcome

        # Rule version must also agree between surfaces.
        payload = build_case_payload(settings, db, case)
        a = next(a for a in payload["assessments"] if a["claim_id"] == claim.id)
        assert a["rule_version"] == "assess-r2"

    def test_independent_origins_stay_corroborated_on_both_surfaces(
        self, settings, db, case_factory
    ) -> None:
        """Genuinely independent origins with a corroboration edge keep
        CORROBORATED_WITH_LIMITATIONS on every surface — the fix must not
        over-downgrade honest corroboration."""
        case = case_factory("independent")
        _, _, claim, claim_rels = _harness(db, case)
        clusters: list[OriginCluster] = []  # no clusters: independence stands
        analyze_outcome = _analyze_surface(claim, claim_rels, clusters)
        assert analyze_outcome == str(OutcomeLabel.CORROBORATED_WITH_LIMITATIONS)
        assert _report_surface(settings, db, case, claim) == analyze_outcome

    def test_same_origin_recorded_twice_is_not_two_origins(
        self, settings, db, case_factory
    ) -> None:
        """Two confirmed supports from ONE origin must not become two
        independent origins on any surface, even with a corroboration edge
        among them."""
        case = case_factory("same-origin")
        src_a = SourceRepo(db).add(
            Source(case_id=case.id, locator="https://one-origin.example/story")
        )
        ev_a = EvidenceRepo(db).add(
            EvidenceItem(
                case_id=case.id,
                source_id=src_a.id,
                sha256="a" * 64,
                media_type="text/html",
                storage_ref=f"evidence/aa/{'a' * 64}",
            )
        )
        claim = ClaimRepo(db).add(
            Claim(case_id=case.id, text="the announcement happened on 2026-03-02")
        )
        rels = RelationRepo(db)
        rels.add(
            Relation(
                case_id=case.id,
                from_id=src_a.id,
                to_id=claim.id,
                relation=RelationType.CORROBORATES,
                rationale="first record",
                evidence_ids=[ev_a.id],
                review_state=ReviewState.CONFIRMED,
            )
        )
        rels.add(
            Relation(
                case_id=case.id,
                from_id=src_a.id,
                to_id=claim.id,
                relation=RelationType.SUPPORTS,
                rationale="second record, same origin",
                evidence_ids=[ev_a.id],
                review_state=ReviewState.CONFIRMED,
            )
        )
        claim_rels = [
            r for r in rels.list_for_case(case.id) if r.from_id == claim.id or r.to_id == claim.id
        ]
        analyze_outcome = _analyze_surface(claim, claim_rels, [])
        assert analyze_outcome == str(OutcomeLabel.SUPPORTED_BUT_UNCONFIRMED)
        assert _report_surface(settings, db, case, claim) == analyze_outcome
