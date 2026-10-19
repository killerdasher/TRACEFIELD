"""Local OCR via Tesseract. Output is machine-derived text, never a
verified transcription. Reports UNAVAILABLE honestly when not installed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.markup import escape

from tracefield.fieldtools.inspect import hash_file, run_backend
from tracefield.security import redact_secrets, sanitize_for_terminal


def ocr_image(path: Path, *, lang: str = "eng", timeout_s: float = 60.0) -> dict[str, Any]:
    """Run Tesseract on a single image. Returns a result dict with a
    ``status`` field: ok | UNAVAILABLE | ERROR."""
    try:
        # Use the absolute path so a relative name beginning with '-' cannot
        # be parsed as an option by tesseract.
        rc, out, err = run_backend(
            ["tesseract", str(path.resolve()), "stdout", "-l", lang],
            timeout_s=timeout_s,
            max_output=5_000_000,
        )
    except FileNotFoundError:
        return {
            "status": "UNAVAILABLE",
            "detail": "tesseract is not installed; install it to enable local OCR",
        }
    if rc != 0:
        return {
            "status": "ERROR",
            "detail": redact_secrets(sanitize_for_terminal(err, max_length=300)),
        }
    return {"status": "ok", "text": redact_secrets(out)}


def ocr_command_impl(path: Path, *, as_json: bool, console: Console) -> None:
    result = {
        "path": str(path.resolve()),
        "source_sha256": hash_file(path),
        "method": "tesseract-local",
        "derived": True,
        "caveat": (
            "OCR output is machine-derived and is NOT a verified transcription. "
            "Recognition errors are routine; always re-check against the image."
        ),
        **ocr_image(path),
    }
    if as_json:
        console.print_json(json.dumps(result))
        return
    status = result["status"]
    if status == "UNAVAILABLE":
        console.print(f"[yellow]UNAVAILABLE:[/yellow] {escape(result['detail'])}")
        raise SystemExit(5)
    if status == "ERROR":
        console.print(f"[red]error:[/red] {escape(result['detail'])}")
        raise SystemExit(1)
    console.print(f"[dim]source sha256: {result['source_sha256']}[/dim]")
    bounded = sanitize_for_terminal(result["text"], max_length=20_000)
    console.print(escape(bounded).rstrip() or "(no text recognized)")
    console.print(f"[dim]{result['caveat']}[/dim]")


def ocr_pdf_first_page_placeholder(path: Path) -> dict[str, Any]:
    """PDF OCR is not implemented in P0; report honestly rather than fake it."""
    return {
        "status": "UNAVAILABLE",
        "detail": (
            "PDF OCR is not implemented in this release; extract page images "
            "with a local tool and OCR those, or wait for a later phase"
        ),
        "path": str(path),
    }
