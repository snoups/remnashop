import os
import time
from pathlib import Path
from typing import Final, Optional

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

from app.cli import pre_migration_dump
from app.core.config import AppConfig
from app.core.constants import ALEMBIC_INI

_HEAD: Final[Optional[str]] = ScriptDirectory.from_config(
    Config(str(ALEMBIC_INI))
).get_current_head()


def _patch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, current: Optional[str]) -> list[Path]:
    dumped: list[Path] = []
    config = AppConfig.get().model_copy(update={"media_dir": tmp_path})

    async def fake_current(config: AppConfig) -> Optional[str]:
        return current

    async def fake_dump(config: AppConfig, dest: Path) -> None:
        dumped.append(dest)

    monkeypatch.setattr(pre_migration_dump, "_current_revision", fake_current)
    monkeypatch.setattr(pre_migration_dump, "create_signed_database_dump", fake_dump)
    monkeypatch.setattr(pre_migration_dump.AppConfig, "get", staticmethod(lambda: config))
    return dumped


@pytest.mark.parametrize("current", [None, _HEAD])
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
    assert dumped[0].parent == tmp_path / "backups"
    assert dumped[0].name.startswith("DATABASE_pre-migration_older_")


async def test_reads_the_migrated_test_database(config: AppConfig) -> None:
    assert await pre_migration_dump._current_revision(config) == _HEAD


async def test_a_restart_loop_keeps_the_recent_dump(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    dumped = _patch(monkeypatch, tmp_path, "older")
    (tmp_path / "backups").mkdir()
    (tmp_path / "backups" / "DATABASE_pre-migration_older_20261106-120000.dump").touch()

    await pre_migration_dump.main()

    assert dumped == []


async def test_an_old_dump_of_the_same_revision_is_not_reused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    dumped = _patch(monkeypatch, tmp_path, "older")
    (tmp_path / "backups").mkdir()
    stale = tmp_path / "backups" / "DATABASE_pre-migration_older_20261001-120000.dump"
    stale.touch()
    week_ago = time.time() - 7 * 24 * 3600
    os.utime(stale, (week_ago, week_ago))

    await pre_migration_dump.main()

    assert len(dumped) == 1
