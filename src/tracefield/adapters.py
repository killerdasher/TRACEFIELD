"""Typed adapter boundary — the only sanctioned way to run an external
backend against case data and turn its raw return into an Observation.

Design contract (decision D19):

- **Typed**: every backend reachable from TRACEFIELD is declared as an
  ``AdapterSpec`` — a frozen dataclass with a literal backend name, a
  version-probe argv, a run-argv builder, and its licence/upstream link.
  A spec whose backend is not in ``ALLOWED_BACKENDS`` cannot be
  registered (fail closed at construction, re-checked at call time).
- **Honest lifecycle**: ``integration_state`` distinguishes ``integrated``
  (the adapter path is exercised end-to-end by our own tests) from
  ``spec-only`` (the typed boundary exists but is not verified here).
  Health is a factual, recorded check — ``ready`` means the backend
  binary answered a version probe *right now*; nothing more is implied.
- **Proposal-free, local-only**: running an adapter is an explicit user
  command. Every shipped spec is local-only; a future network spec must
  set ``needs_network=True`` and then requires ``allow_network`` plus an
  explicit per-call opt-in — mirroring the fetch policy.
- **Raw first**: the adapter stores the tool's raw return verbatim
  (bounded by ``run_backend``'s output cap) and records an Observation
  that *references* it. Interpretation stays a reviewable claim layer —
  adapters never assert conclusions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tracefield.core.domain import utcnow
from tracefield.fieldtools.inspect import ALLOWED_BACKENDS, run_backend

# Health vocabulary — factual states only. "healthy" is deliberately NOT a
# member: health would require a recorded, dated check we do not persist.
HEALTH_READY = "ready"  # version probe answered right now
HEALTH_MISSING_BACKEND = "missing-backend"  # binary not on PATH
HEALTH_DISABLED = "disabled"  # TRACEFIELD_ADAPTERS kill switch engaged
HEALTH_BLOCKED = "blocked"  # network adapter without opt-in

# Integration vocabulary — what WE have verified, not what upstream claims.
INTEGRATED = "integrated"  # adapter path E2E-tested by our suite
SPEC_ONLY = "spec-only"  # typed spec exists; not exercised end-to-end


class AdapterError(RuntimeError):
    """A refused or failed adapter operation, with an honest reason.

    ``state`` carries the health vocabulary member when applicable so
    callers can map to exit codes without string-matching messages.
    """

    def __init__(self, message: str, *, state: str = "") -> None:
        super().__init__(message)
        self.state = state


@dataclass(frozen=True)
class AdapterSpec:
    """Typed declaration of one external backend integration."""

    id: str
    display_name: str
    backend: str  # literal executable name; must be in ALLOWED_BACKENDS
    version_argv: tuple[str, ...]  # probe argv, e.g. ("exiftool", "-ver")
    run_argv: tuple[str, ...]  # argv prefix; the input path is appended after "--"
    description: str
    catalogue_id: str = ""  # registry record this adapter corresponds to
    license_id: str = "UNKNOWN"
    upstream_url: str = ""
    needs_network: bool = False
    integration_state: str = SPEC_ONLY

    def __post_init__(self) -> None:
        # Fail closed at construction: a spec naming a non-allowlisted
        # backend never enters the registry, even if nobody runs it.
        if self.backend not in ALLOWED_BACKENDS:
            raise AdapterError(
                f"adapter spec {self.id!r} names non-allowlisted backend "
                f"{self.backend!r}; registry accepts {sorted(ALLOWED_BACKENDS)}"
            )
        if self.backend not in self.version_argv or self.backend not in self.run_argv:
            raise AdapterError(
                f"adapter spec {self.id!r}: version/run argv must start from "
                "the spec's own backend literal"
            )
        if "{path}" not in self.run_argv:
            raise AdapterError(
                f"adapter spec {self.id!r}: run_argv must contain a {{path}} "
                "placeholder for the input file"
            )
        if self.integration_state not in {INTEGRATED, SPEC_ONLY}:
            raise AdapterError(
                f"adapter spec {self.id!r}: unknown integration_state {self.integration_state!r}"
            )

    def run_argv_for(self, input_path: Path, extra_args: tuple[str, ...] = ()) -> list[str]:
        """Full argv for a run: the spec's template with ``{path}``
        replaced by the absolute input path.

        Absolute paths can never start with a dash, so no backend can
        misread the input as an option; specs that also support ``--``
        keep it in their template for defense in depth. ``extra_args``
        are inserted before the path placeholder.
        """
        path_arg = str(input_path if input_path.is_absolute() else input_path.resolve())
        # Extra args are OPTIONS: they must precede any ``--`` end-of-
        # options separator, because backends read everything after ``--``
        # as filenames. If the template has no separator, insert them
        # immediately before the path placeholder.
        parts = list(self.run_argv)
        sep_index = parts.index("--") if "--" in parts else None
        path_index = parts.index("{path}")
        insert_at = sep_index if sep_index is not None else path_index
        out = parts[:insert_at] + list(extra_args) + parts[insert_at:]
        return [path_arg if part == "{path}" else part for part in out]


@dataclass(frozen=True)
class AdapterResult:
    """Raw adapter return — uninterpreted, with its provenance."""

    spec: AdapterSpec
    exit_code: int
    stdout: str
    stderr: str
    backend_version: str
    ran_at: str = field(default_factory=utcnow)

    @property
    def ok(self) -> bool:
        return self.exit_code == 0

    def provenance(self) -> dict[str, Any]:
        """Machine-readable provenance block for the Observation record."""
        return {
            "adapter_id": self.spec.id,
            "backend": self.spec.backend,
            "backend_version": self.backend_version,
            "exit_code": self.exit_code,
            "ran_at": self.ran_at,
            "network": "none (local process)",
        }


# ---------------------------------------------------------------------------
# Registry — declared, never discovered. Adding a spec here is a code
# change under review, not a runtime scan.
# ---------------------------------------------------------------------------

EXIFTOOL_META = AdapterSpec(
    id="exiftool-meta",
    display_name="ExifTool metadata reader",
    backend="exiftool",
    version_argv=("exiftool", "-ver"),
    run_argv=("exiftool", "-json", "-n", "--", "{path}"),
    description=(
        "Structured file metadata as JSON via a locally installed ExifTool. "
        "Local-only; the raw tool return is stored verbatim."
    ),
    catalogue_id="tool_001b8f8a85",
    license_id="GPL-3.0",
    upstream_url="https://exiftool.org/",
    integration_state=INTEGRATED,
)

FFPROBE_STREAMS = AdapterSpec(
    id="ffprobe-streams",
    display_name="FFprobe container/stream inspector",
    backend="ffprobe",
    version_argv=("ffprobe", "-version"),
    run_argv=(
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        "{path}",
    ),
    description=(
        "Container and stream metadata as JSON via a locally installed FFprobe. "
        "Typed spec only: not exercised end-to-end by our test suite."
    ),
    license_id="LGPL-2.1-or-later",
    upstream_url="https://ffmpeg.org/ffprobe.html",
    integration_state=SPEC_ONLY,
)

TESSERACT_OCR = AdapterSpec(
    id="tesseract-ocr",
    display_name="Tesseract OCR extractor",
    backend="tesseract",
    version_argv=("tesseract", "--version"),
    run_argv=("tesseract", "{path}", "stdout"),
    description=(
        "Plain-text OCR of images via a locally installed Tesseract. "
        "Typed spec only: not exercised end-to-end by our test suite."
    ),
    license_id="Apache-2.0",
    upstream_url="https://github.com/tesseract-ocr/tesseract",
    integration_state=SPEC_ONLY,
)

ADAPTERS: dict[str, AdapterSpec] = {
    spec.id: spec for spec in (EXIFTOOL_META, FFPROBE_STREAMS, TESSERACT_OCR)
}


def get_adapter(adapter_id: str) -> AdapterSpec:
    """Look up a registered adapter or raise an honest AdapterError."""
    spec = ADAPTERS.get(adapter_id)
    if spec is None:
        raise AdapterError(f"unknown adapter: {adapter_id!r} (registered: {sorted(ADAPTERS)})")
    return spec


def backend_version(spec: AdapterSpec) -> str:
    """Probe the backend's version. Raises AdapterError when absent."""
    import shutil

    if shutil.which(spec.backend) is None:
        raise AdapterError(
            f"backend {spec.backend!r} is not installed (or not on PATH)",
            state=HEALTH_MISSING_BACKEND,
        )
    try:
        rc, out, _err = run_backend(list(spec.version_argv), timeout_s=10)
    except (ValueError, FileNotFoundError) as exc:
        # ValueError: not allowlisted (can't happen post-registration, but
        # the boundary re-checks). FileNotFoundError: raced off PATH.
        raise AdapterError(str(exc), state=HEALTH_MISSING_BACKEND) from exc
    if rc != 0:
        raise AdapterError(
            f"version probe for {spec.backend!r} exited {rc}",
            state=HEALTH_MISSING_BACKEND,
        )
    # First line only; versions are single-line in every supported backend.
    return out.strip().splitlines()[0].strip() if out.strip() else "unknown"


