"""Shared pytest fixtures: isolated temp data root, fresh database."""

from __future__ import annotations

from pathlib import Path

import pytest

from tracefield.config import Settings
from tracefield.storage import Database


@pytest.fixture()
def tf_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate TRACEFIELD_HOME so tests never touch the real user data dir."""
    home = tmp_path / "tf-home"
    monkeypatch.setenv("TRACEFIELD_HOME", str(home))
    monkeypatch.delenv("TRACEFIELD_ALLOW_NETWORK", raising=False)
    monkeypatch.delenv("TRACEFIELD_USERNAME_CHECK", raising=False)
    return home


@pytest.fixture()
def settings(tf_home: Path) -> Settings:
    s = Settings(data_root=tf_home)
    s.ensure_dirs()
    return s


@pytest.fixture()
def db(settings: Settings) -> Database:
    database = Database(settings.db_path)
    yield database
    database.close()


@pytest.fixture()
def case_factory(db: Database):
    """Create a case quickly."""
    from tracefield.core.domain import Case
    from tracefield.storage.repositories import CaseRepo

    repo = CaseRepo(db)

    def _make(title: str = "test-case") -> Case:
        case = Case(title=title, purpose="test", scope="fixtures only")
        repo.create(case)
        return case

    return _make
