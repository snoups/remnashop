import asyncio
from typing import Any, Optional, Union

from adaptix import Retort
from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from remnapy import RemnawaveSDK
from remnapy.exceptions import NotFoundError

from src.application.common import TranslatorRunner
from src.application.common.dao import (
    PlanDao,
    ReferralDao,
    SubscriptionDao,
    TransactionDao,
    UserDao,
)
from src.application.dto import PlanDurationDto, RemnaSubscriptionDto, SubscriptionDto, UserDto
from src.application.use_cases.statistics.queries.users import GetUserStatistics
from src.application.use_cases.user.queries.plans import GetAvailablePlans
from src.application.use_cases.user.queries.profile import (
    GetUserDevices,
    GetUserProfile,
    GetUserProfileSubscription,
)
from src.core.constants import DATETIME_FORMAT, TARGET_TELEGRAM_ID
from src.core.enums import PlanAvailability, Role
from src.core.types import RemnaUserDto
from src.core.utils.i18n_helpers import (
    i18n_format_bytes_to_unit,
    i18n_format_days,
    i18n_format_device_limit,
    i18n_format_expire_time,
    i18n_format_traffic_limit,
)
from src.core.utils.i18n_keys import ByteUnitKey


@inject
async def user_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    get_user_profile: FromDishka[GetUserProfile],
    **kwargs: Any,
) -> dict[str, Any]:
    dialog_manager.dialog_data.pop("payload", None)
    target_telegram_id: int = dialog_manager.start_data[TARGET_TELEGRAM_ID]  # type: ignore[call-overload, index, assignment]
    dialog_manager.dialog_data[TARGET_TELEGRAM_ID] = target_telegram_id
    profile = await get_user_profile(user, target_telegram_id)

    data: dict[str, Any] = {
        "telegram_id": profile.target_user.telegram_id,
        "username": profile.target_user.username or False,
        "name": profile.target_user.name,
        "role": profile.target_user.role,
        "language": profile.target_user.language,
        "show_points": profile.show_points,
        "points": profile.target_user.points,
        "personal_discount": profile.target_user.personal_discount,
        "purchase_discount": profile.target_user.purchase_discount,
        "is_blocked": profile.target_user.is_blocked,
        "is_not_self": profile.target_user.telegram_id != user.telegram_id,
        "can_edit": profile.can_edit,
        "status": None,
        "is_trial": False,
        "has_subscription": profile.subscription is not None,
    }

    if profile.subscription:
        data.update(
            {
                "status": profile.subscription.current_status,
                "is_trial": profile.subscription.is_trial,
                "traffic_limit": i18n_format_traffic_limit(profile.subscription.traffic_limit),
                "device_limit": i18n_format_device_limit(profile.subscription.device_limit),
                "expire_time": i18n_format_expire_time(profile.subscription.expire_at),
            }
        )

    return data


@inject
async def subscription_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    get_user_profile_subscription: FromDishka[GetUserProfileSubscription],
    **kwargs: Any,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data[TARGET_TELEGRAM_ID]

    user_profile_subscription = await get_user_profile_subscription(user, target_telegram_id)

    subscription = user_profile_subscription.subscription
    remna_user = user_profile_subscription.remna_user

    return {
        "is_trial": subscription.is_trial,
        "is_active": subscription.is_active,
        "has_devices_limit": subscription.has_devices_limit,
        "has_traffic_limit": subscription.has_traffic_limit,
        "url": remna_user.subscription_url,
        #
        "subscription_id": subscription.user_remna_id,
        "subscription_status": subscription.current_status,
        "traffic_used": i18n_format_bytes_to_unit(
            remna_user.used_traffic_bytes,
            min_unit=ByteUnitKey.MEGABYTE,
        ),
        "traffic_limit": i18n_format_traffic_limit(subscription.traffic_limit),
        "device_limit": i18n_format_device_limit(subscription.device_limit),
        "expire_time": i18n_format_expire_time(subscription.expire_at),
        #
        "internal_squads": user_profile_subscription.formatted_internal_squads or False,
        "external_squad": user_profile_subscription.formatted_external_squad or False,
        "first_connected_at": (
            remna_user.first_connected_at.strftime(DATETIME_FORMAT)
            if remna_user.first_connected_at
            else False
        ),
        "last_connected_at": (
            remna_user.user_traffic.online_at.strftime(DATETIME_FORMAT)
            if remna_user.user_traffic.online_at
            else False
        ),
        "node_name": user_profile_subscription.last_node_name,
        #
        "is_trial_plan": subscription.plan_snapshot.is_trial,
        "plan_name": subscription.plan_snapshot.name,
        "plan_type": subscription.plan_snapshot.type,
        "plan_traffic_limit": i18n_format_traffic_limit(subscription.plan_snapshot.traffic_limit),
        "plan_device_limit": i18n_format_device_limit(subscription.plan_snapshot.device_limit),
        "plan_duration": i18n_format_days(subscription.plan_snapshot.duration),
        "can_edit": user_profile_subscription.can_edit,
    }


