"""Application configuration: paths, privacy defaults, network policy.

Local-first: every external network path is disabled or opt-in by
default. No telemetry exists in this release.
"""

from __future__ import annotations

import contextlib
import os
from dataclasses import dataclass, field
from pathlib import Path

APP_DIR_NAME = ".tracefield"


def default_data_root() -> Path:
    """Case data root: $TRACEFIELD_HOME, else XDG data dir, else ~/.local/share."""
    env = os.environ.get("TRACEFIELD_HOME")
    if env:
        return Path(env).expanduser()
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / "tracefield"
    return Path.home() / ".local" / "share" / "tracefield"


def default_config_path() -> Path:
    env = os.environ.get("TRACEFIELD_CONFIG")
    if env:
        return Path(env).expanduser()
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "tracefield" / "config.toml"
    return Path.home() / ".config" / "tracefield" / "config.toml"


@dataclass
class Settings:
    """Runtime settings. Defaults are privacy-preserving."""

    data_root: Path = field(default_factory=default_data_root)
    config_path: Path = field(default_factory=default_config_path)
    allow_network: bool = False  # network fetches are opt-in
    username_check_enabled: bool = False  # public-profile checks are opt-in
    # Typed adapter boundary (decision D19). Local-only by default; the
    # kill switch exists so a misbehaving backend can be disabled without
    # uninstalling anything.
    adapters_enabled: bool = True
    max_fetch_bytes: int = 10 * 1024 * 1024
    max_fetch_timeout_s: float = 15.0
    max_redirects: int = 5
    redact_exports: bool = True
    # Dissemination identity for reports (OOVS-09). Sourced from the
    # TRACEFIELD_REPORT_AUTHOR environment variable; when unset the report
    # states "author not set" rather than inventing one — an unattributed
    # report is honest about being unattributed.
    report_author: str = ""

    @property
    def db_path(self) -> Path:
        return self.data_root / "tracefield.sqlite3"

    @property
    def cases_root(self) -> Path:
        return self.data_root / "cases"

    def ensure_dirs(self) -> None:
        self.data_root.mkdir(parents=True, exist_ok=True)
        self.cases_root.mkdir(parents=True, exist_ok=True)
        # Privacy at rest: case data must not be group/world accessible.
        for d in (self.data_root, self.cases_root):
            with contextlib.suppress(OSError):
                d.chmod(0o700)


def load_settings() -> Settings:
    """Load settings. Config file support is intentionally minimal (TOML-free
    key=value via environment only in P0) to avoid a dependency; file-based
    overrides land with the config module's next iteration."""
    s = Settings()
    allow = os.environ.get("TRACEFIELD_ALLOW_NETWORK", "")
    s.allow_network = allow.strip().lower() in {"1", "true", "yes"}
    uname = os.environ.get("TRACEFIELD_USERNAME_CHECK", "")
    s.username_check_enabled = uname.strip().lower() in {"1", "true", "yes"}
    adapters = os.environ.get("TRACEFIELD_ADAPTERS", "")
    # Default ON (local-only backends); any explicit falsy value disables.
    s.adapters_enabled = adapters.strip().lower() not in {"0", "false", "no", "off"}
    s.report_author = os.environ.get("TRACEFIELD_REPORT_AUTHOR", "").strip()
    return s
