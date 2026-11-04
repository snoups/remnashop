from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.blacklist import BlacklistRepository
from app.modules.users.dto import BindTelegramDto, UserListItemDto
from app.modules.users.events import TelegramIdBoundEvent
from app.modules.users.listing import detail_roles
from app.modules.users.repository import UserRepository
from app.modules.users.visibility import assert_manageable, get_visible_target


class BindTelegramIdUseCase(UseCase[BindTelegramDto, UserListItemDto]):
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

    async def _execute(self, actor: Actor, data: BindTelegramDto) -> UserListItemDto:
        async with self._uow:
            target = await get_visible_target(
                self._user_repository, actor, data.user_id, for_update=True
            )
            assert_manageable(actor, target, allow_self=True)
            if target.telegram_id == data.telegram_id:
                return await self._user_repository.get_list_item(target.id, detail_roles(actor))
            if await self._blacklist_repository.is_blacklisted_telegram_id(data.telegram_id):
                raise ValidationError(
                    "Telegram ID is blacklisted", code=ErrorCode.TELEGRAM_ID_BLACKLISTED
                )
            updated = await self._user_repository.set_telegram_id(target.id, data.telegram_id)
            await self._event_publisher.publish(
                TelegramIdBoundEvent(
                    actor=actor,
                    target=updated,
                    previous_telegram_id=target.telegram_id,
                    ip_address=data.client_ip,
                )
            )
            return await self._user_repository.get_list_item(updated.id, detail_roles(actor))
