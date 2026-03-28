import asyncio
import base64
import re
import string
from typing import Any, Callable, Optional, Union

from aiogram import Bot
from aiogram.types import (
    BufferedInputFile,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from loguru import logger

from src.application.common import TranslatorHub
from src.application.dto import MessagePayloadDto
from src.application.dto.message_payload import MediaDescriptorDto
from src.application.events import BaseEvent
from src.core.config import AppConfig
from src.core.enums import Locale
from src.core.types import AnyKeyboard
from src.modules.topic_notifications.config import TopicNotificationConfig
from src.telegram.states import Notification


class TopicNotificationModule:
    def __init__(
        self,
        bot: Bot,
        config: AppConfig,
        topic_config: TopicNotificationConfig,
        translator_hub: TranslatorHub,
    ) -> None:
        self.bot = bot
        self.app_config = config
        self.config = topic_config
        self.translator_hub = translator_hub

    @property
    def suppress_admin_dms(self) -> bool:
        return self.config.is_configured and self.config.mode == 1

    async def notify_event(self, event: BaseEvent, payload: MessagePayloadDto) -> bool:
        if not self.config.is_configured or self.config.group_id is None:
            return False

        topic_id = self._resolve_topic_id(event)
        if topic_id is None:
            return False

        try:
            await self._send_payload(
                chat_id=self.config.group_id,
                topic_id=topic_id,
                payload=payload,
            )
        except Exception as e:
            logger.exception(
                f"Failed to route event '{type(event).__name__}' "
                f"to topic '{topic_id}' in chat '{self.config.group_id}': {e}"
            )
            return False

        logger.info(
            f"Routed event '{type(event).__name__}' to topic '{topic_id}' "
            f"in chat '{self.config.group_id}'"
        )
        return True

    def _resolve_topic_id(self, event: BaseEvent) -> Optional[int]:
        routes = self.config.route_map

        for key in self._get_route_keys(event):
            topic_id = routes.get(key)
            if topic_id is not None:
                return topic_id

        return self.config.default_topic_id

    def _get_route_keys(self, event: BaseEvent) -> list[str]:
        route_keys = [
            self._normalize_key(type(event).__name__),
            getattr(event.notification_type, "value", str(event.notification_type)).upper(),
            event.event_key.removeprefix("event-").replace("-", "_").replace(".", "_").upper(),
            "*",
        ]

        unique_route_keys: list[str] = []
        for key in route_keys:
            if key not in unique_route_keys:
                unique_route_keys.append(key)

        return unique_route_keys

    def _normalize_key(self, value: str) -> str:
        normalized = re.sub(r"(?<!^)(?=[A-Z])", "_", value).upper()
        if normalized.endswith("_EVENT"):
            normalized = normalized.removesuffix("_EVENT")
        return normalized

    async def _send_payload(
        self,
        chat_id: int,
        topic_id: Optional[int],
        payload: MessagePayloadDto,
    ) -> Optional[Message]:
        locale = self.app_config.default_locale
        reply_markup = self._prepare_reply_markup(
            payload.reply_markup,
            payload.disable_default_markup,
            payload.delete_after,
            locale,
            chat_id,
        )
        text = self._get_translated_text(locale, payload.i18n_key, payload.i18n_kwargs)

        kwargs: dict[str, Any] = {
            "disable_notification": payload.disable_notification,
            "message_effect_id": payload.message_effect,
            "reply_markup": reply_markup,
            "message_thread_id": topic_id,
        }

        if payload.is_text:
            message = await self.bot.send_message(
                chat_id=chat_id,
                text=text,
                disable_web_page_preview=True,
                **kwargs,
            )
        elif payload.media:
            method = self._get_media_method(payload)
            media = self._build_media(payload.media)

            if not method:
                logger.warning(f"Unknown media type for topic payload '{payload}'")
                return None

            message = await method(chat_id, media, caption=text, **kwargs)
        else:
            logger.error(f"Topic payload must contain text or media for chat '{chat_id}'")
            return None

        if message and payload.delete_after:
            asyncio.create_task(
                self._schedule_message_deletion(
                    chat_id=chat_id,
                    message_id=message.message_id,
                    delay=payload.delete_after,
                )
            )

        return message

    def _get_media_method(self, payload: MessagePayloadDto) -> Optional[Callable[..., Any]]:
        if payload.is_photo:
            return self.bot.send_photo

        if payload.is_video:
            return self.bot.send_video

        if payload.is_document:
            return self.bot.send_document

        return None

    def _get_translated_text(
        self,
        locale: Locale,
        i18n_key: str,
        i18n_data: dict[str, Any] = {},
    ) -> str:
        if not i18n_key:
            return ""

        i18n = self.translator_hub.get_translator_by_locale(locale)
        translated_text = i18n.get(i18n_key, **i18n_data)

        if i18n_key == "ntf-broadcast.message" and "$" in translated_text and i18n_data:
            template = string.Template(translated_text)
            return template.safe_substitute(i18n_data)

        return translated_text

    def _prepare_reply_markup(
        self,
        reply_markup: Optional[AnyKeyboard],
        disable_default_markup: bool,
        delete_after: Optional[int],
        locale: Locale,
        chat_id: int,
    ) -> Optional[AnyKeyboard]:
        if reply_markup is None:
            if not disable_default_markup and delete_after is None:
                close_button = self._get_close_notification_button(locale=locale)
                return self._get_default_keyboard(close_button)
            return None

        translated_markup = self._translate_keyboard_text(reply_markup, locale)

        if disable_default_markup or delete_after is not None:
            return translated_markup

        if isinstance(translated_markup, InlineKeyboardMarkup):
            builder = InlineKeyboardBuilder.from_markup(translated_markup)
            builder.row(self._get_close_notification_button(locale))
            return builder.as_markup()

        logger.warning(
            f"Unsupported reply_markup type '{type(reply_markup).__name__}' "
            f"for topic chat '{chat_id}', close button skipped"
        )
        return translated_markup

    def _get_close_notification_button(self, locale: Locale) -> InlineKeyboardButton:
        text = self._get_translated_text(locale, "btn-common.notification-close")
        return InlineKeyboardButton(text=text, callback_data=Notification.CLOSE.state)

    def _get_default_keyboard(self, button: InlineKeyboardButton) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder([[button]])
        return builder.as_markup()

    def _translate_keyboard_text(self, keyboard: AnyKeyboard, locale: Locale) -> AnyKeyboard:
        if isinstance(keyboard, InlineKeyboardMarkup):
            i_rows = []
            for i_row in keyboard.inline_keyboard:
                i_buttons = []
                for i_btn in i_row:
                    btn_dict = i_btn.model_dump()
                    btn_dict["text"] = self._get_translated_text(locale, i_btn.text) or i_btn.text
                    i_buttons.append(InlineKeyboardButton(**btn_dict))
                i_rows.append(i_buttons)
            return InlineKeyboardMarkup(inline_keyboard=i_rows)

        if isinstance(keyboard, ReplyKeyboardMarkup):
            r_rows = []
            for r_row in keyboard.keyboard:
                r_buttons = []
                for r_btn in r_row:
                    btn_dict = r_btn.model_dump()
                    btn_dict["text"] = self._get_translated_text(locale, r_btn.text) or r_btn.text
                    r_buttons.append(type(r_btn)(**btn_dict))
                r_rows.append(r_buttons)
            return ReplyKeyboardMarkup(keyboard=r_rows, **keyboard.model_dump(exclude={"keyboard"}))

        return keyboard

    async def _schedule_message_deletion(self, chat_id: int, message_id: int, delay: int) -> None:
        logger.debug(
            f"Schedule topic notification '{message_id}' deletion in chat '{chat_id}' after '{delay}'s"
        )
        await asyncio.sleep(delay)
        await self.delete_notification(chat_id, message_id)

    async def delete_notification(self, chat_id: int, message_id: int) -> None:
        try:
            await self.bot.delete_message(chat_id=chat_id, message_id=message_id)
            logger.debug(f"Topic notification '{message_id}' for chat '{chat_id}' deleted")
        except Exception as e:
            logger.error(f"Failed to delete topic notification '{message_id}': {e}")
            await self._clear_reply_markup(chat_id, message_id)

    async def _clear_reply_markup(self, chat_id: int, message_id: int) -> None:
        try:
            await self.bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=None,
            )
            logger.debug(f"Keyboard removed from topic notification '{message_id}'")
        except Exception as e:
            logger.error(f"Failed to remove keyboard from topic notification '{message_id}': {e}")

    def _build_media(self, media: MediaDescriptorDto) -> Union[str, BufferedInputFile, FSInputFile]:
        if media.kind == "file_id":
            return media.value

        if media.kind == "fs":
            return FSInputFile(
                path=media.value,
                filename=media.filename,
            )

        if media.kind == "bytes":
            return BufferedInputFile(
                file=base64.b64decode(media.value),
                filename=media.filename or "file.bin",
            )

        raise ValueError(f"Unsupported media kind '{media.kind}'")
