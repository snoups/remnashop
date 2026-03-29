from dataclasses import asdict
from typing import Any, Optional

from aiogram_dialog import DialogManager
from aiogram_dialog.widgets.common import ManagedScroll
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject

from src.application.common import TranslatorRunner
from src.application.use_cases.statistics.queries.plans import GetPlanStatistics
from src.application.use_cases.statistics.queries.referrals import GetReferralStatistics
from src.application.use_cases.statistics.queries.subscriptions import GetSubscriptionStatistics
from src.application.use_cases.statistics.queries.transactions import GetTransactionStatistics
from src.application.use_cases.statistics.queries.users import GetUsersStatistics
from src.core.enums import Currency
from src.core.utils.i18n_helpers import i18n_format_days


@inject
async def users_getter(
    dialog_manager: DialogManager,
    get_users_statistics: FromDishka[GetUsersStatistics],
    **kwargs: Any,
) -> dict[str, Any]:
    data = await get_users_statistics.system()
    return asdict(data)


@inject
async def transactions_getter(
    dialog_manager: DialogManager,
    get_transaction_statistics: FromDishka[GetTransactionStatistics],
    i18n: FromDishka[TranslatorRunner],
    **kwargs: Any,
) -> dict[str, Any]:
    widget: Optional[ManagedScroll] = dialog_manager.find("scroll_transactions")
    if not widget:
        raise ValueError()

    data = await get_transaction_statistics.system()
    current_page = await widget.get_page()
    total_pages = 1 + len(data.gateway_stats)

    pager_pages = [
        {
            "page": 0,
            "gateway_type": False,
            "is_current": current_page == 0,
        }
    ] + [
        {
            "page": i + 1,
            "gateway_type": g.gateway_type,
            "is_current": current_page == i + 1,
        }
        for i, g in enumerate(data.gateway_stats)
    ]

    if current_page == 0:
        return {
            "pages": total_pages,
            "current_page": 1,
            "pager_pages": pager_pages,
            "gateway_type": False,
            **asdict(data),
        }

    gateway_index = current_page - 1
    if gateway_index >= len(data.gateway_stats):
        await widget.set_page(0)
        return await transactions_getter(
            dialog_manager=dialog_manager,
            get_transaction_statistics=get_transaction_statistics,
            i18n=i18n,
            **kwargs,
        )

    gateway = data.gateway_stats[gateway_index]

    return {
        "pages": total_pages,
        "current_page": current_page + 1,
        "pager_pages": pager_pages,
        "total_transactions": gateway.total_transactions,
        "completed_transactions": gateway.completed_transactions,
        "free_transactions": gateway.free_transactions,
        "gateway_type": gateway.gateway_type,
        "total_income": gateway.total_income,
        "daily_income": gateway.daily_income,
        "weekly_income": gateway.weekly_income,
        "monthly_income": gateway.monthly_income,
        "average_check": round(gateway.total_income / max(1, gateway.paid_count)),
        "total_discounts": gateway.total_discounts,
        "currency": Currency.from_gateway_type(gateway.gateway_type).symbol,
    }


@inject
async def subscriptions_getter(
    dialog_manager: DialogManager,
    i18n: FromDishka[TranslatorRunner],
    get_subscription_statistics: FromDishka[GetSubscriptionStatistics],
    get_plan_statistics: FromDishka[GetPlanStatistics],
    **kwargs: Any,
) -> dict[str, Any]:
    widget: Optional[ManagedScroll] = dialog_manager.find("scroll_subscriptions")
    if not widget:
        raise ValueError()

    common_data = await get_subscription_statistics.system()
    plans_data = await get_plan_statistics.system()
    current_page = await widget.get_page()
    total_pages = 1 + len(plans_data.plans)

    pager_pages = [
        {
            "page": 0,
            "plan_name": False,
            "is_current": current_page == 0,
        }
    ] + [
        {
            "page": i + 1,
            "plan_name": p.plan_name,
            "is_current": current_page == i + 1,
        }
        for i, p in enumerate(plans_data.plans)
    ]

    if current_page == 0:
        return {
            "pages": total_pages,
            "current_page": 1,
            "pager_pages": pager_pages,
            "plan_name": False,
            **asdict(common_data),
        }

    plan_index = current_page - 1
    if plan_index >= len(plans_data.plans):
        await widget.set_page(0)
        return await subscriptions_getter(
            dialog_manager=dialog_manager,
            i18n=i18n,
            get_subscription_statistics=get_subscription_statistics,
            get_plan_statistics=get_plan_statistics,
            **kwargs,
        )

    plan = plans_data.plans[plan_index]

    incomes = [r for r in plans_data.income if r.plan_id == plan.plan_id]
    all_income = (
        "\n".join(
            i18n.get(
                "msg-statistics-subscriptions-plan-income",
                income=r.total_income,
                currency=r.currency,
            )
            for r in incomes
        )
        or "-"
    )

    key, kw = i18n_format_days(plan.popular_duration) if plan.popular_duration else ("unknown", {})

    return {
        "pages": total_pages,
        "current_page": current_page + 1,
        "pager_pages": pager_pages,
        "popular_duration": i18n.get(key, **kw),
        "all_income": all_income,
        **asdict(plan),
    }


@inject
async def referrals_getter(
    dialog_manager: DialogManager,
    get_referral_statistics: FromDishka[GetReferralStatistics],
    **kwargs: Any,
) -> dict[str, Any]:
    data = await get_referral_statistics.system()
    return asdict(data)
