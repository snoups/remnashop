import asyncio
import logging
import sys
from pathlib import Path
from typing import Awaitable, Callable, Optional

import pytest
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncEngine

from app.cli import legacy_guard
from app.cli.legacy import run as run_module
from app.cli.legacy.errors import LegacyMigrationError
from app.cli.legacy.panel import PanelIndex
from app.cli.legacy_guard import main
from app.core import logger as logger_module
from app.core.config import AppConfig

LegacyAt = Callable[[AsyncEngine, str], Awaitable[None]]


def _point_at(monkeypatch: pytest.MonkeyPatch, config: AppConfig, engine: AsyncEngine) -> None:
    pointed = config.model_copy(
        update={"database": config.database.model_copy(update={"name": engine.url.database})}
    )
    monkeypatch.setattr(AppConfig, "get", classmethod(lambda cls: pointed))


def _record_runs(monkeypatch: pytest.MonkeyPatch, error: Optional[Exception] = None) -> list[str]:
    runs: list[str] = []

    async def run(config: AppConfig) -> None:
        runs.append(config.database.name)
        if error is not None:
            raise error

    monkeypatch.setattr(legacy_guard, "run_auto_migration", run)
    return runs


async def test_guard_main_passes_on_empty_database(
    legacy_engine: AsyncEngine,
    config: AppConfig,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _point_at(monkeypatch, config, legacy_engine)
    runs = _record_runs(monkeypatch)
    await asyncio.to_thread(main)
    assert runs == []
    assert capsys.readouterr().err == ""


async def test_guard_main_migrates_a_legacy_database(
    legacy_engine: AsyncEngine,
    config: AppConfig,
    legacy_at: LegacyAt,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await legacy_at(legacy_engine, "0039")
    _point_at(monkeypatch, config, legacy_engine)
    runs = _record_runs(monkeypatch)
    await asyncio.to_thread(main)
    assert runs == [legacy_engine.url.database]


async def test_guard_main_exits_when_the_migration_fails(
    legacy_engine: AsyncEngine,
    config: AppConfig,
    legacy_at: LegacyAt,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    await legacy_at(legacy_engine, "0039")
    _point_at(monkeypatch, config, legacy_engine)
    _record_runs(monkeypatch, LegacyMigrationError("panel is not 3.x"))
    with pytest.raises(SystemExit) as exit_info:
        await asyncio.to_thread(main)
    assert exit_info.value.code == 1
    assert "panel is not 3.x" in capsys.readouterr().err


async def test_guard_main_refuses_a_newer_legacy_revision(
    legacy_engine: AsyncEngine,
    config: AppConfig,
    legacy_at: LegacyAt,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    await legacy_at(legacy_engine, "0046")
    async with legacy_engine.begin() as connection:
        await connection.exec_driver_sql("UPDATE alembic_version SET version_num = '0047'")
    _point_at(monkeypatch, config, legacy_engine)
    runs = _record_runs(monkeypatch)
    with pytest.raises(SystemExit) as exit_info:
        await asyncio.to_thread(main)
    assert exit_info.value.code == 1
    assert runs == []
    assert "newer release than this image" in capsys.readouterr().err


async def test_guard_main_keeps_frame_locals_out_of_the_log(
    legacy_engine: AsyncEngine,
    config: AppConfig,
    legacy_at: LegacyAt,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    await legacy_at(legacy_engine, "0039")
    _point_at(monkeypatch, config, legacy_engine)
    monkeypatch.setattr(logger_module, "LOG_DIR", tmp_path)

    async def noop(*args: object, **kwargs: object) -> None:
        return None

    async def upgraded(engine: AsyncEngine) -> str:
        return "0039"

    async def no_panel(sdk: object) -> PanelIndex:
        return PanelIndex()

    async def failing(*args: object, **kwargs: object) -> None:
        gateway_secret = "gateway-secret-in-a-frame"
        raise ValueError(f"bad row ({len(gateway_secret)})")

    monkeypatch.setattr(run_module, "BACKUP_DIR", tmp_path)
    monkeypatch.setattr(run_module, "preflight", noop)
    monkeypatch.setattr(run_module, "create_signed_database_dump", noop)
    monkeypatch.setattr(run_module, "fetch_panel_index", no_panel)
    monkeypatch.setattr(run_module, "upgrade_legacy_schema", upgraded)
    monkeypatch.setattr(run_module, "migrate", failing)
    root_handlers = logging.getLogger().handlers[:]
    # loguru's own default: diagnose=True on stderr
    logger.remove()
    logger.add(sys.stderr)
    try:
        with pytest.raises(SystemExit):
            await asyncio.to_thread(main)
    finally:
        logger.remove()
        logger.add(sys.stderr)
        logger.configure(patcher=lambda _record: None)
        logging.getLogger().handlers = root_handlers

    err = capfd.readouterr().err
    assert "Legacy migration failed" in err
    assert "gateway-secret-in-a-frame" not in err
    assert config.crypt_key.get_secret_value() not in err
