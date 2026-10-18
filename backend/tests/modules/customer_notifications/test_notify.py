from typing import Any, Optional, cast

import pytest
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import AppConfig
from app.core.constants import REDIS_KEY_PREFIX
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, PaymentOutcome, PurchaseChannel
from app.core.exceptions import RetryableTaskError
from app.core.metrics import WORKER_METRICS_REGISTRY
from app.core.utils.time import datetime_now
from app.modules.customer_notifications.dto import NotifyCustomerDto
from app.modules.customer_notifications.metrics import CUSTOMER_NOTIFICATIONS
from app.modules.customer_notifications.usecases import NotifyCustomerUseCase
from app.modules.notifications.render import NotificationRenderer
from app.modules.settings import SettingsRepository
from app.modules.transactions import TransactionRepository
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository
from tests.fakes.dispatch import RecordingDispatch
from tests.modules.customer_notifications.factories import FakeBotSignals, create_order

_FTL = """\
ntf-customer-open-cabinet = Open cabinet
ntf-customer-subscription-purchased = Subscription is active.
    .title = Activated
ntf-customer-subscription-expiring = Expires soon.
    .title = Expiring
ntf-customer-paid-order-not-fulfilled = Not issued.
    .title = Problem
ntf-customer-torrent-blocker-report = Torrents are forbidden.
    .title = Torrents
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
        orders: TransactionRepository,
        uow: UnitOfWork,
        redis: Redis,
        config: AppConfig,
    ) -> None:
        self.telegram = RecordingDispatch()
        self.email = RecordingDispatch()
        self.users = users
        self.orders = orders
        self.uow = uow
        self.tokens = _Tokens("token")
        self.signals = FakeBotSignals()
        self.use_case = NotifyCustomerUseCase(
            users,
            settings,
            orders,
            cast(Any, _Renderers()),
            cast(Any, self.tokens),
            cast(Any, self.signals),
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

    async def notify(
        self,
        user: UserDto,
        event_type: str = _PURCHASED,
        outbox_id: int = 1,
        payment_key: Optional[str] = None,
    ) -> None:
        await self.use_case.system(
            NotifyCustomerDto(
                user_id=user.id,
                event_type=event_type,
                outbox_id=outbox_id,
                args={},
                payment_key=payment_key,
            )
        )

    async def order(self, user: UserDto, channel: PurchaseChannel, key: str) -> int:
        order = await create_order(self.orders, self.uow, user_id=user.id, channel=channel, key=key)
        return order.id


@pytest.fixture
def fx(
    user_repository: UserRepository,
    settings_repository: SettingsRepository,
    session: AsyncSession,
    uow: UnitOfWork,
    redis: Redis,
    config: AppConfig,
) -> _Fixture:
    return _Fixture(
        user_repository, settings_repository, TransactionRepository(session), uow, redis, config
    )


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


async def test_torrent_warning_is_sent_once_a_day_per_user(fx: _Fixture) -> None:
    first = await fx.create(name="a", telegram_id=8101)
    second = await fx.create(name="b", telegram_id=8102)

    await fx.notify(first, "TorrentBlockerReportEvent", outbox_id=11)
    await fx.notify(first, "TorrentBlockerReportEvent", outbox_id=12)
    await fx.notify(second, "TorrentBlockerReportEvent", outbox_id=13)

    assert [m["user_id"] for m in fx.telegram.messages] == [first.id, second.id]


async def test_failed_torrent_warning_can_be_retried(fx: _Fixture) -> None:
    user = await fx.create(name="a", telegram_id=8103)

    async def boom(**kwargs: Any) -> None:
        raise RuntimeError("broker down")

    original = fx.telegram.kiq
    fx.telegram.kiq = boom  # type: ignore[method-assign]
    with pytest.raises(RetryableTaskError):
        await fx.notify(user, "TorrentBlockerReportEvent", outbox_id=21)

    fx.telegram.kiq = original  # type: ignore[method-assign]
    await fx.notify(user, "TorrentBlockerReportEvent", outbox_id=21)

    assert len(fx.telegram.messages) == 1


async def test_bot_blocked_customer_gets_email_instead(fx: _Fixture) -> None:
    user = await fx.create(name="a", telegram_id=8201, email="a@example.com")
    async with fx.uow:
        await fx.users.set_bot_blocked(user.id, True)

    await fx.notify(user, "SubscriptionExpiringEvent")

    assert fx.telegram.messages == []
    assert len(fx.email.messages) == 1


async def test_a_torrent_warning_that_failed_before_sending_is_retried(
    fx: _Fixture, monkeypatch: Any
) -> None:
    user = await fx.create(name="a", telegram_id=8104)

    async def unavailable() -> tuple[Optional[str], Optional[str]]:
        raise RuntimeError("database blip")

    monkeypatch.setattr(fx.tokens, "get_bot_token", unavailable)
    with pytest.raises(RetryableTaskError):
        await fx.notify(user, "TorrentBlockerReportEvent", outbox_id=31)
    monkeypatch.undo()

    # the failed run left no cooldown behind for the retry to trip over
    await fx.notify(user, "TorrentBlockerReportEvent", outbox_id=31)

    assert len(fx.telegram.messages) == 1


async def test_a_refused_mailbox_gets_no_more_notifications(fx: _Fixture) -> None:
    user = await fx.create(name="a", email="dead@example.com")
    async with fx.uow:
        await fx.users.set_email_undeliverable(user.id, datetime_now())

    await fx.notify(user)

    assert fx.email.messages == []


async def test_bot_order_purchase_shows_window(fx: _Fixture) -> None:
    user = await fx.create(name="a", telegram_id=8201, email="a@example.com")
    order_id = await fx.order(user, PurchaseChannel.BOT, "pay-1")

    await fx.notify(user, payment_key="pay-1")

    assert fx.signals.outcomes == [(8201, order_id, PaymentOutcome.SUCCEEDED)]
    assert fx.telegram.messages == []
    assert len(fx.email.messages) == 1


async def test_bot_order_falls_back_to_text_when_bot_is_down(fx: _Fixture) -> None:
    fx.signals.receivers = 0
    user = await fx.create(name="a", telegram_id=8202)
    await fx.order(user, PurchaseChannel.BOT, "pay-2")

    await fx.notify(user, payment_key="pay-2")

    assert len(fx.telegram.messages) == 1


async def test_cabinet_order_purchase_sends_text(fx: _Fixture) -> None:
    user = await fx.create(name="a", telegram_id=8203)
    await fx.order(user, PurchaseChannel.CABINET, "pay-3")

    await fx.notify(user, payment_key="pay-3")

    assert fx.signals.outcomes == []
    assert len(fx.telegram.messages) == 1


async def test_not_fulfilled_bot_order_shows_window(fx: _Fixture) -> None:
    user = await fx.create(name="a", telegram_id=8204)
    order_id = await fx.order(user, PurchaseChannel.BOT, "pay-4")

    await fx.notify(user, "PaidOrderNotFulfilledEvent", payment_key="pay-4")

    assert fx.signals.outcomes == [(8204, order_id, PaymentOutcome.NOT_FULFILLED)]
    assert fx.telegram.messages == []
