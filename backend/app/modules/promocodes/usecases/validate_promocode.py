from dataclasses import dataclass

from app.core.enums import PromocodeRewardType
from app.core.exceptions import NotFoundError, ValidationError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.plans import PlanRepository
from app.modules.promocodes.availability import (
    assert_available_to,
    assert_subscription_reward_grantable,
)
from app.modules.promocodes.dto import PromocodeDto
from app.modules.promocodes.repository import PromocodeRepository
from app.modules.referrals import ReferralRepository
from app.modules.settings import SettingsRepository
from app.modules.subscriptions import SubscriptionRepository
from app.modules.users import UserDto


@dataclass(frozen=True, kw_only=True)
class ValidatePromocodeDto:
    code: str


class ValidatePromocodeUseCase(UseCase[ValidatePromocodeDto, PromocodeDto]):
    required_permission = Permission.PUBLIC

    def __init__(
        self,
        promocode_repository: PromocodeRepository,
        subscription_repository: SubscriptionRepository,
        referral_repository: ReferralRepository,
        plan_repository: PlanRepository,
        settings_repository: SettingsRepository,
    ) -> None:
        self._promocode_repository = promocode_repository
        self._subscription_repository = subscription_repository
        self._referral_repository = referral_repository
        self._plan_repository = plan_repository
        self._settings_repository = settings_repository

    async def _execute(self, actor: UserDto, data: ValidatePromocodeDto) -> PromocodeDto:
        code = data.code.strip().upper()
        promo = await self._promocode_repository.get_by_code(code)
        if promo is None or not promo.is_active:
            raise NotFoundError(f"Promocode '{code}' not found")

        if promo.expires_at is not None and datetime_now() > promo.expires_at:
            raise ValidationError(f"Promocode '{code}' has expired")

        if promo.max_activations is not None:
            count = await self._promocode_repository.get_activations_count(promo.id)
            if count >= promo.max_activations:
                raise ValidationError(f"Promocode '{code}' activation limit reached")

        if not promo.is_reusable:
            existing = await self._promocode_repository.get_activation_by_user(promo.id, actor.id)
            if existing is not None:
                raise ValidationError(f"Promocode '{code}' already activated by this user")

        await assert_available_to(promo, actor, self._subscription_repository)
        if promo.reward_type is PromocodeRewardType.SUBSCRIPTION:
            await assert_subscription_reward_grantable(
                promo,
                actor,
                self._plan_repository,
                self._subscription_repository,
                self._referral_repository,
                self._settings_repository,
            )
        return promo
