"""SQLite local store with explicit schema migrations and foreign keys.

Binary evidence is never stored in rows; large blobs live in the case
directory and are referenced by relative path + content hash.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import Any

from tracefield import SCHEMA_VERSION

assert SCHEMA_VERSION == 1, "add a migration for a new schema version"

_MIGRATION_1 = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cases (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    purpose TEXT NOT NULL DEFAULT '',
    scope TEXT NOT NULL DEFAULT '',
    owner_label TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'open',
    retention_policy TEXT NOT NULL DEFAULT 'default',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    locator TEXT NOT NULL,
    publisher TEXT NOT NULL DEFAULT '',
    source_type TEXT NOT NULL DEFAULT 'web_page',
    access_method TEXT NOT NULL DEFAULT 'manual',
    published_at TEXT NOT NULL DEFAULT '',
    first_seen_at TEXT NOT NULL,
    collected_at TEXT NOT NULL DEFAULT '',
    collection_agent TEXT NOT NULL DEFAULT '',
    visibility TEXT NOT NULL DEFAULT 'public',
    limitations TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_sources_case ON sources(case_id);

CREATE TABLE IF NOT EXISTS evidence (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    source_id TEXT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    sha256 TEXT NOT NULL,
    media_type TEXT NOT NULL,
    storage_ref TEXT NOT NULL,
    size_bytes INTEGER NOT NULL DEFAULT 0,
    captured_at TEXT NOT NULL,
    acquisition_method TEXT NOT NULL DEFAULT 'manual',
    excerpt TEXT NOT NULL DEFAULT '',
    privacy_label TEXT NOT NULL DEFAULT 'unknown',
    retention_status TEXT NOT NULL DEFAULT 'retained'
);
CREATE INDEX IF NOT EXISTS idx_evidence_case ON evidence(case_id);
CREATE INDEX IF NOT EXISTS idx_evidence_sha ON evidence(sha256);

CREATE TABLE IF NOT EXISTS claims (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    claim_type TEXT NOT NULL DEFAULT 'factual',
    temporal_scope TEXT NOT NULL DEFAULT '',
    spatial_scope TEXT NOT NULL DEFAULT '',
    origin TEXT NOT NULL DEFAULT 'analyst',
    status TEXT NOT NULL DEFAULT 'active',
    review_state TEXT NOT NULL DEFAULT 'unreviewed',
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_claims_case ON claims(case_id);

CREATE TABLE IF NOT EXISTS observations (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    evidence_id TEXT NOT NULL DEFAULT '',
    tool_name TEXT NOT NULL,
    tool_version TEXT NOT NULL DEFAULT '',
    raw_ref TEXT NOT NULL DEFAULT '',
    returned_at TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_obs_case ON observations(case_id);

CREATE TABLE IF NOT EXISTS assertions (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    claim_id TEXT NOT NULL DEFAULT '',
    statement TEXT NOT NULL,
    method TEXT NOT NULL DEFAULT 'analyst',
    attribution TEXT NOT NULL DEFAULT '',
    uncertainty TEXT NOT NULL DEFAULT 'unknown',
    review_state TEXT NOT NULL DEFAULT 'unreviewed',
    evidence_ids TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_assert_case ON assertions(case_id);

CREATE TABLE IF NOT EXISTS relations (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    from_id TEXT NOT NULL,
    to_id TEXT NOT NULL,
    relation TEXT NOT NULL,
    rationale TEXT NOT NULL DEFAULT '',
    method TEXT NOT NULL DEFAULT 'analyst',
    review_state TEXT NOT NULL DEFAULT 'unreviewed',
    evidence_ids TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rel_case ON relations(case_id);

CREATE TABLE IF NOT EXISTS origin_clusters (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    member_ids TEXT NOT NULL DEFAULT '[]',
    indicators TEXT NOT NULL DEFAULT '[]',
    algorithm_version TEXT NOT NULL DEFAULT '',
    confidence_label TEXT NOT NULL DEFAULT 'hypothesis',
    review_state TEXT NOT NULL DEFAULT 'unreviewed',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ocl_case ON origin_clusters(case_id);

CREATE TABLE IF NOT EXISTS analysis_events (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    action TEXT NOT NULL,
    inputs TEXT NOT NULL DEFAULT '[]',
    outputs TEXT NOT NULL DEFAULT '[]',
    tool_fingerprint TEXT NOT NULL DEFAULT '',
    prev_digest TEXT NOT NULL DEFAULT '',
    digest TEXT NOT NULL DEFAULT '',
    occurred_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_aev_case ON analysis_events(case_id);

CREATE TABLE IF NOT EXISTS catalog (
    id TEXT PRIMARY KEY,
    canonical_name TEXT NOT NULL,
    aliases TEXT NOT NULL DEFAULT '[]',
    entry_type TEXT NOT NULL,
    categories TEXT NOT NULL DEFAULT '[]',
    capabilities TEXT NOT NULL DEFAULT '[]',
    description TEXT NOT NULL DEFAULT '',
    upstream_url TEXT NOT NULL DEFAULT '',
    repo_url TEXT NOT NULL DEFAULT '',
    upstream_version TEXT NOT NULL DEFAULT '',
    license_id TEXT NOT NULL DEFAULT 'UNKNOWN',
    license_source TEXT NOT NULL DEFAULT '',
    license_review_state TEXT NOT NULL DEFAULT 'unverified',
    pricing_class TEXT NOT NULL DEFAULT 'unknown',
    key_required TEXT NOT NULL DEFAULT 'unknown',
    key_env_vars TEXT NOT NULL DEFAULT '[]',
    auth_method TEXT NOT NULL DEFAULT '',
    rate_limits TEXT NOT NULL DEFAULT '',
    terms_url TEXT NOT NULL DEFAULT '',
    network_required TEXT NOT NULL DEFAULT 'unknown',
    data_exposure_warning TEXT NOT NULL DEFAULT '',
    passive_active TEXT NOT NULL DEFAULT 'unknown',
    maintenance_status TEXT NOT NULL DEFAULT 'unknown',
    verification_state TEXT NOT NULL DEFAULT 'unverified',
    integration_state TEXT NOT NULL DEFAULT 'indexed',
    first_seen TEXT NOT NULL,
    last_checked TEXT NOT NULL,
    health_checked_at TEXT NOT NULL DEFAULT '',
    health_result TEXT NOT NULL DEFAULT '',
    limitations TEXT NOT NULL DEFAULT '',
    duplicate_group TEXT NOT NULL DEFAULT '',
    source_list TEXT NOT NULL DEFAULT '',
    attribution TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_catalog_name ON catalog(canonical_name);
CREATE INDEX IF NOT EXISTS idx_catalog_type ON catalog(entry_type);
CREATE INDEX IF NOT EXISTS idx_catalog_state ON catalog(integration_state);

CREATE TABLE IF NOT EXISTS providers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    access_url TEXT NOT NULL DEFAULT '',
    auth_type TEXT NOT NULL DEFAULT 'none',
    free_tier TEXT NOT NULL DEFAULT 'unknown',
    quota_docs TEXT NOT NULL DEFAULT '',
    terms_url TEXT NOT NULL DEFAULT '',
    exposure_warning TEXT NOT NULL DEFAULT '',
    checked_at TEXT NOT NULL DEFAULT '',
    verification_state TEXT NOT NULL DEFAULT 'unverified'
);

-- Cross-case provenance guard: evidence must reference a source in the
-- SAME case. Prevents a source from case A anchoring evidence in case B
-- (which would orphan the evidence when case A is deleted).
CREATE TRIGGER IF NOT EXISTS trg_evidence_same_case_ins
BEFORE INSERT ON evidence
BEGIN
    SELECT CASE WHEN NEW.source_id != '' AND NOT EXISTS (
        SELECT 1 FROM sources s
        WHERE s.id = NEW.source_id AND s.case_id = NEW.case_id
    )
    THEN RAISE(ABORT, 'evidence.source_id must belong to the same case') END;
END;

CREATE TRIGGER IF NOT EXISTS trg_evidence_same_case_upd
BEFORE UPDATE OF source_id, case_id ON evidence
BEGIN
    SELECT CASE WHEN NEW.source_id != '' AND NOT EXISTS (
        SELECT 1 FROM sources s
        WHERE s.id = NEW.source_id AND s.case_id = NEW.case_id
    )
    THEN RAISE(ABORT, 'evidence.source_id must belong to the same case') END;
END;
"""

