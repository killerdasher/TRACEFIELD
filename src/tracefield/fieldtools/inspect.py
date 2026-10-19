"""Local file inspection: content-signature type detection, hashes,
filesystem + embedded metadata (via optional exiftool/ffprobe backends).

Everything here is local-only. Optional backends report UNAVAILABLE
honestly when the binary is missing — never silent success.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from rich.console import Console

from tracefield.security import redact_secrets, sanitize_for_terminal

EXIT_OK = 0
EXIT_UNAVAILABLE = 5

# Content signatures (magic bytes). Order matters: longer patterns first.
_MAGIC: tuple[tuple[bytes, str], ...] = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
    (b"BM", "image/bmp"),
    (b"\x1a\x45\xdf\xa3", "video/webm"),  # also matroska
    (b"OggS", "audio/ogg"),
    (b"ID3", "audio/mpeg"),
    (b"\xff\xfb", "audio/mpeg"),
    (b"\xff\xf3", "audio/mpeg"),
    (b"fLaC", "audio/flac"),
    (b"RIFF", "video/avi"),  # refined below for WAV/WEBP
    (b"%PDF-", "application/pdf"),
    (b"PK\x03\x04", "application/zip"),  # also docx/xlsx/jar
    (b"Rar!\x1a\x07", "application/vnd.rar"),
    (b"7z\xbc\xaf\x27\x1c", "application/x-7z-compressed"),
    (b"\x1f\x8b", "application/gzip"),
    (b"BZh", "application/x-bzip2"),
    (b"\xfd7zXZ\x00", "application/x-xz"),
    (b"\x00\x00\x01\xba", "video/mpeg"),
    (b"\x00\x00\x00\x1cftyp", "video/mp4"),  # offset check below
    (b"#!", "text/x-script"),
    (b"{", "application/json"),  # weak; refined by parse attempt
    (b"\xef\xbb\xbf", "text/plain"),  # UTF-8 BOM
)

_OFF_FTYP = 4  # mp4/mov family carries 'ftyp' at offset 4


def detect_media_type(path: str | Path) -> str:
    """Best-effort media type from content signatures, not just extension."""
    p = Path(path)
    with p.open("rb") as f:
        head = f.read(512)
    if len(head) >= 8 and head[4:8] == b"ftyp":
        brand = head[8:12]
        if brand in (b"qt  ",):
            return "video/quicktime"
        return "video/mp4"
    if head[:4] == b"RIFF" and len(head) >= 12:
        sub = head[8:12]
        if sub == b"WAVE":
            return "audio/wav"
        if sub == b"WEBP":
            return "image/webp"
        return "video/avi"
    for magic, mtype in _MAGIC:
        if head.startswith(magic):
            if mtype == "application/json":
                try:
                    json.loads(head.decode("utf-8", errors="strict") + "0" * 0)
                except Exception:
                    continue
                # Only claim JSON if the head actually parses as a JSON prefix;
                # conservative: fall through to text if unsure.
                return "application/json"
            return mtype
    if _looks_like_text(head):
        return "text/plain"
    return "application/octet-stream"


def _looks_like_text(head: bytes) -> bool:
    if not head:
        return True
    sample = head[:4096]
    if b"\x00" in sample:
        return False
    try:
        sample.decode("utf-8")
        return True
    except UnicodeDecodeError:
        # Allow high ratio of printable ASCII
        printable = sum(1 for b in sample if 32 <= b < 127 or b in (9, 10, 13))
        return printable / len(sample) > 0.85


def hash_file(path: str | Path, algorithm: str = "sha256") -> str:
    try:
        h = hashlib.new(algorithm)
    except ValueError as exc:
        raise ValueError(f"unsupported hash algorithm: {algorithm}") from exc
    with Path(path).open("rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def _fs_times(path: Path) -> dict[str, Any]:
    st = path.stat()

    def iso(ts: float) -> str:
        return datetime.fromtimestamp(ts, UTC).isoformat(timespec="seconds").replace("+00:00", "Z")

    out = {
        "size_bytes": st.st_size,
        "mtime": iso(st.st_mtime),
        "ctime": iso(st.st_ctime),
    }
    if hasattr(st, "st_birthtime"):
        out["birthtime"] = iso(st.st_birthtime)  # type: ignore[attr-defined]
    return out


def run_backend(
    argv: list[str], *, timeout_s: float = 30.0, max_output: int = 2_000_000
) -> tuple[int, str, str]:
    """Run an allowlisted local utility. Argument arrays only, never a shell.

    Returns (returncode, stdout, stderr). Raises FileNotFoundError when the
    binary is absent so callers can report UNAVAILABLE.
    """
    exe = argv[0]
    if shutil.which(exe) is None:
        raise FileNotFoundError(exe)
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
            env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LC_ALL": "C"},
        )
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    out = proc.stdout[:max_output]
    err = proc.stderr[:max_output]
    return proc.returncode, out, err


def exiftool_metadata(path: Path) -> dict[str, Any] | str:
    """Structured metadata via ExifTool JSON. Returns dict, or a status string:
    'UNAVAILABLE' when not installed, 'ERROR: ...' on failure."""
    try:
        rc, out, err = run_backend(["exiftool", "-json", "-n", "--", str(path)], timeout_s=60)
    except FileNotFoundError:
        return "UNAVAILABLE"
    if rc != 0:
        return f"ERROR: {redact_secrets(sanitize_for_terminal(err, max_length=200))}"
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return "ERROR: unparseable exiftool output"
    if not data or not isinstance(data[0], dict):
        return {}
    meta = data[0]
    meta.pop("SourceFile", None)
    return cast(dict[str, Any], redact_secrets_json(meta))


def ffprobe_streams(path: Path) -> dict[str, Any] | str:
    """Container/stream metadata via ffprobe JSON. Same status-string contract."""
    try:
        rc, out, err = run_backend(
            [
                "ffprobe",
                "-v",
                "error",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                "--",
                str(path),
            ],
            timeout_s=60,
        )
    except FileNotFoundError:
        return "UNAVAILABLE"
    if rc != 0:
        return f"ERROR: {redact_secrets(sanitize_for_terminal(err, max_length=200))}"
    try:
        return cast(dict[str, Any], redact_secrets_json(json.loads(out)))
    except json.JSONDecodeError:
        return "ERROR: unparseable ffprobe output"


def redact_secrets_json(obj: Any) -> Any:
    if isinstance(obj, str):
        return redact_secrets(obj)
    if isinstance(obj, dict):
        return {k: redact_secrets_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact_secrets_json(v) for v in obj]
    return obj


GPS_KEYS = {
    "GPSLatitude",
    "GPSLongitude",
    "GPSAltitude",
    "GPSCoordinates",
    "GPSPosition",
    "GPSDestLatitude",
    "GPSDestLongitude",
    "Composite:GPSLatitude",
    "Composite:GPSLongitude",
    "location",
}


def find_gps(meta: dict[str, Any]) -> list[str]:
    hits = []
    for k, v in meta.items():
        kl = k.lower()
        if any(g.lower() in kl for g in GPS_KEYS) or "gps" in kl:
            hits.append(f"{k}={v}")
    return hits


def inspect_file(path: Path, *, deep: bool = False) -> dict[str, Any]:
    """Full local inspection result. Never executes file content."""
    result: dict[str, Any] = {
        "path": str(path.resolve()),
        "filename": sanitize_for_terminal(path.name, max_length=200),
        "detected_media_type": detect_media_type(path),
        "extension": path.suffix.lower(),
        "hashes": {},
        "filesystem": _fs_times(path),
        "embedded_metadata": None,
        "media_streams": None,
        "backends": {},
        "warnings": [],
        "caveats": [
            "Metadata can be absent, stripped, edited, fabricated, copied, or "
            "regenerated. Presence of metadata does not prove authenticity; "
            "absence does not prove tampering.",
            "Filesystem timestamps reflect the local filesystem, not necessarily "
            "content creation time.",
        ],
    }
    for algo in ("sha256", "sha512"):
        try:
            result["hashes"][algo] = hash_file(path, algo)
        except ValueError:
            break
    result["hashes"]["md5"] = hash_file(path, "md5")  # identification aid only

    if deep:
        meta = exiftool_metadata(path)
        result["backends"]["exiftool"] = (
            "unavailable" if meta == "UNAVAILABLE" else "error" if isinstance(meta, str) else "ok"
        )
        if isinstance(meta, dict):
            result["embedded_metadata"] = meta
            gps = find_gps(meta)
            if gps:
                result["warnings"].append(
                    "SENSITIVE: GPS/location metadata present — "
                    + "; ".join(gps[:5])
                    + " (treated as file metadata, NOT a verified capture location; "
                    "redact before export)"
                )
        elif isinstance(meta, str) and meta != "UNAVAILABLE":
            result["warnings"].append(f"exiftool: {meta}")

        streams = ffprobe_streams(path)
        result["backends"]["ffprobe"] = (
            "unavailable"
            if streams == "UNAVAILABLE"
            else "error"
            if isinstance(streams, str)
            else "ok"
        )
        if isinstance(streams, dict):
            result["media_streams"] = streams
        elif isinstance(streams, str) and streams != "UNAVAILABLE":
            result["warnings"].append(f"ffprobe: {streams}")
    else:
        result["backends"] = {"exiftool": "not_requested", "ffprobe": "not_requested"}

    return result


def inspect_command_impl(path: Path, *, deep: bool, as_json: bool, console: Console) -> None:
    result = inspect_file(path, deep=deep)
    if as_json:
        console.print_json(json.dumps(result))
        return
    console.print(f"[bold]{result['filename']}[/bold]")
    console.print(f"  path:    {result['path']}")
    console.print(
        f"  type:    {result['detected_media_type']}  (extension: {result['extension'] or 'none'})"
    )
    for algo, digest in result["hashes"].items():
        console.print(f"  {algo:6}  {digest}")
    fs = result["filesystem"]
    console.print(f"  size:    {fs['size_bytes']} bytes")
    console.print(f"  mtime:   {fs['mtime']}")
    for w in result["warnings"]:
        console.print(f"  [yellow]warning:[/yellow] {sanitize_for_terminal(w)}")
    if deep:
        for backend, status in result["backends"].items():
            console.print(f"  backend {backend}: {status}")
        if result["embedded_metadata"]:
            console.print("  embedded metadata:")
            meta_str = json.dumps(result["embedded_metadata"], indent=4, sort_keys=True)
            for line in meta_str.splitlines():
                console.print(f"    {line}")
        if result["media_streams"]:
            streams = result["media_streams"].get("streams", [])
            if streams:
                console.print(f"  streams: {len(streams)}")
                for s in streams[:10]:
                    console.print(
                        f"    #{s.get('index', '?')} "
                        f"codec={s.get('codec_name', '?')} "
                        f"type={s.get('codec_type', '?')}"
                    )
    for caveat in result["caveats"]:
        console.print(f"  [dim]{caveat}[/dim]")


def hash_command_impl(path: Path, algorithm: str, as_json: bool, console: Console) -> None:
    try:
        digest = hash_file(path, algorithm)
    except ValueError as exc:
        console.print(f"[red]error:[/red] {exc}")
        raise SystemExit(1) from exc
    payload = {
        "path": str(path.resolve()),
        "algorithm": algorithm,
        "digest": digest,
        "size_bytes": path.stat().st_size,
    }
    if as_json:
        console.print_json(json.dumps(payload))
    else:
        console.print(f"{algorithm}  {digest}  {path}")
