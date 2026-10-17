from typing import Final, Optional

from app.core.enums import Locale
from app.modules.email.dto import EmailBrandDto
from app.modules.email.layout import render_email

# (subject, title, body) per locale; {code} is the only placeholder
_LOGIN_CODE: Final[dict[Locale, tuple[str, str, str]]] = {
    Locale.EN: (
        "Your sign-in code: {code}",
        "Your sign-in code: {code}",
        "The code is valid for 10 minutes.",
    ),
    Locale.RU: (
        "Код для входа: {code}",
        "Код для входа: {code}",
        "Код действует 10 минут.",
    ),
}

_LINK_CODE: Final[dict[Locale, tuple[str, str, str]]] = {
    Locale.EN: (
        "Your linking code: {code}",
        "Your linking code: {code}",
        "Enter it in the cabinet to add this email to your account. "
        "The code is valid for 10 minutes.",
    ),
    Locale.RU: (
        "Код для привязки почты: {code}",
        "Код для привязки почты: {code}",
        "Введите его в кабинете, чтобы добавить эту почту к аккаунту. Код действует 10 минут.",
    ),
}


def _render_code(
    texts: dict[Locale, tuple[str, str, str]],
    code: str,
    locale: Locale,
    brand: EmailBrandDto,
    cabinet_url: Optional[str],
) -> tuple[str, str, str]:
    subject, title, body = texts.get(locale, texts[Locale.EN])
    text, html = render_email(
        brand=brand.brand,
        color=brand.color,
        has_logo=brand.has_logo,
        title=title.format(code=code),
        body=body,
        cabinet_url=cabinet_url,
        button=None,
    )
    return subject.format(code=code), text, html


def render_login_code(
    code: str, locale: Locale, brand: EmailBrandDto, cabinet_url: Optional[str]
) -> tuple[str, str, str]:
    return _render_code(_LOGIN_CODE, code, locale, brand, cabinet_url)


def render_link_code(
    code: str, locale: Locale, brand: EmailBrandDto, cabinet_url: Optional[str]
) -> tuple[str, str, str]:
    return _render_code(_LINK_CODE, code, locale, brand, cabinet_url)
