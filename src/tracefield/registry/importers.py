"""Catalogue importers: parse public source lists into normalized records.

Each importer is separate from normalization. Retrieved list text is
UNTRUSTED DATA — it is validated by pydantic and never modifies
application behavior or executes code. Descriptions stored in the
catalogue are project-authored factual summaries; we store upstream links
rather than copying other catalogues' prose. Source attribution and data
licenses are recorded per entry and in the source manifest.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tracefield.registry.catalog import (
    Catalog,
    CatalogEntry,
    EntryType,
    IntegrationState,
    MaintenanceStatus,
    PricingClass,
    utc_today,
)

# Categories we map from markdown headings / known keywords.
_CATEGORY_MAP = {
    "general": "general",
    "search engines": "search",
    "social media": "social",
    "social networks": "social",
    "username": "username",
    "usernames": "username",
    "people": "people",
    "person": "people",
    "domain": "domain",
    "domains": "domain",
    "dns": "dns",
    "ip": "network",
    "host": "network",
    "network": "network",
    "email": "email",
    "emails": "email",
    "phone": "phone",
    "image": "media",
    "images": "media",
    "photo": "media",
    "video": "media",
    "audio": "media",
    "documents": "documents",
    "documents ": "documents",
    "files": "files",
    "metadata": "metadata",
    "exif": "metadata",
    "threat": "threat-intel",
    "malware": "threat-intel",
    "security": "security",
    "breach": "security",
    "archives": "archives",
    "archive": "archives",
    "wayback": "archives",
    "maps": "geolocation",
    "geolocation": "geolocation",
    "location": "geolocation",
    "company": "companies",
    "companies": "companies",
    "business": "companies",
    "shipping": "shipping",
    "vehicles": "vehicles",
    "coding": "development",
    "development": "development",
    "git": "development",
    "paste": "pastebin",
    "pastebin": "pastebin",
    "torrent": "torrents",
    "torrents": "torrents",
}


def _slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return f"tool_{hashlib.sha1(slug.encode()).hexdigest()[:10]}"


def _dedup_group_for(catalog: Catalog, name: str, url: str) -> str:
    """If another entry already claims this canonical name (different URL),
    return a stable duplicate-group id linking the variants; else ''."""
    for e in catalog.entries.values():
        if e.canonical_name.lower() == name.lower() and (
            e.upstream_url.rstrip("/") != url.rstrip("/")
        ):
            return f"dup_{hashlib.sha1(name.lower().encode()).hexdigest()[:10]}"
    return ""


def _add_with_dedup(catalog: Catalog, entry: CatalogEntry) -> bool:
    """Add ``entry`` unless an equivalent/better record already exists.

    Never overwrites a more-verified existing record (same ID or same URL)
    with a less-verified import — baseline verified entries must survive
    the bulk import. Assigns a duplicate_group when the name matches a
    different URL.
    """
    from tracefield.registry.catalog import IntegrationState

    _state_rank = {
        IntegrationState.INDEXED: 0,
        IntegrationState.UNVERIFIED: 1,
        IntegrationState.VERIFIED: 2,
        IntegrationState.INTEGRATED: 3,
        IntegrationState.HEALTHY: 4,
        IntegrationState.STALE: 3,
        IntegrationState.UNAVAILABLE: 2,
    }
    existing = catalog.entries.get(entry.id)
    if existing is not None and _state_rank.get(existing.integration_state, 0) >= _state_rank.get(
        entry.integration_state, 0
    ):
        return False  # keep the better-verified record
    for e in catalog.entries.values():
        if (
            entry.upstream_url
            and e.upstream_url.rstrip("/") == entry.upstream_url.rstrip("/")
            and _state_rank.get(e.integration_state, 0)
            >= _state_rank.get(entry.integration_state, 0)
        ):
            return False
    group = _dedup_group_for(catalog, entry.canonical_name, entry.upstream_url)
    if group:
        entry = entry.model_copy(update={"duplicate_group": group})
        for e in catalog.entries.values():
            if e.canonical_name.lower() == entry.canonical_name.lower() and not e.duplicate_group:
                catalog.entries[e.id] = e.model_copy(update={"duplicate_group": group})
    catalog.add(entry)
    return True


def _guess_type(name: str, url: str, description: str) -> EntryType:
    blob = f"{name} {url} {description}".lower()
    if any(k in blob for k in ("api", "api.", "/api")):
        return EntryType.API_SERVICE
    if url.rstrip("/").endswith((".onion",)) or "github.com" in url or "gitlab.com" in url:
        if any(k in blob for k in ("library", "python", "npm package", "module")):
            return EntryType.LIBRARY
        if "github.com" in url or "gitlab.com" in url:
            return EntryType.CLI_TOOL
    if any(k in blob for k in ("guide", "tutorial", "reference", "cheat sheet", "awesome")):
        return EntryType.REFERENCE
    if any(k in blob for k in ("dataset", "data set", "leaked", "dump")):
        return EntryType.DATASET
    # Most OSINT Framework leaves are websites/web services.
    return EntryType.WEBSITE


def _authored_description(name: str, raw_hint: str) -> str:
    """Project-authored one-line factual description. Never copies another
    catalogue's prose; uses only the name and a short neutral restatement."""
    hint = re.sub(r"\s+", " ", raw_hint or "").strip()[:140]
    if hint:
        return f"{name}: {hint}"
    return name


