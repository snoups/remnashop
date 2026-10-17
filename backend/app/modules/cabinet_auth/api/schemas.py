from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from app.core.constants import EMAIL_PATTERN
from app.core.enums import Locale, Role


class CabinetMethodsResponse(BaseModel):
    telegram_webapp: bool
    telegram_deeplink: bool
    email: bool
    oauth: list[str]
    allowed_email_domains: Optional[list[str]]

    @field_validator("oauth", mode="before")
    @classmethod
    def _lowercase(cls, value: list[object]) -> list[str]:
        return [str(provider).lower() for provider in value]


class CabinetAuthResponse(BaseModel):
    access_token: str
    expires_in: int


class TelegramWebAppLoginRequest(BaseModel):
    init_data: str = Field(max_length=4096)


class RequestEmailCodeRequest(BaseModel):
    email: str = Field(max_length=255, pattern=EMAIL_PATTERN)
    locale: Locale = Locale.EN
    ref: Optional[str] = Field(None, max_length=64)
    ad: Optional[str] = Field(None, max_length=64)


class BotSignInRequest(BaseModel):
    token: str = Field(max_length=128)


class VerifyEmailCodeRequest(BaseModel):
    email: str = Field(max_length=255, pattern=EMAIL_PATTERN)
    code: str = Field(pattern=r"^\d{6}$")


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
