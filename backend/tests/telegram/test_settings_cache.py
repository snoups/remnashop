from typing import Any, cast

from aiogram import Bot
from aiogram_dialog import BgManagerFactory
from dishka import Scope
from fluentogram import TranslatorHub

from app.core.config import AppConfig
from app.modules.pricing import PricingRepository
from app.modules.referrals import ReferralRepository
from app.modules.settings import BotCommandDto, SettingsRepository
from app.telegram import settings_cache
from app.telegram.container import create_aiogram_container
from app.telegram.settings_cache import (
    CachedPricingRepository,
    CachedReferralRepository,
    CachedSettingsRepository,
    SettingsSnapshotCache,
)


async def test_a_value_is_reused_until_it_expires(monkeypatch: Any) -> None:
    now = 100.0
    monkeypatch.setattr(settings_cache.time, "monotonic", lambda: now)
    loads: list[int] = []

    async def load() -> int:
        loads.append(1)
        return len(loads)

    cache = SettingsSnapshotCache()
    assert await cache.get("shop", load) == 1
    assert await cache.get("shop", load) == 1

    now += 11
    assert await cache.get("shop", load) == 2
    assert len(loads) == 2


async def test_the_bot_container_reads_settings_through_the_cache(config: AppConfig) -> None:
    placeholder = cast(Any, object())
    container = create_aiogram_container(
        config,
        cast(BgManagerFactory, placeholder),
        cast(Bot, placeholder),
        cast(TranslatorHub, placeholder),
    )
    async with container(scope=Scope.REQUEST) as request:
        assert isinstance(await request.get(SettingsRepository), CachedSettingsRepository)
        assert isinstance(await request.get(ReferralRepository), CachedReferralRepository)
        assert isinstance(await request.get(PricingRepository), CachedPricingRepository)
    await container.close()


async def test_bot_commands_come_back_as_a_fresh_list(monkeypatch: Any) -> None:
    commands = [
        BotCommandDto(command="start", sort_order=0),
        BotCommandDto(command="help", sort_order=1),
    ]

    async def stored(self: SettingsRepository) -> list[BotCommandDto]:
        return list(commands)

    monkeypatch.setattr(SettingsRepository, "list_bot_commands", stored)
    repository = CachedSettingsRepository(cast(Any, None), SettingsSnapshotCache())

    first = await repository.list_bot_commands()
    first.reverse()

    assert await repository.list_bot_commands() == commands
