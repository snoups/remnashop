from dataclasses import dataclass
from typing import Optional

from app.core.enums import Locale, OAuthProvider


@dataclass(frozen=True, kw_only=True)
class CabinetMethodsDto:
    telegram_webapp: bool
    telegram_deeplink: bool
    email: bool
    oauth: list[OAuthProvider]
    allowed_email_domains: Optional[list[str]]


@dataclass(frozen=True, kw_only=True)
class InviteCodesDto:
    referral_code: Optional[str] = None
    ad_link_code: Optional[str] = None


@dataclass(frozen=True, kw_only=True)
class TelegramProfileDto:
    telegram_id: int
    name: str
    username: Optional[str]
    language: Optional[str]


@dataclass(frozen=True, kw_only=True)
class StartTicketDto:
    codes: InviteCodesDto
    # set when the cabinet asked to link Telegram to this account rather than sign in
    link_user_id: Optional[int] = None


@dataclass(frozen=True, kw_only=True)
class BotSignInGrantDto:
    profile: TelegramProfileDto
    codes: InviteCodesDto
    link_user_id: Optional[int] = None


@dataclass(frozen=True, kw_only=True)
class TelegramWebAppDataDto:
    profile: TelegramProfileDto
    start_param: Optional[str]


@dataclass(frozen=True, kw_only=True)
class EmailCodeGrantDto:
    codes: InviteCodesDto
    locale: Locale


@dataclass(frozen=True, kw_only=True)
class DeeplinkTicketDto:
    bot_url: str
    expires_in: int
