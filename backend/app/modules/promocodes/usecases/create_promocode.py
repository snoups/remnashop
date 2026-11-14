from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import PromocodeAvailability, PromocodeRewardType
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.plans import AddOnRepository, PlanRepository
from app.modules.promocodes.dto import CreatePromocodeDto, PromocodeDto
from app.modules.promocodes.events import PromocodeChangedEvent
from app.modules.promocodes.plan_limits import check_allowed_plans
from app.modules.promocodes.repository import PromocodeRepository


class CreatePromocodeUseCase(UseCase[CreatePromocodeDto, PromocodeDto]):
    required_permission = Permission.PROMOCODES_CREATE

    def __init__(
        self,
        promocode_repository: PromocodeRepository,
        addon_repository: AddOnRepository,
        plan_repository: PlanRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._promocode_repository = promocode_repository
        self._addon_repository = addon_repository
        self._plan_repository = plan_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: CreatePromocodeDto) -> PromocodeDto:
        if data.availability == PromocodeAvailability.ALLOWED and not data.allowed_user_ids:
            raise ValidationError(
                "availability=ALLOWED requires at least one allowed user id",
                code=ErrorCode.ALLOWED_LIST_EMPTY,
            )

        async with self._uow:
            await self._validate_reward(data)
            await check_allowed_plans(
                data.reward_type, data.allowed_plan_ids, self._plan_repository
            )
            promo = await self._promocode_repository.create(data)
            await self._event_publisher.publish(
                PromocodeChangedEvent(
                    actor=actor,
                    action="create",
                    promocode_id=promo.id,
                    code=promo.code,
                    ip_address=data.client_ip,
                )
            )
        logger.info(f"{actor.log} Created promocode '{promo.code}'")
        return promo

    async def _validate_subscription_reward(self, data: CreatePromocodeDto) -> None:
        if (
            data.reward_plan_id is None
            or data.reward_duration_days is None
            # 0 grants an unlimited subscription
            or data.reward_duration_days < 0
        ):
            raise ValidationError(
                "reward_plan_id and a reward_duration_days of 0 or more are required "
                "for reward type 'SUBSCRIPTION'",
                code=ErrorCode.PROMOCODE_REWARD_PLAN_REQUIRED,
            )
        plan = await self._plan_repository.get_by_id(data.reward_plan_id)
        if plan.is_trial and data.reward_duration_days == 0:
            raise ValidationError(
                "A trial plan can't be unlimited",
                code=ErrorCode.PLAN_TRIAL_UNLIMITED_DURATION,
            )

    async def _validate_reward(self, data: CreatePromocodeDto) -> None:
        if data.reward_type is PromocodeRewardType.DURATION:
            if data.reward is None or data.reward < 1:
                raise ValidationError(
                    "reward must be >= 1 for reward type 'DURATION'",
                    code=ErrorCode.PROMOCODE_REWARD_INVALID,
                )
        elif data.reward_type in (PromocodeRewardType.TRAFFIC, PromocodeRewardType.DEVICES):
            if data.reward_addon_id is None:
                raise ValidationError(
                    f"reward_addon_id is required for reward type '{data.reward_type}'",
                    code=ErrorCode.PROMOCODE_REWARD_ADDON_REQUIRED,
                )
            addon = await self._addon_repository.get_by_id(data.reward_addon_id)
            if addon.type.value != data.reward_type.value:
                raise ValidationError(
                    f"AddOn '{addon.id}' has type '{addon.type}', expected '{data.reward_type}'",
                    code=ErrorCode.PROMOCODE_REWARD_ADDON_TYPE_MISMATCH,
                )
        elif data.reward_type is PromocodeRewardType.SUBSCRIPTION:
            await self._validate_subscription_reward(data)
        elif data.reward_type in (
            PromocodeRewardType.PERSONAL_DISCOUNT,
            PromocodeRewardType.PURCHASE_DISCOUNT,
        ):
            # matches ck_users_*_discount_range; out of range fails only after
            # the activation is already claimed
            if data.reward is None or not 1 <= data.reward <= 100:
                raise ValidationError(
                    f"reward must be between 1 and 100 for reward type '{data.reward_type}'",
                    code=ErrorCode.PROMOCODE_REWARD_INVALID,
                )
