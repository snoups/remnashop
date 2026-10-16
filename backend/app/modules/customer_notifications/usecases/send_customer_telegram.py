from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.exceptions import RetryableTaskError
from app.core.ports import EventPublisher
from app.core.usecase import UseCase
from app.modules.customer_notifications.dto import SendCustomerTelegramDto
from app.modules.customer_notifications.events import BotBlockedByUserEvent
from app.modules.customer_notifications.metrics import CUSTOMER_NOTIFICATIONS
from app.modules.customer_notifications.routing import CustomerChannel
from app.modules.notifications import BotTokenSource, TelegramSendResult, send_telegram_text
from app.modules.users import UserRepository


class SendCustomerTelegramUseCase(UseCase[SendCustomerTelegramDto, None]):
    required_permission = None

    def __init__(
        self,
        user_repository: UserRepository,
        token_source: BotTokenSource,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._user_repository = user_repository
        self._token_source = token_source
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: SendCustomerTelegramDto) -> None:
        token, proxy = await self._token_source.get_bot_token()
        if token is None:
            logger.warning("Bot is not configured, customer Telegram message was not sent")
            return
        async with self._uow:
            user = await self._user_repository.find_by_id(data.user_id)
        if (
            user is None
            or user.telegram_id is None
            or user.is_blocked
            or user.deleted_at is not None
        ):
            return
        result = await send_telegram_text(token, proxy, user.telegram_id, data.text)
        CUSTOMER_NOTIFICATIONS.labels(
            channel=CustomerChannel.TELEGRAM.value, result=result.value.lower()
        ).inc()
        if result is TelegramSendResult.FORBIDDEN:
            logger.info(f"User {user.id} cannot receive bot messages")
            async with self._uow:
                await self._event_publisher.publish(BotBlockedByUserEvent(user_id=user.id))
        if result is TelegramSendResult.FAILED:
            raise RetryableTaskError(f"Telegram send to user {user.id} failed")
