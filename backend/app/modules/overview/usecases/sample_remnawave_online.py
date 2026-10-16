from typing import Final

from loguru import logger
from packaging.version import InvalidVersion, Version
from redis.asyncio import Redis
from remnapy import RemnawaveSDK

from app.core.actor import Actor
from app.core.constants import (
    REDIS_KEY_PREFIX,
    REMNAWAVE_MAX_VERSION,
    REMNAWAVE_MIN_VERSION,
    TTL_1H,
    TTL_30D,
)
from app.core.db.uow import UnitOfWork
from app.core.events import BaseEvent
from app.core.ports import EventPublisher
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.overview.events import (
    RemnawaveRestoredEvent,
    RemnawaveUnavailableEvent,
    RemnawaveVersionMismatchEvent,
)
from app.modules.overview.online import record_online_sample

_DOWN_KEY: Final[str] = f"{REDIS_KEY_PREFIX}remnawave_down"
_FAILURES_KEY: Final[str] = f"{REDIS_KEY_PREFIX}remnawave_failed_samples"
# samples run every 5 minutes: two misses in a row is ten minutes of silence
_DOWN_AFTER_FAILURES: Final[int] = 2
_VERSION_WARNED_KEY: Final[str] = f"{REDIS_KEY_PREFIX}remnawave_version_warned"


class SampleRemnawaveOnlineUseCase(UseCase[None, None]):
    required_permission = None

    def __init__(
        self,
        remnawave_sdk: RemnawaveSDK,
        redis: Redis,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._remnawave_sdk = remnawave_sdk
        self._redis = redis
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: None) -> None:
        try:
            stats = await self._remnawave_sdk.system.get_stats()
        except Exception as error:
            await self._record_failure(error)
            raise
        await self._redis.delete(_FAILURES_KEY)
        if await self._redis.delete(_DOWN_KEY):
            await self._publish(RemnawaveRestoredEvent())
        await record_online_sample(self._redis, datetime_now(), int(stats.online_stats.online_now))
        try:
            metadata = await self._remnawave_sdk.system.get_metadata()
        except Exception:
            logger.exception("Failed to read the Remnawave version")
            return
        await self._check_version(metadata.version)

    async def _record_failure(self, error: Exception) -> None:
        # a single timeout is not an outage; one event per outage, not per sample
        failures = await self._redis.incr(_FAILURES_KEY)
        await self._redis.expire(_FAILURES_KEY, TTL_1H)
        if failures >= _DOWN_AFTER_FAILURES and await self._redis.set(_DOWN_KEY, "1", nx=True):
            await self._publish(RemnawaveUnavailableEvent(error=type(error).__name__))

    async def _check_version(self, raw: str) -> None:
        try:
            version = Version(raw)
        except InvalidVersion:
            return
        if REMNAWAVE_MIN_VERSION <= version < REMNAWAVE_MAX_VERSION:
            return
        key = f"{_VERSION_WARNED_KEY}:{version}"
        if await self._redis.set(key, "1", nx=True, ex=TTL_30D):
            await self._publish(
                RemnawaveVersionMismatchEvent(
                    version=str(version),
                    supported=f">={REMNAWAVE_MIN_VERSION},<{REMNAWAVE_MAX_VERSION}",
                )
            )

    async def _publish(self, event: BaseEvent) -> None:
        async with self._uow:
            await self._event_publisher.publish(event)
