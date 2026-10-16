from functools import partial
from typing import Final, Optional

from loguru import logger

from app.core.actor import Actor
from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import BroadcastButtonKind, BroadcastStatus
from app.core.ports import EventPublisher
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.broadcasts.dispatch import DeliverBroadcastDispatch, DeliverBroadcastEmailDispatch
from app.modules.broadcasts.events import BroadcastStartedEvent
from app.modules.broadcasts.render import BroadcastRenderer, outgoing_media
from app.modules.broadcasts.repository import BroadcastRepository
from app.modules.broadcasts.telegram_api import (
    SendOutcome,
    TelegramClientFactory,
    get_bot_username,
    send_broadcast_message,
)
from app.modules.broadcasts.validation import promocode_is_usable
from app.modules.promocodes import PromocodeRepository
from app.modules.settings import SettingsRepository

_DEEP_LINK_BUTTONS: Final[frozenset[BroadcastButtonKind]] = frozenset(
    {BroadcastButtonKind.PROMOCODE, BroadcastButtonKind.MENU}
)


class StartBroadcastUseCase(UseCase[int, None]):
    required_permission = None

    def __init__(
        self,
        broadcast_repository: BroadcastRepository,
        settings_repository: SettingsRepository,
        promocode_repository: PromocodeRepository,
        client_factory: TelegramClientFactory,
        config: AppConfig,
        deliver_dispatch: DeliverBroadcastDispatch,
        email_dispatch: DeliverBroadcastEmailDispatch,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._broadcast_repository = broadcast_repository
        self._settings_repository = settings_repository
        self._promocode_repository = promocode_repository
        self._client_factory = client_factory
        self._config = config
        self._deliver_dispatch = deliver_dispatch
        self._email_dispatch = email_dispatch
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: int) -> None:
        now = datetime_now()
        async with self._uow:
            # serializes concurrent starts past the has_sending() check below
            await self._broadcast_repository.lock_starts()
            broadcast = await self._broadcast_repository.try_lock(data)
            if broadcast is None or broadcast.status is not BroadcastStatus.SCHEDULED:
                return
            # one broadcast at a time; the next due one is picked up by the tick
            if await self._broadcast_repository.has_sending():
                return
            dropped = False
            if (
                broadcast.promocode_id is not None
                and await promocode_is_usable(self._promocode_repository, broadcast.promocode_id)
                is None
            ):
                await self._broadcast_repository.update_fields(data, promocode_id=None)
                dropped = True
            total = broadcast.total_count
            if broadcast.started_at is None:
                total = await self._broadcast_repository.materialize(
                    data,
                    broadcast.audience,
                    broadcast.category,
                    broadcast.delivery,
                    broadcast.email_fallback,
                    now,
                )
            await self._broadcast_repository.update_fields(
                data,
                status=BroadcastStatus.SENDING,
                total_count=total,
                started_at=broadcast.started_at or now,
            )
            await self._event_publisher.publish(
                BroadcastStartedEvent(broadcast_id=data, total=total, promocode_dropped=dropped)
            )
            if broadcast.sends_telegram:
                await self._uow.after_commit(partial(self._deliver_dispatch.kiq, broadcast_id=data))
            if broadcast.sends_email:
                await self._uow.after_commit(partial(self._email_dispatch.kiq, broadcast_id=data))
        logger.info(f"Broadcast '{data}' started for {total} recipients")
        # a retry restarts with started_at set, so the channel gets one post only
        if broadcast.post_to_channel and broadcast.started_at is None:
            await self._post_to_channel(data)

    async def _post_to_channel(self, broadcast_id: int) -> None:
        async with self._uow:
            broadcast = await self._broadcast_repository.get_by_id(broadcast_id)
            bot = await self._settings_repository.get_bot_settings()
            requirements = await self._settings_repository.get_bot_requirements()
            code = (
                await promocode_is_usable(self._promocode_repository, broadcast.promocode_id)
                if broadcast.promocode_id is not None
                else None
            )
        channel_id = requirements.channel_id
        if bot.token is None or channel_id is None:
            logger.warning(f"Broadcast '{broadcast_id}' channel post skipped: bot not configured")
            return
        renderer = BroadcastRenderer(broadcast, promocode_code=code, unsubscribe_labels={})
        token = bot.token.get_secret_value()
        try:
            async with self._client_factory.open(bot.proxy) as client:
                username: Optional[str] = None
                if any(b.kind in _DEEP_LINK_BUTTONS for b in broadcast.buttons):
                    username = await get_bot_username(client, token)
                    if username is None:
                        logger.warning(
                            f"Broadcast '{broadcast_id}' channel post: bot username unknown, "
                            "promocode and menu buttons omitted"
                        )
                message = renderer.render_channel(username)
                result = await send_broadcast_message(
                    client,
                    token,
                    channel_id,
                    message.text,
                    message.reply_markup,
                    outgoing_media(self._config.media_dir, broadcast),
                )
        except FileNotFoundError:
            logger.warning(f"Broadcast '{broadcast_id}' channel post skipped: media file missing")
            return
        if result.outcome is not SendOutcome.SENT:
            logger.warning(f"Broadcast '{broadcast_id}' channel post refused: {result.error}")
            return
        values: dict[str, object] = {
            "channel_chat_id": channel_id,
            "channel_message_id": result.message_id,
        }
        if result.file_id:
            values["media_file_id"] = result.file_id
        async with self._uow:
            await self._broadcast_repository.update_fields(broadcast_id, **values)
