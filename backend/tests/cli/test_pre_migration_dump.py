from pathlib import Path
from typing import Optional

import pytest

from app.cli import pre_migration_dump
from app.core.config import AppConfig


def _patch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, current: Optional[str]) -> list[Path]:
    dumped: list[Path] = []

    async def fake_current(config: AppConfig) -> Optional[str]:
        return current

    async def fake_dump(config: AppConfig, dest: Path) -> None:
        dumped.append(dest)

    monkeypatch.setattr(pre_migration_dump, "_current_revision", fake_current)
    monkeypatch.setattr(pre_migration_dump, "create_signed_database_dump", fake_dump)
    monkeypatch.setattr(pre_migration_dump, "BACKUP_DIR", tmp_path)
    return dumped


@pytest.mark.parametrize("current", [None, "current"])
async def test_skips_fresh_or_up_to_date_database(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, current: Optional[str]
) -> None:
    dumped = _patch(monkeypatch, tmp_path, current)

    await pre_migration_dump.main()

    assert dumped == []


async def test_dumps_before_pending_migrations(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    dumped = _patch(monkeypatch, tmp_path, "older")

    await pre_migration_dump.main()

    assert len(dumped) == 1
    assert dumped[0].parent == tmp_path
    assert dumped[0].name.startswith("DATABASE_pre-migration_older_")


async def test_reads_the_migrated_test_database(config: AppConfig) -> None:
    assert await pre_migration_dump._current_revision(config) == "current"
