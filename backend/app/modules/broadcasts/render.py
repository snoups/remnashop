from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Final, Optional

from fluent_compiler.bundle import FluentBundle
from loguru import logger

from app.core.constants import T_ME
from app.core.enums import BroadcastButtonKind, Locale
from app.modules.broadcasts.content import render_text
from app.modules.broadcasts.dto import (
    BroadcastButtonDto,
    BroadcastContentDto,
    BroadcastDto,
    RecipientContextDto,
)
from app.modules.broadcasts.storage import media_path
from app.modules.broadcasts.telegram_api import OutgoingMedia
from app.modules.subscriptions import is_unlimited_expiry
from app.modules.translations import TranslationRepository

UNSUBSCRIBE_KEY: Final[str] = "btn-broadcast.unsubscribe"
FALLBACK_UNSUBSCRIBE: Final[str] = "Unsubscribe"
_DATE_FORMAT: Final[str] = "%d.%m.%Y"
_MENU_START_PAYLOAD: Final[str] = "menu"


@dataclass(frozen=True, kw_only=True)
class RenderedMessage:
    text: str
    reply_markup: Optional[dict[str, Any]]


def recipient_values(
    context: RecipientContextDto, now: datetime, promocode_code: Optional[str]
) -> dict[str, str]:
    # an unlimited subscription has no date to show: the line holding it drops
    expire_at = (
        None
        if context.expire_at is None or is_unlimited_expiry(context.expire_at)
        else context.expire_at
    )
    return {
        "name": context.name,
        "username": f"@{context.username}" if context.username else "",
        "plan": context.plan_name or "",
        "expire_date": expire_at.strftime(_DATE_FORMAT) if expire_at else "",
        "days_left": str(max((expire_at - now).days, 0)) if expire_at else "",
        "bonus_days": str(context.bonus_days),
        "points": str(context.points),
        "promocode": promocode_code or "",
    }


class BroadcastRenderer:
    def __init__(
        self,
        broadcast: BroadcastDto,
        *,
        promocode_code: Optional[str],
    ) -> None:
        self._broadcast = broadcast
        self._promocode_code = promocode_code

    def _content(self, locale: Locale) -> tuple[Locale, BroadcastContentDto]:
        content = self._broadcast.contents.get(locale)
        if content is not None:
            return locale, content
        default = self._broadcast.default_locale
        return default, self._broadcast.contents[default]

    def _action(
        self, button: BroadcastButtonDto, *, channel: bool, link: Optional[str]
    ) -> Optional[dict[str, str]]:
        if button.kind is BroadcastButtonKind.URL and button.url:
            return {"url": button.url}
        if button.kind is BroadcastButtonKind.PROMOCODE and self._promocode_code:
            if not channel:
                return {"callback_data": f"bc:promo:{self._broadcast.id}"}
            if link:
                return {"url": f"{link}?start=bc_{self._broadcast.id}"}
        if button.kind is BroadcastButtonKind.MENU:
            if not channel:
                return {"callback_data": "bc:menu"}
            if link:
                return {"url": f"{link}?start={_MENU_START_PAYLOAD}"}
        return None

    def _keyboard(
        self,
        labels: list[str],
        *,
        channel: bool = False,
        bot_username: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        rows: list[list[dict[str, str]]] = []
        link = f"{T_ME}{bot_username}" if bot_username else None
        for button, label in zip(self._broadcast.buttons, labels, strict=True):
            action = self._action(button, channel=channel, link=link)
            if action is None:
                continue
            if button.icon_custom_emoji_id:
                action["icon_custom_emoji_id"] = button.icon_custom_emoji_id
            rows.append([{"text": label, **action}])
        return {"inline_keyboard": rows} if rows else None

    def render(self, context: RecipientContextDto, now: datetime) -> RenderedMessage:
        # no unsubscribe button in Telegram for now: a marketing email carries its unsubscribe link,
        # the bot keeps answering bc:unsub for messages sent before
        _, content = self._content(context.language)
        values = recipient_values(context, now, self._promocode_code)
        return RenderedMessage(
            text=render_text(content.text, values),
            reply_markup=self._keyboard(content.button_labels),
        )

    def render_channel(self, bot_username: Optional[str]) -> RenderedMessage:
        content = self._broadcast.contents[self._broadcast.default_locale]
        return RenderedMessage(
            text=render_text(content.text, {"promocode": self._promocode_code or ""}),
            reply_markup=self._keyboard(
                content.button_labels, channel=True, bot_username=bot_username
            ),
        )


async def load_unsubscribe_labels(
    translation_repository: TranslationRepository, locales: list[Locale]
) -> dict[Locale, str]:
    texts = await translation_repository.get_fluent_text_by_locale(locales)
    labels: dict[Locale, str] = {}
    for locale, text in texts.items():
        bundle = FluentBundle.from_string(locale.value, text, use_isolating=False)  # type: ignore[no-untyped-call]
        try:
            value, errors = bundle.format(UNSUBSCRIBE_KEY, {})
        except KeyError:
            continue
        for error in errors:
            logger.warning(f"Broadcast unsubscribe label ({locale}): {error}")
        labels[locale] = str(value)
    return labels


def outgoing_media(media_dir: Path, broadcast: BroadcastDto) -> Optional[OutgoingMedia]:
    if broadcast.media_type is None or broadcast.media_extension is None:
        return None
    return OutgoingMedia(
        media_type=broadcast.media_type,
        file_id=broadcast.media_file_id,
        path=media_path(
            media_dir, broadcast.id, broadcast.media_version, broadcast.media_extension
        ),
        content_type=broadcast.media_content_type,
    )