@inject
async def devices_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    get_user_devices: FromDishka[GetUserDevices],
    **kwargs: Any,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data[TARGET_TELEGRAM_ID]
    data = await get_user_devices(user, target_telegram_id)

    formatted_devices = [
        {
            "short_hwid": device.hwid[:32],
            "hwid": device.hwid,
            "platform": device.platform,
            "device_model": device.device_model,
            "user_agent": device.user_agent,
        }
        for device in data.devices
    ]

    dialog_manager.dialog_data["hwid_map"] = formatted_devices

    return {
        "current_count": data.current_count,
        "max_count": i18n_format_device_limit(data.max_count),
        "devices": formatted_devices,
    }


async def discount_getter(dialog_manager: DialogManager, **kwargs: Any) -> dict[str, Any]:
    return {"percentages": [0, 5, 10, 25, 40, 50, 70, 80, 100]}


@inject
async def points_getter(
    dialog_manager: DialogManager,
    user_dao: FromDishka[UserDao],
    **kwargs: Any,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data[TARGET_TELEGRAM_ID]
    target_user = await user_dao.get_by_telegram_id(target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    formatted_points = [
        {
            "operation": "+" if value > 0 else "",
            "points": value,
        }
        for value in [5, -5, 25, -25, 50, -50, 100, -100]
    ]

    return {
        "current_points": target_user.points,
        "points": formatted_points,
    }


async def traffic_limit_getter(dialog_manager: DialogManager, **kwargs: Any) -> dict[str, Any]:
    formatted_traffic = [
        {
            "traffic_limit": i18n_format_traffic_limit(value),
            "traffic": value,
        }
        for value in [100, 200, 300, 500, 1024, 2048, 0]
    ]

    return {"traffic_count": formatted_traffic}


async def device_limit_getter(dialog_manager: DialogManager, **kwargs: Any) -> dict[str, Any]:
    return {"devices_count": [1, 2, 3, 4, 5, 10, 0]}


@inject
async def squads_getter(
    dialog_manager: DialogManager,
    subscription_dao: FromDishka[SubscriptionDao],
    remnawave_sdk: FromDishka[RemnawaveSDK],
    **kwargs: Any,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data[TARGET_TELEGRAM_ID]

    subscription = await subscription_dao.get_current(target_telegram_id)

    if not subscription:
        raise ValueError(f"Subscription for '{target_telegram_id}' not found")

    internal_task = remnawave_sdk.internal_squads.get_internal_squads()
    external_task = remnawave_sdk.external_squads.get_external_squads()

    internal_resp, external_resp = await asyncio.gather(internal_task, external_task)

    internal_dict = {s.uuid: s.name for s in internal_resp.internal_squads}
    internal_names = ", ".join(
        internal_dict.get(uuid, str(uuid)) for uuid in subscription.internal_squads
    )

    external_dict = {s.uuid: s.name for s in external_resp.external_squads}
    external_name = (
        external_dict.get(subscription.external_squad) if subscription.external_squad else None
    )

    return {
        "internal_squads": internal_names or None,
        "external_squad": external_name or None,
    }


@inject
async def internal_squads_getter(
    dialog_manager: DialogManager,
    subscription_dao: FromDishka[SubscriptionDao],
    remnawave_sdk: FromDishka[RemnawaveSDK],
    **kwargs: Any,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data[TARGET_TELEGRAM_ID]
    subscription = await subscription_dao.get_current(telegram_id=target_telegram_id)

    if not subscription:
        raise ValueError(f"Current subscription for user '{target_telegram_id}' not found")

    result = await remnawave_sdk.internal_squads.get_internal_squads()

    squads = [
        {
            "uuid": squad.uuid,
            "name": squad.name,
            "selected": True if squad.uuid in subscription.internal_squads else False,
        }
        for squad in result.internal_squads
    ]

    return {"squads": squads}


@inject
async def external_squads_getter(
    dialog_manager: DialogManager,
    subscription_dao: FromDishka[SubscriptionDao],
    remnawave_sdk: FromDishka[RemnawaveSDK],
    **kwargs: Any,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data[TARGET_TELEGRAM_ID]
    subscription = await subscription_dao.get_current(telegram_id=target_telegram_id)

    if not subscription:
        raise ValueError(f"Current subscription for user '{target_telegram_id}' not found")

    result = await remnawave_sdk.external_squads.get_external_squads()
    existing_squad_uuids = {squad.uuid for squad in result.external_squads}

    if subscription.external_squad and subscription.external_squad not in existing_squad_uuids:
        subscription.external_squad = None

    squads = [
        {
            "uuid": squad.uuid,
            "name": squad.name,
            "selected": True if squad.uuid == subscription.external_squad else False,
        }
        for squad in result.external_squads
    ]

    return {"squads": squads}


@inject
async def expire_time_getter(
    dialog_manager: DialogManager,
    i18n: FromDishka[TranslatorRunner],
    subscription_dao: FromDishka[SubscriptionDao],
    **kwargs: Any,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data[TARGET_TELEGRAM_ID]
    subscription = await subscription_dao.get_current(target_telegram_id)

    if not subscription:
        raise ValueError(f"Current subscription for user '{target_telegram_id}' not found")

    formatted_durations = []
    for value in [1, -1, 3, -3, 7, -7, 14, -14, 30, -30]:
        key, kw = i18n_format_days(value)
        key2, kw2 = i18n_format_days(-value)
        formatted_durations.append(
            {
                "operation": "+" if value > 0 else "-",
                "duration": i18n.get(key, **kw) if value > 0 else i18n.get(key2, **kw2),
                "days": value,
            }
        )

    return {
        "expire_time": i18n_format_expire_time(subscription.expire_at),
        "durations": formatted_durations,
    }


@inject
async def statistics_getter(
    dialog_manager: DialogManager,
    i18n: FromDishka[TranslatorRunner],
    get_user_statistics: FromDishka[GetUserStatistics],
    **kwargs: Any,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data[TARGET_TELEGRAM_ID]
    data = await get_user_statistics.system(target_telegram_id)

    payment_amounts = (
        "\n".join(
            i18n.get(
                "msg-user-statistics-payment-amount",
                currency=p.currency,
                amount=p.total_amount,
            )
            for p in data.payment_amounts
        )
        or False
    )

    return {
        "has_referrals": data.referrals_level_1 > 0,
        "last_payment_at": data.last_payment_at or 0,
        "payment_amounts": payment_amounts,
        "registered_at": data.registered_at,
        "referrer_telegram_id": data.referrer_telegram_id or 0,
        "referrer_username": data.referrer_username or 0,
        "referrals_level_1": data.referrals_level_1,
        "referrals_level_2": data.referrals_level_2,
        "reward_points": data.reward_points,
        "reward_days": data.reward_days,
    }


@inject
async def referrals_getter(
    dialog_manager: DialogManager,
    referral_dao: FromDishka[ReferralDao],
    **kwargs: Any,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data[TARGET_TELEGRAM_ID]
    referrals = await referral_dao.get_referrals_list(referrer_id=target_telegram_id, limit=100)

    return {
        "referrals": [
            {
                "telegram_id": r.referred.telegram_id,
                "name": r.referred.name,
            }
            for r in referrals
        ]
    }


@inject
async def transactions_getter(
    dialog_manager: DialogManager,
    transaction_dao: FromDishka[TransactionDao],
    **kwargs: Any,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data[TARGET_TELEGRAM_ID]
    transactions = await transaction_dao.get_by_user(target_telegram_id)

    if not transactions:
        raise ValueError(f"Transactions not found for user '{target_telegram_id}'")

    formatted_transactions = [
        {
            "payment_id": transaction.payment_id,
            "status": transaction.status,
            "created_at": transaction.created_at.strftime(DATETIME_FORMAT),  # type: ignore[union-attr]
        }
        for transaction in transactions
    ]

    return {"transactions": list(reversed(formatted_transactions))}


@inject
async def transaction_getter(
    dialog_manager: DialogManager,
    transaction_dao: FromDishka[TransactionDao],
    **kwargs: Any,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data[TARGET_TELEGRAM_ID]
    selected_transaction = dialog_manager.dialog_data["selected_transaction"]
    transaction = await transaction_dao.get_by_payment_id(selected_transaction)

    if not transaction:
        raise ValueError(
            f"Transaction '{selected_transaction}' not found for user '{target_telegram_id}'"
        )

    return {
        "is_test": transaction.is_test,
        "is_trial_plan": transaction.plan_snapshot.is_trial,
        "payment_id": transaction.payment_id,
        "purchase_type": transaction.purchase_type,
        "transaction_status": transaction.status,
        "gateway_type": transaction.gateway_type,
        "final_amount": transaction.pricing.final_amount,
        "currency": transaction.currency.symbol,
        "discount_percent": transaction.pricing.discount_percent,
        "original_amount": transaction.pricing.original_amount,
        "created_at": transaction.created_at.strftime(DATETIME_FORMAT),  # type: ignore[union-attr]
        "plan_name": transaction.plan_snapshot.name,
        "plan_type": transaction.plan_snapshot.type,
        "plan_traffic_limit": i18n_format_traffic_limit(transaction.plan_snapshot.traffic_limit),
        "plan_device_limit": i18n_format_device_limit(transaction.plan_snapshot.device_limit),
        "plan_duration": i18n_format_days(transaction.plan_snapshot.duration),
    }


@inject
async def give_access_getter(
    dialog_manager: DialogManager,
    plan_dao: FromDishka[PlanDao],
    i18n: FromDishka[TranslatorRunner],
    **kwargs: Any,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data[TARGET_TELEGRAM_ID]
    plans = await plan_dao.filter_by_availability(PlanAvailability.ALLOWED)

    if not plans:
        raise ValueError("Allowed plans not found")

    formatted_plans = [
        {
            "plan_name": i18n.get(plan.name),
            "plan_id": plan.id,
            "selected": True if target_telegram_id in plan.allowed_user_ids else False,
        }
        for plan in plans
    ]

    return {"plans": formatted_plans}


@inject
async def give_subscription_getter(
    dialog_manager: DialogManager,
    user_dao: FromDishka[UserDao],
    i18n: FromDishka[TranslatorRunner],
    get_available_plans: FromDishka[GetAvailablePlans],
    **kwargs: Any,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data[TARGET_TELEGRAM_ID]
    target_user = await user_dao.get_by_telegram_id(target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    plans = await get_available_plans.system(target_user)

    if not plans:
        raise ValueError("Available plans not found")

    formatted_plans = [
        {
            "plan_name": i18n.get(plan.name),
            "plan_id": plan.id,
        }
        for plan in plans
    ]

    return {"plans": formatted_plans}


@inject
async def subscription_duration_getter(
    dialog_manager: DialogManager,
    retort: FromDishka[Retort],
    plan_dao: FromDishka[PlanDao],
    **kwargs: Any,
) -> dict[str, Any]:
    selected_plan_id = dialog_manager.dialog_data["selected_plan_id"]
    plan = await plan_dao.get_by_id(selected_plan_id)

    if not plan:
        raise ValueError(f"Plan '{selected_plan_id}' not found")

    return {"durations": retort.dump(plan.durations, list[PlanDurationDto])}


@inject
async def role_getter(
    dialog_manager: DialogManager,
    user_dao: FromDishka[UserDao],
    **kwargs: Any,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data[TARGET_TELEGRAM_ID]
    target_user = await user_dao.get_by_telegram_id(target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    roles = [
        role
        for role in Role
        if role != target_user.role and role not in [Role.SYSTEM, Role.OWNER, Role.PREVIEW]
    ]
    return {"roles": roles[::-1]}


@inject
async def sync_getter(  # noqa: C901
    dialog_manager: DialogManager,
    i18n: FromDishka[TranslatorRunner],
    user_dao: FromDishka[UserDao],
    subscription_dao: FromDishka[SubscriptionDao],
    remnawave_sdk: FromDishka[RemnawaveSDK],
    **kwargs: Any,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data[TARGET_TELEGRAM_ID]
    target_user = await user_dao.get_by_telegram_id(target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    bot_sub = await subscription_dao.get_current(target_telegram_id)
    remna_sub: Optional[RemnaSubscriptionDto] = None
    remna_updated_at = None

    try:
        result = await remnawave_sdk.users.get_users_by_telegram_id(
            telegram_id=str(target_telegram_id)
        )
        if result:
            remna_user: RemnaUserDto = result[0]
            remna_sub = RemnaSubscriptionDto.from_remna_user(remna_user)
            remna_updated_at = remna_user.updated_at
    except NotFoundError:
        pass

    squads_res = await remnawave_sdk.internal_squads.get_internal_squads()
    squads_map = {s.uuid: s.name for s in squads_res.internal_squads}

    def format_subscription(sub: Union[None, SubscriptionDto, RemnaSubscriptionDto]) -> str:
        if not sub:
            return ""

        sub_id = str(getattr(sub, "user_remna_id", getattr(sub, "uuid", "")))

        squad_names = ", ".join(squads_map.get(s, str(s)) for s in sub.internal_squads)

        kwargs = {
            "id": sub_id,
            "status": sub.status,
            "url": sub.url,
            "traffic_limit": i18n_format_traffic_limit(sub.traffic_limit),
            "device_limit": i18n_format_device_limit(sub.device_limit),
            "expire_time": i18n_format_expire_time(sub.expire_at),
            "internal_squads": squad_names or False,
            "external_squad": str(sub.external_squad) if sub.external_squad else False,
            "traffic_limit_strategy": sub.traffic_limit_strategy or False,
            "tag": sub.tag or False,
        }
        return i18n.get("msg-user-sync-subscription", **kwargs)

    bot_version_key = "UNKNOWN"
    remna_version_key = "UNKNOWN"

    if bot_sub and remna_sub:
        if bot_sub.updated_at > remna_updated_at:  # type: ignore[operator]
            bot_version_key, remna_version_key = "NEWER", "OLDER"
        elif bot_sub.updated_at < remna_updated_at:  # type: ignore[operator]
            bot_version_key, remna_version_key = "OLDER", "NEWER"

    return {
        "has_bot_subscription": bool(bot_sub),
        "has_remna_subscription": bool(remna_sub),
        "bot_version": i18n.get("msg-user-sync-version", version=bot_version_key),
        "remna_version": i18n.get("msg-user-sync-version", version=remna_version_key),
        "bot_subscription": format_subscription(bot_sub),
        "remna_subscription": format_subscription(remna_sub),
    }
