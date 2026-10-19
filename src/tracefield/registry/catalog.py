"""Tool catalogue: inert metadata only.

A registry entry is DATA, never executable code. Nothing in this module
loads, imports, or executes catalogue content.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator


class EntryType(StrEnum):
    CLI_TOOL = "cli_tool"
    LIBRARY = "library"
    API_SERVICE = "api_service"
    WEBSITE = "website"
    DATASET = "dataset"
    REFERENCE = "reference"
    WORKFLOW = "workflow"


class PricingClass(StrEnum):
    FREE = "free"
    OPEN_SOURCE = "open_source"
    FREE_TIER = "free_tier"
    PAID = "paid"
    FREEMIUM = "freemium"
    UNKNOWN = "unknown"


class IntegrationState(StrEnum):
    INDEXED = "indexed"  # ingested, nothing more claimed
    VERIFIED = "verified"  # upstream identity + license checked
    INTEGRATED = "integrated"  # a runnable adapter exists in tracefield
    HEALTHY = "healthy"  # adapter passed a recent health check
    STALE = "stale"  # health check overdue or last check old
    UNAVAILABLE = "unavailable"  # checked and found unreachable/removed
    UNVERIFIED = "unverified"  # verification attempted but incomplete


class MaintenanceStatus(StrEnum):
    ACTIVE = "active"
    QUIET = "quiet"
    ARCHIVED = "archived"
    UNKNOWN = "unknown"


class CatalogEntry(BaseModel):
    """Strict, versioned registry record. Descriptions are project-authored
    factual summaries; we store upstream links rather than copying other
    catalogues' prose."""

    schema_version: int = 1
    id: str
    canonical_name: str
    aliases: list[str] = Field(default_factory=list)
    entry_type: EntryType
    categories: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    description: str = ""  # project-authored, concise, factual
    upstream_url: str = ""
    repo_url: str = ""
    upstream_version: str = ""
    license_id: str = "UNKNOWN"
    license_source: str = ""
    license_review_state: str = "unverified"
    pricing_class: PricingClass = PricingClass.UNKNOWN
    key_required: str = "unknown"  # yes | no | unknown
    key_env_vars: list[str] = Field(default_factory=list)  # names only, never values
    auth_method: str = ""
    rate_limits: str = ""
    terms_url: str = ""
    network_required: str = "unknown"
    data_exposure_warning: str = ""
    passive_active: str = "unknown"
    maintenance_status: MaintenanceStatus = MaintenanceStatus.UNKNOWN
    verification_state: str = "unverified"
    integration_state: IntegrationState = IntegrationState.INDEXED
    first_seen: str
    last_checked: str
    health_checked_at: str = ""
    health_result: str = ""
    limitations: str = ""
    duplicate_group: str = ""
    source_list: str = ""
    attribution: str = ""

    @field_validator("id")
    @classmethod
    def _id_shape(cls, v: str) -> str:
        if not v or len(v) > 200:
            raise ValueError("id must be 1..200 chars")
        return v

    @field_validator("upstream_url", "repo_url")
    @classmethod
    def _url_scheme(cls, v: str) -> str:
        if v and not v.startswith(("http://", "https://")):
            raise ValueError("urls must be http(s)")
        return v


def utc_today() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


