"""Regression: assessment messages must reflect the actual relation state.

Finding B (specialist review; reproduced 2026-11-11): with an UNREVIEWED
contradiction relation recorded and no confirmed relations, the assessment
vector said ``UNASSESSED`` with the caveat "No supporting or contradicting
relations recorded." — while ``contradicting_count`` was 1. The report
shipped that sentence, telling the reader no contradiction existed when a
candidate was awaiting review.

The evaluator now distinguishes the states the model actually supports
(ReviewState: unreviewed / confirmed / rejected / unresolved):

1. no relations recorded → UNASSESSED, "No … relations recorded" (accurate)
2. relations awaiting review → INSUFFICIENT_EVIDENCE, naming the pending
   contradiction relations explicitly (documented criteria: "only
   unreviewed relations => INSUFFICIENT_EVIDENCE" — the old code applied
   that to supports only)
3. relations reviewed, none confirmed (rejected/unresolved) → UNASSESSED
   with a caveat that names what was recorded and decided
4. confirmed support + pending contradiction → the outcome branches above
   run as before, with the pending state visible via ``supporting_count``
   / ``contradicting_count`` (counting includes unreviewed relations —
   the count is "recorded", the label is "confirmed-only").
"""

from __future__ import annotations

import pytest

from tracefield.core.analysis import assess_claim
from tracefield.core.domain import (
    Claim,
    OutcomeLabel,
    Relation,
    RelationType,
    ReviewState,
)

pytestmark = pytest.mark.integration


def _claim() -> Claim:
    return Claim(case_id="case_" + "b" * 16, text="the announcement date is 2026-03-02")


def _rel(claim: Claim, *, relation: RelationType, state: ReviewState) -> Relation:
    return Relation(
        case_id=claim.case_id,
        from_id="src_" + "1" * 16,
        to_id=claim.id,
        relation=relation,
        review_state=state,
    )


class TestContradictionStateMessaging:
    def test_unreviewed_contradiction_is_not_reported_as_nothing(self) -> None:
        """THE Finding B reproduction: one unreviewed contradiction, nothing
        confirmed → INSUFFICIENT_EVIDENCE naming the pending contradiction,
        never the false 'no relations recorded' sentence."""
        claim = _claim()
        v = assess_claim(
            claim, [_rel(claim, relation=RelationType.CONTRADICTS, state=ReviewState.UNREVIEWED)]
        )
        assert v.outcome == OutcomeLabel.INSUFFICIENT_EVIDENCE
        assert v.contradicting_count == 1
        text = " ".join(v.caveats)
        assert "No supporting or contradicting relations recorded" not in text
        assert "awaiting analyst review" in text
        assert "contradiction relation(s)" in text

    def test_no_relations_message_only_when_truly_empty(self) -> None:
        claim = _claim()
        v = assess_claim(claim, [])
        assert v.outcome == OutcomeLabel.UNASSESSED
        assert "No supporting or contradicting relations recorded" in " ".join(v.caveats)

    def test_rejected_and_unresolved_are_named_not_hidden(self) -> None:
        claim = _claim()
        v = assess_claim(
            claim,
            [
                _rel(claim, relation=RelationType.SUPPORTS, state=ReviewState.REJECTED),
                _rel(claim, relation=RelationType.CONTRADICTS, state=ReviewState.UNRESOLVED),
            ],
        )
        assert v.outcome == OutcomeLabel.UNASSESSED
        text = " ".join(v.caveats)
        assert "1 rejected" in text
        assert "1 unresolved" in text
        assert "No supporting or contradicting relations recorded" not in text

    def test_unreviewed_support_message_unchanged(self) -> None:
        """Existing pinned behavior (unreviewed supports → INSUFFICIENT_
        EVIDENCE) must remain intact."""
        claim = _claim()
        v = assess_claim(
            claim, [_rel(claim, relation=RelationType.SUPPORTS, state=ReviewState.UNREVIEWED)]
        )
        assert v.outcome == OutcomeLabel.INSUFFICIENT_EVIDENCE
        assert "Unreviewed machine suggestions are not evidence" in " ".join(v.caveats)

    def test_pending_contradiction_alongside_confirmed_support(self) -> None:
        """Confirmed support + unreviewed contradiction: outcome branches
        run as before; the pending contradiction is visible in the count
        and never silently treated as a confirmed finding."""
        claim = _claim()
        v = assess_claim(
            claim,
            [
                _rel(claim, relation=RelationType.SUPPORTS, state=ReviewState.CONFIRMED),
                _rel(claim, relation=RelationType.CONTRADICTS, state=ReviewState.UNREVIEWED),
            ],
        )
        assert v.outcome == OutcomeLabel.SUPPORTED_BUT_UNCONFIRMED
        assert v.contradicting_count == 1
        assert v.supporting_count == 1

    def test_unreviewed_only_docstring_criterion_holds(self) -> None:
        """Documented criterion (assess-r2): only unreviewed relations =>
        INSUFFICIENT_EVIDENCE — now true for contradiction-only state."""
        claim = _claim()
        rels = [
            _rel(claim, relation=RelationType.CONTRADICTS, state=ReviewState.UNREVIEWED),
            _rel(claim, relation=RelationType.MENTIONS, state=ReviewState.UNREVIEWED),
        ]
        v = assess_claim(claim, rels)
        assert v.outcome == OutcomeLabel.INSUFFICIENT_EVIDENCE
