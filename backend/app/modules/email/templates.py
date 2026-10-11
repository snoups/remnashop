from typing import Final

from app.core.enums import Locale

# (subject, text, html) per locale; {code} is the only placeholder
_LOGIN_CODE: Final[dict[Locale, tuple[str, str, str]]] = {
    Locale.EN: (
        "Your sign-in code: {code}",
        "Your sign-in code: {code}\nThe code is valid for 10 minutes.",
        "<p>Your sign-in code: <strong>{code}</strong></p><p>The code is valid for 10 minutes.</p>",
    ),
    Locale.RU: (
        "Код для входа: {code}",
        "Код для входа: {code}\nКод действует 10 минут.",
        "<p>Код для входа: <strong>{code}</strong></p><p>Код действует 10 минут.</p>",
    ),
}


def render_login_code(code: str, locale: Locale) -> tuple[str, str, str]:
    subject, text, html = _LOGIN_CODE.get(locale, _LOGIN_CODE[Locale.EN])
    return subject.format(code=code), text.format(code=code), html.format(code=code)
