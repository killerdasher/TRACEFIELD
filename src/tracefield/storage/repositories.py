"""Typed repositories over the SQLite store.

Repositories translate domain models to rows and back. They never touch
the network, TUI, or filesystem beyond the database handle they are given.
"""

from __future__ import annotations

import json
from typing import Any

from tracefield.core.domain import (
    AccessMethod,
    AnalysisEvent,
    Assertion,
    Case,
    CaseReport,
    CaseStatus,
    Claim,
    ClaimStatus,
    Dissemination,
    EvidenceItem,
    Observation,
    OriginCluster,
    Relation,
    RelationType,
    ReportCorrection,
    ReviewState,
    Source,
    SourceType,
)
from tracefield.core.provenance import compute_event_digest
from tracefield.storage.database import Database


def _row_to_case(r: Any) -> Case:
    return Case(
        id=r["id"],
        title=r["title"],
        purpose=r["purpose"],
        scope=r["scope"],
        owner_label=r["owner_label"],
        status=CaseStatus(r["status"]),
        retention_policy=r["retention_policy"],
        created_at=r["created_at"],
        updated_at=r["updated_at"],
    )


def _row_to_source(r: Any) -> Source:
    return Source(
        id=r["id"],
        case_id=r["case_id"],
        locator=r["locator"],
        publisher=r["publisher"],
        source_type=SourceType(r["source_type"]),
        access_method=AccessMethod(r["access_method"]),
        published_at=r["published_at"],
        first_seen_at=r["first_seen_at"],
        collected_at=r["collected_at"],
        collection_agent=r["collection_agent"],
        visibility=r["visibility"],
        limitations=r["limitations"],
    )


def _row_to_evidence(r: Any) -> EvidenceItem:
    return EvidenceItem(
        id=r["id"],
        case_id=r["case_id"],
        source_id=r["source_id"],
        sha256=r["sha256"],
        media_type=r["media_type"],
        storage_ref=r["storage_ref"],
        size_bytes=r["size_bytes"],
        captured_at=r["captured_at"],
        acquisition_method=r["acquisition_method"],
        excerpt=r["excerpt"],
        privacy_label=r["privacy_label"],
        retention_status=r["retention_status"],
    )


def _row_to_claim(r: Any) -> Claim:
    return Claim(
        id=r["id"],
        case_id=r["case_id"],
        text=r["text"],
        claim_type=r["claim_type"],
        temporal_scope=r["temporal_scope"],
        spatial_scope=r["spatial_scope"],
        origin=r["origin"],
        status=ClaimStatus(r["status"]),
        review_state=ReviewState(r["review_state"]),
        notes=r["notes"],
        created_at=r["created_at"],
    )


def _row_to_observation(r: Any) -> Observation:
    return Observation(
        id=r["id"],
        case_id=r["case_id"],
        evidence_id=r["evidence_id"],
        tool_name=r["tool_name"],
        tool_version=r["tool_version"],
        raw_ref=r["raw_ref"],
        returned_at=r["returned_at"],
        summary=r["summary"],
    )


def _row_to_relation(r: Any) -> Relation:
    return Relation(
        id=r["id"],
        case_id=r["case_id"],
        from_id=r["from_id"],
        to_id=r["to_id"],
        relation=RelationType(r["relation"]),
        rationale=r["rationale"],
        method=r["method"],
        review_state=ReviewState(r["review_state"]),
        evidence_ids=json.loads(r["evidence_ids"] or "[]"),
        created_at=r["created_at"],
    )


class CaseRepo:
    def __init__(self, db: Database) -> None:
        self.db = db

    def create(self, case: Case) -> Case:
        self.db.execute(
            "INSERT INTO cases(id,title,purpose,scope,owner_label,status,"
            "retention_policy,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (
                case.id,
                case.title,
                case.purpose,
                case.scope,
                case.owner_label,
                case.status.value,
                case.retention_policy,
                case.created_at,
                case.updated_at,
            ),
        )
        self.db.commit()
        return case

    def get(self, case_id: str) -> Case | None:
        r = self.db.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()
        return _row_to_case(r) if r else None

    def get_by_title(self, title: str) -> Case | None:
        r = self.db.execute(
            "SELECT * FROM cases WHERE title=? ORDER BY created_at DESC LIMIT 1",
            (title,),
        ).fetchone()
        return _row_to_case(r) if r else None

    def list(self) -> list[Case]:
        rows = self.db.execute("SELECT * FROM cases ORDER BY created_at DESC").fetchall()
        return [_row_to_case(r) for r in rows]

    def resolve(self, ref: str) -> Case | None:
        """Resolve a case by ID, then by title."""
        return self.get(ref) or self.get_by_title(ref)

    def touch(self, case_id: str) -> None:
        from tracefield.core.domain import utcnow

        self.db.execute("UPDATE cases SET updated_at=? WHERE id=?", (utcnow(), case_id))
        self.db.commit()

    def delete(self, case_id: str) -> None:
        self.db.execute("DELETE FROM cases WHERE id=?", (case_id,))
        self.db.commit()


