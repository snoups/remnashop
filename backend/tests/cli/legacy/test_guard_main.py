import asyncio
from typing import Awaitable, Callable

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from app.cli.legacy_guard import main
from app.core.config import AppConfig


def _point_at(monkeypatch: pytest.MonkeyPatch, config: AppConfig, engine: AsyncEngine) -> None:
    pointed = config.model_copy(
        update={"database": config.database.model_copy(update={"name": engine.url.database})}
    )
    monkeypatch.setattr(AppConfig, "get", classmethod(lambda cls: pointed))


async def test_guard_main_passes_on_empty_database(
    legacy_engine: AsyncEngine,
    config: AppConfig,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _point_at(monkeypatch, config, legacy_engine)
    await asyncio.to_thread(main)
    assert capsys.readouterr().err == ""


async def test_guard_main_exits_on_legacy_database(
    legacy_engine: AsyncEngine,
    config: AppConfig,
    legacy_at: Callable[[AsyncEngine, str], Awaitable[None]],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    await legacy_at(legacy_engine, "0039")
    _point_at(monkeypatch, config, legacy_engine)
    with pytest.raises(SystemExit) as exit_info:
        await asyncio.to_thread(main)
    assert exit_info.value.code == 1
    assert "docker compose run --rm remnashop cli" in capsys.readouterr().err
