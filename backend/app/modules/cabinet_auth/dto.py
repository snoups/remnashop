from dataclasses import dataclass
from enum import StrEnum, auto
from typing import Optional

from app.core.enums import Locale, OAuthProvider


@dataclass(frozen=True, kw_only=True)
class CabinetMethodsDto:
    telegram_webapp: bool
    telegram_deeplink: bool
    email: bool
    oauth: list[OAuthProvider]


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
class TelegramWebAppDataDto:
    profile: TelegramProfileDto
    start_param: Optional[str]


@dataclass(frozen=True, kw_only=True)
class EmailCodeGrantDto:
    codes: InviteCodesDto
    locale: Locale


class DeeplinkStatus(StrEnum):
    PENDING = auto()
    EXPIRED = auto()
    CONFIRMED = auto()


@dataclass(frozen=True, kw_only=True)
class DeeplinkPendingDto:
    codes: InviteCodesDto
    client_ip: str
    user_agent: str


@dataclass(frozen=True, kw_only=True)
class DeeplinkResult:
    status: DeeplinkStatus
    profile: Optional[TelegramProfileDto] = None
    codes: Optional[InviteCodesDto] = None


@dataclass(frozen=True, kw_only=True)
class DeeplinkTicketDto:
    bot_url: str
    binding: str
    expires_in: int
