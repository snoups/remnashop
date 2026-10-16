from collections.abc import Awaitable, Callable
from typing import Final

from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager, ShowMode, StartMode
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button, Keyboard
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from fluentogram import TranslatorHub, TranslatorRunner
from loguru import logger
from redis.asyncio import Redis

from app.core.constants import REDIS_KEY_PREFIX, USER_KEY
from app.core.enums import PromocodeRewardType
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError, NotFoundError, ValidationError
from app.core.utils.rate_counter import hit_counter
from app.modules.promocodes import (
    ActivatePromocodeDto,
    ActivatePromocodeUseCase,
    ValidatePromocodeDto,
    ValidatePromocodeUseCase,
)
from app.modules.subscriptions import ListOwnActiveSubscriptionsUseCase
from app.modules.users import UserDto
from app.telegram.i18n import get_translator
from app.telegram.states import MainMenu, Promocode

PROMOCODE_INPUT_LIMIT: Final[int] = 10
PROMOCODE_INPUT_WINDOW_S: Final[int] = 60
_NOTIFICATION_BY_CODE: Final[dict[ErrorCode, str]] = {
    ErrorCode.PROMOCODE_NOT_FOUND: "ntf-promocode.not-found",
    ErrorCode.PROMOCODE_EXPIRED: "ntf-promocode.expired",
    ErrorCode.PROMOCODE_ALREADY_ACTIVATED: "ntf-promocode.already-activated",
    ErrorCode.TARGET_SUBSCRIPTION_REQUIRED: "ntf-promocode.no-target-subscription",
}
_TARGET_REQUIRED_REWARDS: Final[frozenset[PromocodeRewardType]] = frozenset(
    {PromocodeRewardType.DURATION, PromocodeRewardType.TRAFFIC, PromocodeRewardType.DEVICES}
)


def _refusal_key(error: AppError) -> str:
    return _NOTIFICATION_BY_CODE.get(error.code, "ntf-promocode.not-available")


async def continue_with_code(
    code: str,
    user: UserDto,
    dialog_manager: DialogManager,
    validate_promocode: ValidatePromocodeUseCase,
    list_own_active_subscriptions: ListOwnActiveSubscriptionsUseCase,
    reply: Callable[[str], Awaitable[object]],
    runner: TranslatorRunner,
) -> None:
    try:
        promo = await validate_promocode(user, ValidatePromocodeDto(code=code))
    except (NotFoundError, ValidationError) as error:
        await reply(runner.get(_refusal_key(error)))
        return

    dialog_manager.dialog_data["promo_code"] = promo.code
    dialog_manager.dialog_data["promo_reward_type"] = promo.reward_type.value
    dialog_manager.dialog_data["promo_reward"] = promo.reward

    if promo.reward_type not in _TARGET_REQUIRED_REWARDS:
        await dialog_manager.switch_to(state=Promocode.CONFIRM)
        return

    active = await list_own_active_subscriptions(user)
    if not active:
        await reply(runner.get("ntf-promocode.no-target-subscription"))
        return
    if len(active) == 1:
        dialog_manager.dialog_data["target_subscription_id"] = active[0].id
        await dialog_manager.switch_to(state=Promocode.CONFIRM)
        return

    await dialog_manager.switch_to(state=Promocode.TARGET)


async def on_promocode(
    callback: CallbackQuery,
    widget: Keyboard,
    dialog_manager: DialogManager,
) -> None:
    await dialog_manager.start(Promocode.INPUT)


@inject
async def on_promocode_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    validate_promocode: FromDishka[ValidatePromocodeUseCase],
    list_own_active_subscriptions: FromDishka[ListOwnActiveSubscriptionsUseCase],
    redis: FromDishka[Redis],
    i18n: FromDishka[TranslatorHub],
) -> None:
    dialog_manager.show_mode = ShowMode.EDIT
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    runner = get_translator(i18n, user)
    code = (message.text or "").strip().upper()
    if not code:
        return

    key = f"{REDIS_KEY_PREFIX}ratelimit:bot_promocode:user:{user.id}"
    if await hit_counter(redis, key, PROMOCODE_INPUT_WINDOW_S) > PROMOCODE_INPUT_LIMIT:
        await message.answer(runner.get("ntf-promocode.too-many-attempts"))
        return

    await continue_with_code(
        code,
        user,
        dialog_manager,
        validate_promocode,
        list_own_active_subscriptions,
        reply=message.answer,
        runner=runner,
    )


async def on_target_subscription_selected(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
) -> None:
    subscription_id = int(dialog_manager.item_id)  # type: ignore[attr-defined]
    dialog_manager.dialog_data["target_subscription_id"] = subscription_id
    await dialog_manager.switch_to(state=Promocode.CONFIRM)


@inject
async def on_promocode_confirm(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    activate_promocode: FromDishka[ActivatePromocodeUseCase],
    i18n: FromDishka[TranslatorHub],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    runner = get_translator(i18n, user)
    code = dialog_manager.dialog_data.get("promo_code")
    if not code:
        return
    target_id = dialog_manager.dialog_data.get("target_subscription_id")

    try:
        await activate_promocode(
            user, ActivatePromocodeDto(code=code, target_subscription_id=target_id)
        )
    except (NotFoundError, ValidationError) as error:
        await callback.answer(runner.get(_refusal_key(error)), show_alert=True)
        return
    except Exception:
        logger.exception(f"{user.log} Promocode activation failed unexpectedly")
        await callback.answer(runner.get("ntf-promocode.activation-failed"), show_alert=True)
        return

    await callback.answer(runner.get("ntf-promocode.activated"))
    await dialog_manager.start(MainMenu.MAIN, mode=StartMode.RESET_STACK)