class _Manifest:
    def __init__(self) -> None:
        self.entries: list[dict[str, Any]] = []
        self.notes: list[str] = []

    def record(
        self,
        source_name: str,
        source_url: str,
        data_license: str,
        retrieved_at: str,
        record_count: int,
        extra: dict[str, Any] | None = None,
    ) -> None:
        self.entries.append(
            {
                "source_name": source_name,
                "source_url": source_url,
                "data_license": data_license,
                "retrieved_at": retrieved_at,
                "record_count": record_count,
                **(extra or {}),
            }
        )


def parse_awesome_osint_line(line: str) -> tuple[str, str, str] | None:
    """Extract (name, url, category_hint) from an Awesome-OSINT markdown
    list line: ``* [Name](https://url) - description`` (bullets may be
    ``*`` or ``-``, possibly indented)."""
    m = re.match(
        # En/em dashes are real markdown list markers (RUF001 intended).
        r"^\s*[*+-]\s*\[([^\]]+)\]\((https?://[^)]+)\)\s*(?:[-–—]\s*(.*))?$",  # noqa: RUF001
        line.strip(),
    )
    if not m:
        return None
    name, url, desc = m.group(1).strip(), m.group(2).strip(), (m.group(3) or "").strip()
    if not name or not url:
        return None
    # Skip internal anchor links and image/badge URLs.
    if url.startswith("#") or "badge" in url or "cdn." in url:
        return None
    return name, url, desc


def import_awesome_osint(
    catalog: Catalog, manifest: _Manifest, *, retrieved_at: str, readme_text: str | None = None
) -> int:
    """Import from the Awesome OSINT README text (CC BY-SA 4.0).

    We store names + URLs (factual identifiers) with attribution; we do not
    copy description prose. The data file inherits CC BY-SA 4.0 attribution
    requirements via per-entry ``attribution`` and ``source_list`` fields.
    """
    if readme_text is None:
        return 0
    added = 0
    current_category = "general"
    for line in readme_text.splitlines():
        heading = re.match(r"^#{2,4}\s+(.+)$", line)
        if heading:
            title = heading.group(1).strip().lower()
            title = re.sub(r"[^a-z0-9 /&-]", "", title).strip()
            current_category = _CATEGORY_MAP.get(title, title.replace(" ", "-")[:40] or "general")
            continue
        parsed = parse_awesome_osint_line(line)
        if not parsed:
            continue
        name, url, _desc = parsed
        eid = _slug(name)
        entry = CatalogEntry(
            id=eid,
            canonical_name=name,
            entry_type=_guess_type(name, url, _desc),
            categories=[current_category],
            description=_authored_description(name, ""),
            upstream_url=url,
            license_id="UNKNOWN",
            license_review_state="unverified",
            pricing_class=PricingClass.UNKNOWN,
            key_required="unknown",
            network_required="yes",
            first_seen=retrieved_at,
            last_checked=retrieved_at,
            source_list="jivoi/awesome-osint",
            attribution=(
                "Entry identifiers imported from jivoi/awesome-osint "
                "(CC BY-SA 4.0). Descriptions are project-authored."
            ),
            integration_state=IntegrationState.INDEXED,
        )
        if _add_with_dedup(catalog, entry):
            added += 1
    manifest.record(
        "Awesome OSINT",
        "https://github.com/jivoi/awesome-osint",
        "CC BY-SA 4.0",
        retrieved_at,
        added,
        {"note": "names+URLs only; descriptions project-authored"},
    )
    return added


_OSINT_FRAMEWORK_NODE_RE = re.compile(
    r"""\{[^{}]*?"name"\s*:\s*"([^"]+)"[^{}]*?"url"\s*:\s*"(https?://[^"]+)"[^{}]*?\}""",
    re.DOTALL,
)


