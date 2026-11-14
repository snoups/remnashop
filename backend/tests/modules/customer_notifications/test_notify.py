import secrets
from dataclasses import replace
from datetime import timedelta
from typing import Any, Optional, Union, cast

import pytest
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import AppConfig
from app.core.constants import REDIS_KEY_PREFIX
from app.core.db.models import CustomerNotification
from app.core.db.uow import UnitOfWork
from app.core.enums import (
    Locale,
    PaymentOutcome,
    PurchaseChannel,
    SessionAudience,
    SubscriptionStatus,
)
from app.core.exceptions import RetryableTaskError
from app.core.metrics import WORKER_METRICS_REGISTRY
from app.core.security import hash_refresh_token
from app.core.utils.time import datetime_now
from app.modules.auth.dto import CreateSessionDto
from app.modules.auth.repository import SessionRepository
from app.modules.customer_notifications.dto import NotifyCustomerDto
from app.modules.customer_notifications.links import customer_url
from app.modules.customer_notifications.metrics import CUSTOMER_NOTIFICATIONS
from app.modules.customer_notifications.repository import CustomerNotificationRepository
from app.modules.customer_notifications.usecases import NotifyCustomerUseCase
from app.modules.notifications.dto import PushMessage
from app.modules.notifications.render import NotificationRenderer
from app.modules.notifications.repository import NotificationRepository
from app.modules.settings import SettingsRepository
from app.modules.settings.dto import UpdateShopSettingsDto
from app.modules.subscriptions import SubscriptionRepository
from app.modules.subscriptions.dto import CreateSubscriptionDto
from app.modules.transactions import TransactionRepository
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository
from tests.fakes.dispatch import RecordingDispatch
from tests.modules.customer_notifications.factories import FakeBotSignals, create_order
from tests.modules.subscriptions.factories import make_plan_snapshot

