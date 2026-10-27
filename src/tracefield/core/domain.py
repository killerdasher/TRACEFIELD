"""Core domain models for cases, claims, sources, evidence, and analysis.

All persistent entities use stable string IDs. Timestamps are UTC ISO-8601
with explicit ``Z`` suffix. These models are pure data: they never import
storage, network, or TUI code.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


def utcnow() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


# ---------------------------------------------------------------------------
# Enums — kept explicit so catalogue/report values are stable and lintable.
# ---------------------------------------------------------------------------


class CaseStatus(StrEnum):
    OPEN = "open"
    ARCHIVED = "archived"
    CLOSED = "closed"


class ClaimStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    RETRACTED = "retracted"


class ReviewState(StrEnum):
    UNREVIEWED = "unreviewed"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    UNRESOLVED = "unresolved"


class SourceType(StrEnum):
    WEB_PAGE = "web_page"
    LOCAL_FILE = "local_file"
    API_RESPONSE = "api_response"
    DOCUMENT = "document"
    INTERVIEW = "interview"
    DATASET = "dataset"
    OTHER = "other"


class AccessMethod(StrEnum):
    MANUAL = "manual"
    FETCHED = "fetched"
    PROVIDED = "provided"
    IMPORTED = "imported"


class PrivacyLabel(StrEnum):
    PUBLIC = "public"
    SENSITIVE = "sensitive"
    PERSONAL = "personal"
    UNKNOWN = "unknown"


class OutcomeLabel(StrEnum):
    """Conservative workflow labels — not metaphysical judgments."""

    UNASSESSED = "UNASSESSED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    SUPPORTED_BUT_UNCONFIRMED = "SUPPORTED_BUT_UNCONFIRMED"
    CORROBORATED_WITH_LIMITATIONS = "CORROBORATED_WITH_LIMITATIONS"
    CONTESTED = "CONTESTED"
    CONTRADICTED_BY_AVAILABLE_EVIDENCE = "CONTRADICTED_BY_AVAILABLE_EVIDENCE"


class UsernameResultState(StrEnum):
    """Per-provider verification states for public-profile checks."""

    CONFIRMED_PUBLIC_PROFILE = "CONFIRMED_PUBLIC_PROFILE"
    LIKELY_MATCH = "LIKELY_MATCH"
    INCONCLUSIVE = "INCONCLUSIVE"
    NOT_FOUND_VERIFIED = "NOT_FOUND_VERIFIED"
    BLOCKED = "BLOCKED"
    RATE_LIMITED = "RATE_LIMITED"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    NOT_CHECKED = "NOT_CHECKED"


# ---------------------------------------------------------------------------
# Entities
# ---------------------------------------------------------------------------


class Case(BaseModel):
    id: str = Field(default_factory=lambda: new_id("case"))
    title: str
    purpose: str = ""
    scope: str = ""
    owner_label: str = ""
    status: CaseStatus = CaseStatus.OPEN
    retention_policy: str = "default"
    created_at: str = Field(default_factory=utcnow)
    updated_at: str = Field(default_factory=utcnow)


class Source(BaseModel):
    id: str = Field(default_factory=lambda: new_id("src"))
    case_id: str
    locator: str  # canonical URL or local path
    publisher: str = ""
    source_type: SourceType = SourceType.WEB_PAGE
    access_method: AccessMethod = AccessMethod.MANUAL
    published_at: str = ""  # when verifiable; distinct from first_seen/collected
    first_seen_at: str = Field(default_factory=utcnow)
    collected_at: str = ""
    collection_agent: str = ""
    visibility: str = "public"
    limitations: str = ""


class EvidenceItem(BaseModel):
    id: str = Field(default_factory=lambda: new_id("ev"))
    case_id: str
    source_id: str
    sha256: str
    media_type: str
    storage_ref: str  # relative path within case directory
    size_bytes: int = 0
    captured_at: str = Field(default_factory=utcnow)
    acquisition_method: str = "manual"
    excerpt: str = ""
    privacy_label: PrivacyLabel = PrivacyLabel.UNKNOWN
    retention_status: str = "retained"


class Observation(BaseModel):
    """A direct tool return — raw, uninterpreted."""

    id: str = Field(default_factory=lambda: new_id("obs"))
    case_id: str
    evidence_id: str = ""
    tool_name: str
    tool_version: str = ""
    raw_ref: str = ""  # storage reference to original raw response
    returned_at: str = Field(default_factory=utcnow)
    summary: str = ""


class Assertion(BaseModel):
    """An evidence-linked interpretation (human or machine)."""

    id: str = Field(default_factory=lambda: new_id("asr"))
    case_id: str
    claim_id: str = ""
    statement: str
    method: str = "analyst"
    attribution: str = ""
    uncertainty: str = "unknown"
    review_state: ReviewState = ReviewState.UNREVIEWED
    evidence_ids: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=utcnow)


class Claim(BaseModel):
    id: str = Field(default_factory=lambda: new_id("clm"))
    case_id: str
    text: str
    claim_type: str = "factual"
    temporal_scope: str = ""
    spatial_scope: str = ""
    origin: str = "analyst"
    status: ClaimStatus = ClaimStatus.ACTIVE
    review_state: ReviewState = ReviewState.UNREVIEWED
    notes: str = ""
    created_at: str = Field(default_factory=utcnow)


class RelationType(StrEnum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    DERIVED_FROM = "derived_from"
    MENTIONS = "mentions"
    ORIGIN_HYPOTHESIS = "origin_hypothesis"
    CORROBORATES = "corroborates"


class Relation(BaseModel):
    id: str = Field(default_factory=lambda: new_id("rel"))
    case_id: str
    from_id: str
    to_id: str
    relation: RelationType
    rationale: str = ""
    method: str = "analyst"
    review_state: ReviewState = ReviewState.UNREVIEWED
    evidence_ids: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=utcnow)


class OriginCluster(BaseModel):
    id: str = Field(default_factory=lambda: new_id("ocl"))
    case_id: str
    member_ids: list[str] = Field(default_factory=list)
    indicators: list[str] = Field(default_factory=list)
    algorithm_version: str = ""
    confidence_label: str = "hypothesis"
    review_state: ReviewState = ReviewState.UNREVIEWED
    created_at: str = Field(default_factory=utcnow)


class AnalysisEvent(BaseModel):
    """Append-only record; ``prev_digest`` chains events for tamper-evidence."""

    id: str = Field(default_factory=lambda: new_id("aev"))
    case_id: str
    action: str
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    tool_fingerprint: str = ""
    prev_digest: str = ""
    digest: str = ""
    occurred_at: str = Field(default_factory=utcnow)


class CaseReport(BaseModel):
    """Durable report identity (OOVS-09): one row per materially rendered
    report. Revision N supersedes revision N-1 — the recipient-facing answer
    to "which exact document did you disseminate, and what replaced it?"."""

    id: str = Field(default_factory=lambda: new_id("rep"))
    case_id: str
    revision: int = 1
    supersedes: str = ""
    superseded_by: str = ""
    created_at: str = Field(default_factory=utcnow)


class ReportCorrection(BaseModel):
    """An analyst correction addressed at ONE specific registered report."""

    id: str = Field(default_factory=lambda: new_id("cor"))
    case_id: str
    corrected_report_id: str
    note: str
    created_at: str = Field(default_factory=utcnow)


class Dissemination(BaseModel):
    """One recorded shipment: which recipient received which report, when.
    Recipient follow-up is an operator action; this register makes it
    traceable, it sends nothing."""

    id: str = Field(default_factory=lambda: new_id("dsp"))
    case_id: str
    report_id: str
    recipient: str
    shipped_at: str = Field(default_factory=utcnow)
    note: str = ""


class AssessmentVector(BaseModel):
    """Explainable multi-dimensional assessment — never a single 'truth score'."""

    claim_id: str
    provenance_completeness: str = "unknown"
    evidence_directness: str = "unknown"
    independence: str = "unknown"
    source_transparency: str = "unknown"
    temporal_fit: str = "unknown"
    supporting_count: int = 0
    contradicting_count: int = 0
    missing_information: str = "unknown"
    reproducibility: str = "unknown"
    outcome: OutcomeLabel = OutcomeLabel.UNASSESSED
    caveats: list[str] = Field(default_factory=list)
    rule_version: str = ""
    computed_at: str = Field(default_factory=utcnow)
