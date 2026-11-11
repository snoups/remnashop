from typing import Any

import pytest
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models import EventOutboxEntry
from app.core.db.uow import UnitOfWork
from app.core.ports import EventPublisher
from app.modules.overview.usecases import SampleRemnawaveOnlineUseCase


class _System:
    def __init__(self) -> None:
        self.fail = False
        self.version = "3.0.0"

    async def get_stats(self) -> Any:
        if self.fail:
            raise ConnectionError("panel down")
        online = type("O", (), {"online_now": 3})()
        return type("S", (), {"online_stats": online})()

    async def get_metadata(self) -> Any:
        return type("M", (), {"version": self.version})()


class _Sdk:
    def __init__(self) -> None:
        self.system = _System()


async def _types(session: AsyncSession) -> list[str]:
    rows = (await session.execute(select(EventOutboxEntry.event_type))).scalars().all()
    return list(rows)


async def test_outage_publishes_once_and_recovery_once(
    session: AsyncSession, redis: Redis, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    sdk = _Sdk()
    use_case = SampleRemnawaveOnlineUseCase(sdk, redis, uow, event_publisher)  # type: ignore[arg-type]

    sdk.system.fail = True
    for _ in range(3):
        with pytest.raises(ConnectionError):
            await use_case.system()
    sdk.system.fail = False
    await use_case.system()
    await use_case.system()

    assert await _types(session) == ["RemnawaveUnavailableEvent", "RemnawaveRestoredEvent"]


async def test_unsupported_version_warns_once_per_version(
    session: AsyncSession, redis: Redis, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    sdk = _Sdk()
    sdk.system.version = "2.9.0"
    use_case = SampleRemnawaveOnlineUseCase(sdk, redis, uow, event_publisher)  # type: ignore[arg-type]

    await use_case.system()
    await use_case.system()

    assert await _types(session) == ["RemnawaveVersionMismatchEvent"]


async def test_a_single_failed_sample_publishes_nothing(
    session: AsyncSession, redis: Redis, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    sdk = _Sdk()
    use_case = SampleRemnawaveOnlineUseCase(sdk, redis, uow, event_publisher)  # type: ignore[arg-type]

    sdk.system.fail = True
    with pytest.raises(ConnectionError):
        await use_case.system()
    sdk.system.fail = False
    await use_case.system()

    assert await _types(session) == []


async def test_metadata_failure_does_not_mark_the_panel_down(
    session: AsyncSession, redis: Redis, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    sdk = _Sdk()

    async def broken_metadata() -> Any:
        raise ConnectionError("metadata down")

    sdk.system.get_metadata = broken_metadata  # type: ignore[method-assign]
    use_case = SampleRemnawaveOnlineUseCase(sdk, redis, uow, event_publisher)  # type: ignore[arg-type]

    for _ in range(3):
        await use_case.system()

    assert await _types(session) == []


class _FlakyPublisher:
    def __init__(self, inner: EventPublisher) -> None:
        self._inner = inner
        self.fail_next = False

    async def publish(self, event: Any) -> None:
        if self.fail_next:
            self.fail_next = False
            raise ConnectionError("db down")
        await self._inner.publish(event)


async def test_a_lost_outage_event_is_published_on_the_next_sample(
    session: AsyncSession, redis: Redis, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    sdk = _Sdk()
    publisher = _FlakyPublisher(event_publisher)
    use_case = SampleRemnawaveOnlineUseCase(sdk, redis, uow, publisher)  # type: ignore[arg-type]

    sdk.system.fail = True
    with pytest.raises(ConnectionError):
        await use_case.system()
    publisher.fail_next = True
    with pytest.raises(ConnectionError):
        await use_case.system()
    with pytest.raises(ConnectionError):
        await use_case.system()
    sdk.system.fail = False
    publisher.fail_next = True
    with pytest.raises(ConnectionError):
        await use_case.system()
    await use_case.system()

    assert await _types(session) == ["RemnawaveUnavailableEvent", "RemnawaveRestoredEvent"]


async def test_the_down_flag_expires(
    redis: Redis, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    sdk = _Sdk()
    use_case = SampleRemnawaveOnlineUseCase(sdk, redis, uow, event_publisher)  # type: ignore[arg-type]

    sdk.system.fail = True
    for _ in range(2):
        with pytest.raises(ConnectionError):
            await use_case.system()

    keys = [key async for key in redis.scan_iter("*remnawave_down")]
    assert len(keys) == 1
    assert await redis.ttl(keys[0]) > 0
