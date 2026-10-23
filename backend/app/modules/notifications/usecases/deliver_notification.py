from typing import Final, Optional, Union

from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import Role
from app.core.exceptions import RetryableTaskError
from app.core.security.permissions import Permission, PermissionPolicy
from app.core.usecase import UseCase
from app.modules.notifications.dto import (
    PUSH_URL,
    DeliverNotificationDto,
    NotificationChannel,
    NotificationGroup,
    PushMessage,
    channels_for,
    group_of,
)
from app.modules.notifications.render import NotificationRenderer, notification_args
from app.modules.notifications.sources import BotTokenSource, NotificationRendererFactory
from app.modules.notifications.telegram import send_telegram_message
from app.modules.notifications.webpush import WebPushSender
from app.modules.users import UserDto, UserRepository

_RECIPIENT_ROLES: Final[tuple[Role, ...]] = (Role.ADMIN, Role.OWNER)
# push services cap the payload near 4 KB and Telegram a message at 4096 chars;
# a raw backup error can exceed both
MAX_BODY_LENGTH: Final[int] = 1000


def _wanted_channels(
    user: UserDto, group: NotificationGroup, actor_id: Optional[int]
) -> frozenset[NotificationChannel]:
    if user.is_blocked or user.deleted_at is not None or user.id == actor_id:
        return frozenset()
    if not PermissionPolicy.has_permission(user, Permission.NOTIFICATIONS_VIEW):
        return frozenset()
    return channels_for(user, group) - {NotificationChannel.BELL}


def _coalescing_notes(
    renderer: NotificationRenderer, user: UserDto, data: DeliverNotificationDto
) -> str:
    notes = ""
    if data.suppressed:
        count: dict[str, Union[str, int]] = {"count": data.suppressed}
        notes += "\n" + renderer.render_message(user.language, "ntf-suppressed", count)
    if data.sources_merged:
        notes += "\n" + renderer.render_message(user.language, "ntf-sources-merged", {})
    return notes


class DeliverNotificationUseCase(UseCase[DeliverNotificationDto, None]):
    required_permission = None

    def __init__(
        self,
        user_repository: UserRepository,
        uow: UnitOfWork,
        push_sender: WebPushSender,
        renderer_factory: NotificationRendererFactory,
        bot_token_source: BotTokenSource,
    ) -> None:
        self._user_repository = user_repository
        self._uow = uow
        self._push_sender = push_sender
        self._renderer_factory = renderer_factory
        self._bot_token_source = bot_token_source

    async def _execute(self, actor: Actor, data: DeliverNotificationDto) -> None:
        group = group_of(data.event_type)
        if group is None:
            return
        try:
            async with self._uow:
                users = await self._user_repository.list_by_roles(_RECIPIENT_ROLES)
            targets = [(u, _wanted_channels(u, group, data.actor_id)) for u in users]
            targets = [(u, channels) for u, channels in targets if channels]
            if not targets:
                return
            renderer = await self._renderer_factory.build()
            token, proxy = await self._bot_token_source.get_bot_token()
        except Exception as error:
            # nothing sent yet, so running the whole task again is safe
            raise RetryableTaskError(f"Notification for {data.event_type} not sent") from error
        args = notification_args(data.payload, data.ip_address)

        for user, channels in targets:
            title, body = renderer.render(user.language, data.event_type, args)
            if len(body) > MAX_BODY_LENGTH:
                body = body[: MAX_BODY_LENGTH - 1] + "…"
            body += _coalescing_notes(renderer, user, data)
            if NotificationChannel.PUSH in channels:
                try:
                    await self._push_sender.send(
                        user.id,
                        PushMessage(title=title, body=body, url=PUSH_URL, tag=data.event_type),
                    )
                except Exception:
                    logger.exception(f"Push notification for {user.log} failed")
            if NotificationChannel.TELEGRAM in channels and token and user.telegram_id:
                try:
                    await send_telegram_message(
                        token, proxy, user.telegram_id, f"{title}\n\n{body}"
                    )
                except Exception:
                    logger.exception(f"Telegram notification for {user.log} failed")
