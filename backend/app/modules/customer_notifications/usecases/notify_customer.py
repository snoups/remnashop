from typing import Final, Optional

from loguru import logger
from redis.asyncio import Redis

from app.core.actor import Actor
from app.core.config import AppConfig
from app.core.constants import REDIS_KEY_PREFIX, TTL_1D, TTL_7D
from app.core.db.uow import UnitOfWork
from app.core.exceptions import RetryableTaskError
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
from app.modules.subscriptions import TorrentBlockerReportEvent
from app.modules.users import UserDto, UserRepository

# outlives the sweep's retries of one outbox row
_DEDUP_TTL_S: Final[int] = TTL_7D
# a torrent client trips the blocker on every connection; one warning a day is enough
_COOLDOWNS: Final[dict[str, int]] = {TorrentBlockerReportEvent.__name__: TTL_1D}


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
        renderer_factory: NotificationRendererFactory,
        token_source: BotTokenSource,
        send_telegram: SendCustomerTelegramDispatch,
        send_email: SendEmailDispatch,
        redis: Redis,
        config: AppConfig,
        uow: UnitOfWork,
    ) -> None:
        self._user_repository = user_repository
        self._settings_repository = settings_repository
        self._renderer_factory = renderer_factory
        self._token_source = token_source
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
            logger.info(f"No channel to notify user {user.id} about {data.event_type}")
            return
        renderer = await self._renderer_factory.build()
        title, body = renderer.render(user.language, f"Customer{data.event_type}", data.args)
        if not body:
            logger.error(f"No customer notification text for {data.event_type}")
            return
        # set only once there is something to send: a failure above must leave
        # the retry free to deliver, and nothing sent must not silence the next one
        cooldown_key = _cooldown_key(data.event_type, user.id)
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
                await self._queue(channel, user, renderer, title, body)
            except Exception as error:
                # a lost mark would silence this channel for the whole TTL
                await self._redis.delete(key)
                first_error = first_error or error
                continue
            CUSTOMER_NOTIFICATIONS.labels(channel=channel.value, result="queued").inc()
        if first_error is not None:
            # the retry must not find its own cooldown and give up
            if cooldown_key is not None:
                await self._redis.delete(cooldown_key)
            raise first_error

    async def _queue(
        self,
        channel: CustomerChannel,
        user: UserDto,
        renderer: NotificationRenderer,
        title: str,
        body: str,
    ) -> None:
        if channel is CustomerChannel.TELEGRAM:
            await self._send_telegram.kiq(user_id=user.id, text=f"{title}\n\n{body}")
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
