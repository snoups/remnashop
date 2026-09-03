from typing import Final

from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager, ShowMode, StartMode
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from fluentogram import TranslatorHub
from loguru import logger

from app.core.constants import USER_KEY
from app.core.enums import PromocodeRewardType
from app.core.exceptions import NotFoundError, ValidationError
from app.modules.promocodes import (
    ActivatePromocodeDto,
    ActivatePromocodeUseCase,
    ValidatePromocodeDto,
    ValidatePromocodeUseCase,
)
from app.modules.subscriptions import SubscriptionRepository
from app.modules.users import UserDto
from app.telegram.i18n import get_translator
from app.telegram.states import MainMenu, Subscription

_TARGET_REQUIRED_REWARDS: Final[frozenset[PromocodeRewardType]] = frozenset(
    {PromocodeRewardType.DURATION, PromocodeRewardType.TRAFFIC, PromocodeRewardType.DEVICES}
)


@inject
async def on_promocode_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    validate_promocode: FromDishka[ValidatePromocodeUseCase],
    subscription_repository: FromDishka[SubscriptionRepository],
    i18n: FromDishka[TranslatorHub],
) -> None:
    dialog_manager.show_mode = ShowMode.EDIT
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    runner = get_translator(i18n, user)
    code = (message.text or "").strip().upper()
    if not code:
        return

    try:
        promo = await validate_promocode(user, ValidatePromocodeDto(code=code))
    except NotFoundError:
        await message.answer(runner.get("ntf-promocode.not-found"))
        return
    except ValidationError:
        # ValidatePromocodeUseCase raises a plain ValidationError for every
        # failure case (expired / already-activated / not-available /
        # activation-limit reached) without a distinct exception type per
        # case, so there's no reliable way to map back to a specific
        # ntf-promocode.* key here -- fall back to one catch-all key rather
        # than guessing from the exception's message string.
        await message.answer(runner.get("ntf-promocode.not-available"))
        return

    dialog_manager.dialog_data["promo_code"] = promo.code
    dialog_manager.dialog_data["promo_reward_type"] = promo.reward_type.value
    dialog_manager.dialog_data["promo_reward"] = promo.reward

    if promo.reward_type not in _TARGET_REQUIRED_REWARDS:
        await dialog_manager.switch_to(state=Subscription.PROMOCODE_CONFIRM)
        return

    active = await subscription_repository.get_active_by_user(user.id)
    if not active:
        await message.answer(runner.get("ntf-promocode.no-target-subscription"))
        return
    if len(active) == 1:
        dialog_manager.dialog_data["target_subscription_id"] = active[0].id
        await dialog_manager.switch_to(state=Subscription.PROMOCODE_CONFIRM)
        return

    await dialog_manager.switch_to(state=Subscription.PROMOCODE_TARGET)


async def on_target_subscription_selected(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
) -> None:
    subscription_id = int(dialog_manager.item_id)  # type: ignore[attr-defined]
    dialog_manager.dialog_data["target_subscription_id"] = subscription_id
    await dialog_manager.switch_to(state=Subscription.PROMOCODE_CONFIRM)


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
    except NotFoundError:
        await callback.answer(runner.get("ntf-promocode.not-found"), show_alert=True)
        return
    except ValidationError:
        await callback.answer(runner.get("ntf-promocode.not-available"), show_alert=True)
        return
    except Exception:
        logger.exception(f"{user.log} Promocode activation failed unexpectedly")
        await callback.answer(runner.get("ntf-promocode.activation-failed"), show_alert=True)
        return

    await callback.answer(runner.get("ntf-promocode.activated"))
    await dialog_manager.start(MainMenu.MAIN, mode=StartMode.RESET_STACK)
