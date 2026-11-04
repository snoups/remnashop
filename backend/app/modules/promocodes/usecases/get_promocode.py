from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.promocodes.dto import PromocodeDto
from app.modules.promocodes.repository import PromocodeRepository


class GetPromocodeUseCase(UseCase[int, PromocodeDto]):
    required_permission = Permission.PROMOCODES_DETAIL_VIEW

    def __init__(self, promocode_repository: PromocodeRepository, uow: UnitOfWork) -> None:
        self._promocode_repository = promocode_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: int) -> PromocodeDto:
        async with self._uow:
            promo = await self._promocode_repository.get_by_id(data)
            (promo,) = await self._promocode_repository.with_activations_count([promo])
            return promo
