from typing import Awaitable, Callable

import pytest
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.cli.legacy.errors import LegacyMigrationError
from app.cli.legacy.migrate import flush_shop_redis, migrate, preflight
from app.cli.legacy.panel import PanelIndex
from app.cli.legacy.rollback import drop_legacy, rollback
from app.cli.legacy.schema import LEGACY_HEAD, current_revision
from app.core.config import AppConfig

LegacyAt = Callable[[AsyncEngine, str], Awaitable[None]]


async def _migrated(engine: AsyncEngine, config: AppConfig, legacy_at: LegacyAt) -> None:
    await legacy_at(engine, LEGACY_HEAD)
    await migrate(
        engine,
        panel_index=PanelIndex(),
        crypt_key=config.crypt_key.get_secret_value(),
        bot_owner_id=None,
        original_revision=LEGACY_HEAD,
    )


async def _revision(engine: AsyncEngine) -> str | None:
    async with engine.connect() as connection:
        return await current_revision(connection)


async def test_rollback_restores_old_public(
    legacy_engine: AsyncEngine, config: AppConfig, legacy_at: LegacyAt
) -> None:
    await _migrated(legacy_engine, config, legacy_at)
    assert await _revision(legacy_engine) == "current"

    await rollback(legacy_engine)

    assert await _revision(legacy_engine) == LEGACY_HEAD
    async with legacy_engine.connect() as connection:
        left = await connection.scalar(
            text("SELECT 1 FROM information_schema.schemata WHERE schema_name = 'legacy'")
        )
    assert left is None


async def test_rollback_without_legacy_fails(
    legacy_engine: AsyncEngine, legacy_at: LegacyAt
) -> None:
    await legacy_at(legacy_engine, LEGACY_HEAD)
    with pytest.raises(LegacyMigrationError):
        await rollback(legacy_engine)
    assert await _revision(legacy_engine) == LEGACY_HEAD


async def test_drop_legacy(
    legacy_engine: AsyncEngine, config: AppConfig, legacy_at: LegacyAt
) -> None:
    await _migrated(legacy_engine, config, legacy_at)
    await drop_legacy(legacy_engine)
    assert await _revision(legacy_engine) == "current"
    with pytest.raises(LegacyMigrationError):
        await drop_legacy(legacy_engine)


async def test_second_migrate_refused(
    legacy_engine: AsyncEngine, config: AppConfig, legacy_at: LegacyAt
) -> None:
    await _migrated(legacy_engine, config, legacy_at)
    with pytest.raises(LegacyMigrationError):
        await preflight(legacy_engine, sdk=None, crypt_key="x")  # type: ignore[arg-type]
    assert await _revision(legacy_engine) == "current"


async def test_flush_shop_redis_clears_legacy_stream(redis: Redis) -> None:
    await redis.xadd("taskiq", {"data": "x"})
    assert await redis.type("taskiq") == "stream"
    await flush_shop_redis(redis)
    assert await redis.exists("taskiq") == 0
