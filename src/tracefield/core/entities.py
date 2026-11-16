"""Entity Core v1 (Phase 22): entities, aliases, mentions, match candidates.

An entity is a recorded analytical object — never proof that a real-world
identity has been established. A mention records that some existing case
record (source, evidence, claim, observation, or assertion) refers to the
entity; the mention class describes HOW the reference was obtained, never
whether it is true. Identity questions are pairwise, analyst-decided, and
auditable: nothing here merges entities, scores similarity, or upgrades an
unreviewed candidate into a fact.

Design contract (extends D18/D19 spirit):
- **Additive only**: new tables in schema v3; no existing table changes.
- **Referential integrity at the DB layer**: mentions validate ``record_id``
  against the existing record tables in the SAME case via triggers (the
  established polymorphic pattern used by ``relations``).
- **Deterministic**: alias normalization is pure (NFKC + casefold +
  whitespace collapse) so identical inputs produce identical rows.
- **No auto-merge, no fuzzy scoring** — those are later phases.

These models are pure data: they never import storage, network, or TUI code.
"""

from __future__ import annotations

import unicodedata
from enum import StrEnum

from pydantic import BaseModel, Field

from tracefield.core.domain import ReviewState, new_id, utcnow

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class EntityType(StrEnum):
    PERSON = "person"
    ORGANISATION = "organisation"
    ACCOUNT = "account"
    DOMAIN = "domain"
    ASSET = "asset"
    EVENT = "event"
    DOCUMENT = "document"
    OTHER = "other"


class MentionClass(StrEnum):
    """How a mention was obtained — provenance of the reference, not truth."""

    EXACT = "exact"  # the referenced record is the entity's own id-bearing record
    STATED = "stated"  # the record's content states the label explicitly
    INFERRED = "inferred"  # an analyst inferred the reference


ENTITY_TYPES = frozenset(t.value for t in EntityType)
MENTION_CLASSES = frozenset(c.value for c in MentionClass)


def normalize_alias(alias: str) -> str:
    """Deterministic alias normalization for duplicate detection.

    NFKC + casefold + whitespace collapse. Purely lexical: two aliases that
    normalize equal are recorded as duplicates of one another — that says
    nothing about whether they denote the same real-world subject.
    """
    normalized = unicodedata.normalize("NFKC", alias)
    return " ".join(normalized.casefold().split())


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class Entity(BaseModel):
    """A recorded analytical object within one case."""

    id: str = Field(default_factory=lambda: new_id("ent"))
    case_id: str
    entity_type: EntityType = EntityType.OTHER
    canonical_label: str
    notes: str = ""
    created_at: str = Field(default_factory=utcnow)
    updated_at: str = Field(default_factory=utcnow)


class EntityAlias(BaseModel):
    """A recorded alternative label for an entity (provenance-bearing)."""

    id: str = Field(default_factory=lambda: new_id("eal"))
    case_id: str
    entity_id: str
    alias: str
    normalized: str = ""
    created_at: str = Field(default_factory=utcnow)


class EntityMention(BaseModel):
    """A traceable reference from an existing case record to an entity.

    ``record_id`` is polymorphic (source/evidence/claim/observation/
    assertion) and is validated at the database layer to point at a record
    in the SAME case — a dangling or cross-case id can never be stored.
    """

    id: str = Field(default_factory=lambda: new_id("men"))
    case_id: str
    entity_id: str
    record_id: str
    mention_class: MentionClass = MentionClass.STATED
    note: str = ""
    created_at: str = Field(default_factory=utcnow)


class EntityMatchCandidate(BaseModel):
    """A pairwise identity question between two entities of one case.

    The review state belongs HERE — on the proposed match — never on the
    entities themselves. A rejected candidate is retained for audit; no
    state ever merges the two entity records.
    """

    id: str = Field(default_factory=lambda: new_id("emc"))
    case_id: str
    entity_a_id: str
    entity_b_id: str
    rationale: str = ""
    review_state: ReviewState = ReviewState.UNREVIEWED
    review_note: str = ""
    created_at: str = Field(default_factory=utcnow)
    reviewed_at: str = ""
