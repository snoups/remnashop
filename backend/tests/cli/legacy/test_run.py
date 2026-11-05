import os
from pathlib import Path
from typing import Awaitable, Callable, Optional

import pytest
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.cli.legacy import run as run_module
from app.cli.legacy.errors import LegacyMigrationError
from app.cli.legacy.migrate import (
    MigrationResult,
    migrate,
    upgrade_legacy_schema,
)
from app.cli.legacy.panel import PanelIndex
from app.cli.legacy.report import MigrationReport
from app.cli.legacy.run import (
    deliver_report,
    read_bot_owner_id,
    render_report,
    rollback_advice,
    run_migration,
    run_rollback,
)
from app.cli.legacy.schema import LEGACY_HEAD, current_revision
from app.core.config import AppConfig

LegacyAt = Callable[[AsyncEngine, str], Awaitable[None]]


def _result(owner: bool = True) -> MigrationResult:
    return MigrationResult(report=MigrationReport(), owner_migrated=owner, original_revision="0039")


def test_render_report_asks_to_register_the_owner(tmp_path: Path) -> None:
    backup = tmp_path / "b.dump"
    migrated = render_report(_result(), backup)
    assert "register the owner account" in migrated
    assert "data is kept" in migrated
    assert "password (" not in migrated.lower()
    assert "Owner login" not in migrated
    assert "No owner was migrated" in render_report(_result(owner=False), backup)


def test_deliver_report_prints_and_writes_the_same_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    backup = tmp_path / "b.dump"
    deliver_report(_result(), backup)
    assert (tmp_path / "b.report.txt").read_text() in capsys.readouterr().out


def test_deliver_report_prints_even_if_the_file_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    deliver_report(_result(), tmp_path / "missing" / "b.dump")
    out = capsys.readouterr().out
    assert "register the owner account" in out
    assert "Warning: writing the report" in out


def test_rollback_advice_by_original_revision(tmp_path: Path) -> None:
    assert "start the old image" in rollback_advice(LEGACY_HEAD, tmp_path)
    assert "Restore backup" not in rollback_advice(LEGACY_HEAD, tmp_path)
    assert "not recorded" in rollback_advice(None, tmp_path)

    oldest = tmp_path / "DATABASE_pre-legacy-migration_0039_2026.dump"
    oldest.touch()
    newer = tmp_path / "DATABASE_pre-legacy-migration_0039_2027.dump"
    newer.touch()
    os.utime(newer, (oldest.stat().st_mtime + 10,) * 2)
    advice = rollback_advice("0039", tmp_path)
    assert "Restore backup" in advice
    assert oldest.name in advice


def _pointed(config: AppConfig, engine: AsyncEngine) -> AppConfig:
    return config.model_copy(
        update={"database": config.database.model_copy(update={"name": engine.url.database})}
    )


