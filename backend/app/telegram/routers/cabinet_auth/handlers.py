from typing import Final, Optional

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from dishka import FromDishka
from fluentogram import TranslatorHub

from app.modules.cabinet_auth import ConfirmDeeplinkUseCase, DeeplinkStore, TelegramProfileDto
from app.modules.users import UserDto
from app.telegram.i18n import get_translator

_WEBAUTH_PREFIX: Final[str] = "webauth_"
_WEBAUTH_PAYLOAD: Final[str] = rf"^{_WEBAUTH_PREFIX}[A-Za-z0-9_-]{{20,64}}$"
# callback_data is capped at 64 bytes; a 43-char token fits
_CONFIRM_PREFIX: Final[str] = "webauth:"

router = Router(name=__name__)


@router.message(CommandStart(deep_link=True, magic=F.args.regexp(_WEBAUTH_PAYLOAD)))
async def on_start_webauth(
    message: Message,
    store: FromDishka[DeeplinkStore],
    i18n: FromDishka[TranslatorHub],
    user: Optional[UserDto] = None,
) -> None:
    if user is None:
        return
    runner = get_translator(i18n, user)
    token = (message.text or "").split(maxsplit=1)[-1].removeprefix(_WEBAUTH_PREFIX)
    pending = await store.peek(token)
    if pending is None:
        await message.answer(runner.get("ntf-cabinet-login.expired"))
        return
    # confirming here would let anyone hand a victim a link; the victim must see where it came from
    await message.answer(
        runner.get("ntf-cabinet-login-ask", ip=pending.client_ip, agent=pending.user_agent or "?"),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=runner.get("btn-cabinet-login.confirm"),
                        callback_data=f"{_CONFIRM_PREFIX}{token}",
                    )
                ]
            ]
        ),
    )


@router.callback_query(F.data.startswith(_CONFIRM_PREFIX))
async def on_confirm_webauth(
    callback: CallbackQuery,
    confirm_deeplink: FromDishka[ConfirmDeeplinkUseCase],
    i18n: FromDishka[TranslatorHub],
    user: Optional[UserDto] = None,
) -> None:
    if user is None:
        await callback.answer()
        return
    token = (callback.data or "").removeprefix(_CONFIRM_PREFIX)
    confirmed = await confirm_deeplink.execute(
        token,
        TelegramProfileDto(
            telegram_id=callback.from_user.id,
            name=callback.from_user.full_name,
            username=callback.from_user.username,
            language=callback.from_user.language_code,
        ),
    )
    runner = get_translator(i18n, user)
    text = runner.get("ntf-cabinet-login.confirmed" if confirmed else "ntf-cabinet-login.expired")
    if isinstance(callback.message, Message):
        await callback.message.edit_text(text)
    await callback.answer()
