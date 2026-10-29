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
    # Dissemination identity for reports (OOVS-09). Per-OPERATOR identity:
    # read from the operator's config file (report_author key) or the
    # TRACEFIELD_REPORT_AUTHOR environment variable, which wins. There is
    # deliberately NO tool-level default — a report authored by an operator
    # is theirs, and an unidentified operator's report states "author not
    # set" rather than claiming someone else's identity.
    report_author: str = ""
    # Non-empty when the operator's config file could not be parsed or held
    # an invalid value; file values are then ignored and the error is shown
    # by `doctor` (fail-closed on config, honest about the refusal).
    config_error: str = ""
    # Keys accepted from the operator's config file in this iteration.
    # Everything else in the file is reported as an unknown-key error rather
    # than silently ignored — a misspelled setting must never look applied.
    _CONFIG_KEYS = frozenset({"report_author"})

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


def _apply_config_file(s: Settings) -> None:
    """Read the operator's config file into ``s`` (env vars keep precedence).

    Accepted keys are the documented allowlist above; the file must be valid
    TOML. Any violation records ``config_error`` and leaves defaults in
    place — a broken config must never be partially applied or silently
    swallowed.
    """
    try:
        import tomllib
    except ModuleNotFoundError:  # pragma: no cover - 3.11+ ships tomllib
        s.config_error = "config module unavailable (python >= 3.11 required)"
        return
    if not s.config_path.exists():
        return
    try:
        with s.config_path.open("rb") as fh:
            data = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        s.config_error = f"config file ignored (not valid TOML): {type(exc).__name__}"
        return
    if not isinstance(data, dict):  # pragma: no cover - tomllib yields dict
        s.config_error = "config file ignored (not a TOML table)"
        return
    unknown = sorted(set(data) - s._CONFIG_KEYS)
    if unknown:
        s.config_error = "config file ignored (unknown key(s): " + ", ".join(unknown) + ")"
        return
    author = data.get("report_author")
    if author is None:
        return
    if not isinstance(author, str):
        s.config_error = "config file ignored (report_author must be a string)"
        return
    s.report_author = author.strip()


def load_settings() -> Settings:
    """Load settings; precedence per key: env var > config file > default.

    Config file support is minimal on purpose (accepted-keys allowlist,
    fail-closed on parse errors) so a typo can never silently change
    behaviour. Network, username-check, and adapter switches remain
    ENV-ONLY by policy (D20-type switches live at the opt-in boundary).
    """
    s = Settings()
    _apply_config_file(s)
    allow = os.environ.get("TRACEFIELD_ALLOW_NETWORK", "")
    s.allow_network = allow.strip().lower() in {"1", "true", "yes"}
    uname = os.environ.get("TRACEFIELD_USERNAME_CHECK", "")
    s.username_check_enabled = uname.strip().lower() in {"1", "true", "yes"}
    adapters = os.environ.get("TRACEFIELD_ADAPTERS", "")
    # Default ON (local-only backends); any explicit falsy value disables.
    s.adapters_enabled = adapters.strip().lower() not in {"0", "false", "no", "off"}
    env_author = os.environ.get("TRACEFIELD_REPORT_AUTHOR", "").strip()
    if env_author:
        s.report_author = env_author
    return s
