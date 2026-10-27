"""Case export with integrity manifest and optional redaction.

Correct order of operations (regression-tested):
1. Copy evidence into the export dir with *writable* permissions.
2. If redaction is on, rewrite text-like files in place (this changes
   their digests — the manifest must therefore be built AFTER redaction).
3. Emit SENSITIVE_METADATA.txt listing files whose embedded metadata
   contains GPS/location keys (key NAMES only, never coordinate values,
   when redaction is on). Binary originals are never silently rewritten:
   rewriting would invalidate the very digests the manifest asserts.
4. Build the manifest over the FINAL exported bytes.
5. Write reports (also redacted) and the export README. The two report
   renderings come from ONE registered payload — a single durable report
   identity (schema v2), with the shipment recorded when ``recipient`` is
   given.
"""

from __future__ import annotations

import json
import shutil
import stat
from pathlib import Path

from tracefield.config import Settings
from tracefield.core.domain import Case
from tracefield.core.provenance import IntegrityManifest
from tracefield.reporting.build import (
    apply_report_identity,
    build_case_payload,
    render_markdown,
)
from tracefield.security import redact_secrets
from tracefield.storage.database import Database
from tracefield.storage.workspace import CaseWorkspace


def _make_writable(path: Path) -> None:
    try:
        mode = path.stat().st_mode
        path.chmod(mode | stat.S_IWUSR)
    except OSError:
        pass


