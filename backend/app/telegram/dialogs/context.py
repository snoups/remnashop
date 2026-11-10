from typing import Any, Final, Optional

from aiogram_dialog import DialogManager

from app.core.enums import SubscriptionStatus
from app.modules.referrals import GetReferralSettingsUseCase
from app.modules.settings import GetShopSettingsUseCase
from app.modules.subscriptions import GetAvailableTrialUseCase, SubscriptionDto
from app.modules.users import UserDto
from app.telegram.i18n import format_price

SELECTED_SUBSCRIPTION_KEY: Final[str] = "subscription_id"


def selected_subscription_id(manager: DialogManager) -> Optional[int]:
    value = manager.dialog_data.get(SELECTED_SUBSCRIPTION_KEY)
    if value is None and isinstance(manager.start_data, dict):
        value = manager.start_data.get(SELECTED_SUBSCRIPTION_KEY)
    return int(value) if value is not None else None


async def menu_flags(
    owned: list[SubscriptionDto],
    get_shop_settings: GetShopSettingsUseCase,
    get_referral_settings: GetReferralSettingsUseCase,
) -> tuple[bool, bool, bool]:
    """(can_purchase, referral_enabled, single_subscription); owned is every
    subscription but a deleted one, an expired one holding its slot as at checkout"""
    max_active = (await get_shop_settings.system()).max_active_subscriptions
    # same count as checkout's cap: a purchase upgrades an active trial in place
    paid = sum(1 for subscription in owned if not subscription.is_trial)
    can_purchase = max_active is None or paid < max_active
    return can_purchase, (await get_referral_settings.system()).enabled, max_active == 1


async def build_condition_data(
    user: UserDto,
    active: list[SubscriptionDto],
    get_available_trial: GetAvailableTrialUseCase,
    *,
    cabinet_url: str,
    selected_id: Optional[int] = None,
    can_purchase: bool = False,
    referral_enabled: bool = False,
    single_subscription: bool = False,
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
    offers_trial = trial.is_trial_available and trial.plan is not None
    # the discount checkout applies next: transactions' pricing takes the
    # largest of the three, capped at 100
    discount = min(max(user.personal_discount, user.purchase_discount, user.loyalty_discount), 100)
    return {
        "name": user.name,
        # a string, so Fluent doesn't group the digits
        "telegram_id": str(user.telegram_id) if user.telegram_id else "",
        "discount": str(discount) if discount > 0 else "",
        "points": str(user.points),
        "bonus_days": user.bonus_days,
        "subscriptions_count": len(active),
        "can_purchase": can_purchase,
        "referral_enabled": referral_enabled,
        # max one subscription: the menu shows it directly instead of a list
        "single_subscription": single_subscription,
        "subscription": subscription,
        "has_subscription": subscription is not None,
        "connectable": subscription is not None
        and subscription.status == SubscriptionStatus.ACTIVE,
        # a free trial is one tap; a paid one opens its purchase
        "trial_available": offers_trial and trial.is_free,
        "trial_paid_available": offers_trial and not trial.is_free,
        "trial_price": (
            f"{format_price(trial.price)} {trial.currency.symbol}"
            if offers_trial and trial.currency is not None
            else ""
        ),
        "has_device_limit": subscription is not None and subscription.effective_device_limit != 0,
        "connect_url": subscription.url if subscription is not None else "",
        "cabinet_url": cabinet_url,
    }