async def test_rollback_after_rerun_names_the_original_backup(
    legacy_engine: AsyncEngine,
    config: AppConfig,
    legacy_at: LegacyAt,
    redis: Redis,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    await legacy_at(legacy_engine, "0039")
    first = tmp_path / "DATABASE_pre-legacy-migration_0039_2026.dump"
    first.touch()
    # first run: upgraded, then migrate failed and rolled back its own transaction
    assert await upgrade_legacy_schema(legacy_engine) == "0039"
    rerun = tmp_path / f"DATABASE_pre-legacy-migration_{LEGACY_HEAD}_2027.dump"
    rerun.touch()
    os.utime(rerun, (first.stat().st_mtime + 10,) * 2)
    original = await upgrade_legacy_schema(legacy_engine)
    assert original == "0039"
    await migrate(
        legacy_engine,
        panel_index=PanelIndex(),
        crypt_key=config.crypt_key.get_secret_value(),
        bot_owner_id=None,
        original_revision=original,
    )
    await redis.xadd("taskiq", {"data": "x"})
    monkeypatch.setattr(run_module, "BACKUP_DIR", tmp_path)

    await run_rollback(_pointed(config, legacy_engine))

    out = capsys.readouterr().out
    assert "Restore backup" in out
    assert first.name in out
    assert await redis.exists("taskiq") == 0
    async with legacy_engine.connect() as connection:
        assert await current_revision(connection) == LEGACY_HEAD


def _stub_run(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, dumps: list[Path], **stubs: object
) -> None:
    async def noop(*args: object, **kwargs: object) -> None:
        return None

    async def dump(config: AppConfig, path: Path) -> None:
        dumps.append(path)

    async def no_panel(sdk: object) -> PanelIndex:
        return PanelIndex()

    monkeypatch.setattr(run_module, "BACKUP_DIR", tmp_path)
    monkeypatch.setattr(run_module, "preflight", noop)
    monkeypatch.setattr(run_module, "create_signed_database_dump", dump)
    monkeypatch.setattr(run_module, "fetch_panel_index", no_panel)
    for name, stub in stubs.items():
        monkeypatch.setattr(run_module, name, stub)


async def test_failed_preflight_leaves_no_dump(
    legacy_engine: AsyncEngine,
    config: AppConfig,
    legacy_at: LegacyAt,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await legacy_at(legacy_engine, "0039")

    async def failing(*args: object, **kwargs: object) -> None:
        raise LegacyMigrationError("panel is not 3.x")

    dumps: list[Path] = []
    _stub_run(monkeypatch, tmp_path, dumps, preflight=failing)
    with pytest.raises(LegacyMigrationError, match="3.x"):
        await run_migration(_pointed(config, legacy_engine))
    assert dumps == []


async def test_failed_panel_index_does_not_move_the_database(
    legacy_engine: AsyncEngine,
    config: AppConfig,
    legacy_at: LegacyAt,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await legacy_at(legacy_engine, "0039")

    async def failing(sdk: object) -> PanelIndex:
        raise LegacyMigrationError("panel unreachable")

    dumps: list[Path] = []
    _stub_run(monkeypatch, tmp_path, dumps, fetch_panel_index=failing)
    with pytest.raises(LegacyMigrationError, match="unreachable"):
        await run_migration(_pointed(config, legacy_engine))
    async with legacy_engine.connect() as connection:
        assert await current_revision(connection) == "0039"


async def test_failed_migrate_names_the_original_revision_and_backup(
    legacy_engine: AsyncEngine,
    config: AppConfig,
    legacy_at: LegacyAt,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await legacy_at(legacy_engine, "0039")

    async def failing(*args: object, **kwargs: object) -> None:
        raise SQLAlchemyError("boom")

    dumps: list[Path] = []
    _stub_run(monkeypatch, tmp_path, dumps, migrate=failing)
    with pytest.raises(LegacyMigrationError) as error:
        await run_migration(_pointed(config, legacy_engine))
    message = str(error.value)
    assert "revision 0039" in message
    assert "Restore backup" in message
    assert str(dumps[0]) in message


async def test_failed_rerun_names_the_original_revision_backup(
    legacy_engine: AsyncEngine,
    config: AppConfig,
    legacy_at: LegacyAt,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await legacy_at(legacy_engine, "0039")
    original = tmp_path / "DATABASE_pre-legacy-migration_0039_2026.dump"
    original.touch()
    assert await upgrade_legacy_schema(legacy_engine) == "0039"

    async def failing(*args: object, **kwargs: object) -> None:
        raise SQLAlchemyError("boom")

    dumps: list[Path] = []
    _stub_run(monkeypatch, tmp_path, dumps, migrate=failing)
    with pytest.raises(LegacyMigrationError) as error:
        await run_migration(_pointed(config, legacy_engine))
    message = str(error.value)
    assert str(original) in message
    assert str(dumps[0]) not in message


async def test_unexpected_transform_error_gets_the_failure_message(
    legacy_engine: AsyncEngine,
    config: AppConfig,
    legacy_at: LegacyAt,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await legacy_at(legacy_engine, "0039")

    async def failing(*args: object, **kwargs: object) -> None:
        raise ValueError("'XXX' is not a valid Currency")

    dumps: list[Path] = []
    _stub_run(monkeypatch, tmp_path, dumps, migrate=failing)
    with pytest.raises(LegacyMigrationError) as error:
        await run_migration(_pointed(config, legacy_engine))
    message = str(error.value)
    assert "not a valid Currency" in message
    assert "revision 0039" in message
    assert str(dumps[0]) in message


@pytest.mark.parametrize(
    ("raw", "expected"), [("123", 123), ("abc", None), ("", None), (None, None)]
)
def test_read_bot_owner_id(
    monkeypatch: pytest.MonkeyPatch, raw: Optional[str], expected: Optional[int]
) -> None:
    if raw is None:
        monkeypatch.delenv("BOT_OWNER_ID", raising=False)
    else:
        monkeypatch.setenv("BOT_OWNER_ID", raw)
    assert read_bot_owner_id() == expected


async def test_run_migration_refuses_current_database(
    legacy_engine: AsyncEngine,
    config: AppConfig,
    legacy_at: LegacyAt,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await legacy_at(legacy_engine, LEGACY_HEAD)
    await migrate(
        legacy_engine,
        panel_index=PanelIndex(),
        crypt_key=config.crypt_key.get_secret_value(),
        bot_owner_id=None,
        original_revision=LEGACY_HEAD,
    )
    pointed = config.model_copy(
        update={"database": config.database.model_copy(update={"name": legacy_engine.url.database})}
    )
    monkeypatch.setattr(run_module, "BACKUP_DIR", Path("/nonexistent-no-backup"))

    with pytest.raises(LegacyMigrationError, match="Nothing to migrate"):
        await run_migration(pointed)

    async with legacy_engine.connect() as connection:
        assert await current_revision(connection) == "current"
        assert await connection.scalar(text("SELECT count(*) FROM legacy.users")) == 0
