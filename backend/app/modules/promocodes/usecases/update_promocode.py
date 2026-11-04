from dataclasses import replace
from typing import Final

from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import PromocodeAvailability
from app.core.error_codes import ErrorCode
from app.core.events import changed_fields
from app.core.exceptions import ValidationError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.plans import PlanRepository
from app.modules.promocodes.dto import PromocodeDto, UpdatePromocodeDto
from app.modules.promocodes.events import PromocodeChangedEvent
from app.modules.promocodes.plan_limits import check_allowed_plans
from app.modules.promocodes.repository import PromocodeRepository

_EDITABLE_FIELDS: Final[tuple[str, ...]] = (
    "is_active",
    "availability",
    "allowed_user_ids",
    "allowed_plan_ids",
    "expires_at",
    "max_activations",
    "is_reusable",
)


class UpdatePromocodeUseCase(UseCase[UpdatePromocodeDto, PromocodeDto]):
    required_permission = Permission.PROMOCODES_UPDATE

    def __init__(
        self,
        promocode_repository: PromocodeRepository,
        plan_repository: PlanRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._promocode_repository = promocode_repository
        self._plan_repository = plan_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: UpdatePromocodeDto) -> PromocodeDto:
        # validates the merged result: a PATCH with only allowed_user_ids=[]
        # leaves availability alone, and checking just the patch would leave an
        # ALLOWED promocode active but redeemable by nobody
        async with self._uow:
            current = await self._promocode_repository.get_by_id(data.promocode_id)
            availability = data.availability or current.availability
            allowed_user_ids = (
                data.allowed_user_ids
                if data.allowed_user_ids is not None
                else current.allowed_user_ids
            )
            if availability == PromocodeAvailability.ALLOWED and not allowed_user_ids:
                raise ValidationError(
                    "availability=ALLOWED requires at least one allowed user id",
                    code=ErrorCode.ALLOWED_LIST_EMPTY,
                )
            if data.allowed_plan_ids is not None:
                # the reward type is fixed at creation
                data = replace(
                    data,
                    allowed_plan_ids=await check_allowed_plans(
                        current.reward_type,
                        data.allowed_plan_ids,
                        self._plan_repository,
                        already_stored=current.allowed_plan_ids,
                    ),
                )

            promo = await self._promocode_repository.update(data)
            (promo,) = await self._promocode_repository.with_activations_count([promo])
            await self._event_publisher.publish(
                PromocodeChangedEvent(
                    actor=actor,
                    action="update",
                    promocode_id=data.promocode_id,
                    code=promo.code,
                    changed_fields=changed_fields(current, promo, _EDITABLE_FIELDS),
                    ip_address=data.client_ip,
                )
            )
        logger.info(f"{actor.log} Updated promocode '{data.promocode_id}'")
        return promo
