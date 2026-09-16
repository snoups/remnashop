from app.core.enums import PromocodeAvailability, PromocodeRewardType
from app.core.exceptions import ValidationError
from app.modules.plans import PlanDto, PlanRepository, is_plan_purchasable_by
from app.modules.promocodes.dto import PromocodeDto
from app.modules.referrals import ReferralRepository
from app.modules.settings import SettingsRepository
from app.modules.subscriptions import SubscriptionRepository
from app.modules.users import UserDto


async def assert_subscription_reward_grantable(
    promo: PromocodeDto,
    actor: UserDto,
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    referral_repository: ReferralRepository,
    settings_repository: SettingsRepository,
) -> PlanDto:
    """Everything a SUBSCRIPTION reward needs beyond the promocode itself, in
    one place so the preview and the real activation can't disagree. Called
    before claim_activation: a refusal here must not spend the code."""
    assert promo.reward_type is PromocodeRewardType.SUBSCRIPTION
    assert promo.reward_plan_id is not None

    shop_settings = await settings_repository.get_shop_settings()
    max_active = shop_settings.max_active_subscriptions
    if max_active is not None:
        active = await subscription_repository.get_active_by_user(actor.id)
        if len(active) >= max_active:
            raise ValidationError(
                f"User '{actor.id}' is already at the concurrent-subscription cap"
            )

    plan = await plan_repository.get_by_id(promo.reward_plan_id)
    # Same purchasability gate a direct checkout applies -- a promocode grants
    # a plan, it doesn't bypass whether that plan is still active/available.
    has_purchase_history = await subscription_repository.has_any_subscription(
        actor.id, include_trial=False
    )
    has_referrer = await referral_repository.has_referrer(actor.id)
    if not is_plan_purchasable_by(
        plan, actor, has_purchase_history=has_purchase_history, has_referrer=has_referrer
    ):
        raise ValidationError(f"Plan '{plan.id}' is not available for purchase")
    return plan


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
