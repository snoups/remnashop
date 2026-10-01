from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.promocodes.dto import UserPromocodeActivationDto
from app.modules.promocodes.repository import PromocodeRepository


class ListUserPromocodeActivationsUseCase(UseCase[int, list[UserPromocodeActivationDto]]):
    required_permission = Permission.PROMOCODES_ACTIVATIONS_VIEW

    def __init__(self, promocode_repository: PromocodeRepository, uow: UnitOfWork) -> None:
        self._promocode_repository = promocode_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: int) -> list[UserPromocodeActivationDto]:
        async with self._uow:
            return await self._promocode_repository.list_activations_by_user(data)
