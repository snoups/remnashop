from typing import Any, Optional, cast

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from fluentogram import TranslatorRunner
from remnapy import RemnawaveSDK
from remnapy.exceptions import NotFoundError
from remnapy.models import GetOneNodeResponseDto

from src.core.config import AppConfig
from src.core.constants import DATETIME_FORMAT
from src.core.enums import UserRole
from src.core.i18n.keys import ByteUnitKey
from src.core.i18n.translator import get_translated_kwargs
from src.core.utils.formatters import (
    i18n_format_bytes_to_unit,
    i18n_format_days,
    i18n_format_device_limit,
    i18n_format_expire_time,
    i18n_format_traffic_limit,
)
from src.infrastructure.database.models.dto import UserDto
from src.infrastructure.database.models.dto.subscription import RemnaSubscriptionDto
from src.services.plan import PlanService
from src.services.remnawave import RemnawaveService
from src.services.settings import SettingsService
from src.services.subscription import SubscriptionService
from src.services.transaction import TransactionService
from src.services.user import UserService


@inject
async def user_getter(
    dialog_manager: DialogManager,
    config: AppConfig,
    user: UserDto,
    user_service: FromDishka[UserService],
    subscription_service: FromDishka[SubscriptionService],
    settings_service: FromDishka[SettingsService],
    **kwargs: Any,
) -> dict[str, Any]:
    settings = await settings_service.get_referral_settings()
    dialog_manager.dialog_data.pop("payload", None)
    start_data = cast(dict[str, Any], dialog_manager.start_data)
    target_telegram_id = start_data["target_telegram_id"]
    dialog_manager.dialog_data["target_telegram_id"] = target_telegram_id
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    subscription = await subscription_service.get_current(target_telegram_id)

    data: dict[str, Any] = {
        "user_id": str(target_user.telegram_id),
        "username": target_user.username or False,
        "user_name": target_user.name,
        "role": target_user.role,
        "language": target_user.language,
        "show_points": settings.reward.is_points,
        "points": target_user.points,
        "personal_discount": target_user.personal_discount,
        "purchase_discount": target_user.purchase_discount,
        "is_blocked": target_user.is_blocked,
        "is_not_self": target_user.telegram_id != user.telegram_id,
        "can_edit": user.role > target_user.role or config.bot.dev_id == user.telegram_id,
        "status": None,
        "is_trial": False,
        "has_subscription": subscription is not None,
    }

    if subscription:
        data.update(
            {
                "status": subscription.get_status,
                "is_trial": subscription.is_trial,
                "traffic_limit": i18n_format_traffic_limit(subscription.traffic_limit),
                "device_limit": i18n_format_device_limit(subscription.device_limit),
                "expire_time": i18n_format_expire_time(subscription.expire_at),
            }
        )

    return data


