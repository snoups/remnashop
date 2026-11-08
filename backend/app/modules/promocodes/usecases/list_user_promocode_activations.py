from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.promocodes.dto import ListUserPromocodeActivationsDto, UserPromocodeActivationDto
from app.modules.promocodes.repository import PromocodeRepository
from app.modules.users import UserRepository, get_visible_target


class ListUserPromocodeActivationsUseCase(
    UseCase[ListUserPromocodeActivationsDto, tuple[list[UserPromocodeActivationDto], int]]
):
    required_permission = Permission.PROMOCODES_ACTIVATIONS_VIEW

    def __init__(
        self,
        promocode_repository: PromocodeRepository,
        user_repository: UserRepository,
        uow: UnitOfWork,
    ) -> None:
        self._promocode_repository = promocode_repository
        self._user_repository = user_repository
        self._uow = uow

    async def _execute(
        self, actor: Actor, data: ListUserPromocodeActivationsDto
    ) -> tuple[list[UserPromocodeActivationDto], int]:
        async with self._uow:
            await get_visible_target(self._user_repository, actor, data.user_id)
            return await self._promocode_repository.list_activations_by_user(
                data.user_id, page=data.page, page_size=data.page_size
            )
