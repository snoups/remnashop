from typing import Any, Awaitable, Callable

from aiogram.enums import ChatType
from aiogram.types import CallbackQuery, Chat, Message, TelegramObject
from dishka import AsyncContainer
from fluentogram import TranslatorHub

from app.core.constants import CONTAINER_KEY, USER_KEY
from app.core.enums import AdLinkChannel, Locale, MiddlewareEventType
from app.modules.access import CheckRegistrationAccessDto, CheckRegistrationAccessUseCase
from app.modules.cabinet_auth import DeeplinkStore
from app.modules.users import RegisterTelegramUserDto, RegisterTelegramUserUseCase
from app.telegram.middlewares._codes import (
    parse_ad_link_code,
    parse_referral_code,
    parse_webauth_token,
)
from app.telegram.middlewares.base import EventTypedMiddleware


class UserMiddleware(EventTypedMiddleware):
    __event_types__ = [
        MiddlewareEventType.MESSAGE,
        MiddlewareEventType.CALLBACK_QUERY,
    ]

    async def middleware_logic(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        # PrivateFilter runs inside the outer middlewares, so without this
        # check group-chat senders would get a DB write before it rejects them
        chat = data.get("event_chat")
        if not isinstance(chat, Chat) or chat.type != ChatType.PRIVATE:
            return await handler(event, data)

        aiogram_user = self._get_aiogram_user(data)

        if aiogram_user is None or aiogram_user.is_bot:
            return await handler(event, data)

        container: AsyncContainer = data[CONTAINER_KEY]
        use_case = await container.get(RegisterTelegramUserUseCase)
        hub = await container.get(TranslatorHub)
        # "pt-br" -> "pt"; only a locale the bot actually serves counts
        code = (aiogram_user.language_code or "").split("-")[0].lower()
        telegram_language = Locale(code) if code in hub.translators_map else None
        language = telegram_language or Locale(hub.root_locale)
        referral_code = parse_referral_code(event)
        ad_link_code = parse_ad_link_code(event)
        channel = AdLinkChannel.BOT
        # a newcomer arriving from the cabinet button registers with the cabinet's invite
        if webauth_token := parse_webauth_token(event):
            pending = await (await container.get(DeeplinkStore)).peek(webauth_token)
            if pending is not None:
                referral_code = pending.referral_code
                ad_link_code = pending.ad_link_code
                channel = AdLinkChannel.WEBCABINET

        check_access = await container.get(CheckRegistrationAccessUseCase)
        denial = await check_access.system(
            CheckRegistrationAccessDto(
                channel=channel,
                telegram_id=aiogram_user.id,
                referral_code=referral_code,
                ad_link_code=ad_link_code,
            )
        )
        if denial is not None:
            text = hub.get_translator_by_locale(language.value).get(
                f"ntf-access.{denial.value.lower().replace('_', '-')}"
            )
            if isinstance(event, Message):
                await event.answer(text)
            elif isinstance(event, CallbackQuery):
                await event.answer(text, show_alert=True)
            return None

        data[USER_KEY] = await use_case.system(
            RegisterTelegramUserDto(
                telegram_id=aiogram_user.id,
                name=aiogram_user.full_name,
                username=aiogram_user.username,
                language=language,
                sync_language=telegram_language is not None,
                ad_link_code=ad_link_code,
                referral_code=referral_code,
                channel=channel,
            )
        )
        return await handler(event, data)