def health(spec: AdapterSpec, *, allow_network: bool = False) -> dict[str, Any]:
    """Factual health state of one adapter. Records what was checked.

    A version probe is the entire check: ``ready`` means the binary
    answered *now*. No claim is made about correctness of the backend's
    output, its upstream's maintenance, or fitness for any purpose.
    """
    from tracefield.config import load_settings

    settings = load_settings()
    version = ""
    if not settings.adapters_enabled:
        state = HEALTH_DISABLED
        detail = "adapters disabled via TRACEFIELD_ADAPTERS"
    elif spec.needs_network and not (allow_network and settings.allow_network):
        state = HEALTH_BLOCKED
        detail = "network adapter requires TRACEFIELD_ALLOW_NETWORK=1 and explicit opt-in"
    else:
        try:
            version = backend_version(spec)
        except AdapterError as exc:
            return {
                "adapter_id": spec.id,
                "state": exc.state or HEALTH_MISSING_BACKEND,
                "backend_version": "",
                "checked_at": utcnow(),
                "note": str(exc),
            }
        state = HEALTH_READY
        detail = "version probe answered"
    return {
        "adapter_id": spec.id,
        "state": state,
        "backend_version": version if state == HEALTH_READY else "",
        "checked_at": utcnow(),
        "note": detail,
    }


