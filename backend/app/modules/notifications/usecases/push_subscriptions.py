from typing import Final, Optional
from urllib.parse import urlsplit

from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError, ValidationError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.notifications.dto import (
    PUSH_URL,
    PushMessage,
    PushSubscriptionDto,
    SubscribePushDto,
)
from app.modules.notifications.render import TEST_EVENT_TYPE
from app.modules.notifications.repository import NotificationRepository
from app.modules.notifications.sources import NotificationRendererFactory
from app.modules.notifications.webpush import WebPushSender
from app.modules.users import UserDto

# Browsers' push services, matched by host rather than by resolving it: behind a
# fake-IP DNS (proxy TUN modes, 198.18.0.0/15) they resolve to "private" addresses
_PUSH_SERVICE_HOSTS: Final[frozenset[str]] = frozenset({"fcm.googleapis.com"})
_PUSH_SERVICE_SUFFIXES: Final[tuple[str, ...]] = (
    ".notify.windows.com",
    ".push.services.mozilla.com",
    ".push.apple.com",
)


def _assert_push_service(endpoint: str) -> None:
    # the worker POSTs to this URL; anything else would let staff aim it at internal hosts
    parsed = urlsplit(endpoint)
    host = (parsed.hostname or "").lower()
    if (
        parsed.scheme == "https"
        and parsed.port in (None, 443)
        and (host in _PUSH_SERVICE_HOSTS or host.endswith(_PUSH_SERVICE_SUFFIXES))
    ):
        return
    raise ValidationError(
        f"Not a browser push service: {host or endpoint}",
        code=ErrorCode.PUSH_ENDPOINT_NOT_ALLOWED,
    )


class GetPushPublicKeyUseCase(UseCase[None, Optional[str], UserDto]):
    required_permission = Permission.OWN_ACCOUNT_MANAGE

    def __init__(self, notification_repository: NotificationRepository, uow: UnitOfWork) -> None:
        self._notification_repository = notification_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: None) -> Optional[str]:
        async with self._uow:
            return (await self._notification_repository.get_settings()).vapid_public_key


class ListPushSubscriptionsUseCase(UseCase[None, list[PushSubscriptionDto], UserDto]):
    required_permission = Permission.OWN_ACCOUNT_MANAGE

    def __init__(self, notification_repository: NotificationRepository, uow: UnitOfWork) -> None:
        self._notification_repository = notification_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: None) -> list[PushSubscriptionDto]:
        async with self._uow:
            return await self._notification_repository.list_push_subscriptions(actor.id)


class SubscribePushUseCase(UseCase[SubscribePushDto, tuple[PushSubscriptionDto, bool], UserDto]):
    required_permission = Permission.OWN_ACCOUNT_MANAGE

    def __init__(self, notification_repository: NotificationRepository, uow: UnitOfWork) -> None:
        self._notification_repository = notification_repository
        self._uow = uow

    async def _execute(
        self, actor: UserDto, data: SubscribePushDto
    ) -> tuple[PushSubscriptionDto, bool]:
        _assert_push_service(data.endpoint)
        async with self._uow:
            return await self._notification_repository.upsert_push_subscription(
                user_id=actor.id,
                session_id=data.session_id,
                endpoint=data.endpoint,
                p256dh=data.p256dh,
                auth=data.auth,
                user_agent=data.user_agent,
            )


class DeletePushSubscriptionUseCase(UseCase[int, None, UserDto]):
    required_permission = Permission.OWN_ACCOUNT_MANAGE

    def __init__(self, notification_repository: NotificationRepository, uow: UnitOfWork) -> None:
        self._notification_repository = notification_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: int) -> None:
        async with self._uow:
            if not await self._notification_repository.delete_push_subscription(data, actor.id):
                raise NotFoundError(
                    f"Push subscription '{data}' not found",
                    code=ErrorCode.PUSH_SUBSCRIPTION_NOT_FOUND,
                )


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
