from typing import Any, cast

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from remnawave import RemnawaveSDK
from remnawave.models import GetAllInternalSquadsResponseDto

from src.core.config import AppConfig
from src.core.constants import DATETIME_FORMAT
from src.core.enums import UserRole
from src.core.i18n.keys import ByteUnitKey
from src.core.utils.formatters import (
    i18n_format_bytes_to_unit,
    i18n_format_days,
    i18n_format_device_limit,
    i18n_format_expire_time,
    i18n_format_traffic_limit,
)
from src.infrastructure.database.models.dto import UserDto
from src.services.plan import PlanService
from src.services.remnawave import RemnawaveService
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
    **kwargs: Any,
) -> dict[str, Any]:
    dialog_manager.dialog_data.pop("payload", None)
    start_data = cast(dict[str, Any], dialog_manager.start_data)
    target_telegram_id = start_data["target_telegram_id"]
    dialog_manager.dialog_data["target_telegram_id"] = target_telegram_id
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    subscription = await subscription_service.get_current(target_telegram_id)

    if not subscription:
        return {
            "user_id": str(target_user.telegram_id),
            "username": target_user.username or False,
            "user_name": target_user.name,
            "role": target_user.role,
            "language": target_user.language,
            "personal_discount": target_user.personal_discount,
            "purchase_discount": target_user.purchase_discount,
            "is_blocked": target_user.is_blocked,
            "status": None,
            "is_not_self": target_user.telegram_id != user.telegram_id,
            "can_edit": user.role > target_user.role or config.bot.dev_id == user.telegram_id,
            "is_trial": False,
            "has_subscription": False,
        }

    return {
        "user_id": str(target_user.telegram_id),
        "username": target_user.username or False,
        "user_name": target_user.name,
        "role": target_user.role,
        "language": target_user.language,
        "personal_discount": target_user.personal_discount,
        "purchase_discount": target_user.purchase_discount,
        "is_blocked": target_user.is_blocked,
        "status": subscription.status,
        "is_not_self": target_user.telegram_id != user.telegram_id,
        "can_edit": user.role > target_user.role or config.bot.dev_id == user.telegram_id,
        "is_trial": subscription.is_trial,
        "traffic_limit": i18n_format_traffic_limit(subscription.traffic_limit),
        "device_limit": i18n_format_device_limit(subscription.device_limit),
        "expire_time": i18n_format_expire_time(subscription.expire_at),
        "has_subscription": True,
    }


@inject
async def subscription_getter(
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

    remna_user = await remnawave_service.get_user(subscription.user_remna_id)

    if not remna_user:
        raise ValueError(f"User Remnawave '{target_telegram_id}' not found")

    squads = (
        ", ".join(squad.name for squad in remna_user.active_internal_squads)
        if remna_user.active_internal_squads
        else False
    )

    return {
        "is_trial": subscription.is_trial,
        "is_active": subscription.is_active,
        "has_devices_limit": subscription.has_devices_limit,
        "has_traffic_limit": subscription.has_traffic_limit,
        "url": remna_user.subscription_url,
        #
        "subscription_id": str(subscription.user_remna_id),
        "subscription_status": subscription.status,
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
            remna_user.last_connected_node.connected_at.strftime(DATETIME_FORMAT)
            if remna_user.last_connected_node
            else False
        ),
        "node_name": (
            remna_user.last_connected_node.node_name if remna_user.last_connected_node else False
        ),
        #
        "plan_name": subscription.plan.name,
        "plan_type": subscription.plan.type,
        "plan_traffic_limit": i18n_format_traffic_limit(subscription.plan.traffic_limit),
        "plan_device_limit": i18n_format_device_limit(subscription.plan.device_limit),
        "plan_duration": i18n_format_days(subscription.plan.duration),
    }


@inject
async def devices_getter(
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    remnawave_service: FromDishka[RemnawaveService],
    **kwargs: Any,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    subscription = target_user.current_subscription

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

    response = await remnawave.internal_squads.get_internal_squads()

    if not isinstance(response, GetAllInternalSquadsResponseDto):
        raise ValueError("Wrong response from Remnawave")

    squads = [
        {
            "uuid": squad.uuid,
            "name": squad.name,
            "selected": True if squad.uuid in subscription.internal_squads else False,
        }
        for squad in response.internal_squads
    ]

    return {"squads": squads}


@inject
async def expire_time_getter(
    dialog_manager: DialogManager,
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

    formatted_durations = [
        {
            "operation": "ADD" if value > 0 else "SUB",
            "duration": i18n_format_days(value) if value > 0 else i18n_format_days(-value),
            "days": value,
        }
        for value in [1, -1, 3, -3, 7, -7, 14, -14, 30, -30]
    ]

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
