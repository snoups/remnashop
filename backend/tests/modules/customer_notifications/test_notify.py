from typing import Any, Optional, cast

import pytest
from redis.asyncio import Redis

from app.core.config import AppConfig
from app.core.constants import REDIS_KEY_PREFIX
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale
from app.core.exceptions import RetryableTaskError
from app.core.metrics import WORKER_METRICS_REGISTRY
from app.modules.customer_notifications.dto import NotifyCustomerDto
from app.modules.customer_notifications.metrics import CUSTOMER_NOTIFICATIONS
from app.modules.customer_notifications.usecases import NotifyCustomerUseCase
from app.modules.notifications.render import NotificationRenderer
from app.modules.settings import SettingsRepository
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository
from tests.fakes.dispatch import RecordingDispatch

_FTL = """\
ntf-customer-open-cabinet = Open cabinet
ntf-customer-subscription-purchased = Subscription is active.
    .title = Activated
ntf-customer-subscription-expiring = Expires soon.
    .title = Expiring
"""
_PURCHASED = "SubscriptionPurchasedEvent"


class _Renderers:
    async def build(self) -> NotificationRenderer:
        return NotificationRenderer({Locale.EN: _FTL}, default_locale=Locale.EN)


class _Tokens:
    def __init__(self, token: Optional[str]) -> None:
        self.token = token

    async def get_bot_token(self) -> tuple[Optional[str], Optional[str]]:
        return self.token, None


class _Fixture:
    def __init__(
        self,
        users: UserRepository,
        settings: SettingsRepository,
        uow: UnitOfWork,
        redis: Redis,
        config: AppConfig,
    ) -> None:
        self.telegram = RecordingDispatch()
        self.email = RecordingDispatch()
        self.users = users
        self.uow = uow
        self.tokens = _Tokens("token")
        self.use_case = NotifyCustomerUseCase(
            users,
            settings,
            cast(Any, _Renderers()),
            cast(Any, self.tokens),
            cast(Any, self.telegram),
            cast(Any, self.email),
            redis,
            config,
            uow,
        )

    async def create(self, **fields: Any) -> UserDto:
        async with self.uow:
            user = await self.users.create(CreateUserDto(**fields))
            await self.uow.commit()
        return user

    async def notify(self, user: UserDto, event_type: str = _PURCHASED, outbox_id: int = 1) -> None:
        await self.use_case.system(
            NotifyCustomerDto(user_id=user.id, event_type=event_type, outbox_id=outbox_id, args={})
        )


@pytest.fixture
def fx(
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
    redis: Redis,
    config: AppConfig,
) -> _Fixture:
    return _Fixture(user_repository, settings_repository, uow, redis, config)


async def test_telegram_and_email_both_queued(fx: _Fixture) -> None:
    user = await fx.create(name="a", telegram_id=8001, email="a@example.com")

    await fx.notify(user)

    assert fx.telegram.messages == [
        {"user_id": user.id, "text": "Activated\n\nSubscription is active."}
    ]
    assert len(fx.email.messages) == 1
    message = fx.email.messages[0]
    assert message["to"] == "a@example.com"
    assert message["subject"] == "Activated"
    assert "Subscription is active." in message["html"]


async def test_same_outbox_id_is_not_sent_twice(fx: _Fixture) -> None:
    user = await fx.create(name="a", telegram_id=8002, email="a@example.com")

    await fx.notify(user)
    await fx.notify(user)

    assert len(fx.telegram.messages) == 1
    assert len(fx.email.messages) == 1


async def test_blocked_user_gets_nothing(fx: _Fixture) -> None:
    user = await fx.create(name="a", telegram_id=8003, email="a@example.com", is_blocked=True)

    await fx.notify(user)

    assert fx.telegram.messages == []
    assert fx.email.messages == []


async def test_missing_translation_falls_back_to_default_locale(fx: _Fixture) -> None:
    user = await fx.create(name="a", telegram_id=8004, language=Locale.DE)

    await fx.notify(user)

    text = fx.telegram.messages[0]["text"]
    assert text == "Activated\n\nSubscription is active."


async def test_email_only_customer_gets_only_email_for_reminder(fx: _Fixture) -> None:
    user = await fx.create(name="a", email="a@example.com")

    await fx.notify(user, "SubscriptionExpiringEvent")

    assert fx.telegram.messages == []
    assert len(fx.email.messages) == 1


async def test_smtp_pause_does_not_block_queueing(fx: _Fixture, redis: Redis) -> None:
    await redis.set(f"{REDIS_KEY_PREFIX}smtp_unavailable", "1", ex=60)
    user = await fx.create(name="a", telegram_id=8006, email="a@example.com")

    await fx.notify(user)

    assert len(fx.telegram.messages) == 1
    assert len(fx.email.messages) == 1


async def test_failed_email_releases_its_key_and_keeps_telegram(fx: _Fixture, redis: Redis) -> None:
    user = await fx.create(name="a", telegram_id=8007, email="a@example.com")

    async def boom(**kwargs: Any) -> None:
        raise RuntimeError("broker down")

    original = fx.email.kiq
    fx.email.kiq = boom  # type: ignore[method-assign]
    with pytest.raises(RetryableTaskError):
        await fx.notify(user)

    assert len(fx.telegram.messages) == 1
    assert not await redis.exists(f"{REDIS_KEY_PREFIX}customer_notified:1:EMAIL")

    fx.email.kiq = original  # type: ignore[method-assign]
    await fx.notify(user)

    assert len(fx.telegram.messages) == 1
    assert len(fx.email.messages) == 1


async def test_no_bot_token_means_no_telegram_channel(fx: _Fixture) -> None:
    fx.tokens.token = None
    user = await fx.create(name="a", telegram_id=8008, email="a@example.com")

    await fx.notify(user, "SubscriptionExpiringEvent")

    assert fx.telegram.messages == []
    assert len(fx.email.messages) == 1


async def test_transient_lookup_failure_is_retryable(fx: _Fixture, monkeypatch: Any) -> None:
    user = await fx.create(name="a", telegram_id=8009, email="a@example.com")

    async def boom() -> None:
        raise ConnectionError("db down")

    monkeypatch.setattr(fx.tokens, "get_bot_token", boom)
    with pytest.raises(RetryableTaskError):
        await fx.notify(user)

    monkeypatch.undo()
    await fx.notify(user)
    assert len(fx.telegram.messages) == 1
    assert len(fx.email.messages) == 1


def test_counter_is_in_the_worker_registry() -> None:
    CUSTOMER_NOTIFICATIONS.labels(channel="EMAIL", result="queued").inc()
    assert WORKER_METRICS_REGISTRY.get_sample_value(
        "remnashop_customer_notifications_total", {"channel": "EMAIL", "result": "queued"}
    )
