import asyncio

import pytest
from redis.asyncio import Redis

from app.core.bot_signals import RedisBotSignals
from app.core.constants import TELEGRAM_RESTART_CHANNEL
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, Role
from app.core.exceptions import PermissionDeniedError
from app.modules.settings.usecases import RestartBotUseCase
from app.modules.users.dto import UserDto
from tests.fakes.events import RecordingEventPublisher

OWNER = UserDto(id=1, login="admin", name="admin", role=Role.OWNER, language=Locale.EN)
REGULAR_USER = UserDto(id=2, name="Bob", role=Role.USER, language=Locale.EN)


async def test_publishes_to_restart_channel(redis: Redis, uow: UnitOfWork) -> None:
    pubsub = redis.pubsub()
    await pubsub.subscribe(TELEGRAM_RESTART_CHANNEL)
    await pubsub.get_message(timeout=1)  # discard the subscribe confirmation

    await RestartBotUseCase(RedisBotSignals(redis), uow, RecordingEventPublisher())(OWNER)

    message = await pubsub.get_message(timeout=2)
    assert message is not None
    assert message["type"] == "message"
    assert message["channel"] == TELEGRAM_RESTART_CHANNEL

    await pubsub.unsubscribe(TELEGRAM_RESTART_CHANNEL)
    await pubsub.aclose()


async def test_regular_user_cannot_restart_bot(redis: Redis, uow: UnitOfWork) -> None:
    with pytest.raises(PermissionDeniedError):
        await RestartBotUseCase(RedisBotSignals(redis), uow, RecordingEventPublisher())(
            REGULAR_USER
        )


async def test_no_subscriber_does_not_raise(redis: Redis, uow: UnitOfWork) -> None:
    # Fire-and-forget: publishing with nobody listening must not error.
    await asyncio.wait_for(
        RestartBotUseCase(RedisBotSignals(redis), uow, RecordingEventPublisher())(OWNER), timeout=2
    )
