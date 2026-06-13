from datetime import datetime, timezone
from typing import Optional

from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager, ShowMode, StartMode
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button, Select
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from loguru import logger

from src.application.common import Notifier
from src.application.common.dao import PlanDao, PromocodeDao
from src.application.dto import UserDto
from src.application.use_cases.promocode.commands.management import (
    CreatePromocode,
    CreatePromocodeDto,
    DeactivatePromocode,
    DeactivatePromocodeDto,
)
from src.core.constants import USER_KEY
from src.core.enums import PromoAudience
from src.core.exceptions import (
    PromocodeInvalidDiscountError,
    PromocodeInvalidMaxActivationsError,
    PromocodeNotFoundError,
)
from src.telegram.states import DashboardPromocodes
from src.telegram.utils import is_double_click

_WIZARD_KEYS = [
    "code",
    "discount_percent",
    "plan_id",
    "plan_name",
    "audience",
    "max_activations",
    "expires_at_str",
    "expires_at_iso",
    "is_edit",
    "is_active",
    "activations_count",
    "promocode_id",
]


async def on_create(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
) -> None:
    for key in _WIZARD_KEYS:
        dialog_manager.dialog_data.pop(key, None)
    dialog_manager.dialog_data["is_edit"] = False
    await dialog_manager.switch_to(DashboardPromocodes.CODE)


@inject
async def on_code_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    notifier: FromDishka[Notifier],
    promocode_dao: FromDishka[PromocodeDao],
) -> None:
    dialog_manager.show_mode = ShowMode.EDIT
    user: UserDto = dialog_manager.middleware_data[USER_KEY]

    if not message.text:
        await notifier.notify_user(user, i18n_key="ntf-common.invalid-value")
        return

    code = message.text.strip().upper()
    if not code or len(code) > 64:
        await notifier.notify_user(user, i18n_key="ntf-common.invalid-value")
        return

    existing = await promocode_dao.get_by_code(code)
    if existing:
        await notifier.notify_user(user, i18n_key="ntf-promocode.code-already-exists")
        return

    dialog_manager.dialog_data["code"] = code
    logger.info(f"{user.log} Set promocode code='{code}'")
    await dialog_manager.switch_to(DashboardPromocodes.REWARD)


@inject
async def on_reward_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    notifier: FromDishka[Notifier],
) -> None:
    dialog_manager.show_mode = ShowMode.EDIT
    user: UserDto = dialog_manager.middleware_data[USER_KEY]

    if not message.text:
        await notifier.notify_user(user, i18n_key="ntf-common.invalid-value")
        return

    try:
        percent = int(message.text.strip())
        if not (1 <= percent <= 99):
            raise ValueError("out of range")
    except ValueError:
        await notifier.notify_user(user, i18n_key="ntf-common.invalid-value")
        return

    dialog_manager.dialog_data["discount_percent"] = percent
    logger.info(f"{user.log} Set promocode discount_percent={percent}")
    await dialog_manager.switch_to(DashboardPromocodes.ALLOWED)


async def on_plan_select(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    selected_plan_id: int,
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]

    cached_plans: list = dialog_manager.dialog_data.get("_plans_cache", [])
    plan_name = next(
        (p["name"] for p in cached_plans if p["id"] == selected_plan_id),
        str(selected_plan_id),
    )

    dialog_manager.dialog_data["plan_id"] = selected_plan_id
    dialog_manager.dialog_data["plan_name"] = plan_name
    logger.info(f"{user.log} Selected plan_id={selected_plan_id} for promocode")
    await dialog_manager.switch_to(DashboardPromocodes.AVAILABILITY)


async def on_audience_select(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    selected_audience: PromoAudience,
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    dialog_manager.dialog_data["audience"] = selected_audience.value
    logger.info(f"{user.log} Selected audience={selected_audience.value} for promocode")
    await dialog_manager.switch_to(DashboardPromocodes.TYPE)


@inject
async def on_max_activations_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    notifier: FromDishka[Notifier],
) -> None:
    dialog_manager.show_mode = ShowMode.EDIT
    user: UserDto = dialog_manager.middleware_data[USER_KEY]

    if not message.text:
        await notifier.notify_user(user, i18n_key="ntf-common.invalid-value")
        return

    try:
        count = int(message.text.strip())
        if count < 1:
            raise ValueError("must be >= 1")
    except ValueError:
        await notifier.notify_user(user, i18n_key="ntf-common.invalid-value")
        return

    dialog_manager.dialog_data["max_activations"] = count
    logger.info(f"{user.log} Set promocode max_activations={count}")
    await dialog_manager.switch_to(DashboardPromocodes.LIFETIME)


