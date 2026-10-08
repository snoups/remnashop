from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission, PermissionPolicy
from app.core.usecase import UseCase
from app.modules.blacklist import BlacklistRepository
from app.modules.users.dto import BindTelegramDto, UserDto
from app.modules.users.events import TelegramIdBoundEvent
from app.modules.users.repository import UserRepository


class BindTelegramIdUseCase(UseCase[BindTelegramDto, UserDto]):
    required_permission = Permission.USERS_TELEGRAM_BIND

    def __init__(
        self,
        user_repository: UserRepository,
        blacklist_repository: BlacklistRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._user_repository = user_repository
        self._blacklist_repository = blacklist_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: BindTelegramDto) -> UserDto:
        async with self._uow:
            target = await self._user_repository.get_for_update(data.user_id)
            if target is None or target.deleted_at is not None:
                raise NotFoundError("User not found", code=ErrorCode.USER_NOT_FOUND)
            if target.is_privileged and not (
                PermissionPolicy.has_permission(actor, Permission.ADMINS_MANAGE)
                and (target.id == actor.id or PermissionPolicy.can_manage(actor, target))
            ):
                raise PermissionDeniedError
            if target.telegram_id == data.telegram_id:
                return target
            if await self._blacklist_repository.is_blacklisted_telegram_id(data.telegram_id):
                raise ValidationError(
                    "Telegram ID is blacklisted", code=ErrorCode.TELEGRAM_ID_BLACKLISTED
                )
            updated = await self._user_repository.set_telegram_id(target.id, data.telegram_id)
            await self._event_publisher.publish(
                TelegramIdBoundEvent(
                    actor=actor, target=updated, previous_telegram_id=target.telegram_id
                )
            )
        return updated
