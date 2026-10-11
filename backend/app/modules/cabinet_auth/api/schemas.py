from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.core.enums import Locale


class CabinetMethodsResponse(BaseModel):
    telegram_webapp: bool
    telegram_deeplink: bool
    email: bool
    oauth: list[str]

    @field_validator("oauth", mode="before")
    @classmethod
    def _lowercase(cls, value: list[object]) -> list[str]:
        return [str(provider).lower() for provider in value]


class CabinetAuthResponse(BaseModel):
    access_token: str
    expires_in: int


class CabinetProfileResponse(BaseModel):
    id: int
    name: str
    email: Optional[str]
    telegram_id: Optional[int]
    username: Optional[str]
    language: str


class TelegramWebAppLoginRequest(BaseModel):
    init_data: str = Field(max_length=4096)


_EMAIL_PATTERN = r'^[^@\s(),<>;:"]+@[^@\s(),<>;:"]+$'


class RequestEmailCodeRequest(BaseModel):
    email: str = Field(max_length=255, pattern=_EMAIL_PATTERN)
    locale: Locale = Locale.EN
    ref: Optional[str] = Field(None, max_length=64)
    ad: Optional[str] = Field(None, max_length=64)


class VerifyEmailCodeRequest(BaseModel):
    email: str = Field(max_length=255, pattern=_EMAIL_PATTERN)
    code: str = Field(pattern=r"^\d{6}$")


class InviteCodesRequest(BaseModel):
    ref: Optional[str] = Field(None, max_length=64)
    ad: Optional[str] = Field(None, max_length=64)


class DeeplinkResponse(BaseModel):
    bot_url: str
    expires_in: int


class CabinetOAuthAuthorizeResponse(BaseModel):
    url: str


class CabinetOAuthCallbackRequest(BaseModel):
    code: str = Field(max_length=2048)
    state: str = Field(max_length=256)
