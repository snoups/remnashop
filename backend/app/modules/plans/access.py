from app.core.enums import PlanAvailability
from app.modules.plans.dto import PlanDto
from app.modules.users import UserDto


def is_plan_purchasable_by(
    plan: PlanDto, actor: UserDto, *, has_purchase_history: bool, has_referrer: bool
) -> bool:
    """Whether `actor` may purchase `plan` right now, given a specific plan_id
    -- gates every provisioning entry point (checkout, promocode SUBSCRIPTION
    reward), so a plan's availability/allowlist can't be bypassed by calling a
    lower-level endpoint with a known plan_id. `has_purchase_history` = actor
    has ever purchased a non-trial subscription (any status, including
    DELETED/EXPIRED) -- matches main's UserDao.has_any_subscription.

    LINK plans are unconditionally purchasable once you know the plan_id (a
    link/code IS the access control), as in the earlier GetAvailablePlanByCode
    -- but ListActivePlansUseCase excludes them from the catalog before this
    is ever called for one, as in the earlier GetAvailablePlans having no case
    for LINK."""
    if not plan.is_active:
        return False
    if plan.availability == PlanAvailability.ALL:
        return True
    if plan.availability == PlanAvailability.ALLOWED:
        telegram_id = getattr(actor, "telegram_id", None)
        email = getattr(actor, "email", None)
        return (telegram_id is not None and telegram_id in plan.allowed_telegram_ids) or (
            email is not None and email in plan.allowed_emails
        )
    if plan.availability == PlanAvailability.NEW:
        return not has_purchase_history
    if plan.availability == PlanAvailability.EXISTING:
        return has_purchase_history
    if plan.availability == PlanAvailability.LINK:
        return True
    if plan.availability == PlanAvailability.INVITED:
        return has_referrer
    return False