def _detect_sensitive_metadata(export_dir: Path) -> list[tuple[str, list[str]]]:
    """Scan exported evidence for GPS/location-like keys in text/JSON files
    and, when exiftool is available, in image/document binaries.

    Returns (relative_path, [key names]) — key names only.
    """
    findings: list[tuple[str, list[str]]] = []
    from tracefield.fieldtools.inspect import exiftool_metadata, find_gps

    ev_dir = export_dir / "evidence"
    if not ev_dir.exists():
        return findings
    for path in sorted(ev_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(ev_dir).as_posix()
        keys: list[str] = []
        # Text/JSON scan
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            text = ""
        if text:
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                data = None
            if isinstance(data, dict):
                from tracefield.fieldtools.inspect import find_gps as _fg

                for hit in _fg(data):
                    keys.append(hit.split("=", 1)[0])
        # Binary scan via exiftool (optional)
        meta = exiftool_metadata(path)
        if isinstance(meta, dict):
            for hit in find_gps(meta):
                key = hit.split("=", 1)[0]
                if key not in keys:
                    keys.append(key)
        if keys:
            findings.append((rel, keys))
    return findings


def export_case(
    settings: Settings,
    db: Database,
    ws: CaseWorkspace,
    case: Case,
    output: Path,
    *,
    redact: bool = True,
    recipient: str = "",
) -> None:
    output.mkdir(parents=True, exist_ok=True)
    case_dir = ws.case_dir(case.id)
    ev_dir = output / "evidence"
    # Copy the case's evidence subtree itself (not the whole case dir, which
    # would nest it as evidence/evidence/...).
    case_ev = case_dir / "evidence"
    if case_ev.exists():
        shutil.copytree(case_ev, ev_dir, dirs_exist_ok=True)
        # Copies inherit 0o400 from immutable originals; make writable so
        # redaction (and user inspection) can proceed.
        for p in ev_dir.rglob("*"):
            if p.is_file():
                _make_writable(p)

    if redact:
        for p in ev_dir.rglob("*") if ev_dir.exists() else []:
            if not p.is_file() or p.stat().st_size > 5_000_000:
                continue
            try:
                text = p.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            cleaned = redact_secrets(text)
            if cleaned != text:
                p.write_text(cleaned, encoding="utf-8")

    # Sensitive-metadata advisory (key names only; no coordinate values
    # are written when redaction is enabled).
    sensitive = _detect_sensitive_metadata(output)
    lines = [
        "TRACEFIELD export — sensitive metadata advisory",
        "=" * 47,
        "",
        "The following exported files contain GPS/location-like metadata",
        "keys, detected via local metadata backends. Coordinates can",
        "identify people and places; review before sharing this export.",
        "",
    ]
    if sensitive:
        for rel, keys in sensitive:
            lines.append(f"- {rel}")
            for k in keys:
                lines.append(f"    key: {k}")
    else:
        lines.append(
            "(none detected — absence is not proof of absence; "
            "metadata may have been stripped before collection)"
        )
    lines.append("")
    lines.append(
        "NOTE: binary evidence files were NOT rewritten to strip GPS — "
        "rewriting would invalidate the integrity digests this export "
        "asserts. Strip sensitive metadata from originals BEFORE attaching "
        "them if the source itself must not retain coordinates."
    )
    (output / "SENSITIVE_METADATA.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Manifest over FINAL bytes, after any redaction.
    manifest = IntegrityManifest.build_from_dir(case.id, output, redaction_applied=redact)
    (output / "manifest.json").write_text(manifest.to_json(), encoding="utf-8")

    # ONE payload, registered ONCE: report.json and report.md are two
    # renderings of the same durable identity. Registering per format would
    # mint two revisions for one shipped document — a false correction trail.
    payload = build_case_payload(settings, db, case)
    identity = apply_report_identity(db, payload, case.id)
    report_json = json.dumps(payload, indent=2, sort_keys=True)
    report_md = render_markdown(payload)
    if redact:
        report_json = redact_secrets(report_json)
        report_md = redact_secrets(report_md)
    (output / "report.json").write_text(report_json + "\n", encoding="utf-8")
    (output / "report.md").write_text(report_md, encoding="utf-8")

    supersedes_clause = (
        f", supersedes {identity.supersedes}" if identity.supersedes else ", first revision"
    )
    readme = (
        "TRACEFIELD case export\n"
        "=====================\n"
        "manifest.json           — integrity manifest (SHA-256 per evidence "
        "file, built after redaction)\n"
        "report.md / report.json — case report "
        f"{identity.id} (revision {identity.revision}{supersedes_clause}) — two "
        "renderings of one registered document; corrections recorded against "
        "its lineage appear in the report's Corrections section\n"
        "SENSITIVE_METADATA.txt  — GPS/location metadata advisory\n"
        "evidence/               — evidence copies (content-addressed)\n\n"
        "Digests prove byte integrity of files in THIS export at generation\n"
        "time only. Deleting the active TRACEFIELD database does NOT erase\n"
        "this export or any other copies you have made.\n"
        "Secret redaction was " + ("ENABLED" if redact else "DISABLED") + ".\n"
    )
    if recipient:
        from tracefield.storage.repositories import ReportRepo

        shipment = ReportRepo(db).add_shipment(case.id, identity.id, recipient)
        readme += (
            f"\nRecorded shipment: report {identity.id} (revision "
            f'{identity.revision}) to recipient "{recipient}" at '
            f"{shipment.shipped_at} (dissemination entry {shipment.id}).\n"
            "Replaced or corrected this report later? Recipients on record —\n"
            "see `tracefield report-history` — must be told which revision is\n"
            "current; this register exists to make that notification possible.\n"
        )
    (output / "EXPORT_README.txt").write_text(readme, encoding="utf-8")


def verify_manifest(export_dir: Path) -> tuple[bool, list[str]]:
    """Re-hash exported evidence and compare with the manifest."""
    problems: list[str] = []
    manifest_path = export_dir / "manifest.json"
    if not manifest_path.exists():
        return False, ["manifest.json missing"]
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    import hashlib

    for entry in data.get("files", []):
        path = export_dir / "evidence" / entry["storage_ref"]
        if not path.exists():
            problems.append(f"missing file: {entry['storage_ref']}")
            continue
        h = hashlib.sha256(path.read_bytes()).hexdigest()
        if h != entry["sha256"]:
            problems.append(f"digest mismatch: {entry['storage_ref']}")
    return (not problems), problems
