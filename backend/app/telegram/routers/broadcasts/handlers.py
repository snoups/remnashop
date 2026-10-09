import re
from collections.abc import Awaitable, Callable
from typing import Final, Optional

from aiogram import Bot, F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram_dialog import DialogManager, ShowMode, StartMode
from dishka import FromDishka
from fluentogram import TranslatorHub, TranslatorRunner

from app.core.constants import INT32_MAX
from app.modules.broadcasts import GetBroadcastPromocodeUseCase
from app.modules.promocodes import ValidatePromocodeUseCase
from app.modules.subscriptions import ListOwnActiveSubscriptionsUseCase
from app.modules.users import SetMarketingOptOutUseCase, UserDto
from app.telegram.broadcast_callbacks import (
    MENU_CALLBACK,
    MENU_START_PAYLOAD,
    PROMO_PREFIX,
    RESUBSCRIBE_CALLBACK,
    START_PREFIX,
    UNSUBSCRIBE_CALLBACK,
)
from app.telegram.i18n import get_translator
from app.telegram.routers.promocode.handlers import continue_with_code
from app.telegram.states import Subscription

_START_PAYLOAD: Final[re.Pattern[str]] = re.compile(rf"{START_PREFIX}([0-9]+)")

router = Router(name=__name__)


def _broadcast_id(raw: str) -> Optional[int]:
    # broadcasts.id is int32; anything else can't be one of ours
    if not (raw.isascii() and raw.isdigit()):
        return None
    value = int(raw)
    return value if value <= INT32_MAX else None


def parse_broadcast_id(data: str) -> Optional[int]:
    return _broadcast_id(data.removeprefix(PROMO_PREFIX))


def parse_start_broadcast_id(payload: str) -> Optional[int]:
    match = _START_PAYLOAD.fullmatch(payload)
    return _broadcast_id(match.group(1)) if match else None


# the user middleware skips bots and callbacks without a chat
async def _answer_unknown_user(callback: CallbackQuery, i18n: TranslatorHub) -> None:
    runner = i18n.get_translator_by_locale(i18n.root_locale)
    await callback.answer(runner.get("ntf-broadcast.start-required"), show_alert=True)


async def _open_promocode(
    broadcast_id: Optional[int],
    user: UserDto,
    dialog_manager: DialogManager,
    runner: TranslatorRunner,
    get_broadcast_promocode: GetBroadcastPromocodeUseCase,
    validate_promocode: ValidatePromocodeUseCase,
    list_own_active_subscriptions: ListOwnActiveSubscriptionsUseCase,
    reply: Callable[[str], Awaitable[object]],
) -> bool:
    code = await get_broadcast_promocode(user, broadcast_id) if broadcast_id is not None else None
    if code is None:
        return False
    await dialog_manager.start(
        Subscription.PROMOCODE, mode=StartMode.RESET_STACK, show_mode=ShowMode.SEND
    )
    await continue_with_code(
        code,
        user,
        dialog_manager,
        validate_promocode,
        list_own_active_subscriptions,
        reply=reply,
        runner=runner,
    )
    # switch_to only changes state; re-render the window the user should land on
    await dialog_manager.show(ShowMode.EDIT)
    return True


@router.message(CommandStart(deep_link=True, magic=F.args.regexp(rf"^{START_PREFIX}\d+$")))
async def on_start_broadcast(
    message: Message,
    dialog_manager: DialogManager,
    get_broadcast_promocode: FromDishka[GetBroadcastPromocodeUseCase],
    validate_promocode: FromDishka[ValidatePromocodeUseCase],
    list_own_active_subscriptions: FromDishka[ListOwnActiveSubscriptionsUseCase],
    i18n: FromDishka[TranslatorHub],
    user: Optional[UserDto] = None,
) -> None:
    if user is None:
        return
    runner = get_translator(i18n, user)
    payload = (message.text or "").split(maxsplit=1)[-1]
    opened = await _open_promocode(
        parse_start_broadcast_id(payload),
        user,
        dialog_manager,
        runner,
        get_broadcast_promocode,
        validate_promocode,
        list_own_active_subscriptions,
        message.answer,
    )
    if not opened:
        await message.answer(runner.get("ntf-broadcast.promo-gone"))


@router.callback_query(F.data.startswith(PROMO_PREFIX))
async def on_broadcast_promocode(
    callback: CallbackQuery,
    bot: Bot,
    get_broadcast_promocode: FromDishka[GetBroadcastPromocodeUseCase],
    i18n: FromDishka[TranslatorHub],
    user: Optional[UserDto] = None,
) -> None:
    if user is None:
        await _answer_unknown_user(callback, i18n)
        return
    broadcast_id = parse_broadcast_id(callback.data or "")
    code = await get_broadcast_promocode(user, broadcast_id) if broadcast_id is not None else None
    if code is None:
        runner = get_translator(i18n, user)
        await callback.answer(runner.get("ntf-broadcast.promo-gone"), show_alert=True)
        return
    # the client opens the private chat and sends /start bc_<id>; the dialog must not touch the post
    await callback.answer(
        url=f"https://t.me/{(await bot.me()).username}?start={START_PREFIX}{broadcast_id}"
    )


@router.callback_query(F.data == UNSUBSCRIBE_CALLBACK)
async def on_broadcast_unsubscribe(
    callback: CallbackQuery,
    bot: Bot,
    set_marketing_opt_out: FromDishka[SetMarketingOptOutUseCase],
    i18n: FromDishka[TranslatorHub],
    user: Optional[UserDto] = None,
) -> None:
    if user is None:
        await _answer_unknown_user(callback, i18n)
        return
    runner = get_translator(i18n, user)
    await set_marketing_opt_out(user, True)
    await callback.answer()
    await bot.send_message(
        callback.from_user.id,
        runner.get("ntf-broadcast.unsubscribed"),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=runner.get("btn-broadcast.resubscribe"),
                        callback_data=RESUBSCRIBE_CALLBACK,
                    )
                ]
            ]
        ),
    )


@router.callback_query(F.data == RESUBSCRIBE_CALLBACK)
async def on_broadcast_resubscribe(
    callback: CallbackQuery,
    set_marketing_opt_out: FromDishka[SetMarketingOptOutUseCase],
    i18n: FromDishka[TranslatorHub],
    user: Optional[UserDto] = None,
) -> None:
    if user is None:
        await _answer_unknown_user(callback, i18n)
        return
    await set_marketing_opt_out(user, False)
    await callback.answer(
        get_translator(i18n, user).get("ntf-broadcast.resubscribed"), show_alert=True
    )


@router.callback_query(F.data == MENU_CALLBACK)
async def on_broadcast_menu(
    callback: CallbackQuery,
    bot: Bot,
    i18n: FromDishka[TranslatorHub],
    user: Optional[UserDto] = None,
) -> None:
    if user is None:
        await _answer_unknown_user(callback, i18n)
        return
    await callback.answer(
        url=f"https://t.me/{(await bot.me()).username}?start={MENU_START_PAYLOAD}"
    )
