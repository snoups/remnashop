from typing import Final, Optional

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, Message
from dishka import FromDishka
from fluentogram import TranslatorHub
from loguru import logger

from app.core.config import AppConfig
from app.core.constants import TTL_5M, WEBAUTH_START_PREFIX
from app.core.enums import Locale
from app.modules.cabinet_auth import IssueBotSignInLinkUseCase, TelegramProfileDto
from app.modules.users import UserDto
from app.telegram.dialogs.rendering import label_with_icon
from app.telegram.i18n import get_translator, telegram_locale
from app.telegram.notice import answer_notice, delete_later

_WEBAUTH_PAYLOAD: Final[str] = rf"^{WEBAUTH_START_PREFIX}[A-Za-z0-9_-]{{20,64}}$"

router = Router(name=__name__)


@router.message(CommandStart(deep_link=True, magic=F.args.regexp(_WEBAUTH_PAYLOAD)))
async def on_start_webauth(
    message: Message,
    issue_link: FromDishka[IssueBotSignInLinkUseCase],
    i18n: FromDishka[TranslatorHub],
    user: Optional[UserDto] = None,
    *,
    config: FromDishka[AppConfig],
) -> None:
    if message.from_user is None:
        return
    # a link start from a Telegram without an account arrives with no user
    if user is not None:
        runner = get_translator(i18n, user)
    else:
        locale = telegram_locale(i18n, message.from_user.language_code)
        runner = i18n.get_translator_by_locale((locale or Locale(i18n.root_locale)).value)
    if not config.cabinet.url:
        logger.warning("Bot sign-in link requested, but CABINET_DOMAIN is not set")
        await answer_notice(message, runner.get("ntf-cabinet-login.unavailable"))
        return
    start = (message.text or "").split(maxsplit=1)[-1].removeprefix(WEBAUTH_START_PREFIX)
    # the link lands only in this chat, so whoever handed out the start link gains nothing
    link = await issue_link.execute(
        start,
        TelegramProfileDto(
            telegram_id=message.from_user.id,
            name=message.from_user.full_name,
            username=message.from_user.username,
            language=message.from_user.language_code,
        ),
    )
    if link is None:
        await answer_notice(message, runner.get("ntf-cabinet-login.expired"))
        return
    prefix = "cabinet-link" if link.is_link else "cabinet-login"
    sent = await message.answer(
        runner.get(f"ntf-{prefix}.link"),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [label_with_icon(runner, f"btn-{prefix}.open").inline_button(url=link.url)]
            ]
        ),
    )
    # gone with the link's own lifetime: a spent or expired button only misleads
    delete_later(sent, TTL_5M)
