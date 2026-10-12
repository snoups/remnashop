import html
import re
from typing import Final, Optional, Protocol

from app.modules.email.dto import EmailBrandDto
from app.modules.settings import AppearanceSettingsDto

_COLOR: Final[re.Pattern[str]] = re.compile(r"^#[0-9a-fA-F]{6}$")
_DEFAULT_COLOR: Final[str] = "#3b82f6"
_DEFAULT_BRAND: Final[str] = "remnashop"


class _AppearanceSource(Protocol):
    async def get_appearance_settings(self) -> AppearanceSettingsDto: ...


async def load_email_brand(settings_repository: _AppearanceSource) -> EmailBrandDto:
    appearance = await settings_repository.get_appearance_settings()
    return EmailBrandDto(
        brand=appearance.brand_name or _DEFAULT_BRAND,
        color=appearance.primary_color,
        has_logo=appearance.has_logo,
    )


def render_email(
    *,
    brand: str,
    color: Optional[str],
    has_logo: bool,
    title: str,
    body: str,
    cabinet_url: Optional[str],
    button: Optional[str],
) -> tuple[str, str]:
    accent = color if color and _COLOR.fullmatch(color) else _DEFAULT_COLOR
    safe_body = "<br>".join(html.escape(line) for line in body.split("\n"))
    logo = (
        '<img src="cid:logo" alt="" height="40" style="display:block;margin:0 auto 16px">'
        if has_logo
        else ""
    )
    action = ""
    if cabinet_url and button:
        action = (
            f'<p style="margin:24px 0 0"><a href="{html.escape(cabinet_url, quote=True)}" '
            f'style="background:{accent};color:#fff;padding:10px 20px;border-radius:999px;'
            f'text-decoration:none;display:inline-block">{html.escape(button)}</a></p>'
        )
    page = (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="background:#f4f4f5;padding:24px 0"><tr><td align="center">'
        '<table role="presentation" width="480" cellpadding="0" cellspacing="0" '
        'style="background:#fff;border-radius:16px;padding:32px;'
        'font-family:Arial,sans-serif;color:#18181b">'
        f'<tr><td align="center">{logo}'
        f'<h1 style="font-size:20px;margin:0 0 16px">{html.escape(title)}</h1>'
        f'<p style="font-size:15px;line-height:1.5;margin:0">{safe_body}</p>{action}'
        f'<p style="font-size:12px;color:#71717a;margin:32px 0 0">{html.escape(brand)}</p>'
        "</td></tr></table></td></tr></table>"
    )
    text = "\n\n".join(part for part in (title, body, cabinet_url or "") if part)
    return text, page