class SourceRepo:
    def __init__(self, db: Database) -> None:
        self.db = db

    def add(self, source: Source) -> Source:
        self.db.execute(
            "INSERT INTO sources(id,case_id,locator,publisher,source_type,"
            "access_method,published_at,first_seen_at,collected_at,"
            "collection_agent,visibility,limitations) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                source.id,
                source.case_id,
                source.locator,
                source.publisher,
                source.source_type.value,
                source.access_method.value,
                source.published_at,
                source.first_seen_at,
                source.collected_at,
                source.collection_agent,
                source.visibility,
                source.limitations,
            ),
        )
        self.db.commit()
        return source

    def get(self, source_id: str) -> Source | None:
        r = self.db.execute("SELECT * FROM sources WHERE id=?", (source_id,)).fetchone()
        return _row_to_source(r) if r else None

    def list_for_case(self, case_id: str) -> list[Source]:
        rows = self.db.execute(
            "SELECT * FROM sources WHERE case_id=? ORDER BY first_seen_at", (case_id,)
        ).fetchall()
        return [_row_to_source(r) for r in rows]


class EvidenceRepo:
    def __init__(self, db: Database) -> None:
        self.db = db

    def add(self, ev: EvidenceItem) -> EvidenceItem:
        self.db.execute(
            "INSERT INTO evidence(id,case_id,source_id,sha256,media_type,storage_ref,"
            "size_bytes,captured_at,acquisition_method,excerpt,privacy_label,"
            "retention_status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                ev.id,
                ev.case_id,
                ev.source_id,
                ev.sha256,
                ev.media_type,
                ev.storage_ref,
                ev.size_bytes,
                ev.captured_at,
                ev.acquisition_method,
                ev.excerpt,
                ev.privacy_label.value,
                ev.retention_status,
            ),
        )
        self.db.commit()
        return ev

    def get(self, ev_id: str) -> EvidenceItem | None:
        r = self.db.execute("SELECT * FROM evidence WHERE id=?", (ev_id,)).fetchone()
        return _row_to_evidence(r) if r else None

    def list_for_case(self, case_id: str) -> list[EvidenceItem]:
        rows = self.db.execute(
            "SELECT * FROM evidence WHERE case_id=? ORDER BY captured_at", (case_id,)
        ).fetchall()
        return [_row_to_evidence(r) for r in rows]

    def find_by_sha(self, case_id: str, sha256: str) -> EvidenceItem | None:
        r = self.db.execute(
            "SELECT * FROM evidence WHERE case_id=? AND sha256=? LIMIT 1",
            (case_id, sha256),
        ).fetchone()
        return _row_to_evidence(r) if r else None


class ClaimRepo:
    def __init__(self, db: Database) -> None:
        self.db = db

    def add(self, claim: Claim) -> Claim:
        self.db.execute(
            "INSERT INTO claims(id,case_id,text,claim_type,temporal_scope,"
            "spatial_scope,origin,status,review_state,notes,created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (
                claim.id,
                claim.case_id,
                claim.text,
                claim.claim_type,
                claim.temporal_scope,
                claim.spatial_scope,
                claim.origin,
                claim.status.value,
                claim.review_state.value,
                claim.notes,
                claim.created_at,
            ),
        )
        self.db.commit()
        return claim

    def get(self, claim_id: str) -> Claim | None:
        r = self.db.execute("SELECT * FROM claims WHERE id=?", (claim_id,)).fetchone()
        return _row_to_claim(r) if r else None

    def list_for_case(self, case_id: str) -> list[Claim]:
        rows = self.db.execute(
            "SELECT * FROM claims WHERE case_id=? ORDER BY created_at", (case_id,)
        ).fetchall()
        return [_row_to_claim(r) for r in rows]


