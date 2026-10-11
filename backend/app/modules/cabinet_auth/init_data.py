import hashlib
import hmac
import json
from typing import Final, Optional
from urllib.parse import parse_qsl

from app.core.constants import TIME_1D
from app.core.error_codes import ErrorCode
from app.core.exceptions import AuthenticationError
from app.modules.cabinet_auth.dto import InviteCodesDto, TelegramProfileDto, TelegramWebAppDataDto

_REFERRAL_PREFIX: Final[str] = "ref_"
_AD_LINK_PREFIX: Final[str] = "ad_"
_CLOCK_SKEW_S: Final[int] = 60
_TEXT_FIELDS: Final[tuple[str, ...]] = (
    "first_name",
    "last_name",
    "username",
    "language_code",
)


def _invalid() -> AuthenticationError:
    return AuthenticationError("Invalid Telegram init data", code=ErrorCode.INVALID_INIT_DATA)


def verify_init_data(
    init_data: str, bot_token: str, now: int, max_age: int = TIME_1D
) -> TelegramWebAppDataDto:
    fields = dict(parse_qsl(init_data, keep_blank_values=True))
    presented = fields.pop("hash", None)
    if not presented:
        raise _invalid()
    data_check = "\n".join(f"{key}={value}" for key, value in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(presented, expected):
        raise _invalid()
    try:
        auth_date = int(fields["auth_date"])
        user = json.loads(fields["user"])
        telegram_id = int(user["id"])
    except (KeyError, ValueError, TypeError):
        raise _invalid() from None
    # a non-object `user` already failed on user["id"] above
    if any(not isinstance(user.get(key) or "", str) for key in _TEXT_FIELDS):
        raise _invalid()
    if not -_CLOCK_SKEW_S <= now - auth_date <= max_age:
        raise _invalid()
    name = " ".join(filter(None, (user.get("first_name"), user.get("last_name"))))
    return TelegramWebAppDataDto(
        profile=TelegramProfileDto(
            telegram_id=telegram_id,
            name=name,
            username=user.get("username"),
            language=user.get("language_code"),
        ),
        start_param=fields.get("start_param"),
    )


def codes_from_start_param(start_param: Optional[str]) -> InviteCodesDto:
    if start_param and start_param.startswith(_REFERRAL_PREFIX):
        return InviteCodesDto(referral_code=start_param[len(_REFERRAL_PREFIX) :] or None)
    if start_param and start_param.startswith(_AD_LINK_PREFIX):
        return InviteCodesDto(ad_link_code=start_param[len(_AD_LINK_PREFIX) :] or None)
    return InviteCodesDto()
