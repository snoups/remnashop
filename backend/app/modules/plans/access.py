from app.core.actor import Actor
from app.core.enums import PlanAvailability
from app.modules.plans.dto import PlanDto


def is_plan_purchasable_by(
    plan: PlanDto, actor: Actor, *, has_purchase_history: bool, has_referrer: bool
) -> bool:
    """Whether `actor` may purchase `plan` right now, given a specific plan_id
    -- gates every provisioning entry point (checkout, promocode SUBSCRIPTION
    reward), so a plan's availability/allowlist can't be bypassed by calling a
    lower-level endpoint with a known plan_id. `has_purchase_history` = actor
    has ever purchased a non-trial subscription (any status, including
    DELETED/EXPIRED) -- matches main's UserDao.has_any_subscription.

    LINK plans pass here unconditionally: their access control is the random
    public_code, which checkout requires on top of this check (as in the earlier
    GetAvailablePlanByCode). ListActivePlansUseCase excludes them from the
    catalog before this is ever called for one."""
    if not plan.is_active:
        return False
    if plan.availability == PlanAvailability.ALL:
        return True
    if plan.availability == PlanAvailability.ALLOWED:
        return (
            actor.telegram_id is not None and actor.telegram_id in plan.allowed_telegram_ids
        ) or (actor.email is not None and actor.email in plan.allowed_emails)
    if plan.availability == PlanAvailability.NEW:
        return not has_purchase_history
    if plan.availability == PlanAvailability.EXISTING:
        return has_purchase_history
    if plan.availability == PlanAvailability.LINK:
        return True
    if plan.availability == PlanAvailability.INVITED:
        return has_referrer
    return False