class ObservationRepo:
    def __init__(self, db: Database) -> None:
        self.db = db

    def add(self, obs: Observation) -> Observation:
        self.db.execute(
            "INSERT INTO observations(id,case_id,evidence_id,tool_name,tool_version,"
            "raw_ref,returned_at,summary) VALUES(?,?,?,?,?,?,?,?)",
            (
                obs.id,
                obs.case_id,
                obs.evidence_id,
                obs.tool_name,
                obs.tool_version,
                obs.raw_ref,
                obs.returned_at,
                obs.summary,
            ),
        )
        self.db.commit()
        return obs

    def list_for_case(self, case_id: str) -> list[Observation]:
        rows = self.db.execute(
            "SELECT * FROM observations WHERE case_id=? ORDER BY returned_at",
            (case_id,),
        ).fetchall()
        return [
            Observation(
                id=r["id"],
                case_id=r["case_id"],
                evidence_id=r["evidence_id"],
                tool_name=r["tool_name"],
                tool_version=r["tool_version"],
                raw_ref=r["raw_ref"],
                returned_at=r["returned_at"],
                summary=r["summary"],
            )
            for r in rows
        ]


class RelationRepo:
    def __init__(self, db: Database) -> None:
        self.db = db

    def add(self, rel: Relation) -> Relation:
        self.db.execute(
            "INSERT INTO relations(id,case_id,from_id,to_id,relation,rationale,"
            "method,review_state,evidence_ids,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                rel.id,
                rel.case_id,
                rel.from_id,
                rel.to_id,
                rel.relation.value,
                rel.rationale,
                rel.method,
                rel.review_state.value,
                json.dumps(rel.evidence_ids),
                rel.created_at,
            ),
        )
        self.db.commit()
        return rel

    def get(self, rel_id: str) -> Relation | None:
        r = self.db.execute("SELECT * FROM relations WHERE id=?", (rel_id,)).fetchone()
        return _row_to_relation(r) if r else None

    def list_for_case(self, case_id: str) -> list[Relation]:
        rows = self.db.execute(
            "SELECT * FROM relations WHERE case_id=? ORDER BY created_at", (case_id,)
        ).fetchall()
        return [_row_to_relation(r) for r in rows]

    def set_review_state(self, rel_id: str, state: ReviewState) -> None:
        self.db.execute("UPDATE relations SET review_state=? WHERE id=?", (state.value, rel_id))
        self.db.commit()


class AssertionRepo:
    def __init__(self, db: Database) -> None:
        self.db = db

    def add(self, a: Assertion) -> Assertion:
        self.db.execute(
            "INSERT INTO assertions(id,case_id,claim_id,statement,method,attribution,"
            "uncertainty,review_state,evidence_ids,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                a.id,
                a.case_id,
                a.claim_id,
                a.statement,
                a.method,
                a.attribution,
                a.uncertainty,
                a.review_state.value,
                json.dumps(a.evidence_ids),
                a.created_at,
            ),
        )
        self.db.commit()
        return a

    def list_for_case(self, case_id: str) -> list[Assertion]:
        rows = self.db.execute(
            "SELECT * FROM assertions WHERE case_id=? ORDER BY created_at", (case_id,)
        ).fetchall()
        return [
            Assertion(
                id=r["id"],
                case_id=r["case_id"],
                claim_id=r["claim_id"],
                statement=r["statement"],
                method=r["method"],
                attribution=r["attribution"],
                uncertainty=r["uncertainty"],
                review_state=ReviewState(r["review_state"]),
                evidence_ids=json.loads(r["evidence_ids"]),
                created_at=r["created_at"],
            )
            for r in rows
        ]