_FTL = """\
ntf-customer-open-cabinet = Open cabinet
ntf-customer-button-renew = Renew
ntf-customer-button-buy = Buy
ntf-customer-button-close = Close
ntf-customer-button-connect = Connect
ntf-customer-button-support = Support
ntf-customer-button-revoke-sessions = End sessions
ntf-customer-cabinet-new-device-sign-in = Signed in from { $ip }.
    .title = New sign-in
ntf-customer-subscription-changed = Plan changed.
    .title = Changed
ntf-customer-subscription-purchased = Subscription is active.
    .title = Activated
ntf-customer-subscription-granted = { $plan_name } granted.
    .title = Granted
ntf-customer-subscription-expiring = Expires soon. { $is_trial ->
        [yes] Buy one.
       *[no] Renew it.
    }
    .title = Expiring
ntf-customer-subscription-not-connected = Subscribed { $span } { $span_unit } ago.
    .title = Connect
ntf-customer-paid-order-not-fulfilled = Not issued.
    .title = Problem
ntf-customer-torrent-blocker-report = Torrents are forbidden.
    .title = Torrents
ntf-customer-payments-restored = Payments are back.
    .title = Payments
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


class _Push:
    def __init__(self) -> None:
        self.sent: list[tuple[int, PushMessage, SessionAudience]] = []

    async def send(self, user_id: int, message: PushMessage, audience: SessionAudience) -> int:
        self.sent.append((user_id, message, audience))
        return 1


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
        self.push = _Push()
        self.users = users
        self.settings = settings
        self.orders = orders
        self.uow = uow
        self.feed = CustomerNotificationRepository(orders.session)
        self.notifications = NotificationRepository(orders.session)
        self.tokens = _Tokens("token")
        self.signals = FakeBotSignals()
        self.use_case = NotifyCustomerUseCase(
            users,
            settings,
            orders,
            SubscriptionRepository(orders.session),
            cast(Any, _Renderers()),
            cast(Any, self.tokens),
            cast(Any, self.signals),
            cast(Any, self.telegram),
            cast(Any, self.email),
            self.feed,
            self.notifications,
            cast(Any, self.push),
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
        subscription_id: Optional[int] = None,
        telegram_refused: bool = False,
        args: Optional[dict[str, Union[str, int]]] = None,
    ) -> None:
        await self.use_case.system(
            NotifyCustomerDto(
                user_id=user.id,
                event_type=event_type,
                outbox_id=outbox_id,
                args=args or {},
                payment_key=payment_key,
                subscription_id=subscription_id,
                telegram_refused=telegram_refused,
            )
        )

    async def subscribe_push(self, user: UserDto, audience: SessionAudience) -> None:
        async with self.uow:
            session = await SessionRepository(self.orders.session).create(
                CreateSessionDto(
                    user_id=user.id,
                    refresh_token_hash=hash_refresh_token(secrets.token_urlsafe(16)),
                    ip_address="127.0.0.1",
                    user_agent=None,
                    expires_at=datetime_now() + timedelta(days=30),
                    audience=audience,
                )
            )
            await self.notifications.upsert_push_subscription(
                user_id=user.id,
                session_id=session.id,
                endpoint=f"https://push.example/{secrets.token_hex(4)}",
                p256dh="k",
                auth="a",
                user_agent=None,
            )

    async def feed_rows(self, user: UserDto) -> list[CustomerNotification]:
        rows = await self.orders.session.scalars(
            select(CustomerNotification).where(CustomerNotification.user_id == user.id)
        )
        return list(rows)

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
        {
            "user_id": user.id,
            "text": "<b>🔔 Activated</b>\n\n<blockquote>Subscription is active.</blockquote>",
            "buttons": [{"text": "Close", "callback_data": "cn:close"}],
            "notification": {
                "user_id": user.id,
                "event_type": _PURCHASED,
                "outbox_id": 1,
                "args": {},
                "payment_key": None,
                "subscription_id": None,
                "telegram_refused": False,
            },
            "html": True,
        }
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
    assert text == "<b>🔔 Activated</b>\n\n<blockquote>Subscription is active.</blockquote>"


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
    assert not await redis.exists(f"{REDIS_KEY_PREFIX}customer_notified:1:{user.id}:EMAIL")

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


async def test_a_refused_telegram_send_goes_out_by_email(fx: _Fixture) -> None:
    user = await fx.create(name="a", telegram_id=8202, email="a@example.com")
    # the cooldown run already took its slot when Telegram refused
    await fx.notify(user, "TorrentBlockerReportEvent", outbox_id=41)
    assert fx.email.messages == []
    async with fx.uow:
        await fx.users.set_bot_blocked(user.id, True)

    await fx.notify(user, "TorrentBlockerReportEvent", outbox_id=41, telegram_refused=True)
    await fx.notify(user, "TorrentBlockerReportEvent", outbox_id=41, telegram_refused=True)

    assert len(fx.telegram.messages) == 1
    assert [m["to"] for m in fx.email.messages] == ["a@example.com"]


async def test_a_refused_receipt_is_not_emailed_twice(fx: _Fixture) -> None:
    user = await fx.create(name="a", telegram_id=8203, email="a@example.com")
    await fx.notify(user, outbox_id=42)
    async with fx.uow:
        await fx.users.set_bot_blocked(user.id, True)

    await fx.notify(user, outbox_id=42, telegram_refused=True)

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


async def test_expiring_subscription_gets_a_renew_button(fx: _Fixture) -> None:
    user = await fx.create(name="r", telegram_id=8090)

    await fx.notify(user, "SubscriptionExpiringEvent", subscription_id=77)

    (message,) = fx.telegram.messages
    assert message["buttons"] == [
        {"text": "Renew", "callback_data": "cn:renew:77"},
        {"text": "Close", "callback_data": "cn:close"},
    ]


async def test_expiring_trial_gets_a_buy_button(fx: _Fixture) -> None:
    user = await fx.create(name="t", telegram_id=8091)
    async with fx.uow:
        trial = await SubscriptionRepository(fx.orders.session).create(
            CreateSubscriptionDto(
                user_id=user.id,
                remnawave_user_id=880_091,
                status=SubscriptionStatus.ACTIVE,
                is_trial=True,
                traffic_limit=0,
                device_limit=0,
                expire_at=datetime_now(),
                url="https://example.test/sub",
                plan_snapshot=make_plan_snapshot(plan_id=1),
            )
        )

    await fx.notify(user, "SubscriptionExpiringEvent", subscription_id=trial.id)

    (message,) = fx.telegram.messages
    assert message["buttons"][0] == {"text": "Buy", "callback_data": "cn:buy"}
    assert (
        message["text"] == "<b>🔔 Expiring</b>\n\n<blockquote>Expires soon. Buy one.</blockquote>"
    )
    (row,) = await fx.feed_rows(user)
    assert row.args == {"is_trial": "yes"}


async def test_a_grant_names_its_plan(fx: _Fixture) -> None:
    # the event carries only the plan id; the feed renders the row again later
    user = await fx.create(name="g", telegram_id=8093)
    async with fx.uow:
        granted = await SubscriptionRepository(fx.orders.session).create(
            CreateSubscriptionDto(
                user_id=user.id,
                remnawave_user_id=880_093,
                status=SubscriptionStatus.ACTIVE,
                traffic_limit=0,
                device_limit=0,
                expire_at=datetime_now(),
                url="https://example.test/sub",
                plan_snapshot=replace(make_plan_snapshot(plan_id=1), name="Про"),
            )
        )

    await fx.notify(
        user,
        "SubscriptionGrantedEvent",
        subscription_id=granted.id,
        args={"duration_days": 30},
    )

    (row,) = await fx.feed_rows(user)
    assert row.args == {"duration_days": 30, "plan_name": "Про"}


async def test_hours_are_rendered_as_a_span_but_stored_as_hours(fx: _Fixture) -> None:
    user = await fx.create(name="h", telegram_id=8092)

    await fx.notify(user, "SubscriptionNotConnectedEvent", subscription_id=5, args={"hours": 48})

    (message,) = fx.telegram.messages
    assert message["text"] == "<b>🔔 Connect</b>\n\n<blockquote>Subscribed 2 day ago.</blockquote>"
    (row,) = await fx.feed_rows(user)
    assert row.args == {"hours": 48}


async def test_feed_row_written(fx: _Fixture) -> None:
    user = await fx.create(name="f", telegram_id=8301)

    await fx.notify(user, "SubscriptionExpiringEvent", subscription_id=5)

    (row,) = await fx.feed_rows(user)
    assert (row.event_type, row.args, row.subscription_id, row.outbox_id) == (
        "SubscriptionExpiringEvent",
        {"is_trial": "no"},
        5,
        1,
    )


async def test_feed_row_without_any_channel(fx: _Fixture) -> None:
    user = await fx.create(name="f")

    await fx.notify(user)

    assert len(await fx.feed_rows(user)) == 1
    assert fx.telegram.messages == []
    assert fx.email.messages == []


async def test_feed_not_duplicated_on_retry(fx: _Fixture) -> None:
    user = await fx.create(name="f", telegram_id=8302)

    await fx.notify(user, outbox_id=51)
    await fx.notify(user, outbox_id=51)

    assert len(await fx.feed_rows(user)) == 1


async def test_feed_not_duplicated_on_retry_after_channel_failure(
    fx: _Fixture, redis: Redis
) -> None:
    user = await fx.create(name="f", telegram_id=8307)
    await fx.subscribe_push(user, SessionAudience.CABINET)
    sent = fx.push.sent

    async def boom(*args: Any) -> int:
        raise RuntimeError("push gateway down")

    healthy = fx.push.send
    fx.push.send = boom  # type: ignore[method-assign]
    with pytest.raises(RetryableTaskError):
        await fx.notify(user, outbox_id=52)

    assert len(await fx.feed_rows(user)) == 1
    assert len(fx.telegram.messages) == 1
    assert not await redis.exists(f"{REDIS_KEY_PREFIX}customer_notified:52:{user.id}:PUSH")

    fx.push.send = healthy  # type: ignore[method-assign]
    await fx.notify(user, outbox_id=52)

    assert len(await fx.feed_rows(user)) == 1
    assert len(fx.telegram.messages) == 1
    assert len(sent) == 1


async def test_feed_respects_cooldown(fx: _Fixture) -> None:
    user = await fx.create(name="f", telegram_id=8303)

    await fx.notify(user, "TorrentBlockerReportEvent", outbox_id=61)
    await fx.notify(user, "TorrentBlockerReportEvent", outbox_id=62)

    assert len(await fx.feed_rows(user)) == 1


async def test_push_sent_to_cabinet_when_subscribed(fx: _Fixture) -> None:
    user = await fx.create(name="p", telegram_id=8304, email="p@example.com")
    await fx.subscribe_push(user, SessionAudience.CABINET)

    await fx.notify(user, "SubscriptionExpiringEvent", subscription_id=9)

    assert fx.push.sent == [
        (
            user.id,
            PushMessage(
                title="Expiring",
                body="Expires soon. Renew it.",
                url=customer_url("SubscriptionExpiringEvent", 9, {}),
                tag="SubscriptionExpiringEvent",
            ),
            SessionAudience.CABINET,
        )
    ]
    assert len(fx.telegram.messages) == 1
    assert fx.email.messages == []


async def test_push_only_customer_gets_push(fx: _Fixture) -> None:
    user = await fx.create(name="p")
    await fx.subscribe_push(user, SessionAudience.CABINET)

    await fx.notify(user)

    assert len(fx.push.sent) == 1


async def test_push_not_sent_twice_for_one_outbox(fx: _Fixture) -> None:
    user = await fx.create(name="p", telegram_id=8305)
    await fx.subscribe_push(user, SessionAudience.CABINET)

    await fx.notify(user, outbox_id=71)
    await fx.notify(user, outbox_id=71)

    assert len(fx.push.sent) == 1


async def test_no_push_without_cabinet_subscription(fx: _Fixture) -> None:
    user = await fx.create(name="p", telegram_id=8306)
    await fx.subscribe_push(user, SessionAudience.DASHBOARD)

    await fx.notify(user)

    assert fx.push.sent == []
    assert len(fx.telegram.messages) == 1


async def test_one_outbox_event_reaches_every_customer_it_names(fx: _Fixture) -> None:
    # the payment waitlist: one AccessSettingsChangedEvent, a notification per waiting customer
    first = await fx.create(name="w1", telegram_id=8401)
    second = await fx.create(name="w2", email="w2@example.com")

    await fx.notify(first, event_type="PaymentsRestored", outbox_id=77)
    await fx.notify(second, event_type="PaymentsRestored", outbox_id=77)

    assert len(fx.telegram.messages) == 1
    # a one-line italic notice, not a card
    text = fx.telegram.messages[0]["text"]
    assert text.startswith("<i>") and text.endswith("</i>") and "<b>" not in text
    assert len(fx.email.messages) == 1
    assert len(await fx.feed_rows(first)) == 1
    assert len(await fx.feed_rows(second)) == 1


async def _subscription(fx: _Fixture, user: UserDto, remnawave_user_id: int) -> int:
    async with fx.uow:
        subscription = await SubscriptionRepository(fx.orders.session).create(
            CreateSubscriptionDto(
                user_id=user.id,
                remnawave_user_id=remnawave_user_id,
                status=SubscriptionStatus.ACTIVE,
                traffic_limit=0,
                device_limit=3,
                expire_at=datetime_now() + timedelta(days=10),
                url="https://example.test/sub",
                plan_snapshot=make_plan_snapshot(plan_id=1, name="Pro"),
            )
        )
    return subscription.id


async def test_a_purchase_offers_to_connect_through_the_subscription_page(fx: _Fixture) -> None:
    user = await fx.create(name="c", telegram_id=8092)
    subscription_id = await _subscription(fx, user, 880_092)

    await fx.notify(user, _PURCHASED, subscription_id=subscription_id)

    (message,) = fx.telegram.messages
    assert message["buttons"] == [
        {"text": "Connect", "url": "https://example.test/sub"},
        {"text": "Close", "callback_data": "cn:close"},
    ]


async def test_a_customer_who_never_connected_gets_connect_and_support(fx: _Fixture) -> None:
    user = await fx.create(name="s", telegram_id=8093)
    subscription_id = await _subscription(fx, user, 880_093)
    async with fx.uow:
        await fx.settings.update_shop_settings(
            UpdateShopSettingsDto(
                support_telegram="help_desk", fields_set=frozenset({"support_telegram"})
            )
        )

    await fx.notify(
        user, "SubscriptionNotConnectedEvent", subscription_id=subscription_id, args={"hours": 5}
    )

    (message,) = fx.telegram.messages
    assert message["buttons"] == [
        {"text": "Connect", "url": "https://example.test/sub"},
        {"text": "Support", "url": "https://t.me/help_desk"},
        {"text": "Close", "callback_data": "cn:close"},
    ]


async def test_a_plan_change_shows_the_new_plan_under_the_text(fx: _Fixture) -> None:
    user = await fx.create(name="p", telegram_id=8094)
    subscription_id = await _subscription(fx, user, 880_094)

    await fx.notify(user, "SubscriptionChangedEvent", subscription_id=subscription_id)

    (message,) = fx.telegram.messages
    assert "📦 <b>Pro</b>:\n<blockquote>" in message["text"]


async def test_a_new_sign_in_offers_to_end_every_session(fx: _Fixture) -> None:
    user = await fx.create(name="n", telegram_id=8095)
    async with fx.uow:
        await fx.settings.update_shop_settings(
            UpdateShopSettingsDto(
                support_url="https://help.test", fields_set=frozenset({"support_url"})
            )
        )

    await fx.notify(
        user, "CabinetNewDeviceSignInEvent", args={"ip": "1.2.3.4", "browser": "Firefox"}
    )

    (message,) = fx.telegram.messages
    assert message["buttons"] == [
        {"text": "End sessions", "callback_data": "cn:revoke-sessions"},
        {"text": "Support", "url": "https://help.test"},
        {"text": "Close", "callback_data": "cn:close"},
    ]
