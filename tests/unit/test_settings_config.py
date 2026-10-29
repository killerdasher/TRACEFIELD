"""Unit tests: operator config file loading (report author identity, FS-17).

Contract under test (settings.py):
- accepted-keys allowlist; validity required; fail-closed on any violation
- env var precedence over the config file
- absent file = defaults, no error; error text is recorded, not thrown
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

AUTHOR = "killerdasher — github.com/killerdasher/TRACEFIELD"


@pytest.fixture()
def iso_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point TRACEFIELD_CONFIG at a per-test path DEFINED but absent,
    delegating the isolation guarantees of tf_home without needing the
    integration fixtures."""
    cfg = tmp_path / "config.toml"
    monkeypatch.setenv("TRACEFIELD_CONFIG", str(cfg))
    monkeypatch.delenv("TRACEFIELD_REPORT_AUTHOR", raising=False)
    return cfg


def _load():
    from tracefield.config import load_settings

    return load_settings()


def _write(cfg: Path, text: str) -> None:
    cfg.write_text(text, encoding="utf-8")


class TestConfigFileLoading:
    def test_absent_file_is_defaults(self, iso_config: Path) -> None:
        s = _load()
        assert s.report_author == ""
        assert s.config_error == ""

    def test_report_author_from_file(self, iso_config: Path) -> None:
        _write(iso_config, f'report_author = "{AUTHOR}"\n')
        s = _load()
        assert s.report_author == AUTHOR
        assert s.config_error == ""

    def test_env_wins_over_file(self, iso_config: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _write(iso_config, f'report_author = "{AUTHOR}"\n')
        monkeypatch.setenv("TRACEFIELD_REPORT_AUTHOR", "operator via env")
        s = _load()
        assert s.report_author == "operator via env"

    def test_invalid_toml_fails_closed(self, iso_config: Path) -> None:
        _write(iso_config, "report_author = [not valid\n")
        s = _load()
        assert s.report_author == ""  # defaults, nothing partially applied
        assert "not valid TOML" in s.config_error

    def test_unknown_key_is_refused(self, iso_config: Path) -> None:
        _write(iso_config, f'report_author = "{AUTHOR}"\nallow_network = true\n')
        s = _load()
        # BOTH the typo'd key and the good value are refused: a misspelled
        # setting must never look applied while others take effect.
        assert s.report_author == ""
        assert s.allow_network is False
        assert "unknown key" in s.config_error and "allow_network" in s.config_error

    def test_non_string_author_is_refused(self, iso_config: Path) -> None:
        _write(iso_config, "report_author = 123\n")
        s = _load()
        assert s.report_author == ""
        assert "must be a string" in s.config_error

    def test_blank_author_in_file_counts_as_unset(self, iso_config: Path) -> None:
        _write(iso_config, 'report_author = "   "\n')
        s = _load()
        assert s.report_author == ""  # stripped to empty: honest fallback
        assert s.config_error == ""  # valid config, no error
