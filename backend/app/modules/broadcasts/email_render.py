import html
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from app.core.enums import BroadcastCategory, Locale
from app.core.utils.telegram_text import PREMIUM_EMOJI_RE
from app.modules.broadcasts.content import EMPTY_VALUE, VARIABLE_RE, render_text
from app.modules.broadcasts.dto import (
    BroadcastDto,
    BroadcastEmailContentDto,
    RecipientContextDto,
    RenderedEmailDto,
)
from app.modules.broadcasts.email_html import email_image_ids, email_text, style_email_html
from app.modules.broadcasts.render import FALLBACK_UNSUBSCRIBE, recipient_values
from app.modules.email import EmailBrandDto, brand_accent, render_email_html
from app.modules.users import unsubscribe_token


@dataclass(frozen=True, kw_only=True)
class UnsubscribeLinks:
    page: Callable[[int], str]
    one_click: Callable[[int], str]


def unsubscribe_links(cabinet_url: str, secret: str) -> UnsubscribeLinks:
    base = cabinet_url.rstrip("/")
    return UnsubscribeLinks(
        page=lambda uid: f"{base}/unsubscribe?token={unsubscribe_token(uid, secret)}",
        one_click=lambda uid: f"{base}/api/unsubscribe?token={unsubscribe_token(uid, secret)}",
    )


class BroadcastEmailRenderer:
    def __init__(
        self,
        broadcast: BroadcastDto,
        *,
        promocode_code: Optional[str],
        brand: EmailBrandDto,
        unsubscribe: Optional[UnsubscribeLinks],
        unsubscribe_labels: dict[Locale, str],
        image_src: Callable[[int], str],
    ) -> None:
        self._broadcast = broadcast
        self._promocode_code = promocode_code
        self._brand = brand
        self._unsubscribe = unsubscribe
        self._unsubscribe_labels = unsubscribe_labels
        self._image_src = image_src

    def _content(self, locale: Locale) -> tuple[Locale, BroadcastEmailContentDto]:
        content = self._broadcast.email_contents.get(locale)
        if content is not None:
            return locale, content
        default = self._broadcast.default_locale
        return default, self._broadcast.email_contents[default]

    def render(self, context: RecipientContextDto, now: datetime) -> RenderedEmailDto:
        locale, content = self._content(context.language)
        values = recipient_values(context, now, self._promocode_code)
        # a header is plain text: no HTML escaping, but no line breaks either
        subject = VARIABLE_RE.sub(
            lambda m: values.get(m.group(1)) or EMPTY_VALUE,
            PREMIUM_EMOJI_RE.sub(r"\1", content.subject),
        )
        body = style_email_html(
            render_text(PREMIUM_EMOJI_RE.sub(r"\1", content.html), values),
            accent=brand_accent(self._brand.color),
            image_src=self._image_src,
        )
        text = email_text(body)
        footer = ""
        headers: dict[str, str] = {}
        if self._broadcast.category is BroadcastCategory.MARKETING and self._unsubscribe:
            label = (
                self._unsubscribe_labels.get(locale)
                or self._unsubscribe_labels.get(self._broadcast.default_locale)
                or FALLBACK_UNSUBSCRIBE
            )
            page_url = self._unsubscribe.page(context.user_id)
            footer = (
                f'<a href="{html.escape(page_url, quote=True)}" style="color:#71717a">'
                f"{html.escape(label)}</a>"
            )
            text += f"\n\n{label}: {page_url}"
            headers = {
                "List-Unsubscribe": f"<{self._unsubscribe.one_click(context.user_id)}>",
                "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
            }
        return RenderedEmailDto(
            subject=" ".join(subject.split()),
            html=render_email_html(
                brand=self._brand.brand,
                color=self._brand.color,
                has_logo=self._brand.has_logo,
                body_html=body,
                footer_html=footer,
            ),
            text=text,
            image_ids=email_image_ids(content.html),
            headers=headers,
        )