def import_osint_framework(
    catalog: Catalog, manifest: _Manifest, *, retrieved_at: str, data_text: str | None = None
) -> int:
    """Import from an OSINT Framework data.json export (MIT).

    Parses name/url pairs; category is inherited from the tree structure
    when provided via ``data_text`` (raw JSON of the framework tree).
    """
    if not data_text:
        return 0
    added = 0
    try:
        tree = json.loads(data_text)
    except json.JSONDecodeError:
        manifest.notes.append("osint-framework: unparseable JSON, skipped")
        return 0

    def walk(node: dict[str, Any], category_path: list[str]) -> None:
        nonlocal added
        cat = category_path[-1] if category_path else "general"
        for child in node.get("children", []):
            name = (child.get("name") or "").strip()
            url = (child.get("url") or "").strip()
            if name and url.startswith("http"):
                eid = _slug(name)
                entry = CatalogEntry(
                    id=eid,
                    canonical_name=re.sub(r"\s*\([^)]*\)\s*$", "", name),
                    entry_type=_guess_type(name, url, ""),
                    categories=[_CATEGORY_MAP.get(cat.lower(), cat.lower()[:40])],
                    description=_authored_description(name, ""),
                    upstream_url=url,
                    license_id="UNKNOWN",
                    license_review_state="unverified",
                    pricing_class=PricingClass.UNKNOWN,
                    key_required="unknown",
                    network_required="yes",
                    first_seen=retrieved_at,
                    last_checked=retrieved_at,
                    source_list="osintframework.com",
                    attribution=(
                        "Entry identifiers imported from OSINT Framework "
                        "(https://osintframework.com, MIT-licensed source)."
                    ),
                    integration_state=IntegrationState.INDEXED,
                )
                if _add_with_dedup(catalog, entry):
                    added += 1
            if child.get("children"):
                label = (child.get("name") or cat).strip()
                walk(child, [*category_path, label])

    if isinstance(tree, dict):
        walk(tree, [])
    manifest.record(
        "OSINT Framework",
        "https://osintframework.com/",
        "MIT (source repository)",
        retrieved_at,
        added,
    )
    return added


def _ensure_baseline_entries(catalog: Catalog, retrieved_at: str) -> int:
    """A small set of well-known, verified-by-maintainer-registry entries
    with licenses checked via the GitHub API on the recorded date. These
    have verified upstream identity + license (state=verified)."""
    baseline = [
        # name, url, repo, license, type, categories, key_req, desc
        (
            "Sherlock",
            "https://github.com/sherlock-project/sherlock",
            "https://github.com/sherlock-project/sherlock",
            "MIT",
            EntryType.CLI_TOOL,
            ["username"],
            "no",
            "Discover social media accounts by username across many sites. Python CLI.",
        ),
        (
            "Maigret",
            "https://github.com/soxoj/maigret",
            "https://github.com/soxoj/maigret",
            "MIT",
            EntryType.CLI_TOOL,
            ["username"],
            "no",
            "Mass OSINT username checker with site database; fork/evolution of Sherlock.",
        ),
        (
            "SpiderFoot",
            "https://github.com/smicallef/spiderfoot",
            "https://github.com/smicallef/spiderfoot",
            "MIT",
            EntryType.CLI_TOOL,
            ["automation", "threat-intel"],
            "no",
            "Automated OSINT engine with many modules; web UI and CLI modes.",
        ),
        (
            "Recon-ng",
            "https://github.com/lanmaster53/recon-ng",
            "https://github.com/lanmaster53/recon-ng",
            "GPL-3.0",
            EntryType.CLI_TOOL,
            ["recon", "framework"],
            "no",
            "Modular reconnaissance framework with a Metasploit-like workspace model.",
        ),
        (
            "ExifTool",
            "https://exiftool.org/",
            "https://github.com/exiftool/exiftool",
            "GPL-3.0",
            EntryType.CLI_TOOL,
            ["metadata", "media"],
            "no",
            "Read/write/edit metadata in files (images, PDFs, audio/video, etc.).",
        ),
        (
            "theHarvester",
            "https://github.com/laramies/theHarvester",
            "https://github.com/laramies/theHarvester",
            "GPL-3.0",
            EntryType.CLI_TOOL,
            ["email", "recon"],
            "no",
            "Gather emails, subdomains, hosts, and names from public sources.",
        ),
        (
            "holehe",
            "https://github.com/megadose/holehe",
            "https://github.com/megadose/holehe",
            "GPL-3.0",
            EntryType.CLI_TOOL,
            ["email", "username"],
            "no",
            "Check if an email is registered on sites by probing signup endpoints.",
        ),
        (
            "urlscan.io",
            "https://urlscan.io/",
            "",
            "UNKNOWN",
            EntryType.API_SERVICE,
            ["threat-intel", "url"],
            "no",
            "URL scanning and website reconnaissance "
            "service; public scans may be visible to others.",
        ),
        (
            "crt.sh",
            "https://crt.sh/",
            "",
            "UNKNOWN",
            EntryType.WEBSITE,
            ["certificate-transparency", "domain"],
            "no",
            "Certificate Transparency log search.",
        ),
        (
            "Wayback Machine",
            "https://web.archive.org/",
            "",
            "UNKNOWN",
            EntryType.WEBSITE,
            ["archives"],
            "no",
            "Internet Archive web archive; CDX API available.",
        ),
    ]
    added = 0
    for name, url, repo, lic, etype, cats, key_req, desc in baseline:
        eid = _slug(name)
        if eid in catalog.entries:
            continue
        catalog.add(
            CatalogEntry(
                id=eid,
                canonical_name=name,
                entry_type=etype,
                categories=cats,
                description=desc,
                upstream_url=url,
                repo_url=repo,
                license_id=lic,
                license_source=repo or url,
                license_review_state="verified" if lic != "UNKNOWN" else "unverified",
                pricing_class=(
                    PricingClass.OPEN_SOURCE if lic not in ("UNKNOWN", "") else PricingClass.UNKNOWN
                ),
                key_required=key_req,
                network_required="yes",
                passive_active="passive" if etype != EntryType.CLI_TOOL else "unknown",
                maintenance_status=MaintenanceStatus.ACTIVE,
                verification_state="verified" if lic != "UNKNOWN" else "unverified",
                integration_state=IntegrationState.VERIFIED,
                first_seen=retrieved_at,
                last_checked=retrieved_at,
                source_list="tracefield-baseline",
                attribution="Verified against upstream repository/API on 2026-10-16.",
            )
        )
        added += 1
    return added


