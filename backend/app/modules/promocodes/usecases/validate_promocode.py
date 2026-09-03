from dataclasses import dataclass

from app.core.enums import PromocodeAvailability
from app.core.exceptions import NotFoundError, ValidationError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.promocodes.dto import PromocodeDto
from app.modules.promocodes.repository import PromocodeRepository
from app.modules.referrals import ReferralRepository
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
    ) -> None:
        self._promocode_repository = promocode_repository
        self._subscription_repository = subscription_repository
        self._referral_repository = referral_repository

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

        await self._check_availability(actor, promo)
        return promo

    async def _check_availability(self, actor: UserDto, promo: PromocodeDto) -> None:
        if promo.availability is PromocodeAvailability.ALL:
            return
        if promo.availability is PromocodeAvailability.NEW:
            has_sub = await self._subscription_repository.has_any_subscription(
                actor.id, include_trial=False
            )
            if has_sub:
                raise ValidationError(f"Promocode '{promo.code}' is for new users only")
            return
        if promo.availability is PromocodeAvailability.EXISTING:
            has_sub = await self._subscription_repository.has_any_subscription(
                actor.id, include_trial=False
            )
            if not has_sub:
                raise ValidationError(f"Promocode '{promo.code}' is for existing users only")
            return
        if promo.availability is PromocodeAvailability.ALLOWED:
            if actor.id not in promo.allowed_user_ids:
                raise ValidationError(f"Promocode '{promo.code}' is not available to this user")
            return
        raise ValidationError(f"Promocode '{promo.code}' is not available to this user")