@inject
async def subscription_getter(
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    subscription_service: FromDishka[SubscriptionService],
    remnawave_service: FromDishka[RemnawaveService],
    remnawave: FromDishka[RemnawaveSDK],
    **kwargs: Any,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    subscription = await subscription_service.get_current(target_telegram_id)

    if not subscription:
        raise ValueError(f"Current subscription for user '{target_telegram_id}' not found")

    remna_user = await remnawave_service.get_user(subscription.user_remna_id)

    if not remna_user:
        raise ValueError(f"User Remnawave '{target_telegram_id}' not found")

    squads = (
        ", ".join(squad.name for squad in remna_user.active_internal_squads)
        if remna_user.active_internal_squads
        else False
    )

    last_node: Optional[GetOneNodeResponseDto] = None
    if remna_user.last_connected_node_uuid:
        result = await remnawave.nodes.get_one_node(remna_user.last_connected_node_uuid)
        last_node = result

    return {
        "is_trial": subscription.is_trial,
        "is_active": subscription.is_active,
        "has_devices_limit": subscription.has_devices_limit,
        "has_traffic_limit": subscription.has_traffic_limit,
        "url": remna_user.subscription_url,
        #
        "subscription_id": str(subscription.user_remna_id),
        "subscription_status": subscription.get_status,
        "traffic_used": i18n_format_bytes_to_unit(
            remna_user.used_traffic_bytes,
            min_unit=ByteUnitKey.MEGABYTE,
        ),
        "traffic_limit": (
            i18n_format_bytes_to_unit(remna_user.traffic_limit_bytes)
            if remna_user.traffic_limit_bytes and remna_user.traffic_limit_bytes > 0
            else i18n_format_traffic_limit(-1)
        ),
        "device_limit": i18n_format_device_limit(subscription.device_limit),
        "expire_time": i18n_format_expire_time(subscription.expire_at),
        #
        "squads": squads,
        "first_connected_at": (
            remna_user.first_connected.strftime(DATETIME_FORMAT)
            if remna_user.first_connected
            else False
        ),
        "last_connected_at": (
            remna_user.first_connected.strftime(DATETIME_FORMAT)
            if remna_user.first_connected
            else False
        ),
        "node_name": last_node.name if last_node else False,
        #
        "plan_name": subscription.plan.name,
        "plan_type": subscription.plan.type,
        "plan_traffic_limit": i18n_format_traffic_limit(subscription.plan.traffic_limit),
        "plan_device_limit": i18n_format_device_limit(subscription.plan.device_limit),
        "plan_duration": i18n_format_days(subscription.plan.duration),
        "can_edit": not subscription.is_expired,
    }


@inject
async def devices_getter(
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    subscription_service: FromDishka[SubscriptionService],
    remnawave_service: FromDishka[RemnawaveService],
    **kwargs: Any,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    subscription = await subscription_service.get_current(target_telegram_id)

    if not subscription:
        raise ValueError(f"Current subscription for user '{target_telegram_id}' not found")

    devices = await remnawave_service.get_devices_user(target_user)

    if not devices:
        raise ValueError(f"Devices not found for user '{target_telegram_id}'")

    formatted_devices = [
        {
            "hwid": device.hwid,
            "platform": device.platform,
            "device_model": device.device_model,
            "user_agent": device.user_agent,
        }
        for device in devices
    ]

    return {
        "current_count": len(devices),
        "max_count": i18n_format_device_limit(subscription.device_limit),
        "devices": formatted_devices,
    }


async def discount_getter(
    dialog_manager: DialogManager,
    **kwargs: Any,
) -> dict[str, Any]:
    return {"percentages": [0, 5, 10, 25, 40, 50, 70, 80, 100]}


@inject
async def points_getter(
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    **kwargs: Any,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

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


async def traffic_limit_getter(
    dialog_manager: DialogManager,
    **kwargs: Any,
) -> dict[str, Any]:
    formatted_traffic = [
        {
            "traffic_limit": i18n_format_traffic_limit(value),
            "traffic": value,
        }
        for value in [100, 200, 300, 500, 1024, 2048, -1]
    ]

    return {"traffic_count": formatted_traffic}


async def device_limit_getter(
    dialog_manager: DialogManager,
    **kwargs: Any,
) -> dict[str, Any]:
    return {"devices_count": [1, 2, 3, 4, 5, 10, -1]}


@inject
async def squads_getter(
    dialog_manager: DialogManager,
    subscription_service: FromDishka[SubscriptionService],
    remnawave: FromDishka[RemnawaveSDK],
    **kwargs: Any,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    subscription = await subscription_service.get_current(telegram_id=target_telegram_id)

    if not subscription:
        raise ValueError(f"Current subscription for user '{target_telegram_id}' not found")

    internal_response = await remnawave.internal_squads.get_internal_squads()
    internal_dict = {s.uuid: s.name for s in internal_response.internal_squads}
    internal_squads_names = ", ".join(
        internal_dict.get(squad, str(squad)) for squad in subscription.internal_squads
    )

    external_response = await remnawave.external_squads.get_external_squads()
    external_dict = {s.uuid: s.name for s in external_response.external_squads}
    external_squad_name = (
        external_dict.get(subscription.external_squad) if subscription.external_squad else False
    )

    return {
        "internal_squads": internal_squads_names or False,
        "external_squad": external_squad_name or False,
    }


@inject
async def internal_squads_getter(
    dialog_manager: DialogManager,
    subscription_service: FromDishka[SubscriptionService],
    remnawave: FromDishka[RemnawaveSDK],
    **kwargs: Any,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    subscription = await subscription_service.get_current(telegram_id=target_telegram_id)

    if not subscription:
        raise ValueError(f"Current subscription for user '{target_telegram_id}' not found")

    result = await remnawave.internal_squads.get_internal_squads()

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
    subscription_service: FromDishka[SubscriptionService],
    remnawave: FromDishka[RemnawaveSDK],
    **kwargs: Any,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    subscription = await subscription_service.get_current(telegram_id=target_telegram_id)

    if not subscription:
        raise ValueError(f"Current subscription for user '{target_telegram_id}' not found")

    result = await remnawave.external_squads.get_external_squads()
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
    user_service: FromDishka[UserService],
    subscription_service: FromDishka[SubscriptionService],
    **kwargs: Any,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    subscription = await subscription_service.get_current(target_telegram_id)

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
async def transactions_getter(
    dialog_manager: DialogManager,
    transaction_service: FromDishka[TransactionService],
    **kwargs: Any,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    transactions = await transaction_service.get_by_user(target_telegram_id)

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
    transaction_service: FromDishka[TransactionService],
    **kwargs: Any,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    selected_transaction = dialog_manager.dialog_data["selected_transaction"]
    transaction = await transaction_service.get(selected_transaction)

    if not transaction:
        raise ValueError(
            f"Transaction '{selected_transaction}' not found for user '{target_telegram_id}'"
        )

    return {
        "is_test": transaction.is_test,
        "payment_id": str(transaction.payment_id),
        "purchase_type": transaction.purchase_type,
        "transaction_status": transaction.status,
        "gateway_type": transaction.gateway_type,
        "final_amount": transaction.pricing.final_amount,
        "currency": transaction.currency.symbol,
        "discount_percent": transaction.pricing.discount_percent,
        "original_amount": transaction.pricing.original_amount,
        "created_at": transaction.created_at.strftime(DATETIME_FORMAT),  # type: ignore[union-attr]
        "plan_name": transaction.plan.name,
        "plan_type": transaction.plan.type,
        "plan_traffic_limit": i18n_format_traffic_limit(transaction.plan.traffic_limit),
        "plan_device_limit": i18n_format_device_limit(transaction.plan.device_limit),
        "plan_duration": i18n_format_days(transaction.plan.duration),
    }


@inject
async def give_access_getter(
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    plan_service: FromDishka[PlanService],
    **kwargs: Any,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    plans = await plan_service.get_allowed_plans()

    if not plans:
        raise ValueError("Allowed plans not found")

    formatted_plans = [
        {
            "plan_name": plan.name,
            "plan_id": plan.id,
            "selected": True if target_telegram_id in plan.allowed_user_ids else False,
        }
        for plan in plans
    ]

    return {"plans": formatted_plans}


@inject
async def give_subscription_getter(
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    plan_service: FromDishka[PlanService],
    **kwargs: Any,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    plans = await plan_service.get_available_plans(target_user)

    if not plans:
        raise ValueError("Available plans not found")

    formatted_plans = [
        {
            "plan_name": plan.name,
            "plan_id": plan.id,
        }
        for plan in plans
    ]

    return {"plans": formatted_plans}


@inject
async def subscription_duration_getter(
    dialog_manager: DialogManager,
    plan_service: FromDishka[PlanService],
    **kwargs: Any,
) -> dict[str, Any]:
    selected_plan_id = dialog_manager.dialog_data["selected_plan_id"]
    plan = await plan_service.get(selected_plan_id)

    if not plan:
        raise ValueError(f"Plan '{selected_plan_id}' not found")

    durations = [duration.model_dump() for duration in plan.durations]
    return {"durations": durations}


@inject
async def role_getter(
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    **kwargs: Any,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    roles = [role for role in UserRole if role != target_user.role]
    return {"roles": roles}


@inject
async def sync_getter(  # noqa: C901
    dialog_manager: DialogManager,
    i18n: FromDishka[TranslatorRunner],
    user_service: FromDishka[UserService],
    subscription_service: FromDishka[SubscriptionService],
    remnawave: FromDishka[RemnawaveSDK],
    **kwargs: Any,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    bot_subscription = await subscription_service.get_current(target_telegram_id)

    remna_subscription: Optional[RemnaSubscriptionDto] = None

    try:
        result = await remnawave.users.get_users_by_telegram_id(telegram_id=str(target_telegram_id))
    except NotFoundError:
        result = None

    if result:
        remna_user = result[0]
        remna_subscription = RemnaSubscriptionDto.from_remna_user(remna_user)

    bot_info = ""
    remna_info = ""
    bot_version = ""
    remna_version = ""

    internal_response = await remnawave.internal_squads.get_internal_squads()
    internal_dict = {s.uuid: s.name for s in internal_response.internal_squads}

    if bot_subscription:
        internal_squads_names = ", ".join(
            internal_dict.get(squad, str(squad)) for squad in bot_subscription.internal_squads
        )
        bot_kwargs = {
            "id": str(bot_subscription.user_remna_id),
            "status": bot_subscription.status,
            "url": bot_subscription.url,
            "traffic_limit": i18n_format_traffic_limit(bot_subscription.traffic_limit),
            "device_limit": i18n_format_device_limit(bot_subscription.device_limit),
            "expire_time": i18n_format_expire_time(bot_subscription.expire_at),
            "internal_squads": internal_squads_names or False,
            "external_squad": str(bot_subscription.external_squad)
            if bot_subscription.external_squad
            else False,
            "traffic_limit_strategy": bot_subscription.traffic_limit_strategy,
            "tag": bot_subscription.tag or False,
            "updated_at": bot_subscription.updated_at,
        }
        bot_info = i18n.get(
            "msg-user-sync-subscription",
            **get_translated_kwargs(i18n, bot_kwargs),
        )

    if remna_subscription:
        internal_squads_names = ", ".join(
            internal_dict.get(squad, str(squad)) for squad in remna_subscription.internal_squads
        )
        remna_kwargs = {
            "id": str(remna_subscription.uuid),
            "status": remna_subscription.status,
            "url": remna_subscription.url,
            "traffic_limit": i18n_format_traffic_limit(remna_subscription.traffic_limit),
            "device_limit": i18n_format_device_limit(remna_subscription.device_limit),
            "expire_time": i18n_format_expire_time(remna_subscription.expire_at),
            "internal_squads": internal_squads_names or False,
            "external_squad": str(remna_subscription.external_squad)
            if remna_subscription.external_squad
            else False,
            "traffic_limit_strategy": remna_subscription.traffic_limit_strategy or False,
            "tag": remna_subscription.tag or False,
            "updated_at": remna_user.updated_at,
        }
        remna_info = i18n.get(
            "msg-user-sync-subscription",
            **get_translated_kwargs(i18n, remna_kwargs),
        )

    bot_time = bot_subscription.updated_at if bot_subscription else None
    remna_time = remna_user.updated_at if remna_subscription else None

    if bot_subscription and remna_subscription:
        bot_time = bot_subscription.updated_at
        remna_time = remna_user.updated_at

        if bot_time > remna_time:
            bot_version, remna_version = "NEWER", "OLDER"
        elif bot_time < remna_time:
            bot_version, remna_version = "OLDER", "NEWER"
        else:
            bot_version = remna_version = "UNKNOWN"
    else:
        bot_version = remna_version = "UNKNOWN"

    bot_version = i18n.get("msg-user-sync-version", version=bot_version)
    remna_version = i18n.get("msg-user-sync-version", version=remna_version)

    return {
        "has_bot_subscription": bool(bot_subscription),
        "has_remna_subscription": bool(remna_subscription),
        "bot_version": bot_version,
        "remna_version": remna_version,
        "bot_subscription": bot_info,
        "remna_subscription": remna_info,
    }