class Catalog:
    """In-memory catalogue with JSONL persistence. Loaders treat file
    content as untrusted data — validated by pydantic, never executed."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self.entries: dict[str, CatalogEntry] = {}
        self.import_errors: list[str] = []
        if path and path.exists():
            self.load(path)

    def load(self, path: Path) -> int:
        count = 0
        with path.open("r", encoding="utf-8") as f:
            for lineno, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    entry = CatalogEntry.model_validate(data)
                except Exception as exc:
                    self.import_errors.append(f"{path.name}:{lineno}: {exc}")
                    continue
                self.entries[entry.id] = entry
                count += 1
        self.path = path
        return count

    def save(self, path: Path | None = None) -> None:
        target = path or self.path
        if target is None:
            raise ValueError("no path")
        with target.open("w", encoding="utf-8") as f:
            for eid in sorted(self.entries):
                f.write(self.entries[eid].model_dump_json() + "\n")
        self.path = target

    def add(self, entry: CatalogEntry) -> None:
        self.entries[entry.id] = entry

    def search(
        self,
        query: str = "",
        *,
        entry_type: str | None = None,
        category: str | None = None,
        license_id: str | None = None,
        key_required: str | None = None,
        integration_state: str | None = None,
        network_required: str | None = None,
        limit: int = 50,
    ) -> list[CatalogEntry]:
        q = query.lower()
        out = []
        for e in self.entries.values():
            if entry_type and e.entry_type.value != entry_type:
                continue
            if category and category not in e.categories:
                continue
            if license_id and e.license_id != license_id:
                continue
            if key_required and e.key_required != key_required:
                continue
            if integration_state and e.integration_state.value != integration_state:
                continue
            if network_required and e.network_required != network_required:
                continue
            if q:
                hay = " ".join(
                    [
                        e.canonical_name,
                        e.description,
                        " ".join(e.aliases),
                        " ".join(e.categories),
                        " ".join(e.capabilities),
                    ]
                ).lower()
                if q not in hay:
                    continue
            out.append(e)
        out.sort(key=lambda e: e.canonical_name.lower())
        return out[:limit]

    def get(self, entry_id: str) -> CatalogEntry | None:
        if entry_id in self.entries:
            return self.entries[entry_id]
        for e in self.entries.values():
            if e.canonical_name.lower() == entry_id.lower():
                return e
            if entry_id.lower() in [a.lower() for a in e.aliases]:
                return e
        return None

    def counts(self) -> dict[str, Any]:
        """Truthful tiered counts. Indexed ≠ integrated ≠ healthy."""
        by_state: dict[str, int] = {}
        by_type: dict[str, int] = {}
        licenses: dict[str, int] = {}
        for e in self.entries.values():
            by_state[e.integration_state.value] = by_state.get(e.integration_state.value, 0) + 1
            by_type[e.entry_type.value] = by_type.get(e.entry_type.value, 0) + 1
            licenses[e.license_id] = licenses.get(e.license_id, 0) + 1
        return {
            "total_records": len(self.entries),
            "by_integration_state": by_state,
            "by_entry_type": by_type,
            "by_license": licenses,
            "import_errors": len(self.import_errors),
        }

    def validate(self) -> list[str]:
        """Catalogue lint: schema already enforced at load; check the rest."""
        problems: list[str] = list(self.import_errors)
        seen_ids: set[str] = set()
        seen_names: dict[str, str] = {}
        for e in self.entries.values():
            if e.id in seen_ids:
                problems.append(f"duplicate id: {e.id}")
            seen_ids.add(e.id)
            key = e.canonical_name.lower()
            # Same name, different id: allowed only if duplicate_group set.
            if key in seen_names and seen_names[key] != e.id and not e.duplicate_group:
                problems.append(
                    f"name collision without duplicate_group: "
                    f"{e.canonical_name!r} ({seen_names[key]} vs {e.id})"
                )
            seen_names[key] = e.id
            if not e.upstream_url:
                problems.append(f"{e.id}: missing upstream_url")
            if e.license_id == "UNKNOWN" and e.license_review_state == "verified":
                problems.append(f"{e.id}: license marked verified but is UNKNOWN")
            if e.integration_state == IntegrationState.INTEGRATED:
                problems.append(
                    f"{e.id}: integration_state=integrated but no adapter "
                    "manifest reference recorded (adapters are separate)"
                )
            for env in e.key_env_vars:
                if "=" in env or len(env) > 100:
                    problems.append(f"{e.id}: suspicious key_env_vars entry {env!r}")
        return problems
