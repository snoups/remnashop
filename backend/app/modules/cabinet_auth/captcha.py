from typing import Any, Final, Optional

import httpx
from loguru import logger

from app.core.enums import CaptchaProvider
from app.core.error_codes import ErrorCode
from app.core.exceptions import PermissionDeniedError
from app.modules.settings import CabinetAuthSettingsDto

# both take the same form fields and answer {"success": bool, ...}
_VERIFY_URLS: Final[dict[CaptchaProvider, str]] = {
    CaptchaProvider.TURNSTILE: "https://challenges.cloudflare.com/turnstile/v0/siteverify",
    CaptchaProvider.HCAPTCHA: "https://api.hcaptcha.com/siteverify",
}
_TIMEOUT_S: Final[float] = 5.0


async def _siteverify(url: str, form: dict[str, str]) -> Any:
    async with httpx.AsyncClient(timeout=_TIMEOUT_S, follow_redirects=False) as client:
        response = await client.post(url, data=form)
    response.raise_for_status()
    return response.json()


def _passed(reply: Any, hostname: Optional[str]) -> bool:
    if not isinstance(reply, dict) or reply.get("success") is not True:
        return False
    # solved on another site under the same keys doesn't count
    solved_on = reply.get("hostname")
    return hostname is None or solved_on is None or solved_on == hostname


async def verify_captcha(
    cabinet: CabinetAuthSettingsDto,
    token: Optional[str],
    client_ip: Optional[str],
    hostname: Optional[str],
) -> None:
    if not cabinet.captcha_enabled or cabinet.captcha_secret_key is None:
        return
    if token:
        form = {"secret": cabinet.captcha_secret_key.get_secret_value(), "response": token}
        if client_ip:
            form["remoteip"] = client_ip
        try:
            reply = await _siteverify(_VERIFY_URLS[cabinet.captcha_provider], form)
            if _passed(reply, hostname):
                return
        # an unreachable provider fails closed: the other sign-in methods don't depend on it
        except (httpx.HTTPError, ValueError) as error:
            logger.warning(f"Captcha check via '{cabinet.captcha_provider}' failed: {error!r}")
    raise PermissionDeniedError("Captcha check failed", code=ErrorCode.CAPTCHA_FAILED)
