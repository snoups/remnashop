from app.core.enums import PromocodeAvailability
from app.core.exceptions import ValidationError
from app.modules.promocodes.dto import PromocodeDto
from app.modules.subscriptions import SubscriptionRepository
from app.modules.users import UserDto


async def assert_available_to(
    promo: PromocodeDto, actor: UserDto, subscription_repository: SubscriptionRepository
) -> None:
    """Shared by ValidatePromocodeUseCase (the pre-activation preview) and
    ActivatePromocodeUseCase (the real thing) -- the two must agree, or the
    preview says "available" on a code activation then refuses."""
    if promo.availability is PromocodeAvailability.ALL:
        return
    if promo.availability in (PromocodeAvailability.NEW, PromocodeAvailability.EXISTING):
        # "New" = never purchased a non-trial subscription, not "has none
        # active right now" -- matches main's UserDao.has_any_subscription.
        has_sub = await subscription_repository.has_any_subscription(actor.id, include_trial=False)
        if promo.availability is PromocodeAvailability.NEW and has_sub:
            raise ValidationError(f"Promocode '{promo.code}' is for new users only")
        if promo.availability is PromocodeAvailability.EXISTING and not has_sub:
            raise ValidationError(f"Promocode '{promo.code}' is for existing users only")
        return
    if promo.availability is PromocodeAvailability.ALLOWED:
        if actor.id not in promo.allowed_user_ids:
            raise ValidationError(f"Promocode '{promo.code}' is not available to this user")
        return
    # PromocodeAvailability.INVITED (promocode redemption eligibility) is
    # intentionally out of scope for the referrals module -- see
    # docs/superpowers/specs/2026-08-31-referrals-design.md §10; always deny
    # for now.
    raise ValidationError(f"Promocode '{promo.code}' is not available to this user")
