from dataclasses import asdict
from typing import Final, Optional

from loguru import logger
from redis.asyncio import Redis

from app.core.actor import Actor
from app.core.config import AppConfig
from app.core.constants import (
    CUSTOMER_NOTIFICATION_BUY_CALLBACK,
    CUSTOMER_NOTIFICATION_CLOSE_CALLBACK,
    CUSTOMER_NOTIFICATION_RENEW_PREFIX,
    REDIS_KEY_PREFIX,
    TTL_1D,
    TTL_7D,
)
from app.core.db.uow import UnitOfWork
from app.core.enums import PaymentOutcome, PurchaseChannel
from app.core.exceptions import NotFoundError, RetryableTaskError
from app.core.ports import BotSignals
from app.core.usecase import UseCase
from app.modules.customer_notifications.dispatch import SendCustomerTelegramDispatch
from app.modules.customer_notifications.dto import NotifyCustomerDto
from app.modules.customer_notifications.metrics import CUSTOMER_NOTIFICATIONS
from app.modules.customer_notifications.routing import CustomerChannel, channels_for
from app.modules.email import SendEmailDispatch, load_email_brand, render_email
from app.modules.notifications import (
    BotTokenSource,
    NotificationRenderer,
    NotificationRendererFactory,
)
from app.modules.settings import SettingsRepository
from app.modules.subscriptions import (
    SubscriptionChangedEvent,
    SubscriptionExpiredAgoEvent,
    SubscriptionExpiredEvent,
    SubscriptionExpiringEvent,
    SubscriptionPurchasedEvent,
    SubscriptionRenewedEvent,
    SubscriptionRepository,
    SubscriptionTrafficLimitedEvent,
    TorrentBlockerReportEvent,
)
from app.modules.transactions import PaidOrderNotFulfilledEvent, TransactionRepository
from app.modules.users import UserDto, UserRepository

# outlives the sweep's retries of one outbox row
_DEDUP_TTL_S: Final[int] = TTL_7D
# a torrent client trips the blocker on every connection; one warning a day is enough
_COOLDOWNS: Final[dict[str, int]] = {TorrentBlockerReportEvent.__name__: TTL_1D}
# a bot order shows these in the bot's own window instead of a Telegram text
_OUTCOMES: Final[dict[str, PaymentOutcome]] = {
    SubscriptionPurchasedEvent.__name__: PaymentOutcome.SUCCEEDED,
    SubscriptionChangedEvent.__name__: PaymentOutcome.SUCCEEDED,
    SubscriptionRenewedEvent.__name__: PaymentOutcome.SUCCEEDED,
    PaidOrderNotFulfilledEvent.__name__: PaymentOutcome.NOT_FULFILLED,
}

# a subscription running out gets a way to pay for more right under the message
_RENEWABLE: Final[frozenset[str]] = frozenset(
    event.__name__
    for event in (
        SubscriptionExpiringEvent,
        SubscriptionExpiredEvent,
        SubscriptionExpiredAgoEvent,
        SubscriptionTrafficLimitedEvent,
    )
)


def _cooldown_key(event_type: str, user_id: int) -> Optional[str]:
    if event_type not in _COOLDOWNS:
        return None
    return f"{REDIS_KEY_PREFIX}customer_cooldown:{event_type}:{user_id}"