_MIGRATIONS: dict[int, str] = {1: _MIGRATION_1}


class SchemaVersionError(RuntimeError):
    """The database was written by a newer TRACEFIELD than this build.

    Refusing loudly beats guessing: an unknown future schema must never be
    silently opened (and potentially mis-parsed) by an older binary.
    """


class StorageUnavailableError(RuntimeError):
    """The store could not be opened (locked, corrupt, or unwritable).

    A storage *availability* problem — not a bug and not a schema mismatch.
    The CLI maps this to the documented "unavailable" exit code (5) so a
    concurrent-writer lock or a damaged file is never reported as a generic
    failure (exit 1). Cause carries the underlying sqlite3 error.
    """


class Database:
    """Thin wrapper over sqlite3 with migrations and foreign-key enforcement."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        try:
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON")
            # WAL probe raises DatabaseError on a corrupt/truncated file.
            self._conn.execute("PRAGMA journal_mode = WAL")
            self._conn.execute("PRAGMA busy_timeout = 5000")
            # Restrict at-rest permissions: case data must not be world-readable.
            self.migrate()
        except Exception:
            # A half-built instance (corrupt/truncated file, newer-schema
            # refusal, any setup or migration failure) must not leak an open
            # connection into the GC unraisable handler.
            self._conn.close()
            raise
        with suppress(OSError):
            self.path.chmod(0o600)

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        try:
            yield self._conn
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    def migrate(self) -> None:
        cur = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='meta'"
        )
        if cur.fetchone() is None:
            version = 0
        else:
            row = self._conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
            version = int(row["value"]) if row else 0
        if version > SCHEMA_VERSION:
            raise SchemaVersionError(
                f"database schema v{version} is newer than this build supports "
                f"(v{SCHEMA_VERSION}); upgrade TRACEFIELD or restore a matching backup"
            )
        for target in range(version + 1, SCHEMA_VERSION + 1):
            script = _MIGRATIONS[target]
            with self.tx() as conn:
                conn.executescript(script)
                conn.execute(
                    "INSERT OR REPLACE INTO meta(key, value) VALUES('schema_version', ?)",
                    (str(target),),
                )

    @property
    def schema_version(self) -> int:
        row = self._conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        return int(row["value"]) if row else 0

    def close(self) -> None:
        self._conn.close()

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Cursor:
        return self._conn.execute(sql, params)

    def executemany(self, sql: str, seq: list[tuple[Any, ...]]) -> sqlite3.Cursor:
        return self._conn.executemany(sql, seq)

    def commit(self) -> None:
        self._conn.commit()
