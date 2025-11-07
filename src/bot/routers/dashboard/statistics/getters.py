from typing import Any, Optional

from aiogram_dialog import DialogManager
from aiogram_dialog.widgets.common import ManagedScroll
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from fluentogram import TranslatorRunner

from src.core.enums import Currency, PaymentGatewayType, PromocodeRewardType, SubscriptionStatus
from src.core.utils.formatters import format_percent, i18n_format_days
from src.core.utils.time import datetime_now
from src.infrastructure.database.models.dto import (
    PlanDto,
    PromocodeDto,
    SubscriptionDto,
    TransactionDto,
    UserDto,
)
from src.services.plan import PlanService
from src.services.promocode import PromocodeService
from src.services.subscription import SubscriptionService
from src.services.transaction import TransactionService
from src.services.user import UserService


@inject
async def statistics_getter(
    dialog_manager: DialogManager,
    i18n: FromDishka[TranslatorRunner],
    users_service: FromDishka[UserService],
    transaction_service: FromDishka[TransactionService],
    subscription_service: FromDishka[SubscriptionService],
    plan_service: FromDishka[PlanService],
    promocode_service: FromDishka[PromocodeService],
    **kwargs: Any,
) -> dict[str, Any]:
    widget: Optional[ManagedScroll] = dialog_manager.find("statistics")

    if not widget:
        raise ValueError()

    current_page = await widget.get_page()

    match current_page:
        case 0:
            users = await users_service.get_all()
            transactions = await transaction_service.get_all()
            subscriptions = await subscription_service.get_all()
            statistics = get_users_statistics(users, transactions, subscriptions)
            template = "msg-statistics-users"
        case 1:
            transactions = await transaction_service.get_all()
            statistics = get_transactions_statistics(transactions, i18n)
            template = "msg-statistics-transactions"
        case 2:
            subscriptions = await subscription_service.get_all()
            statistics = get_subscriptions_statistics(subscriptions)
            template = "msg-statistics-subscriptions"
        case 3:
            plans = await plan_service.get_all()
            subscriptions = await subscription_service.get_all()
            transactions = await transaction_service.get_all()
            statistics = get_plans_statistics(plans, subscriptions, transactions, i18n)
            template = "msg-statistics-plans"
        case 4:
            promocodes = await promocode_service.get_all()
            statistics = get_promocodes_statistics(promocodes)
            template = "msg-statistics-promocodes"
        case 5:
            # referrals = await referral_service.get_all()
            # statistics = get_referrals_statistics(referrals)
            template = "msg-statistics-referrals"
        case _:
            raise ValueError(f"Invalid statistics page index: '{current_page}'")

    formatted_message = i18n.get(template, **statistics)

    return {
        "pages": 4,
        "current_page": current_page + 1,
        "statistics": formatted_message,
    }


def get_users_statistics(
    users: list[UserDto],
    transactions: list[TransactionDto],
    subscriptions: list[SubscriptionDto],
) -> dict[str, Any]:
    total_users = len(users)
    new_users_daily = sum(1 for u in users if u.age_days is not None and u.age_days == 0)
    new_users_weekly = sum(1 for u in users if u.age_days is not None and u.age_days <= 7)
    new_users_monthly = sum(1 for u in users if u.age_days is not None and u.age_days <= 30)

    users_with_subscription = sum(1 for u in users if u.current_subscription)
    users_without_subscription = total_users - users_with_subscription
    users_with_trial = sum(
        1 for u in users if u.current_subscription and u.current_subscription.is_trial
    )

    blocked_users = sum(1 for u in users if u.is_blocked)
    bot_blocked_users = sum(1 for u in users if u.is_bot_blocked)

    paying_users_ids = {
        t.user.id
        for t in transactions
        if t.is_completed and not t.pricing.is_free and t.user is not None
    }
    user_conversion = format_percent(len(paying_users_ids), total_users) if total_users else 0

    trial_users = 0
    converted_from_trial = 0

    subs_by_user: dict[int, list[SubscriptionDto]] = {}
    for s in subscriptions:
        if not s.user:
            continue

        subs_by_user.setdefault(s.user.telegram_id, []).append(s)

    for user in users:
        user_subs = subs_by_user.get(user.telegram_id, [])

        if not user_subs:
            continue

        had_trial = any(s.is_trial for s in user_subs)
        if had_trial:
            trial_users += 1
            converted = any(not s.is_trial and s for s in user_subs)
            if converted:
                converted_from_trial += 1

    trial_conversion = format_percent(converted_from_trial, trial_users) if trial_users else 0

    return {
        "total_users": total_users,
        "new_users_daily": new_users_daily,
        "new_users_weekly": new_users_weekly,
        "new_users_monthly": new_users_monthly,
        "users_with_subscription": users_with_subscription,
        "users_without_subscription": users_without_subscription,
        "users_with_trial": users_with_trial,
        "blocked_users": blocked_users,
        "bot_blocked_users": bot_blocked_users,
        "user_conversion": user_conversion,
        "trial_conversion": trial_conversion,
    }