class NotifyCustomerUseCase(UseCase[NotifyCustomerDto, None]):
    required_permission = None

    def __init__(
        self,
        user_repository: UserRepository,
        settings_repository: SettingsRepository,
        transaction_repository: TransactionRepository,
        subscription_repository: SubscriptionRepository,
        renderer_factory: NotificationRendererFactory,
        token_source: BotTokenSource,
        bot_signals: BotSignals,
        send_telegram: SendCustomerTelegramDispatch,
        send_email: SendEmailDispatch,
        redis: Redis,
        config: AppConfig,
        uow: UnitOfWork,
    ) -> None:
        self._user_repository = user_repository
        self._settings_repository = settings_repository
        self._transaction_repository = transaction_repository
        self._subscription_repository = subscription_repository
        self._renderer_factory = renderer_factory
        self._token_source = token_source
        self._bot_signals = bot_signals
        self._send_telegram = send_telegram
        self._send_email = send_email
        self._redis = redis
        self._config = config
        self._uow = uow

    async def _execute(self, actor: Actor, data: NotifyCustomerDto) -> None:
        # the outbox row is already processed, so only a retry can save a failed run;
        # channels sent earlier are skipped by the dedup key
        try:
            await self._notify(data)
        except Exception as error:
            raise RetryableTaskError(str(error)) from error

    async def _notify(self, data: NotifyCustomerDto) -> None:
        async with self._uow:
            user = await self._user_repository.find_by_id(data.user_id)
        if user is None or user.is_blocked or user.deleted_at is not None:
            return
        token, _ = await self._token_source.get_bot_token()
        channels = channels_for(
            data.event_type,
            telegram_id=user.telegram_id if token and not user.is_bot_blocked else None,
            # a mailbox that refused us for good is skipped until the address is proven again
            email=user.email if user.email_undeliverable_at is None else None,
        )
        if not channels:
            logger.info(f"No channel to notify {user.log} about {data.event_type}")
            return
        renderer = await self._renderer_factory.build()
        title, body = renderer.render(user.language, f"Customer{data.event_type}", data.args)
        if not body:
            logger.error(f"No customer notification text for {data.event_type}")
            return
        # set only once there is something to send: a failure above must leave
        # the retry free to deliver, and nothing sent must not silence the next one
        # a requeue after Telegram refused: the first run already took the cooldown slot
        cooldown_key = None if data.telegram_refused else _cooldown_key(data.event_type, user.id)
        if cooldown_key is not None and not await self._redis.set(
            cooldown_key, "1", nx=True, ex=_COOLDOWNS[data.event_type]
        ):
            return
        first_error: Optional[Exception] = None
        for channel in channels:
            key = f"{REDIS_KEY_PREFIX}customer_notified:{data.outbox_id}:{channel}"
            if not await self._redis.set(key, "1", nx=True, ex=_DEDUP_TTL_S):
                continue
            try:
                result = await self._deliver(data, channel, user, renderer, title, body)
            except Exception as error:
                # a lost mark would silence this channel for the whole TTL
                await self._redis.delete(key)
                first_error = first_error or error
                continue
            CUSTOMER_NOTIFICATIONS.labels(channel=channel.value, result=result).inc()
        if first_error is not None:
            # the retry must not find its own cooldown and give up
            if cooldown_key is not None:
                await self._redis.delete(cooldown_key)
            raise first_error

    async def _deliver(
        self,
        data: NotifyCustomerDto,
        channel: CustomerChannel,
        user: UserDto,
        renderer: NotificationRenderer,
        title: str,
        body: str,
    ) -> str:
        if channel is CustomerChannel.TELEGRAM and await self._show_window(data, user):
            return "window"
        await self._queue(data, channel, user, renderer, title, body)
        return "queued"

    async def _show_window(self, data: NotifyCustomerDto, user: UserDto) -> bool:
        outcome = _OUTCOMES.get(data.event_type)
        if data.payment_key is None or outcome is None or user.telegram_id is None:
            return False
        async with self._uow:
            order = await self._transaction_repository.find_by_idempotency_key(data.payment_key)
        if order is None or order.channel is not PurchaseChannel.BOT:
            return False
        # no bot process listening: the text is the fallback
        return await self._bot_signals.payment_outcome(user.telegram_id, order.id, outcome) > 0

    async def _queue(
        self,
        data: NotifyCustomerDto,
        channel: CustomerChannel,
        user: UserDto,
        renderer: NotificationRenderer,
        title: str,
        body: str,
    ) -> None:
        if channel is CustomerChannel.TELEGRAM:
            await self._send_telegram.kiq(
                user_id=user.id,
                text=f"{title}\n\n{body}",
                buttons=await self._telegram_buttons(data, user, renderer),
                notification=asdict(data),
            )
            return
        assert user.email is not None
        async with self._uow:
            brand = await load_email_brand(self._settings_repository)
        text, html = render_email(
            brand=brand.brand,
            color=brand.color,
            has_logo=brand.has_logo,
            title=title,
            body=body,
            cabinet_url=self._config.cabinet.url or None,
            button=renderer.text(user.language, "ntf-customer-open-cabinet"),
        )
        await self._send_email.kiq(to=user.email, subject=title, text=text, html=html)

    async def _telegram_buttons(
        self, data: NotifyCustomerDto, user: UserDto, renderer: NotificationRenderer
    ) -> list[dict[str, str]]:
        buttons = []
        if data.event_type in _RENEWABLE and data.subscription_id is not None:
            # a trial isn't renewed: a purchase replaces it and keeps its link
            if await self._is_trial(data.subscription_id):
                buttons.append(("ntf-customer-button-buy", CUSTOMER_NOTIFICATION_BUY_CALLBACK))
            else:
                buttons.append(
                    (
                        "ntf-customer-button-renew",
                        f"{CUSTOMER_NOTIFICATION_RENEW_PREFIX}{data.subscription_id}",
                    )
                )
        buttons.append(("ntf-customer-button-close", CUSTOMER_NOTIFICATION_CLOSE_CALLBACK))
        # Telegram refuses the whole message over one empty label
        return [
            {"text": text, "callback_data": callback_data}
            for key, callback_data in buttons
            if (text := renderer.text(user.language, key))
        ]

    async def _is_trial(self, subscription_id: int) -> bool:
        async with self._uow:
            try:
                subscription = await self._subscription_repository.get_by_id(subscription_id)
            except NotFoundError:
                return False
        return subscription.is_trial
