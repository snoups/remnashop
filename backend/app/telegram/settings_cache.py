import time
from collections.abc import Awaitable, Callable
from typing import Any, Final, TypeVar, cast

from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.pricing import PricingRepository, PricingSettingsDto
from app.modules.referrals import ReferralRepository, ReferralSettingsDto
from app.modules.settings import (
    AccessSettingsDto,
    BotCommandDto,
    BotRequirementsDto,
    SettingsRepository,
    ShopSettingsDto,
)

T = TypeVar("T")
# how late a dashboard change to these settings may reach the bot
_TTL_S: Final[float] = 10.0


class SettingsSnapshotCache:
    """Settings rows every update reads (access mode, requirements, commands,
    shop and referral settings) were most of a /start's database round trips;
    the bot keeps each for a few seconds per process."""

    def __init__(self) -> None:
        self._entries: dict[str, tuple[float, Any]] = {}

    async def get(self, key: str, load: Callable[[], Awaitable[T]]) -> T:
        now = time.monotonic()
        entry = self._entries.get(key)
        if entry is not None and entry[0] > now:
            return cast(T, entry[1])
        value = await load()
        self._entries[key] = (now + _TTL_S, value)
        return value


class CachedSettingsRepository(SettingsRepository):
    def __init__(self, session: AsyncSession, cache: SettingsSnapshotCache) -> None:
        super().__init__(session)
        self._cache = cache

    async def get_shop_settings(self) -> ShopSettingsDto:
        return await self._cache.get("shop", super().get_shop_settings)

    async def get_access_settings(self) -> AccessSettingsDto:
        return await self._cache.get("access", super().get_access_settings)

    async def get_bot_requirements(self) -> BotRequirementsDto:
        return await self._cache.get("bot_requirements", super().get_bot_requirements)

    async def list_bot_commands(self) -> list[BotCommandDto]:
        # a copy: the caller may reorder the list it gets
        return list(await self._cache.get("bot_commands", super().list_bot_commands))


class CachedReferralRepository(ReferralRepository):
    def __init__(self, session: AsyncSession, cache: SettingsSnapshotCache) -> None:
        super().__init__(session)
        self._cache = cache

    async def get_settings(self) -> ReferralSettingsDto:
        return await self._cache.get("referral", super().get_settings)


class CachedPricingRepository(PricingRepository):
    def __init__(self, session: AsyncSession, cache: SettingsSnapshotCache) -> None:
        super().__init__(session)
        self._cache = cache

    async def get_settings(self) -> PricingSettingsDto:
        return await self._cache.get("pricing", super().get_settings)


class SettingsCacheProvider(Provider):
    """Registered after the module providers in the bot's container only: api
    and worker keep reading these rows fresh."""

    settings_snapshot_cache = provide(SettingsSnapshotCache, scope=Scope.APP)

    @provide(scope=Scope.REQUEST)
    def settings_repository(
        self, session: AsyncSession, cache: SettingsSnapshotCache
    ) -> SettingsRepository:
        return CachedSettingsRepository(session, cache)

    @provide(scope=Scope.REQUEST)
    def referral_repository(
        self, session: AsyncSession, cache: SettingsSnapshotCache
    ) -> ReferralRepository:
        return CachedReferralRepository(session, cache)

    @provide(scope=Scope.REQUEST)
    def pricing_repository(
        self, session: AsyncSession, cache: SettingsSnapshotCache
    ) -> PricingRepository:
        return CachedPricingRepository(session, cache)
