from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.promocodes.dto import ListPromocodeActivatedUsersDto, PromocodeActivatedUserDto
from app.modules.promocodes.repository import PromocodeRepository
from app.modules.users import UserRepository


class ListPromocodeActivatedUsersUseCase(
    UseCase[ListPromocodeActivatedUsersDto, tuple[list[PromocodeActivatedUserDto], int]]
):
    required_permission = Permission.PROMOCODES_USERS_VIEW

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
        self, actor: Actor, data: ListPromocodeActivatedUsersDto
    ) -> tuple[list[PromocodeActivatedUserDto], int]:
        async with self._uow:
            # NotFoundError for an unknown id; the router maps it to 404
            await self._promocode_repository.get_by_id(data.promocode_id)
            activations, total = await self._promocode_repository.list_activations_paginated(
                data.promocode_id, page=data.page, page_size=data.page_size
            )
            users_by_id = {
                user.id: user
                for user in await self._user_repository.list_by_ids(
                    [activation.user_id for activation in activations]
                )
            }

        return [
            PromocodeActivatedUserDto(
                activation_id=activation.id,
                user_id=activation.user_id,
                name=users_by_id[activation.user_id].name,
                subscription_id=activation.subscription_id,
                activated_at=activation.activated_at,
            )
            for activation in activations
            if activation.user_id in users_by_id
        ], total
