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


def render_login_code(
    code: str, locale: Locale, brand: EmailBrandDto, cabinet_url: Optional[str]
) -> tuple[str, str, str]:
    subject, title, body = _LOGIN_CODE.get(locale, _LOGIN_CODE[Locale.EN])
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
