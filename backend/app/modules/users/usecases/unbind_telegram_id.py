from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import OAuthProvider
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.users.dto import UnbindTelegramDto, UserListItemDto
from app.modules.users.events import TelegramIdUnboundEvent
from app.modules.users.listing import detail_roles
from app.modules.users.ports import SignInMethodCheck
from app.modules.users.repository import UserRepository
from app.modules.users.visibility import assert_manageable, get_visible_target


class UnbindTelegramIdUseCase(UseCase[UnbindTelegramDto, UserListItemDto]):
    required_permission = Permission.USERS_TELEGRAM_UNBIND

    def __init__(
        self,
        user_repository: UserRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
        sign_in_method_check: SignInMethodCheck,
    ) -> None:
        self._user_repository = user_repository
        self._uow = uow
        self._event_publisher = event_publisher
        self._sign_in_method_check = sign_in_method_check

    async def _execute(self, actor: Actor, data: UnbindTelegramDto) -> UserListItemDto:
        async with self._uow:
            target = await get_visible_target(
                self._user_repository, actor, data.user_id, for_update=True
            )
            assert_manageable(actor, target, allow_self=True)
            if target.telegram_id is None:
                return await self._user_repository.get_list_item(
                    target.id, detail_roles(actor, target.id)
                )
            updated = await self._user_repository.clear_telegram_id(target.id)
            if target.is_privileged:
                # raising here rolls the unbinding back
                await self._sign_in_method_check.assert_one_left(
                    target, without_provider=OAuthProvider.TELEGRAM
                )
            await self._event_publisher.publish(
                TelegramIdUnboundEvent(
                    actor=actor,
                    target=updated,
                    previous_telegram_id=target.telegram_id,
                    ip_address=data.client_ip,
                )
            )
            return await self._user_repository.get_list_item(
                updated.id, detail_roles(actor, updated.id)
            )