def describe(spec: AdapterSpec) -> dict[str, Any]:
    """Full typed descriptor of one adapter (no probing, no side effects)."""
    return {
        "id": spec.id,
        "display_name": spec.display_name,
        "backend": spec.backend,
        "description": spec.description,
        "catalogue_id": spec.catalogue_id,
        "license_id": spec.license_id,
        "upstream_url": spec.upstream_url,
        "needs_network": spec.needs_network,
        "integration_state": spec.integration_state,
    }


def run_adapter(
    spec: AdapterSpec,
    input_path: Path,
    *,
    allow_network: bool = False,
    extra_args: tuple[str, ...] = (),
) -> AdapterResult:
    """Run one adapter against one local file. Explicit call, no defaults.

    Refuses: unknown/disabled adapters, missing backends, network specs
    without opt-in, non-allowlisted backends (re-checked at call time),
    and non-existent input files. Never interprets the output.
    """
    from tracefield.config import load_settings

    settings = load_settings()
    # Call-time re-check of the invariant, independent of construction.
    if spec.backend not in ALLOWED_BACKENDS:
        raise AdapterError(
            f"backend {spec.backend!r} is not allowlisted — refusing to run",
            state=HEALTH_DISABLED,
        )
    if not settings.adapters_enabled:
        raise AdapterError("adapters are disabled (TRACEFIELD_ADAPTERS)", state=HEALTH_DISABLED)
    if spec.needs_network and not (allow_network and settings.allow_network):
        raise AdapterError(
            "network adapter requires TRACEFIELD_ALLOW_NETWORK=1 and explicit opt-in",
            state=HEALTH_BLOCKED,
        )
    if not input_path.is_file():
        raise AdapterError(f"not a regular file: {input_path}")

    version = backend_version(spec)
    argv = spec.run_argv_for(input_path, extra_args)
    rc, out, err = run_backend(argv, timeout_s=60)
    return AdapterResult(
        spec=spec,
        exit_code=rc,
        stdout=out,
        stderr=err,
        backend_version=version,
    )


__all__ = [
    "ADAPTERS",
    "EXIFTOOL_META",
    "FFPROBE_STREAMS",
    "TESSERACT_OCR",
    "AdapterError",
    "AdapterResult",
    "AdapterSpec",
    "describe",
    "get_adapter",
    "health",
    "run_adapter",
]
