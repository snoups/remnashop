from loguru import logger

from app.core.db.uow import UnitOfWork
from app.core.enums import PromocodeAvailability
from app.core.exceptions import ValidationError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.promocodes.dto import PromocodeDto, UpdatePromocodeDto
from app.modules.promocodes.repository import PromocodeRepository
from app.modules.users import UserDto


class UpdatePromocodeUseCase(UseCase[UpdatePromocodeDto, PromocodeDto]):
    required_permission = Permission.PROMOCODES_UPDATE

    def __init__(self, promocode_repository: PromocodeRepository, uow: UnitOfWork) -> None:
        self._promocode_repository = promocode_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: UpdatePromocodeDto) -> PromocodeDto:
        if data.availability == PromocodeAvailability.ALLOWED and data.allowed_user_ids == []:
            raise ValidationError("availability=ALLOWED requires at least one allowed user id")

        async with self._uow:
            promo = await self._promocode_repository.update(data)
        logger.info(f"{actor.log} Updated promocode id={data.promocode_id}")
        return promo