class ReportRepo:
    """Durable report identity, corrections, and shipment register (v2).

    All register writes are small and transactional; chain maintenance
    (supersedes/superseded_by) happens inside ``register`` so a report
    identity is never left partially linked."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def register(self, case_id: str) -> CaseReport:
        """Mint the next revision for ``case_id`` and link the chain."""
        prev_row = self.db.execute(
            "SELECT id, revision FROM case_reports WHERE case_id=? ORDER BY revision DESC LIMIT 1",
            (case_id,),
        ).fetchone()
        identity = CaseReport(
            case_id=case_id,
            revision=(prev_row["revision"] + 1) if prev_row else 1,
            supersedes=prev_row["id"] if prev_row else "",
        )
        self.db.execute(
            "INSERT INTO case_reports(id,case_id,revision,supersedes,superseded_by,"
            "created_at) VALUES(?,?,?,?,?,?)",
            (
                identity.id,
                identity.case_id,
                identity.revision,
                identity.supersedes,
                "",
                identity.created_at,
            ),
        )
        if prev_row is not None:
            self.db.execute(
                "UPDATE case_reports SET superseded_by=? WHERE id=?",
                (identity.id, prev_row["id"]),
            )
        self.db.commit()
        return identity

    def get(self, report_id: str) -> CaseReport | None:
        r = self.db.execute("SELECT * FROM case_reports WHERE id=?", (report_id,)).fetchone()
        if r is None:
            return None
        return CaseReport(
            id=r["id"],
            case_id=r["case_id"],
            revision=r["revision"],
            supersedes=r["supersedes"],
            superseded_by=r["superseded_by"],
            created_at=r["created_at"],
        )

    def list_for_case(self, case_id: str) -> list[CaseReport]:
        rows = self.db.execute(
            "SELECT * FROM case_reports WHERE case_id=? ORDER BY revision", (case_id,)
        ).fetchall()
        return [
            CaseReport(
                id=r["id"],
                case_id=r["case_id"],
                revision=r["revision"],
                supersedes=r["supersedes"],
                superseded_by=r["superseded_by"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

    def lineage(self, report_id: str) -> list[CaseReport]:
        """The report and every ancestor it supersedes, newest first."""
        chain: list[CaseReport] = []
        seen: set[str] = set()
        cur = self.get(report_id)
        while cur is not None and cur.id not in seen:
            chain.append(cur)
            seen.add(cur.id)
            cur = self.get(cur.supersedes) if cur.supersedes else None
        return chain

    def add_correction(self, case_id: str, report_id: str, note: str) -> ReportCorrection:
        correction = ReportCorrection(case_id=case_id, corrected_report_id=report_id, note=note)
        self.db.execute(
            "INSERT INTO report_corrections(id,case_id,corrected_report_id,note,"
            "created_at) VALUES(?,?,?,?,?)",
            (
                correction.id,
                correction.case_id,
                correction.corrected_report_id,
                correction.note,
                correction.created_at,
            ),
        )
        self.db.commit()
        return correction

    def corrections_for_chain(self, report_id: str) -> list[ReportCorrection]:
        """Corrections addressed at ``report_id`` or any ancestor it
        supersedes — a superseded report's corrections travel with the
        lineage, so a re-render never silently drops a known error."""
        chain_ids = [rep.id for rep in self.lineage(report_id)]
        if not chain_ids:
            return []
        placeholders = ",".join("?" for _ in chain_ids)
        rows = self.db.execute(
            "SELECT * FROM report_corrections WHERE corrected_report_id IN "
            f"({placeholders}) ORDER BY created_at, rowid",
            tuple(chain_ids),
        ).fetchall()
        return [
            ReportCorrection(
                id=r["id"],
                case_id=r["case_id"],
                corrected_report_id=r["corrected_report_id"],
                note=r["note"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

    def corrections_for_case(self, case_id: str) -> list[ReportCorrection]:
        rows = self.db.execute(
            "SELECT * FROM report_corrections WHERE case_id=? ORDER BY created_at, rowid",
            (case_id,),
        ).fetchall()
        return [
            ReportCorrection(
                id=r["id"],
                case_id=r["case_id"],
                corrected_report_id=r["corrected_report_id"],
                note=r["note"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

    def add_shipment(
        self, case_id: str, report_id: str, recipient: str, note: str = ""
    ) -> Dissemination:
        shipment = Dissemination(
            case_id=case_id,
            report_id=report_id,
            recipient=recipient,
            note=note,
        )
        self.db.execute(
            "INSERT INTO dissemination(id,case_id,report_id,recipient,shipped_at,"
            "note) VALUES(?,?,?,?,?,?)",
            (
                shipment.id,
                shipment.case_id,
                shipment.report_id,
                shipment.recipient,
                shipment.shipped_at,
                shipment.note,
            ),
        )
        self.db.commit()
        return shipment

    def shipments_for_case(self, case_id: str) -> list[Dissemination]:
        rows = self.db.execute(
            "SELECT * FROM dissemination WHERE case_id=? ORDER BY rowid", (case_id,)
        ).fetchall()
        return [
            Dissemination(
                id=r["id"],
                case_id=r["case_id"],
                report_id=r["report_id"],
                recipient=r["recipient"],
                shipped_at=r["shipped_at"],
                note=r["note"],
            )
            for r in rows
        ]


class ClusterRepo:
    def __init__(self, db: Database) -> None:
        self.db = db

    def add(self, c: OriginCluster) -> OriginCluster:
        self.db.execute(
            "INSERT INTO origin_clusters(id,case_id,member_ids,indicators,"
            "algorithm_version,confidence_label,review_state,created_at) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (
                c.id,
                c.case_id,
                json.dumps(c.member_ids),
                json.dumps(c.indicators),
                c.algorithm_version,
                c.confidence_label,
                c.review_state.value,
                c.created_at,
            ),
        )
        self.db.commit()
        return c

    def list_for_case(self, case_id: str) -> list[OriginCluster]:
        rows = self.db.execute(
            "SELECT * FROM origin_clusters WHERE case_id=? ORDER BY created_at",
            (case_id,),
        ).fetchall()
        return [
            OriginCluster(
                id=r["id"],
                case_id=r["case_id"],
                member_ids=json.loads(r["member_ids"]),
                indicators=json.loads(r["indicators"]),
                algorithm_version=r["algorithm_version"],
                confidence_label=r["confidence_label"],
                review_state=ReviewState(r["review_state"]),
                created_at=r["created_at"],
            )
            for r in rows
        ]


class EventRepo:
    """Append-only analysis event log."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def append(self, event: AnalysisEvent) -> AnalysisEvent:
        self.db.execute(
            "INSERT INTO analysis_events(id,case_id,action,inputs,outputs,"
            "tool_fingerprint,prev_digest,digest,occurred_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (
                event.id,
                event.case_id,
                event.action,
                json.dumps(event.inputs),
                json.dumps(event.outputs),
                event.tool_fingerprint,
                event.prev_digest,
                event.digest,
                event.occurred_at,
            ),
        )
        self.db.commit()
        return event

    def last_digest(self, case_id: str) -> str:
        r = self.db.execute(
            "SELECT digest FROM analysis_events WHERE case_id=? "
            "ORDER BY occurred_at DESC, rowid DESC LIMIT 1",
            (case_id,),
        ).fetchone()
        return r["digest"] if r else ""

    def latest_action(self, case_id: str, actions: tuple[str, ...]) -> AnalysisEvent | None:
        """The most recently recorded event among ``actions`` (rowid order,
        append-only). None when no such event was ever recorded."""
        placeholders = ",".join("?" for _ in actions)
        r = self.db.execute(
            "SELECT * FROM analysis_events WHERE case_id=? AND action IN "
            f"({placeholders}) ORDER BY rowid DESC LIMIT 1",
            (case_id, *actions),
        ).fetchone()
        if r is None:
            return None
        return AnalysisEvent(
            id=r["id"],
            case_id=r["case_id"],
            action=r["action"],
            inputs=json.loads(r["inputs"]),
            outputs=json.loads(r["outputs"]),
            tool_fingerprint=r["tool_fingerprint"],
            prev_digest=r["prev_digest"],
            digest=r["digest"],
            occurred_at=r["occurred_at"],
        )

    def get(self, event_id: str) -> AnalysisEvent | None:
        r = self.db.execute("SELECT * FROM analysis_events WHERE id=?", (event_id,)).fetchone()
        if r is None:
            return None
        return AnalysisEvent(
            id=r["id"],
            case_id=r["case_id"],
            action=r["action"],
            inputs=json.loads(r["inputs"]),
            outputs=json.loads(r["outputs"]),
            tool_fingerprint=r["tool_fingerprint"],
            prev_digest=r["prev_digest"],
            digest=r["digest"],
            occurred_at=r["occurred_at"],
        )

    def list_for_case(self, case_id: str) -> list[AnalysisEvent]:
        rows = self.db.execute(
            "SELECT * FROM analysis_events WHERE case_id=? ORDER BY rowid",
            (case_id,),
        ).fetchall()
        return [
            AnalysisEvent(
                id=r["id"],
                case_id=r["case_id"],
                action=r["action"],
                inputs=json.loads(r["inputs"]),
                outputs=json.loads(r["outputs"]),
                tool_fingerprint=r["tool_fingerprint"],
                prev_digest=r["prev_digest"],
                digest=r["digest"],
                occurred_at=r["occurred_at"],
            )
            for r in rows
        ]

    def verify_chain(self, case_id: str) -> tuple[bool, str]:
        """Verify the hash chain. Tamper-evident within this store's threat
        model only — a sufficiently privileged operator who rewrites every
        row can defeat it. Not a blockchain."""
        events = self.list_for_case(case_id)
        prev = ""
        for ev in events:
            if ev.prev_digest != prev:
                return False, f"chain break before event {ev.id}: prev_digest mismatch"
            expected = compute_event_digest(ev.action, ev.inputs, ev.outputs, prev, ev.occurred_at)
            if ev.digest and ev.digest != expected:
                return False, f"digest mismatch at event {ev.id}"
            prev = ev.digest or expected
        return True, f"ok ({len(events)} events)"
