from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from app.core.constants import EMAIL_PATTERN
from app.core.enums import CaptchaProvider, Locale, Role
from app.core.utils.validators import known_locale


class CaptchaWidgetResponse(BaseModel):
    provider: CaptchaProvider
    site_key: str


class CabinetMethodsResponse(BaseModel):
    telegram_webapp: bool
    telegram_deeplink: bool
    email: bool
    oauth: list[str]
    allowed_email_domains: Optional[list[str]]
    captcha: Optional[CaptchaWidgetResponse]

    @field_validator("oauth", mode="before")
    @classmethod
    def _lowercase(cls, value: list[object]) -> list[str]:
        return [str(provider).lower() for provider in value]


class CabinetAuthResponse(BaseModel):
    access_token: str
    expires_in: int


class TelegramWebAppLoginRequest(BaseModel):
    init_data: str = Field(max_length=4096)
    legal_locale: Optional[Locale] = None

    _legal_locale = field_validator("legal_locale", mode="before")(known_locale)


class RequestEmailCodeRequest(BaseModel):
    email: str = Field(max_length=255, pattern=EMAIL_PATTERN)
    locale: Locale = Locale.EN
    ref: Optional[str] = Field(None, max_length=64)
    ad: Optional[str] = Field(None, max_length=64)
    captcha_token: Optional[str] = Field(None, max_length=4096)


class BotSignInRequest(BaseModel):
    token: str = Field(max_length=128)
    legal_locale: Optional[Locale] = None

    _legal_locale = field_validator("legal_locale", mode="before")(known_locale)


class VerifyEmailCodeRequest(BaseModel):
    email: str = Field(max_length=255, pattern=EMAIL_PATTERN)
    code: str = Field(pattern=r"^\d{6}$")
    legal_locale: Optional[Locale] = None

    _legal_locale = field_validator("legal_locale", mode="before")(known_locale)


class InviteCodesRequest(BaseModel):
    ref: Optional[str] = Field(None, max_length=64)
    ad: Optional[str] = Field(None, max_length=64)


class DeeplinkResponse(BaseModel):
    bot_url: str
    expires_in: int


class OAuthAuthorizeRequest(BaseModel):
    audience: Literal["dashboard", "cabinet"]
    ref: Optional[str] = Field(None, max_length=64)
    ad: Optional[str] = Field(None, max_length=64)


class OAuthAuthorizeResponse(BaseModel):
    url: str


class OAuthSignInResponse(BaseModel):
    access_token: str
    expires_in: int
    id: int
    login: Optional[str]
    role: Role


class OAuthCallbackRequest(BaseModel):
    code: str = Field(max_length=2048)
    state: str = Field(max_length=256)
    legal_locale: Optional[Locale] = None

    _legal_locale = field_validator("legal_locale", mode="before")(known_locale)
