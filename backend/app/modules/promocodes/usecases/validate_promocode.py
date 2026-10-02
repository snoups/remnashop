from app.core.db.uow import UnitOfWork
from app.core.enums import PromocodeRewardType
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.plans import PlanRepository
from app.modules.promocodes.availability import (
    assert_available_to,
    assert_subscription_reward_grantable,
    get_usable_promocode,
)
from app.modules.promocodes.dto import PromocodeDto, ValidatePromocodeDto
from app.modules.promocodes.repository import PromocodeRepository
from app.modules.subscriptions import PurchaseEligibility, SubscriptionRepository
from app.modules.users import UserDto


class ValidatePromocodeUseCase(UseCase[ValidatePromocodeDto, PromocodeDto, UserDto]):
    required_permission = Permission.PUBLIC

    def __init__(
        self,
        promocode_repository: PromocodeRepository,
        subscription_repository: SubscriptionRepository,
        plan_repository: PlanRepository,
        eligibility: PurchaseEligibility,
        uow: UnitOfWork,
    ) -> None:
        self._promocode_repository = promocode_repository
        self._subscription_repository = subscription_repository
        self._plan_repository = plan_repository
        self._eligibility = eligibility
        self._uow = uow

    async def _execute(self, actor: UserDto, data: ValidatePromocodeDto) -> PromocodeDto:
        async with self._uow:
            promo = await get_usable_promocode(self._promocode_repository, data.code)

            if promo.max_activations is not None:
                count = await self._promocode_repository.get_activations_count(promo.id)
                if count >= promo.max_activations:
                    raise ValidationError(
                        f"Promocode '{promo.code}' activation limit reached",
                        code=ErrorCode.PROMOCODE_LIMIT_REACHED,
                    )

            if not promo.is_reusable:
                existing = await self._promocode_repository.get_activation_by_user(
                    promo.id, actor.id
                )
                if existing is not None:
                    raise ValidationError(
                        f"Promocode '{promo.code}' already activated by this user",
                        code=ErrorCode.PROMOCODE_ALREADY_ACTIVATED,
                    )

        await assert_available_to(promo, actor, self._subscription_repository)
        if promo.reward_type is PromocodeRewardType.SUBSCRIPTION:
            await assert_subscription_reward_grantable(
                promo,
                actor,
                self._plan_repository,
                self._eligibility,
            )
        return promo
