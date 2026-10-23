from app.core.actor import Actor
from app.core.enums import PromocodeAvailability, PromocodeRewardType
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError, ValidationError
from app.core.utils.time import datetime_now
from app.modules.plans import PlanDto, PlanRepository
from app.modules.promocodes.dto import PromocodeDto
from app.modules.promocodes.repository import PromocodeRepository
from app.modules.promocodes.rules import assert_usable
from app.modules.subscriptions import PurchaseEligibility, ReferrerLookup, SubscriptionRepository
from app.modules.users import UserDto


async def get_usable_promocode(
    promocode_repository: PromocodeRepository, raw_code: str
) -> PromocodeDto:
    # the code as a user typed it: an active, unexpired promocode or a refusal
    code = raw_code.strip().upper()
    promo = await promocode_repository.find_by_code(code)
    if promo is None:
        raise NotFoundError(f"Promocode '{code}' not found", code=ErrorCode.PROMOCODE_NOT_FOUND)
    assert_usable(promo, datetime_now())
    return promo


async def assert_subscription_reward_grantable(
    promo: PromocodeDto,
    actor: Actor,
    plan_repository: PlanRepository,
    eligibility: PurchaseEligibility,
) -> PlanDto:
    """Everything a SUBSCRIPTION reward needs beyond the promocode itself, in
    one place so the preview and the real activation can't disagree. Called
    before claim_activation: a refusal here must not spend the code."""
    assert promo.reward_type is PromocodeRewardType.SUBSCRIPTION
    assert promo.reward_plan_id is not None

    # an unpaid NEW order counts like it does at checkout: paying it later skips the cap
    open_orders = await eligibility.open_new_orders(actor.id)
    await eligibility.assert_below_cap(actor.id, pending=open_orders)
    plan = await plan_repository.get_by_id(promo.reward_plan_id)
    # a promocode grants a plan, it doesn't bypass the plan's own availability
    if not await eligibility.is_purchasable(plan, actor, has_open_order=open_orders > 0):
        raise ValidationError(
            f"Plan '{plan.id}' is not available for purchase", code=ErrorCode.PLAN_NOT_AVAILABLE
        )
    return plan


async def assert_available_to(
    promo: PromocodeDto,
    actor: Actor,
    subscription_repository: SubscriptionRepository,
    referrer_lookup: ReferrerLookup,
) -> None:
    """Shared by ValidatePromocodeUseCase (the pre-activation preview) and
    ActivatePromocodeUseCase (the real thing). The two must agree, or the
    preview says "available" on a code activation then refuses."""
    if promo.availability is PromocodeAvailability.ALL:
        return
    if promo.availability in (PromocodeAvailability.NEW, PromocodeAvailability.EXISTING):
        # "New" = never purchased a non-trial subscription, not "has none
        # active right now".
        has_sub = await subscription_repository.has_any_subscription(actor.id, include_trial=False)
        if promo.availability is PromocodeAvailability.NEW and has_sub:
            raise ValidationError(
                f"Promocode '{promo.code}' is for new users only",
                code=ErrorCode.PROMOCODE_NEW_USERS_ONLY,
            )
        if promo.availability is PromocodeAvailability.EXISTING and not has_sub:
            raise ValidationError(
                f"Promocode '{promo.code}' is for existing users only",
                code=ErrorCode.PROMOCODE_EXISTING_USERS_ONLY,
            )
        return
    if promo.availability is PromocodeAvailability.ALLOWED:
        if actor.id not in promo.allowed_user_ids:
            raise ValidationError(
                f"Promocode '{promo.code}' is not available to this user",
                code=ErrorCode.PROMOCODE_NOT_AVAILABLE,
            )
        return
    if promo.availability is PromocodeAvailability.INVITED:
        if not await referrer_lookup.has_referrer(actor.id):
            raise ValidationError(
                f"Promocode '{promo.code}' is for invited users only",
                code=ErrorCode.PROMOCODE_NOT_AVAILABLE,
            )
        return
    raise ValidationError(
        f"Promocode '{promo.code}' is not available to this user",
        code=ErrorCode.PROMOCODE_NOT_AVAILABLE,
    )


def assert_discount_improves(promo: PromocodeDto, user: UserDto) -> None:
    """A discount code fills one slot; a smaller one would overwrite a better
    discount the customer already has. Refused before the claim, so the code
    isn't spent on it."""
    if promo.reward is None:
        return
    if promo.reward_type is PromocodeRewardType.PERSONAL_DISCOUNT:
        current = user.personal_discount
    elif promo.reward_type is PromocodeRewardType.PURCHASE_DISCOUNT:
        current = user.purchase_discount
    else:
        return
    if promo.reward < current:
        raise ValidationError(
            f"Promocode '{promo.code}' gives less than the current {current}% discount",
            code=ErrorCode.PROMOCODE_DISCOUNT_NOT_BETTER,
        )
