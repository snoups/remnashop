from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.promocodes.dto import ListPromocodesDto, PromocodeDto
from app.modules.promocodes.repository import PromocodeRepository


class ListPromocodesUseCase(UseCase[ListPromocodesDto, tuple[list[PromocodeDto], int]]):
    required_permission = Permission.PROMOCODES_VIEW

    def __init__(self, promocode_repository: PromocodeRepository, uow: UnitOfWork) -> None:
        self._promocode_repository = promocode_repository
        self._uow = uow

    async def _execute(
        self, actor: Actor, data: ListPromocodesDto
    ) -> tuple[list[PromocodeDto], int]:
        async with self._uow:
            promocodes, total = await self._promocode_repository.list_paginated(data)
            return await self._promocode_repository.with_activations_count(promocodes), total
