from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.notifications.dto import (
    PUSH_URL,
    PushMessage,
)
from app.modules.notifications.render import TEST_EVENT_TYPE
from app.modules.notifications.repository import NotificationRepository
from app.modules.notifications.sources import NotificationRendererFactory
from app.modules.notifications.webpush import WebPushSender
from app.modules.users import UserDto


class SendTestPushUseCase(UseCase[None, int, UserDto]):
    required_permission = Permission.OWN_ACCOUNT_MANAGE

    def __init__(
        self,
        notification_repository: NotificationRepository,
        uow: UnitOfWork,
        sender: WebPushSender,
        renderer_factory: NotificationRendererFactory,
    ) -> None:
        self._notification_repository = notification_repository
        self._uow = uow
        self._sender = sender
        self._renderer_factory = renderer_factory

    async def _execute(self, actor: UserDto, data: None) -> int:
        async with self._uow:
            if not await self._notification_repository.is_push_configured():
                raise ValidationError(
                    "Web push is not configured", code=ErrorCode.PUSH_NOT_CONFIGURED
                )
            if not await self._notification_repository.list_push_subscriptions(actor.id):
                raise ValidationError("No push subscriptions", code=ErrorCode.PUSH_NO_SUBSCRIPTIONS)
        renderer = await self._renderer_factory.build()
        title, body = renderer.render(actor.language, TEST_EVENT_TYPE, {})
        return await self._sender.send(
            actor.id, PushMessage(title=title, body=body, url=PUSH_URL, tag=TEST_EVENT_TYPE)
        )
