from typing import Any, Awaitable, Callable

from aiogram.enums import ChatType
from aiogram.types import Chat, TelegramObject
from dishka import AsyncContainer
from fluentogram import TranslatorHub

from app.core.constants import CONTAINER_KEY, USER_KEY
from app.core.enums import AdLinkChannel, Locale, MiddlewareEventType, RegistrationSource
from app.modules.access import CheckRegistrationAccessDto, CheckRegistrationAccessUseCase
from app.modules.cabinet_auth import DeeplinkStore
from app.modules.users import (
    FindTelegramUserUseCase,
    RegisterTelegramUserDto,
    RegisterTelegramUserUseCase,
    RegistrationSnapshotDto,
)
from app.telegram.i18n import telegram_locale
from app.telegram.middlewares._codes import (
    parse_ad_link_code,
    parse_referral_code,
    parse_start_payload,
    parse_webauth_token,
)
from app.telegram.middlewares.base import EventTypedMiddleware
from app.telegram.notice import answer_notice


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
        telegram_language = telegram_locale(hub, aiogram_user.language_code)
        language = telegram_language or Locale(hub.root_locale)
        referral_code = parse_referral_code(event)
        ad_link_code = parse_ad_link_code(event)
        channel = AdLinkChannel.BOT
        # a newcomer arriving from the cabinet button registers with the cabinet's invite
        if webauth_token := parse_webauth_token(event):
            pending = await (await container.get(DeeplinkStore)).peek(webauth_token)
            if pending is not None and pending.link_user_id is not None:
                # linking to a cabinet account: no new account here, and invite-only
                # doesn't apply; the handler gets the existing account or None
                find_user = await container.get(FindTelegramUserUseCase)
                data[USER_KEY] = await find_user.system(aiogram_user.id)
                return await handler(event, data)
            if pending is not None:
                referral_code = pending.codes.referral_code
                ad_link_code = pending.codes.ad_link_code
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
            await answer_notice(event, text)
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
                snapshot=RegistrationSnapshotDto(
                    source=RegistrationSource.BOT
                    if channel is AdLinkChannel.BOT
                    else RegistrationSource.CABINET_BOT_LINK,
                    start_payload=parse_start_payload(event),
                    telegram_language_code=aiogram_user.language_code,
                    telegram_is_premium=aiogram_user.is_premium,
                ),
            )
        )
        return await handler(event, data)


class DialogUserMiddleware(EventTypedMiddleware):
    # a background dialog start (bg manager) carries only a user id, no message to
    # register from; an error raised before UserMiddleware ran (aiogram-dialog's
    # UnknownIntent) reaches the error handlers without one too
    __event_types__ = [MiddlewareEventType.AIOGD_UPDATE, MiddlewareEventType.ERROR]

    async def middleware_logic(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        aiogram_user = self._get_aiogram_user(data)
        if USER_KEY not in data and aiogram_user is not None:
            find_user = await data[CONTAINER_KEY].get(FindTelegramUserUseCase)
            data[USER_KEY] = await find_user.system(aiogram_user.id)
        return await handler(event, data)
