from loguru import logger

from app.core.db.uow import UnitOfWork
from app.core.enums import PromocodeAvailability
from app.core.exceptions import ValidationError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.promocodes.dto import PromocodeDto, UpdatePromocodeDto
from app.modules.promocodes.events import PromocodeChangedEvent
from app.modules.promocodes.repository import PromocodeRepository
from app.modules.users import UserDto


class UpdatePromocodeUseCase(UseCase[UpdatePromocodeDto, PromocodeDto]):
    required_permission = Permission.PROMOCODES_UPDATE

    def __init__(
        self,
        promocode_repository: PromocodeRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._promocode_repository = promocode_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: UserDto, data: UpdatePromocodeDto) -> PromocodeDto:
        # Validate the merged result, not the patch on its own: a PATCH
        # carrying only allowed_user_ids=[] leaves availability untouched, so
        # checking the patch alone lets an already-ALLOWED promocode end up
        # with an empty allowlist -- still active, but redeemable by nobody.
        async with self._uow:
            current = await self._promocode_repository.get_by_id(data.promocode_id)
            availability = data.availability or current.availability
            allowed_user_ids = (
                data.allowed_user_ids
                if data.allowed_user_ids is not None
                else current.allowed_user_ids
            )
            if availability == PromocodeAvailability.ALLOWED and not allowed_user_ids:
                raise ValidationError("availability=ALLOWED requires at least one allowed user id")

        async with self._uow:
            promo = await self._promocode_repository.update(data)
            await self._event_publisher.publish(
                PromocodeChangedEvent(user=actor, action="update", promocode_id=data.promocode_id)
            )
        logger.info(f"{actor.log} Updated promocode id={data.promocode_id}")
        return promo
