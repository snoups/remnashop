from typing import Any, Final, Optional

from aiogram_dialog import DialogManager

from app.core.enums import SubscriptionStatus
from app.modules.referrals import GetReferralSettingsUseCase
from app.modules.settings import GetShopSettingsUseCase
from app.modules.subscriptions import GetAvailableTrialUseCase, SubscriptionDto
from app.modules.users import UserDto

SELECTED_SUBSCRIPTION_KEY: Final[str] = "subscription_id"


def selected_subscription_id(manager: DialogManager) -> Optional[int]:
    value = manager.dialog_data.get(SELECTED_SUBSCRIPTION_KEY)
    if value is None and isinstance(manager.start_data, dict):
        value = manager.start_data.get(SELECTED_SUBSCRIPTION_KEY)
    return int(value) if value is not None else None


async def menu_flags(
    active_count: int,
    get_shop_settings: GetShopSettingsUseCase,
    get_referral_settings: GetReferralSettingsUseCase,
) -> tuple[bool, bool]:
    """(can_purchase, referral_enabled)"""
    max_active = (await get_shop_settings.system()).max_active_subscriptions
    can_purchase = max_active is None or active_count < max_active
    return can_purchase, (await get_referral_settings.system()).enabled


async def build_condition_data(
    user: UserDto,
    active: list[SubscriptionDto],
    get_available_trial: GetAvailableTrialUseCase,
    *,
    selected_id: Optional[int] = None,
    can_purchase: bool = False,
    referral_enabled: bool = False,
) -> dict[str, Any]:
    """What catalog conditions and variables resolve against, so a button an
    admin configures behaves the same whichever window they put it in. Device
    data is not in here: it costs a panel call, and only the devices window
    itself needs it."""
    if selected_id is None:
        subscription = active[0] if active else None
    else:
        subscription = next((s for s in active if s.id == selected_id), None)
    trial = await get_available_trial(user)
    return {
        "name": user.name,
        "telegram_id": user.telegram_id or "",
        "points": str(user.points),
        "bonus_days": user.bonus_days,
        "subscriptions_count": len(active),
        "can_purchase": can_purchase,
        "referral_enabled": referral_enabled,
        "subscription": subscription,
        "has_subscription": subscription is not None,
        "connectable": subscription is not None
        and subscription.status == SubscriptionStatus.ACTIVE,
        "trial_available": trial.is_trial_available and trial.plan is not None,
        "has_device_limit": subscription is not None and subscription.effective_device_limit != 0,
        "connect_url": subscription.url if subscription is not None else "",
    }