def get_transactions_statistics(
    transactions: list[TransactionDto],
    i18n: TranslatorRunner,
) -> dict[str, Any]:
    total_transactions = len(transactions)
    completed_transactions = sum(1 for t in transactions if t.is_completed)
    free_transactions = sum(1 for t in transactions if t.pricing.is_free)
    gateways_stats: dict[str, dict[str, float]] = {}

    for t in transactions:
        if not t.is_completed:
            continue

        g = t.gateway_type

        if g not in gateways_stats:
            gateways_stats[g] = {
                "total": 0.0,
                "daily": 0.0,
                "weekly": 0.0,
                "monthly": 0.0,
                "completed": 0,
                "discount": 0.0,
                "paid_count": 0,
            }

        stats = gateways_stats[g]
        amount = float(t.pricing.final_amount)
        stats["total"] += amount
        stats["completed"] += 1 if t.is_completed else 0
        stats["discount"] += float(t.pricing.original_amount - t.pricing.final_amount)

        if not t.pricing.is_free:
            stats["paid_count"] += 1

        days_ago = (datetime_now() - t.created_at).days if t.created_at else 0
        if days_ago == 0:
            stats["daily"] += amount
        if days_ago <= 7:
            stats["weekly"] += amount
        if days_ago <= 30:
            stats["monthly"] += amount

    popular_gateway = None

    if len(gateways_stats) > 1:
        popular_gateway = max(gateways_stats.items(), key=lambda x: x[1]["paid_count"])[0]

    payment_gateways_stats = [
        i18n.get(
            "msg-statistics-transactions-gateway",
            gateway_type=gateway,
            total_income=stats["total"],
            daily_income=stats["daily"],
            weekly_income=stats["weekly"],
            monthly_income=stats["monthly"],
            average_check=(stats["total"] / max(1, stats["paid_count"])),
            total_discounts=stats["discount"],
            currency=Currency.from_gateway_type(PaymentGatewayType(gateway)).symbol,
        )
        for gateway, stats in gateways_stats.items()
    ]

    return {
        "total_transactions": total_transactions,
        "completed_transactions": completed_transactions,
        "free_transactions": free_transactions,
        "popular_gateway": i18n.get("gateway-type", gateway_type=popular_gateway)
        if popular_gateway
        else False,
        "payment_gateways": "\n".join(payment_gateways_stats),
    }


def get_subscriptions_statistics(
    subscriptions: list[SubscriptionDto],
) -> dict[str, Any]:
    total_active_subscriptions = 0
    total_expire_subscriptions = 0
    active_trial_subscriptions = 0
    expiring_subscriptions = 0
    total_unlimited = 0
    total_traffic = 0
    total_devices = 0

    now = datetime_now()

    for s in subscriptions:
        if s.is_active:
            total_active_subscriptions += 1
            if s.is_trial:
                active_trial_subscriptions += 1
            if 0 <= (s.expire_at - now).days <= 7:
                expiring_subscriptions += 1

            # TODO: separate unlim for traffic, device, duration
            if not s.has_devices_limit or not s.has_traffic_limit or s.is_unlimited:
                total_unlimited += 1
            if s.traffic_limit != -1:
                total_traffic += 1
            if s.device_limit != -1:
                total_devices += 1

        elif s.status == SubscriptionStatus.EXPIRED:
            total_expire_subscriptions += 1

    return {
        "total_active_subscriptions": total_active_subscriptions,
        "total_expire_subscriptions": total_expire_subscriptions,
        "active_trial_subscriptions": active_trial_subscriptions,
        "expiring_subscriptions": expiring_subscriptions,
        "total_unlimited": total_unlimited,
        "total_traffic": total_traffic,
        "total_devices": total_devices,
    }