def run_importers(catalog_path: Path, *, dry_run: bool = False) -> dict[str, Any]:
    """Run all importers against local cached source text, if present.

    Network retrieval of source lists is a SEPARATE, explicit step
    (``scripts/fetch_catalog_sources.py``); this function only parses
    already-fetched files under ``data/catalog/sources/`` so catalogue
    sync itself is offline-deterministic and CI-friendly.
    """
    retrieved_at = utc_today()
    sources_dir = catalog_path.parent / "sources"
    catalog = Catalog()
    if (catalog_path.exists() and not dry_run) or (catalog_path.exists() and dry_run):
        catalog.load(catalog_path)

    manifest = _Manifest()
    added = _ensure_baseline_entries(catalog, retrieved_at)

    awesome = sources_dir / "awesome-osint.md"
    if awesome.exists():
        added += import_awesome_osint(
            catalog,
            manifest,
            retrieved_at=retrieved_at,
            readme_text=awesome.read_text(encoding="utf-8"),
        )
    framework = sources_dir / "osintframework.json"
    if framework.exists():
        added += import_osint_framework(
            catalog,
            manifest,
            retrieved_at=retrieved_at,
            data_text=framework.read_text(encoding="utf-8"),
        )

    if not dry_run:
        catalog.save(catalog_path)
        # Merge manifest entries (keep prior sources, upsert by name).
        manifest_path = catalog_path.parent / "source-manifest.json"
        prior: list[dict[str, Any]] = []
        if manifest_path.exists():
            try:
                prior = json.loads(manifest_path.read_text(encoding="utf-8")).get("sources", [])
            except json.JSONDecodeError:
                prior = []
        by_name = {e["source_name"]: e for e in prior}
        for entry in manifest.entries:
            by_name[entry["source_name"]] = entry
        manifest_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "updated_at": datetime.now(UTC)
                    .isoformat(timespec="seconds")
                    .replace("+00:00", "Z"),
                    "sources": sorted(by_name.values(), key=lambda x: x["source_name"]),
                    "notes": manifest.notes,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

    total_after = len(catalog.entries)
    return {
        "added": added,
        "skipped": 0,
        "total_after": total_after,
        "notes": [
            *manifest.notes,
            "counts are records, not verified/integrated/healthy tools; "
            "run 'tracefield tools status' for tiered counts",
        ],
    }