@inject
async def on_lifetime_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    notifier: FromDishka[Notifier],
) -> None:
    dialog_manager.show_mode = ShowMode.EDIT
    user: UserDto = dialog_manager.middleware_data[USER_KEY]

    if not message.text:
        await notifier.notify_user(user, i18n_key="ntf-common.invalid-value")
        return

    dt = _parse_date(message.text.strip())
    if dt is None:
        await notifier.notify_user(user, i18n_key="ntf-common.invalid-value")
        return

    dialog_manager.dialog_data["expires_at_iso"] = dt.isoformat()
    dialog_manager.dialog_data["expires_at_str"] = dt.strftime("%d.%m.%Y %H:%M UTC")
    logger.info(f"{user.log} Set promocode expires_at={dt.isoformat()}")
    await dialog_manager.switch_to(DashboardPromocodes.CONFIGURATOR)


def _parse_date(text: str) -> Optional[datetime]:
    for fmt in ("%d.%m.%Y %H:%M", "%d.%m.%Y"):
        try:
            dt = datetime.strptime(text, fmt)
            if fmt == "%d.%m.%Y":
                dt = dt.replace(hour=23, minute=59, second=59)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


@inject
async def on_confirm(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    notifier: FromDishka[Notifier],
    create_promocode: FromDishka[CreatePromocode],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    data = dialog_manager.dialog_data

    try:
        expires_at = datetime.fromisoformat(data["expires_at_iso"])
        dto = CreatePromocodeDto(
            code=data["code"],
            discount_percent=int(data["discount_percent"]),
            plan_id=int(data["plan_id"]),
            audience=PromoAudience(data["audience"]),
            max_activations=int(data["max_activations"]),
            expires_at=expires_at,
        )
        await create_promocode(user, dto)

        logger.info(f"{user.log} Created promocode '{data['code']}'")
        await notifier.notify_user(user, i18n_key="ntf-promocode.admin-created")
        await dialog_manager.start(DashboardPromocodes.MAIN, mode=StartMode.RESET_STACK)

    except PromocodeInvalidDiscountError:
        await notifier.notify_user(user, i18n_key="ntf-common.invalid-value")
    except PromocodeInvalidMaxActivationsError:
        await notifier.notify_user(user, i18n_key="ntf-common.invalid-value")
    except Exception as e:
        logger.warning(f"{user.log} Promocode creation failed: {e}")
        await notifier.notify_user(user, i18n_key="ntf-error.unknown")


@inject
async def on_promocode_select(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    notifier: FromDishka[Notifier],
    promocode_dao: FromDishka[PromocodeDao],
    plan_dao: FromDishka[PlanDao],
) -> None:
    promo_id = int(dialog_manager.item_id)  # type: ignore[attr-defined]
    user: UserDto = dialog_manager.middleware_data[USER_KEY]

    promocode = await promocode_dao.get_by_id(promo_id)
    if not promocode:
        await notifier.notify_user(user, i18n_key="ntf-promocode.not-found")
        return

    plan_name: str = str(promocode.plan_id)
    plan = await plan_dao.get_by_id(promocode.plan_id)
    if plan:
        plan_name = plan.name

    expires_str = promocode.expires_at.strftime("%d.%m.%Y %H:%M UTC")

    dialog_manager.dialog_data.update(
        {
            "is_edit": True,
            "promocode_id": promocode.id,
            "code": promocode.code,
            "discount_percent": promocode.discount_percent,
            "plan_id": promocode.plan_id,
            "plan_name": plan_name,
            "audience": promocode.audience.value,
            "max_activations": promocode.max_activations,
            "expires_at_str": expires_str,
            "is_active": promocode.is_active,
        }
    )

    logger.info(f"{user.log} Viewing promocode id={promo_id}")
    await dialog_manager.switch_to(DashboardPromocodes.CONFIGURATOR)


@inject
async def on_deactivate(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    notifier: FromDishka[Notifier],
    deactivate_promocode: FromDishka[DeactivatePromocode],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    promo_id = dialog_manager.dialog_data.get("promocode_id")

    if promo_id is None:
        await notifier.notify_user(user, i18n_key="ntf-error.unknown")
        return

    if is_double_click(dialog_manager, key=f"deactivate_confirm_{promo_id}", cooldown=10):
        try:
            await deactivate_promocode(user, DeactivatePromocodeDto(promocode_id=int(promo_id)))
            dialog_manager.dialog_data["is_active"] = False
            logger.info(f"{user.log} Deactivated promocode id={promo_id}")
            await notifier.notify_user(user, i18n_key="ntf-promocode.admin-deactivated")
            await dialog_manager.switch_to(DashboardPromocodes.LIST)
        except PromocodeNotFoundError:
            await notifier.notify_user(user, i18n_key="ntf-promocode.not-found")
        return

    await notifier.notify_user(user, i18n_key="ntf-common.double-click-confirm")
    logger.debug(f"{user.log} Clicked deactivate for promocode id={promo_id} (awaiting confirmation)")
