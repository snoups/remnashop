from app.core.actor import Actor
from app.core.enums import PlanAvailability
from app.modules.plans.dto import PlanDto


def is_plan_purchasable_by(
    plan: PlanDto, actor: Actor, *, has_purchase_history: bool, has_referrer: bool
) -> bool:
    """Whether `actor` may purchase `plan` right now. Every provisioning entry
    point (checkout, a promocode's SUBSCRIPTION reward) checks it, so a known
    plan_id can't get around availability. `has_purchase_history`: a non-trial
    subscription in any status, DELETED and EXPIRED included.

    LINK plans pass unconditionally: their public_code is the access control,
    and checkout requires it on top of this check."""
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
