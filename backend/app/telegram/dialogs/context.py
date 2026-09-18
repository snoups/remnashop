from typing import Any

from app.core.enums import SubscriptionStatus
from app.modules.subscriptions import GetAvailableTrialUseCase, SubscriptionRepository
from app.modules.users import UserDto


async def build_condition_data(
    user: UserDto,
    subscription_repository: SubscriptionRepository,
    get_available_trial: GetAvailableTrialUseCase,
) -> dict[str, Any]:
    """What catalog conditions and variables resolve against, so a button an
    admin configures behaves the same whichever window they put it in. Device
    data is not in here -- it costs a panel call, and only the devices window
    itself needs it."""
    active = await subscription_repository.get_active_by_user(user.id)
    subscription = active[0] if active else None
    trial = await get_available_trial(user)
    return {
        "name": user.name,
        "has_subscription": subscription is not None,
        "connectable": subscription is not None
        and subscription.status == SubscriptionStatus.ACTIVE,
        "trial_available": trial.is_trial_available and trial.plan is not None,
        "has_device_limit": subscription is not None and subscription.effective_device_limit != 0,
        "connect_url": subscription.url if subscription is not None else "",
    }
