from typing import Final
from urllib.parse import urlsplit

from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.notifications.dto import (
    PushSubscriptionDto,
    SubscribePushDto,
)
from app.modules.notifications.repository import NotificationRepository
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