def get_plans_statistics(
    plans: list[PlanDto],
    subscriptions: list[SubscriptionDto],
    transactions: list[TransactionDto],
    i18n: TranslatorRunner,
) -> dict[str, Any]:
    plan_income: dict[int, dict[str, float]] = {}
    plan_durations_count: dict[int, dict[int, int]] = {}

    for s in subscriptions:
        plan_id = s.plan.id
        plan_durations_count.setdefault(plan_id, {})
        duration_days = s.plan.duration
        plan_durations_count[plan_id][duration_days] = (
            plan_durations_count[plan_id].get(duration_days, 0) + 1
        )

    for t in transactions:
        if not (t.is_completed and t.plan and t.plan.id):
            continue
        plan_id = t.plan.id
        currency = t.currency.symbol
        amount = float(t.pricing.final_amount)

        plan_income.setdefault(plan_id, {})
        plan_income[plan_id][currency] = plan_income[plan_id].get(currency, 0.0) + amount

    active_plan_counts = {
        p.id: sum(1 for s in subscriptions if s.plan.id == p.id and s.is_active)
        for p in plans
        if p.id
    }

    popular_plan_id = None
    if len(active_plan_counts) > 1:
        popular_plan_id = max(active_plan_counts.items(), key=lambda x: x[1])[0]

    plans_stats = []
    for p in plans:
        if not p.id:
            continue

        total_subs = sum(1 for s in subscriptions if s.plan.id == p.id)
        active_subs = sum(1 for s in subscriptions if s.plan.id == p.id and s.is_active)

        durations_count = plan_durations_count.get(p.id, {})
        popular_duration = (
            max(durations_count.items(), key=lambda x: x[1])[0] if durations_count else 0
        )

        incomes = plan_income.get(p.id, {})
        all_income = (
            "\n".join(
                i18n.get(
                    "msg-statistics-plan-income",
                    income=f"{amount:.2f}",
                    currency=currency,
                )
                for currency, amount in incomes.items()
            )
            or "-"
        )

        key, kw = i18n_format_days(popular_duration)
        plans_stats.append(
            i18n.get(
                "msg-statistics-plan",
                popular=(p.id == popular_plan_id),
                plan_name=p.name,
                total_subscriptions=total_subs,
                active_subscriptions=active_subs,
                popular_duration=i18n.get(key, **kw),
                all_income=all_income,
            )
        )

    return {"plans": "\n\n".join(plans_stats)}


def get_promocodes_statistics(promocodes: list[PromocodeDto]) -> dict[str, Any]:
    total_promo_activations = sum(len(p.activations) for p in promocodes)
    most_popular_promo = max(promocodes, key=lambda p: len(p.activations), default=None)

    total_promo_days = 0
    total_promo_traffic = 0
    total_promo_subscriptions = 0
    total_promo_personal_discounts = 0
    total_promo_purchase_discounts = 0

    for p in promocodes:
        times_used = len(p.activations)
        reward_value = p.reward or 0

        if p.reward_type == PromocodeRewardType.DURATION:
            total_promo_days += reward_value * times_used
        elif p.reward_type == PromocodeRewardType.TRAFFIC:
            total_promo_traffic += reward_value * times_used
        elif p.reward_type == PromocodeRewardType.SUBSCRIPTION:
            total_promo_subscriptions += reward_value * times_used
        elif p.reward_type == PromocodeRewardType.PERSONAL_DISCOUNT:
            total_promo_personal_discounts += reward_value * times_used
        elif p.reward_type == PromocodeRewardType.PURCHASE_DISCOUNT:
            total_promo_purchase_discounts += reward_value * times_used

    return {
        "total_promo_activations": total_promo_activations,
        "most_popular_promo": most_popular_promo.code if most_popular_promo else "-",
        "total_promo_days": total_promo_days,
        "total_promo_traffic": total_promo_traffic,
        "total_promo_subscriptions": total_promo_subscriptions,
        "total_promo_personal_discounts": total_promo_personal_discounts,
        "total_promo_purchase_discounts": total_promo_purchase_discounts,
    }
