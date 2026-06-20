from typing import Any, cast

from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager, ShowMode, StartMode
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from loguru import logger

from src.application.common import EventPublisher, Notifier
from src.application.common.dao import SubscriptionDao
from src.application.dto import TelegramUserDto
from src.application.events import ErrorEvent
from src.application.use_cases.promocode.commands.activate import (
    ActivatePromocode,
    ActivatePromocodeDto,
)
from src.application.use_cases.promocode.queries.validate import (
    ValidatePromocode,
    ValidatePromocodeDto,
)
from src.core.config import AppConfig
from src.core.constants import USER_KEY
from src.core.enums import PromocodeRewardType
from src.core.exceptions import (
    PromocodeAlreadyActivatedError,
    PromocodeExpiredError,
    PromocodeNotAvailableError,
    PromocodeNotFoundError,
)
from src.telegram.states import MainMenu
from src.telegram.utils import is_double_click

PENDING_PROMO_KEY = "pending_promo_code"
PENDING_PROMO_DTO_KEY = "pending_promo_dto"
PENDING_PROMO_REPLACE_KEY = "pending_promo_replace"


@inject
async def on_promocode_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    validate_promocode: FromDishka[ValidatePromocode],
    subscription_dao: FromDishka[SubscriptionDao],
    notifier: FromDishka[Notifier],
) -> None:
    dialog_manager.show_mode = ShowMode.EDIT
    user: TelegramUserDto = dialog_manager.middleware_data[USER_KEY]
    code = (message.text or "").strip().upper()

    if not code:
        return

    try:
        promo = await validate_promocode(user, ValidatePromocodeDto(code=code, user=user))
    except PromocodeNotFoundError:
        await notifier.notify_user(user, i18n_key="ntf-promocode.not-found")
        return
    except PromocodeAlreadyActivatedError:
        await notifier.notify_user(user, i18n_key="ntf-promocode.already-activated")
        return
    except PromocodeExpiredError:
        await notifier.notify_user(user, i18n_key="ntf-promocode.expired")
        return
    except PromocodeNotAvailableError:
        await notifier.notify_user(user, i18n_key="ntf-promocode.not-available")
        return

    will_replace = False
    if promo.reward_type == PromocodeRewardType.SUBSCRIPTION:
        current = await subscription_dao.get_current(user.id)
        will_replace = current is not None

    logger.info(f"{user.log} Promocode '{code}' validated, pending confirmation")

    dialog_manager.dialog_data[PENDING_PROMO_KEY] = promo.code
    dialog_manager.dialog_data[PENDING_PROMO_DTO_KEY] = {
        "code": promo.code,
        "reward_type": promo.reward_type.value,
        "reward": promo.reward,
    }
    dialog_manager.dialog_data[PENDING_PROMO_REPLACE_KEY] = will_replace


@inject
async def on_promocode_confirm(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    activate_promocode: FromDishka[ActivatePromocode],
    notifier: FromDishka[Notifier],
    event_publisher: FromDishka[EventPublisher],
    config: FromDishka[AppConfig],
) -> None:
    if is_double_click(dialog_manager, key="promo_confirm"):
        return

    user: TelegramUserDto = dialog_manager.middleware_data[USER_KEY]
    code = dialog_manager.dialog_data.get(PENDING_PROMO_KEY)

    if not code:
        return

    try:
        promo = await activate_promocode(user, ActivatePromocodeDto(code=code, user=user))
    except PromocodeAlreadyActivatedError:
        await notifier.notify_user(user, i18n_key="ntf-promocode.already-activated")
        return
    except PromocodeExpiredError:
        await notifier.notify_user(user, i18n_key="ntf-promocode.expired")
        return
    except PromocodeNotFoundError:
        await notifier.notify_user(user, i18n_key="ntf-promocode.not-found")
        return
    except PromocodeNotAvailableError:
        await notifier.notify_user(user, i18n_key="ntf-promocode.not-available")
        return
    except Exception as exc:
        logger.exception(f"{user.log} Promocode '{code}' activation failed unexpectedly")
        await notifier.notify_user(user, i18n_key="ntf-promocode.activation-failed")
        await event_publisher.publish(
            ErrorEvent(
                **config.build.data,
                telegram_id=user.telegram_id,
                username=user.username,
                name=user.name,
                exception=exc,
            )
        )
        return

    logger.info(f"{user.log} Activated promocode '{promo.code}'")
    await notifier.notify_user(user, i18n_key="ntf-promocode.activated")
    await dialog_manager.start(MainMenu.MAIN, mode=StartMode.RESET_STACK)


async def getter_promocode(dialog_manager: DialogManager, **kwargs: Any) -> dict[str, Any]:
    if dialog_manager.start_data and not dialog_manager.dialog_data.get(PENDING_PROMO_KEY):
        start_data = cast(dict[str, Any], dialog_manager.start_data)
        prefill = start_data.get("prefill_code")
        if prefill:
            dialog_manager.dialog_data[PENDING_PROMO_KEY] = prefill

    promo_data: dict[str, Any] = cast(
        dict[str, Any], dialog_manager.dialog_data.get(PENDING_PROMO_DTO_KEY, {})
    )
    reward_type = promo_data.get("reward_type", "")
    return {
        "has_promo": bool(promo_data),
        "promo_code": promo_data.get("code", dialog_manager.dialog_data.get(PENDING_PROMO_KEY, "")),
        "promo_reward_type": reward_type,
        "promo_reward": promo_data.get("reward") or 0,
        "show_reset_warning": reward_type
        in {PromocodeRewardType.TRAFFIC.value, PromocodeRewardType.DEVICES.value},
        "will_replace_subscription": bool(
            dialog_manager.dialog_data.get(PENDING_PROMO_REPLACE_KEY)
        ),
    }
